
# Persistent State
from typing import TypedDict, Annotated, Optional

from canada_tax_ai.models import UserProfile, TaxResult


class AgentState(TypedDict):
    messages: Annotated[list, "add_messages"]   # conversation history
    knowledge: Optional[dict]                             # long-term knowledge base (auto-saved)
    last_verified: Optional[dict]               # last verification result
    profile: Optional[UserProfile]            # structured user profile (validated by LLM)
    file_path: Optional[str]                      # path to uploaded tax slip file
    extracted_data: Optional[dict]                    # latest extracted tax slip data
    tax_result: Optional[TaxResult]                        # latest tax calculation result
    next_tool: Optional[str]                      # next tool to call, set by router
