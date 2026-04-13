
from langchain_core.tools import tool

from canada_tax_ai.models import UserProfile
from canada_tax_ai.persist.repository import TaxSlipRepository
from canada_tax_ai.persist.supabase_client import SupabaseClient
from ..tax_calculator import calculate_tax
from ..rag import retriever
from supabase import create_client, Client
from datetime import datetime
import json
from ..core.agent_state import AgentState

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

@tool
def process_t4_ocr(image_path: str):
    """Your PaddleOCR + regex processing tool"""
    # Put your previous OCR + regex code here
    # Return structured data
    return {"status": "success", "data": {...}}

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
def save_userprofile_to_db(profile: UserProfile):
    """Saves the UserProfile entity to the database. This should be called whenever the UserProfile is updated with new information."""
    repo = TaxSlipRepository()
    data = profile.model_dump(exclude_none=True)
    print("Prepared data for DB:", data)
    message =""
    try:
        saved = repo.upsert(data, "user_profiles")
        message = "Successful save with ID: " + saved.get("id")
    except Exception as e:
        print("Error saving UserProfile to DB:", e)
        message = str(e)

    return {
        "messages": [message + " | Data: " + json.dumps(data, ensure_ascii=False)],
        "knowledge": "knowledge",
        "profile": profile
    }

@tool
def end_chain(profile: UserProfile):
    """This tool can be called to signal the end of the workflow. It doesn't perform any action but can be used for clarity in the graph."""
    return {
        "messages": "UserProfile saved to DB.",
        "knowledge": "knowledge",
        "profile": profile
    }