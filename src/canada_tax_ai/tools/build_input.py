from functools import reduce

from loguru import logger
from canada_tax_ai.models import TaxInputData
from canada_tax_ai.models import TaxInputData
from typing import List, Dict, Optional


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

def update_tax_input_from_dict(existing: TaxInputData, updates: dict) -> TaxInputData:
    """
    Update existing TaxInputData with a partial dict of new values.
    Only updates fields present in the dict — all other fields unchanged.
    """
    if not updates:
        return existing

    current = existing.model_dump()

    for field, value in updates.items():
        if field not in current:
            logger.warning(f"⚠ Unknown field '{field}' — skipped")
            continue
        if value is not None:
            logger.info(f"  ✅ {field}: {current.get(field)} → {value}")
            current[field] = value

    return TaxInputData(**current)

def update_tax_input(
    existing: TaxInputData,
    t4_list: list[dict],
    t5_list: list[dict]
) -> TaxInputData:
    """
    Update existing TaxInputData with values from T4/T5 slips.
    - Slip values only fill None fields — never overwrite user-provided values.
    - Zero slip values are skipped (stored as None).
    """
    t4_list = t4_list or []
    t5_list = t5_list or []
    logger.info(f"Updating TaxInputData from {len(t4_list)} T4 and {len(t5_list)} T5 slips.")

    def none_if_zero(value: float) -> Optional[float]:
        return value if value else None
    
    # ── Compute from slips ────────────────────────────────────────────────
    slip_values = {
        # Province — first T4, fall back to ON
        "province": _first_field(t4_list, "province_employment"),
        # T4
        "employment_income":    none_if_zero(_sum_field(t4_list, "gross_income")),
        "rrsp_contribution":    none_if_zero(_sum_field(t4_list, "rrsp")),
        "union_dues":           none_if_zero(_sum_field(t4_list, "union_dues")),
        "federal_tax_withheld": none_if_zero(_sum_field(t4_list, "tax_deducted")),
        "cpp_contributions":    none_if_zero(_sum_field(t4_list, "cpp")),
        "ei_premiums":          none_if_zero(_sum_field(t4_list, "ei")),
        # T5
        "eligible_dividends":   none_if_zero(
                                    _sum_field(t5_list, "actual_dividends") +
                                    _sum_field(t5_list, "actual_amount_other_dividends")
                                ),
        "capital_gains":        none_if_zero(_sum_field(t5_list, "capital_gains_dividends")),
    }

    # ── Merge: existing value wins, slip value fills None fields ──────────

    logger.info(f"Existing TaxInputData Type is {type(existing)}")
    logger.info(f"Existing TaxInputData before update: {existing.model_dump(exclude_none=True)}")
    current = existing.model_dump()
    for field, slip_value in slip_values.items():
        if current.get(field) is None and slip_value is not None:
            current[field] = slip_value
            logger.info(f"  ✅ {field} filled from slip: {slip_value}")
        elif current.get(field) is not None:
            logger.info(f"  ⏭ {field} kept user value: {current[field]}")

    return TaxInputData(**current)
