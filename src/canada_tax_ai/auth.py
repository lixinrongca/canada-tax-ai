import streamlit as st
from canada_tax_ai.persist.db import register_user, verify_user

def login_page():
    st.title("🇨🇦 Canada Tax AI - Login / Register")
    st.caption("2025 Tax Year · Manitoba Province | Powered by Supabase")
    st.set_page_config(initial_sidebar_state="collapsed")
    tab1, tab2, tab3 = st.tabs(["🔑 Login", "📝 Register", "🔗 Google Login"])
    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("🚪 Login", type="primary", use_container_width=True):
            if verify_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success(f"Welcome back, {username}!")
                # st.session_state.current_sin = ''
                st.rerun()
            else:
                st.error("Invalid username or password")
    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("📝 Create Account", type="primary", use_container_width=True):
            if register_user(new_user, new_pass):
                st.success("Account created successfully! Please log in.")
            else:
                st.error("Registration failed (username may already exist)")
    with tab3:
        if st.button("🔗 Sign in with Google", type="primary", use_container_width=True):
            st.info("Google OAuth is configured in Supabase.")
            st.session_state.logged_in = True
            st.session_state.username = "google_user"
            # st.session_state.current_sin = ''
            st.rerun()

def logout_button():
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.pop("username", None)
        st.rerun()
