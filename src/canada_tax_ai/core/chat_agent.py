
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import json
from typing import Literal

from canada_tax_ai.models import TaxInputData, UserProfile,to_tax_input
from canada_tax_ai.prompt.tax_advisor import advisor_message
from .llm import get_llm
from .agent_state import AgentState
from ..prompt.prompt_registry import sys_prompt,temp_prompt
from ..tools.tools import  save_profile, update_profile_data, update_tax_data, verify_addresss
from loguru import logger

tools = [verify_addresss,update_tax_data,update_profile_data]  # tool names for LLM to call

llm = get_llm(tools=tools)


# Helper function (add this once, anywhere before the graph)
def _is_user_profile_complete(state: AgentState) -> bool:
    """Return True ONLY when UserProfile is complete AND the last message is NOT a tool result"""
    print("Checking if UserProfile is complete...")
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

def _update_tax_input_from_dict(existing: TaxInputData, updates: dict) -> TaxInputData:
    """
    Update existing TaxInputData with a partial dict of new values.
    Only updates fields present in the dict — all other fields unchanged.
    """
    if not updates:
        return existing
    inp = to_tax_input(existing)  # Ensure we have a TaxInputData instance to start with
    current = inp.model_dump()

    for field, value in updates.items():
        if field not in current:
            logger.warning(f"⚠ Unknown field '{field}' — skipped")
            continue
        if value is not None:
            logger.info(f"  ✅ {field}: {current.get(field)} → {value}")
            current[field] = value
    # return current
    return TaxInputData(**current)

def chat_node(state: AgentState):

    profile = state.get("profile", UserProfile())
    knowledge_json = json.dumps(state.get("knowledge", {}), ensure_ascii=False, indent=2)
    profile_json = profile.model_dump_json(indent=2)
    
    existing = state.get("tax_input_data", {})
    logger.info(f"Current tax input data: {existing}")

    system_message = SystemMessage(content=temp_prompt("user_profile", "v1",knowledge_json=knowledge_json, profile_json=profile_json))
    # input_messages = [system_message] + state["messages"]

    input_messages = advisor_message(state) + state["messages"]
    logger.info(f"System message for LLM:\n{input_messages}")
    if(_is_user_profile_complete(state)):
        logger.info("UserProfile is complete. Generating advisor message...")
        save_profile(profile)  # Auto-save complete profile to DB

    agent = create_agent(llm, tools)# LLM do not invoke tools directly, it will return a special message indicating which tool to call and with what arguments. The router will parse that message and call the corresponding tool, then feed the tool result back into the conversation.
    response = agent.invoke({"messages": input_messages})
    
    ai_messages = [m for m in response["messages"] if isinstance(m, AIMessage)]
    last_ai = ai_messages[-1]

    logger.info(f"LLM response: {response}")
    new_messages = state["messages"] + [AIMessage(content=last_ai.content)]
    
    # Auto-extract memory update from LLM response
    knowledge = state.get("knowledge", {})
    if "[Memory Update]" in last_ai.content:
        try:
            update_part = last_ai.content.split("[Memory Update]")[1].strip()
            update_dict = json.loads(update_part)
            knowledge.update(update_dict)
            
            logger.info(f"Current profile before update: {profile.model_dump_json(indent=2)}")
            profile = profile.model_copy(update=update_dict)
        except:
            pass  # parsing failed, continue anyway
    

    tool_call_message = next(
        (m for m in reversed(response["messages"]) if isinstance(m, AIMessage) and m.tool_calls),
        None
    )

    tax_input = state.get("tax_input_data") if state.get("tax_input_data") else TaxInputData()

    # Handle tool calls manually
    if tool_call_message:
        if tool_call_message.tool_calls:
            logger.info(f"Tool calls detected in LLM response: {tool_call_message.tool_calls}")
            for tool_call in tool_call_message.tool_calls:
                name = tool_call["name"]
                args = tool_call["args"]

                if name == "update_tax_data":
                    # ✅ Build TaxInputData and update state directly
                    tax_data = TaxInputData(**args)
                    data = tax_data.model_dump(exclude_none=True)

                    tax_input = _update_tax_input_from_dict(tax_input, data)
                    # state_updates["tax_input_data"] = data  # ✅ returned from node
                    logger.info(f"✅ tax_input_data updated in node: {tax_input.model_dump(exclude_none=True)}")
                if name == "update_profile_data":
                    # ✅ Build UserProfile and update state directly
                    profile_data = UserProfile(**args)
                    data = profile_data.model_dump(exclude_none=True)

                    profile = profile.model_copy(update=data)
                    logger.info(f"✅ profile updated in node: {profile.model_dump_json(indent=2)}")
                # add other tools here...

    # ✅ Node returns all state updates including tax_input_data
    return {
        **state,
        "messages": new_messages,
        "knowledge": knowledge,
        "profile": profile,
        "tax_input_data": tax_input # ✅ include updated tax input data in state
    }
