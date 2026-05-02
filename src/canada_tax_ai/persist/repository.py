# db/repository.py
from dataclasses import asdict

from supabase import create_client, Client

from canada_tax_ai.persist.supabase_client import SupabaseClient
from .schema_manager import SchemaManager
from ..config import config
from datetime import datetime, timezone
import uuid
import os
import time
from loguru import logger
from canada_tax_ai.models import TaxResult

class TaxSlipRepository:

    def __init__(self):
        self.supabase: Client = SupabaseClient.get()
        self.schema_manager = SchemaManager()

    def _prepare_record(self, extracted: dict) -> dict:
        """Flatten extracted data into a single DB row."""
        doc_type = ""
        if not isinstance(extracted, TaxResult):# Tax Result doesn't have document_type field, so we infer it from context or default to empty string
            doc_type = extracted.get("document_type", "")
        logger.info(f"Preparing record for DB insertion. Extracted data keys: {extracted}, document type: {doc_type}")
        if(doc_type not in ["T4", "T5"]):
            if isinstance(extracted, TaxResult):
                extend_data = asdict(extracted)  # Convert dataclass to dict
            else:
                extend_data = extracted
            logger.info(f"Document type '{doc_type}' is not T4/T5. Saving with generic schema. Extend data keys: {extend_data}")
            
            record = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                **extend_data  # flatten T4/T5 fields directly into row
            }
        else:
            extend_data = extracted.get("t4", [])[-1] if doc_type == "T4" else extracted.get("t5", []) [-1]
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
            logger.info(f"✅ Saved to Supabase: id={saved.get('id')}, type={saved.get('document_type')}")
            return saved
        except Exception as e:
            logger.warning(f"⚠️ Supabase insert failed: {e}")
            raise

    def get_t45_by_sin(self, sin: str,table_name: str) -> list[dict]:
        result = self.supabase.table(table_name).select("*").eq("sin", sin).execute()
        return result.data or []

    def upsert(self, extracted: dict,table_name: str, retries: int = 3) -> dict:
        """Update if SIN + document_type exists, else insert."""
        record = self._prepare_record(extracted)
        logger.info(f"Upserting into '{table_name}' with record keys: {list(record.keys())}")
        self.schema_manager.ensure_schema(record, table_name)
        logger.info(f"Schema ensured for upsert. Attempting to upsert record with keys: {list(record.keys())}")
        for attempt in range(retries):
            try:
                result = self.supabase.table(table_name).upsert(
                    record,
                    on_conflict="sin"
                ).execute()
                saved = result.data[0] if result.data else record
                logger.info(f"✅ Upserted: id={saved.get('id')}")
                return saved
            except Exception as e:
                logger.warning(f"⚠️ Supabase upsert failed: {e}")
                if "schema cache" in str(e).lower() and attempt < retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.info(f"⚠️ Schema cache miss — retrying in {wait}s (attempt {attempt + 1}/{retries})")
                    time.sleep(wait)
                else:
                    raise e