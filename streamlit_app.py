# ──────────────────────────────────────────────────────────────────────────────
# Atmosphere Society Directory - BRANDED + SHOWCASE
# ──────────────────────────────────────────────────────────────────────────────

import os
import re
import time
from datetime import datetime
from typing import List, Optional

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# Optional: Google Drive for file uploads to Showcase
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    DRIVE_AVAILABLE = True
except Exception:
    DRIVE_AVAILABLE = False

# ---------- Page ----------
st.set_page_config(
    page_title="Atmosphere Society Business Directory",
    page_icon="🏡",
    layout="wide",
)

# ---------- BRAND COLORS (Atmosphere blues) ----------
BRAND_PRIMARY   = "#1a8ed1"   # mid sky blue
BRAND_PRIMARY_2 = "#0e78b4"   # deeper
BRAND_ACCENT    = "#7cc8ff"   # light accent
CARD_BG         = "#0f172a"   # slate-900
PAGE_BG         = "#07111f"   # dark blue
TEXT_SUB        = "#cbd5e1"

# ---------- STYLE ----------
st.markdown(
    f"""
    <style>
      .stApp {{
        background: radial-gradient(1300px 600px at 15% 0%, #0a1d34 0%, {PAGE_BG} 40%, #050d1a 100%);
      }}
      .atm-top {{
        margin: 6px 0 22px 0;
        border-radius: 18px;
        padding: 16px 20px;
        background: linear-gradient(90deg, {BRAND_PRIMARY_2}, {BRAND_PRIMARY});
        color: #fff;
        display: flex;
        align-items: center;
        gap: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,.35);
      }}
      .atm-title {{
        margin: 0;
        font-size: 1.8rem;
        line-height: 1.2;
        font-weight: 800;
      }}
      .atm-sub {{
        opacity: .9;
        font-size: .95rem;
      }}
      .atm-card {{
        background: {CARD_BG};
        border-radius: 16px;
        padding: 16px;
        border: 1px solid rgba(255,255,255,.06);
      }}
      .atm-card h3 {{
        color: #fff; margin: 0 0 4px 0; font-size: 1.1rem;
      }}
      .atm-small {{
        color: {TEXT_SUB}; font-size: .9rem;
      }}
      .stButton>button.atm-approve {{
        background: #22c55e; color: #0b0f1a; border: 0; font-weight: 700;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- LOGO ----------
def render_header():
    logo_path = "logo.png"
    logo_url = st.secrets.get("LOGO_URL", "")
    have_file = os.path.exists(logo_path)
    col1, col2 = st.columns([0.1, 0.9])
    with st.container():
        st.markdown('<div class="atm-top">', unsafe_allow_html=True)
        if have_file:
            col1.image(logo_path, width=56)
        elif logo_url:
            col1.image(logo_url, width=56)
        else:
            col1.markdown("🏡", help="Upload logo.png to the repo for a branded header.")
        col2.markdown('<div class="atm-title">Atmosphere Society Business Directory</div>', unsafe_allow_html=True)
        col2.markdown('<div class="atm-sub">Discover resident businesses • Submit listings • Showcase products</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

render_header()

# ---------- CONFIG (EDIT URL ONLY if you change sheet) ----------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SWVjrtC8qh9fXFhrcXbc_6cgNS39tc87vvPz1PCaeFY/edit?gid=0#gid=0"

DIRECTORY_SHEET = "Business_Listings"
VENDORS_SHEET   = "Vicinity_Vendors"
SHOWCASE_SHEET  = "Showcase"           # <-- new

EXPECTED_COLUMNS: List[str] = [
    "Approved","Phase","Wing","Flat_No",
    "Resident_Name","Phone","Email",
    "Business_Name","Category","Subcategory","Service_Type",
    "Short_Description","Detailed_Description",
    "Website","Instagram","Address"
]

SHOWCASE_COLUMNS: List[str] = [
    "Approved","Title","Description","Media_Type","Image_URL","Video_URL","Uploader","Created_At"
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
    return gspread.authorize(creds), creds

gc, creds = get_gspread_client()

# ---------- Sheet helpers ----------
def open_sheet_by_url(url: str):
    try:
        return gc.open_by_url(url)
    except SpreadsheetNotFound as e:
        st.error("Could not open the spreadsheet by URL. Double-check the URL.")
        st.code(str(e)); st.stop()

def get_or_create_ws(sh, tab_name: str, header: List[str]):
    names = [ws.title for ws in sh.worksheets()]
    if tab_name in names:
        return sh.worksheet(tab_name)
    ws = sh.add_worksheet(title=tab_name, rows=2000, cols=max(len(header), 20))
    ws.update([header])
    return ws

def ws_to_df(ws, header_cols: List[str]) -> pd.DataFrame:
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame(columns=header_cols)
    header, body = rows[0], rows[1:]
    df = pd.DataFrame(body, columns=header)
    df = df.replace("", pd.NA).dropna(how="all")
    for col in header_cols:
        if col not in df.columns: df[col] = ""
    return df

def append_row(ws, cols: List[str], data: dict):
    ws.append_row([data.get(c, "") for c in cols], value_input_option="USER_ENTERED")

def approve_row(ws, row_idx: int, col_name="Approved"):
    header = ws.row_values(1)
    try:
        col = header.index(col_name) + 1
    except ValueError:
        return
    ws.update_cell(row_idx, col, "Yes")

# ---------- Drive uploader (optional) ----------
@st.cache_resource(show_spinner=False)
def get_drive():
    if not DRIVE_AVAILABLE:
        return None
    try:
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None

DRIVE = get_drive()
SHOWCASE_FOLDER = st.secrets.get("SHOWCASE_DRIVE_FOLDER", "")

def upload_to_drive(local_path: str, file_name: str) -> Optional[str]:
    """Uploads to the showcase folder; returns a public file link (view)."""
    if not DRIVE or not SHOWCASE_FOLDER:
        return None
    media = MediaFileUpload(local_path, resumable=False)
    file_meta = {"name": file_name, "parents": [SHOWCASE_FOLDER]}
    file = DRIVE.files().create(body=file_meta, media_body=media, fields="id").execute()
    file_id = file.get("id")
    # Make it viewable by link
    try:
        DRIVE.permissions().create(fileId=file_id, body={"role":"reader", "type":"anyone"}).execute()
    except Exception:
        pass
    return f"https://drive.google.com/uc?id={file_id}"

# ---------- Load sheets ----------
sh = open_sheet_by_url(SHEET_URL)
ws_dir = get_or_create_ws(sh, DIRECTORY_SHEET, EXPECTED_COLUMNS)
ws_vnd = get_or_create_ws(sh, VENDORS_SHEET,   EXPECTED_COLUMNS)
ws_show = get_or_create_ws(sh, SHOWCASE_SHEET, SHOWCASE_COLUMNS)

df_dir = ws_to_df(ws_dir, EXPECTED_COLUMNS)
df_vnd = ws_to_df(ws_vnd, EXPECTED_COLUMNS)
df_show = ws_to_df(ws_show, SHOWCASE_COLUMNS)

# ---------- Util ----------
def nice(s): return (s or "").strip()

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

def render_cards(df: pd.DataFrame, empty_msg="Nothing yet."):
    if df.empty:
        st.info(empty_msg); return
    cols = st.columns([1,1,1], gap="large")
    i = 0
    for _, r in df.iterrows():
        with cols[i % 3]:
            st.markdown('<div class="atm-card">', unsafe_allow_html=True)
            st.markdown(f"<h3>{nice(r.get('Business_Name') or r.get('Title') or 'Untitled')}</h3>", unsafe_allow_html=True)
            small = []
            if r.get("Category"): small.append(nice(r["Category"]))
            if r.get("Service_Type"): small.append(nice(r["Service_Type"]))
            if r.get("Resident_Name"): small.append(nice(r["Resident_Name"]))
            if small:
                st.markdown(f'<div class="atm-small">{" • ".join(small)}</div>', unsafe_allow_html=True)

            # For Showcase: media
            if "Media_Type" in r.index:
                if nice(r["Media_Type"]).lower()=="image" and nice(r["Image_URL"]):
                    st.image(nice(r["Image_URL"]), use_container_width=True)
                elif nice(r["Media_Type"]).lower()=="video":
                    if nice(r["Video_URL"]):
                        st.video(nice(r["Video_URL"]))
                if nice(r.get("Description","")):
                    st.caption(r["Description"])
            else:
                if nice(r.get("Short_Description","")):
                    st.caption(r["Short_Description"])

            links = []
            for label, key in [("Website","Website"),("Instagram","Instagram"),("Email","Email"),("Phone","Phone")]:
                v = nice(r.get(key,""))
                if not v: continue
                if label in ("Website","Instagram"):
                    links.append(f'[{label}]({v})')
                else:
                    links.append(f'{label}: {v}')
            if links: st.markdown(" • ".join(links))

            st.markdown("</div>", unsafe_allow_html=True)
        i += 1

# ---------- Tabs ----------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Browse Directory", "Submit Listing", "Vicinity Vendors", "Showcase (Free Wall)", "Admin"
])

# ── 1) Browse Directory
with tab1:
    st.subheader("Browse resident businesses")
    approved = df_dir[df_dir["Approved"].str.strip().str.lower()=="yes"]
    phases = ["All"] + sorted([p for p in approved["Phase"].dropna().unique() if p])
    cats   = ["All"] + sorted([c for c in approved["Category"].dropna().unique() if c])
    svcs   = ["All"] + sorted([s for s in approved["Service_Type"].dropna().unique() if s])

    c1,c2,c3,c4 = st.columns([1,1,1,2])
    phase = c1.selectbox("Phase", phases, index=0)
    cat   = c2.selectbox("Category", cats, index=0)
    svc   = c3.selectbox("Service Type", svcs, index=0)
    q     = c4.text_input("Search", placeholder="name, service, keyword...")

    show = filter_df(approved, phase, cat, svc, q)
    render_cards(show, "No approved listings yet.")

# ── 2) Submit Listing
with tab2:
    st.subheader("Submit your business")
    with st.form("submit_form", clear_on_submit=True):
        phase = st.selectbox("Phase", ["Atmosphere 1","Atmosphere 2"])
        wing  = st.selectbox("Wing", list("ABCDEFGHIJ"))
        flat  = st.text_input("Flat No (e.g., 1203)")
        rname = st.text_input("Resident Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        c     = st.text_input("Category")
        sc    = st.text_input("Subcategory")
        stype = st.text_input("Service Type")
        bname = st.text_input("Business Name*")
        short = st.text_area("Short Description (one line)")
        detail= st.text_area("Detailed Description")
        web   = st.text_input("Website URL")
        ig    = st.text_input("Instagram URL")
        addr  = st.text_area("Address")

        submitted = st.form_submit_button("Submit")
        if submitted:
            if not bname.strip():
                st.warning("Please provide Business Name.")
            else:
                payload = {
                    "Approved":"No","Phase":phase,"Wing":wing,"Flat_No":flat,
                    "Resident_Name":rname,"Phone":phone,"Email":email,
                    "Business_Name":bname,"Category":c,"Subcategory":sc,"Service_Type":stype,
                    "Short_Description":short,"Detailed_Description":detail,
                    "Website":web,"Instagram":ig,"Address":addr
                }
                append_row(ws_dir, EXPECTED_COLUMNS, payload)
                st.success("Submitted! Your listing will appear after admin approval.")

# ── 3) Vicinity Vendors
with tab3:
    st.subheader("Vicinity Vendors (nearby)")
    approved_v = df_vnd[df_vnd["Approved"].str.strip().str.lower()=="yes"]
    cats_v = ["All"] + sorted([c for c in approved_v["Category"].dropna().unique() if c])
    svc_v  = ["All"] + sorted([s for s in approved_v["Service_Type"].dropna().unique() if s])
    c1,c2,c3 = st.columns([1,1,2])
    catv = c1.selectbox("Category", cats_v, index=0, key="v_cat")
    svcv = c2.selectbox("Service Type", svc_v, index=0, key="v_svc")
    qv   = c3.text_input("Search", key="v_q")
    show_v = filter_df(approved_v, "All", catv, svcv, qv)
    render_cards(show_v, "No approved vendors yet.")

    st.divider()
    with st.expander("Suggest a new vendor"):
        with st.form("vendor_form", clear_on_submit=True):
            bname = st.text_input("Vendor / Shop Name*")
            c     = st.text_input("Category")
            sc    = st.text_input("Subcategory")
            stype = st.text_input("Service Type")
            short = st.text_area("Short Description")
            contact = st.text_input("Phone / Email")
            web   = st.text_input("Website URL")
            ig    = st.text_input("Instagram URL")
            addr  = st.text_area("Address / Exact location")
            v_submit = st.form_submit_button("Suggest Vendor")
            if v_submit:
                if not bname.strip():
                    st.warning("Please provide a vendor name.")
                else:
                    payload = {
                        "Approved":"No","Phase":"","Wing":"","Flat_No":"",
                        "Resident_Name":"","Phone":contact,"Email":"",
                        "Business_Name":bname,"Category":c,"Subcategory":sc,"Service_Type":stype,
                        "Short_Description":short,"Detailed_Description":"",
                        "Website":web,"Instagram":ig,"Address":addr
                    }
                    append_row(ws_vnd, EXPECTED_COLUMNS, payload)
                    st.success("Thank you! Vendor will appear after admin approval.")

# ── 4) Showcase (Free Wall)
with tab4:
    st.subheader("Showcase (Free Wall) — images & 10s videos")
    st.caption("Post product promos here. Paste a link (YouTube / Drive / Instagram) or upload a file.")
    approved_show = df_show[df_show["Approved"].str.strip().str.lower()=="yes"]

    # Gallery
    cols = st.columns([1,1,1], gap="large")
    if approved_show.empty:
        st.info("No approved showcase posts yet.")
    else:
        i = 0
        for _, r in approved_show.iterrows():
            with cols[i % 3]:
                st.markdown('<div class="atm-card">', unsafe_allow_html=True)
                st.markdown(f"<h3>{nice(r['Title']) or 'Untitled'}</h3>", unsafe_allow_html=True)
                if nice(r["Media_Type"]).lower()=="image" and nice(r["Image_URL"]):
                    st.image(nice(r["Image_URL"]), use_container_width=True)
                elif nice(r["Media_Type"]).lower()=="video" and nice(r["Video_URL"]):
                    st.video(nice(r["Video_URL"]))
                if nice(r["Description"]):
                    st.caption(r["Description"])
                if nice(r["Uploader"]):
                    st.caption(f"By: {r['Uploader']}")
                st.markdown("</div>", unsafe_allow_html=True)
            i += 1

    st.divider()
    # Submit to showcase
    with st.expander("Post to Showcase"):
        c1, c2 = st.columns(2)
        with c1:
            title = st.text_input("Title*")
            mtype = st.selectbox("Media Type", ["Image", "Video"])
            desc  = st.text_area("Short description")
            who   = st.text_input("Your name / flat (optional)")
        with c2:
            link  = st.text_input("Paste a link (YouTube / Instagram / Google Drive / image URL)")
            upload = st.file_uploader("Or upload a file (image / mp4 up to ~10s)", type=["png","jpg","jpeg","gif","mp4"])

        if st.button("Submit to Showcase"):
            if not title.strip():
                st.warning("Please add a title.")
            else:
                image_url, video_url = "", ""
                # Prefer uploaded file if provided and Drive configured
                if upload is not None:
                    tmp_path = f"/tmp/{upload.name}"
                    with open(tmp_path, "wb") as f:
                        f.write(upload.read())
                    drv_url = upload_to_drive(tmp_path, upload.name)
                    if drv_url:
                        if mtype.lower()=="image":
                            image_url = drv_url
                        else:
                            video_url = drv_url
                    else:
                        st.info("Upload via Drive not configured; using your pasted link (if any).")
                # Fallback to pasted link
                if not image_url and not video_url and link.strip():
                    if mtype.lower()=="image":
                        image_url = link.strip()
                    else:
                        video_url = link.strip()

                if (mtype.lower()=="image" and not image_url) or (mtype.lower()=="video" and not video_url):
                    st.warning("Please provide a valid link or enable Drive uploads (see instructions).")
                else:
                    payload = {
                        "Approved":"No",
                        "Title":title.strip(),
                        "Description":desc.strip(),
                        "Media_Type":mtype,
                        "Image_URL":image_url,
                        "Video_URL":video_url,
                        "Uploader":who.strip(),
                        "Created_At": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    append_row(ws_show, SHOWCASE_COLUMNS, payload)
                    st.success("Posted! It will appear once admin approves.")

# ── 5) Admin
with tab5:
    st.subheader("Admin")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u == st.secrets["APP_USERNAME"] and p == st.secrets["APP_PASSWORD"]:
            st.session_state["_is_admin"] = True
            st.success("Welcome, admin!")
            time.sleep(.5); st.experimental_rerun()
        else:
            st.error("Invalid credentials.")

    if st.session_state.get("_is_admin"):
        st.success("Logged in as admin.")
        colA, colB, colC = st.columns(3)

        with colA:
            st.markdown("**Resident listings — pending**")
            pending = df_dir[df_dir["Approved"].str.strip().str.lower()!="yes"]
            if pending.empty: st.info("None")
            for idx, r in pending.iterrows():
                with st.container(border=True):
                    st.write(f"**{nice(r['Business_Name'])}** — {nice(r['Category'])}/{nice(r['Service_Type'])}")
                    st.caption(nice(r["Short_Description"]))
                    if st.button("Approve", key=f"a_dir_{idx}", help="Make visible"):
                        approve_row(ws_dir, idx + 2)
                        st.success("Approved."); time.sleep(.3); st.experimental_rerun()

        with colB:
            st.markdown("**Vicinity vendors — pending**")
            pending_v = df_vnd[df_vnd["Approved"].str.strip().str.lower()!="yes"]
            if pending_v.empty: st.info("None")
            for idx, r in pending_v.iterrows():
                with st.container(border=True):
                    st.write(f"**{nice(r['Business_Name'])}** — {nice(r['Category'])}/{nice(r['Service_Type'])}")
                    st.caption(nice(r["Short_Description"]))
                    if st.button("Approve", key=f"a_v_{idx}"):
                        approve_row(ws_vnd, idx + 2)
                        st.success("Approved."); time.sleep(.3); st.experimental_rerun()

        with colC:
            st.markdown("**Showcase posts — pending**")
            pending_s = df_show[df_show["Approved"].str.strip().str.lower()!="yes"]
            if pending_s.empty: st.info("None")
            for idx, r in pending_s.iterrows():
                with st.container(border=True):
                    st.write(f"**{nice(r['Title'])}** — {nice(r['Media_Type'])}")
                    st.caption(nice(r["Description"]))
                    if st.button("Approve", key=f"a_s_{idx}"):
                        approve_row(ws_show, idx + 2)
                        st.success("Approved."); time.sleep(.3); st.experimental_rerun()

