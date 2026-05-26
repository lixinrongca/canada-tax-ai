# tax_result_component.py
import streamlit as st
from dataclasses import dataclass


def render_tax_result2(tax_result):
    """
    Render a professional Canadian tax return summary in Streamlit.
    Pass a TaxResult dataclass or dict.
    """

    # Support both dataclass and dict
    r = tax_result if isinstance(tax_result, dict) else vars(tax_result)

    def fmt(v): return f"${v:,.2f}"
    def pct(v, base): return f"{(v/base*100):.1f}%" if base else "—"

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');

    .tax-root { font-family: 'DM Sans', sans-serif; }

    .tax-hero {
        background: linear-gradient(135deg, #0a1628 0%, #0d2137 50%, #0a1628 100%);
        border: 1px solid rgba(196,163,95,0.3);
        border-radius: 16px;
        padding: 36px 40px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
    }
    .tax-hero::before {
        content: '';
        position: absolute;
        top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: radial-gradient(ellipse at 30% 50%, rgba(196,163,95,0.06) 0%, transparent 60%);
        pointer-events: none;
    }
    .tax-hero-label {
        font-family: 'DM Mono', monospace;
        font-size: 11px;
        letter-spacing: 3px;
        color: #c4a35f;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .tax-hero-title {
        font-family: 'DM Serif Display', serif;
        font-size: 42px;
        color: #f0e6cc;
        margin: 0;
        line-height: 1.1;
    }
    .tax-hero-sub {
        font-size: 14px;
        color: rgba(240,230,204,0.5);
        margin-top: 6px;
        font-family: 'DM Mono', monospace;
    }
    .tax-badge {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 20px;
        font-size: 12px;
        font-family: 'DM Mono', monospace;
        font-weight: 500;
        letter-spacing: 1px;
        margin-top: 16px;
    }
    .badge-refund { background: rgba(52,199,89,0.15); color: #34c759; border: 1px solid rgba(52,199,89,0.3); }
    .badge-owing  { background: rgba(255,69,58,0.15);  color: #ff453a; border: 1px solid rgba(255,69,58,0.3); }
    .badge-zero   { background: rgba(196,163,95,0.15); color: #c4a35f; border: 1px solid rgba(196,163,95,0.3); }

    .tax-section {
        background: #0d1f33;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 16px;
    }
    .tax-section-title {
        font-family: 'DM Mono', monospace;
        font-size: 10px;
        letter-spacing: 3px;
        color: #c4a35f;
        text-transform: uppercase;
        margin-bottom: 18px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(196,163,95,0.2);
    }
    .tax-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
    }
    .tax-row:last-child { border-bottom: none; }
    .tax-row-label {
        font-size: 13px;
        color: rgba(255,255,255,0.55);
        font-weight: 300;
    }
    .tax-row-value {
        font-family: 'DM Mono', monospace;
        font-size: 14px;
        color: #e8dcc8;
        font-weight: 500;
    }
    .tax-row-highlight .tax-row-label { color: rgba(255,255,255,0.85); font-weight: 500; }
    .tax-row-highlight .tax-row-value { color: #c4a35f; font-size: 15px; }

    .tax-total-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 0 4px;
        margin-top: 8px;
        border-top: 1px solid rgba(196,163,95,0.3);
    }
    .tax-total-label {
        font-size: 14px;
        color: rgba(255,255,255,0.8);
        font-weight: 500;
    }
    .tax-total-value {
        font-family: 'DM Serif Display', serif;
        font-size: 22px;
        color: #c4a35f;
    }

    .tax-note {
        background: rgba(196,163,95,0.08);
        border-left: 3px solid #c4a35f;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        font-size: 13px;
        color: rgba(240,230,204,0.7);
        margin-top: 16px;
        font-family: 'DM Mono', monospace;
    }

    .tax-metric-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    .tax-metric {
        background: #0d1f33;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
        padding: 16px 18px;
        text-align: center;
    }
    .tax-metric-val {
        font-family: 'DM Serif Display', serif;
        font-size: 22px;
        color: #e8dcc8;
    }
    .tax-metric-lbl {
        font-family: 'DM Mono', monospace;
        font-size: 10px;
        color: rgba(255,255,255,0.4);
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-top: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

    balance = r.get("balance_owing", 0.0)
    if balance < 0:
        badge_cls, badge_txt = "badge-refund", f"REFUND  {fmt(abs(balance))}"
    elif balance > 0:
        badge_cls, badge_txt = "badge-owing", f"OWING  {fmt(balance)}"
    else:
        badge_cls, badge_txt = "badge-zero", "BALANCED — NO AMOUNT DUE"

    # ── Hero ──────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="tax-root">
    <div class="tax-hero">
        <div class="tax-hero-label">Canada Revenue Agency · Tax Assessment</div>
        <div class="tax-hero-title">{fmt(r.get('total_payable', 0))}</div>
        <div class="tax-hero-sub">Total Tax Payable</div>
        <div class="tax-badge {badge_cls}">{badge_txt}</div>
    </div>
    """, unsafe_allow_html=True)

    # # ── Key metrics ───────────────────────────────────────────────
    # st.markdown(f"""
    # <div class="tax-metric-grid">
    #     <div class="tax-metric">
    #         <div class="tax-metric-val">{fmt(r.get('total_income', 0))}</div>
    #         <div class="tax-metric-lbl">Total Income</div>
    #     </div>
    #     <div class="tax-metric">
    #         <div class="tax-metric-val">{fmt(r.get('taxable_income', 0))}</div>
    #         <div class="tax-metric-lbl">Taxable Income</div>
    #     </div>
    #     <div class="tax-metric">
    #         <div class="tax-metric-val">{fmt(r.get('combined_tax', 0))}</div>
    #         <div class="tax-metric-lbl">Combined Tax</div>
    #     </div>
    # </div>
    # """, unsafe_allow_html=True)

    # ── Income breakdown ─────────────────────────────────────────
    st.markdown(f"""
    <div class="tax-section">
        <div class="tax-section-title">Income Summary</div>
        <div class="tax-row">
            <span class="tax-row-label">Total Income</span>
            <span class="tax-row-value">{fmt(r.get('total_income', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Grossed-Up Dividends</span>
            <span class="tax-row-value">{fmt(r.get('grossed_up_dividends', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Net Income</span>
            <span class="tax-row-value">{fmt(r.get('net_income', 0))}</span>
        </div>
        <div class="tax-row tax-row-highlight">
            <span class="tax-row-label">Taxable Income</span>
            <span class="tax-row-value">{fmt(r.get('taxable_income', 0))}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tax calculation ──────────────────────────────────────────
    st.markdown(f"""
    <div class="tax-section">
        <div class="tax-section-title">Tax Calculation</div>
        <div class="tax-row">
            <span class="tax-row-label">Federal Tax (before credits)</span>
            <span class="tax-row-value">{fmt(r.get('federal_tax_before_credits', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Provincial Tax</span>
            <span class="tax-row-value">{fmt(r.get('provincial_tax', 0))}</span>
        </div>
        <div class="tax-row tax-row-highlight">
            <span class="tax-row-label">Combined Tax</span>
            <span class="tax-row-value">{fmt(r.get('combined_tax', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Net Federal Tax</span>
            <span class="tax-row-value">{fmt(r.get('net_federal_tax', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Net Provincial Tax</span>
            <span class="tax-row-value">{fmt(r.get('net_provincial_tax', 0))}</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">Total Payable</span>
            <span class="tax-total-value">{fmt(r.get('total_payable', 0))}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Federal credits ──────────────────────────────────────────
    st.markdown(f"""
    <div class="tax-section">
        <div class="tax-section-title">Federal Non-Refundable Credits</div>
        <div class="tax-row">
            <span class="tax-row-label">Basic Personal Amount</span>
            <span class="tax-row-value">{fmt(r.get('federal_basic_personal_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">CPP Contributions</span>
            <span class="tax-row-value">{fmt(r.get('federal_cpp_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">EI Premiums</span>
            <span class="tax-row-value">{fmt(r.get('federal_ei_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Medical Expenses</span>
            <span class="tax-row-value">{fmt(r.get('federal_medical_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Charitable Donations</span>
            <span class="tax-row-value">{fmt(r.get('federal_donation_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Tuition</span>
            <span class="tax-row-value">{fmt(r.get('federal_tuition_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Dividend Tax Credit</span>
            <span class="tax-row-value">{fmt(r.get('federal_dividend_credit', 0))}</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">Total Federal Credits</span>
            <span class="tax-total-value">{fmt(r.get('total_federal_credits', 0))}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Provincial credits ───────────────────────────────────────
    st.markdown(f"""
    <div class="tax-section">
        <div class="tax-section-title">Provincial Non-Refundable Credits</div>
        <div class="tax-row">
            <span class="tax-row-label">Basic Personal Amount</span>
            <span class="tax-row-value">{fmt(r.get('provincial_basic_personal_credit', 0))}</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">Total Provincial Credits</span>
            <span class="tax-total-value">{fmt(r.get('total_provincial_credits', 0))}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Balance ──────────────────────────────────────────────────
    credits_paid = r.get("total_credits_and_payments", 0)
    st.markdown(f"""
    <div class="tax-section">
        <div class="tax-section-title">Final Balance</div>
        <div class="tax-row">
            <span class="tax-row-label">Total Payable</span>
            <span class="tax-row-value">{fmt(r.get('total_payable', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Credits & Payments Applied</span>
            <span class="tax-row-value">({fmt(credits_paid)})</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">{'Refund' if balance < 0 else 'Balance Owing'}</span>
            <span class="tax-total-value" style="color: {'#34c759' if balance <= 0 else '#ff453a'}">
                {fmt(abs(balance))}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Notes ────────────────────────────────────────────────────
    notes = r.get("notes", [])
    if notes:
        for note in notes:
            st.markdown(f'<div class="tax-note">ℹ️ &nbsp;{note}</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)




def render_tax_result(tax_result):
    # Support both dataclass and dict
    r = tax_result if isinstance(tax_result, dict) else vars(tax_result)

    def fmt(v): return f"${v:,.2f}"

    st.markdown("""
    <style>
    /* ── Floating container ──────────────────────────────────── */
    .tax-float-wrapper {
        position: fixed;
        bottom: 24px;
        right: 24px;
        width: 380px;
        max-height: 85vh;
        overflow-y: auto;
        z-index: 9999;
        scrollbar-width: thin;
        scrollbar-color: rgba(196,163,95,0.3) transparent;
    }
    .tax-float-wrapper::-webkit-scrollbar {
        width: 4px;
    }
    .tax-float-wrapper::-webkit-scrollbar-thumb {
        background: rgba(196,163,95,0.3);
        border-radius: 4px;
    }

    /* ── Collapse toggle button ──────────────────────────────── */
    .tax-toggle {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 10000;
        background: #0a1628;
        border: 1px solid rgba(196,163,95,0.4);
        border-radius: 50%;
        width: 48px;
        height: 48px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        font-size: 20px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    }

    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');
    .tax-root { font-family: 'DM Sans', sans-serif; }

    /* ... rest of your existing styles ... */
    .tax-hero {
        background: linear-gradient(135deg, #0a1628 0%, #0d2137 50%, #0a1628 100%);
        border: 1px solid rgba(196,163,95,0.3);
        border-radius: 16px;
        padding: 24px 28px;           /* slightly tighter for floating panel */
        margin-bottom: 12px;
        position: relative;
        overflow: hidden;
    }
    .tax-hero-label {
        font-family: 'DM Mono', monospace;
        font-size: 10px;
        letter-spacing: 3px;
        color: #c4a35f;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    .tax-hero-title {
        font-family: 'DM Serif Display', serif;
        font-size: 32px;              /* smaller for panel */
        color: #f0e6cc;
        margin: 0;
        line-height: 1.1;
    }
    .tax-hero-sub {
        font-size: 12px;
        color: rgba(240,230,204,0.5);
        margin-top: 4px;
        font-family: 'DM Mono', monospace;
    }
    .tax-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-family: 'DM Mono', monospace;
        font-weight: 500;
        letter-spacing: 1px;
        margin-top: 12px;
    }
    .badge-refund { background: rgba(52,199,89,0.15);  color: #34c759; border: 1px solid rgba(52,199,89,0.3); }
    .badge-owing  { background: rgba(255,69,58,0.15);   color: #ff453a; border: 1px solid rgba(255,69,58,0.3); }
    .badge-zero   { background: rgba(196,163,95,0.15);  color: #c4a35f; border: 1px solid rgba(196,163,95,0.3); }

    .tax-section {
        background: #0d1f33;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 10px;
    }
    .tax-section-title {
        font-family: 'DM Mono', monospace;
        font-size: 9px;
        letter-spacing: 3px;
        color: #c4a35f;
        text-transform: uppercase;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(196,163,95,0.2);
    }
    .tax-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid rgba(255,255,255,0.04);
    }
    .tax-row:last-child { border-bottom: none; }
    .tax-row-label {
        font-size: 12px;
        color: rgba(255,255,255,0.55);
        font-weight: 300;
    }
    .tax-row-value {
        font-family: 'DM Mono', monospace;
        font-size: 12px;
        color: #e8dcc8;
        font-weight: 500;
    }
    .tax-row-highlight .tax-row-label { color: rgba(255,255,255,0.85); font-weight: 500; }
    .tax-row-highlight .tax-row-value { color: #c4a35f; font-size: 13px; }
    .tax-total-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0 2px;
        margin-top: 6px;
        border-top: 1px solid rgba(196,163,95,0.3);
    }
    .tax-total-label { font-size: 13px; color: rgba(255,255,255,0.8); font-weight: 500; }
    .tax-total-value { font-family: 'DM Serif Display', serif; font-size: 18px; color: #c4a35f; }
    .tax-note {
        background: rgba(196,163,95,0.08);
        border-left: 3px solid #c4a35f;
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        font-size: 11px;
        color: rgba(240,230,204,0.7);
        margin-top: 10px;
        font-family: 'DM Mono', monospace;
    }
    </style>
    """, unsafe_allow_html=True)

    balance = r.get("balance_owing", 0.0)
    if balance < 0:
        badge_cls, badge_txt = "badge-refund", f"REFUND  {fmt(abs(balance))}"
    elif balance > 0:
        badge_cls, badge_txt = "badge-owing",  f"OWING  {fmt(balance)}"
    else:
        badge_cls, badge_txt = "badge-zero",   "BALANCED — NO AMOUNT DUE"

    # ✅ Wrap everything in the floating container
    st.markdown(f"""
    <div class="tax-float-wrapper">
    <div class="tax-root">

    <div class="tax-hero">
        <div class="tax-hero-label">Canada Revenue Agency · Tax Assessment</div>
        <div class="tax-hero-title">{fmt(r.get('total_payable', 0))}</div>
        <div class="tax-hero-sub">Total Tax Payable</div>
        <div class="tax-badge {badge_cls}">{badge_txt}</div>
    </div>

    <div class="tax-section">
        <div class="tax-section-title">Income Summary</div>
        <div class="tax-row">
            <span class="tax-row-label">Total Income</span>
            <span class="tax-row-value">{fmt(r.get('total_income', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Grossed-Up Dividends</span>
            <span class="tax-row-value">{fmt(r.get('grossed_up_dividends', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Net Income</span>
            <span class="tax-row-value">{fmt(r.get('net_income', 0))}</span>
        </div>
        <div class="tax-row tax-row-highlight">
            <span class="tax-row-label">Taxable Income</span>
            <span class="tax-row-value">{fmt(r.get('taxable_income', 0))}</span>
        </div>
    </div>

    <div class="tax-section">
        <div class="tax-section-title">Tax Calculation</div>
        <div class="tax-row">
            <span class="tax-row-label">Federal Tax (before credits)</span>
            <span class="tax-row-value">{fmt(r.get('federal_tax_before_credits', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Provincial Tax</span>
            <span class="tax-row-value">{fmt(r.get('provincial_tax', 0))}</span>
        </div>
        <div class="tax-row tax-row-highlight">
            <span class="tax-row-label">Combined Tax</span>
            <span class="tax-row-value">{fmt(r.get('combined_tax', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Net Federal Tax</span>
            <span class="tax-row-value">{fmt(r.get('net_federal_tax', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Net Provincial Tax</span>
            <span class="tax-row-value">{fmt(r.get('net_provincial_tax', 0))}</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">Total Payable</span>
            <span class="tax-total-value">{fmt(r.get('total_payable', 0))}</span>
        </div>
    </div>

    <div class="tax-section">
        <div class="tax-section-title">Federal Non-Refundable Credits</div>
        <div class="tax-row">
            <span class="tax-row-label">Basic Personal Amount</span>
            <span class="tax-row-value">{fmt(r.get('federal_basic_personal_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">CPP Contributions</span>
            <span class="tax-row-value">{fmt(r.get('federal_cpp_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">EI Premiums</span>
            <span class="tax-row-value">{fmt(r.get('federal_ei_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Medical Expenses</span>
            <span class="tax-row-value">{fmt(r.get('federal_medical_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Charitable Donations</span>
            <span class="tax-row-value">{fmt(r.get('federal_donation_credit', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Dividend Tax Credit</span>
            <span class="tax-row-value">{fmt(r.get('federal_dividend_credit', 0))}</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">Total Federal Credits</span>
            <span class="tax-total-value">{fmt(r.get('total_federal_credits', 0))}</span>
        </div>
    </div>

    <div class="tax-section">
        <div class="tax-section-title">Final Balance</div>
        <div class="tax-row">
            <span class="tax-row-label">Total Payable</span>
            <span class="tax-row-value">{fmt(r.get('total_payable', 0))}</span>
        </div>
        <div class="tax-row">
            <span class="tax-row-label">Credits & Payments Applied</span>
            <span class="tax-row-value">({fmt(r.get('total_credits_and_payments', 0))})</span>
        </div>
        <div class="tax-total-row">
            <span class="tax-total-label">{'Refund' if balance < 0 else 'Balance Owing'}</span>
            <span class="tax-total-value" style="color: {'#34c759' if balance <= 0 else '#ff453a'}">
                {fmt(abs(balance))}
            </span>
        </div>
    </div>

    {"".join(f'<div class="tax-note">ℹ️ &nbsp;{note}</div>' for note in r.get("notes", []))}

    </div>
    </div>
    """, unsafe_allow_html=True)