from canatax import IncomeTaxCalculator
from .config import config

def calculate_tax(gross_income: float, rrsp: float = 0.0, other_deductions: float = 0.0, has_spouse: bool = False, children: int = 0) -> dict:
    taxable_income = max(0.0, gross_income - rrsp - other_deductions)
    estimate = IncomeTaxCalculator.calculate(income=taxable_income, province=config.PROVINCE, year=config.TAX_YEAR)
    extra_credits = (1200 if has_spouse else 0) + children * 800
    federal_tax = max(0.0, estimate.federal_tax - extra_credits * 0.145)
    provincial_tax = max(0.0, estimate.provincial_tax - extra_credits * 0.108)
    total_tax = federal_tax + provincial_tax + estimate.cpp + estimate.ei
    return {
        "gross_income": round(gross_income, 2),
        "taxable_income": round(taxable_income, 2),
        "federal_tax": round(federal_tax, 2),
        "provincial_tax": round(provincial_tax, 2),
        "cpp": round(estimate.cpp, 2),
        "ei": round(estimate.ei, 2),
        "total_tax": round(total_tax, 2),
        "net_income": round(estimate.net_income, 2),
        "estimated_refund_owing": round(gross_income - total_tax - taxable_income, 2),
    }
