# prompts/tax_advisor.py
from langchain.messages import SystemMessage, ToolMessage

from canada_tax_ai.core.agent_state import AgentState
from canada_tax_ai.models import TaxInputData, UserProfile
from canada_tax_ai.prompt.prompt_registry import sys_prompt, temp_prompt
from canada_tax_ai.prompt.provincial_credits import get_provincial_credits, get_province, PROVINCES
from loguru import logger
import json
from datetime import datetime
from canada_tax_ai.utils import calculate_age
from dataclasses import dataclass, asdict

BASIC_INFORMATION_PROMPT = """
You are a professional financial expert assisting the user with preparing their personal income tax return (Canada CRA is the default; if the user is in another country, confirm the tax authority first).  
Follow the below STEPs to collect basic information. Ask ONE question at a time, keep your tone friendly, professional, and concise. Only move to the next question after the user answers. Never dump all questions at once.  
Ask every item and confirm nothing is missing before summarizing.

STEP 1:You MUST confirm a couple of details with user first?
-The user's preferred language
-The user's province or territory (this is needed for your tax file)
##Rules (must be followed strictly):
    - Always ask for both fields if missing in UserProfile.
    - Once the user provides a preferred language, switch ALL subsequent responses to that language.
    - Clearly explain that the province is required for the user’s tax file.
    - Accept province as either full name (e.g., Ontario) or abbreviation (e.g., ON).
    - Normalize province to the 2-letter code: AB, BC, MB, NB, NL, NS, NT, NU, ON, PE, QC, SK, YT.
    - If the province is invalid or not Canadian, ask the user to correct it.
    - Do NOT assume or default values.

STEP 2:Collect and confirm all necessary information about the user's profile.
##Rules (must be followed strictly):
    1. The UserProfile entities are automatically updated from every user message and tool result using direct reflection.
    2. For UserProfile entity:
        - If ANY property is blank, empty, or missing, ask the user for the missing properties (maximum 1-2 questions at a time).
        - If address is provided, call the tool `verify_addresss` to validate it. You MUST replace the address with the tool result in your final answer.If the tool returns invalid, ask the user to re-enter a valid address.
        - If SIN is provided, validate it using the standard SIN validation algorithm. If invalid, ask the user to re-enter a valid SIN.You MUST format the SIN in the standard format (e.g., 123-456-789) before saving to UserProfile.
        - Only when ALL properties of UserProfile have values, You MUST send a clear summary and ask: "Is this correct? Reply YES or provide any corrections."
    3. Never ask again about any property or topic that is already confirmed.
    4. If the user want to update any existing property, ask for the new value and update it in UserProfile. Do NOT overwrite any existing value unless the user explicitly provides a correction.
    5. Always keep the tone friendly, professional, and concise. Never ask multiple questions at once.
    6. At the end of every reply, you MUST output:
        [Memory Update]
        Strictly output ONLY a single valid JSON object that exactly conforms to the Pydantic schema of the UserProfile models defined below, with no additional text, explanations, markdown, or code blocks before or after the JSON.
        class UserProfile(BaseModel):
          last_name: str 
          first_name: str 
          phone_number: str
          date_of_birth: str 
          address: str 
          marital_status: str 
          dependents: List[Dict] 
          sin: str 
          province: str
          language: str


      Current knowledge base:
      {knowledge_json}


      Current UserProfile entity:
      {profile_json}

      Update entities with any new property values.
      Keep all previous values unless explicitly updated.
"""

TAX_ADVISOR_SYSTEM_PROMPT = """
You are an expert Canadian tax advisor specializing in maximizing tax refunds.
You have deep knowledge of CRA rules, tax credits, and deductions for the current tax year.

## Your Goal


Guide the user to claim every eligible deduction and credit to maximize their refund based on the confirmed UserProfile and any confirmed slips, proactively identify ALL applicable tax credits and deductions for this user.
Be proactive — suggest things they may have forgotten or not know about.
If you’ve already provided this information, just let me know if it’s still correct.

## What You Know About This User
Province: {province} ({province_name})
Filing Year: {filing_year}
Marital Status: {marital_status}
Has Dependants: {has_dependants}
Already Claimed: {already_claimed}

## Confirmed Income Slips
{confirmed_slips}

## Provincial Context
{provincial_context}

## Rules
    - Ask ONE topic at a time — never overwhelm with multiple questions
    - When user says NO to a category, move on immediately
    - When user says YES, ask for the specific amount or slip
    - Always explain WHY something saves them money (rough estimate if possible)
    - Flag high-value opportunities first
    - Never ask about something already confirmed or denied
    - Keep responses concise and friendly

You MUST call the tool `update_tax_data` after the user provides the specific amount according to tool’s schema definition.
Tool Execution Policy (Schema Compliance Required):

You MUST call the tool `update_profile_data` after the user provides any new or updated profile information according to tool’s schema definition.

1. Always derive tool inputs strictly from the tool’s schema definition.
2. Input must be a valid JSON-like dictionary matching:
   - required fields exactly
   - correct data types
   - no additional or unexpected keys

3. Data validation rules:
   - number fields → must be numeric (no symbols, commas, or text)
   - string fields → must match expected format if defined
   - optional fields → include only if explicitly provided

4. Missing data handling:
   - If any required field is missing → DO NOT call the tool
   - Instead, ask the user only for the missing values

5. Output rules:
   - Never wrap tool input in markdown or code blocks
   - Never include explanations when emitting tool input
   - Tool input must be returned as a raw dictionary/object only
"""


# ------------------------------------------------------------------ #
#  Federal opportunities — apply to all provinces
# ------------------------------------------------------------------ #
FEDERAL_OPPORTUNITIES = [

    # ── Tier 1: Almost always applicable ──────────────────────────
    {
        "id": "rrsp",
        "tier": 1,
        "title": "RRSP Contributions",
        "slip": "Receipts from bank",
        "trigger": "always",
        "prompt": """
Do you have any RRSP contributions for {filing_year} (including first 60 days of {next_year})?

Every $1,000 contributed saves ~${rrsp_savings} at your income level.
This is one of the most powerful deductions available.

What was your total RRSP contribution this year?

""",
        "value_hint": "Saves ~{marginal_rate}% of contributed amount"
    },
    {
        "id": "cpp_ei_withheld",
        "tier": 1,
        "title": "CPP/EI Credits",
        "slip": "T4 Box 16, 18",
        "trigger": "has_t4",
        "auto_apply": True,
        "prompt": """
Already extracted tax data from T4 slip(s):
${already_extracted_tax_data}

RULES:
- If tax data has already been extracted (provided in <already_extracted_tax_data>),
  NEVER ask the user to re-enter those values.
- Use the extracted values directly in all calculations.
- Only ask the user for values that are missing or not yet extracted.
""",
        "value_hint": "Automatic from T4"
    },
    {
        "id": "basic_personal",
        "tier": 1,
        "title": "Basic Personal Amount",
        "slip": "Automatic",
        "trigger": "always",
        "auto_apply": True,
        "prompt": "Federal basic personal amount of $16,129 automatically applied. ✅",
        "value_hint": "Automatic"
    },

    # ── Tier 2: Very common ────────────────────────────────────────
    {
        "id": "medical_expenses",
        "tier": 2,
        "title": "Medical Expenses",
        "slip": "Receipts",
        "trigger": "always",
        "prompt": """
Did you pay out-of-pocket medical expenses in {filing_year} for yourself{spouse_text}{dependant_text}?

Eligible expenses include:
- Prescriptions & medications
- Dental (cleanings, fillings, braces)
- Glasses, contacts, laser eye surgery
- Physiotherapy, chiropractic, massage (if prescribed)
- Medical travel over 40km
- Private health insurance premiums
- Mental health therapy

Claim amounts exceeding 3% of net income (~${medical_threshold}).
Even $2,000 in expenses could generate a ~$300 credit.

Do you have medical receipts to claim?
""",
        "value_hint": "Credit on amounts exceeding 3% of net income"
    },
    {
        "id": "charitable_donations",
        "tier": 2,
        "title": "Donations and Gifts",
        "slip": "Official tax receipts",
        "trigger": "always",
        "prompt": """
Did you make any charitable donations in {filing_year}? (Or unclaimed donations from past 5 years?)

- 15% federal credit on first $200
- 29–33% federal credit above $200
- Plus provincial credit on top

A $500 donation saves ~$150 in taxes.
Do you have donation receipts?
""",
        "value_hint": "29-33% credit on donations over $200"
    },
    {
        "id": "union_dues",
        "tier": 2,
        "title": "Union / Professional Dues",
        "slip": "T4 Box 44 or receipts",
        "trigger": "always",
        "prompt": """
Did you pay union dues, professional fees, or association dues in {filing_year}?

These are 100% deductible — $800 in dues saves ~${union_savings} at your rate.
Check T4 Box 44 first. Any dues NOT already on your T4?
""",
        "value_hint": "100% deductible at marginal rate"
    },
    {
        "id": "work_from_home",
        "tier": 2,
        "title": "Work-From-Home Expenses",
        "slip": "T2200 + receipts",
        "trigger": "has_t4",
        "prompt": """
Did you work from home in {filing_year} with a T2200 from your employer?

Deductible expenses include:
- Internet (work portion)
- Electricity & heat (work portion)
- Home office supplies
- Rent (work portion)

Did you work from home and have a T2200?
""",
        "value_hint": "Typically $500–$2,000+ deduction"
    },

    # ── Tier 3: Situational ────────────────────────────────────────
    {
        "id": "tuition",
        "tier": 3,
        "title": "Tuition and Education Amounts",
        "slip": "T2202",
        "trigger": "always",
        "prompt": """
Did you or a dependant pay post-secondary tuition in {filing_year}?

- 15% federal non-refundable credit
- Unused amounts carry forward indefinitely
- Can transfer up to $5,000 to a parent/spouse

Do you have a T2202 from a college or university?
""",
        "value_hint": "15% credit on tuition paid"
    },
    {
        "id": "canada_training_credit",
        "tier": 3,
        "title": "Canada Training Credit",
        "slip": "T2202 or receipts",
        "trigger": "always",
        "prompt": """
Did you take eligible courses or training in {filing_year}?

- Accumulates $250/year (lifetime max $5,000)
- Covers 50% of eligible tuition/fees
- REFUNDABLE — you get it even with no tax owing

Check CRA My Account for your limit. Did you take any courses?
""",
        "value_hint": "Refundable — money back even with no tax owing"
    },
    {
        "id": "spouse_common_law",
        "tier": 3,
        "title": "Spouse or Common-Law Partner",
        "slip": "Their SIN required",
        "trigger": "marital_status_unknown",
        "prompt": """
Do you have a spouse or common-law partner?

If their net income was below $16,129:
- Spousal amount credit up to $2,419 federally
- Pension income splitting (up to 50%)
- Transfer unused credits (tuition, disability, age)
- Combine medical/donations for larger credits

Are you married or in a common-law relationship?
""",
        "value_hint": "Up to $2,419 + pension splitting"
    },
    {
        "id": "dependants",
        "tier": 3,
        "title": "Dependants and Child Credits",
        "slip": "None",
        "trigger": "always",
        "prompt": """
Do you have children or dependants?

You may qualify for:
- Canada Child Benefit (CCB) — tax-free monthly payments
- Amount for eligible dependant (single parent) — up to $2,419
- Child care expenses (T778)
- Disability amount transfer (T2201)
- Caregiver amount

Do you have children or dependants to declare?
""",
        "value_hint": "Potentially $1,000s in credits"
    },
    {
        "id": "moving_expenses",
        "tier": 3,
        "title": "Moving Expenses",
        "slip": "Receipts — Form T1-M",
        "trigger": "always",
        "prompt": """
Did you move in {filing_year} for a new job, business, or full-time school?

If you moved 40km+ closer to your new location, deduct:
- Moving truck/company
- Travel (gas, hotels)
- Temporary accommodation (up to 15 days)
- Storage fees
- Real estate commissions and legal fees

Did you relocate for work or school?
""",
        "value_hint": "Full deduction of eligible moving costs"
    },
    {
        "id": "investment_carrying_charges",
        "tier": 3,
        "title": "Investment Carrying Charges",
        "slip": "Advisor statements",
        "trigger": "has_t5",
        "prompt": """
Since you have investment income (T5), you may deduct:
- Investment advisor fees (non-registered accounts only)
- Interest on money borrowed to invest
- Safety deposit box fees

Did you pay fees for managing non-registered investments?
""",
        "value_hint": "100% deductible — reduces investment income"
    },
    {
        "id": "capital_gains",
        "tier": 3,
        "title": "Capital Gains or Losses",
        "slip": "T5008 or brokerage statements",
        "trigger": "has_t5",
        "prompt": """
Did you sell investments, crypto, or property in {filing_year}?

- Gains: 50% inclusion rate (only half taxable)
- Losses offset gains — carry back 3 years or forward indefinitely
- Principal residence sale may be fully exempt

Do you have capital gains or losses to report?
""",
        "value_hint": "Losses offset gains from prior/future years"
    },
    {
        "id": "home_buyers",
        "tier": 3,
        "title": "First-Time Home Buyers' Amount",
        "slip": "Purchase records",
        "trigger": "always",
        "prompt": """
Did you buy your first home in {filing_year}?

- $10,000 credit → worth $1,500 federally
- Neither you nor partner owned a home in past 4 years

Did you purchase a home this year?
""",
        "value_hint": "$1,500 federal tax credit"
    },
    {
        "id": "disability",
        "tier": 3,
        "title": "Disability Amount",
        "slip": "T2201 on file with CRA",
        "trigger": "always",
        "prompt": """
Do you or a dependant have a severe prolonged physical or mental impairment?

With an approved T2201:
- $9,428 federal disability amount (~$1,414 credit)
- Plus provincial disability credits
- Unused amount transfers to supporting family member

Do you or a dependant have a disability tax certificate?
""",
        "value_hint": "Up to $1,414 federal + provincial credit"
    },
    {
        "id": "student_loan_interest",
        "tier": 3,
        "title": "Student Loan Interest",
        "slip": "Statement from lender",
        "trigger": "always",
        "prompt": """
Did you pay interest on a government student loan in {filing_year}?

- 15% federal credit on interest paid
- Carries forward 5 years if unused

Did you make student loan interest payments?
""",
        "value_hint": "15% credit on interest paid"
    },
    {
        "id": "northern_residents",
        "tier": 3,
        "title": "Northern Residents Deduction",
        "slip": "Travel receipts",
        "trigger": "province_north",
        "prompt": """
Since you live in {province_name}, you qualify for the Northern Residents Deduction:

- Basic residency deduction: up to $24/day
- Additional residency deduction (remote zones)
- Travel benefit deduction for personal trips

Did you take any personal travel trips in {filing_year}?
""",
        "value_hint": "Up to $8,760/year basic + travel"
    },
    {
        "id": "rental_income",
        "tier": 3,
        "title": "Rental Income",
        "slip": "Receipts and records",
        "trigger": "always",
        "prompt": """
Did you earn rental income in {filing_year} from property or a room in your home?

Deductible expenses:
- Mortgage interest (not principal)
- Property taxes, insurance
- Repairs and maintenance
- Depreciation (CCA)
- Utilities (if included in rent)

Did you receive any rental income?
""",
        "value_hint": "Expenses reduce taxable rental income"
    },
]


# ------------------------------------------------------------------ #
#  Trigger evaluation
# ------------------------------------------------------------------ #
NORTHERN_PROVINCES = {"NT", "NU", "YT"}


def evaluate_trigger(
    trigger: str,
    province: str,
    has_t4: bool,
    has_t5: bool,
    marital_status: str,
    is_senior: bool,
    has_dependants: bool,
    is_investor: bool,
    is_farmer: bool,
    is_self_employed: bool,
    is_under_25: bool,
) -> bool:
    return {
        "always":                True,
        "has_t4":                has_t4,
        "has_t5":                has_t5,
        "marital_status_unknown": not marital_status,
        "province_north":        province in NORTHERN_PROVINCES,
        "senior":                is_senior,
        "married":               marital_status in ("married", "common-law"),
        "has_dependants":        has_dependants,
        "investor":              is_investor,
        "farmer":                is_farmer,
        "self_employed":         is_self_employed,
        "under_25":              is_under_25,
    }.get(trigger, False)


# ------------------------------------------------------------------ #
#  Build dynamic opportunity list = federal + provincial
# ------------------------------------------------------------------ #
def build_opportunity_list(
    province: str,
    filing_year: int,
    has_t4: bool = False,
    has_t5: bool = False,
    marital_status: str = "",
    is_senior: bool = False,
    has_dependants: bool = False,
    is_investor: bool = False,
    is_farmer: bool = False,
    is_self_employed: bool = False,
    is_under_25: bool = False,
) -> list[dict]:
    """
    Combine federal opportunities + provincial credits
    into one prioritized list for the advisor to work through.
    """
    trigger_kwargs = dict(
        province=province,
        has_t4=has_t4, has_t5=has_t5,
        marital_status=marital_status,
        is_senior=is_senior, has_dependants=has_dependants,
        is_investor=is_investor, is_farmer=is_farmer,
        is_self_employed=is_self_employed, is_under_25=is_under_25,
    )

    # Federal opportunities
    federal = [
        opp for opp in FEDERAL_OPPORTUNITIES
        if evaluate_trigger(opp.get("trigger", "always"), **trigger_kwargs)
    ]

    # Provincial credits → convert to opportunity dict format
    provincial_credits = get_provincial_credits(
        province_code=province,
        filing_year=filing_year,
        is_senior=is_senior,
        is_married=marital_status in ("married", "common-law"),
        has_dependants=has_dependants,
        is_investor=is_investor,
        is_farmer=is_farmer,
        is_self_employed=is_self_employed,
        is_under_25=is_under_25,
        has_t4=has_t4,
        has_t5=has_t5,
    )

    provincial = [
        {
            "id":         f"provincial_{c.id}",
            "tier":       3,
            "title":      c.title,
            "slip":       c.slip,
            "trigger":    c.trigger,
            "prompt":     c.question.replace("{filing_year}", str(filing_year)),
            "value_hint": c.value_hint,
            "auto_apply": c.question.endswith("✅"),
            "provincial": True,
        }
        for c in provincial_credits
    ]

    # Merge: federal first (tier 1→3), then provincial
    all_opps = federal + provincial
    return sorted(all_opps, key=lambda x: (x["tier"], x.get("provincial", False)))


# ------------------------------------------------------------------ #
#  Get next opportunity
# ------------------------------------------------------------------ #
def get_next_opportunity(
    already_claimed: list[str],
    already_denied: list[str],
    province: str,
    filing_year: int,
    has_t4: bool = False,
    has_t5: bool = False,
    marital_status: str = "",
    is_senior: bool = False,
    has_dependants: bool = False,
    is_investor: bool = False,
    is_farmer: bool = False,
    is_self_employed: bool = False,
    is_under_25: bool = False,
) -> dict | None:
    """Return next unchecked opportunity for this user."""
    done = set(already_claimed + already_denied)

    opportunities = build_opportunity_list(
        province=province,
        filing_year=filing_year,
        has_t4=has_t4, has_t5=has_t5,
        marital_status=marital_status,
        is_senior=is_senior,
        has_dependants=has_dependants,
        is_investor=is_investor,
        is_farmer=is_farmer,
        is_self_employed=is_self_employed,
        is_under_25=is_under_25,
    )

    for opp in opportunities:
        if opp["id"] in done:
            continue
        if opp.get("auto_apply"):
            continue
        return opp

    return None


# ------------------------------------------------------------------ #
#  Build system prompt
# ------------------------------------------------------------------ #
def build_advisor_prompt(
    province: str,
    filing_year: int,
    marital_status: str,
    has_dependants: bool,
    confirmed_slips: list[str],
    already_claimed: list[str],
    marginal_rate: float,
    net_income: float = 50_000,
    cpp: float = 0,
    ei: float = 0,
    already_extracted_tax_data: str = "{}",
    is_senior: bool = False,
    is_investor: bool = False,
    is_farmer: bool = False,
    is_self_employed: bool = False,
    is_under_25: bool = False,
) -> str:
    province_config = get_province(province)
    province_name = province_config.name

    # Build provincial credits summary for system prompt
    credits = get_provincial_credits(
        province_code=province,
        filing_year=filing_year,
        is_senior=is_senior,
        is_married=marital_status in ("married", "common-law"),
        has_dependants=has_dependants,
        is_investor=is_investor,
        is_farmer=is_farmer,
        is_self_employed=is_self_employed,
        is_under_25=is_under_25,
    )
    provincial_context = "\n".join(
        f"• {c.title} ({c.value_hint})"
        for c in credits
        if not c.question.endswith("✅")
    ) or "None identified yet."

    return TAX_ADVISOR_SYSTEM_PROMPT.format(
        province=province,
        province_name=province_name,
        filing_year=filing_year,
        ei=ei,
        cpp=cpp,
        marital_status=marital_status or "unknown",
        has_dependants="Yes" if has_dependants else "No",
        already_claimed=", ".join(already_claimed) if already_claimed else "None yet",
        confirmed_slips=", ".join(confirmed_slips) if confirmed_slips else "None uploaded yet",
        provincial_context=provincial_context,
        already_extracted_tax_data=already_extracted_tax_data,
    )

def advisor_message(state: AgentState):
    profile = state.get("profile", {})
    knowledge_json = json.dumps(state.get("knowledge", {}), ensure_ascii=False, indent=2)
    # existing = state.get("extracted_data", {})
    logger.info(f"Current UserProfile Type: {type(profile)}")
    logger.info(f"Current knowledge: {knowledge_json}")
    # profile_json = json.dumps(profile)

    if not _is_user_profile_complete(state):
        logger.warning("UserProfile is incomplete. Prompting for missing information before proceeding to tax advice.")
        system_message = SystemMessage(content=temp_prompt("user_profile", "v1",knowledge_json=knowledge_json, profile_json=profile))
        return [system_message]+ state["messages"]

    province       = getattr(profile, "province", "ON")
    marital_status = getattr(profile, "marital_status", "")
    filing_year    = datetime.now().strftime("%Y")
    
    # is_senior      = getattr(profile, "age", 0) >= 65
    # is_under_25    = getattr(profile, "age", 30) < 25

    date_of_birth = getattr(profile, "date_of_birth")
    if date_of_birth not in (None, "", "None", "null", {},[]):
        age = calculate_age(date_of_birth)
        is_senior      = age >= 65
        is_under_25    = age < 25

    already_claimed = state.get("already_claimed", [])
    already_denied  = state.get("already_denied", [])


    
    logger.info(f"state is {state}")

    taxslips = state.get("extracted_data")
    logger.info(f"Extracted tax slips: {taxslips}")
    t4 = taxslips.get("t4", []) if taxslips else []
    logger.info(f"t4 is {t4}")
    t5 = taxslips.get("t5", []) if taxslips else []
    logger.info(f"t5 is {t5}")
    has_t4 = bool(t4)
    logger.info(f"t4 is {has_t4}")

    has_t5 = bool(t5)
    logger.info(f"t5 is {has_t5}")

    # inp = build_tax_input(t4, t5)
    raw = state.get("tax_input_data", {})
    if raw is None:
        input_data = TaxInputData()
    if isinstance(raw, TaxInputData):
        input_data = raw          # already correct type (first run, before checkpoint)
    if isinstance(raw, dict):
        input_data = TaxInputData(**raw)  

    next_opp = get_next_opportunity(
        already_claimed=already_claimed,
        already_denied=already_denied,
        province=province,
        filing_year=filing_year,
        has_t4=has_t4,
        has_t5=has_t5,
        marital_status=marital_status,
        is_senior=is_senior,
        has_dependants=bool(getattr(profile, "dependants", False)),
        is_investor=has_t5,
        is_farmer=getattr(profile, "is_farmer", False),
        is_self_employed=getattr(profile, "is_self_employed", False),
        is_under_25=is_under_25,
    )

    system = build_advisor_prompt(
        province=province,
        filing_year=filing_year,
        marital_status=marital_status,
        has_dependants=bool(getattr(profile, "dependants", False)),
        confirmed_slips=[str(x) for x in t4] + [str(x) for x in t5] if taxslips else [],
        already_claimed=already_claimed,
        marginal_rate=state.get("marginal_rate", 33),
        net_income=input_data.employment_income if input_data.employment_income else 50_000,
        # cpp=inp.cpp_contributions if inp.cpp_contributions else 0,
        # ei=inp.ei_premiums if inp.ei_premiums else 0,
        already_extracted_tax_data=input_data.model_dump() if input_data else "{}",
        is_senior=is_senior,
        is_investor=has_t5,
        is_farmer=getattr(profile, "is_farmer", False),
        is_self_employed=getattr(profile, "is_self_employed", False),
        is_under_25=is_under_25,
    )

    if next_opp:
        system += f"\n\n## Now Ask About\n{next_opp['prompt']}"
        system += f"\nValue to user: {next_opp['value_hint']}"
        system += f"\nRequired slip: {next_opp['slip']}"
    else:
        system += "\n\n## Status\nAll opportunities have been reviewed. Summarize what was claimed and generate the final tax estimate."

    messages = [SystemMessage(content=system)] + state["messages"]
    return messages

# Helper function (add this once, anywhere before the graph)
def _is_user_profile_complete(state: AgentState) -> bool:
    """Return True ONLY when UserProfile is complete AND the last message is NOT a tool result"""
    print("Checking if UserProfile is complete...")
    user = state.get("profile", {})
    if not user:
        return False
    
    # Check if ALL fields are filled
    all_filled = True
    for field in UserProfile.model_fields:
        value = user.get(field) if isinstance(user, dict) else getattr(user, field, None)
        if value in (None, "", "None", "null", {}):
            all_filled = False
            break
    
    # Prevent loop: if the last message is already a ToolMessage (save just happened), stop
    last_msg = state["messages"][-1] if state["messages"] else None
    if isinstance(last_msg, ToolMessage):
        print(f"Checking profile completeness: all_filled={all_filled}, last_msg_type={type(last_msg).__name__}")
        return False
    
    return all_filled