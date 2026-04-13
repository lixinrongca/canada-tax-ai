from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Config(BaseModel):
    TAX_YEAR: int = 2025
    PROVINCE: str = "MB"
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "openai/gpt-oss-120b"
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")

config = Config()
