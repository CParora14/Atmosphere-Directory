# Atmosphere Society — Community Hub
# Full one-file app

from __future__ import annotations
import uuid, datetime as dt
from typing import Optional, Dict, List

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# ===================== BRAND / THEME =====================
PRIMARY   = "#18B8CB"
PRIMARY_2 = "#6BC6FF"
INK       = "#0C2AAA"
CARD_BG   = "#0E1C2B"
PAGE_BG   = "#0A1522"

LOGO_URL     = st.secrets.get("LOGO_URL", "")       # optional
BACKDROP_URL = st.secrets.get("BACKDROP_URL", "")   # optional

st.set_page_config(
    page_title="Atmosphere Society — Community Hub",
    page_icon="🏡", layout="wide", initial_sidebar_state="collapsed",
)

backdrop_css = f", url('{BACKDROP_URL}')" if BACKDROP_URL else ""
st.markdown(
    f"""
<style>
:root {{
  --brand:{PRIMARY}; --brand2:{PRIMARY_2}; --ink:{INK}; --card:{CARD_BG}; --page:{PAGE_BG};
}}
html, body, [data-testid="stAppViewContainer"] {{
  background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0.65)) {backdrop_css};
  background-size: cover; background-attachment: fixed; background-position: center;
  color:#EAF2FA!important;
}}
.block-container {{ padding-top:1rem; padding-bottom:2rem; max-width:1200px; }}
[data-testid="stHeader"] {{ background: transparent; }}
.stTabs [data-baseweb="tab"] {{ color:#EAF2FA; font-weight:600; }}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(90deg, var(--brand), var(--brand2))!important;
  color:#001018!important; border-radius:10px;
}}
.banner {{ width:100%; padding:18px 22px; border-radius:18px;
          background: linear-gradient(135deg, {PRIMARY} 0%, {PRIMARY_2} 100%);
          color:#001018; box-shadow:0 10px 30px rgba(0,0,0,.25) }}
.card {{ background:var(--card); border-radius:16px; padding:16px 18px;
         border:1px solid rgba(255,255,255,.06) }}
.badge {{ padding:2px 8px; border-radius:100px; font-size:12px;
         background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.08) }}
.small-dim {{ color:#b9c8d8; font-size:12px; }}
</style>
""",
    unsafe_allow_html=True,
)

# ===================== UTILS / CONSTANTS =====================
TRUE_LIKE = {"true", "yes", "y", "1"}

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _safe_rerun():
    try: st.rerun()
    except Exception:
        try: st.experimental_rerun()
        except Exception: pass

def clear_data_cache():
    try: st.cache_data.clear()
    except Exception: pass

# ===================== SECRETS =====================
APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
SHEET_URL    = st.secrets.get("SHEET_URL", "")

# ===================== GOOGLE AUTH + SHEET (low-read) =====================
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
        st.error("SHEET_URL missing in Secrets."); st.stop()
    return _gc().open_by_url(SHEET_URL)

with st.spinner("Connecting to Google Sheets…"):
    sh = _open_sheet()

@st.cache_resource(show_spinner=False)
def _list_titles(sh) -> list[str]:
    try:
        return [ws.title for ws in sh.worksheets()]
    except Exception:
        return []

def ensure_ws(sh, title: str, headers: list[str]):
    """
    Open worksheet named `title`. Create it if missing.
    Only one metadata read via _list_titles to avoid 429.
    """
    titles = _list_titles(sh)
    try:
        if title in titles:
            return sh.worksheet(title)
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(26, len(headers)))
        ws.update("A1", [headers])  # write headers without reading
        try: _list_titles.clear()
        except Exception: pass
        return ws
    except APIError as e:
        st.error(f"Google Sheets error for tab '{title}'.")
        st.code(str(e)); st.stop()

# ===================== HEADERS =====================
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

# Prefill categories/subcategories (edit freely)
CATEGORIES: Dict[str, List[str]] = {
    "Food & Catering": ["Home Tiffin","Catering","Bakery","Snacks"],
    "Education": ["Tuition","Coaching","Music","Dance","Art/Craft","Languages"],
    "Wellness": ["Yoga","Fitness Trainer","Physiotherapy","Salon/Beautician","Massage"],
    "Home Services": ["Electrician","Plumber","Carpenter","AC Service","Cleaning","Pest Control"],
    "Events": ["Decoration","Photography","Videography","Make-up","Anchoring","DJ"],
    "Retail": ["Clothing","Accessories","Gifts","Stationery"],
    "Tech": ["Laptop Repair","Mobile Repair","Software/IT Services","Web Design"],
    "Other": ["Other"]
}

# Ensure tabs exist
ws_members  = ensure_ws(sh, "Members",           MEM_HEADERS)
ws_dir      = ensure_ws(sh, "Business_Listings", DIR_HEADERS)
ws_ven      = ensure_ws(sh, "Vicinity_Vendors",  VEN_HEADERS)
ws_show     = ensure_ws(sh, "Showcase",          SHOW_HEADERS)
ws_rate     = ensure_ws(sh, "Ratings",           RATE_HEADERS)
ws_supp     = ensure_ws(sh, "Support_Tickets",   SUPP_HEADERS)

# ===================== READ HELPERS (cache) =====================
@st.cache_data(ttl=45)
def read_df(tab: str) -> pd.DataFrame:
    try:
        ws = sh.worksheet(tab)
        vals = ws.get_all_values()
        if not vals: return pd.DataFrame()
        if len(vals) == 1: return pd.DataFrame(columns=vals[0])
        return pd.DataFrame(vals[1:], columns=vals[0])
    except Exception:
        return pd.DataFrame()

def df_public(df: pd.DataFrame, approved_col="Approved", expires_col: Optional[str]="Expires_On") -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    d = df.copy()
    if approved_col in d.columns:
        d["_ok"] = d[approved_col].astype(str).str.strip().str.lower().isin(TRUE_LIKE)
        d = d[d["_ok"]==True].drop(columns=["_ok"])
    if expires_col and expires_col in d.columns:
        d["_exp"] = pd.to_datetime(d[expires_col], errors="coerce", utc=True)
        now = pd.Timestamp.utcnow()
        d = d[(d["_exp"].isna()) | (d["_exp"] >= now)].drop(columns=["_exp"])
    return d.reset_index(drop=True)

# ===================== ADMIN AUTH =====================
def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))

def admin_login_ui():
    if is_admin(): return
    with st.expander("🔐 Admin login", expanded=False):
        u = st.text_input("Username", key="adm_user")
        p = st.text_input("Password", type="password", key="adm_pass")
        if st.button("Sign in", type="primary", key="adm_btn"):
            if u.strip()==APP_USERNAME and p==APP_PASSWORD:
                st.session_state.is_admin = True
                st.success("✅ Admin logged in."); _safe_rerun()
            else:
                st.error("❌ Wrong credentials.")

# ===================== WRITE HELPERS =====================
def _append_row(ws, data: dict, headers: list[str]):
    ws.append_row([str(data.get(h,"")) for h in headers])

def member_is_approved(email: str) -> bool:
    if not email: return False
    df = read_df("Members")
    if df.empty or "Email" not in df.columns or "Approved" not in df.columns: return False
    m = df[df["Email"].str.strip().str.lower()==email.strip().lower()]
    if m.empty: return False
    return m["Approved"].astype(str).str.strip().str.lower().isin(TRUE_LIKE).any()

def save_member(d: dict):
    data = dict(
        Member_ID=f"M-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="",
        Resident_Type=d.get("Resident_Type",""), Phase=d.get("Phase",""),
        Wing=d.get("Wing",""), Flat_No=d.get("Flat_No",""),
        Name=d.get("Name",""), Email=d.get("Email",""), Phone=d.get("Phone",""),
    )
    _append_row(ws_members, data, MEM_HEADERS); clear_data_cache()

def save_directory(d: dict):
    days = int(d.get("Duration_Days",0) or 0)
    data = dict(
        Listing_ID=f"D-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="",
        Member_Email=d.get("Member_Email",""),
        Resident_Type=d.get("Resident_Type",""),
        Phase=d.get("Phase",""), Wing=d.get("Wing",""), Flat_No=d.get("Flat_No",""),
        Business_Name=d.get("Business_Name",""),
        Category=d.get("Category",""), Subcategory=d.get("Subcategory",""),
        Service_Type=d.get("Service_Type",""),
        Short_Description=d.get("Short_Description",""),
        Detailed_Description=d.get("Detailed_Description",""),
        Image_URL_1=d.get("Image_URL_1",""),
        Image_URL_2=d.get("Image_URL_2",""),
        Image_URL_3=d.get("Image_URL_3",""),
        Duration_Days=str(days),
        Expires_On=(dt.date.today()+dt.timedelta(days=days)).isoformat() if days>0 else ""
    )
    _append_row(ws_dir, data, DIR_HEADERS); clear_data_cache()

def save_vendor(d: dict):
    days = int(d.get("Duration_Days",0) or 0)
    data = dict(
        Vendor_ID=f"V-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="",
        Member_Email=d.get("Member_Email",""),
        Vendor_Name=d.get("Vendor_Name",""), Contact=d.get("Contact",""),
        Phone=d.get("Phone",""), Address=d.get("Address",""),
        Category=d.get("Category",""), Short_Description=d.get("Short_Description",""),
        Image_URL_1=d.get("Image_URL_1",""), Image_URL_2=d.get("Image_URL_2",""), Image_URL_3=d.get("Image_URL_3",""),
        Duration_Days=str(days),
        Expires_On=(dt.date.today()+dt.timedelta(days=days)).isoformat() if days>0 else ""
    )
    _append_row(ws_ven, data, VEN_HEADERS); clear_data_cache()

def save_ticket(email: str, subject: str, message: str):
    data = dict(Ticket_ID=f"T-{uuid.uuid4().hex[:8].upper()}",
                When=_now_iso(), Email=email, Subject=subject, Message=message, Status="Open")
    _append_row(ws_supp, data, SUPP_HEADERS)

def save_showcase(d: dict, approve=False):
    data = dict(
        Show_ID=f"S-{uuid.uuid4().hex[:8].upper()}",
        Submitted_At=_now_iso(), Approved="TRUE" if approve else "",
        Title=d.get("Title",""), Type=d.get("Type","image"), URL=d.get("URL",""),
        Posted_By=d.get("Posted_By",""), Notes=d.get("Notes",""),
    )
    _append_row(ws_show, data, SHOW_HEADERS); clear_data_cache()

def save_rating(listing_id: str, stars: int, comment: str, email: str):
    data = dict(When=_now_iso(), Type="Business", Target_ID=listing_id,
                Stars=str(stars), Comment=comment, Rater_Email=email)
    _append_row(ws_rate, data, RATE_HEADERS)

# ===================== ADMIN ACTION HELPERS =====================
def _header_map(ws, defaults: list[str]) -> dict[str,int]:
    try: row1 = ws.row_values(1) or defaults
    except APIError: row1 = defaults
    return {h:i+1 for i,h in enumerate(row1)}

def _find_row_by_id(ws, id_col_idx: int, id_value: str) -> Optional[int]:
    try: col = ws.col_values(id_col_idx)
    except APIError: col = []
    for i,v in enumerate(col, start=1):
        if str(v).strip()==str(id_value).strip():
            return i
    return None

def approve_by_id(ws, id_col: str, id_val: str, defaults: list[str], extra: dict|None=None):
    hdr = _header_map(ws, defaults); id_idx = hdr.get(id_col); ap_idx = hdr.get("Approved")
    if not id_idx or not ap_idx: return
    row = _find_row_by_id(ws, id_idx, id_val); if row is None: return
    ws.update_cell(row, ap_idx, "TRUE")
    if extra:
        for k,v in extra.items():
            idx = hdr.get(k)
            if idx: ws.update_cell(row, idx, v)
    clear_data_cache()

def reject_by_id(ws, id_col: str, id_val: str, defaults: list[str]):
    hdr = _header_map(ws, defaults); id_idx = hdr.get(id_col); ap_idx = hdr.get("Approved")
    if not id_idx or not ap_idx: return
    row = _find_row_by_id(ws, id_idx, id_val); if row is None: return
    ws.update_cell(row, ap_idx, "REJECTED"); clear_data_cache()

def extend_expiry(ws, id_col: str, id_val: str, defaults: list[str], extra_days: int):
    hdr = _header_map(ws, defaults); id_idx = hdr.get(id_col); ex_idx = hdr.get("Expires_On")
    if not id_idx or not ex_idx: return
    row = _find_row_by_id(ws, id_idx, id_val); if row is None: return
    current = ws.cell(row, ex_idx).value or dt.date.today().isoformat()
    try: cur = dt.date.fromisoformat(current)
    except Exception: cur = dt.date.today()
    ws.update_cell(row, ex_idx, (cur+dt.timedelta(days=int(extra_days or 0))).isoformat())
    clear_data_cache()

# ===================== HEADER UI + MEMBER BAR =====================
def header():
    a,b = st.columns([1,10])
    with a:
        if LOGO_URL: st.image(LOGO_URL, use_container_width=True)
        else: st.markdown("<div class='badge'>Atmosphere</div>", unsafe_allow_html=True)
    with b:
        st.markdown(
            "<div class='banner'><h2 style='margin:0'>Atmosphere Society — Community Hub</h2>"
            "<div>Showcase • Directory • Vendors • Support</div></div>", unsafe_allow_html=True
        )
header()

def member_bar():
    with st.expander("✅ Member verification (for submissions & ratings)", expanded=False):
        email_in = st.text_input("Your Email (member)", key="me_email_top").strip()
        if st.button("Set as me", key="me_set_top"):
            if member_is_approved(email_in):
                st.session_state.me = email_in
                st.success("You’re set as a verified member.")
            else:
                st.warning("Not found or not approved yet. Register or wait for approval.")
member_bar()

# ===================== NAV =====================
tabs = st.tabs(["🏠 Showcase", "ℹ️ About", "📇 Directory",
                "🛒 Vicinity Vendors", "🆘 Support", "🧑‍🤝‍🧑 Register", "🛠️ Admin"])

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
                    f"**{r.get('Title','')}**  ·  <span class='badge'>{r.get('Type','')}</span>  "
                    f"<span class='small-dim'>by {r.get('Posted_By','')}</span>", unsafe_allow_html=True
                )
                url = (r.get("URL","") or "").strip()
                if r.get("Type","").lower()=="video" and url: st.video(url)
                elif url: st.image(url, use_container_width=True, caption=r.get("Notes",""))

# ---- About ----
with tabs[1]:
    st.subheader("About the App")
    st.markdown("""
**What is this?**  
A simple, community-first hub for *Atmosphere Society* residents & tenants.

**You can**
- Browse the **Directory** of resident-run businesses (approved).
- Suggest **Vicinity Vendors** that help the community.
- See the **Showcase** wall for ads/promotions (admin-posted).
- Submit a **Support Ticket** if you need help.

**Listings**
- Submissions go to **Admin Approval**.
- Choose listing period: **7 / 15 / 30 / 45 / 60 / 90 days**.
- Expired listings stop showing automatically; Admin can extend.
""")

# ---- Directory ----
with tabs[2]:
    st.subheader("Resident Business Directory")
    df = df_public(read_df("Business_Listings"))
    if df.empty:
        st.info("No approved listings yet.")
    else:
        c = st.columns(5)
        with c[0]: f_phase = st.selectbox("Phase", ["All"]+sorted(df["Phase"].dropna().unique().tolist()))
        with c[1]: f_cat   = st.selectbox("Category", ["All"]+sorted(df["Category"].dropna().unique().tolist()))
        with c[2]: f_srv   = st.selectbox("Service Type", ["All"]+sorted(df["Service_Type"].dropna().unique().tolist()))
        with c[3]: f_wing  = st.selectbox("Wing", ["All"]+sorted(df["Wing"].dropna().unique().tolist()))
        with c[4]: q       = st.text_input("Search", key="dir_search")

        view = df.copy()
        if f_phase!="All": view = view[view["Phase"]==f_phase]
        if f_cat  !="All": view = view[view["Category"]==f_cat]
        if f_srv  !="All": view = view[view["Service_Type"]==f_srv]
        if f_wing !="All": view = view[view["Wing"]==f_wing]
        if q:
            qc = q.lower()
            view = view[view.apply(lambda r: qc in (" ".join(map(str,r.values))).lower(), axis=1)]

        st.dataframe(view[[
            "Business_Name","Category","Subcategory","Service_Type",
            "Short_Description","Phase","Wing","Flat_No","Resident_Type","Expires_On","Listing_ID"
        ]], use_container_width=True, hide_index=True)

        st.markdown("#### Rate a business")
        if "me" not in st.session_state:
            st.info("Sign in above to rate.")
        else:
            if not view.empty:
                options = [f"{row.Business_Name} — {row.Listing_ID}" for _,row in view.iterrows()]
                choice  = st.selectbox("Select listing", options, key="rate_choice") if options else None
                stars   = st.slider("Stars", 1, 5, 5, key="rate_stars")
                comment = st.text_input("Short comment (optional)", key="rate_comment")
                if st.button("Submit rating", key="rate_submit"):
                    if choice:
                        listing_id = choice.split("—")[-1].strip()
                        save_rating(listing_id, stars, comment, st.session_state.me)
                        st.success("Thanks for your rating!")

    st.markdown("---")
    st.markdown("### Submit your business")
    if "me" not in st.session_state:
        st.info("Sign in as a verified member (email) above to submit.")
    else:
        with st.form("dir_submit_form"):
            c1,c2,c3 = st.columns(3)
            with c1:
                phase = st.selectbox("Phase", ["Atmosphere 1","Atmosphere 2"], key="dir_phase")
                wing  = st.selectbox("Wing", list("ABCDEFGH"), key="dir_wing")
                flat  = st.text_input("Flat No (e.g., 1203)", key="dir_flat")
            with c2:
                resident_type = st.selectbox("Resident Type", ["Resident","Tenant"], key="dir_rtype")
                cat_list = list(CATEGORIES.keys())
                category = st.selectbox("Category", cat_list, key="dir_cat")
                subcategory = st.selectbox("Subcategory", CATEGORIES.get(category, ["Other"]), key="dir_subcat")
            with c3:
                service  = st.text_input("Service Type", key="dir_service")
                duration = st.selectbox("Listing duration (days)", [7,15,30,45,60,90], key="dir_dur")

            b_name = st.text_input("Business Name *", key="dir_bname")
            short  = st.text_area("Short Description *", max_chars=200, key="dir_short")
            detail = st.text_area("Detailed Description", max_chars=1000, key="dir_detail")
            i1,i2,i3 = st.columns(3)
            with i1: u1 = st.text_input("Image URL 1", key="dir_u1")
            with i2: u2 = st.text_input("Image URL 2", key="dir_u2")
            with i3: u3 = st.text_input("Image URL 3", key="dir_u3")
            ok = st.form_submit_button("Submit for approval", type="primary")
            if ok:
                save_directory(dict(
                    Member_Email=st.session_state.me, Resident_Type=resident_type,
                    Phase=phase, Wing=wing, Flat_No=flat, Business_Name=b_name,
                    Category=category, Subcategory=subcategory, Service_Type=service,
                    Short_Description=short, Detailed_Description=detail,
                    Image_URL_1=u1, Image_URL_2=u2, Image_URL_3=u3, Duration_Days=int(duration)
                ))
                st.success("Submitted! Admin will review & approve.")

# ---- Vendors ----
with tabs[3]:
    st.subheader("Vicinity Vendors")
    vdf = df_public(read_df("Vicinity_Vendors"))
    if vdf.empty:
        st.info("No approved vendors yet.")
    else:
        st.dataframe(vdf[[
            "Vendor_Name","Category","Short_Description","Contact","Phone","Address","Expires_On","Vendor_ID"
        ]], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Suggest a vendor")
    if "me" not in st.session_state:
        st.info("Sign in as a verified member (email) in Directory tab before submitting.")
    else:
        with st.form("ven_submit_form"):
            c1,c2 = st.columns(2)
            with c1:
                vname   = st.text_input("Vendor Name *", key="ven_name")
                vcat    = st.selectbox("Category", list(CATEGORIES.keys()), key="ven_cat")
                vcontact= st.text_input("Contact person", key="ven_contact")
            with c2:
                vphone  = st.text_input("Phone", key="ven_phone")
                vaddr   = st.text_input("Address", key="ven_addr")
                vdur    = st.selectbox("Listing duration (days)", [7,15,30,45,60,90], key="ven_dur")
            vshort = st.text_area("Short Description *", max_chars=300, key="ven_short")
            i1,i2,i3 = st.columns(3)
            with i1: vu1 = st.text_input("Image URL 1", key="ven_u1")
            with i2: vu2 = st.text_input("Image URL 2", key="ven_u2")
            with i3: vu3 = st.text_input("Image URL 3", key="ven_u3")
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
    with st.form("supp_form"):
        em  = st.text_input("Your Email", key="sup_email")
        sub = st.text_input("Subject", key="sup_subject")
        msg = st.text_area("Message", height=120, key="sup_msg")
        ok  = st.form_submit_button("Create Ticket", type="primary")
        if ok:
            save_ticket(em, sub, msg); st.success("Thanks! Ticket submitted.")

# ---- Register ----
with tabs[5]:
    st.subheader("Register as Resident or Tenant")
    with st.form("reg_form"):
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

        with st.expander("Add Showcase (image/video)"):
            t = st.text_input("Title", key="sc_title")
            typ = st.selectbox("Type", ["image","video"], key="sc_type")
            url = st.text_input("URL (image or video link)", key="sc_url")
            by  = st.text_input("Posted by", key="sc_by")
            notes = st.text_area("Notes", key="sc_notes")
            approve_now = st.checkbox("Approve now?", value=True, key="sc_ok")
            if st.button("Add to Showcase", type="primary", key="sc_submit"):
                save_showcase(dict(Title=t, Type=typ, URL=url, Posted_By=by, Notes=notes), approve=approve_now)
                st.success("Added to Showcase.")

        st.markdown("### Approvals")

        dfm = read_df("Members")
        dfd = read_df("Business_Listings")
        dfv = read_df("Vicinity_Vendors")

        # Members
        pend_m = dfm[dfm["Approved"].astype(str).str.upper()!="TRUE"] if not dfm.empty else pd.DataFrame()
        with st.expander(f"Members (pending: {len(pend_m)})", expanded=False):
            if pend_m.empty: st.info("No pending members.")
            else:
                for _, row in pend_m.iterrows():
                    with st.expander(f"{row.get('Name','')} · {row.get('Email','')}"):
                        st.write(dict(row))
                        c1,c2 = st.columns(2)
                        with c1:
                            if st.button("Approve member", key=f"m_ap_{row['Member_ID']}"):
                                approve_by_id(ws_members,"Member_ID",row["Member_ID"],MEM_HEADERS)
                                st.success("Approved."); _safe_rerun()
                        with c2:
                            if st.button("Reject member", key=f"m_rj_{row['Member_ID']}"):
                                reject_by_id(ws_members,"Member_ID",row["Member_ID"],MEM_HEADERS)
                                st.warning("Rejected."); _safe_rerun()

        # Business Listings
        pend_d = dfd[dfd["Approved"].astype(str).str.upper()!="TRUE"] if not dfd.empty else pd.DataFrame()
        with st.expander(f"Business Listings (pending: {len(pend_d)})", expanded=False):
            if pend_d.empty: st.info("No pending listings.")
            else:
                for _, row in pend_d.iterrows():
                    with st.expander(f"{row.get('Business_Name','(no name)')} · {row.get('Member_Email','')}"):
                        st.write(dict(row))
                        c1,c2,c3 = st.columns(3)
                        with c1:
                            if st.button("Approve listing", key=f"d_ap_{row['Listing_ID']}"):
                                try:
                                    days = int(row.get("Duration_Days","0") or "0")
                                    extra = {"Expires_On": (dt.date.today()+dt.timedelta(days=days)).isoformat()} if days>0 else {}
                                except Exception:
                                    extra = {}
                                approve_by_id(ws_dir,"Listing_ID",row["Listing_ID"],DIR_HEADERS,extra)
                                st.success("Approved."); _safe_rerun()
                        with c2:
                            if st.button("Reject listing", key=f"d_rj_{row['Listing_ID']}"):
                                reject_by_id(ws_dir,"Listing_ID",row["Listing_ID"],DIR_HEADERS)
                                st.warning("Rejected."); _safe_rerun()
                        with c3:
                            more = st.number_input("Extend by days",0,365,0,key=f"d_ext_{row['Listing_ID']}")
                            if st.button("Apply extension", key=f"d_ext_btn_{row['Listing_ID']}"):
                                extend_expiry(ws_dir,"Listing_ID",row["Listing_ID"],DIR_HEADERS,int(more))
                                st.success("Expiry extended."); _safe_rerun()

        # Vendors
        pend_v = dfv[dfv["Approved"].astype(str).str.upper()!="TRUE"] if not dfv.empty else pd.DataFrame()
        with st.expander(f"Vicinity Vendors (pending: {len(pend_v)})", expanded=False):
            if pend_v.empty: st.info("No pending vendor submissions.")
            else:
                for _, row in pend_v.iterrows():
                    with st.expander(f"{row.get('Vendor_Name','Vendor')} · {row.get('Member_Email','')}"):
                        st.write(dict(row))
                        c1,c2,c3 = st.columns(3)
                        with c1:
                            if st.button("Approve vendor", key=f"v_ap_{row['Vendor_ID']}"):
                                try:
                                    days = int(row.get("Duration_Days","0") or "0")
                                    extra = {"Expires_On": (dt.date.today()+dt.timedelta(days=days)).isoformat()} if days>0 else {}
                                except Exception:
                                    extra = {}
                                approve_by_id(ws_ven,"Vendor_ID",row["Vendor_ID"],VEN_HEADERS,extra)
                                st.success("Approved."); _safe_rerun()
                        with c2:
                            if st.button("Reject vendor", key=f"v_rj_{row['Vendor_ID']}"):
                                reject_by_id(ws_ven,"Vendor_ID",row["Vendor_ID"],VEN_HEADERS)
                                st.warning("Rejected."); _safe_rerun()
                        with c3:
                            more = st.number_input("Extend by days",0,365,0,key=f"v_ext_{row['Vendor_ID']}")
                            if st.button("Apply extension", key=f"v_ext_btn_{row['Vendor_ID']}"):
                                extend_expiry(ws_ven,"Vendor_ID",row["Vendor_ID"],VEN_HEADERS,int(more))
                                st.success("Expiry extended."); _safe_rerun()

        st.markdown("### Export CSV")
        if not dfd.empty: st.download_button("Businesses.csv", dfd.to_csv(index=False).encode(), "businesses.csv")
        if not dfv.empty: st.download_button("Vendors.csv",   dfv.to_csv(index=False).encode(), "vendors.csv")
        if not dfm.empty: st.download_button("Members.csv",   dfm.to_csv(index=False).encode(), "members.csv")
