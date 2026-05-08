# ------------------------------------------------------------------ #
#  Usage in advisor_node
# ------------------------------------------------------------------ #
from canada_tax_ai.core.agent_state import AgentState
from canada_tax_ai.core.llm import get_llm
from canada_tax_ai.prompt.tax_advisor import build_advisor_prompt, get_next_opportunity
from langchain_core.messages import SystemMessage


def advisor_node(state: AgentState) -> dict:

    llm = get_llm()
    profile = state.get("profile", {})

    province       = profile.get("province", "ON")
    marital_status = profile.get("marital_status", "")
    filing_year    = profile.get("filing_year", 2025)
    is_senior      = profile.get("age", 0) >= 65
    is_under_25    = profile.get("age", 30) < 25

    already_claimed = state.get("already_claimed", [])
    already_denied  = state.get("already_denied", [])

    next_opp = get_next_opportunity(
        already_claimed=already_claimed,
        already_denied=already_denied,
        province=province,
        filing_year=filing_year,
        has_t4=bool(state.get("t4_slips")),
        has_t5=bool(state.get("t5_slips")),
        marital_status=marital_status,
        is_senior=is_senior,
        has_dependants=bool(profile.get("dependants")),
        is_investor=bool(state.get("t5_slips")),
        is_farmer=profile.get("is_farmer", False),
        is_self_employed=profile.get("is_self_employed", False),
        is_under_25=is_under_25,
    )

    system = build_advisor_prompt(
        province=province,
        filing_year=filing_year,
        marital_status=marital_status,
        has_dependants=bool(profile.get("dependants")),
        confirmed_slips=state.get("confirmed_slips", []),
        already_claimed=already_claimed,
        marginal_rate=state.get("marginal_rate", 33),
        net_income=state.get("net_income", 50_000),
        cpp=state.get("cpp", 0),
        ei=state.get("ei", 0),
        is_senior=is_senior,
        is_investor=bool(state.get("t5_slips")),
        is_farmer=profile.get("is_farmer", False),
        is_self_employed=profile.get("is_self_employed", False),
        is_under_25=is_under_25,
    )

    if next_opp:
        system += f"\n\n## Now Ask About\n{next_opp['prompt']}"
        system += f"\nValue to user: {next_opp['value_hint']}"
        system += f"\nRequired slip: {next_opp['slip']}"
    else:
        system += "\n\n## Status\nAll opportunities have been reviewed. Summarize what was claimed and generate the final tax estimate."

    response = llm.invoke([SystemMessage(content=system)] + state["messages"])
    return {"messages": [response]}