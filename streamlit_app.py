import streamlit as st
import pandas as pd

st.set_page_config(page_title="Atmosphere Directory", layout="wide")

st.title("🏠 Atmosphere Society Business Directory")

# Temporary login (we can upgrade later to Gmail auth)
password = st.text_input("Enter password:", type="password")
if password == "1234":  # <-- change this later
    st.success("✅ Logged in successfully!")

    st.subheader("Resident Business Listings")
    st.write("This will connect to Google Sheets and display records.")
else:
    st.warning("Please enter the correct password to continue.")
