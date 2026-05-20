from fpdf import FPDF
import re
from datetime import date, datetime

from pydantic import BaseModel

class TaxPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Canada Tax AI - 2025 Tax Report", align="C")
        self.ln(10)

def generate_tax_pdf(result: dict, filename: str = "tax_report.pdf"):
    pdf = TaxPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Gross Income: ${result['gross_income']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Taxable Income: ${result['taxable_income']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Federal Tax: ${result['federal_tax']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Manitoba Tax: ${result['provincial_tax']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Total Tax: ${result['total_tax']:,.2f}", ln=1)
    pdf.cell(0, 10, f"Estimated Refund/Owing: ${result['estimated_refund_owing']:,.2f}", ln=1)
    pdf.output(filename)
    return filename


def parse_t5(text: str) -> dict:
    """Extract all T5 fields from OCR text using regex."""

    def find(pattern: str, default=None):
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else default

    return {
        # ── Identity ──────────────────────────────────────────────
        "year": find(r'\b(20\d{2})\b'),

        "recipient_name": find(
            r"Recipient['\u2019]?s\s+name[^/\n]*?[/\n].*?\n([A-Z][A-Z\s]+)\n"
        ) or find(r"^([A-Z]+\s+[A-Z]+)\n", ),

        "payer_name": find(
            r"Payer['\u2019]?s\s+name[^/\n]*?[/\n].*?\n([A-Z][A-Z\s,.']+(?:BANK|TRUST|CORP|INC|LTD|RBC|TD|BMO|CIBC|SCOTIA)[A-Z\s,.']*)\n"
        ) or find(r"(ROYAL BANK OF CANADA|TD BANK|CIBC|BMO|SCOTIABANK|[A-Z\s]+(?:BANK|TRUST|CORP|INC|LTD))"),

        "recipient_sin": find(
            r'(?:Recipient\s+identification\s+number|Numéro\s+d\'identification)[^\n]*\n[^\n]*?(\d{3}\s*\d{3}\s*\d{3})'
        ) or find(r'\b([O0]\s*\d{3}\s*\d{3}\s*\d{3})\b'),  # handles OCR O/0 confusion

        "recipient_type": find(
            r'(?:Recipient\s+type|Type\s+de\s+bénéficiaire)[^\n]*?\n[^\n]*?(\d)',
        ),

        "report_code": find(
            r'(?:21\s*\|\s*Report|Code\s+du\s+feuillet)[^\n]*?\n([A-Z0-9])'
        ) or find(r'Report\s+(?:Code\s+)?[\|]?\s*([A-Z0-9])\b'),

        # TODO extracted data is not accurate, need to improve regex or rely more on LLM parsing
        "interest_income": find(                            # Box 13
            r'(?:13\s*\|?\s*Interest\s+from\s+Canadian\s+sources'
            r'|Intérêts\s+de\s+source\s+canadienne)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "capital_gains_dividends": find(                   # Box 18
            r'(?:18\s*\|?\s*Capital\s+gains\s+dividends'
            r'|Dividendes\s+sur\s+gains\s+en\s+capital)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "actual_dividends": find(                          # Box 24
            r'(?:24\s*\|?\s*Actual\s+amount\s+of\s+eligible\s+dividends'
            r'|Montant\s+réel\s+des\s+dividendes\s+déterminés)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "taxable_dividends": find(                         # Box 25
            r'(?:25\s*\|?\s*Taxable\s+amount\s+of\s+eligible\s+dividends'
            r'|Montant\s+imposable\s+des\s+dividendes\s+déterminés)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "dividend_tax_credit": find(                       # Box 26
            r'(?:26\s*\|?\s*Dividend\s+tax\s+credit\s+for\s+eligible'
            r'|Crédit\s+d\'impôt\s+pour\s+dividendes\s+déterminés)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "actual_amount_other_dividends": find(             # Box 10
            r'(?:10\s*\|?\s*Actual\s+amount\s+of\s+dividends\s+other'
            r'|Montant\s+réel\s+des\s+dividendes\s+autres)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "taxable_amount_other_dividends": find(            # Box 11
            r'(?:11\s*\|?\s*Taxable\s+amount\s+of\s+dividends'
            r'|Montant\s+imposable\s+des\s+dividendes\s+autres)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "dividend_tax_credit_other_dividends": find(       # Box 12
            r'(?:12\s*\|?\s*Dividend\s+tax\s+credit\s+for\s+dividends'
            r'|Crédit\s+d\'impôt\s+pour\s+dividendes\s+autres)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "foreign_income": find(                            # Box 15
            r'(?:15\s*\|?\s*Foreign\s+income'
            r'|Revenus\s+étrangers)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "foreign_tax_paid": find(                          # Box 16
            r'(?:16\s*\|?\s*Foreign\s+tax\s+paid'
            r'|Impôt\s+étranger\s+payé)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        "investment_income": find(                         # Box 11 other
            r'(?:11\s*\|?\s*Other\s+investment\s+income'
            r'|Autres\s+revenus\s+de\s+placement)'
            r'[^\d]*?([\d,]+\.\d{2})'
        ),

        # ── Currency & account ────────────────────────────────────
        "foreign_currency": find(                          # Box 27
            r'(?:27\s*\|?\s*Foreign\s+currency'
            r'|Devises\s+étrangères)'
            r'[^\n]*?\n([A-Z]{3})'                         # e.g. USD, EUR
        ),

        "transit": find(                                   # Box 28
            r'(?:28\s*\|?\s*Transit'
            r'|Succursale)'
            r'[^\d]*?(\d{4,6})'
        ),

        "recipient_account_number": find(                  # Box 29
            r'(?:29\s*\|?\s*Recipient\s+account\s+number'
            r'|Numéro\s+de\s+compte\s+du\s+bénéficiaire)'
            r'[^\d]*?([\dA-Z-]+)'
        ),
    }

# ------------------------------------------------------------------ #
#  Clean numeric strings → float
# ------------------------------------------------------------------ #
def to_float(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return 0.0


def parse_t5_typed(text: str) -> dict:
    raw = parse_t5(text)
    numeric_fields = {
        "interest_income", "capital_gains_dividends",
        "actual_dividends", "taxable_dividends", "dividend_tax_credit",
        "actual_amount_other_dividends", "taxable_amount_other_dividends",
        "dividend_tax_credit_other_dividends", "foreign_income", "foreign_tax_paid",
        "investment_income",
    }
    return {
        k: to_float(v) if k in numeric_fields else v
        for k, v in raw.items()
    }

def parse_t4(text: str) -> dict:
    # t4_regex = r'(?P<employer_name>[A-Z][A-Za-z0-9\s,.\-\'\&]+?)\s+(?P<year>\d{4})\s+[\d\sA-Za-z,.-]+?\s+(?P<employer_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)\s+(?P<box_14_employment_income>\d{1,7}\.\d{2})\s+(?P<box_22_income_tax_deducted>\d{1,7}\.\d{2})\s+\d+\s+(?P<box_16_cpp_contributions>\d{1,7}\.\d{2})\s+(?P<province_of_employment>[A-Z]{2})\s+(?P<social_insurance_number>\d{3}\s+\d{3}\s+\d{3})\s+(?:0\.00\s+)?(?P<box_24_ei_insurable_earnings>\d{1,7}\.\d{2})\s+(?P<box_26_cpp_pensionable_earnings>\d{1,7}\.\d{2})(?:\s+\d{1,7}\.\d{2})?\s+(?P<employee_last_name>[A-Z]+)\s+(?P<employee_first_name>[A-Z][a-z]+)\s+(?P<box_18_rpp_contributions>\d{1,7}\.\d{2})\s+[\d\sA-Za-z,.-]+?\s+(?P<employee_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)\s+(?P<form_code>RC-\d+-\d+)'
    t4_regex = (
    r'(?P<employer_name>[A-Z][A-Za-z0-9\s,.\-\'\&]+?)\n'   # Sysics Innovation Co., Ltd.
    r'(?P<year>\d{4})\n'                                     # 2025
    r'[^\n]+\n'                                              # 196 Osborne St
    r'(?P<employer_city>[A-Za-z\s]+),\s*'                   # Winnipeg,
    r'(?P<employer_province>[A-Z]{2})\s+'                   # MB
    r'(?P<employer_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)\n' # R3L 1Z3
    r'(?P<box_14_employment_income>\d{1,7}\.\d{2})\s+'      # 56394.00
    r'(?P<box_22_income_tax_deducted>\d{1,7}\.\d{2})\n'     # 9150.09
    r'\d+\n'                                                  # 1
    r'(?P<box_16_cpp_contributions>\d{1,7}\.\d{2})\n'       # 3147.30
    r'(?P<province_of_employment>[A-Z]{2})\n'               # MB
    r'(?P<social_insurance_number>\d{3}\s+\d{3}\s+\d{3})\s+'# 961 653 359
    r'(?P<box_16a_second_cpp>[\d.]+)\n'                     # 0.00
    r'(?P<box_24_ei_insurable_earnings>\d{1,7}\.\d{2})\s+'  # 56394.00
    r'(?P<box_26_cpp_pensionable_earnings>\d{1,7}\.\d{2})\n'# 56394.00
    r'(?P<employee_last_name>[A-Z]+)\s+'                    # LI
    r'(?P<employee_first_name>[A-Za-z]+)\n'                 # Xinrong
    r'(?P<box_18_ei_premiums>\d{1,7}\.\d{2})\n'            # 924.82  ← EI premiums
    r'[^\n]+\n'                                              # 2 Millikin Rd
    r'(?P<employee_city>[A-Za-z\s]+),\s*'                   # Winnipeg,
    r'(?P<employee_province>[A-Z]{2})\s+'                   # MB
    r'(?P<employee_postal_code>[A-Z]\d[A-Z]\s*\d[A-Z]\d)\n'# R3T 3V4
    r'(?P<form_code>RC-\d+-\d+)'                            # RC-14-107
)
    match = re.search(t4_regex, text)
    if not match:
        return {}
    return match.groupdict()

def calculate_age(bod: str) -> int:
    # bod format: "YYYY-MM-DD"
    birth_date = datetime.strptime(bod, "%Y-%m-%d").date()
    today = date.today()

    age = today.year - birth_date.year

    # If birthday hasn't happened yet this year, subtract 1
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age

import re

def remove_sin_hyphens(sin_number: str) -> str:
    """
    Normalize a Canadian SIN by removing all non-digit characters
    and returning a strict 9-digit numeric string.

    Examples:
        "123-456-789" -> "123456789"
        "123 456 789" -> "123456789"
        "123.456.789" -> "123456789"
    """

    if not isinstance(sin_number, str):
        raise TypeError("SIN number must be a string.")

    cleaned = re.sub(r"\D+", "", sin_number.strip())

    if not re.fullmatch(r"\d{9}", cleaned):
        raise ValueError(
            "Invalid SIN number: must contain exactly 9 digits after normalization."
        )

    return cleaned

def render_markdown_table(data: list[dict]) -> str:
    """
    Convert a list of dictionaries into a markdown table.

    Example:
        [
            {"name": "John", "age": 30},
            {"name": "Alice", "age": 25}
        ]
    """

    if not data:
        return "No data available."

    sections = []

    for index, row in enumerate(data, start=1):
        lines = [
            f"### Record {index}",
            "",
            "| Field | Value |",
            "|---|---|"
        ]

        for key, value in row.items():
            if key not in ["id","created_at","updated_at"]:
                lines.append(f"| {key} | {value} |")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def render_slip_table(extracted: dict, doc_type: str,model:BaseModel) -> str:
    """Render the latest T4 or T5 slip as a markdown table."""
    
    slip_list = extracted.get("t4" if doc_type == "T4" else "t5", [])
    
    if not slip_list:
        return f"_No {doc_type} slip data found._"
    
    slip        = slip_list[-1]  # latest slip
    descriptions = {k: v.description for k, v in model.model_fields.items()}

    def fmt(value) -> str:
        if isinstance(value, float): return f"{value:,.2f}"
        if isinstance(value, int):   return f"{value:,}"
        return str(value) if value else "—"

    # Build rows
    rows = [
        f"| {descriptions.get(field, field)} | {fmt(value)} |"
        for field, value in slip.items()
        if field in descriptions
    ]

    header = f"| Description | Value |\n|---|---|"
    return "\n".join([header, *rows])