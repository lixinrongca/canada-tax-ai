import os
from dotenv import load_dotenv
from supabase import create_client, Client

from canada_tax_ai.persist.supabase_client import SupabaseClient

load_dotenv()
supabase: Client = SupabaseClient.get()

def register_user(username: str, password: str) -> bool:
    try:
        email = f"{username}@taxai.local"
        res = supabase.auth.sign_up({"email": email, "password": password})
        supabase.table("users").insert({"id": res.user.id, "username": username, "email": email}).execute()
        return True
    except Exception as e:
        print("Registration error:", e)
        return False

def verify_user(username: str, password: str) -> bool:
    try:
        email = f"{username}@taxai.local"
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        return True
    except Exception:
        return False

def save_tax_report(username: str, report_data: dict):
    try:
        supabase.table("tax_reports").insert({"username": username, **report_data}).execute()
    except Exception:
        pass
