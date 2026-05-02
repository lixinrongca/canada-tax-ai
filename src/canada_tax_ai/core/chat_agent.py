
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import json
from typing import Literal

from canada_tax_ai.models import UserProfile
from .llm import get_llm
from .agent_state import AgentState
from ..prompt.prompt_registry import sys_prompt,temp_prompt
from ..tools.tools import  verify_addresss
from loguru import logger

tools = [verify_addresss]  # tool names for LLM to call

llm = get_llm(tools=tools)

def chat_node(state: AgentState):

    profile = state.get("profile", UserProfile())
    knowledge_json = json.dumps(state.get("knowledge", {}), ensure_ascii=False, indent=2)
    profile_json = profile.model_dump_json(indent=2)
    
    system_message = SystemMessage(
        content=temp_prompt("user_profile", "v1",knowledge_json=knowledge_json, profile_json=profile_json)
    )
    input_messages = [system_message] + state["messages"]

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
    
    return {
        "messages": new_messages,
        "knowledge": knowledge,
        "profile": profile
    }
