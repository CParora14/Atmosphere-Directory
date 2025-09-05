# Atmosphere Society — Community Hub
# Showcase • Directory • Vendors • Support
# Replace your streamlit_app.py with this file

from __future__ import annotations
import uuid
import datetime as dt
from typing import Optional

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# =========================== THEME / BRANDING ===========================
PRIMARY   = "#18B8CB"   # teal
PRIMARY_2 = "#6BC6FF"   # light blue
INK       = "#0C2AAA"   # deep ink
CARD_BG   = "#0E1C2B"   # dark card
PAGE_BG   = "#0A1522"   # darker page
LOGO_URL  = st.secrets.get("LOGO_URL", "")  # Optional public logo URL

st.set_page_config(
    page_title="Atmosphere Society — Community Hub",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    f"""
<style>
:root {{
  --brand: {PRIMARY};
  --brand2:{PRIMARY_2};
  --ink:   {INK};
  --card:  {CARD_BG};
  --page:  {PAGE_BG};
}}
html, body, [data-testid="stAppViewContainer"] {{
  background: var(--page)!important;
  color: #EAF2FA!important;
}}
.block-container {{
  padding-top: 1.5rem;
  padding-bottom: 3rem;
  max-width: 1200px;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.stTabs [data-baseweb="tab"] {{ color: #EAF2FA; font-weight: 600; }}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(90deg, var(--brand), var(--brand2))!important;
  color: #001018!important;
  border-radius: 10px;
}}
.banner {{
  width: 100%; padding: 20px 24px; border-radius: 18px;
  background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_2} 100%);
  color: #001018; box-shadow: 0 10px 30px rgba(0,0,0,.25);
}}
.card {{
  background: var(--card); border-radius: 16px; padding: 16px 18px;
  border: 1px solid rgba(255,255,255,.06)
}}
.badge {{
  padding: 2px 8px; border-radius: 100px; font-size: 12px;
  background: rgba(255,255,255,.08);
  border: 1px solid rgba(255,255,255,.08);
}}
</style>
""",
    unsafe_allow_html=True,
)

# =========================== SMALL UTILITIES ===========================
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

# =========================== HELPERS (Sheets/DF) ===========================
def ensure_ws(sh, title: str, headers: list[str]):
    """
    Ensure a worksheet exists with given title and headers in row 1.
    """
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(26, len(headers)))
        ws.append_row(headers)
        return ws

    # Make sure headers exist in row 1. If blank, write them once.
    try:
        row1 = ws.row_values(1)
    except APIError:
        row1 = []
    if not row1:
        ws.update("A1", [headers])
    return ws

def ws_to_df(ws) -> pd.DataFrame:
    """
    Convert a gspread worksheet to DataFrame using row-1 headers.
    """
    try:
        vals = ws.get_all_values()
    except Exception:
        return pd.DataFrame()
    if not vals:
        return pd.DataFrame()
    if len(vals) == 1:
        return pd.DataFrame(columns=vals[0])
    return pd.DataFrame(vals[1:], columns=vals[0])

def df_public(df: pd.DataFrame,
              approved_col: str = "Approved",
              expires_col: Optional[str] = "Expires_On") -> pd.DataFrame:
    """
    Filter to rows Approved == TRUE-like and (if present) not expired.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    d = df.copy()
    # Approved flag
    if approved_col in d.columns:
        d["_approved_flag"] = d[approved_col].astype(str).str.strip().str.lower().isin(TRUE_LIKE)
        d = d[d["_approved_flag"] == True].drop(columns=["_approved_flag"])

    # Expiry
    if expires_col and (expires_col in d.columns):
        d["_exp_dt"] = pd.to_datetime(d[expires_col], errors="coerce", utc=True)
        now = pd.Timestamp.utcnow()
        d = d[(d["_exp_dt"].isna()) | (d["_exp_dt"] >= now)].drop(columns=["_exp_dt"])

    return d.reset_index(drop=True)

# =========================== REQUIRED HEADERS ===========================
MEM_HEADERS = [
    "Member_ID","Submitted_At","Approved","Resident_Type","Phase","Wing",
    "Flat_No","Name","Email","Phone"
]
DIR_HEADERS = [
    "Listing_ID","Submitted_At","Approved","Member_Email","Resident_Type","Phase","Wing","Flat_No",
    "Business_Name","Category","Subcategory","Service_Type",
    "Short_Description","Detailed_Description",
    "Image_URL_1","Image_URL_2","Image_URL_3",
    "Duration_Days","Expires_On"
]
VEN_HEADERS = [
    "Vendor_ID","Submitted_At","Approved","Member_Email","Vendor_Name","Contact",
    "Phone","Address","Category","Short_Description",
    "Image_URL_1","Image_URL_2","Image_URL_3","Duration_Days","Expires_On"
]
SHOW_HEADERS = ["Show_ID","Submitted_At","Approved","Title","Type","URL","Posted_By","Notes"]
RATE_HEADERS = ["When","Type","Target_ID","Stars","Comment","Rater_Email"]
SUPP_HEADERS = ["Ticket_ID","When","Email","Subject","Message","Status"]

# =========================== GOOGLE AUTH & SHEET OPEN ===========================
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
    url = st.secrets.get("SHEET_URL", "")
    if not url:
        st.error("SHEET_URL not set in Secrets. Go to App ▸ Settings ▸ Secrets and add it.")
        st.stop()
    return _gc().open_by_url(url)

with st.spinner("Connecting to Google Sheets…"):
    sh = _open_sheet()
    # --- DIAGNOSTIC: show service account + list tabs (remove after it works) ---
sa_email = st.secrets["gcp_service_account"]["client_email"]
st.caption(f"Service Account: `{sa_email}`")
try:
    titles = [ws.title for ws in sh.worksheets()]
    st.caption("Sheets I can see: " + ", ".join(titles))
except Exception as e:
    st.error("Cannot list worksheets – likely a permissions/share issue.")
    st.code(str(e))
    st.stop()

ws_members  = ensure_ws(sh, "Members",           MEM_HEADERS)
ws_dir      = ensure_ws(sh, "Business_Listings", DIR_HEADERS)
ws_ven      = ensure_ws(sh, "Vicinity_Vendors",  VEN_HEADERS)
ws_show     = ensure_ws(sh, "Showcase",          SHOW_HEADERS)
ws_rate     = ensure_ws(sh, "Ratings",           RATE_HEADERS)
ws_supp     = ensure_ws(sh, "Support_Tickets",   SUPP_HEADERS)

# =========================== ADMIN AUTH ===========================
APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

def is_admin() -> bool:
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    return st.session_state.is_admin

def admin_login_ui():
    if is_admin():
        return
    with st.expander("🔐 Admin login", expanded=False):
        u = st.text_input("Username", key="adm_u")
        p = st.text_input("Password", type="password", key="adm_p")
        if st.button("Sign in", type="primary"):
            if u.strip() == APP_USERNAME and p == APP_PASSWORD:
                st.session_state.is_admin = True
                st.success("✅ Admin logged in.")
                _safe_rerun()
            else:
                st.error("❌ Wrong credentials.")

# =========================== SAVE / LOOKUP FUNCTIONS ===========================
def _append_row(ws, data: dict, headers: list[str]):
    """Append a dict as a row under given headers order."""
    row = [str(data.get(h, "")) for h in headers]
    ws.append_row(row)

def member_is_approved(email: str) -> bool:
    if not email:
        return False
    df = ws_to_df(ws_members)
    if df.empty:
        return False
    m = df[(df["Email"].str.strip().str.lower() == email.strip().lower())]
    if m.empty:
        return False
    return m["Approved"].astype(str).str.strip().str.lower().isin(TRUE_LIKE).any()

def save_member(data: dict):
    mid = f"M-{uuid.uuid4().hex[:8].upper()}"
    payload = dict(
        Member_ID=mid,
        Submitted_At=_now_iso(),
        Approved="",
        Resident_Type=data.get("Resident_Type",""),
        Phase=data.get("Phase",""),
        Wing=data.get("Wing",""),
        Flat_No=data.get("Flat_No",""),
        Name=data.get("Name",""),
        Email=data.get("Email",""),
        Phone=data.get("Phone",""),
    )
    _append_row(ws_members, payload, MEM_HEADERS)

def save_directory(data: dict):
    lid = f"D-{uuid.uuid4().hex[:8].upper()}"
    days = int(data.get("Duration_Days", 0) or 0)
    expires = (dt.date.today() + dt.timedelta(days=days)).isoformat() if days > 0 else ""
    payload = dict(
        Listing_ID=lid,
        Submitted_At=_now_iso(),
        Approved="",
        Member_Email=data.get("Member_Email",""),
        Resident_Type=data.get("Resident_Type",""),
        Phase=data.get("Phase",""),
        Wing=data.get("Wing",""),
        Flat_No=data.get("Flat_No",""),
        Business_Name=data.get("Business_Name",""),
        Category=data.get("Category",""),
        Subcategory=data.get("Subcategory",""),
        Service_Type=data.get("Service_Type",""),
        Short_Description=data.get("Short_Description",""),
        Detailed_Description=data.get("Detailed_Description",""),
        Image_URL_1=data.get("Image_URL_1",""),
        Image_URL_2=data.get("Image_URL_2",""),
        Image_URL_3=data.get("Image_URL_3",""),
        Duration_Days=str(days),
        Expires_On=expires,
    )
    _append_row(ws_dir, payload, DIR_HEADERS)

def save_vendor(data: dict):
    vid = f"V-{uuid.uuid4().hex[:8].upper()}"
    days = int(data.get("Duration_Days", 0) or 0)
    expires = (dt.date.today() + dt.timedelta(days=days)).isoformat() if days > 0 else ""
    payload = dict(
        Vendor_ID=vid,
        Submitted_At=_now_iso(),
        Approved="",
        Member_Email=data.get("Member_Email",""),
        Vendor_Name=data.get("Vendor_Name",""),
        Contact=data.get("Contact",""),
        Phone=data.get("Phone",""),
        Address=data.get("Address",""),
        Category=data.get("Category",""),
        Short_Description=data.get("Short_Description",""),
        Image_URL_1=data.get("Image_URL_1",""),
        Image_URL_2=data.get("Image_URL_2",""),
        Image_URL_3=data.get("Image_URL_3",""),
        Duration_Days=str(days),
        Expires_On=expires,
    )
    _append_row(ws_ven, payload, VEN_HEADERS)

def save_ticket(email: str, subject: str, message: str):
    tid = f"T-{uuid.uuid4().hex[:8].upper()}"
    payload = dict(
        Ticket_ID=tid, When=_now_iso(),
        Email=email, Subject=subject, Message=message, Status="Open"
    )
    _append_row(ws_supp, payload, SUPP_HEADERS)

def save_showcase(data: dict, approve: bool = False):
    sid = f"S-{uuid.uuid4().hex[:8].upper()}"
    payload = dict(
        Show_ID=sid, Submitted_At=_now_iso(),
        Approved="TRUE" if approve else "",
        Title=data.get("Title",""),
        Type=data.get("Type","image"),
        URL=data.get("URL",""),
        Posted_By=data.get("Posted_By",""),
        Notes=data.get("Notes",""),
    )
    _append_row(ws_show, payload, SHOW_HEADERS)

# =========================== ADMIN ACTION HELPERS ===========================
def _header_map(ws, defaults: list[str]) -> dict[str, int]:
    """Header name -> 1-based column index."""
    try:
        row1 = ws.row_values(1)
        if not row1:
            row1 = defaults
    except APIError:
        row1 = defaults
    return {h: i+1 for i, h in enumerate(row1)}

def _find_row_by_id(ws, id_col_idx: int, id_value: str) -> Optional[int]:
    try:
        col_vals = ws.col_values(id_col_idx)
    except APIError:
        col_vals = []
    for i, v in enumerate(col_vals, start=1):
        if str(v).strip() == str(id_value).strip():
            return i
    return None

def approve_by_id(ws, id_col: str, id_value: str, defaults: list[str], extra_updates: dict | None = None):
    hdr = _header_map(ws, defaults)
    id_idx = hdr.get(id_col)
    ap_idx = hdr.get("Approved")
    if not id_idx or not ap_idx:
        st.error("Missing headers: need ID column and Approved.")
        return
    row = _find_row_by_id(ws, id_idx, id_value)
    if not row:
        st.warning(f"Row not found for {id_col}={id_value}")
        return
    ws.update_cell(row, ap_idx, "TRUE")
    if extra_updates:
        for k, v in extra_updates.items():
            idx = hdr.get(k)
            if idx:
                ws.update_cell(row, idx, v)

def reject_by_id(ws, id_col: str, id_value: str, defaults: list[str]):
    hdr = _header_map(ws, defaults)
    id_idx = hdr.get(id_col); ap_idx = hdr.get("Approved")
    if not id_idx or not ap_idx:
        st.error("Missing headers: need ID column and Approved.")
        return
    row = _find_row_by_id(ws, id_idx, id_value)
    if not row:
        st.warning(f"Row not found for {id_col}={id_value}")
        return
    ws.update_cell(row, ap_idx, "REJECTED")

def extend_expiry(ws, id_col: str, id_value: str, defaults: list[str], extra_days: int):
    hdr = _header_map(ws, defaults)
    id_idx = hdr.get(id_col); ex_idx = hdr.get("Expires_On")
    if not id_idx or not ex_idx:
        st.error("Missing headers: need ID and Expires_On.")
        return
    row = _find_row_by_id(ws, id_idx, id_value)
    if not row:
        st.warning(f"Row not found for {id_col}={id_value}")
        return
    current = ws.cell(row, ex_idx).value or dt.date.today().isoformat()
    try:
        cur = dt.date.fromisoformat(current)
    except Exception:
        cur = dt.date.today()
    new_dt = cur + dt.timedelta(days=int(extra_days or 0))
    ws.update_cell(row, ex_idx, new_dt.isoformat())

# =========================== HEADER UI ===========================
def header():
    cols = st.columns([1,10])
    with cols[0]:
        if LOGO_URL:
            st.image(LOGO_URL, use_container_width=True)
        else:
            st.markdown("<div class='badge'>Atmosphere</div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(
            f"<div class='banner'><h2 style='margin:0'>Atmosphere Society — Community Hub</h2>"
            f"<div>Showcase • Directory • Vendors • Support</div></div>",
            unsafe_allow_html=True
        )

header()

# =========================== NAV TABS ===========================
tabs = st.tabs(["🏠 Showcase", "ℹ️ About", "📇 Directory", "🛒 Vicinity Vendors", "🆘 Support", "🧑‍🤝‍🧑 Register", "🛠️ Admin"])

# =========================== TAB 0: SHOWCASE ===========================
with tabs[0]:
    st.subheader("Showcase Wall")
    s = df_public(ws_to_df(ws_show), approved_col="Approved", expires_col=None)
    if s.empty:
        st.info("No items yet. Admin can add in the Admin tab.")
    else:
        for _, r in s.sort_values("Submitted_At", ascending=False).iterrows():
            with st.container(border=True):
                st.markdown(f"**{r.get('Title','')}**  ·  <span class='badge'>{r.get('Type','')}</span>", unsafe_allow_html=True)
                url = (r.get("URL","") or "").strip()
                if r.get("Type","").lower()=="video":
                    st.video(url)
                else:
                    if url:
                        st.image(url, use_container_width=True, caption=r.get("Notes",""))

# =========================== TAB 1: ABOUT ===========================
with tabs[1]:
    st.subheader("About the App")
    st.markdown("""
**What is this?**  
A simple, community-first hub for *Atmosphere Society* residents & tenants.

**What you can do**
- Browse the **Directory** of resident-run businesses (approved).
- Suggest **Vicinity Vendors** that help the community.
- See the **Showcase** wall for ads/promotions (admin-posted).
- Submit a **Support Ticket** if you need help.

**How listings work**
- When you submit a business/vendor, it goes to **Admin Approval**.
- Select a listing period: **7 / 15 / 30 / 45 / 60 / 90 days**.
- Expired listings stop showing automatically. Admin can extend.
""")

# =========================== TAB 2: DIRECTORY (Residents) ===========================
with tabs[2]:
    st.subheader("Resident Business Directory")

    # Member quick sign-in (email) to allow submissions & ratings.
    with st.expander("Member quick sign-in (for submissions & rating)"):
        me = st.text_input("Your Email", key="me_email").strip()
        if st.button("Set as me", key="me_set"):
            if member_is_approved(me):
                st.session_state.me = me
                st.success("You’re set as a verified member.")
            else:
                st.warning("Not found or not yet approved. Register or wait for approval.")

    df = df_public(ws_to_df(ws_dir))
    if df.empty:
        st.info("No approved listings yet.")
    else:
        # Filters
        c = st.columns(5)
        with c[0]:
            f_phase = st.selectbox("Phase", ["All"] + sorted(df["Phase"].dropna().unique().tolist()))
        with c[1]:
            f_cat = st.selectbox("Category", ["All"] + sorted(df["Category"].dropna().unique().tolist()))
        with c[2]:
            f_srv = st.selectbox("Service Type", ["All"] + sorted(df["Service_Type"].dropna().unique().tolist()))
        with c[3]:
            f_wing = st.selectbox("Wing", ["All"] + sorted(df["Wing"].dropna().unique().tolist()))
        with c[4]:
            q = st.text_input("Search")

        view = df.copy()
        if f_phase != "All": view = view[view["Phase"]==f_phase]
        if f_cat   != "All": view = view[view["Category"]==f_cat]
        if f_srv   != "All": view = view[view["Service_Type"]==f_srv]
        if f_wing  != "All": view = view[view["Wing"]==f_wing]
        if q:
            qc = q.lower()
            view = view[view.apply(lambda r: qc in (" ".join(map(str,r.values))).lower(), axis=1)]

        st.dataframe(view[[
            "Business_Name","Category","Subcategory","Service_Type",
            "Short_Description","Phase","Wing","Flat_No","Resident_Type","Expires_On"
        ]], use_container_width=True)

    st.markdown("---")
    st.markdown("### Submit your business")
    if "me" not in st.session_state:
        st.info("Sign in as a verified member (email) above to submit.")
    else:
        with st.form("dir_submit"):
            c1,c2,c3 = st.columns(3)
            with c1:
                phase = st.selectbox("Phase", ["Atmosphere 1", "Atmosphere 2"])
                wing  = st.selectbox("Wing", list("ABCDEFGH"))
                flat  = st.text_input("Flat No (e.g., 1203)")
            with c2:
                resident_type = st.selectbox("Resident Type", ["Resident","Tenant"])
                category = st.text_input("Category")
                subcategory = st.text_input("Subcategory")
            with c3:
                service = st.text_input("Service Type")
                duration = st.selectbox("Listing duration (days)", [7,15,30,45,60,90])

            b_name = st.text_input("Business Name *")
            short  = st.text_area("Short Description *", max_chars=200)
            detail = st.text_area("Detailed Description", max_chars=1000)
            i1,i2,i3 = st.columns(3)
            with i1: u1 = st.text_input("Image URL 1")
            with i2: u2 = st.text_input("Image URL 2")
            with i3: u3 = st.text_input("Image URL 3")

            ok = st.form_submit_button("Submit for approval", type="primary")
            if ok:
                save_directory(dict(
                    Member_Email=st.session_state.me, Resident_Type=resident_type,
                    Phase=phase, Wing=wing, Flat_No=flat,
                    Business_Name=b_name, Category=category, Subcategory=subcategory,
                    Service_Type=service, Short_Description=short, Detailed_Description=detail,
                    Image_URL_1=u1, Image_URL_2=u2, Image_URL_3=u3,
                    Duration_Days=int(duration)
                ))
                st.success("Submitted! Admin will review & approve.")

# =========================== TAB 3: VICINITY VENDORS ===========================
with tabs[3]:
    st.subheader("Vicinity Vendors")
    vdf = df_public(ws_to_df(ws_ven))
    if vdf.empty:
        st.info("No approved vendors yet.")
    else:
        st.dataframe(vdf[[
            "Vendor_Name","Category","Short_Description","Contact","Phone","Address","Expires_On"
        ]], use_container_width=True)

    st.markdown("---")
    st.markdown("### Suggest a vendor")
    if "me" not in st.session_state:
        st.info("Sign in as a verified member (email) in Directory tab before submitting.")
    else:
        with st.form("ven_submit"):
            c1,c2 = st.columns(2)
            with c1:
                vname = st.text_input("Vendor Name *")
                vcat  = st.text_input("Category")
                vcontact = st.text_input("Contact person")
            with c2:
                vphone = st.text_input("Phone")
                vaddr  = st.text_input("Address")
                vdur   = st.selectbox("Listing duration (days)", [7,15,30,45,60,90])
            vshort = st.text_area("Short Description *", max_chars=300)
            i1,i2,i3 = st.columns(3)
            with i1: vu1 = st.text_input("Image URL 1")
            with i2: vu2 = st.text_input("Image URL 2")
            with i3: vu3 = st.text_input("Image URL 3")

            ok = st.form_submit_button("Submit vendor", type="primary")
            if ok:
                save_vendor(dict(
                    Member_Email=st.session_state.me,
                    Vendor_Name=vname, Category=vcat, Contact=vcontact,
                    Phone=vphone, Address=vaddr, Short_Description=vshort,
                    Image_URL_1=vu1, Image_URL_2=vu2, Image_URL_3=vu3,
                    Duration_Days=int(vdur)
                ))
                st.success("Submitted! Admin will review & approve.")

# =========================== TAB 4: SUPPORT ===========================
with tabs[4]:
    st.subheader("Support")
    st.caption("Replies may take 7–15 days.")
    with st.form("supp"):
        em = st.text_input("Your Email")
        sub = st.text_input("Subject")
        msg = st.text_area("Message", height=120)
        ok = st.form_submit_button("Create Ticket", type="primary")
        if ok:
            save_ticket(em, sub, msg)
            st.success("Thanks! Ticket submitted.")

# =========================== TAB 5: REGISTER (Members) ===========================
with tabs[5]:
    st.subheader("Register as Resident or Tenant")
    with st.form("reg"):
        c1,c2,c3 = st.columns(3)
        with c1:
            rtype = st.selectbox("Resident Type", ["Resident","Tenant"])
            phase = st.selectbox("Phase", ["Atmosphere 1","Atmosphere 2"])
            wing  = st.selectbox("Wing", list("ABCDEFGH"))
        with c2:
            flat  = st.text_input("Flat No (e.g., 1203)")
            name  = st.text_input("Full Name")
            email = st.text_input("Email")
        with c3:
            phone = st.text_input("Phone")
        ok = st.form_submit_button("Register", type="primary")
        if ok:
            save_member(dict(
                Resident_Type=rtype, Phase=phase, Wing=wing, Flat_No=flat,
                Name=name, Email=email, Phone=phone
            ))
            st.success("Registered! Wait for admin approval.")

# =========================== TAB 6: ADMIN ===========================
with tabs[6]:
    admin_login_ui()
    if not is_admin():
        st.warning("Admin only.")
    else:
        st.subheader("🛠️ Admin Panel")

        # Quick add to Showcase
        with st.expander("Add Showcase (image/video)"):
            t = st.text_input("Title")
            typ = st.selectbox("Type", ["image","video"])
            url = st.text_input("URL (image link or video link)")
            by  = st.text_input("Posted by")
            notes = st.text_area("Notes")
            approve_now = st.checkbox("Approve now?", value=True)
            if st.button("Add to Showcase", type="primary"):
                save_showcase(dict(Title=t, Type=typ, URL=url, Posted_By=by, Notes=notes), approve=approve_now)
                st.success("Added to Showcase.")

        st.markdown("### Approvals")

        # Members — Pending
        dfm = ws_to_df(ws_members)
        pend_m = dfm[(dfm["Approved"].str.upper() != "TRUE")] if not dfm.empty else pd.DataFrame()
        with st.expander(f"Members (pending: {len(pend_m)})", expanded=False):
            if pend_m.empty:
                st.info("No pending members.")
            else:
                for _, row in pend_m.iterrows():
                    with st.expander(f"{row.get('Name','')} · {row.get('Email','')}", expanded=False):
                        st.write(dict(row))
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Approve member", key=f"m_ap_{row['Member_ID']}"):
                                approve_by_id(ws_members, "Member_ID", row["Member_ID"], MEM_HEADERS)
                                st.success("Approved.")
                                _safe_rerun()
                        with c2:
                            if st.button("Reject member", key=f"m_rj_{row['Member_ID']}"):
                                reject_by_id(ws_members, "Member_ID", row["Member_ID"], MEM_HEADERS)
                                st.warning("Rejected.")
                                _safe_rerun()

        # Business Listings — Pending
        dfd = ws_to_df(ws_dir)
        pend_d = dfd[(dfd["Approved"].str.upper() != "TRUE")] if not dfd.empty else pd.DataFrame()
        with st.expander(f"Business Listings (pending: {len(pend_d)})", expanded=False):
            if pend_d.empty:
                st.info("No pending listings.")
            else:
                for _, row in pend_d.iterrows():
                    with st.expander(f"{row.get('Business_Name','(no name)')} · {row.get('Member_Email','')}", expanded=False):
                        st.write(dict(row))
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("Approve listing", key=f"d_ap_{row['Listing_ID']}"):
                                extra = {}
                                try:
                                    days = int(row.get("Duration_Days","0") or "0")
                                    if days > 0:
                                        extra["Expires_On"] = (dt.date.today() + dt.timedelta(days=days)).isoformat()
                                except Exception:
                                    pass
                                approve_by_id(ws_dir, "Listing_ID", row["Listing_ID"], DIR_HEADERS, extra_updates=extra)
                                st.success("Approved.")
                                _safe_rerun()
                        with c2:
                            if st.button("Reject listing", key=f"d_rj_{row['Listing_ID']}"):
                                reject_by_id(ws_dir, "Listing_ID", row["Listing_ID"], DIR_HEADERS)
                                st.warning("Rejected.")
                                _safe_rerun()
                        with c3:
                            add_days = st.number_input("Extend by days", min_value=0, max_value=365, value=0, key=f"d_ext_{row['Listing_ID']}")
                            if st.button("Apply extension", key=f"d_ext_btn_{row['Listing_ID']}"):
                                extend_expiry(ws_dir, "Listing_ID", row["Listing_ID"], DIR_HEADERS, int(add_days))
                                st.success("Expiry extended.")
                                _safe_rerun()

        # Vendors — Pending
        dfv = ws_to_df(ws_ven)
        pend_v = dfv[(dfv["Approved"].str.upper() != "TRUE")] if not dfv.empty else pd.DataFrame()
        with st.expander(f"Vicinity Vendors (pending: {len(pend_v)})", expanded=False):
            if pend_v.empty:
                st.info("No pending vendor submissions.")
            else:
                for _, row in pend_v.iterrows():
                    with st.expander(f"{row.get('Vendor_Name','Vendor')} · {row.get('Member_Email','')}", expanded=False):
                        st.write(dict(row))
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("Approve vendor", key=f"v_ap_{row['Vendor_ID']}"):
                                extra = {}
                                try:
                                    days = int(row.get("Duration_Days","0") or "0")
                                    if days > 0:
                                        extra["Expires_On"] = (dt.date.today() + dt.timedelta(days=days)).isoformat()
                                except Exception:
                                    pass
                                approve_by_id(ws_ven, "Vendor_ID", row["Vendor_ID"], VEN_HEADERS, extra_updates=extra)
                                st.success("Approved.")
                                _safe_rerun()
                        with c2:
                            if st.button("Reject vendor", key=f"v_rj_{row['Vendor_ID']}"):
                                reject_by_id(ws_ven, "Vendor_ID", row["Vendor_ID"], VEN_HEADERS)
                                st.warning("Rejected.")
                                _safe_rerun()
                        with c3:
                            add_days = st.number_input("Extend by days", min_value=0, max_value=365, value=0, key=f"v_ext_{row['Vendor_ID']}")
                            if st.button("Apply extension", key=f"v_ext_btn_{row['Vendor_ID']}"):
                                extend_expiry(ws_ven, "Vendor_ID", row["Vendor_ID"], VEN_HEADERS, int(add_days))
                                st.success("Expiry extended.")
                                _safe_rerun()

        st.markdown("### Export CSV")
        col1, col2, col3 = st.columns(3)
        if not dfd.empty:
            col1.download_button("Businesses.csv", dfd.to_csv(index=False).encode(), "businesses.csv")
        if not dfv.empty:
            col2.download_button("Vendors.csv", dfv.to_csv(index=False).encode(), "vendors.csv")
        if not dfm.empty:
            col3.download_button("Members.csv", dfm.to_csv(index=False).encode(), "members.csv")





