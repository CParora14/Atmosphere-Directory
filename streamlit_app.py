import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Page setup
st.set_page_config(page_title="Atmosphere Society Business Directory", layout="wide")

# -----------------------------
# AUTH: use credentials from Streamlit secrets (TOML)
# -----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    sa_info = dict(st.secrets["gcp_service_account"])   # load service account from secrets
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

gc = get_gspread_client()

# -----------------------------
# Example Google Sheet Access
# -----------------------------
SPREADSHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"   # 👈 replace with your Sheet ID

try:
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    data = worksheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])  # first row as header
    st.success("✅ Connected to Google Sheet!")
    st.dataframe(df)
except Exception as e:
    st.error(f"❌ Could not connect: {e}")

