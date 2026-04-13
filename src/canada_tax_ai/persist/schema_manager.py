# db/schema_manager.py
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from supabase import create_client, Client

from canada_tax_ai.core.llm import get_llm
from canada_tax_ai.persist.supabase_client import SupabaseClient
from ..config import config
import json
import re


class SchemaManager:
    """LLM inspects parsed data and auto-creates Supabase tables if needed."""

    CREATE_TABLE_PROMPT = """You are a database architect. 
Given this parsed tax slip data, generate a Supabase SQL CREATE TABLE statement.

Rules:
- Table name: {table_name}
- Always include: id (uuid primary key), created_at (timestamptz), updated_at (timestamptz)
- Map Python types: float→numeric(12,2), str→text, int→integer, bool→boolean
- All fields nullable except id, created_at, updated_at
- Use snake_case for column names
- Add IF NOT EXISTS
- Add a comment per column describing what it stores
- Always add a UNIQUE constraint on (sin) — this is required for upsert ON CONFLICT to work
- DO NOT generate any trigger or function — only TABLE and INDEX SQL
- Always end with a CREATE INDEX on sin for fast lookups

Parsed data sample:
{data}

Return ONLY the SQL statement, no explanation, no markdown fences."""

    ADD_COLUMN_PROMPT = """You are a database architect.
The table {table_name} exists with these columns:
{existing_columns}

New parsed data has these extra fields not in the table:
{new_fields}

Generate ALTER TABLE statements to add the missing columns.
Rules:
- Use ALTER TABLE tax_slips ADD COLUMN IF NOT EXISTS
- Map types correctly: float→numeric(12,2), str→text, int→integer, bool→boolean
- One statement per column

Return ONLY the SQL statements separated by semicolons, no explanation, no markdown."""

    def __init__(self):
        self.supabase: Client = SupabaseClient.get()
        self.llm = get_llm()
        self._existing_columns: set[str] = set()

    def _ask_llm(self, prompt: str) -> str:
        response = self.llm.invoke([HumanMessage(content=prompt)])
        # Strip markdown fences if present
        sql = re.sub(r"^```sql|^```|```$", "", response.content.strip(), flags=re.MULTILINE)
        return sql.strip()

    def _get_existing_columns(self,table_name: str) -> set[str]:
        """Fetch current columns from Supabase information_schema."""
        try:
            result = self.supabase.rpc("get_columns", {"table_name": table_name}).execute()
            if result.data:
                self._existing_columns = {row["column_name"] for row in result.data}
            return self._existing_columns
        except Exception:
            return set()

    def _execute_sql(self, sql: str):
        """Execute raw SQL via Supabase RPC."""
        try:
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for stmt in statements:
                self.supabase.rpc("execute_sql", {"sql": stmt}).execute()
                print(f"✅ SQL executed: {stmt[:80]}...")
        except Exception as e:
            print(f"⚠️ SQL execution error: {e}")
            raise

    def ensure_schema(self, data: dict,table_name: str):
        """
        Main entry: LLM checks data, creates table or adds missing columns.
        Called automatically after every successful parse.
        """
        existing = self._get_existing_columns(table_name)

        if not existing:
            # Table doesn't exist — LLM creates it
            print("📋 Table not found — asking LLM to create schema...")
            sql = self._ask_llm(
                self.CREATE_TABLE_PROMPT.format(data=json.dumps(data, indent=2),table_name=table_name)
            )
            print(f"Generated SQL:\n{sql}")

            self._execute_sql(sql)
        else:
            # Table exists — check for new columns
            flat_data = self._flatten(data)
            new_fields = {
                k: type(v).__name__
                for k, v in flat_data.items()
                if k not in existing
            }
            if new_fields:
                print(f"🔧 New fields detected: {new_fields} — asking LLM to add columns...")
                sql = self._ask_llm(self.ADD_COLUMN_PROMPT.format(
                    existing_columns=", ".join(existing),
                    new_fields=json.dumps(new_fields, indent=2),
                    table_name=table_name
                ))
                print(f"Generated SQL:\n{sql}")
                self._execute_sql(sql)
        #fix unterminated dollar-quoted string at or near "$$\nBEGIN\n    NEW.updated_at = now()"
        function_sql = """
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER
            LANGUAGE plpgsql
            AS 'BEGIN NEW.updated_at = now(); RETURN NEW; END;';
            """
        print("Creating function...")
        result = self.supabase.rpc("execute_sql", {"sql": function_sql}).execute()
        print(f"Function created: {result}")

        trigger_sql = f"""
            CREATE OR REPLACE TRIGGER trigger_{table_name}_updated_at
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            """
        print("Creating trigger...")
        result = self.supabase.rpc("execute_sql", {"sql": trigger_sql}).execute()
        print(f"Trigger created: {result}")
        
        # Refresh column cache
        self._get_existing_columns(table_name)

    def _flatten(self, data: dict, prefix: str = "") -> dict:
        """Flatten nested dicts (e.g. t4: {gross_income: ...}) into dot notation."""
        result = {}
        for k, v in data.items():
            key = f"{prefix}{k}" if not prefix else f"{prefix}_{k}"
            if isinstance(v, dict):
                result.update(self._flatten(v, key))
            else:
                result[key] = v
        return result