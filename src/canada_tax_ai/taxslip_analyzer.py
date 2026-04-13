from csv import reader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from canada_tax_ai.core.llm import get_llm
from .config import config
from .models import TaxSlipData, T4SlipData, T5SlipData
from .persist.repository import TaxSlipRepository
import pdfplumber
import base64
import re
import io
from PIL import Image

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
        self.t4_prompt = ChatPromptTemplate.from_template("""
You are a Canadian tax expert. Extract T4 slip fields from the content below.
Boxes to extract:
- Box 14: Employment income
- Box 16: CPP contributions
- Box 18: EI premiums
- Box 20: RPP/RRSP contributions
- Box 22: Income tax deducted
- Box 24: EI insurable earnings
- Box 26: CPP pensionable earnings

{format_instructions}

Content:
{text}

Return ONLY a valid JSON object. Use 0.0 for missing numbers.
""")

        self.t5_prompt = ChatPromptTemplate.from_template("""
You are a Canadian tax expert. Extract T5 slip fields from the content below.
Boxes to extract:
- Box 11: Other investment income
- Box 13: Interest from Canadian sources
- Box 15: Foreign income
- Box 16: Foreign tax paid
- Box 18: Capital gains dividends
- Box 22: Income tax deducted
- Box 24: Actual amount of eligible dividends
- Box 25: Taxable amount of eligible dividends
- Box 26: Dividend tax credit

{format_instructions}

Content:
{text}

Return ONLY a valid JSON object. Use 0.0 for missing numbers, empty string for missing text.
""")

        # Vision prompt handles both T4 and T5
        self.vision_prompt = """
You are a Canadian tax expert analyzing a CRA tax slip image.
First identify if this is a T4 or T5, then extract ALL fields precisely.

If T4, extract boxes: 14, 16, 18, 20, 22, 24, 26
If T5, extract boxes: 11, 13, 15, 16, 18, 22, 24, 25, 26

Also extract:
- document_type: "T4" or "T5"
- sin: Social Insurance Number (9 digits)
- other_info: anything else notable

{format_instructions}

Return ONLY a valid JSON object. Use 0.0 for missing numbers, empty string for missing text.
"""


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
        format_instructions = self.parser.get_format_instructions()

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
        result = self.parser.parse(response.content)
        return result


    def analyze(self, file_path: str) -> dict:
        t4_regex = r"(?P<year>\d{4})\s+[\d\sA-Za-z,.-]+?\s+(?P<employer_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)\s+(?P<box_14_employment_income>\d{1,7}\.\d{2})\s+(?P<box_22_income_tax_deducted>\d{1,7}\.\d{2})\s+\d+\s+(?P<box_16_cpp_contributions>\d{1,7}\.\d{2})\s+(?P<province_of_employment>[A-Z]{2})\s+(?P<social_insurance_number>\d{3}\s+\d{3}\s+\d{3})\s+(?:0\.00\s+)?(?P<box_24_ei_insurable_earnings>\d{1,7}\.\d{2})\s+(?P<box_26_cpp_pensionable_earnings>\d{1,7}\.\d{2})(?:\s+\d{1,7}\.\d{2})?\s+(?P<employee_last_name>[A-Z]+)\s+(?P<employee_first_name>[A-Z][a-z]+)\s+(?P<box_18_employee_ei_premiums>\d{1,7}\.\d{2})\s+[\d\sA-Za-z,.-]+?\s+(?P<employee_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)\s+(?P<form_code>RC-\d+-\d+)"
        t5_regex = r'(?P<year>\d{4})\s+Statement of Investment Income[\s\S]*?(?P<recipient_name>[A-Z][A-Z\s\'-]+?)\s+[\d-]+\s+[\w\s-]+?\s+(?P<recipient_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)[\s\S]*?(?P<payer_name>[A-Z][A-Z\s,.-]+?)\s+P\.O\.\s*BOX[\s\S]*?(?P<payer_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)[\s\S]*?(?P<recipient_sin>\d{3}\s+\d{3}\s+\d{3})[\s\S]*?24\s*[\|]?\s*(?P<box_24_eligible_dividends>\d{1,7}\.\d{2})(?:[\s\S]*?13\s*[\|]?\s*(?P<box_13_interest>\d{1,7}\.\d{2}))?(?:[\s\S]*?10\s*[\|]?\s*(?P<box_10_other_dividends>\d{1,7}\.\d{2}))?'
        # --- Image path: send directly to vision LLM ---
        if file_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            print("Image detected — sending directly to vision LLM...")
            result = self._extract_from_image_via_llm(file_path)
            print(f"Vision LLM Extracted:\n{result}")
            return result.model_dump()

        # --- PDF path: use pdfplumber + regex + text LLM ---
        #TODO - if regex fails, send raw text to LLM with a prompt to extract fields without regex guidance
        #TODO - if the PDF is not text-based (i.e. scanned), fallback to OCR + vision LLM extraction
        data = ""
        with pdfplumber.open(file_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            t4match = re.search(t4_regex, text)
            print(f"PDF text extracted, applying regex...{text}...")

            if t4match:
                data = t4match.groupdict()
                data['document_type'] = 'T4' if data.get('form_code', '').startswith('RC-14') else 'Unknown'
                print(f"T4 regex match: {data}")
            else:
                t5match = re.search(t5_regex, text)
                if t5match:
                    data = t4match.groupdict()
                    data['document_type'] = 'T5'

                    data['recipient_name'] = ' '.join(data['recipient_name'].split())
                else:
                    # Fallback: send raw PDF text to LLM if regex fails
                    print("Regex did not match — falling back to raw text LLM extraction...")
                    data = text

        doc_type = self._detect_doc_type(text)
        sin = self._extract_sin(text)
        parser, prompt = self._get_parser_and_prompt(doc_type)

        chain = prompt | self.llm | parser
        slip_data = chain.invoke({
            "text": data,
            "format_instructions": parser.get_format_instructions()
        })

        # Assemble unified output
        result = TaxSlipData(document_type=doc_type, sin=sin)
        if doc_type == "T4":
            result.t4 = slip_data
            table_name = "t4"
        else:
            result.t5 = slip_data
            table_name = "t4" 
        
        print(f"Parsed Tax Slip Data:\n{result}")
        extracted = result.model_dump(exclude_none=True)
        try:
            saved = self.repo.upsert(extracted, table_name)
            extracted["db_id"] = saved.get("id")
        except Exception as e:
            extracted["db_error"] = str(e)
        return extracted