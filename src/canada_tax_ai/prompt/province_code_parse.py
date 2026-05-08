from difflib import get_close_matches
from dataclasses import dataclass, field

@dataclass
class ProvincialCredit:
    """A single provincial/territorial tax credit or benefit."""
    id: str
    title: str
    description: str
    value_hint: str
    slip: str
    trigger: str = "always"
    question: str = ""


@dataclass
class ProvinceConfig:
    """Full tax credit configuration for a province/territory."""
    code: str
    name: str
    basic_personal_amount: float
    tax_brackets: list[tuple[float, float]]   # (rate, threshold)
    credits: list[ProvincialCredit] = field(default_factory=list)



# ================================================================== #
#  All Provinces & Territories
# ================================================================== #

PROVINCES: dict[str, ProvinceConfig] = {

    # ── Alberta ───────────────────────────────────────────────────
    "AB": ProvinceConfig(
        code="AB", name="Alberta",
        basic_personal_amount=21_003.0,
        tax_brackets=[(0.10, 0), (0.12, 148_269), (0.13, 177_922),
                      (0.14, 237_230), (0.15, 355_845)],
        credits=[
            ProvincialCredit(
                id="ab_basic_personal",
                title="Alberta Basic Personal Amount",
                description="Alberta's basic personal amount is one of the highest in Canada at $21,003.",
                value_hint="~$2,100 credit (10% of BPA)",
                slip="Automatic",
                trigger="always",
                question="Applied automatically. ✅"
            ),
            ProvincialCredit(
                id="ab_spouse",
                title="Alberta Spousal Amount",
                description="Claim if your spouse/partner earned less than $21,003.",
                value_hint="Up to $2,100 credit",
                slip="None",
                trigger="married",
                question="Did your spouse or common-law partner earn less than $21,003 in {filing_year}?"
            ),
            ProvincialCredit(
                id="ab_disability",
                title="Alberta Disability Amount",
                description="Provincial disability credit for eligible individuals with T2201.",
                value_hint="~$1,400 provincial credit",
                slip="T2201",
                trigger="always",
                question="Do you or a dependant have an approved T2201 Disability Tax Certificate on file with CRA?"
            ),
            ProvincialCredit(
                id="ab_medical",
                title="Alberta Medical Expenses",
                description="Alberta allows the same medical expense deduction as federal.",
                value_hint="10% credit on eligible amounts",
                slip="Receipts",
                trigger="always",
                question="Did you pay out-of-pocket medical expenses in {filing_year}? (Dental, prescriptions, glasses, physio, etc.)"
            ),
            ProvincialCredit(
                id="ab_political",
                title="Alberta Political Contributions Credit",
                description="Credit for contributions to Alberta political parties.",
                value_hint="75% on first $200, then graduated",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to any Alberta provincial political party in {filing_year}?"
            ),
        ]
    ),

    # ── British Columbia ───────────────────────────────────────────
    "BC": ProvinceConfig(
        code="BC", name="British Columbia",
        basic_personal_amount=11_981.0,
        tax_brackets=[(0.0506, 0), (0.077, 45_654), (0.105, 91_310),
                      (0.1229, 104_835), (0.147, 127_299),
                      (0.168, 172_602), (0.205, 240_716)],
        credits=[
            ProvincialCredit(
                id="bc_climate_action",
                title="BC Climate Action Tax Credit",
                description="Quarterly payments to offset carbon taxes — income-tested.",
                value_hint="Up to $504/year for individuals",
                slip="Automatic via CRA",
                trigger="always",
                question="Are you registered with CRA for the BC Climate Action Tax Credit? It's paid automatically if you file."
            ),
            ProvincialCredit(
                id="bc_renter",
                title="BC Renter's Tax Credit",
                description="Refundable credit for BC residents who rent their home.",
                value_hint="Up to $400/year",
                slip="Rental receipts",
                trigger="always",
                question="Did you rent your home in BC in {filing_year}? You may qualify for up to $400 refundable credit."
            ),
            ProvincialCredit(
                id="bc_seniors_home_renovation",
                title="BC Seniors' Home Renovation Tax Credit",
                description="For seniors 65+ who renovated their home for accessibility.",
                value_hint="10% of up to $10,000 = $1,000 credit",
                slip="Receipts",
                trigger="senior",
                question="Are you 65 or older and did you pay for home renovations to improve accessibility or safety in {filing_year}?"
            ),
            ProvincialCredit(
                id="bc_political",
                title="BC Political Contributions Credit",
                description="Credit for contributions to registered BC political parties.",
                value_hint="75% on first $100, then graduated",
                slip="Official receipt",
                trigger="always",
                question="Did you make any contributions to a registered BC provincial political party in {filing_year}?"
            ),
            ProvincialCredit(
                id="bc_mining_exploration",
                title="BC Mining Exploration Tax Credit",
                description="For investors in BC mining flow-through shares.",
                value_hint="20% of eligible expenses",
                slip="T101",
                trigger="investor",
                question="Did you invest in BC mining flow-through shares in {filing_year}?"
            ),
            ProvincialCredit(
                id="bc_training",
                title="BC Training Tax Credit",
                description="For apprentices registered in eligible Red Seal trades.",
                value_hint="Up to $2,500 refundable credit",
                slip="Employer certification",
                trigger="always",
                question="Are you a registered apprentice in a Red Seal trade program in BC?"
            ),
        ]
    ),

    # ── Manitoba ──────────────────────────────────────────────────
    "MB": ProvinceConfig(
        code="MB", name="Manitoba",
        basic_personal_amount=15_780.0,
        tax_brackets=[(0.108, 0), (0.1275, 36_842), (0.174, 79_625)],
        credits=[
            ProvincialCredit(
                id="mb_personal",
                title="Manitoba Personal Tax Credit",
                description="Manitoba's basic personal tax credit applied to all residents.",
                value_hint="~$1,704 credit",
                slip="Automatic",
                trigger="always",
                question="Applied automatically. ✅"
            ),
            ProvincialCredit(
                id="mb_homeowner_renter",
                title="Manitoba Homeowners/Renters Affordability Tax Credit",
                description="Refundable credit for Manitoba residents who own or rent their home.",
                value_hint="Up to $1,725",
                slip="Property tax statement or rental receipts",
                trigger="always",
                question="Did you own or rent your home in Manitoba in {filing_year}? You may qualify for up to $1,725 refundable credit."
            ),
            ProvincialCredit(
                id="mb_seniors_school_rebate",
                title="Manitoba Seniors School Tax Rebate",
                description="Rebate on school taxes for Manitoba homeowners 65+.",
                value_hint="Up to $470 rebate",
                slip="Property tax statement",
                trigger="senior",
                question="Are you 65 or older and did you own your home in Manitoba in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_primary_caregiver",
                title="Manitoba Primary Caregiver Tax Credit",
                description="For Manitobans who provide care for a family member, neighbour, or friend.",
                value_hint="Up to $1,400 refundable credit",
                slip="Caregiver certification",
                trigger="always",
                question="Were you the primary unpaid caregiver for someone with a severe disability or chronic illness in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_green_energy",
                title="Manitoba Green Energy Equipment Tax Credit",
                description="For installation or manufacture of geothermal heat pumps.",
                value_hint="10% of eligible costs",
                slip="Receipts",
                trigger="always",
                question="Did you install a geothermal heat pump or qualifying green energy equipment in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_community_enterprise",
                title="Manitoba Community Enterprise Development Tax Credit",
                description="For investments in eligible community enterprise development projects.",
                value_hint="45% of investment",
                slip="T1256",
                trigger="investor",
                question="Did you invest in any Manitoba community enterprise development projects in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_small_business_venture",
                title="Manitoba Small Business Venture Capital Tax Credit",
                description="Credit for investments in eligible MB small businesses.",
                value_hint="45% of eligible investment",
                slip="T1256-1",
                trigger="investor",
                question="Did you invest in any Manitoba small business venture capital projects in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_employee_share",
                title="Manitoba Employee Share Purchase Tax Credit",
                description="For employees who purchased shares through an ESOP plan.",
                value_hint="15% of share purchase",
                slip="T1256-2",
                trigger="has_t4",
                question="Did you participate in an employee share ownership plan (ESOP) through your Manitoba employer in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_fitness",
                title="Manitoba Fitness Amount for Young Adults",
                description="For residents under 25 with eligible fitness expenses.",
                value_hint="Up to $54 credit",
                slip="Receipts",
                trigger="under_25",
                question="Are you under 25 and did you pay for eligible fitness activities (gym, sports leagues, etc.) in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_mineral_exploration",
                title="Manitoba Mineral Exploration Tax Credit",
                description="For investors in Manitoba flow-through shares.",
                value_hint="30% of eligible expenses",
                slip="T101",
                trigger="investor",
                question="Did you invest in Manitoba mining flow-through shares in {filing_year}?"
            ),
            ProvincialCredit(
                id="mb_odour_control",
                title="Manitoba Odour-Control Tax Credit",
                description="For Manitoba farmers who incurred eligible odour-control expenses.",
                value_hint="Up to $22,500 credit",
                slip="Receipts",
                trigger="farmer",
                question="Are you a Manitoba farmer who paid for eligible odour-control equipment or structures in {filing_year}?"
            ),
        ]
    ),

    # ── Ontario ───────────────────────────────────────────────────
    "ON": ProvinceConfig(
        code="ON", name="Ontario",
        basic_personal_amount=11_865.0,
        tax_brackets=[(0.0505, 0), (0.0915, 51_446), (0.1116, 102_894),
                      (0.1216, 150_000), (0.1316, 220_000)],
        credits=[
            ProvincialCredit(
                id="on_trillium",
                title="Ontario Trillium Benefit (OTB)",
                description="Combines 3 credits: Ontario Energy & Property Tax, Northern Ontario Energy, Ontario Sales Tax. Monthly payments.",
                value_hint="Up to $1,421/year",
                slip="Property tax or rent receipts",
                trigger="always",
                question="Did you pay rent or property tax in Ontario in {filing_year}? The Ontario Trillium Benefit could give you up to $1,421 — paid monthly."
            ),
            ProvincialCredit(
                id="on_seniors_care",
                title="Ontario Seniors' Home Safety Tax Credit",
                description="For seniors 65+ who made their home safer or more accessible.",
                value_hint="25% of up to $10,000 = $2,500 credit",
                slip="Receipts",
                trigger="senior",
                question="Are you 65+ and did you renovate your Ontario home for safety or accessibility in {filing_year}?"
            ),
            ProvincialCredit(
                id="on_staycation",
                title="Ontario Staycation Tax Credit",
                description="For leisure travel within Ontario — hotels, motels, campgrounds.",
                value_hint="20% of up to $1,000 = $200 credit",
                slip="Receipts",
                trigger="always",
                question="Did you take a leisure trip within Ontario and stay at an eligible accommodation in {filing_year}?"
            ),
            ProvincialCredit(
                id="on_childcare",
                title="Ontario Child Care Access and Relief from Expenses (CARE)",
                description="Refundable credit for child care expenses — income-tested.",
                value_hint="Up to 75% of eligible child care expenses",
                slip="T778 + receipts",
                trigger="has_dependants",
                question="Did you pay for child care in Ontario in {filing_year}? The CARE credit can refund up to 75% of eligible expenses."
            ),
            ProvincialCredit(
                id="on_political",
                title="Ontario Political Contributions Credit",
                description="For contributions to registered Ontario political parties.",
                value_hint="75% on first $368, then graduated",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to a registered Ontario provincial political party in {filing_year}?"
            ),
            ProvincialCredit(
                id="on_training",
                title="Ontario Jobs Training Tax Credit",
                description="Refundable credit for eligible tuition and training fees.",
                value_hint="50% of eligible expenses up to $4,000 = $2,000",
                slip="T2202 or receipts",
                trigger="always",
                question="Did you pay for eligible job training or courses in Ontario in {filing_year}?"
            ),
        ]
    ),

    # ── Quebec ────────────────────────────────────────────────────
    "QC": ProvinceConfig(
        code="QC", name="Quebec",
        basic_personal_amount=17_183.0,
        tax_brackets=[(0.14, 0), (0.19, 51_780), (0.24, 103_545), (0.2575, 126_000)],
        credits=[
            ProvincialCredit(
                id="qc_solidarity",
                title="Quebec Solidarity Tax Credit",
                description="Refundable credit combining housing, QST, and northern villages components.",
                value_hint="Up to $2,000+/year",
                slip="Lease or property tax",
                trigger="always",
                question="Did you live in Quebec on December 31 {filing_year}? The Solidarity Tax Credit is a major refundable benefit — are you registered?"
            ),
            ProvincialCredit(
                id="qc_childcare",
                title="Quebec Subsidized Childcare / Childcare Expense Credit",
                description="Quebec's subsidized daycare system + refundable credit for unsubsidized care.",
                value_hint="Up to 78% of eligible expenses",
                slip="RL-24 + receipts",
                trigger="has_dependants",
                question="Did you pay for child care in Quebec in {filing_year}? Quebec's childcare credit can cover up to 78% of eligible expenses."
            ),
            ProvincialCredit(
                id="qc_home_support",
                title="Quebec Tax Credit for Home-Support Services for Seniors",
                description="Refundable credit for seniors 70+ who pay for home support services.",
                value_hint="36% of eligible expenses",
                slip="Receipts from home support provider",
                trigger="senior",
                question="Are you 70+ and did you pay for home support services (cleaning, meals, nursing, etc.) in {filing_year}?"
            ),
            ProvincialCredit(
                id="qc_rrsp",
                title="Quebec RRSP Deduction",
                description="Quebec also allows RRSP deduction at provincial rates.",
                value_hint="14-25.75% provincial savings",
                slip="RRSP receipts",
                trigger="always",
                question="Your RRSP contributions save you both federal AND Quebec provincial tax. Have you maximized your contributions?"
            ),
            ProvincialCredit(
                id="qc_medical",
                title="Quebec Medical Expense Credit",
                description="Quebec's medical expense credit has a lower threshold than federal.",
                value_hint="25.75% on eligible amounts over 3% of income",
                slip="Receipts",
                trigger="always",
                question="Did you pay out-of-pocket medical expenses in {filing_year}? Quebec's medical credit may give more than the federal one."
            ),
            ProvincialCredit(
                id="qc_rpap",
                title="Quebec Parental Insurance Plan (QPIP) Premium Credit",
                description="Credit for QPIP premiums paid — appears on RL-1 slip.",
                value_hint="Automatic from RL-1",
                slip="RL-1",
                trigger="has_t4",
                question="Applied automatically from your RL-1. ✅"
            ),
        ]
    ),

    # ── Saskatchewan ──────────────────────────────────────────────
    "SK": ProvinceConfig(
        code="SK", name="Saskatchewan",
        basic_personal_amount=17_661.0,
        tax_brackets=[(0.105, 0), (0.125, 49_720), (0.145, 142_058)],
        credits=[
            ProvincialCredit(
                id="sk_graduate_retention",
                title="Saskatchewan Graduate Retention Program",
                description="Refundable credit for SK graduates who live and work in Saskatchewan.",
                value_hint="Up to $20,000 over 7 years",
                slip="Proof of graduation",
                trigger="always",
                question="Did you graduate from a post-secondary program and currently live and work in Saskatchewan? You may qualify for up to $20,000 over 7 years."
            ),
            ProvincialCredit(
                id="sk_active_families",
                title="Saskatchewan Active Families Benefit",
                description="Refundable credit for children's arts, culture, and recreation activities.",
                value_hint="Up to $150 per child",
                slip="Receipts",
                trigger="has_dependants",
                question="Did you pay for sports, arts, or recreation activities for your children in Saskatchewan in {filing_year}?"
            ),
            ProvincialCredit(
                id="sk_home_renovation",
                title="Saskatchewan Home Renovation Tax Credit",
                description="For eligible home renovation expenses in Saskatchewan.",
                value_hint="10.5% of up to $20,000",
                slip="Receipts",
                trigger="always",
                question="Did you pay for home renovations in Saskatchewan in {filing_year}?"
            ),
            ProvincialCredit(
                id="sk_political",
                title="Saskatchewan Political Contributions Credit",
                description="Credit for contributions to registered SK political parties.",
                value_hint="75% on first $400",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to a registered Saskatchewan provincial political party in {filing_year}?"
            ),
        ]
    ),

    # ── Nova Scotia ───────────────────────────────────────────────
    "NS": ProvinceConfig(
        code="NS", name="Nova Scotia",
        basic_personal_amount=8_481.0,
        tax_brackets=[(0.0879, 0), (0.1495, 29_590), (0.1667, 59_180),
                      (0.175, 93_000), (0.21, 150_000)],
        credits=[
            ProvincialCredit(
                id="ns_affordable_living",
                title="Nova Scotia Affordable Living Tax Credit",
                description="Quarterly refundable credit for lower-income NS residents.",
                value_hint="Up to $255/year",
                slip="Automatic via CRA",
                trigger="always",
                question="Are you a lower-income Nova Scotia resident? The Affordable Living Tax Credit is paid quarterly — are you registered?"
            ),
            ProvincialCredit(
                id="ns_poverty_reduction",
                title="Nova Scotia Poverty Reduction Credit",
                description="For NS residents with income below $30,000.",
                value_hint="Up to $625/year",
                slip="Automatic",
                trigger="always",
                question="Applied automatically if your income qualifies. ✅"
            ),
            ProvincialCredit(
                id="ns_innovation_equity",
                title="Nova Scotia Innovation Equity Tax Credit",
                description="For investments in NS innovation companies.",
                value_hint="35% of eligible investment",
                slip="NS investment certificate",
                trigger="investor",
                question="Did you invest in any Nova Scotia innovation equity companies in {filing_year}?"
            ),
            ProvincialCredit(
                id="ns_venture_capital",
                title="Nova Scotia Venture Capital Tax Credit",
                description="For investments in NS venture capital eligible companies.",
                value_hint="35% of eligible investment",
                slip="NS investment certificate",
                trigger="investor",
                question="Did you receive a Nova Scotia venture capital investment certificate in {filing_year}?"
            ),
            ProvincialCredit(
                id="ns_seniors_care",
                title="Nova Scotia Age Amount",
                description="Additional credit for NS residents 65 and older.",
                value_hint="~$400 provincial credit",
                slip="Automatic",
                trigger="senior",
                question="Applied automatically if you are 65+. ✅"
            ),
        ]
    ),

    # ── New Brunswick ─────────────────────────────────────────────
    "NB": ProvinceConfig(
        code="NB", name="New Brunswick",
        basic_personal_amount=12_458.0,
        tax_brackets=[(0.094, 0), (0.14, 47_715), (0.16, 95_431),
                      (0.195, 176_756), (0.203, 176_757)],
        credits=[
            ProvincialCredit(
                id="nb_seniors_home_renovation",
                title="New Brunswick Seniors' Home Renovation Credit",
                description="For NB homeowners 65+ who renovated for accessibility.",
                value_hint="10% of up to $10,000 = $1,000",
                slip="Receipts",
                trigger="senior",
                question="Are you 65+ and did you renovate your NB home for accessibility or safety in {filing_year}?"
            ),
            ProvincialCredit(
                id="nb_political",
                title="New Brunswick Political Contributions Credit",
                description="For donations to registered NB political parties.",
                value_hint="75% on first $200",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to a registered New Brunswick provincial political party in {filing_year}?"
            ),
            ProvincialCredit(
                id="nb_low_income",
                title="New Brunswick Low-Income Tax Reduction",
                description="Reduces NB tax to zero for lower-income residents.",
                value_hint="Full provincial tax reduction",
                slip="Automatic",
                trigger="always",
                question="Applied automatically based on your income. ✅"
            ),
        ]
    ),

    # ── Prince Edward Island ──────────────────────────────────────
    "PE": ProvinceConfig(
        code="PE", name="Prince Edward Island",
        basic_personal_amount=12_000.0,
        tax_brackets=[(0.096, 0), (0.1368, 32_656), (0.167, 64_313),
                      (0.18, 105_000), (0.187, 140_000)],
        credits=[
            ProvincialCredit(
                id="pe_political",
                title="PEI Political Contributions Credit",
                description="For donations to registered PEI political parties.",
                value_hint="Up to $500 credit",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to a registered PEI political party in {filing_year}?"
            ),
            ProvincialCredit(
                id="pe_volunteer_firefighter",
                title="PEI Volunteer Firefighter/Search and Rescue Amount",
                description="For PEI volunteer firefighters and search and rescue volunteers.",
                value_hint="~$450 provincial credit",
                slip="Certification from organization",
                trigger="always",
                question="Were you a volunteer firefighter or search and rescue volunteer in PEI in {filing_year}?"
            ),
        ]
    ),

    # ── Newfoundland and Labrador ─────────────────────────────────
    "NL": ProvinceConfig(
        code="NL", name="Newfoundland and Labrador",
        basic_personal_amount=10_900.0,
        tax_brackets=[(0.087, 0), (0.145, 43_198), (0.158, 86_395),
                      (0.178, 154_244), (0.198, 215_943),
                      (0.208, 275_870), (0.213, 551_739)],
        credits=[
            ProvincialCredit(
                id="nl_seniors_benefit",
                title="Newfoundland and Labrador Seniors' Benefit",
                description="Refundable credit for NL seniors with lower income.",
                value_hint="Up to $1,516/year",
                slip="Automatic",
                trigger="senior",
                question="Are you 65+ with income below ~$40,000? The NL Seniors' Benefit is refundable — are you registered?"
            ),
            ProvincialCredit(
                id="nl_child_benefit",
                title="NL Child Benefit / Mother Baby Nutrition Supplement",
                description="Supplement for lower-income NL families with young children.",
                value_hint="Up to $1,000+/year",
                slip="Automatic via CRA",
                trigger="has_dependants",
                question="Do you have children under 18 in Newfoundland? The NL Child Benefit is paid automatically with CCB."
            ),
            ProvincialCredit(
                id="nl_political",
                title="NL Political Contributions Credit",
                description="For donations to registered NL political parties.",
                value_hint="Up to $500 credit",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to a registered NL provincial political party in {filing_year}?"
            ),
        ]
    ),

    # ── Northwest Territories ─────────────────────────────────────
    "NT": ProvinceConfig(
        code="NT", name="Northwest Territories",
        basic_personal_amount=16_593.0,
        tax_brackets=[(0.059, 0), (0.086, 50_597), (0.122, 101_198), (0.1405, 164_525)],
        credits=[
            ProvincialCredit(
                id="nt_cost_of_living",
                title="NWT Cost of Living Tax Credit",
                description="Refundable credit to offset high northern living costs.",
                value_hint="Up to $1,200/year",
                slip="Automatic",
                trigger="always",
                question="Applied automatically for NWT residents. ✅"
            ),
            ProvincialCredit(
                id="nt_northern_residents",
                title="Northern Residents Deduction",
                description="Federal deduction for living in a prescribed northern zone.",
                value_hint="Up to $24/day basic residency + travel",
                slip="Receipts for travel",
                trigger="always",
                question="You qualify for the Northern Residents Deduction since you live in the NWT. Did you take any personal travel trips in {filing_year}?"
            ),
        ]
    ),

    # ── Nunavut ───────────────────────────────────────────────────
    "NU": ProvinceConfig(
        code="NU", name="Nunavut",
        basic_personal_amount=17_925.0,
        tax_brackets=[(0.04, 0), (0.07, 53_268), (0.09, 106_537), (0.115, 173_205)],
        credits=[
            ProvincialCredit(
                id="nu_cost_of_living",
                title="Nunavut Cost of Living Tax Credit",
                description="Refundable credit for Nunavut residents to offset remote living costs.",
                value_hint="Up to $1,200/year",
                slip="Automatic",
                trigger="always",
                question="Applied automatically for Nunavut residents. ✅"
            ),
            ProvincialCredit(
                id="nu_northern_residents",
                title="Northern Residents Deduction",
                description="Federal deduction — Nunavut is a prescribed northern zone.",
                value_hint="Up to $24/day + travel benefits",
                slip="Travel receipts",
                trigger="always",
                question="As a Nunavut resident you qualify for the Northern Residents Deduction. Did you travel for personal reasons in {filing_year}?"
            ),
        ]
    ),

    # ── Yukon ─────────────────────────────────────────────────────
    "YT": ProvinceConfig(
        code="YT", name="Yukon",
        basic_personal_amount=15_705.0,
        tax_brackets=[(0.064, 0), (0.09, 57_375), (0.109, 114_750),
                      (0.128, 177_882), (0.15, 500_000)],
        credits=[
            ProvincialCredit(
                id="yt_children_fitness",
                title="Yukon Children's Arts and Fitness Amount",
                description="Credit for children's arts and fitness program fees.",
                value_hint="Up to $1,000 × 6.4% = $64 per child",
                slip="Receipts",
                trigger="has_dependants",
                question="Did you pay for fitness or arts programs for your children in Yukon in {filing_year}?"
            ),
            ProvincialCredit(
                id="yt_political",
                title="Yukon Political Contributions Credit",
                description="For contributions to registered Yukon political parties.",
                value_hint="Up to $500 credit",
                slip="Official receipt",
                trigger="always",
                question="Did you donate to a registered Yukon political party in {filing_year}?"
            ),
            ProvincialCredit(
                id="yt_northern_residents",
                title="Northern Residents Deduction",
                description="Federal deduction for Yukon residents in prescribed zones.",
                value_hint="Up to $24/day + travel",
                slip="Travel receipts",
                trigger="always",
                question="As a Yukon resident you qualify for the Northern Residents Deduction. Did you take any personal travel in {filing_year}?"
            ),
            ProvincialCredit(
                id="yt_business_incentive",
                title="Yukon Business Incentive Program",
                description="Rebate on Yukon payroll tax for eligible businesses.",
                value_hint="Varies by business",
                slip="Business records",
                trigger="self_employed",
                question="Do you operate a business in Yukon and pay payroll tax?"
            ),
        ]
    ),
}



# ------------------------------------------------------------------ #
#  Build lookup maps at module load time
# ------------------------------------------------------------------ #

# Full name → code mapping (lowercase keys for case-insensitive lookup)
_NAME_TO_CODE: dict[str, str] = {
    config.name.lower(): code
    for code, config in PROVINCES.items()
}

# Common aliases and abbreviations → code
_ALIASES: dict[str, str] = {
    # English full names
    "alberta":                          "AB",
    "british columbia":                 "BC",
    "manitoba":                         "MB",
    "ontario":                          "ON",
    "quebec":                           "QC",
    "québec":                           "QC",
    "saskatchewan":                     "SK",
    "nova scotia":                      "NS",
    "new brunswick":                    "NB",
    "prince edward island":             "PE",
    "newfoundland and labrador":        "NL",
    "newfoundland":                     "NL",
    "labrador":                         "NL",
    "northwest territories":            "NT",
    "northwest territory":              "NT",
    "nunavut":                          "NU",
    "yukon":                            "YT",
    "yukon territory":                  "YT",

    # French full names
    "colombie-britannique":             "BC",
    "île-du-prince-édouard":           "PE",
    "ile-du-prince-edouard":           "PE",
    "nouveau-brunswick":               "NB",
    "nouvelle-écosse":                 "NS",
    "nouvelle-ecosse":                 "NS",
    "terre-neuve-et-labrador":         "NL",
    "territoires du nord-ouest":       "NT",
    "territoire du yukon":             "YT",

    # Common abbreviations and nicknames
    "bc":  "BC",
    "ab":  "AB",
    "mb":  "MB",
    "on":  "ON",
    "qc":  "QC",
    "sk":  "SK",
    "ns":  "NS",
    "nb":  "NB",
    "pe":  "PE",
    "pei": "PE",
    "nl":  "NL",
    "nt":  "NT",
    "nwt": "NT",
    "nu":  "NU",
    "yt":  "YT",

    # Casual / spoken
    "nfld":         "NL",
    "nfld.":        "NL",
    "p.e.i.":       "PE",
    "pei.":         "PE",
    "n.s.":         "NS",
    "n.b.":         "NB",
    "b.c.":         "BC",
    "ont":          "ON",
    "ont.":         "ON",
    "alta":         "AB",
    "alta.":        "AB",
    "sask":         "SK",
    "sask.":        "SK",
    "man":          "MB",
    "man.":         "MB",
    "que":          "QC",
    "que.":         "QC",
    "qué":          "QC",
    "qué.":         "QC",
}


def _normalize(raw: str) -> str:
    """Lowercase, strip, collapse multiple spaces."""
    return " ".join(raw.lower().strip().split())


def get_province(code: str) -> ProvinceConfig:
    """
    Get province config by code, full name, French name,
    abbreviation, or common alias — case-insensitive.

    Examples:
        get_province("MB")
        get_province("manitoba")
        get_province("British Columbia")
        get_province("colombie-britannique")
        get_province("PEI")
        get_province("SASK.")
        get_province("nwt")
    """
    if not code or not isinstance(code, str):
        raise ValueError(f"Province input must be a non-empty string, got: {code!r}")

    normalized = _normalize(code)

    # 1. Direct code match (AB, BC, ON ...)
    upper = normalized.upper()
    if upper in PROVINCES:
        return PROVINCES[upper]

    # 2. Alias / abbreviation match
    if normalized in _ALIASES:
        return PROVINCES[_ALIASES[normalized]]

    # 3. Full name match from province configs
    if normalized in _NAME_TO_CODE:
        return PROVINCES[_NAME_TO_CODE[normalized]]

    # 4. Fuzzy match — handle typos like "Manitoба", "Ontarion"
    all_keys = list(_ALIASES.keys()) + list(_NAME_TO_CODE.keys())
    close = get_close_matches(normalized, all_keys, n=1, cutoff=0.8)
    if close:
        matched = close[0]
        resolved = _ALIASES.get(matched) or _NAME_TO_CODE.get(matched)
        if resolved:
            return PROVINCES[resolved]

    # 5. Partial match — "brit" → "british columbia"
    for alias, prov_code in _ALIASES.items():
        if normalized in alias or alias.startswith(normalized):
            return PROVINCES[prov_code]

    raise ValueError(
        f"Unknown province: {code!r}\n"
        f"Valid codes: {list(PROVINCES.keys())}\n"
        f"Or use full name e.g. 'Manitoba', 'British Columbia', 'Québec'"
    )


def resolve_province_code(raw: str) -> str:
    """Return just the 2-letter code from any province input."""
    return get_province(raw).code