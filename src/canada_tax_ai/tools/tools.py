from langchain.agents import AgentState
from langchain_core.tools import InjectedToolCallId, tool
from canada_tax_ai.core.agent_state import AgentState

from canada_tax_ai.models import T4SlipData, T5SlipData, UserProfile,TaxInputData
from canada_tax_ai.persist.repository import TaxSlipRepository
from canada_tax_ai.persist.supabase_client import SupabaseClient
from ..tax_calculator import calculate_tax
from ..rag.rag import retriever
from supabase import Client
from datetime import datetime
import json
from loguru import logger
from typing import Annotated, Optional
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from canada_tax_ai.utils import remove_sin_hyphens,render_markdown_table,render_slip_table

@tool
def canadian_tax_calculator(gross_income: float, rrsp: float = 0.0, other_deductions: float = 0.0, has_spouse: bool = False, children: int = 0) -> dict:
    """
    Calculate Canadian federal and provincial taxes based on the provided financial information and family status.
    This function uses the calculate_tax function from tax_calculator.py to perform the actual calculations."""
    return calculate_tax(gross_income, rrsp, other_deductions, has_spouse, children)

@tool
def query_cra_rules(query: str) -> str:
    """
    Query CRA tax rules using a retriever. This can be used to fetch specific tax regulations, credits, or deductions based on user questions.
    """
    docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])


def query_tax_slips(state: AgentState):
    """Your PaddleOCR + regex processing tool"""
    raw_sin = state.get("profile", {}).model_dump().get("sin") if state.get("profile") else None
    try:
        sin = remove_sin_hyphens(raw_sin)
    except Exception as e:
        logger.info(f"Sin is not correct")
        return {"messages": "No SIN available in user profile to query tax slips.What is your SIN?", "knowledge": state.get("knowledge", {})}
    if sin:
        try:
            repo = TaxSlipRepository()
            slips = repo.get_t45_by_sin(sin,"t4")
            logger.info(f"Queried tax slips for SIN {sin}: {slips}")
            doc_type = "T4" if slips and slips[0].get("document_type") == "T4" else "T5"
            model = T4SlipData if doc_type == "T4" else T5SlipData
            # table = dict_to_markdown_table(slips)
            table = render_slip_table({"t4": slips}, "T4", model)
            return {"messages": table if slips else "No tax slips found for this SIN.", "knowledge": state.get("knowledge", {})}
        except Exception as e:
            print(f"Error querying tax slips: {e}")
            return {"messages": "Please upload your tax slips.", "knowledge": state.get("knowledge", {})}
    else:
        return {"messages": "No SIN available in user profile to query tax slips.What is your SIN?",
            "knowledge": state.get("knowledge", {})}

def query_profile(state: AgentState):
    """Your PaddleOCR + regex processing tool"""
    print(f"Getting user profile for tool: {state.get('next_tool')}")
    if(state.get("profile")):
        profile = state.get("profile")
        table = render_markdown_table([profile.model_dump()])
        return {"messages": table, "knowledge": state.get("knowledge", {})}
    else:
        return {"messages": "No profile data available.", "knowledge": state.get("knowledge", {})}

def confirm_profile(state: AgentState):
    """This tool can be called to confirm that the UserProfile is complete and accurate before saving to DB."""
    profile = state.get("profile", {})
    print(f"Confirming user profile: {profile}")
    if not profile:
        return {"messages": "No profile data to confirm.", "knowledge": state.get("knowledge", {})}
    
    # Here you could add additional checks or even call an LLM to validate the profile data before confirming
    return {
        "messages": "Please confirm that your profile information is correct:\n" + json.dumps(profile.model_dump(exclude_none=True), indent=2),
        "knowledge": state.get("knowledge", {}),
    }

def merge_node(state: AgentState) -> AgentState:
    """Runs after both parallel branches complete."""
    return state   # LangGraph has already merged via reducers


@tool
def save_tax_record_to_db(record: dict):
    """Call this tool ONLY when you have a clear, verified T5 (or T4) extraction.
    Saves the full record to Supabase PostgreSQL."""
    
    supabase: Client = SupabaseClient.get()

    timestamp = datetime.now().isoformat()
    
    data = {
        "document_type": record.get("document_type", "UNKNOWN"),
        "year": record.get("year"),
        "recipient_sin": record.get("recipient_sin") or record.get("social_insurance_number"),
        "recipient_name": record.get("recipient_name") or 
                         f"{record.get('employee_first_name', '')} {record.get('employee_last_name', '')}".strip(),
        "data_json": json.dumps(record, ensure_ascii=False),
        "timestamp": timestamp
    }
    
    response = supabase.table("tax_records").upsert(data).execute()
    
    return {
        "status": "saved",
        "record_id": response.data[0].get("id") if response.data else None,
        "saved_at": timestamp
    }

@tool
def save_to_db(profile: UserProfile):
    """Saves the UserProfile entity to the database. This should be called whenever the UserProfile is updated with new information."""
    repo = TaxSlipRepository()
    data = profile.model_dump(exclude_none=True)
    print(f"Prepared data for DB: {data}")
    message =""
    try:
        saved = repo.upsert(data, "user_profiles")
        message = "Successful save with ID: " + saved.get("id")
    except Exception as e:
        print(f"Error saving to DB: {e}")
        message = str(e)

    return {
        "messages": [message + " | Data: " + json.dumps(data, ensure_ascii=False)],
        "knowledge": {},
        "profile": profile
    }


def save_profile(profile: UserProfile)->str:
    """Saves the UserProfile entity to the database. This should be called whenever the UserProfile is updated with new information."""
    logger.info(f"Saving profile to DB: {profile}")
    repo = TaxSlipRepository()
    data = profile.model_dump(exclude_none=True)
    message =""
    try:
        saved = repo.upsert(data, "user_profiles")
        message = "Successful save with ID: " + saved.get("id")
    except Exception as e:
        logger.info(f"Error saving to DB: {e}")
        message = str(e)

    return {
        "messages": [message + " | Data: " + json.dumps(data, ensure_ascii=False)],
        "knowledge": {},
        "profile": profile
    }

@tool(args_schema=TaxInputData)
def update_tax_data(
    province: Optional[str] = None,
    employment_income:     Optional[float] = None,
    eligible_dividends:    Optional[float] = None,
    capital_gains:         Optional[float] = None,
    capital_losses:        Optional[float] = None,
    self_employment_income: Optional[float] = None,
    rrsp_contribution:     Optional[float] = None,
    union_dues:             Optional[float] = None,
    childcare_expenses:     Optional[float] = None,
    moving_expenses:        Optional[float] = None,
    other_deductions:       Optional[float] = None,
    medical_expenses:         Optional[float] = None,
    charitable_donations:     Optional[float] = None,
    tuition_paid:             Optional[float] = None,
    federal_tax_withheld:  Optional[float] = None,
    cpp_contributions:     Optional[float] = None,
    ei_premiums:           Optional[float] = None,
    total_rent_paid:          Optional[float] = None,
    property_tax_paid:        Optional[float] = None,
    other_investment_income: Optional[float] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None  
) -> Command:   
    """Save extracted tax data fields to the database."""
    data = {k: v for k, v in locals().items() if v is not None}
    # save data...
    logger.info(f"Saving tax data to DB: {data}")
    return Command(
        update={
            "tax_input_data": data,
            "messages": [ToolMessage(         # ✅ required — tells LLM tool succeeded
                content=f"Update tax data: {json.dumps(data, ensure_ascii=False)}",
                tool_call_id=tool_call_id
            )]
        }
    )
    # return f"Saved {len(data)} tax fields successfully"
    
@tool
def end_node(profile: UserProfile):
    """This tool can be called to signal the end of the workflow. It doesn't perform any action but can be used for clarity in the graph."""

    return {
        "messages": "UserProfile saved to DB.",
        "knowledge": {},
        "profile": profile
    }


@tool
def  verify_addresss(address_input: str) -> str:
    """A tool to verify and correct the user's address using an external API (e.g., Canada Post). 
    This is just a placeholder function. In production, implement actual API calls to validate and standardize the address."""
    print(f"Verifying address: {address_input}")
    # Simulate verification by appending "Verified" to the address
    verified_address = address_input + " (Verified)"
    return verified_address
