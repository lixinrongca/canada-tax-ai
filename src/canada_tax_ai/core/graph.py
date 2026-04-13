# src/canada_tax_ai/graph.py （已修复版）
from typing import TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
import json

from canada_tax_ai.models import UserProfile
from ..tools.tools import canadian_tax_calculator, end_chain, query_cra_rules, save_userprofile_to_db
from .llm import get_llm
from .agent_state import AgentState


llm = get_llm()

tools = [save_userprofile_to_db]
tool_node = ToolNode(tools)

SYSTEM_PROMPT = """You are a professional financial expert assisting the user with preparing their personal income tax return (Canada CRA is the default; if the user is in another country, confirm the tax authority first).  
Follow this exact order. Ask ONE question at a time, keep your tone friendly, professional, and concise. Only move to the next question after the user answers. Never dump all questions at once.  
Ask every item and confirm nothing is missing before summarizing.

1. Basic Identity  
   - What is your full name, date of birth, SIN (Social Insurance Number), and current address?

2. Family Situation  
   - What is your marital status (single / married / common-law / separated / divorced / widowed)? Do you have any children under 18 or other dependents? (Please provide names, dates of birth, and relationship.)

3. Income Information  
   - What were all your income sources for 2025? Please provide the amounts or scanned copies of T4, T5, T4A, or any other income slips. (Employment, self-employment, investment, rental, pension, foreign income, etc.)

4. Deductions & Credits  
   - Do you have any of the following deductible or creditable items? (Confirm one by one)  
     • Medical expenses, prescriptions, dental  
     • Charitable donations  
     • Child care expenses  
     • Home office / work-related expenses (self-employed only)  
     • Tuition, training, RRSP / TFSA contributions  
     • Other (moving, disability, caregiver, etc.)

5. Assets & Special Situations  
   - Do you own any real estate, investment accounts, cryptocurrency, or foreign assets?  
   - Any immigration, study-abroad, foreign income, or other tax events that need special handling?

6. Previous Year Status  
   - Did you file your 2024 tax return? Did you receive any CRA notice for refund or balance owing?

7. Documents & Filing Preference  
   - Please provide all supporting documents (T-slips, receipts, bank statements, etc.).  
   - How would you like to file? (NETFILE, paper, or shall I prepare the TurboTax / StudioTax file for you?)


After every question has been answered and confirmed complete, reply:  
“Information collection is complete. Please wait while I organize your return summary and any optimization suggestions.
"""
VERIFY_PROMPT = """
Core rules (must be followed strictly):
1. The UserProfile entities are automatically updated from every user message and tool result using direct reflection.
2. For UserProfile entity:
   - If ANY property is blank, empty, or missing, ask the user for the missing properties (maximum 1-2 questions at a time).
   - Only when ALL properties have values, send a clear summary and ask: "Is this correct? Reply YES or provide any corrections."
3. Never ask again about any property or topic that is already confirmed.
4. Call tool save_userprofile_to_db to save UserProfile to DB once it is complete.
5. Always keep the tone friendly, professional, and concise. Never ask multiple questions at once.
6. At the end of every reply, you MUST output:
   [Memory Update]
   Strictly output ONLY a single valid JSON object that exactly conforms to the Pydantic schema of the UserProfile models defined below, with no additional text, explanations, markdown, or code blocks before or after the JSON.
   class UserProfile(BaseModel):
    last_name: str 
    first_name: str 
    phone_number: str
    date_of_birth: str 
    address: str 
    marital_status: str 
    dependents: List[Dict] 
    sin: str 

Current knowledge base:
{knowledge_json}


Current UserProfile entity:
{profile_json}

Update entities with any new property values.
Keep all previous values unless explicitly updated.
"""
def verifier_node(state: AgentState):

    profile = state.get("profile", UserProfile())
    knowledge_json = json.dumps(state.get("knowledge", {}), ensure_ascii=False, indent=2)
    profile_json = profile.model_dump_json(indent=2)

    
    system_message = SystemMessage(
        content=VERIFY_PROMPT.format(knowledge_json=knowledge_json, profile_json=profile_json)
    )
    input_messages = [system_message] + state["messages"]

    response = llm.invoke(input_messages)
    # structured_llm = llm.with_structured_output(UserProfile)
    # response = structured_llm.invoke(input_messages)
    
    new_messages = state["messages"] + [AIMessage(content=response.content)]
    
    # Auto-extract memory update from LLM response
    knowledge = state.get("knowledge", {})
    if "[Memory Update]" in response.content:
        try:
            update_part = response.content.split("[Memory Update]")[1].strip()
            update_dict = json.loads(update_part)
            knowledge.update(update_dict)
            
            print("Current profile before update:", profile.model_dump_json(indent=2))
            profile = profile.model_copy(update=update_dict)
        except:
            pass  # parsing failed, continue anyway
    
    return {
        "messages": new_messages,
        "knowledge": knowledge,
        "profile": profile
    }
# Helper function (add this once, anywhere before the graph)
def is_user_profile_complete(state: AgentState) -> bool:
    """Return True ONLY when UserProfile is complete AND the last message is NOT a tool result"""
    user = state.get("profile", {})
    if not user:
        return False
    
    # Check if ALL fields are filled
    all_filled = True
    for field in UserProfile.model_fields:
        value = user.get(field) if isinstance(user, dict) else getattr(user, field, None)
        if value in (None, "", "None", "null", {}):
            all_filled = False
            break
    
    # Prevent loop: if the last message is already a ToolMessage (save just happened), stop
    last_msg = state["messages"][-1] if state["messages"] else None
    if isinstance(last_msg, ToolMessage):
        print(f"Checking profile completeness: all_filled={all_filled}, last_msg_type={type(last_msg).__name__}")
        return False
    
    return all_filled


workflow = StateGraph(AgentState)

workflow.add_node("verifier", verifier_node)
# workflow.add_node("db", tool_node)
workflow.add_node("db", save_userprofile_to_db)
workflow.add_node("end", end_chain)
workflow.add_edge(START, "verifier")
workflow.add_conditional_edges(
    "verifier",
    lambda state: "db" if is_user_profile_complete(state) else END
)
workflow.add_edge("db", "end")

# Persistent memory (cross-session)
checkpointer = MemorySaver()   # Production: use PostgresSaver or Redis

app = workflow.compile(checkpointer=checkpointer)

def chat(user_input: str, thread_id: str = "t4_project"):
    config = {"configurable": {"thread_id": thread_id}}
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ]
    result = app.invoke({
        "messages": messages
    }, config=config)

    #TODO fix error no attribute content for messages[-1] when the last message is a tool result (ToolMessage)
    if isinstance(result["messages"][-1], str):
        ai_reply = result["messages"]
    else:        
        ai_reply = result["messages"][-1].content
    current_knowledge = result["knowledge"]
    
    print("🤖 AI:", ai_reply)
    print("Current knowledge base:", current_knowledge)
    print(f"📚 Current knowledge base size: {len(current_knowledge)} items")
    
    # Optional: save knowledge base to file
    with open(f"knowledge_{thread_id}.json", "w", encoding="utf-8") as f:
        json.dump(current_knowledge, f, ensure_ascii=False, indent=2)
    
    return ai_reply