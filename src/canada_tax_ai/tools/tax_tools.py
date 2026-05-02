"""
Canada T1 Personal Income Tax Return Algorithm
Tax year: 2024
Covers: employment, investment, capital gains, self-employment
"""

from dataclasses import dataclass, field
from typing import Optional

from canada_tax_ai.persist.repository import TaxSlipRepository
from canada_tax_ai.tools.build_input import build_tax_input
from ..core.agent_state import AgentState
from canada_tax_ai.models import TaxResult, TaxInput, validate_sin
from loguru import logger
from dataclasses import asdict


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


def _extracted_data_to_tax_input(data: dict) -> TaxInput:
    """
    Convert extracted tax slip data (T4 + T5) into a TaxInput for calculate_tax().
    
    Handles:
    - Missing or None values (defaults to 0.0)
    - Province from T4 province_of_employment
    - T4 Box 22 → tax_withheld, Box 16 → cpp, Box 18 → ei
    - T5 eligible dividends, interest, capital gains dividends
    """

    def safe_float(value, default: float = 0.0) -> float:
        """Return float or default if value is None / empty string / unparseable."""
        if value is None or value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
        
    logger.info(f"Converting extracted data to TaxInput. Raw data keys: {data}")
    t4 = data.get("t4", [])
    t5 = data.get("t5", [])
    logger.info(f"Extracted data for tax input conversion: \n\r{t4[0].get("gross_income")} \n\r {t4[0].get("rrsp")}")

    return TaxInput(
        # Province from T4; fall back to "ON" if missing
        province=t4.get("province_employment") or "ON",

        # ── Income ────────────────────────────────────────────────
        employment_income       = safe_float(t4.get("gross_income")),

        # T5 Box 24 — actual amount of eligible dividends
        eligible_dividends      = safe_float(t5.get("actual_dividends")),

        # T5 Box 13 interest + Box 15 foreign income (if present)
        other_investment_income = (
            safe_float(t5.get("interest_income"))
            + safe_float(t5.get("foreign_income"))
        ),

        # T5 Box 18 capital gains dividends treated as gross gains
        capital_gains           = safe_float(t5.get("capital_gains_dividends")),
        capital_losses          = 0.0,          # not available on T4/T5; requires Schedule 3

        self_employment_income  = 0.0,          # requires T2125; not on T4/T5

        # ── Deductions ────────────────────────────────────────────
        rrsp_deduction          = safe_float(t4.get("rrsp")),
        union_dues              = safe_float(t4.get("union_dues")),       # T4 Box 44
        childcare_expenses      = 0.0,          # requires Form T778
        moving_expenses         = 0.0,          # requires Form T1-M
        other_deductions        = 0.0,

        # ── Credits ───────────────────────────────────────────────
        medical_expenses        = 0.0,          # requires receipts
        charitable_donations    = 0.0,          # requires receipts
        tuition_paid            = 0.0,          # requires T2202

        # ── Withholdings ─────────────────────────────────────────
        tax_withheld            = safe_float(t4.get("tax_deducted")),     # T4 Box 22
        cpp_contributions       = safe_float(t4.get("cpp")),              # T4 Box 16
        ei_premiums             = safe_float(t4.get("ei")),               # T4 Box 18
    )

def calculate_tax(state: AgentState) -> TaxResult:
    # inp: TaxInput
    data = state.get("extracted_data", {})
    current_sin = data.get("sin", "").replace(" ", "")
    inp = build_tax_input(data.get("t4", []), data.get("t5", []))
    logger.info(f"Converted extracted data to TaxInput: {data} \r\n {inp}")
    r = TaxResult()
    if validate_sin(current_sin):
        r.sin = current_sin
    else:
        logger.warning(f"Invalid or missing SIN: '{current_sin}' — proceeding without SIN in tax result.")
        raise ValueError(f"Unknown sin: {current_sin}")
    
    prov = inp.province.upper()

    if prov not in PROVINCIAL_RATES:
        raise ValueError(f"Unknown province code: {prov}")

    # ── STEP 1: Compute gross-up on eligible dividends ─────────────────────
    r.grossed_up_dividends = inp.eligible_dividends * (1 + ELIGIBLE_DIV_GROSSUP)

    # ── STEP 2: Total income (line 15000) ──────────────────────────────────
    net_capital_gains = max(inp.capital_gains - inp.capital_losses, 0)
    taxable_cap_gains  = net_capital_gains * CAPITAL_GAINS_INCLUSION

    r.total_income = (
        inp.employment_income
        + r.grossed_up_dividends
        + inp.other_investment_income
        + taxable_cap_gains
        + inp.self_employment_income
    )

    # ── STEP 3: Net income (line 23600) ────────────────────────────────────
    deductions = (
        inp.rrsp_deduction
        + inp.union_dues
        + inp.childcare_expenses
        + inp.moving_expenses
        + inp.other_deductions
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
    cpp_credit = _calculate_cpp(inp.employment_income, inp.cpp_contributions)
    ei_credit  = _calculate_ei(inp.employment_income, inp.ei_premiums)

    r.federal_basic_personal_credit = _non_refundable_credit(FEDERAL_BASIC_PERSONAL)
    r.federal_cpp_credit            = _non_refundable_credit(cpp_credit)
    r.federal_ei_credit             = _non_refundable_credit(ei_credit)

    # Medical: only amount exceeding 3% of net income or $2,635 (lesser)
    medical_threshold = min(r.net_income * 0.03, 2_635)
    eligible_medical  = max(inp.medical_expenses - medical_threshold, 0)
    r.federal_medical_credit = _non_refundable_credit(eligible_medical)

    # Charitable donations: 15% on first $200, 29% above $200
    if inp.charitable_donations <= 200:
        r.federal_donation_credit = inp.charitable_donations * 0.15
    else:
        r.federal_donation_credit = 200 * 0.15 + (inp.charitable_donations - 200) * 0.29

    r.federal_tuition_credit  = _non_refundable_credit(inp.tuition_paid)
    r.federal_dividend_credit = inp.eligible_dividends * ELIGIBLE_DIV_GROSSUP * ELIGIBLE_DIV_CREDIT

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
    r.total_credits_and_payments = inp.tax_withheld   # add GST/HST credit, CCB etc. here

    # ── STEP 11: Balance owing / refund ────────────────────────────────────
    r.balance_owing = r.total_payable - r.total_credits_and_payments

    if r.balance_owing > 0:
        r.notes.append(f"Balance owing: ${r.balance_owing:,.2f} — due Apr 30 (Jun 15 for self-employed)")
    else:
        r.notes.append(f"Refund: ${abs(r.balance_owing):,.2f} — expect ~2 weeks via direct deposit")

    if inp.self_employment_income > 0:
        self_emp_cpp = min(
            (inp.self_employment_income - CPP_EXEMPTION) * CPP_RATE * 2,
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


def print_summary(r: TaxResult) -> None:
    """Print a formatted T1 summary."""
    width = 52
    sep   = "─" * width

    def row(label, value, indent=0):
        prefix = "  " * indent
        print(f"  {prefix}{label:<{width - 4 - len(prefix)}} ${value:>12,.2f}")

    print(f"\n{'═' * (width + 4)}")
    print(f"  CANADA T1 TAX RETURN SUMMARY")
    print(f"{'═' * (width + 4)}")

    print(f"\n  INCOME")
    print(f"  {sep}")
    row("Grossed-up dividends included", r.grossed_up_dividends)
    row("Total income          (line 15000)", r.total_income)
    row("Net income            (line 23600)", r.net_income)
    row("Taxable income        (line 26000)", r.taxable_income)

    print(f"\n  TAX CALCULATION")
    print(f"  {sep}")
    row("Federal tax before credits",    r.federal_tax_before_credits)
    row("Less: total federal credits",  -r.total_federal_credits)
    row("Net federal tax    (line 42000)", r.net_federal_tax)
    row("Provincial/territorial tax",    r.net_provincial_tax)
    row("Total payable      (line 43500)", r.total_payable)

    print(f"\n  PAYMENTS & WITHHOLDINGS")
    print(f"  {sep}")
    row("Tax withheld (T4 Box 22 etc.)", r.total_credits_and_payments)

    print(f"\n  {'═' * width}")
    label = "BALANCE OWING" if r.balance_owing >= 0 else "REFUND"
    print(f"  {label:<{width - 2}} ${abs(r.balance_owing):>12,.2f}")
    print(f"  {'═' * width}")

    if r.notes:
        print(f"\n  NOTES")
        for note in r.notes:
            print(f"  • {note}")
    print()


# ── Example usage ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    taxpayer = TaxInput(
        province             = "ON",

        # Income
        employment_income    = 95_000,
        eligible_dividends   = 5_000,
        other_investment_income = 1_200,
        capital_gains        = 8_000,
        capital_losses       = 2_000,
        self_employment_income = 12_000,

        # Deductions
        rrsp_deduction       = 10_000,
        union_dues           = 800,
        childcare_expenses   = 4_000,

        # Credits
        medical_expenses     = 3_500,
        charitable_donations = 500,
        tuition_paid         = 0,

        # Withholdings
        tax_withheld         = 22_000,
        cpp_contributions    = 3_300,
        ei_premiums          = 1_049,
    )
    

    result = calculate_tax(taxpayer)
    print_summary(result)
