# Atmosphere Society — Community Hub
# Showcase • Directory • Vendors • Support
# One-file app – paste over your streamlit_app.py

from __future__ import annotations
import re, time, uuid, math, datetime as dt
from typing import List, Tuple

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials

# ------------------------------ THEME / BRANDING ------------------------------
PRIMARY   = "#18B8CB"   # brand teal
PRIMARY_2 = "#6BC6FF"   # light blue
INK       = "#0C2AAA"   # deep ink
CARD_BG   = "#0E1C2B"   # dark card
PAGE_BG   = "#0A1522"   # darker page

LOGO_URL = st.secrets.get("LOGO_URL", "")  # optional: put a public URL in secrets

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
.stTabs [data-baseweb="tab"] {{
  color: #EAF2FA; font-weight: 600;
}}
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
.kpi {{ display:flex; gap:16px; flex-wrap:wrap; }}
.kpi > div {{
  background: var(--card); border:1px solid rgba(255,255,255,.06);
  border-radius:14px; padding:14px 16px; min-width: 180px;
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

# ---------------------------- AUTH: ADMIN (Secrets) ---------------------------
# --------------------------- AUTH / ADMIN (Secrets) ---------------------------
APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

def _safe_rerun():
    """Works on both new/old Streamlit versions without crashing."""
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def is_admin() -> bool:
    """True if admin session flag is set."""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    return st.session_state.is_admin

def admin_login_ui():
    """
    Small login box that flips the admin flag on success.
    Call this anywhere you want to prompt for admin login.
    """
    if is_admin():
        st.success("Admin mode enabled.")
        return

    with st.expander("🔐 Admin login", expanded=False):
        u = st.text_input("Username", key="adm_u")
        p = st.text_input("Password", type="password", key="adm_p")
        if st.button("Sign in", type="primary"):
            if u.strip() == APP_USERNAME and p == APP_PASSWORD:
                st.session_state.is_admin = True
                st.success("✅ Logged in.")
                _safe_rerun()
            else:
                st.error("❌ Wrong credentials.")

def admin_tab():
    """
    Example wrapper you can wire to your Admin page/tab.
    It first shows the login. If not admin yet, we stop.
    """
    # show login if not already admin
    admin_login_ui()
    if not is_admin():
        st.stop()

    st.subheader("🛠️ Admin Panel")
    st.info("Admin actions will appear here once you’re logged in.")

    # ---- MEMBERS (approve registrations) ----
    st.markdown("### Members — Pending")
    dfm = ws_to_df(ws_members)

    if dfm.empty:
        st.info("No member records yet.")
    else:
        pend_m = dfm[dfm["Approved"].astype(str).str.upper() != "TRUE"]
        if pend_m.empty:
            st.success("No pending members.")
        else:
            for _, row in pend_m.iterrows():
                with st.expander(f"{row.get('Name','(no name)')} • {row.get('Email','')}"):
                    st.write(dict(row))
                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button("Approve member", key=f"m_ap_{row['Member_ID']}"):
                            approve_by_id(ws_members, "Member_ID", row["Member_ID"], MEM_HEADERS)
                            st.success("Approved.")
                            _safe_rerun()

                    with c2:
                        if st.button("Reject member", key=f"m_rj_{row['Member_ID']}"):
                            reject_by_id(ws_members, "Member_ID", row["Member_ID"])
                            st.warning("Rejected.")
                            _safe_rerun()

    st.divider()

    # ---- BUSINESS LISTINGS (approve / reject / extend) ----
    st.markdown("### Resident Business Listings — Pending")
    dfd = ws_to_df(ws_dir)

    if dfd.empty:
        st.info("No business listings yet.")
    else:
        pend_b = dfd[dfd["Approved"].astype(str).str.upper() != "TRUE"]
        if pend_b.empty:
            st.success("No pending business listings.")
        else:
            for _, row in pend_b.iterrows():
                with st.expander(f"{row.get('Business_Name','(no business)')} • {row.get('Member_Email','')}"):
                    st.write(dict(row))
                    c1, c2, c3 = st.columns(3)

                    with c1:
                        if st.button("Approve business", key=f"b_ap_{row['Listing_ID']}"):
                            approve_by_id(ws_dir, "Listing_ID", row["Listing_ID"], DIR_HEADERS)
                            st.success("Approved.")
                            _safe_rerun()

                    with c2:
                        if st.button("Reject business", key=f"b_rj_{row['Listing_ID']}"):
                            reject_by_id(ws_dir, "Listing_ID", row["Listing_ID"])
                            st.warning("Rejected.")
                            _safe_rerun()

                    with c3:
                        if st.button("Extend expiry", key=f"b_ex_{row['Listing_ID']}"):
                            extend_by_id(ws_dir, "Listing_ID", row["Listing_ID"], extra_days=30)
                            st.info("Extended by 30 days.")
                            _safe_rerun()

    # ---- VENDORS (approve / reject / extend) ----
    st.markdown("### Vicinity Vendors — Pending")
    dfv = ws_to_df(ws_ven)
    if dfv.empty:
        st.info("No vendors.")
    else:
        pend_v = dfv[dfv["Approved"].str.upper() != "TRUE"] if "Approved" in dfv else pd.DataFrame()
        if pend_v.empty:
            st.success("No pending vendor submissions.")
        else:
            for _, row in pend_v.iterrows():
                with st.expander(f"{row.get('Vendor_Name','')} · {row.get('Member_Email','')}"):
                    st.write(dict(row))
                    c1, c2, c3 = st.columns([1,1,2])
                    with c1:
                        if st.button("Approve", key=f"v_ap_{row['Vendor_ID']}"):
                            approve_by_id(ws_ven, "Vendor_ID", row["Vendor_ID"], VEN_HEADERS)
                            st.success("Approved.")
                            st.experimental_rerun()
                    with c2:
                        if st.button("Reject", key=f"v_rj_{row['Vendor_ID']}"):
                            reject_by_id(ws_ven, "Vendor_ID", row["Vendor_ID"], VEN_HEADERS)
                            st.warning("Rejected.")
                            st.experimental_rerun()
                    with c3:
                        extra = st.number_input("Extend days", min_value=0, max_value=365, value=0, key=f"v_ex_{row['Vendor_ID']}")
                        if st.button("Apply extension", key=f"v_ex_btn_{row['Vendor_ID']}"):
                            extend_expiry(ws_ven, "Vendor_ID", row["Vendor_ID"], VEN_HEADERS, extra)
                            st.success("Expiry extended.")
                            st.experimental_rerun()

    st.divider()
    st.markdown("### Export CSV")
    col1, col2, col3 = st.columns(3)
    with col1:
        if not dfd.empty:
            st.download_button("Businesses.csv", dfd.to_csv(index=False).encode(), "businesses.csv")
    with col2:
        if not dfv.empty:
            st.download_button("Vendors.csv", dfv.to_csv(index=False).encode(), "vendors.csv")
    with col3:
        if not dfm.empty:
            st.download_button("Members.csv", dfm.to_csv(index=False).encode(), "members.csv")

# --------------------------- GOOGLE SHEETS CONNECTION -------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource(show_spinner=False)
def get_client():
    sa_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

def open_sh(url:str):
    gc = get_client()
    return gc.open_by_url(url)

# ---------- safest worksheet opener: no reads, no header checks ----------
def ensure_ws(sh, title: str, headers: list[str]):
    """
    Return a worksheet called `title`. Create it if missing.
    DOES NOT read row values. You set headers manually in Sheets.
    """
    try:
        try:
            # Try to open existing sheet
            ws = sh.worksheet(title)
            return ws
        except WorksheetNotFound:
            # Create if missing (no reads here)
            ws = sh.add_worksheet(title=title, rows=1000, cols=max(26, len(headers)))
            return ws
    except APIError as e:
        st.error(f"Google Sheets API error opening/creating '{title}'.")
        st.code(str(e))
        st.stop()
def ws_to_df(ws) -> pd.DataFrame:
    vals = ws.get_all_values()
    if len(vals) <= 1:
        return pd.DataFrame(columns=[])
    return pd.DataFrame(vals[1:], columns=vals[0])

def append(ws, row:List[str]):
    ws.append_row(row)

# ---------------------------- REQUIRED SHEETS / HEADERS -----------------------
MEM_HEADERS = [
    "Member_ID","Submitted_At","Approved","Resident_Type","Phase","Wing","Flat_No","Name","Email","Phone"
]
DIR_HEADERS = [
    "Listing_ID","Submitted_At","Approved","Member_Email",
    "Resident_Type","Phase","Wing","Flat_No",
    "Business_Name","Category","Subcategory","Service_Type",
    "Short_Description","Detailed_Description",
    "Image_URL_1","Image_URL_2","Image_URL_3",
    "Duration_Days","Expires_On"
]
VEN_HEADERS = [
    "Vendor_ID","Submitted_At","Approved","Member_Email",
    "Vendor_Name","Contact","Phone","Address","Category",
    "Short_Description","Image_URL_1","Image_URL_2","Image_URL_3",
    "Duration_Days","Expires_On"
]
SHOW_HEADERS = [
    "Show_ID","Submitted_At","Approved","Title","Type","URL","Posted_By","Notes"
]
RATE_HEADERS = [
    "When","Type","Target_ID","Stars","Comment","Rater_Email"
]
SUPP_HEADERS = [
    "Ticket_ID","When","Email","Subject","Message","Status"
]

# ------------------------------ OPEN SPREADSHEET ------------------------------
SHEET_URL = st.secrets["SHEET_URL"]   # already in your secrets

with st.spinner("Connecting to Google Sheets…"):
    try:
        sh = open_sh(SHEET_URL)
    except Exception as e:
        st.error("Could not open spreadsheet. Check SHEET_URL and sharing to service account.")
        st.stop()

ws_members  = ensure_ws(sh, "Members",          MEM_HEADERS)
ws_dir      = ensure_ws(sh, "Business_Listings", DIR_HEADERS)
ws_ven      = ensure_ws(sh, "Vicinity_Vendors",  VEN_HEADERS)
ws_show     = ensure_ws(sh, "Showcase",          SHOW_HEADERS)
ws_rate     = ensure_ws(sh, "Ratings",           RATE_HEADERS)
ws_supp     = ensure_ws(sh, "Support_Tickets",   SUPP_HEADERS)

# ------------------------------- HELPERS --------------------------------------
# ---------- Admin helpers: header map, approve/reject, extend ----------
from datetime import date, timedelta
from gspread.exceptions import APIError

def _header_map(ws, default_headers: list[str]) -> dict:
    """Return header name -> column index (1-based). Falls back to defaults if read fails."""
    try:
        vals = ws.get_values('1:1')  # first row only
        headers = vals[0] if vals else default_headers
    except APIError:
        headers = default_headers
    return {h: i+1 for i, h in enumerate(headers)}

def _find_row_by_id(ws, id_col_idx: int, id_value: str) -> int:
    """Return row number (1-based) for the given id_value in the id column."""
    try:
        col_vals = ws.col_values(id_col_idx)  # reads only one column
        if id_value in col_vals:
            return col_vals.index(id_value) + 1
    except APIError:
        pass
    # Fallback: search anywhere
    cell = ws.find(id_value)
    return cell.row

def approve_by_id(ws, id_col_name: str, id_value: str, headers_defaults: list[str]):
    hdr = _header_map(ws, headers_defaults)
    id_col = hdr.get(id_col_name)
    appr_col = hdr.get("Approved")
    if not id_col or not appr_col:
        st.error("Headers missing: need both ID column and Approved.")
        return
    row = _find_row_by_id(ws, id_col, id_value)
    ws.update_cell(row, appr_col, "TRUE")

def reject_by_id(ws, id_col_name: str, id_value: str, headers_defaults: list[str]):
    hdr = _header_map(ws, headers_defaults)
    id_col = hdr.get(id_col_name)
    appr_col = hdr.get("Approved")
    if not id_col or not appr_col:
        st.error("Headers missing: need both ID column and Approved.")
        return
    row = _find_row_by_id(ws, id_col, id_value)
    ws.update_cell(row, appr_col, "REJECTED")

def extend_expiry(ws, id_col_name: str, id_value: str, headers_defaults: list[str], extra_days: int):
    hdr = _header_map(ws, headers_defaults)
    id_col = hdr.get(id_col_name)
    exp_col = hdr.get("Expires_On")
    if not id_col or not exp_col:
        st.error("Headers missing: need ID and Expires_On.")
        return
    row = _find_row_by_id(ws, id_col, id_value)
    current = ws.cell(row, exp_col).value
    try:
        new_dt = date.fromisoformat(current) + timedelta(days=int(extra_days))
    except Exception:
        new_dt = date.today() + timedelta(days=int(extra_days))
    ws.update_cell(row, exp_col, new_dt.isoformat())
# ------------------------------- UI HEAD --------------------------------------
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
admin_login_ui()

# ----------------------------- TABS (NAV) -------------------------------------
tabs = st.tabs(["🏠 Showcase", "ℹ️ About", "📇 Directory", "🛒 Vicinity Vendors", "📝 Support", "🧑‍🤝‍🧑 Register", "🛠️ Admin"])

# ------------------------------ SHOWCASE --------------------------------------
with tabs[0]:
    st.subheader("Showcase Wall")
    s = df_public(ws_to_df(ws_show), approved_col="Approved", expires_col=None)
    if s.empty:
        st.info("No items yet. Admin can add in the Admin tab.")
    else:
        for _, r in s.sort_values("Submitted_At", ascending=False).iterrows():
            with st.container(border=True):
                st.markdown(f"**{r.get('Title','')}**  ·  <span class='badge'>{r.get('Type','')}</span>", unsafe_allow_html=True)
                url = r.get("URL","").strip()
                if r.get("Type","").lower()=="video":
                    st.video(url)
                else:
                    st.image(url, use_container_width=True, caption=r.get("Notes",""))

# -------------------------------- ABOUT ---------------------------------------
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
- You can select a listing period: **7/15/30/45/60/90 days**.
- Expired listings stop showing automatically. Admin can extend.
""")

# ------------------------------- DIRECTORY ------------------------------------
with tabs[2]:
    st.subheader("Resident Business Directory")

    # member quick sign-in (email)
    with st.expander("Member quick sign-in (for submissions & rating)"):
        me = st.text_input("Your Email", key="me_email").strip()
        if st.button("Set as me", key="me_set"):
            if member_is_approved(me):
                st.session_state.me = me
                st.success("You’re set as a verified member.")
            else:
                st.warning("Not found or not approved yet. Register or wait for approval.")

    df = df_public(ws_to_df(ws_dir))
    if df.empty:
        st.info("No approved listings yet.")
    else:
        # filters
        filt_cols = st.columns(5)
        with filt_cols[0]:
            f_phase = st.selectbox("Phase", ["All"] + sorted(df["Phase"].dropna().unique().tolist()))
        with filt_cols[1]:
            f_cat = st.selectbox("Category", ["All"] + sorted(df["Category"].dropna().unique().tolist()))
        with filt_cols[2]:
            f_srv = st.selectbox("Service Type", ["All"] + sorted(df["Service_Type"].dropna().unique().tolist()))
        with filt_cols[3]:
            f_wing = st.selectbox("Wing", ["All"] + sorted(df["Wing"].dropna().unique().tolist()))
        with filt_cols[4]:
            q = st.text_input("Search")

        view = df.copy()
        def fapply(val, choice): 
            return (choice=="All") or (str(val).strip()==choice)
        if f_phase!="All": view = view[view["Phase"]==f_phase]
        if f_cat!="All":   view = view[view["Category"]==f_cat]
        if f_srv!="All":   view = view[view["Service_Type"]==f_srv]
        if f_wing!="All":  view = view[view["Wing"]==f_wing]
        if q:              view = view[view.apply(lambda r: q.lower() in (" ".join(map(str,r.values))).lower(), axis=1)]

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
                data = dict(
                    Member_Email=st.session_state.me, Resident_Type=resident_type,
                    Phase=phase, Wing=wing, Flat_No=flat,
                    Business_Name=b_name, Category=category, Subcategory=subcategory,
                    Service_Type=service, Short_Description=short, Detailed_Description=detail,
                    Image_URL_1=u1, Image_URL_2=u2, Image_URL_3=u3, Duration_Days=int(duration)
                )
                save_directory(data)
                st.success("Submitted! Admin will review & approve.")

# --------------------------- VICINITY VENDORS ---------------------------------
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

# -------------------------------- SUPPORT -------------------------------------
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

# ------------------------------ REGISTER --------------------------------------
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

# -------------------------------- ADMIN ---------------------------------------
with tabs[6]:
    if not is_admin():
        st.warning("Admin only.")
    else:
        st.subheader("Admin Panel")

        # quick add to Showcase
        with st.expander("Add Showcase (image/video)"):
            t = st.text_input("Title")
            typ = st.selectbox("Type", ["image","video"])
            url = st.text_input("URL (image link or video link)")
            by  = st.text_input("Posted by")
            notes = st.text_area("Notes")
            approve = st.checkbox("Approve now?", value=True)
            if st.button("Add to Showcase", type="primary"):
                save_showcase(dict(Title=t, Type=typ, URL=url, Posted_By=by, Notes=notes), approve=approve)
                st.success("Added to Showcase.")

        # approvals
        st.markdown("### Approvals")

        members_df = ws_to_df(ws_members)
        dir_df     = ws_to_df(ws_dir)
        ven_df     = ws_to_df(ws_ven)
        show_df    = ws_to_df(ws_show)

        def bool_select(s): return st.radio("", ["FALSE","TRUE"], horizontal=True, index=0 if str(s).upper()!="TRUE" else 1)

        # Members
        with st.expander("Members"):
            if members_df.empty:
                st.info("No members.")
            else:
                pending = members_df[members_df["Approved"].str.upper()!="TRUE"]
                st.write("Pending:", len(pending))
                st.dataframe(members_df, use_container_width=True)
                # Download
                st.download_button("Download Members CSV",
                                   members_df.to_csv(index=False).encode(),
                                   "members.csv", "text/csv")

        # Directory
        with st.expander("Business Listings"):
            if dir_df.empty:
                st.info("No listings.")
            else:
                st.dataframe(dir_df, use_container_width=True)
                expiring = dir_df[pd.to_datetime(dir_df["Expires_On"], errors="coerce").dt.date <= add_days(today(), 7)]
                if not expiring.empty:
                    st.warning(f"Expiring soon: {len(expiring)}")
                    st.dataframe(expiring[["Business_Name","Expires_On","Member_Email"]], use_container_width=True)
                st.download_button("Download Listings CSV",
                                   dir_df.to_csv(index=False).encode(),
                                   "business_listings.csv", "text/csv")

        # Vendors
        with st.expander("Vicinity Vendors"):
            if ven_df.empty:
                st.info("No vendors.")
            else:
                st.dataframe(ven_df, use_container_width=True)
                st.download_button("Download Vendors CSV",
                                   ven_df.to_csv(index=False).encode(),
                                   "vendors.csv", "text/csv")

        # Showcase table + approvals
        with st.expander("Showcase table"):
            if show_df.empty:
                st.info("No showcase entries.")
            else:
                st.dataframe(show_df, use_container_width=True)

        st.caption("Use Google Sheets to flip **Approved** to TRUE / extend **Expires_On**. Changes show instantly.")




