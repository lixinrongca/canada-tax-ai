# src/canada_tax_ai/graph.py 
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import json
from typing import Literal
from canada_tax_ai.models import UserProfile
from canada_tax_ai.route.embedding_route import cosine_similarity_router
from ..tools.tools import  confirm_profile, end_node, query_profile, query_cra_rules, save_to_db,query_tax_slips
from .agent_state import AgentState
from ..prompt.prompt_registry import sys_prompt,temp_prompt
from .document_agent import document_node
from .chat_agent import chat_node
from ..tools.tax_tools import calculate_tax
from loguru import logger
import streamlit as st


tools = [query_tax_slips, query_profile, query_cra_rules]
tool_node = ToolNode(tools)

user_thread_id = st.session_state.get("username", "tax_project")


SYSTEM_PROMPT = sys_prompt("user_profile", "v1")

# def _route_initial(
#         state: AgentState,
#     ) -> Literal["document_node", "router_node"]:
#         """According to the initial message, route to document_agent if it's about tax slip extraction, otherwise route to chat_agent."""
#         # TODO: this is a very naive routing based on keywords. In production, consider using a small classifier model or embedding-based similarity search for more robust routing.
#         return state.get("next_tool")

def _route_initial(state: AgentState):
    # process_document() sets file_path, process_chat() doesn't
    if state.get("file_path"):
        return "document_node"
    return "router_node"

# Helper function (add this once, anywhere before the graph)
def _is_user_profile_complete(state: AgentState) -> bool:
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
        logger.info(f"Checking profile completeness: all_filled={all_filled}, last_msg_type={type(last_msg).__name__}")
        return False
    
    logger.info(f"Checking if UserProfile is complete... {all_filled}")
    return all_filled


workflow = StateGraph(AgentState)
workflow.add_node("chat_node", chat_node)
# workflow.add_node("db", save_to_db)
workflow.add_node("end", end_node)
workflow.add_node("confirm_profile", confirm_profile)

workflow.add_node("document_node", document_node)
workflow.add_node("calculate_tax", calculate_tax)

workflow.add_node("router_node", lambda state: {
    # **state,
    "next_tool": cosine_similarity_router(state["messages"][-1].content)
})
# workflow.add_node("start_node", start_node)

workflow.add_node("query_tax_slips", query_tax_slips)
workflow.add_node("query_profile", query_profile)
workflow.add_node("Testquery", query_cra_rules)

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # 
# workflow.add_edge(START, "start_node")
workflow.add_conditional_edges(START, _route_initial, ["document_node", "router_node"])
workflow.add_edge("document_node", "calculate_tax")
workflow.add_edge("calculate_tax", END)

# workflow.add_edge("chat_node", "router")
workflow.add_conditional_edges(
    "router_node",
    lambda state: state.get("next_tool", "general_chat"),  # default to general_chat if router fails
    {
        "tax_slips": "query_tax_slips",
        "user_profile": "query_profile",
        "report_generation": "Testquery",
        "general_chat": "chat_node"
    }
)
workflow.add_conditional_edges(
    "chat_node",
    lambda state: "calculate_tax" if _is_user_profile_complete(state) else END
)

# workflow.add_conditional_edges(
#     "chat_node",
#     lambda state: "db" if _is_user_profile_complete(state) else END
# )
# workflow.add_edge("db", "end")


# Persistent memory (cross-session)
checkpointer = MemorySaver()   # Production: use PostgresSaver or Redis

app = workflow.compile(checkpointer=checkpointer)

def process_chat(user_input: str, thread_id: str = "tax_project"):
    config = {"configurable": {"thread_id": user_thread_id}}
    messages = [
        # SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ]
    result = app.invoke({
        "messages": messages,
        # "next_tool": "router_node",  # start with router to decide the path
    }, config=config)

    #TODO fix error no attribute content for messages[-1] when the last message is a tool result (ToolMessage)
    logger.info(f"Chat processing result: {result}")
    if isinstance(result["messages"][-1], str):
        ai_reply = result["messages"]
    elif isinstance(result["messages"][-1], dict):  #for tax slip query results, which return dict with "messages" and "knowledge"
        ai_reply = result["messages"][-1]
    else:      
        ai_reply = result["messages"][-1].content
    current_knowledge = result["knowledge"]
    
    logger.info(f"🤖 AI: {ai_reply}")
    logger.info(f"Current knowledge base: {current_knowledge}")
    logger.info(f"📚 Current knowledge base size: {len(current_knowledge)} items")
    
    # Optional: save knowledge base to file
    with open(f"knowledge_{thread_id}.json", "w", encoding="utf-8") as f:
        json.dump(current_knowledge, f, ensure_ascii=False, indent=2)
    tax_result = result.get("tax_result", None)
    return {"messages": ai_reply,
            "tax_result": tax_result,}

def process_document(file_path: str,thread_id: str = "tax_project"):
    config = {"configurable": {"thread_id": user_thread_id}}
    
    result = app.invoke({
        "messages": [HumanMessage(content=f"Process tax document at {file_path}")],
        "file_path": file_path,
        # "next_tool": "document_node",
    }, config=config)

    logger.info(f"Document processing result: {result}")
    return result