# ──────────────────────────────────────────────────────────────────────────────
# Atmosphere Society Directory - Streamlit
# Tabs: Directory | Submit | Vicinity Vendors | Admin
# Google Sheets auth: st.secrets["gcp_service_account"]
# Login (Admin): st.secrets["APP_USERNAME"], st.secrets["APP_PASSWORD"]
# ──────────────────────────────────────────────────────────────────────────────

import re
import time
from typing import List

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# ---------- Page & Style ----------
st.set_page_config(
    page_title="Atmosphere Society Business Directory",
    page_icon="🏡",
    layout="wide",
)

# Color palette inspired by “Atmosphere”
ACCENT = "#22c55e"      # emerald
PRIMARY = "#3b82f6"     # sky/blue
PRIMARY_2 = "#2563eb"   # deeper blue
INK = "#e5e7eb"         # light gray text
CARD_BG = "#0f172a"     # slate-900
PAGE_BG = "#0b1220"     # near-black
WARNING = "#f59e0b"     # amber

st.markdown(
    f"""
    <style>
      .stApp {{
        background: linear-gradient(120deg, {PAGE_BG} 10%, #0a1a32 100%);
      }}
      .atm-hero {{
        border-radius: 18px;
        padding: 28px 24px;
        background: linear-gradient(90deg, {PRIMARY_2}, {PRIMARY});
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,.35);
      }}
      .atm-badge {{
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(255,255,255,.18);
        font-size: .85rem;
        color: #fff;
      }}
      .atm-card {{
        background: {CARD_BG};
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(255,255,255,.06);
      }}
      .atm-title {{
        font-weight: 700;
        color: #fff;
        margin-bottom: 6px;
      }}
      .atm-sub {{
        color: {INK};
        font-size: .9rem;
      }}
      .atm-rowgap > div {{
        margin-bottom: 16px;
      }}
      .stTabs [data-baseweb="tab"] {{
        font-size: 1rem;
      }}
      .stButton>button.atm-approve {{
        background: {ACCENT};
        color: #0b0f1a;
        border: 0;
        font-weight: 600;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="atm-hero">
      <div class="atm-badge">Phase 1 & 2 • Community-first • Mobile-ready</div>
      <h1 style="margin:6px 0 0 0">Atmosphere Society Business Directory</h1>
      <div style="opacity:.92">Discover resident businesses, recommend services, and support local vendors.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Config (EDIT THESE TWO NAMES IF YOU LIKE) ----------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SWVjrtC8qh9fXFhrcXbc_6cgNS39tc87vvPz1PCaeFY/edit?gid=0#gid=0"

DIRECTORY_SHEET = "Business_Listings"       # tab for resident listings
VENDORS_SHEET   = "Vicinity_Vendors"        # tab for outside vendors

# Expected columns for both tabs (feel free to add columns; the app ignores unknowns)
EXPECTED_COLUMNS: List[str] = [
    "Approved", "Phase", "Wing", "Flat_No",
    "Resident_Name", "Phone", "Email",
    "Business_Name", "Category", "Subcategory", "Service_Type",
    "Short_Description", "Detailed_Description",
    "Website", "Instagram", "Address"
]

# ---------- Google Sheets client ----------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    sa_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

gc = get_gspread_client()

# ---------- Sheet helpers ----------
def open_sheet_by_url(url: str):
    try:
        return gc.open_by_url(url)
    except SpreadsheetNotFound as e:
        st.error("Could not open the spreadsheet by URL. Double-check the URL.")
        st.code(str(e))
        st.stop()

def get_or_create_ws(sh, tab_name: str, expected_header: List[str]):
    """Open a worksheet; if missing, create it with header row."""
    names = [ws.title for ws in sh.worksheets()]
    if tab_name in names:
        return sh.worksheet(tab_name)
    # Create with headers if missing
    ws = sh.add_worksheet(title=tab_name, rows=2000, cols=max(len(expected_header), 20))
    ws.update([expected_header])
    return ws

def ws_to_df(ws) -> pd.DataFrame:
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    header, body = rows[0], rows[1:]
    df = pd.DataFrame(body, columns=header)
    # Trim empty rows
    df = df.replace("", pd.NA).dropna(how="all")
    # Ensure all expected columns exist
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df

def append_row(ws, ordered_cols: List[str], data: dict):
    row = [data.get(c, "") for c in ordered_cols]
    ws.append_row(row, value_input_option="USER_ENTERED")

def approve_row(ws, row_idx: int):
    # Finds "Approved" column and sets to "Yes" for the given 1-based data row
    header = ws.row_values(1)
    try:
        col = header.index("Approved") + 1
    except ValueError:
        return
    ws.update_cell(row_idx, col, "Yes")

# ---------- Load the spreadsheet & tabs ----------
sh = open_sheet_by_url(SHEET_URL)
st.success(f"Connected to **{sh.title}**")

ws_dir = get_or_create_ws(sh, DIRECTORY_SHEET, EXPECTED_COLUMNS)
ws_vnd = get_or_create_ws(sh, VENDORS_SHEET,   EXPECTED_COLUMNS)

df_dir = ws_to_df(ws_dir)
df_vnd = ws_to_df(ws_vnd)

# ---------- Small Utilities ----------
def nice(s: str) -> str:
    return (s or "").strip()

def filter_df(df: pd.DataFrame, phase, cat, svc, q) -> pd.DataFrame:
    out = df.copy()
    if phase and phase != "All":
        out = out[out["Phase"].str.strip().fillna("") == phase]
    if cat and cat != "All":
        out = out[out["Category"].str.strip().fillna("") == cat]
    if svc and svc != "All":
        out = out[out["Service_Type"].str.strip().fillna("") == svc]
    if q:
        pat = re.compile(re.escape(q), re.IGNORECASE)
        cols = ["Business_Name", "Short_Description", "Detailed_Description", "Resident_Name", "Subcategory", "Address"]
        mask = pd.Series(False, index=out.index)
        for c in cols:
            mask = mask | out[c].astype(str).str.contains(pat, na=False)
        out = out[mask]
    return out

def render_cards(df: pd.DataFrame, empty_msg="No approved listings yet."):
    if df.empty:
        st.info(empty_msg)
        return
    # Create a fluid grid
    cols = st.columns([1,1,1], gap="large")
    i = 0
    for _, r in df.iterrows():
        with cols[i % 3]:
            st.markdown('<div class="atm-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="atm-title">{nice(r["Business_Name"]) or "Untitled"}</div>', unsafe_allow_html=True)
            sub = f'{nice(r["Category"])} • {nice(r["Service_Type"])}'
            st.markdown(f'<div class="atm-sub">{sub}</div>', unsafe_allow_html=True)
            if nice(r["Short_Description"]):
                st.markdown(f'<div style="margin:6px 0;color:#cbd5e1">{r["Short_Description"]}</div>', unsafe_allow_html=True)

            meta = []
            if nice(r["Phase"]): meta.append(f'Phase {r["Phase"]}')
            if nice(r["Wing"]):  meta.append(f'Wing {r["Wing"]}')
            if nice(r["Resident_Name"]): meta.append(r["Resident_Name"])
            if meta:
                st.caption(" • ".join(meta))

            links = []
            if nice(r["Website"]):    links.append(f'🌐 [Website]({r["Website"]})')
            if nice(r["Instagram"]):  links.append(f'📸 [Instagram]({r["Instagram"]})')
            if nice(r["Email"]):      links.append(f'✉️ {r["Email"]}')
            if nice(r["Phone"]):      links.append(f'📞 {r["Phone"]}')
            if links:
                st.markdown(" • ".join(links))

            st.markdown("</div>", unsafe_allow_html=True)
        i += 1

# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["Browse Directory", "Submit Listing", "Vicinity Vendors", "Admin"])

# ── 1) Browse Directory
with tab1:
    st.subheader("Browse resident businesses")
    approved = df_dir[df_dir["Approved"].str.strip().str.lower() == "yes"]

    # Filter options from data
    phases = ["All"] + sorted([p for p in approved["Phase"].dropna().unique() if p])
    cats   = ["All"] + sorted([c for c in approved["Category"].dropna().unique() if c])
    svcs   = ["All"] + sorted([s for s in approved["Service_Type"].dropna().unique() if s])

    c1,c2,c3,c4 = st.columns([1,1,1,2])
    phase = c1.selectbox("Phase", phases, index=0)
    cat   = c2.selectbox("Category", cats, index=0)
    svc   = c3.selectbox("Service Type", svcs, index=0)
    q     = c4.text_input("Search", placeholder="name, service, keyword...")

    show = filter_df(approved, phase, cat, svc, q)
    st.markdown('<div class="atm-rowgap">', unsafe_allow_html=True)
    render_cards(show)
    st.markdown('</div>', unsafe_allow_html=True)

# ── 2) Submit Listing
with tab2:
    st.subheader("Submit your business")
    with st.form("submit_form", clear_on_submit=True):
        phase = st.selectbox("Phase", ["Atmosphere 1", "Atmosphere 2"])
        wing  = st.selectbox("Wing", list("ABCDEFGHIJ"))
        flat  = st.text_input("Flat No (e.g., 1203)")
        rname = st.text_input("Resident Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")

        c = st.text_input("Category")
        sc = st.text_input("Subcategory")
        stype = st.text_input("Service Type")
        bname = st.text_input("Business Name*")
        short = st.text_area("Short Description (one line)")
        detail= st.text_area("Detailed Description")

        web = st.text_input("Website URL")
        ig  = st.text_input("Instagram URL")
        addr= st.text_area("Address")

        submitted = st.form_submit_button("Submit")
        if submitted:
            if not bname.strip():
                st.warning("Please provide Business Name.")
            else:
                payload = {
                    "Approved": "No",
                    "Phase": phase,
                    "Wing": wing,
                    "Flat_No": flat,
                    "Resident_Name": rname,
                    "Phone": phone,
                    "Email": email,
                    "Business_Name": bname,
                    "Category": c,
                    "Subcategory": sc,
                    "Service_Type": stype,
                    "Short_Description": short,
                    "Detailed_Description": detail,
                    "Website": web,
                    "Instagram": ig,
                    "Address": addr,
                }
                append_row(ws_dir, EXPECTED_COLUMNS, payload)
                st.success("Submitted! Your listing will appear after admin approval.")

# ── 3) Vicinity Vendors
with tab3:
    st.subheader("Vicinity Vendors (nearby)")
    approved_v = df_vnd[df_vnd["Approved"].str.strip().str.lower() == "yes"]

    cats_v = ["All"] + sorted([c for c in approved_v["Category"].dropna().unique() if c])
    svc_v  = ["All"] + sorted([s for s in approved_v["Service_Type"].dropna().unique() if s])

    c1,c2,c3 = st.columns([1,1,2])
    catv = c1.selectbox("Category", cats_v, index=0, key="v_cat")
    svcv = c2.selectbox("Service Type", svc_v, index=0, key="v_svc")
    qv   = c3.text_input("Search", key="v_q")

    show_v = filter_df(approved_v, "All", catv, svcv, qv)
    render_cards(show_v, empty_msg="No approved vendors yet.")

    st.divider()
    with st.expander("Suggest a new vendor"):
        with st.form("vendor_form", clear_on_submit=True):
            bname = st.text_input("Vendor / Shop Name*")
            c = st.text_input("Category")
            sc = st.text_input("Subcategory")
            stype = st.text_input("Service Type")
            short = st.text_area("Short Description")
            contact = st.text_input("Phone / Email")
            web = st.text_input("Website URL")
            ig  = st.text_input("Instagram URL")
            addr= st.text_area("Address / Exact location")

            v_submit = st.form_submit_button("Suggest Vendor")
            if v_submit:
                if not bname.strip():
                    st.warning("Please provide a vendor name.")
                else:
                    payload = {
                        "Approved": "No",
                        "Phase": "", "Wing": "", "Flat_No": "",
                        "Resident_Name": "", "Phone": contact, "Email": "",
                        "Business_Name": bname,
                        "Category": c, "Subcategory": sc, "Service_Type": stype,
                        "Short_Description": short, "Detailed_Description": "",
                        "Website": web, "Instagram": ig, "Address": addr,
                    }
                    append_row(ws_vnd, EXPECTED_COLUMNS, payload)
                    st.success("Thank you! Vendor will appear after admin approval.")

# ── 4) Admin
with tab4:
    st.subheader("Admin")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == st.secrets["APP_USERNAME"] and p == st.secrets["APP_PASSWORD"]:
            st.session_state["_is_admin"] = True
            st.success("Welcome, admin!")
            time.sleep(0.6)
            st.experimental_rerun()
        else:
            st.error("Invalid credentials.")

    if st.session_state.get("_is_admin"):
        st.success("Logged in as admin.")
        st.write("Approve pending items. Use refresh after bulk actions.")

        colA, colB = st.columns(2)

        with colA:
            st.markdown("**Resident listings — pending**")
            pending = df_dir[df_dir["Approved"].str.strip().str.lower() != "yes"]
            if pending.empty:
                st.info("No pending resident listings.")
            else:
                for idx, r in pending.iterrows():
                    with st.container(border=True):
                        st.write(f"**{nice(r['Business_Name'])}** — {nice(r['Category'])} / {nice(r['Service_Type'])}")
                        st.caption(nice(r["Short_Description"]))
                        if st.button("Approve", key=f"a_dir_{idx}", help="Make visible"):
                            # +2 because: header is row 1, df row is 0-based, gspread is 1-based
                            approve_row(ws_dir, row_idx=idx + 2)
                            st.success("Approved.")
                            time.sleep(.4)
                            st.experimental_rerun()

        with colB:
            st.markdown("**Vicinity vendors — pending**")
            pending_v = df_vnd[df_vnd["Approved"].str.strip().str.lower() != "yes"]
            if pending_v.empty:
                st.info("No pending vendors.")
            else:
                for idx, r in pending_v.iterrows():
                    with st.container(border=True):
                        st.write(f"**{nice(r['Business_Name'])}** — {nice(r['Category'])} / {nice(r['Service_Type'])}")
                        st.caption(nice(r["Short_Description"]))
                        if st.button("Approve", key=f"a_v_{idx}"):
                            approve_row(ws_vnd, row_idx=idx + 2)
                            st.success("Approved.")
                            time.sleep(.4)
                            st.experimental_rerun()

