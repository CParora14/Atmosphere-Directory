import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Atmosphere Society Business Directory", layout="wide")

# -----------------------------
# OPTIONAL LOGIN (uses Secrets). If not set, app runs without login.
# -----------------------------
def require_login_if_configured():
    user_key = "APP_USERNAME"
    pass_key = "APP_PASSWORD"
    if user_key in st.secrets and pass_key in st.secrets:
        st.subheader("Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if not st.session_state.logged_in:
            if u and p:
                if u == st.secrets[user_key] and p == st.secrets[pass_key]:
                    st.session_state.logged_in = True
                    st.success("Logged in successfully!")
                else:
                    st.error("Wrong username or password.")
                    st.stop()
            else:
                st.info("Enter username and password to continue.")
                st.stop()

require_login_if_configured()

st.title("🏡 Atmosphere Society Business Directory")

# -----------------------------
#  AUTH via Streamlit Secrets (TOML)
# -----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    sa_info = dict(st.secrets["gcp_service_account"])   # <- from Secrets page
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

gc = get_gspread_client()

# -----------------------------
#  GOOGLE SHEETS (change these two if needed)
# -----------------------------
SHEET_ID = "1SWVjrtC8qh9fXFhrcXbc_6cgNS39tc87vvPz1PCaeFY"   # your Sheet ID
WANTED_SHEET_NAME = "Business_Listings"                    # tab name at bottom

# Show which service account we’re using (quick check)
sa_email = st.secrets["gcp_service_account"]["client_email"]
st.caption("Google Sheets connection")
st.write("Service account email:", f"`{sa_email}`")

# -----------------------------
#  OPEN SHEET, LOAD DATA
# -----------------------------
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

try:
    # Open by KEY (most reliable)
    sh = gc.open_by_key(SHEET_ID)
    st.success(f"Opened spreadsheet: **{sh.title}**")

    # Show tabs so you can confirm the name
    tabs = [ws.title for ws in sh.worksheets()]
    st.write("Available tabs:", tabs)

    # Pick your tab (or fall back to first)
    if WANTED_SHEET_NAME in tabs:
        ws = sh.worksheet(WANTED_SHEET_NAME)
    else:
        ws = sh.worksheets()[0]
        st.warning(f"Tab '{WANTED_SHEET_NAME}' not found. Using first tab: '{ws.title}'")

    # Read data into DataFrame (assumes first row = headers)
    rows = ws.get_all_values()
    df = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()

    st.success("✅ Connected and loaded data!")
    st.dataframe(df, use_container_width=True)

except SpreadsheetNotFound as e:
    st.error("❌ Could not open the spreadsheet by KEY.")
    st.write("- Double-check the SHEET_ID in the code.")
    st.write("- Make sure the sheet is **shared as Editor** with:")
    st.code(sa_email)
    st.write("- Ensure **Google Sheets API** and **Google Drive API** are enabled in your GCP project.")
    st.code(str(e))

except WorksheetNotFound as e:
    st.error("❌ Spreadsheet opened, but the worksheet/tab name is wrong.")
    st.write("Tabs in this sheet:", tabs if 'tabs' in locals() else "unknown")
    st.code(str(e))

except Exception as e:
    st.error("❌ Unexpected error while connecting to Google Sheets.")
    st.code(str(e))

