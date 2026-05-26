import streamlit as st
from canada_tax_ai.core.graph import process_chat, process_document
from canada_tax_ai.utils import render_slip_table
from canada_tax_ai.pages.auth import login_page, logout_button
from canada_tax_ai.persist.db import save_tax_report
from canada_tax_ai.core.document_agent import TaxSlipAnalyzer
from langchain_core.messages import HumanMessage
import datetime
import pandas as pd
import json
from canada_tax_ai.models import TaxSlipData, T4SlipData, T5SlipData
from canada_tax_ai.pages.views import render_tax_result
from canada_tax_ai.models import TaxResult
from loguru import logger

st.set_page_config(page_title="Canada Tax AI", layout="wide", initial_sidebar_state="expanded")
# ── Global styles — fixed bottom bar ──────────────────────────────
st.markdown("""
<style>
#MainMenu { visibility: hidden; }
            
#footer, header { visibility: hidden; }

.block-container {
    padding-bottom: 130px !important;
    padding-top: 0rem !important;
    max-width: 100% !important;
}
    
[data-testid="stLayoutWrapper"] {
    padding-right: 15px!important;
}

/* This targets Streamlit's actual fixed chat input */
[data-testid="stChatInput"] {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    z-index: 99999 !important;
    # background: #0a1628 !important;
    # border-top: 1px solid rgba(196,163,95,0.2) !important;
    padding: 12px 24px 16px !important;
    margin-right: 28% !important;
    margin-left: 30px !important;
    backdrop-filter: blur(12px) !important;
}

.bottom-label {
    font-size: 10px;
    letter-spacing: 2px;
    color: rgba(196,163,95,0.5);
    text-transform: uppercase;
    margin-bottom: 4px;
    font-family: monospace;
}
</style>

<script>
// Escape the bottom-bar div from Streamlit's container
// and re-attach directly to document.body so position:fixed works
(function fixBottomBar() {
    function moveBar() {
        const bar = document.querySelector('.bottom-bar');
        if (bar && bar.parentElement !== document.body) {
            // Clone styles to body-level element
            bar.style.position = 'fixed';
            bar.style.bottom = '0';
            bar.style.left = '0';
            bar.style.right = '0';
            bar.style.zIndex = '99999';
            document.body.appendChild(bar);
            console.log('bottom-bar moved to body');
        }
    }

    // Run immediately and on any DOM change
    moveBar();
    const observer = new MutationObserver(moveBar);
    observer.observe(document.body, { childList: true, subtree: true });
})();
</script>
""", unsafe_allow_html=True)

# ── Auth guard ────────────────────────────────────────────────────
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    # st.title("🇨🇦 Canada Tax AI")
    # st.caption("2025 Tax Year · Manitoba Province")
    login_page()
    st.stop()
left_col1, right_col1 = st.columns([92, 8], gap="small")
with left_col1:
    st.caption(f"2025 Tax Year · Manitoba Province · {st.session_state.username} | {datetime.date.today()}")
with right_col1:
    logout_button()

# ── Main layout ───────────────────────────────────────────────────
left_col, right_col = st.columns([75, 25], gap="small")

with left_col:
    # st.subheader("💬 Chat with AI Tax Assistant")

    # Scrollable chat history — takes all space above bottom bar
    chat_container = st.container()
    with chat_container:
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": (
                    f"Hello {st.session_state.username}! 👋\n\n"
                    "To help you with your Canadian tax return, I'll ask you a few questions step by step.\n\n"
                    "First: What is your prefered language?"
                )}
            ]

        for msg in st.session_state.messages:
            avatar = "👤" if msg["role"] == "user" else "🇨🇦"
            with st.chat_message(msg["role"], avatar=avatar):
                if isinstance(msg["content"], pd.DataFrame):
                    st.dataframe(msg["content"])
                else:
                    st.write(msg["content"])
        
    # ── Fixed bottom bar — chat input + file upload ───────────────────
    st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
    with st.container():

        if prompt := st.chat_input("Type your message...", 
                                    key="main_chat_input",
                                    height=102,
                                    accept_audio=True,
                                    accept_file=True,
                                    file_type=["jpg", "jpeg", "png", "pdf"],):
            with st.spinner("Thinking..."):
                if prompt and prompt.text:
                    # st.markdown(prompt.text)
                    st.session_state.messages.append({"role": "user", "content": prompt.text})
                    response = process_chat(prompt.text)
                    response_content = response.get("messages", "") if isinstance(response, dict) else response
                    tax_result = response.get("tax_result", {}) if isinstance(response, dict) else None
                    logger.info(f"Chat response content: {response}")
                    if tax_result:
                        st.session_state.tax_result = tax_result
                    if isinstance(response_content, dict) and "document_type" in response_content:
                        doc_type = response_content.get("document_type", "").upper()
                        model = T4SlipData if doc_type == "T4" else T5SlipData
                        table = render_slip_table(response_content, doc_type, model)
                        st.session_state.messages.append({"role": "assistant", "content": table})
                    else:
                        st.session_state.messages.append({"role": "assistant", "content": response_content})

                if prompt and prompt["files"]:
                    logger.info(f"Received files: {prompt['files']}")
                    uploaded_file = prompt["files"][0]
                    
                    file_key = f"file_{uploaded_file.name}_{uploaded_file.size}"
                    if file_key in st.session_state.get("processed_files", {}):
                        extracted = st.session_state.processed_files[file_key]
                    else:
                        temp_path = f"/tmp/{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        response_data = process_document(temp_path)

                        logger.info(f"Document processing result: {response_data.get('tax_result', {})}")
                        tax_result = response_data.get("tax_result", {}) if response_data.get("tax_result") else None
                        if tax_result:
                            st.session_state.tax_result = tax_result


                        extracted = response_data.get("extracted_data", {})
                        doc_type = extracted.get("document_type", "Unknown").upper()

                        if "processed_files" not in st.session_state:
                            st.session_state.processed_files = {}
                        st.session_state.processed_files[file_key] = extracted

                        model = T4SlipData if doc_type == "T4" else T5SlipData
                        table = render_slip_table(extracted, doc_type, model)

                        current_sin = extracted.get("sin", "").replace(" ", "")
                        if not current_sin:
                            slip = extracted.get("t4", [])[-1] if doc_type == "T4" else extracted.get("t5", [])[-1]
                            current_sin = slip.get("recipient_sin", "").replace(" ", "")

                        if not current_sin:
                            st.session_state.messages.append({"role": "assistant", "content": "❌ Could not detect SIN in this file."})
                        elif "current_sin" not in st.session_state:
                            st.session_state.current_sin = current_sin
                            st.session_state.messages.append({"role": "assistant", "content": f"✅ SIN detected: {current_sin}"})
                            st.session_state.messages.append({"role": "assistant", "content": table})
                        elif current_sin != st.session_state.current_sin:
                            st.session_state.messages.append({"role": "assistant", "content": (
                                f"❌ SIN mismatch! File belongs to {current_sin}, "
                                f"but current session is {st.session_state.current_sin}."
                            )})
                        else:
                            st.session_state.messages.append({"role": "assistant", "content": table})

                        st.session_state.extracted_data = extracted
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

with right_col:
    # st.subheader("📊 Tax Calculation")
    extracted = st.session_state.get("extracted_data", {})
    result = st.session_state.get("tax_result", {}) or TaxResult(
        notes=["Upload a T4 or T5 to calculate your return."]
    )
    logger.info(f"Extracted data for tax calculation: {result}")
    render_tax_result(result)
    st.markdown('</div>', unsafe_allow_html=True)


