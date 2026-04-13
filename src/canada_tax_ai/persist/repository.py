# db/repository.py
from supabase import create_client, Client

from canada_tax_ai.persist.supabase_client import SupabaseClient
from .schema_manager import SchemaManager
from ..config import config
from datetime import datetime, timezone
import uuid
import os
import time

class TaxSlipRepository:

    def __init__(self):
        self.supabase: Client = SupabaseClient.get()
        self.schema_manager = SchemaManager()

    def _prepare_record(self, extracted: dict) -> dict:
        """Flatten extracted data into a single DB row."""
        doc_type = extracted.get("document_type", "")
        if(doc_type not in ["T4", "T5"]):
            extend_data = extracted
            record = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                **extend_data  # flatten T4/T5 fields directly into row
            }
        else:
            extend_data = extracted.get("t4", {}) if doc_type == "T4" else extracted.get("t5", {})
            record = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "document_type": doc_type,
                "sin": extracted.get("sin", ""),
                "other_info": extracted.get("other_info", ""),
                **extend_data  # flatten T4/T5 fields directly into row
            }

        # Remove None values — let DB use column defaults
        return {k: v for k, v in record.items() if v is not None}

    def save(self, extracted: dict) -> dict:
        """
        1. LLM ensures schema is up to date
        2. Insert record into Supabase
        3. Return saved record
        """
        record = self._prepare_record(extracted)

        # Step 1: auto-create or update schema
        self.schema_manager.ensure_schema(record)

        # Step 2: insert into Supabase
        try:
            result = self.supabase.table("tax_slips").insert(record).execute()
            saved = result.data[0] if result.data else record
            print(f"✅ Saved to Supabase: id={saved.get('id')}, type={saved.get('document_type')}")
            return saved
        except Exception as e:
            print(f"⚠️ Supabase insert failed: {e}")
            raise

    def get_by_sin(self, sin: str) -> list[dict]:
        result = self.supabase.table("tax_slips").select("*").eq("sin", sin).execute()
        return result.data or []

    def upsert(self, extracted: dict,table_name: str, retries: int = 3) -> dict:
        """Update if SIN + document_type exists, else insert."""
        record = self._prepare_record(extracted)
        self.schema_manager.ensure_schema(record, table_name)
        for attempt in range(retries):
            try:
                result = self.supabase.table(table_name).upsert(
                    record
                ).execute()
                saved = result.data[0] if result.data else record
                print(f"✅ Upserted: id={saved.get('id')}")
                return saved
            except Exception as e:
                print(f"⚠️ Supabase upsert failed: {e}")
                if "schema cache" in str(e).lower() and attempt < retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    print(f"⚠️ Schema cache miss — retrying in {wait}s (attempt {attempt + 1}/{retries})")
                    time.sleep(wait)
                else:
                    raise e