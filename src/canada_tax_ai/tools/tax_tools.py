"""
Canada T1 Personal Income Tax Return Algorithm
Tax year: 2024
Covers: employment, investment, capital gains, self-employment
"""

from dataclasses import dataclass, field
from typing import Optional

from canada_tax_ai.persist.repository import TaxSlipRepository
from ..core.agent_state import AgentState
from canada_tax_ai.models import TaxInputData, TaxResult, to_tax_input, validate_sin
from loguru import logger


# ── 2024 Federal brackets ──────────────────────────────────────────────────
FEDERAL_BRACKETS = [
    (57_375,   0.15),
    (57_375,   0.205),
    (63_511,   0.26),
    (70_649,   0.29),
    (float("inf"), 0.33),
]

# Basic personal amount (federal, 2024)
FEDERAL_BASIC_PERSONAL = 15_705

# CPP contribution rates/limits (2024)
CPP_RATE          = 0.0595
CPP_MAX_PENSIONABLE = 68_500
CPP_EXEMPTION     = 3_500

# EI premium rates (2024)
EI_RATE           = 0.0166
EI_MAX_INSURABLE  = 63_200

# Capital gains inclusion rate
CAPITAL_GAINS_INCLUSION = 0.50

# Dividend gross-up and federal credit rates (eligible dividends)
ELIGIBLE_DIV_GROSSUP = 0.38
ELIGIBLE_DIV_CREDIT  = 0.150198   # federal dividend tax credit rate

# ── Provincial rates (simplified flat approximation per province) ──────────
PROVINCIAL_RATES = {
    "AB": 0.10,
    "BC": 0.0506,  # bottom bracket
    "MB": 0.108,
    "NB": 0.094,
    "NL": 0.087,
    "NS": 0.0879,
    "NT": 0.059,
    "NU": 0.04,
    "ON": 0.0505,  # bottom bracket
    "PE": 0.0965,
    "QC": 0.14,
    "SK": 0.105,
    "YT": 0.064,
}

PROVINCIAL_BASIC_PERSONAL = {
    "AB": 21_003, "BC": 11_981, "MB": 15_780, "NB": 12_458,
    "NL": 10_818, "NS": 8_481,  "NT": 16_593, "NU": 17_925,
    "ON": 11_865, "PE": 12_000, "QC": 17_183, "SK": 17_661,
    "YT": 15_705,
}


def _apply_federal_brackets(taxable_income: float) -> float:
    """Apply graduated federal tax brackets."""
    tax = 0.0
    remaining = taxable_income
    for bracket_size, rate in FEDERAL_BRACKETS:
        if remaining <= 0:
            break
        taxable_in_bracket = min(remaining, bracket_size)
        tax += taxable_in_bracket * rate
        remaining -= taxable_in_bracket
    return tax


def _calculate_cpp(employment_income: float, cpp_paid: float) -> float:
    """
    Calculate CPP contributions owing (for self-employed, double rate).
    Returns the employee-share credit amount.
    """
    max_contrib = (CPP_MAX_PENSIONABLE - CPP_EXEMPTION) * CPP_RATE
    return min(cpp_paid, max_contrib)


def _calculate_ei(employment_income: float, ei_paid: float) -> float:
    """Returns the EI premiums credit amount."""
    max_premium = EI_MAX_INSURABLE * EI_RATE
    return min(ei_paid, max_premium)


def _non_refundable_credit(amount: float, rate: float = 0.15) -> float:
    """Convert a credit base amount to federal tax reduction (15% federal rate)."""
    return amount * rate

def calculate_tax(state: AgentState) -> TaxResult:
    def f(value: Optional[float]) -> float:
        """Convert None tax field to 0.0 for safe arithmetic."""
        return value or 0.0
    # inp: TaxInput
    profile = state.get("profile",{})
    logger.info(f"User Profile is {profile}")
    
    data = state.get("extracted_data", {})
    current_sin = data.get("sin", "").replace(" ", "")

    inp = to_tax_input(state.get("tax_input_data", {}))
    # if raw is None:
    #     inp = TaxInputData()
    # if isinstance(raw, TaxInputData):
    #     inp = raw          # already correct type (first run, before checkpoint)
    # if isinstance(raw, dict):
    #     inp = TaxInputData(**raw)  
    
    logger.info(f"Converted extracted data to TaxInput: {data} \r\n {inp}")
    r = TaxResult()
    if validate_sin(current_sin):
        r.sin = current_sin
    else:
        current_sin = getattr(profile, "sin", "").replace(" ", "")
        if validate_sin(current_sin):
            r.sin = current_sin
        else:
            logger.warning(f"Invalid or missing SIN: '{current_sin}' — proceeding without SIN in tax result.")
            raise ValueError(f"Unknown sin: {current_sin}")
    
    
    prov = getattr(profile, "province", "").upper()
    if prov not in PROVINCIAL_RATES:
        prov = getattr(inp, "province", "").upper()
    if prov not in PROVINCIAL_RATES:
        logger.warning(f"Province not found in input or profile: '{prov}' — defaulting")
        return {
            "messages": "Which province do you reside in? (You can reply with the full name, e.g., Ontario, or the abbreviation, e.g., ON.) This is needed to calculate your provincial tax and credits accurately.",
            "knowledge": state.get("knowledge", {}),
        }

    # ── STEP 1: Compute gross-up on eligible dividends ─────────────────────
    r.grossed_up_dividends = f(inp.eligible_dividends) * (1 + ELIGIBLE_DIV_GROSSUP)

    # ── STEP 2: Total income (line 15000) ──────────────────────────────────
    net_capital_gains = max(f(inp.capital_gains) - f(inp.capital_losses), 0)
    taxable_cap_gains  = net_capital_gains * CAPITAL_GAINS_INCLUSION

    r.total_income = (
        f(inp.employment_income)
        + r.grossed_up_dividends
        + f(inp.other_investment_income)
        + taxable_cap_gains
        + f(inp.self_employment_income)
    )

    # ── STEP 3: Net income (line 23600) ────────────────────────────────────
    deductions = (
        f(inp.rrsp_contribution)
        + f(inp.union_dues)
        + f(inp.childcare_expenses)
        + f(inp.moving_expenses)
        + f(inp.other_deductions)
    )
    r.net_income = max(r.total_income - deductions, 0)

    # ── STEP 4: Taxable income (line 26000) ────────────────────────────────
    # (Capital losses beyond gains already zeroed above; no further adjustment here)
    r.taxable_income = r.net_income

    # ── STEP 5: Federal tax before credits ─────────────────────────────────
    r.federal_tax_before_credits = _apply_federal_brackets(r.taxable_income)

    # ── STEP 6: Provincial tax (simplified) ────────────────────────────────
    prov_rate           = PROVINCIAL_RATES[prov]
    prov_basic          = PROVINCIAL_BASIC_PERSONAL.get(prov, 10_000)
    prov_basic_credit   = prov_basic * prov_rate
    r.provincial_tax    = max(r.taxable_income * prov_rate - prov_basic_credit, 0)
    r.total_provincial_credits = prov_basic_credit
    r.net_provincial_tax = r.provincial_tax

    # ── STEP 7: Federal non-refundable credits ─────────────────────────────
    cpp_credit = _calculate_cpp(f(inp.employment_income), f(inp.cpp_contributions))
    ei_credit  = _calculate_ei(f(inp.employment_income), f(inp.ei_premiums))

    r.federal_basic_personal_credit = _non_refundable_credit(FEDERAL_BASIC_PERSONAL)
    r.federal_cpp_credit            = _non_refundable_credit(cpp_credit)
    r.federal_ei_credit             = _non_refundable_credit(ei_credit)

    # Medical: only amount exceeding 3% of net income or $2,635 (lesser)
    medical_threshold = min(r.net_income * 0.03, 2_635)
    eligible_medical  = max(f(inp.medical_expenses) - medical_threshold, 0)
    r.federal_medical_credit = _non_refundable_credit(eligible_medical)

    # Charitable donations: 15% on first $200, 29% above $200
    if f(inp.charitable_donations) <= 200:
        r.federal_donation_credit = f(inp.charitable_donations) * 0.15
    else:
        r.federal_donation_credit = 200 * 0.15 + (f(inp.charitable_donations) - 200) * 0.29

    r.federal_tuition_credit  = _non_refundable_credit(f(inp.tuition_paid))
    r.federal_dividend_credit = f(inp.eligible_dividends) * ELIGIBLE_DIV_GROSSUP * ELIGIBLE_DIV_CREDIT

    r.total_federal_credits = (
        r.federal_basic_personal_credit
        + r.federal_cpp_credit
        + r.federal_ei_credit
        + r.federal_medical_credit
        + r.federal_donation_credit
        + r.federal_tuition_credit
        + r.federal_dividend_credit
    )

    # ── STEP 8: Net federal tax (line 42000) ───────────────────────────────
    r.net_federal_tax = max(r.federal_tax_before_credits - r.total_federal_credits, 0)

    # ── STEP 9: Combined tax payable (line 43500) ──────────────────────────
    r.combined_tax  = r.federal_tax_before_credits + r.provincial_tax
    r.total_payable = r.net_federal_tax + r.net_provincial_tax

    # ── STEP 10: Subtract withholdings and refundable credits ──────────────
    r.total_credits_and_payments = f(inp.federal_tax_withheld)   # add GST/HST credit, CCB etc. here

    # ── STEP 11: Balance owing / refund ────────────────────────────────────
    r.balance_owing = r.total_payable - r.total_credits_and_payments

    if r.balance_owing > 0:
        r.notes.append(f"Balance owing: ${r.balance_owing:,.2f} — due Apr 30 (Jun 15 for self-employed)")
    else:
        r.notes.append(f"Refund: ${abs(r.balance_owing):,.2f} — expect ~2 weeks via direct deposit")

    if f(inp.self_employment_income) > 0:
        self_emp_cpp = min(
            (f(inp.self_employment_income) - CPP_EXEMPTION) * CPP_RATE * 2,
            (CPP_MAX_PENSIONABLE - CPP_EXEMPTION) * CPP_RATE * 2
        )
        r.notes.append(
            f"Self-employed CPP (both shares): ~${self_emp_cpp:,.2f} "
            f"— deduct half on line 22200, credit half on Schedule 8"
        )
    logger.info(f"Calculated tax result: {r}")
    result = {"tax_result": r}

    repo = TaxSlipRepository()
    
    try:
        saved = repo.upsert(r, "tax_results")
        result["db_id"] = saved.get("id")
    except Exception as e:
        result["db_error"] = str(e)
        logger.error(f"Error saving tax result to database: {e}")

    return result
