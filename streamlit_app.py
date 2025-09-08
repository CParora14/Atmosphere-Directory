# ================== TOP SECTION (imports + theme + backdrop) ==================
from __future__ import annotations
import uuid, datetime as dt
from typing import Optional, Dict, List

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# -------------------- BRAND / THEME --------------------
PRIMARY   = "#18B8CB"
PRIMARY_2 = "#6BC6FF"
INK       = "#0C2AAA"
CARD_BG   = "#0E1C2B"
PAGE_BG   = "#0A1522"

# Logo / backdrop come from Streamlit Secrets so you can change them without editing code
# In Streamlit Cloud: App → Settings → Secrets
#   LOGO_URL = "https://..."
#   BACKDROP_URL = "https://raw.githubusercontent.com/.../Wadhwaatmosphere1%20Image.webp"
LOGO_URL     = st.secrets.get("LOGO_URL", "").strip()
BACKDROP_URL = st.secrets.get("BACKDROP_URL", "").strip()

st.set_page_config(
    page_title="Atmosphere Society — Community Hub",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------- RELIABLE FULL-SCREEN BACKDROP --------------------
# We render the background image behind the app using a fixed ::before layer.
# This is more reliable than styling the container background directly.
bg_url = BACKDROP_URL  # alias

st.markdown(f"""
<style>
/* Reset any previous backgrounds so we fully control the canvas */
html, body, .stApp, .stApp > div[data-testid="stAppViewContainer"] {{
  background: transparent !important;
}}

/* Full-screen image behind everything with a subtle dark gradient on top */
.stApp::before {{
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;  /* keep it behind all content */
  background-image:
    linear-gradient(180deg, rgba(0,0,0,0.25), rgba(0,0,0,0.45)) ,
    url('{bg_url}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}

/* Global typography/colors and tabs */
:root {{
  --brand:{PRIMARY}; --brand2:{PRIMARY_2}; --ink:{INK}; --card:{CARD_BG}; --page:{PAGE_BG};
}}
.block-container {{ padding-top:1rem; padding-bottom:2rem; max-width:1200px; }}
[data-testid="stHeader"] {{ background: transparent; }}

.stTabs [data-baseweb="tab"] {{ color:#EAF2FA; font-weight:600; }}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(90deg, var(--brand), var(--brand2))!important;
  color:#001018!important; border-radius:10px;
}}

.banner {{
  width:100%; padding:18px 22px; border-radius:18px;
  background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_2} 100%);
  color:#001018; box-shadow:0 10px 30px rgba(0,0,0,.25);
}}
.card {{
  background:var(--card); border-radius:16px; padding:16px 18px;
  border:1px solid rgba(255,255,255,.06)
}}
.badge {{
  padding:2px 8px; border-radius:100px; font-size:12px;
  background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.08)
}}
.small-dim {{ color:#b9c8d8; font-size:12px; }}
hr {{ border: none; border-top: 1px solid rgba(255,255,255,.15); margin: 0.6rem 0 1rem; }}
</style>
""", unsafe_allow_html=True)

# Optional little line so you can verify the image URL is actually set
st.caption(f"Backdrop URL: {bg_url or '(not set — add BACKDROP_URL in Secrets)'}")

# -------------------- SMALL UTILS USED LATER --------------------
TRUE_LIKE = {"true", "yes", "y", "1"}

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def clear_cache():
    try:
        st.cache_data.clear()
    except Exception:
        pass
# ================== END TOP SECTION ===========================================

# -------------------- SECRETS --------------------
APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
SHEET_URL    = st.secrets.get("SHEET_URL", "")

# -------------------- GOOGLE AUTH + OPEN SHEET --------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource(show_spinner=False)
def _gc():
    sa_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def _open_sheet():
    if not SHEET_URL:
        st.error("SHEET_URL not set in Secrets. Add it in App → Settings → Secrets.")
        st.stop()
    return _gc().open_by_url(SHEET_URL)

with st.spinner("Connecting to Google Sheets…"):
    sh = _open_sheet()

# -------------------- REQUIRED HEADERS --------------------
MEM_HEADERS = ["Member_ID","Submitted_At","Approved","Resident_Type","Phase","Wing",
               "Flat_No","Name","Email","Phone"]
DIR_HEADERS = ["Listing_ID","Submitted_At","Approved","Member_Email","Resident_Type","Phase","Wing","Flat_No",
               "Business_Name","Category","Subcategory","Service_Type",
               "Short_Description","Detailed_Description",
               "Image_URL_1","Image_URL_2","Image_URL_3","Duration_Days","Expires_On"]
VEN_HEADERS = ["Vendor_ID","Submitted_At","Approved","Member_Email","Vendor_Name","Contact",
               "Phone","Address","Category","Short_Description",
               "Image_URL_1","Image_URL_2","Image_URL_3","Duration_Days","Expires_On"]
SHOW_HEADERS= ["Show_ID","Submitted_At","Approved","Title","Type","URL","Posted_By","Notes"]
RATE_HEADERS= ["When","Type","Target_ID","Stars","Comment","Rater_Email"]
SUPP_HEADERS= ["Ticket_ID","When","Email","Subject","Message","Status"]

# -------------------- CATEGORY → SUBCATEGORY --------------------
CATEGORIES: Dict[str, List[str]] = {
    "Food & Catering": ["Home Tiffin","Catering","Bakery","Snacks","Chaat","Sweets","Healthy Meals","Other"],
    "Education": ["Tuition","Coaching","Music","Dance","Languages","Coding","Art & Craft","Other"],
    "Wellness": ["Yoga","Fitness Trainer","Physiotherapy","Massage","Salon/Beautician","Ayurveda/Homeopathy","Other"],
    "Home Services": ["Electrician","Plumber","Carpenter","AC Service","Cleaning","Pest Control","Painting","Other"],
    "Events": ["Decoration","Photography/Videography","Make-up","Anchoring","Sound/Lighting","Party Planner","Other"],
    "Retail": ["Clothing","Accessories","Footwear","Gifts","Stationery","Home Decor","Groceries","Other"],
    "Tech": ["Laptop Repair","Mobile Repair","Networking","Software Services","Web/Apps","CCTV/Smart Home","Other"],
    "Finance & Legal": ["CA/Tax","Loans/Insurance","Legal/Notary","Accounting","Other"],
    "Pets": ["Grooming","Boarding","Training","Supplies","Other"],
    "Transport": ["Driver on Call","Cab Service","Packers & Movers","Courier","Other"],
    "Other": ["Other"]
}

# -------------------- ENSURE WORKSHEETS & HEADERS (with retry/backoff) --------------------
# -------------------- ENSURE WORKSHEETS & HEADERS (resilient) --------------------
import time
from random import random

IS_EDIT_MODE = str(st.secrets.get("EDIT_MODE", "")).strip().lower() == "true"

def _retry(call, *args, **kwargs):
    """Retry helper with exponential backoff for transient Google errors."""
    last = None
    for attempt in range(5):  # 0..4
        try:
            return call(*args, **kwargs)
        except APIError as e:
            last = e
            # backoff: 0.3, 0.6, 1.2, 2.4, 4.8 (+ jitter)
            sleep_s = (0.3 * (2 ** attempt)) + (random() * 0.2)
            time.sleep(sleep_s)
    raise last  # all retries failed

def _ensure_headers(ws, headers):
    """Write headers only if first row is empty; ignore errors."""
    try:
        row1 = _retry(ws.row_values, 1)
        if not row1:
            _retry(ws.update, "A1", [headers])
    except APIError:
        pass

def _get_or_create_worksheets(sh, required: list[tuple[str, list[str]]]):
    """
    Do a single metadata fetch (sh.worksheets()) and then create any missing tabs.
    Returns dict: title -> Worksheet
    """
    title_to_ws = {}
    try:
        existing = {ws.title: ws for ws in _retry(sh.worksheets)}
    except APIError as e:
        # If even listing fails, show a soft message and continue to EDIT mode
        st.warning("Google Sheets not reachable right now. Running in read-only UI.")
        raise e

    for title, headers in required:
        if title in existing:
            ws = existing[title]
        else:
            # create missing tab with fewer calls
            ws = _retry(sh.add_worksheet, title=title, rows=1000, cols=max(26, len(headers)))
        _ensure_headers(ws, headers)
        title_to_ws[title] = ws
    return title_to_ws

REQUIRED_TABS = [
    ("Members",           MEM_HEADERS),
    ("Business_Listings", DIR_HEADERS),
    ("Vicinity_Vendors",  VEN_HEADERS),
    ("Showcase",          SHOW_HEADERS),
    ("Ratings",           RATE_HEADERS),
    ("Support_Tickets",   SUPP_HEADERS),
]

# If you’re only changing colors/images, skip Google for stability.
if IS_EDIT_MODE:
    st.info("🚧 EDIT MODE is ON — Google Sheets calls are skipped so you can safely tweak UI.")
    ws_members = ws_dir = ws_ven = ws_show = ws_rate = ws_supp = None

    @st.cache_data(ttl=1)
    def read_df(tab: str) -> pd.DataFrame:
        # Return empty frames in edit mode
        if tab == "Business_Listings":
            # You can return a tiny sample here if you want to see cards in preview.
            return pd.DataFrame(columns=DIR_HEADERS)
        return pd.DataFrame()

else:
    try:
        tabs_map = _get_or_create_worksheets(sh, REQUIRED_TABS)
        ws_members  = tabs_map["Members"]
        ws_dir      = tabs_map["Business_Listings"]
        ws_ven      = tabs_map["Vicinity_Vendors"]
        ws_show     = tabs_map["Showcase"]
        ws_rate     = tabs_map["Ratings"]
        ws_supp     = tabs_map["Support_Tickets"]
    except Exception as e:
        st.error("⚠️ Could not open or create worksheets right now. Please try again shortly.")
        st.caption("Tip: turn EDIT_MODE = \"true\" in Secrets to keep the app up while editing UI.")
        st.stop()

    # Cached read uses a single call per tab and respects TTL to avoid 429
    @st.cache_data(ttl=45)
    def read_df(tab: str) -> pd.DataFrame:
        try:
            ws = {
                "Members": ws_members, "Business_Listings": ws_dir, "Vicinity_Vendors": ws_ven,
                "Showcase": ws_show, "Ratings": ws_rate, "Support_Tickets": ws_supp
            }.get(tab)
            if ws is None:
                return pd.DataFrame()
            vals = _retry(ws.get_all_values)
            if not vals:
                return pd.DataFrame()
            if len(vals) == 1:
                return pd.DataFrame(columns=vals[0])
            return pd.DataFrame(vals[1:], columns=vals[0])
        except Exception:
            return pd.DataFrame()

# -------------------- CACHED READS (helps avoid 429 rate limits) --------------------
@st.cache_data(ttl=30)
def read_df(tab: str) -> pd.DataFrame:
    try:
        ws = sh.worksheet(tab)
        vals = ws.get_all_values()
        if not vals:
            return pd.DataFrame()
        if len(vals) == 1:
            return pd.DataFrame(columns=vals[0])
        return pd.DataFrame(vals[1:], columns=vals[0])
    except Exception:
        return pd.DataFrame()

def df_public(df: pd.DataFrame, approved_col="Approved", expires_col: Optional[str]="Expires_On") -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    if approved_col in d.columns:
        d["_ok"] = d[approved_col].astype(str).str.strip().str.lower().isin(TRUE_LIKE)
        d = d[d["_ok"]==True].drop(columns=["_ok"])
    if expires_col and (expires_col in d.columns):
        d["_exp"] = pd.to_datetime(d[expires_col], errors="coerce", utc=True)
        now = pd.Timestamp.utcnow()
        d = d[(d["_exp"].isna()) | (d["_exp"] >= now)].drop(columns=["_exp"])
    return d.reset_index(drop=True)

# -------------------- ADMIN AUTH --------------------
def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))

def admin_login_ui():
    if is_admin():
        return
    with st.expander("🔐 Admin login", expanded=False):
        u = st.text_input("Username", key="adm_u")
        p = st.text_input("Password", type="password", key="adm_p")
        if st.button("Sign in", type="primary", key="adm_btn_signin"):
            if u.strip() == st.secrets.get("APP_USERNAME","") and p == st.secrets.get("APP_PASSWORD",""):
                st.session_state.is_admin = True
                st.success("✅ Admin logged in.")
                _safe_rerun()
            else:
                st.error("❌ Wrong credentials.")

# -------------------- MEMBER VERIFY SIGN-IN (PINNED) --------------------
def member_is_approved(email: str) -> bool:
    if not email:
        return False
    df = read_df("Members")
    if df.empty or "Email" not in df:
        return False
    m = df[df["Email"].str.strip().str.lower() == email.strip().lower()]
    if m.empty:
        return False
    return m["Approved"].astype(str).str.strip().str.lower().isin(TRUE_LIKE).any()

def member_bar():
    st.markdown("<hr/>", unsafe_allow_html=True)
    with st.container():
        cols = st.columns([2,5,2])
        with cols[0]:
            st.markdown("#### 👤 Member Sign-in", unsafe_allow_html=True)
        with cols[1]:
            email_in = st.text_input("Your Email (member)", key="me_email_input").strip()
        with cols[2]:
            if st.button("Set as me", key="btn_set_me"):
                if member_is_approved(email_in):
                    st.session_state.me = email_in
                    st.success("You’re set as a **verified** member.")
                else:
                    st.warning("Not found or not approved yet. Register or wait for approval.")
    st.markdown("<hr/>", unsafe_allow_html=True)

# -------------------- WRITE HELPERS --------------------
def _append_row(ws, data: dict, headers: list[str]):
    ws.append_row([str(data.get(h,"")) for h in headers])

def save_member(data: dict):
    payload = dict(
        Member_ID=f"M-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="",
        Resident_Type=data.get("Resident_Type",""), Phase=data.get("Phase",""),
        Wing=data.get("Wing",""), Flat_No=data.get("Flat_No",""),
        Name=data.get("Name",""), Email=data.get("Email",""), Phone=data.get("Phone",""),
    )
    _append_row(ws_members, payload, MEM_HEADERS)
    clear_cache()

def save_directory(data: dict):
    days = int(data.get("Duration_Days",0) or 0)
    payload = dict(
        Listing_ID=f"D-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="",
        Member_Email=data.get("Member_Email",""),
        Resident_Type=data.get("Resident_Type",""),
        Phase=data.get("Phase",""), Wing=data.get("Wing",""), Flat_No=data.get("Flat_No",""),
        Business_Name=data.get("Business_Name",""),
        Category=data.get("Category",""), Subcategory=data.get("Subcategory",""),
        Service_Type=data.get("Service_Type",""),
        Short_Description=data.get("Short_Description",""),
        Detailed_Description=data.get("Detailed_Description",""),
        Image_URL_1=data.get("Image_URL_1",""),
        Image_URL_2=data.get("Image_URL_2",""),
        Image_URL_3=data.get("Image_URL_3",""),
        Duration_Days=str(days),
        Expires_On=(dt.date.today()+dt.timedelta(days=days)).isoformat() if days>0 else ""
    )
    _append_row(ws_dir, payload, DIR_HEADERS)
    clear_cache()

def save_vendor(data: dict):
    days = int(data.get("Duration_Days",0) or 0)
    payload = dict(
        Vendor_ID=f"V-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="",
        Member_Email=data.get("Member_Email",""),
        Vendor_Name=data.get("Vendor_Name",""), Contact=data.get("Contact",""),
        Phone=data.get("Phone",""), Address=data.get("Address",""),
        Category=data.get("Category",""), Short_Description=data.get("Short_Description",""),
        Image_URL_1=data.get("Image_URL_1",""),
        Image_URL_2=data.get("Image_URL_2",""),
        Image_URL_3=data.get("Image_URL_3",""),
        Duration_Days=str(days),
        Expires_On=(dt.date.today()+dt.timedelta(days=days)).isoformat() if days>0 else ""
    )
    _append_row(ws_ven, payload, VEN_HEADERS)
    clear_cache()

def save_ticket(email: str, subject: str, message: str):
    payload = dict(
        Ticket_ID=f"T-{uuid.uuid4().hex[:8].upper()}",
        When=_now_iso(), Email=email, Subject=subject, Message=message, Status="Open"
    )
    _append_row(ws_supp, payload, SUPP_HEADERS)

def save_showcase(data: dict, approve: bool=False):
    payload = dict(
        Show_ID=f"S-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="TRUE" if approve else "",
        Title=data.get("Title",""), Type=data.get("Type","image"),
        URL=data.get("URL",""), Posted_By=data.get("Posted_By",""), Notes=data.get("Notes",""),
    )
    _append_row(ws_show, payload, SHOW_HEADERS)
    clear_cache()

def save_rating(listing_id: str, stars: int, comment: str, email: str):
    payload = dict(
        When=_now_iso(), Type="Business", Target_ID=listing_id,
        Stars=str(stars), Comment=comment, Rater_Email=email
    )
    _append_row(ws_rate, payload, RATE_HEADERS)

# -------------------- ADMIN ACTION HELPERS --------------------
def _header_map(ws, defaults: list[str]) -> dict[str,int]:
    try:
        row1 = ws.row_values(1) or defaults
    except APIError:
        row1 = defaults
    return {h:i+1 for i,h in enumerate(row1)}

def _find_row_by_id(ws, id_col_idx: int, id_value: str) -> Optional[int]:
    try:
        col = ws.col_values(id_col_idx)
    except APIError:
        col = []
    for i, v in enumerate(col, start=1):
        if str(v).strip() == str(id_value).strip():
            return i
    return None

def approve_by_id(ws, id_col: str, id_val: str, defaults: list[str], extra: dict | None = None):
    hdr = _header_map(ws, defaults)
    id_idx = hdr.get(id_col)
    ap_idx = hdr.get("Approved")
    if not id_idx or not ap_idx:
        return
    row = _find_row_by_id(ws, id_idx, id_val)
    if row is None:
        return
    ws.update_cell(row, ap_idx, "TRUE")
    if extra:
        for k, v in extra.items():
            idx = hdr.get(k)
            if idx:
                ws.update_cell(row, idx, v)
    clear_cache()

def reject_by_id(ws, id_col: str, id_val: str, defaults: list[str]):
    hdr = _header_map(ws, defaults)
    id_idx = hdr.get(id_col)
    ap_idx = hdr.get("Approved")
    if not id_idx or not ap_idx:
        return
    row = _find_row_by_id(ws, id_idx, id_val)
    if row is None:
        return
    ws.update_cell(row, ap_idx, "REJECTED")
    clear_cache()

def extend_expiry(ws, id_col: str, id_val: str, defaults: list[str], extra_days: int):
    hdr = _header_map(ws, defaults)
    id_idx = hdr.get(id_col)
    ex_idx = hdr.get("Expires_On")
    if not id_idx or not ex_idx:
        return
    row = _find_row_by_id(ws, id_idx, id_val)
    if row is None:
        return
    current = ws.cell(row, ex_idx).value or dt.date.today().isoformat()
    try:
        cur = dt.date.fromisoformat(current)
    except Exception:
        cur = dt.date.today()
    new_date = (cur + dt.timedelta(days=int(extra_days or 0))).isoformat()
    ws.update_cell(row, ex_idx, new_date)
    clear_cache()

# -------------------- HEADER UI --------------------
def header():
    cols = st.columns([1,10])
    with cols[0]:
        if LOGO_URL:
            st.image(LOGO_URL, use_container_width=True)
        else:
            st.markdown("<div class='badge'>Atmosphere</div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            "<div class='banner'><h2 style='margin:0'>Atmosphere Society — Community Hub</h2>"
            "<div>Showcase • Directory • Vendors • Support</div></div>",
            unsafe_allow_html=True
        )

header()

# -------------------- PINNED MEMBER SIGN-IN --------------------
member_bar()

# -------------------- NAV TABS --------------------
tabs = st.tabs([
    "🏠 Showcase", "ℹ️ About", "📇 Resident Directory",
    "🛒 Vicinity Vendors", "🆘 Support", "🧑‍🤝‍🧑 Register", "🛠️ Admin"
])

# ---- Showcase ----
with tabs[0]:
    st.subheader("Showcase Wall")
    s = df_public(read_df("Showcase"), approved_col="Approved", expires_col=None)
    if s.empty:
        st.info("No items yet. Admin can add in the Admin tab.")
    else:
        for _, r in s.sort_values("Submitted_At", ascending=False).iterrows():
            with st.container(border=True):
                st.markdown(
                    f"**{r.get('Title','')}**  ·  "
                    f"<span class='badge'>{r.get('Type','')}</span>  "
                    f"<span class='small-dim'>by {r.get('Posted_By','')}</span>",
                    unsafe_allow_html=True
                )
                url = (r.get("URL","") or "").strip()
                if r.get("Type","").lower()=="video" and url:
                    st.video(url)
                elif url:
                    st.image(url, use_container_width=True, caption=r.get("Notes",""))

# ---- About ----
with tabs[1]:
    st.subheader("About the App")
    st.markdown("""
**What is this?**  
A simple, community-first hub for *Atmosphere Society* residents & tenants.

**You can**
- Browse the **Resident Directory** (approved listings).
- Suggest **Vicinity Vendors** that help the community.
- See the **Showcase** wall for ads/promotions (admin-posted).
- Submit a **Support Ticket** if you need help.

**Listings**
- Submissions go to **Admin Approval**.
- Choose listing period: **7 / 15 / 30 / 45 / 60 / 90 days**.
- Expired listings stop showing automatically; Admin can extend.
""")

# ---- Resident Directory (Business) ----
with tabs[2]:
    st.subheader("Resident Business Directory")
    df = df_public(read_df("Business_Listings"))
    if df.empty:
        st.info("No approved listings yet.")
    else:
        # FILTERS
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            phase_sel = st.selectbox("Phase", ["All"] + sorted(df["Phase"].dropna().unique().tolist()), key="f_phase")
        with f2:
            cat_sel   = st.selectbox("Category", ["All"] + sorted(df["Category"].dropna().unique().tolist()), key="f_cat")
        with f3:
            srv_sel   = st.selectbox("Service Type", ["All"] + sorted(df["Service_Type"].dropna().unique().tolist()), key="f_srv")
        with f4:
            wing_sel  = st.selectbox("Wing", ["All"] + sorted(df["Wing"].dropna().unique().tolist()), key="f_wing")
        with f5:
            query     = st.text_input("Search", key="f_query")

        view = df.copy()
        if phase_sel != "All": view = view[view["Phase"]==phase_sel]
        if cat_sel   != "All": view = view[view["Category"]==cat_sel]
        if srv_sel   != "All": view = view[view["Service_Type"]==srv_sel]
        if wing_sel  != "All": view = view[view["Wing"]==wing_sel]
        if query:
            ql = query.lower()
            view = view[view.apply(lambda r: ql in (" ".join(map(str, r.values))).lower(), axis=1)]

        if view.empty:
            st.info("No matches.")
        else:
            # Show as cards with rating box for verified members
            for _, r in view.sort_values("Submitted_At", ascending=False).iterrows():
                with st.container(border=True):
                    st.markdown(f"### {r.get('Business_Name','')}")
                    st.caption(f"{r.get('Category','')} → {r.get('Subcategory','')} · {r.get('Service_Type','')}")
                    st.write(r.get("Short_Description",""))
                    col_img = st.columns(3)
                    imgs = [r.get("Image_URL_1",""), r.get("Image_URL_2",""), r.get("Image_URL_3","")]
                    for i, url in enumerate(imgs):
                        if url:
                            with col_img[i]:
                                st.image(url, use_container_width=True)
                    st.caption(f"Phase: {r.get('Phase','')} · Wing: {r.get('Wing','')} · Flat: {r.get('Flat_No','')} · {r.get('Resident_Type','')}")
                    st.caption(f"Listing ID: {r.get('Listing_ID','')} · Expires: {r.get('Expires_On','')}")

                    # Ratings: only if verified member
                    if "me" in st.session_state:
                        with st.form(f"rate_{r.get('Listing_ID','')}"):
                            st.markdown("**Rate this business**")
                            stars = st.slider("Stars", 1, 5, 5, key=f"stars_{r.get('Listing_ID','')}")
                            comment = st.text_input("Comment (optional)", key=f"com_{r.get('Listing_ID','')}")
                            ok = st.form_submit_button("Submit rating")
                            if ok:
                                save_rating(
                                    listing_id=r.get("Listing_ID",""),
                                    stars=int(stars),
                                    comment=comment,
                                    email=st.session_state.me
                                )
                                st.success("Thanks! Rating recorded.")
                    else:
                        st.info("Sign in as verified member (top bar) to rate.")

    st.markdown("---")
    st.markdown("### Submit your business")
    if "me" not in st.session_state:
        st.info("Sign in as a verified member (top bar) to submit.")
    else:
        with st.form("dir_submit"):
            c1,c2,c3 = st.columns(3)
            with c1:
                phase = st.selectbox("Phase", ["Atmosphere 1","Atmosphere 2"], key="dir_phase")
                wing  = st.selectbox("Wing", list("ABCDEFGH"), key="dir_wing")
                flat  = st.text_input("Flat No (e.g., 1203)", key="dir_flat")
            with c2:
                resident_type = st.selectbox("Resident Type", ["Resident","Tenant"], key="dir_resident_type")
                cat_list = list(CATEGORIES.keys())
                category = st.selectbox("Category", cat_list, key="dir_cat")
                subcategory = st.selectbox("Subcategory", CATEGORIES.get(category, ["Other"]), key="dir_subcat")
            with c3:
                service = st.text_input("Service Type", key="dir_service")
                duration = st.selectbox("Listing duration (days)", [7,15,30,45,60,90], key="dir_duration")

            b_name = st.text_input("Business Name *", key="dir_bname")
            short  = st.text_area("Short Description *", max_chars=200, key="dir_short")
            detail = st.text_area("Detailed Description", max_chars=1000, key="dir_detail")
            i1,i2,i3 = st.columns(3)
            with i1: u1 = st.text_input("Image URL 1", key="dir_img1")
            with i2: u2 = st.text_input("Image URL 2", key="dir_img2")
            with i3: u3 = st.text_input("Image URL 3", key="dir_img3")

            ok = st.form_submit_button("Submit for approval", type="primary")
            if ok:
                save_directory(dict(
                    Member_Email=st.session_state.me, Resident_Type=resident_type,
                    Phase=phase, Wing=wing, Flat_No=flat,
                    Business_Name=b_name, Category=category, Subcategory=subcategory,
                    Service_Type=service, Short_Description=short, Detailed_Description=detail,
                    Image_URL_1=u1, Image_URL_2=u2, Image_URL_3=u3, Duration_Days=int(duration)
                ))
                st.success("Submitted! Admin will review & approve.")

# ---- Vicinity Vendors ----
with tabs[3]:
    st.subheader("Vicinity Vendors")
    vdf = df_public(read_df("Vicinity_Vendors"))
    if vdf.empty:
        st.info("No approved vendors yet.")
    else:
        st.dataframe(vdf[[
            "Vendor_Name","Category","Short_Description","Contact","Phone","Address","Expires_On","Vendor_ID"
        ]], use_container_width=True)

    st.markdown("---")
    st.markdown("### Suggest a vendor")
    if "me" not in st.session_state:
        st.info("Sign in as a verified member (top bar) before submitting.")
    else:
        with st.form("ven_submit"):
            c1,c2 = st.columns(2)
            with c1:
                vname = st.text_input("Vendor Name *", key="ven_name")
                vcat  = st.selectbox("Category", list(CATEGORIES.keys()), key="ven_cat")
                vcontact = st.text_input("Contact person", key="ven_contact")
            with c2:
                vphone = st.text_input("Phone", key="ven_phone")
                vaddr  = st.text_input("Address", key="ven_addr")
                vdur   = st.selectbox("Listing duration (days)", [7,15,30,45,60,90], key="ven_dur")
            vshort = st.text_area("Short Description *", max_chars=300, key="ven_short")
            i1,i2,i3 = st.columns(3)
            with i1: vu1 = st.text_input("Image URL 1", key="ven_img1")
            with i2: vu2 = st.text_input("Image URL 2", key="ven_img2")
            with i3: vu3 = st.text_input("Image URL 3", key="ven_img3")
            ok = st.form_submit_button("Submit vendor", type="primary")
            if ok:
                save_vendor(dict(
                    Member_Email=st.session_state.me, Vendor_Name=vname, Category=vcat,
                    Contact=vcontact, Phone=vphone, Address=vaddr, Short_Description=vshort,
                    Image_URL_1=vu1, Image_URL_2=vu2, Image_URL_3=vu3, Duration_Days=int(vdur)
                ))
                st.success("Submitted! Admin will review & approve.")

# ---- Support ----
with tabs[4]:
    st.subheader("Support")
    st.caption("Replies may take 7–15 days.")
    with st.form("supp"):
        em = st.text_input("Your Email", key="sup_email")
        sub = st.text_input("Subject", key="sup_subject")
        msg = st.text_area("Message", height=120, key="sup_message")
        ok = st.form_submit_button("Create Ticket", type="primary")
        if ok:
            save_ticket(em, sub, msg)
            st.success("Thanks! Ticket submitted.")

# ---- Register ----
with tabs[5]:
    st.subheader("Register as Resident or Tenant")
    with st.form("reg"):
        c1,c2,c3 = st.columns(3)
        with c1:
            rtype = st.selectbox("Resident Type", ["Resident","Tenant"], key="reg_rtype")
            phase = st.selectbox("Phase", ["Atmosphere 1","Atmosphere 2"], key="reg_phase")
            wing  = st.selectbox("Wing", list("ABCDEFGH"), key="reg_wing")
        with c2:
            flat  = st.text_input("Flat No (e.g., 1203)", key="reg_flat")
            name  = st.text_input("Full Name", key="reg_name")
            email = st.text_input("Email", key="reg_email")
        with c3:
            phone = st.text_input("Phone", key="reg_phone")
        ok = st.form_submit_button("Register", type="primary")
        if ok:
            save_member(dict(
                Resident_Type=rtype, Phase=phase, Wing=wing, Flat_No=flat,
                Name=name, Email=email, Phone=phone
            ))
            st.success("Registered! Wait for admin approval.")

# ---- Admin ----
with tabs[6]:
    admin_login_ui()
    if not is_admin():
        st.warning("Admin only.")
    else:
        st.subheader("🛠️ Admin Panel")

        with st.expander("Add Showcase (image/video)", expanded=False):
            t = st.text_input("Title", key="adm_show_title")
            typ = st.selectbox("Type", ["image","video"], key="adm_show_type")
            url = st.text_input("URL (image link or video link)", key="adm_show_url")
            by  = st.text_input("Posted by", key="adm_show_by")
            notes = st.text_area("Notes", key="adm_show_notes")
            approve_now = st.checkbox("Approve now?", value=True, key="adm_show_apr")
            if st.button("Add to Showcase", type="primary", key="adm_show_btn"):
                save_showcase(dict(Title=t, Type=typ, URL=url, Posted_By=by, Notes=notes), approve=approve_now)
                st.success("Added to Showcase.")

        st.markdown("### Approvals")

        dfm   = read_df("Members")
        dfd   = read_df("Business_Listings")
        dfv   = read_df("Vicinity_Vendors")

        # Members
        pend_m = dfm[dfm["Approved"].astype(str).str.upper()!="TRUE"] if not dfm.empty and "Approved" in dfm else pd.DataFrame()
        with st.expander(f"Members (pending: {len(pend_m)})", expanded=False):
            if pend_m.empty:
                st.info("No pending members.")
            else:
                for _, row in pend_m.iterrows():
                    with st.expander(f"{row.get('Name','')} · {row.get('Email','')}"):
                        st.write(dict(row))
                        c1,c2 = st.columns(2)
                        with c1:
                            if st.button("Approve member", key=f"m_ap_{row.get('Member_ID','')}"):
                                approve_by_id(ws_members,"Member_ID",row.get("Member_ID",""),MEM_HEADERS)
                                st.success("Approved."); _safe_rerun()
                        with c2:
                            if st.button("Reject member", key=f"m_rj_{row.get('Member_ID','')}"):
                                reject_by_id(ws_members,"Member_ID",row.get("Member_ID",""),MEM_HEADERS)
                                st.warning("Rejected."); _safe_rerun()

        # Business Listings
        pend_d = dfd[dfd["Approved"].astype(str).str.upper()!="TRUE"] if not dfd.empty and "Approved" in dfd else pd.DataFrame()
        with st.expander(f"Business Listings (pending: {len(pend_d)})", expanded=False):
            if pend_d.empty:
                st.info("No pending listings.")
            else:
                for _, row in pend_d.iterrows():
                    with st.expander(f"{row.get('Business_Name','(no name)')} · {row.get('Member_Email','')}"):
                        st.write(dict(row))
                        c1,c2,c3 = st.columns(3)
                        with c1:
                            if st.button("Approve listing", key=f"d_ap_{row.get('Listing_ID','')}"):
                                try:
                                    days = int(row.get("Duration_Days","0") or "0")
                                    extra = {"Expires_On": (dt.date.today()+dt.timedelta(days=days)).isoformat()} if days>0 else {}
                                except Exception:
                                    extra = {}
                                approve_by_id(ws_dir,"Listing_ID",row.get("Listing_ID",""),DIR_HEADERS,extra)
                                st.success("Approved."); _safe_rerun()
                        with c2:
                            if st.button("Reject listing", key=f"d_rj_{row.get('Listing_ID','')}"):
                                reject_by_id(ws_dir,"Listing_ID",row.get("Listing_ID",""),DIR_HEADERS)
                                st.warning("Rejected."); _safe_rerun()
                        with c3:
                            more = st.number_input("Extend by days",0,365,0,key=f"d_ext_{row.get('Listing_ID','')}")
                            if st.button("Apply extension", key=f"d_ext_btn_{row.get('Listing_ID','')}"):
                                extend_expiry(ws_dir,"Listing_ID",row.get("Listing_ID",""),DIR_HEADERS,int(more))
                                st.success("Expiry extended."); _safe_rerun()

        # Vendors
        pend_v = dfv[dfv["Approved"].astype(str).str.upper()!="TRUE"] if not dfv.empty and "Approved" in dfv else pd.DataFrame()
        with st.expander(f"Vicinity Vendors (pending: {len(pend_v)})", expanded=False):
            if pend_v.empty:
                st.info("No pending vendor submissions.")
            else:
                for _, row in pend_v.iterrows():
                    with st.expander(f"{row.get('Vendor_Name','Vendor')} · {row.get('Member_Email','')}"):
                        st.write(dict(row))
                        c1,c2,c3 = st.columns(3)
                        with c1:
                            if st.button("Approve vendor", key=f"v_ap_{row.get('Vendor_ID','')}"):
                                try:
                                    days = int(row.get("Duration_Days","0") or "0")
                                    extra = {"Expires_On": (dt.date.today()+dt.timedelta(days=days)).isoformat()} if days>0 else {}
                                except Exception:
                                    extra = {}
                                approve_by_id(ws_ven,"Vendor_ID",row.get("Vendor_ID",""),VEN_HEADERS,extra)
                                st.success("Approved."); _safe_rerun()
                        with c2:
                            if st.button("Reject vendor", key=f"v_rj_{row.get('Vendor_ID','')}"):
                                reject_by_id(ws_ven,"Vendor_ID",row.get("Vendor_ID",""),VEN_HEADERS)
                                st.warning("Rejected."); _safe_rerun()
                        with c3:
                            more = st.number_input("Extend by days",0,365,0,key=f"v_ext_{row.get('Vendor_ID','')}")
                            if st.button("Apply extension", key=f"v_ext_btn_{row.get('Vendor_ID','')}"):
                                extend_expiry(ws_ven,"Vendor_ID",row.get("Vendor_ID",""),VEN_HEADERS,int(more))
                                st.success("Expiry extended."); _safe_rerun()

        st.markdown("### Export CSV")
        if not dfd.empty: st.download_button("Businesses.csv", dfd.to_csv(index=False).encode(), "businesses.csv")
        if not dfv.empty: st.download_button("Vendors.csv",   dfv.to_csv(index=False).encode(), "vendors.csv")
        if not dfm.empty: st.download_button("Members.csv",   dfm.to_csv(index=False).encode(), "members.csv")
