from functools import reduce

from loguru import logger
from canada_tax_ai.models import TaxInput


def _safe_float(val) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _sum_field(slips: list[dict], field: str) -> float:
    """Sum a field across all slips in a list."""
    return sum(_safe_float(slip.get(field)) for slip in slips)


def _first_field(slips: list[dict], field: str, default=None):
    """Get first non-empty value of a field across slips."""
    for slip in slips:
        val = slip.get(field)
        if val:
            return val
    return default


def build_tax_input(t4_list: list[dict], t5_list: list[dict]) -> TaxInput:
    """
    Build TaxInput from multiple T4 and T5 slips.
    Numeric fields are summed across all slips.
    Non-numeric fields use first non-empty value.
    """
    # Fallback to empty list if None
    t4_list = t4_list or []
    t5_list = t5_list or []
    logger.info(f"Building TaxInput from {len(t4_list)} T4 slips and {len(t5_list)} T5 slips.")

    return TaxInput(
        # Province — first T4, fall back to ON
        province=_first_field(t4_list, "province_employment") or "ON",

        # ── Income ────────────────────────────────────────────────
        # Sum employment income across all T4s (e.g. two jobs)
        employment_income=_sum_field(t4_list, "gross_income"),

        # Sum eligible dividends across all T5s
        eligible_dividends=_sum_field(t5_list, "actual_dividends"),

        # Sum interest + foreign income across all T5s
        other_investment_income=(
            _sum_field(t5_list, "interest_income")
            + _sum_field(t5_list, "foreign_income")
        ),

        # Sum capital gains dividends across all T5s
        capital_gains=_sum_field(t5_list, "capital_gains_dividends"),

        capital_losses=0.0,           # requires Schedule 3
        self_employment_income=0.0,   # requires T2125

        # ── Deductions ────────────────────────────────────────────
        rrsp_deduction=_sum_field(t4_list, "rrsp"),
        union_dues=_sum_field(t4_list, "union_dues"),      # T4 Box 44
        childcare_expenses=0.0,       # requires Form T778
        moving_expenses=0.0,          # requires Form T1-M
        other_deductions=0.0,

        # ── Credits ───────────────────────────────────────────────
        medical_expenses=0.0,         # requires receipts
        charitable_donations=0.0,     # requires receipts
        tuition_paid=0.0,             # requires T2202

        # ── Withholdings ─────────────────────────────────────────
        # Sum across all T4s — multiple employers each withhold tax
        tax_withheld=_sum_field(t4_list, "tax_deducted"),  # T4 Box 22
        cpp_contributions=_sum_field(t4_list, "cpp"),      # T4 Box 16
        ei_premiums=_sum_field(t4_list, "ei"),             # T4 Box 18
    )