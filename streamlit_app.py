import streamlit as st

st.set_page_config(page_title="Atmosphere Society Business Directory", layout="wide")

# --- Read secrets (must exist on Streamlit Cloud) ---
APP_USERNAME = st.secrets.get("APP_USERNAME")
APP_PASSWORD = st.secrets.get("APP_PASSWORD")

if not APP_USERNAME or not APP_PASSWORD:
    st.error("Server secrets missing. Set APP_USERNAME and APP_PASSWORD in App → Settings → Secrets.")
    st.stop()

# --- Simple login state ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.title("🏡 Atmosphere Society Business Directory")

if not st.session_state.logged_in:
    col1, col2 = st.columns(2)
    with col1:
        user = st.text_input("Username")
    with col2:
        pwd = st.text_input("Password", type="password")

    if st.button("Sign in"):
        if user == APP_USERNAME and pwd == APP_PASSWORD:
            st.session_state.logged_in = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    st.stop()

# --- App content after login ---
st.success(f"Welcome, {APP_USERNAME}!")
st.write("This is where the directory UI will appear.")
