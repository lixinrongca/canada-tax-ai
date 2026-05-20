from csv import reader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from canada_tax_ai.core.llm import get_llm
from canada_tax_ai.tools.build_input import update_tax_input
from canada_tax_ai.utils import parse_t4, parse_t5
from ..config import config
from ..models import TaxInputData, TaxSlipData, T4SlipData, T5SlipData
from ..persist.repository import TaxSlipRepository
from .agent_state import AgentState
import pdfplumber
import base64
import re
import io
from loguru import logger
from PIL import Image
from ..prompt.prompt_registry import sys_prompt,temp_prompt

class TaxSlipAnalyzer:
    def __init__(self):
        self.llm = get_llm()
        # Separate vision model — use Groq's vision-capable model
        self.vision_llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", api_key=config.GROQ_API_KEY, temperature=0)
        
        self.repo = TaxSlipRepository()
        # Per-type parsers
        self.t4_parser = PydanticOutputParser(pydantic_object=T4SlipData)
        self.t5_parser = PydanticOutputParser(pydantic_object=T5SlipData)
        # Vision parser uses full unified model
        self.vision_parser = PydanticOutputParser(pydantic_object=TaxSlipData)
        # Per-type prompts
        self.t4_prompt = ChatPromptTemplate.from_template(sys_prompt("t4_extraction", "v1"))

        self.t5_prompt = ChatPromptTemplate.from_template(sys_prompt("t5_extraction", "v1"))
        

    def _encode_image(self, file_path: str, max_size: int = 1024, quality: int = 85) -> tuple[str, str]:
        """Encode image to base64, resizing and compressing to stay under Groq's limit."""
        with Image.open(file_path) as img:
            # Convert RGBA/palette to RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Resize if too large (keep aspect ratio)
            w, h = img.size
            if max(w, h) > max_size:
                scale = max_size / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                print(f"Resized image: {w}x{h} → {img.size[0]}x{img.size[1]}")

            # Compress to JPEG in memory
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            buffer.seek(0)

            # If still too large, reduce quality further
            while buffer.getbuffer().nbytes > 4 * 1024 * 1024 and quality > 30:
                quality -= 10
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality, optimize=True)
                buffer.seek(0)
                print(f"Re-compressed at quality={quality}, size={buffer.getbuffer().nbytes / 1024:.1f}KB")

            print(f"Final image size: {buffer.getbuffer().nbytes / 1024:.1f}KB")
            image_data = base64.standard_b64encode(buffer.read()).decode("utf-8")

        return image_data, "image/jpeg"

    def _extract_sin(self, text: str) -> str:
        """Extract SIN from raw text."""
        match = re.search(r'\b(\d{3})[-\s]?(\d{3})[-\s]?(\d{3})\b', text)
        return "".join(match.groups()) if match else ""


    def _detect_doc_type(self, text: str) -> str:
        """Detect T4 vs T5 from raw PDF text."""
        text_lower = text.lower()
        t4_signals = ["employment income", "ei premiums", "cpp contributions", "rc-14", "remuneration"]
        t5_signals = ["investment income", "eligible dividends", "interest from canadian", "rc-24", "dividends"]
        t4_score = sum(1 for kw in t4_signals if kw in text_lower)
        t5_score = sum(1 for kw in t5_signals if kw in text_lower)
        if t4_score > t5_score:
            return "T4"
        elif t5_score > t4_score:
            return "T5"
        return "Other"

    def _get_parser_and_prompt(self, doc_type: str):
        """Return the correct parser + prompt for the detected type."""
        if doc_type == "T5":
            return self.t5_parser, self.t5_prompt
        return self.t4_parser, self.t4_prompt
    
    def _extract_from_image_via_llm(self, file_path: str) -> TaxSlipData:
        """Send image directly to vision LLM and parse structured T4/T5 data."""
        image_data, media_type = self._encode_image(file_path)
        format_instructions = self.vision_parser.get_format_instructions()

        message = HumanMessage(content=[
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{image_data}"
                }
            },
            {
                "type": "text",
                "text": f"""You are an expert Canadian tax accountant.
This is a CRA T4 or T5 tax slip image.
Extract ALL numeric values and fields directly from the image.
Be precise — read every box number and its corresponding dollar amount carefully.

{format_instructions}

Return ONLY a valid JSON object. If a field is missing, use 0.0 for numbers and empty string for text."""
            }
        ])

        response = self.vision_llm.invoke([message])
        logger.info(f"Vision LLM raw response:\n{response.content}")
        result = self.vision_parser.parse(response.content)
        return result
    
def document_node(state: AgentState):
    analyzer = TaxSlipAnalyzer()
    file_path = state.get("file_path")
    logger.info(f"Tax input data : {state.get('tax_input_data')}")
    # --- Image path: send directly to vision LLM ---
    if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        logger.info("Image detected — sending directly to vision LLM...")
        result = analyzer._extract_from_image_via_llm(file_path)
        return {"extracted_data": result.model_dump()}

    # --- PDF path: use pdfplumber + regex + text LLM ---
    #TODO - if regex fails, send raw text to LLM with a prompt to extract fields without regex guidance
    #TODO - if the PDF is not text-based (i.e. scanned), fallback to OCR + vision LLM extraction
    data = ""
    with pdfplumber.open(file_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()
        logger.info(f"Extracted text from PDF:\n{text}")

        sin = analyzer._extract_sin(text)
        doc_type = analyzer._detect_doc_type(text)
        if doc_type == "T4":
            data = parse_t4(text)
        elif doc_type == "T5":
            data = parse_t5(text)
        else:                
            data = text  # fallback to raw text for LLM parsing if type detection fails 

    parser, prompt = analyzer._get_parser_and_prompt(doc_type)

    chain = prompt | analyzer.llm | parser
    slip_data = chain.invoke({
        "text": data,
        "format_instructions": parser.get_format_instructions()
    })

    existing = state.get("extracted_data", {})
    logger.info(f"Updated agent state with extracted data: {existing}")
    # Assemble unified output
    result = TaxSlipData(document_type=doc_type, sin=sin)
    if doc_type == "T4":
        result.t4 = existing.get("t4", [])+[slip_data]
        result.t5 = existing.get("t5", [])  
        table_name = "t4"
    else:
        result.t5 = existing.get("t5", [])+[slip_data]
        result.t4 = existing.get("t4", [])  
        table_name = "t5"
    
    logger.info(f"Parsed Tax Slip Data:\n{result}")
    extracted = result.model_dump(exclude_none=True)
    try:
        saved = analyzer.repo.upsert(extracted, table_name)
        extracted["db_id"] = saved.get("id")
    except Exception as e:
        extracted["db_error"] = str(e)

    raw = state.get("tax_input_data") if state.get("tax_input_data") else TaxInputData()
    if raw is None:
        existing_tax_input_data = TaxInputData()
    if isinstance(raw, TaxInputData):
        existing_tax_input_data = raw          # already correct type (first run, before checkpoint)
    if isinstance(raw, dict):
        existing_tax_input_data = TaxInputData(**raw)   # ✅ deserialize from checkpoint
    logger.info(f"Existing TaxInputData Type is {type(existing_tax_input_data)}")
    logger.info(f"Existing TaxInputData before update: {existing_tax_input_data}")
    updated_tax_input_data = update_tax_input(existing_tax_input_data, extracted.get("t4", []), extracted.get("t5", []))

    return {"extracted_data": extracted, 
            "tax_input_data": updated_tax_input_data.model_dump(exclude_none=True),
            "file_path": None}