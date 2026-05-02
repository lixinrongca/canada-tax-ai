# models.py
import re

from pydantic import BaseModel, Field, field_validator
from pydantic import BaseModel, Field
from typing import List, Dict
from dataclasses import dataclass, field

class UserProfile(BaseModel):
    last_name: str = Field("", pattern=r"^[A-Za-z\-']+$", description="User's last name")
    first_name: str = Field("", pattern=r"^[A-Za-z\-']+$", description="User's first name")
    phone_number: str = Field("",pattern=r"^\+?1?\d{10,15}$",description="User's phone number")
    date_of_birth: str = Field("",pattern=r"^\d{4}-\d{2}-\d{2}$",description="Date of birth in YYYY-MM-DD format")
    address: str = Field("", min_length=5, description="Current residential address")
    marital_status: str = Field("",pattern=r"^(single|married|common-law|separated|divorced|widowed)$",description="Marital status")
    dependents: List[Dict] = Field(default_factory=list,description="List of dependents with name, DOB, and relationship")
    sin: str = Field("", pattern=r"^\d{3} \d{3} \d{3}$", description="Social Insurance Number (SIN) in format XXX XXX XXX")
    province: str = Field("", description="Province of residence for tax purposes")
    
    # sin: str = ""
    # @field_validator("sin")
    # @classmethod
    # def validate_sin_field(cls, v):
    #     if v and not validate_sin(v):
    #         raise ValueError("Invalid SIN (failed Luhn check)")
    #     return v

class T4SlipData(BaseModel):
    year: str = Field("", description="Tax year of the slip")
    province_employment: str = Field("", description="Box 10 - Province of employment")
    employer_name: str = Field("", description="Employer's name")
    employee_last_name: str = Field("", description="Employee's last name")
    employee_first_name: str = Field("", description="Employee's first name")
    gross_income: float = Field(0.0, description="Box 14 - Employment income")
    cpp: float = Field(0.0, description="Box 16 - CPP contributions")
    ei: float = Field(0.0, description="Box 18 - EI premiums")
    rrsp: float = Field(0.0, description="Box 20 - RPP contributions")
    tax_deducted: float = Field(0.0, description="Box 22 - Income tax deducted")
    ei_insurable: float = Field(0.0, description="Box 24 - EI insurable earnings")
    cpp_pensionable: float = Field(0.0, description="Box 26 - CPP pensionable earnings")


class T5SlipData(BaseModel):
    year: str = Field("", description="Tax year of the slip")
    interest_income: float = Field(0.0, description="Box 13 - Interest from Canadian sources")
    capital_gains_dividends: float = Field(0.0, description="Box 18 - Capital gains dividends")
    actual_dividends: float = Field(0.0, description="Box 24 - Actual amount of eligible dividends")
    taxable_dividends: float = Field(0.0, description="Box 25 - Taxable amount of eligible dividends")
    dividend_tax_credit: float = Field(0.0, description="Box 26 - Dividend tax credit for eligible dividends")
    actual_amount_other_dividends: float = Field(0.0, description="Box 10 - Actual amount of dividends other than eligible dividends")
    taxable_amount_other_dividends: float = Field(0.0, description="Box 11 - Taxable amount of dividends other than eligible dividends")
    dividend_tax_credit_other_dividends: float = Field(0.0, description="Box 12 - Dividend tax credit for dividends other than eligible dividends")
    report_code: str = Field("", description="Box 21 - Report Code")
    recipient_sin: str = Field("", description="Box 22 - Recipient identification number")
    recipient_type: str = Field("", description="Box 23 - Recipient type (individual, corporation, trust)")
    foreign_currency: str = Field("", description="Box 27 - Foreign currency")
    transit: str = Field("", description="Box 28 - Transit number")
    recipient_account_number: str = Field("", description="Box 29 - Recipient's account number")
    payer_name: str = Field("", description="Payer/issuer name")
    recipient_name: str = Field("", description="Recipient name")


class TaxSlipData(BaseModel):
    """Unified output — only relevant fields populated based on document_type."""
    document_type: str = Field("", description="T4, T5, or Other")
    sin: str = Field("", description="Social Insurance Number")
    t4: list[T4SlipData] = Field(default_factory=list, description="T4 specific fields")
    t5: list[T5SlipData] = Field(default_factory=list, description="T5 specific fields")
    other_info: str = Field("", description="Any other important information")


@dataclass
class TaxResult:
    sin: str = ""
    # Income
    total_income:           float = 0.0   # line 15000
    net_income:             float = 0.0   # line 23600
    taxable_income:         float = 0.0   # line 26000

    # Gross-up for dividends
    grossed_up_dividends:   float = 0.0

    # Tax before credits
    federal_tax_before_credits: float = 0.0
    provincial_tax:             float = 0.0
    combined_tax:               float = 0.0

    # Non-refundable credits
    federal_basic_personal_credit:  float = 0.0
    federal_cpp_credit:             float = 0.0
    federal_ei_credit:              float = 0.0
    federal_medical_credit:         float = 0.0
    federal_donation_credit:        float = 0.0
    federal_tuition_credit:         float = 0.0
    federal_dividend_credit:        float = 0.0
    total_federal_credits:          float = 0.0

    provincial_basic_personal_credit: float = 0.0
    total_provincial_credits:         float = 0.0

    net_federal_tax:        float = 0.0   # line 42000
    net_provincial_tax:     float = 0.0
    total_payable:          float = 0.0   # line 43500

    # Payments
    total_credits_and_payments: float = 0.0

    # Final
    balance_owing:          float = 0.0   # positive = you owe, negative = refund
    notes: list            = field(default_factory=list)


@dataclass
class TaxInput:
    province: str = "ON"

    # Income sources
    employment_income:      float = 0.0   # T4 Box 14
    eligible_dividends:     float = 0.0   # T3/T5 eligible dividends (actual amount)
    other_investment_income: float = 0.0  # interest, foreign income, etc.
    capital_gains:          float = 0.0   # total capital gains (gross)
    capital_losses:         float = 0.0   # total capital losses (gross)
    self_employment_income: float = 0.0   # T2125 net business income

    # Deductions
    rrsp_deduction:         float = 0.0
    union_dues:             float = 0.0   # T4 Box 44
    childcare_expenses:     float = 0.0
    moving_expenses:        float = 0.0
    other_deductions:       float = 0.0   # line 23200

    # Credits (amounts paid / qualifying expenses)
    medical_expenses:       float = 0.0
    charitable_donations:   float = 0.0
    tuition_paid:           float = 0.0   # T2202

    # Withholdings / prepayments
    tax_withheld:           float = 0.0   # T4 Box 22
    cpp_contributions:      float = 0.0   # T4 Box 16 (employee share)
    ei_premiums:            float = 0.0   # T4 Box 18


def validate_sin(sin: str) -> bool:
        sin = sin.replace(" ", "")
        if not re.fullmatch(r"\d{9}", sin):
            return False
        if sin[0] == "0":
            return False
        digits = [int(d) for d in sin]
        total = 0
        for i, d in enumerate(digits):
            if i % 2 == 1:  
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0