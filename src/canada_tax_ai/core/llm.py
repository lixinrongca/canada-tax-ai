# core/llm.py
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from ..config import config


_llm = None

def get_llm(tools=None):
    global _llm

    if _llm is None:
        _llm = ChatGroq(
                model=config.LLM_MODEL,
                api_key=config.GROQ_API_KEY,
                temperature=0,           
)
    if tools:
        _llm = _llm.bind_tools(tools)
    return _llm


