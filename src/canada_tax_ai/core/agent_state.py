
# Persistent State
from typing import TypedDict, Annotated, Optional

from canada_tax_ai.models import UserProfile


class AgentState(TypedDict):
    messages: Annotated[list, "add_messages"]   # conversation history
    knowledge: dict                             # long-term knowledge base (auto-saved)
    last_verified: Optional[dict]               # last verification result
    profile: UserProfile             # structured user profile (validated by LLM)
