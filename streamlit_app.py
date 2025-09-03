# ---------------------------------------------------------------
# Atmosphere Society Business Directory – Streamlit
# Tabs: Directory | Submit | Vicinity Vendors | Showcase | Admin
# Auth: Google Sheets via st.secrets["gcp_service_account"]
# Login: username & password from secrets (Admin only)
# ---------------------------------------------------------------

from __future__ import annotations

import re
import time
from typing import List

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# ------------- Branding (Atmosphere) ---------------------------

PRIMARY   = "#1B8CD8"   # main Atmosphere blue
PRIMARY_2 = "#6BC6FF"   # light blue accent
INK       = "#0C2A4A"   # dark ink for text
CARD_BG   = "#0E1C2B"   # dark card
PAGE_BG   = "#0A1522"   # page bg
WARNING   = "#F7B500"

BANNER_GRADIENT = f"linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_2} 100%)"

LOGO_PATH = "logo.png"          # put a file called logo.png in the repo root (optional)
LOGO_URL  = st.secrets.get("LOGO_URL", None)  # or set in secrets if you prefer a hosted logo

# ------------- Streamlit basics --------------------------------
st.set_page_config(
    page_title="Atmosphere Society Business Directory",
    page_icon="🏡",
    layout="wide",
)

# Global CSS (brand look)
st.markdown(
    f"""
    <style>
      .stApp {{
        background: {PAGE_BG};
        color: #FFFFFF;
      }}
      section[data-testid="stSidebar"] {{
        background: {CARD_BG};
      }}
      .atm-banner {{
        background: {BANNER_GRADIENT};
        padding: 18px 22px;
        border-radius: 18px;
        box-shadow: 0 10px 35px rgba(0,0,0,.35);
        margin-bottom: 18px;
      }}
      .atm-card {{
        background: {CARD_BG};
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(255,255,255,.08);
      }}
      .atm-pill {{
        background: rgba(255,255,255,.1);
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
      }}
      .atm-title {{
        font-weight: 700;
        font-size: 42px;
        letter-spacing: .2px;
      }}
      .atm-subt {{
        opacity: .9;
        font-size: 14px;
      }}
      .atm-btn {{
        background: {PRIMARY};
        color: white !important;
        padding: 8px 14px;
        border-radius: 8px;
        text-decoration: none;
        border: none;
      }}
      .small-dim {{
        opacity: .7;
        font-size: 12px;
      }}
      .atm-grid {{
        display: grid;
        gap: 16px;
      }}
      @media (min-width: 1100px) {{
        .atm-grid.cols-3 {{ grid-template-columns: repeat(3, 1fr); }}
      }}
      @media (max-width: 1099px) {{
        .atm-grid.cols-3 {{ grid-template-columns: repeat(1, 1fr); }}
      }}
      .atm-logo {{
        height: 42px;
        margin-right: 8px;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# Banner with optional logo
col_logo, col_title = st.columns([1, 6])
with col_logo:
    try:
        if LOGO_URL:
            st.image(LOGO_URL, use_container_width=False, caption=None)
        else:
            st.image(LOGO_PATH, use_container_width=False, caption=None)
    except Exception:
        pass

with col_title:
    st.markdown(
        f"""
        <div class="atm-banner">
          <div class="atm-title">Atmosphere Society Business Directory</div>
          <div class="atm-subt">Phase 1 & 2 · Simple, free, community-first</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------- Admin login (username + password) ---------------

APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

def login_ui() -> bool:
    """Return True if authenticated (admin), else False."""
    # Keep auth in session
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    if st.session_state.is_admin:
        return True

    with st.expander("Admin login", expanded=False):
        u = st.text_input("Username", key="u_name", placeholder="Admin username")
        p = st.text_input("Password", key="p_word", type="password", placeholder="Admin password")
        if st.button("Sign in", type="primary"):
            if u.strip() == APP_USERNAME and p == APP_PASSWORD:
                st.session_state.is_admin = True
                st.success("Logged in as Admin.")
            else:
                st.error("Incorrect username or password.")
                time.sleep(1)
    return st.session_state.is_admin

# ------------- Google Sheets connection ------------------------

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

# Use the spreadsheet you already shared with the service account
SHEET_URL = st.secrets.get(
    "SHEET_URL",
    # Fallback – paste your Sheet URL here if you prefer hard-coding:
    "https://docs.google.com/spreadsheets/d/1SWVjrtC8qh9fXFhrcXbc_6cgNS39tc87vvPz1PCaeFY/edit#gid=0",
)

@st.cache_resource(show_spinner=False)
def open_spreadsheet(url: str):
    return gc.open_by_url(url)

def ensure_worksheet(sh, title: str, headers: List[str]) -> gspread.Worksheet:
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
        ws.append_row(headers)
    # If empty, put headers
    values = ws.get_all_values()
    if not values:
        ws.append_row(headers)
    return ws

def ws_to_df(ws: gspread.Worksheet) -> pd.DataFrame:
    vals = ws.get_all_values()
    if not vals:
        return pd.DataFrame()
    if len(vals) == 1:
        return pd.DataFrame(columns=vals[0])
    return pd.DataFrame(vals[1:], columns=vals[0])

def append_row(ws: gspread.Worksheet, row: List[str]):
    ws.append_row(row)

# ------------- Prepare workbook & tabs -------------------------

try:
    sh = open_spreadsheet(SHEET_URL)

    # Directory
    DIR_HEADERS = [
        "Submitted_At","Approved","Phase","Wing","Flat_No","Resident_Name","Email","Phone",
        "Business_Name","Category","Subcategory","Service_Type",
        "Short_Description","Detailed_Description"
    ]
    ws_dir = ensure_worksheet(sh, "Business_Listings", DIR_HEADERS)

    # Vendors (vicinity)
    VEN_HEADERS = [
        "Submitted_At","Approved","Vendor_Name","Contact","Phone","Category","Subcategory","Location",
        "Short_Description","Detailed_Description"
    ]
    ws_vendors = ensure_worksheet(sh, "Vicinity_Vendors", VEN_HEADERS)

    # Showcase wall (photos/videos marketing)
    SHOW_HEADERS = [
        "Submitted_At","Approved","Title","Type","URL","Posted_By","Notes"
    ]
    ws_show = ensure_worksheet(sh, "Showcase", SHOW_HEADERS)

except SpreadsheetNotFound as e:
    st.error("Could not open the spreadsheet by URL. Check your SHEET_URL secret or share settings.")
    st.stop()

# ------------- Helpers for Drive links (for videos/images) -----

def extract_drive_file_id(url: str) -> str | None:
    """
    Returns a file ID from common Google Drive share links.
    """
    patterns = [
        r"https?://drive\.google\.com/file/d/([^/]+)/",    # /file/d/<id>/
        r"https?://drive\.google\.com/open\?id=([^&]+)",   # open?id=<id>
        r"https?://drive\.google\.com/uc\?id=([^&]+)",     # uc?id=<id>
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None

def to_direct_image(url: str) -> str:
    """
    Try to convert a Drive link to a direct image link (works for images).
    Otherwise return the URL as-is.
    """
    fid = extract_drive_file_id(url)
    if fid:
        return f"https://drive.google.com/uc?export=view&id={fid}"
    return url

def to_drive_preview(url: str) -> str:
    """
    Convert to Drive preview (good for iframed video playback).
    """
    fid = extract_drive_file_id(url)
    if fid:
        return f"https://drive.google.com/file/d/{fid}/preview"
    return url

# ------------- UI: Tabs ---------------------------------------

TABS = st.tabs(["📖 Directory", "📝 Submit", "🏪 Vicinity Vendors", "🎞️ Showcase Wall", "🛠️ Admin"])

# ----------------- Directory ----------------------------------
with TABS[0]:
    st.subheader("Resident Business Listings")

    df_dir = ws_to_df(ws_dir)
    if df_dir.empty:
        st.info("No directory data yet. Add from **Submit** or via **Admin**.")
    else:
        # Filters
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            phase = st.selectbox("Phase", ["All"] + sorted(df_dir["Phase"].dropna().unique().tolist()))
        with col2:
            cat = st.selectbox("Category", ["All"] + sorted(df_dir["Category"].dropna().unique().tolist()))
        with col3:
            svc = st.selectbox("Service Type", ["All"] + sorted(df_dir["Service_Type"].dropna().unique().tolist()))
        with col4:
            txt = st.text_input("Search name or description")

        # show only Approved == "Yes"
        mask = (df_dir["Approved"].str.strip().str.lower() == "yes")
        if phase != "All":
            mask &= (df_dir["Phase"] == phase)
        if cat != "All":
            mask &= (df_dir["Category"] == cat)
        if svc != "All":
            mask &= (df_dir["Service_Type"] == svc)
        if txt:
            txt_low = txt.lower()
            mask &= (
                df_dir["Business_Name"].str.lower().str.contains(txt_low, na=False) |
                df_dir["Short_Description"].str.lower().str.contains(txt_low, na=False) |
                df_dir["Detailed_Description"].str.lower().str.contains(txt_low, na=False)
            )

        view = df_dir[mask].copy()
        if view.empty:
            st.warning("No approved listings match your filters.")
        else:
            st.dataframe(view, use_container_width=True)

# ----------------- Submit -------------------------------------
with TABS[1]:
    st.subheader("Submit Your Business")

    with st.form("submit_business"):
        colA, colB, colC = st.columns(3)
        with colA:
            phase = st.selectbox("Phase", ["Atmosphere 1", "Atmosphere 2"])
            wing = st.text_input("Wing")
            flat = st.text_input("Flat No (e.g., 1203)")
        with colB:
            name = st.text_input("Resident Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
        with colC:
            bname = st.text_input("Business Name")
            category = st.text_input("Category")
            subcategory = st.text_input("Subcategory")

        svc_type = st.text_input("Service Type")
        short_d = st.text_area("Short Description", max_chars=120)
        detail_d = st.text_area("Detailed Description")

        submitted = st.form_submit_button("Send for Approval")
        if submitted:
            append_row(ws_dir, [
                time.strftime("%Y-%m-%d %H:%M:%S"),
                "No",  # not approved by default
                phase, wing, flat, name, email, phone,
                bname, category, subcategory, svc_type, short_d, detail_d
            ])
            st.success("Submitted! An admin will review and approve.")

# ----------------- Vicinity Vendors ---------------------------
with TABS[2]:
    st.subheader("Vicinity Vendors")

    df_vendors = ws_to_df(ws_vendors)
    if df_vendors.empty:
        st.info("No vendors yet.")
    else:
        mask = (df_vendors["Approved"].str.strip().str.lower() == "yes")
        st.dataframe(df_vendors[mask], use_container_width=True)

# ----------------- Showcase Wall ------------------------------
with TABS[3]:
    st.subheader("Showcase Wall – Photos & 10s Videos")

    df_show = ws_to_df(ws_show)

    # View Area – only approved
    if df_show.empty:
        st.info("Nothing here yet. Admin can post items in the **Admin** tab.")
    else:
        approved = df_show[df_show["Approved"].str.strip().str.lower() == "yes"].copy()
        if approved.empty:
            st.info("No approved showcase items yet.")
        else:
            # Cards
            st.markdown('<div class="atm-grid cols-3">', unsafe_allow_html=True)

            for _, row in approved.iterrows():
                title = row.get("Title", "")
                typ   = (row.get("Type", "") or "").lower()
                url   = row.get("URL", "")
                by    = row.get("Posted_By", "")
                notes = row.get("Notes", "")

                st.markdown('<div class="atm-card">', unsafe_allow_html=True)
                if "video" in typ:
                    drive_preview = to_drive_preview(url)
                    # Use iframe so Drive preview plays reliably
                    st.components.v1.iframe(drive_preview, height=260, scrolling=False)
                else:
                    st.image(to_direct_image(url), use_container_width=True)

                st.markdown(f"**{title}**  \n<span class='small-dim'>by {by}</span>", unsafe_allow_html=True)
                if notes:
                    st.caption(notes)
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

# ----------------- Admin --------------------------------------
with TABS[4]:
    st.subheader("Admin")

    if not login_ui():
        st.info("Log in above to access admin actions.")
        st.stop()

    st.success("Admin mode enabled.")

    tabA, tabB = st.tabs(["Approve / Manage", "Post to Showcase"])

    # --- Approvals for Directory & Vendors & Showcase
    with tabA:
        st.markdown("### Pending approvals")

        df_dir_full = ws_to_df(ws_dir)
        df_v_full   = ws_to_df(ws_vendors)
        df_s_full   = ws_to_df(ws_show)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Business Listings**")
            if df_dir_full.empty:
                st.caption("No rows yet.")
            else:
                pend = df_dir_full[df_dir_full["Approved"].str.lower() != "yes"]
                st.dataframe(pend, use_container_width=True, height=280)

        with col2:
            st.markdown("**Vicinity Vendors**")
            if df_v_full.empty:
                st.caption("No rows yet.")
            else:
                pend = df_v_full[df_v_full["Approved"].str.lower() != "yes"]
                st.dataframe(pend, use_container_width=True, height=280)

        with col3:
            st.markdown("**Showcase**")
            if df_s_full.empty:
                st.caption("No rows yet.")
            else:
                pend = df_s_full[df_s_full["Approved"].str.lower() != "yes"]
                st.dataframe(pend, use_container_width=True, height=280)

        st.info("To approve, you can edit the Google Sheet column **Approved** to `Yes`. Refresh the app after saving.")

    # --- Post to Showcase (Admin-only uploader by link)
    with tabB:
        st.markdown("### Add a new Showcase item (Admin only)")
        st.caption("Upload is by sharing a **public link** (e.g., Google Drive or direct https). "
                   "For Drive, set the file to *Anyone with the link can view*.")
        with st.form("showcase_add"):
            title = st.text_input("Title")
            typ   = st.selectbox("Type", ["Image", "Video (<=10s)"])
            url   = st.text_input("Public URL (Google Drive or direct https)")
            notes = st.text_area("Notes (optional)")
            by    = st.text_input("Posted By", value="Admin")

            submitted = st.form_submit_button("Post to Showcase")
            if submitted:
                if not title or not url:
                    st.error("Title and URL are required.")
                else:
                    append_row(ws_show, [
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        "Yes",      # Admin posting => approved
                        title,
                        typ.lower(),
                        url,
                        by,
                        notes,
                    ])
                    st.success("Posted! It is now visible on the Showcase Wall.")


