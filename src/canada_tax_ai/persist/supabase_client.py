# db/supabase_client.py
import os

from supabase import create_client, Client



class SupabaseClient:
    _instance: Client | None = None

    @classmethod
    def get(cls) -> Client:
        if cls._instance is None:
            cls._instance = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))
            print("✅ Supabase client created")
        return cls._instance