
# Persistent State
from typing import TypedDict, Annotated, Optional

from pydantic import field_validator

from canada_tax_ai.models import TaxInputData, UserProfile, TaxResult
from langgraph.graph import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   =[] # conversation history
    knowledge: Optional[dict]                 =None            # long-term knowledge base (auto-saved)
    last_verified: Optional[dict]             =None # last verification result
    profile: Optional[UserProfile]            =None # structured user profile (validated by LLM)
    file_path: Optional[str]                  =None # path to uploaded tax slip file
    extracted_data: Optional[dict]            =None # latest extracted tax slip data
    tax_result: Optional[TaxResult]           =None # latest tax calculation result
    next_tool: Optional[str]                  =None # next tool to call, set by router
    tax_input_data: Optional[TaxInputData]    = None                 # latest tax input data for calculation

    @field_validator("tax_input_data", mode="before")
    @classmethod
    def coerce_tax_input(cls, v):
        if isinstance(v, dict): return TaxInputData(**v)
        return v
