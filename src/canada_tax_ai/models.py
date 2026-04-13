# models.py
import re

from pydantic import BaseModel, Field, field_validator
from pydantic import BaseModel, Field
from typing import List, Dict

class UserProfile(BaseModel):
    last_name: str = Field("", pattern=r"^[A-Za-z\-']+$", description="User's last name")
    first_name: str = Field("", pattern=r"^[A-Za-z\-']+$", description="User's first name")
    phone_number: str = Field("",pattern=r"^\+?1?\d{10,15}$",description="User's phone number")
    date_of_birth: str = Field("",pattern=r"^\d{4}-\d{2}-\d{2}$",description="Date of birth in YYYY-MM-DD format")
    address: str = Field("", min_length=5, description="Current residential address")
    marital_status: str = Field("",pattern=r"^(single|married|common-law|separated|divorced|widowed)$",description="Marital status")
    dependents: List[Dict] = Field(default_factory=list,description="List of dependents with name, DOB, and relationship")
    sin: str = Field("", pattern=r"^\d{3} \d{3} \d{3}$", description="Social Insurance Number (SIN) in format XXX XXX XXX")
    
    # sin: str = ""
    # @field_validator("sin")
    # @classmethod
    # def validate_sin_field(cls, v):
    #     if v and not validate_sin(v):
    #         raise ValueError("Invalid SIN (failed Luhn check)")
    #     return v

class T4SlipData(BaseModel):
    gross_income: float = Field(0.0, description="Box 14 - Employment income")
    cpp: float = Field(0.0, description="Box 16 - CPP contributions")
    ei: float = Field(0.0, description="Box 18 - EI premiums")
    rrsp: float = Field(0.0, description="Box 20 - RPP contributions")
    tax_deducted: float = Field(0.0, description="Box 22 - Income tax deducted")
    ei_insurable: float = Field(0.0, description="Box 24 - EI insurable earnings")
    cpp_pensionable: float = Field(0.0, description="Box 26 - CPP pensionable earnings")


class T5SlipData(BaseModel):
    interest_income: float = Field(0.0, description="Box 13 - Interest from Canadian sources")
    investment_income: float = Field(0.0, description="Box 11 - Other investment income")
    foreign_income: float = Field(0.0, description="Box 15 - Foreign income")
    foreign_tax_paid: float = Field(0.0, description="Box 16 - Foreign tax paid")
    capital_gains_dividends: float = Field(0.0, description="Box 18 - Capital gains dividends")
    actual_dividends: float = Field(0.0, description="Box 24 - Actual eligible dividends")
    taxable_dividends: float = Field(0.0, description="Box 25 - Taxable eligible dividends")
    dividend_tax_credit: float = Field(0.0, description="Box 26 - Dividend tax credit")
    tax_deducted: float = Field(0.0, description="Box 22 - Income tax deducted")
    payer_name: str = Field("", description="Payer/issuer name")
    recipient_name: str = Field("", description="Recipient name")


class TaxSlipData(BaseModel):
    """Unified output — only relevant fields populated based on document_type."""
    document_type: str = Field("", description="T4, T5, or Other")
    sin: str = Field("", description="Social Insurance Number")
    t4: T4SlipData = Field(default_factory=T4SlipData, description="T4 specific fields")
    t5: T5SlipData = Field(default_factory=T5SlipData, description="T5 specific fields")
    other_info: str = Field("", description="Any other important information")


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