import streamlit as st
from canada_tax_ai.tax_calculator import calculate_tax
from canada_tax_ai.core.graph import chat
from canada_tax_ai.utils import generate_tax_pdf
from canada_tax_ai.auth import login_page, logout_button
from canada_tax_ai.persist.db import save_tax_report
from canada_tax_ai.taxslip_analyzer import TaxSlipAnalyzer
from langchain_core.messages import HumanMessage
import datetime
import pandas as pd
from canada_tax_ai.models import TaxSlipData, T4SlipData, T5SlipData

st.set_page_config(page_title="Canada Tax AI", layout="wide",initial_sidebar_state="collapsed")


if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.title("🇨🇦 Canada Tax AI")
    st.caption("2025 Tax Year · Manitoba Province")
    login_page()
    st.set_page_config(initial_sidebar_state="collapsed")
    st.stop()

st.caption(f"2025 Tax Year · Manitoba Province · Logged in as: {st.session_state.username} | {datetime.date.today()}")
logout_button()

left_col, right_col = st.columns([2.8, 1.2], gap="small")

with left_col:
    st.subheader("💬 Chat with AI Tax Assistant")
    
    chat_container = st.container()
    with chat_container:
        if "messages" not in st.session_state:
            st.session_state.messages = [
                 {"role": "assistant", "content": f"Hello {st.session_state.username}! 👋\n\nTo help you with your Canadian tax return, I'll ask you a few questions step by step.\n\nFirst question: What is your full name, date of birth, SIN (Social Insurance Number), and current address?"}
            ]
        
        for msg in st.session_state.messages:
            avatar = "👤" if msg["role"] == "user" else "🇨🇦"  # set avatar
            with st.chat_message(msg["role"], avatar=avatar):
                st.write(msg["content"])

    with st.expander("📎 Upload T4 / T5 File (PDF or Image)", expanded=False):
        with st.spinner("Uploading file..."):
            uploaded_file = st.file_uploader("Choose file", type=["pdf", "jpg", "png", "jpeg"], label_visibility="collapsed")
        #only for debugging 
        if uploaded_file:
            if st.session_state.get("processed_file") != uploaded_file.name:
                #TODO: MD5 is better for file identity than name+size, but this is a quick fix for now
                file_key = f"file_{uploaded_file.name}_{uploaded_file.size}"

                if file_key in st.session_state.get("processed_files", {}):
                    st.info("This file has already been processed. Displaying previous results.")
                    extracted = st.session_state.processed_files[file_key]
                else:
                    with st.spinner("AI is analyzing your file..."):
                        temp_path = f"/tmp/{uploaded_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        analyzer = TaxSlipAnalyzer()
                        extracted = analyzer.analyze(temp_path)
                        print(f"Extracted data in streamlit_app: {extracted}")

                        # 自动识别并完整展示所有数据
                        doc_type = extracted.get('document_type', 'Unknown').upper()

                        if "processed_files" not in st.session_state:
                            st.session_state.processed_files = {}
                        st.session_state.processed_files[file_key] = extracted

                        st.session_state.messages.append({"role": "assistant", "content": "File analyzed and cached. Displaying results below."})
                        

                        model = T4SlipData if doc_type == "T4" else T5SlipData
                        descriptions = {k: v.description for k, v in model.model_fields.items()}

                        table = (
                            pd.DataFrame(extracted.get("t4", {}) if doc_type == "T4" else extracted.get("t5", {}), index=[0])
                            .T
                            .rename(columns={0: "Value"})
                            .assign(Description=lambda df: df.index.map(descriptions))
                            [["Description", "Value"]]
                            .assign(Value=lambda df: df["Value"].apply(lambda x: f"{float(x):.2f}" if isinstance(x, (int, float)) else x))
                            )

                        # SIN 验证逻辑
                        current_sin = extracted.get('sin', '').replace(" ", "")
                        if not current_sin:
                            st.error("❌ Could not detect SIN in this file.")
                        elif "current_sin" not in st.session_state:
                            st.session_state.current_sin = current_sin
                            st.session_state.messages.append({"role": "assistant", "content": f"✅ SIN detected: {current_sin} (First file recorded)"})
                            st.session_state.messages.append({"role": "assistant", "content": table})
                        elif current_sin != st.session_state.current_sin:
                            st.session_state.messages.append({"role": "assistant", "content": f"❌ SIN mismatch! This file belongs to SIN {current_sin}, but you are processing SIN {st.session_state.current_sin}. Please finish the current person's files first."})
                        else:
                            st.session_state.messages.append({"role": "assistant", "content": table})
                        st.session_state.extracted_data = extracted
                        st.session_state.processed_file = uploaded_file.name
                        st.rerun()
            else:
                st.info("This file has already been processed. Seeing above.")

    with st.spinner("Thinking..."):
        if prompt := st.chat_input("Type your message..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            # with st.chat_message("user", avatar="👤"):
            #     st.write(prompt)
        
            response = chat(prompt)  
            # response = result["messages"][-1].content
            st.session_state.messages.append({"role": "assistant", "content": response})
            # with st.chat_message("assistant", avatar="🇨🇦"):
            #     st.write(response)

            st.rerun()


with right_col:
    st.subheader("📊 Dynamic Tax Calculation")
    extracted = st.session_state.get("extracted_data", {})
    
    scenario = st.selectbox("Select Tax Scenario", ["Employment Income (T4)", "Self-Employed Income", "Rental Income", "Investment & Foreign Income"])
    with st.form("tax_form"):
        gross_income = st.number_input("Gross Income (CAD)", value=extracted.get('gross_income', 80000.0), step=1000.0)
        rrsp = st.number_input("RRSP Contribution", value=extracted.get('rrsp', 0.0), step=500.0)
        other_deductions = st.number_input("Other Deductions", value=0.0, step=100.0)
        has_spouse = st.checkbox("Has Spouse / Common-law Partner")
        children = st.number_input("Number of Children", value=0, step=1)
        submitted = st.form_submit_button("🚀 Calculate Tax", type="primary")
    
    if submitted:
        result = calculate_tax(gross_income, rrsp, other_deductions, has_spouse, children)
        st.session_state.tax_result = result
        save_tax_report(st.session_state.username, result)
        st.success(f"Estimated Total Tax: ${result['total_tax']:,.2f}")
        pdf_path = generate_tax_pdf(result)
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF Report", f, "tax_report.pdf")
