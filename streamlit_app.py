# --- Google Sheets connection (using your URL) ---
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound

SHEET_URL = "https://docs.google.com/spreadsheets/d/1SWVjrtC8qh9fXFhrcXbc_6cgNS39tc87vvPz1PCaeFY/edit?gid=0#gid=0"
WANTED_SHEET_NAME = "Business_Listings"  # change this to your actual tab name if different

sa_email = st.secrets["gcp_service_account"]["client_email"]
st.caption("Google Sheets connection")
st.write("Service account email:", f"`{sa_email}`")

try:
    sh = gc.open_by_url(SHEET_URL)
    st.success(f"Opened spreadsheet: **{sh.title}**")

    # List available tabs so you can confirm the name
    tabs = [ws.title for ws in sh.worksheets()]
    st.write("Available tabs:", tabs)

    # Use requested tab if it exists; otherwise use the first tab and warn
    if WANTED_SHEET_NAME in tabs:
        ws = sh.worksheet(WANTED_SHEET_NAME)
    else:
        ws = sh.worksheets()[0]
        st.warning(f"Tab '{WANTED_SHEET_NAME}' not found. Using first tab: '{ws.title}'")

    rows = ws.get_all_values()
    df = pd.DataFrame(rows[1:], columns=rows[0]) if rows else pd.DataFrame()
    st.success("✅ Connected and loaded data!")
    st.dataframe(df, use_container_width=True)

except SpreadsheetNotFound as e:
    st.error("❌ Could not open the spreadsheet by URL.")
    st.write("- Check the URL is exactly the one from your address bar (you pasted it above).")
    st.write(f"- Make sure the sheet is **shared as Editor** with: `{sa_email}`")
    st.write("- Ensure **Google Sheets API** AND **Google Drive API** are enabled in your GCP project.")
    st.code(str(e))

except WorksheetNotFound as e:
    st.error("❌ Spreadsheet opened, but the worksheet/tab name is wrong.")
    st.code(str(e))

except Exception as e:
    st.error("❌ Unexpected error while connecting to Google Sheets.")
    st.code(str(e))
