from __future__ import annotations
import re, time, uuid, math, datetime as dt
from typing import List, Tuple

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials

# -------------------- THEME / BRAND --------------------
PRIMARY   = "#18B8CB"   # Atmosphere blue
ACCENT    = "#06B6FF"
INK       = "#0C2AA4"
CARD_BG   = "rgba(15,34,64,0.65)"  # translucent dark overlay for readability
TEXT_ON_D = "#ECF7FF"

REPO_RAW   = "https://raw.githubusercontent.com/CPArora14/Atmosphere-Directory/main/assets"
BG_URL     = f"{REPO_RAW}/bg.jpg"
LOGO_URL   = f"{REPO_RAW}/logo.png"

st.set_page_config(page_title="Atmosphere Society — Community Hub", layout="wide")
st.markdown(
    f"""
    <style>
      [data-testid="stAppViewContainer"] > .main {{
        background: linear-gradient(0deg, rgba(0,20,40,.65), rgba(0,20,40,.65)),
                    url('{BG_URL}') center/cover fixed no-repeat;
      }}
      [data-testid="stHeader"] {{ background: transparent; }}
      .stButton > button {{
        background:{PRIMARY}; color:white; border:0; border-radius:10px; padding:.6rem 1rem;
      }}
      .stButton > button:hover {{ filter:brightness(1.08); }}
      .card {{
        background:{CARD_BG}; color:{TEXT_ON_D};
        padding:1rem; border-radius:16px; border:1px solid rgba(255,255,255,.08);
      }}
      .pill {{ background:{ACCENT}; color:white; border-radius:999px; padding:.2rem .6rem; font-size:.8rem; }}
      .star {{ color:#FFD85A; font-size:20px; line-height:1; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- SAFE RERUN -----------------------
def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

# -------------------- AUTH (env + admin) ----------------
APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")
SHEET_URL    = st.secrets.get("SHEET_URL", "")

def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))

def admin_login_ui():
    if is_admin():
        st.success("Admin mode enabled.")
        return
    with st.expander("🔐 Admin login", expanded=False):
        u = st.text_input("Username", key="adm_u")
        p = st.text_input("Password", type="password", key="adm_p")
        if st.button("Sign in", type="primary"):
            if u.strip()==APP_USERNAME and p==APP_PASSWORD:
                st.session_state.is_admin = True
                st.success("Logged in.")
                _safe_rerun()
            else:
                st.error("Wrong credentials.")

# -------------------- GOOGLE SHEETS CLIENT --------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
@st.cache_resource(show_spinner=False)
def get_gc():
    sa_info = dict(st.secrets["gcp_service_account"])
    creds   = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

def open_sh(url:str):
    gc = get_gc()
    try:
        return gc.open_by_url(url)
    except SpreadsheetNotFound:
        st.error("Could not open spreadsheet. Check SHEET_URL in Secrets and sharing.")
        st.stop()

def ensure_ws(sh, title:str, headers:List[str]):
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=len(headers)+10)
        ws.append_row(headers)
    # ensure headers present
    vals = ws.get_all_values()
    if not vals or vals[0] != headers:
        ws.clear()
        ws.append_row(headers)
    return ws

def ws_to_df(ws) -> pd.DataFrame:
    vals = ws.get_all_values()
    if len(vals) <= 1:
        return pd.DataFrame()
    return pd.DataFrame(vals[1:], columns=vals[0])

def append_row(ws, row:List[str]):
    ws.append_row(row)

# -------------------- REQUIRED TABS + HEADERS -----------
MEM_HEADERS = ["Member_ID","Submitted_At","Approved","Resident_Type","Phase","Wing","Flat_No","Name","Email","Phone"]
DIR_HEADERS = ["Listing_ID","Submitted_At","Approved","Member_Email","Resident_Type","Phase","Wing",
               "Flat_No","Business_Name","Category","Subcategory","Service_Type",
               "Short_Description","Detailed_Description","Image_URL_1","Image_URL_2","Image_URL_3",
               "Duration_Days","Expires_On"]

VEN_HEADERS = ["Vendor_ID","Submitted_At","Approved","Member_Email","Vendor_Name","Contact","Phone",
               "Area","Category","Notes","Duration_Days","Expires_On"]

SHOW_HEADERS = ["Submitted_At","Approved","Title","Type","URL","Posted_By","Notes"]
RATE_HEADERS = ["When","Listing_ID","Stars","Comment","Rater_Email"]
SUPP_HEADERS = ["Ticket_ID","When","Email","Subject","Message","Status"]

# -------------------- OPEN SHEET / ENSURE TABS ----------
sh          = open_sh(SHEET_URL)

ws_members  = ensure_ws(sh,"Members", MEM_HEADERS)
ws_dir      = ensure_ws(sh,"Business_Listings", DIR_HEADERS)
ws_ven      = ensure_ws(sh,"Vicinity_Vendors", VEN_HEADERS)
ws_show     = ensure_ws(sh,"Showcase", SHOW_HEADERS)
ws_rate     = ensure_ws(sh,"Ratings", RATE_HEADERS)
ws_supp     = ensure_ws(sh,"Support_Tickets", SUPP_HEADERS)

# -------------------- HEADER ----------------------------
col_l, col_r = st.columns([1,5], gap="large")
with col_l:
    st.image(LOGO_URL, width=140)
with col_r:
    st.write("")
    st.write("")
    st.markdown(f"<h1 style='color:{TEXT_ON_D};'>Atmosphere Society — Community Hub</h1>", unsafe_allow_html=True)
    st.markdown(f"<div class='pill'>Showcase • Directory • Vendors • Support</div>", unsafe_allow_html=True)

st.divider()

# -------------------- MEMBER VERIFY ---------------------
def member_verify_box():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("✅ Member verification")
    if st.session_state.get("member_email"):
        st.write(f"Signed in as **{st.session_state.member_email}**")
        st.markdown("</div>", unsafe_allow_html=True)
        return True

    with st.form("member_form", clear_on_submit=False):
        email = st.text_input("Your Email (will be used for submissions & ratings)")
        name  = st.text_input("Full Name")
        phase = st.selectbox("Phase", ["Atmosphere 1","Atmosphere 2","Other"])
        wing  = st.text_input("Wing (A/B/…)")
        flat  = st.text_input("Flat No (e.g., 1203)")
        rtype = st.selectbox("Resident type", ["Resident","Tenant"])
        phone = st.text_input("Phone")
        submit = st.form_submit_button("Verify & Save", type="primary")
    if submit:
        if not re.match(r".+@.+\..+", email):
            st.error("Enter a valid email.")
        else:
            now = dt.datetime.utcnow().isoformat()
            row = [str(uuid.uuid4()), now, "TRUE", rtype, phase, wing, flat, name, email, phone]
            append_row(ws_members, row)
            st.session_state.member_email = email
            st.success("Saved. You’re verified.")
            _safe_rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return False

# -------------------- DIRECTORY (Resident Business) -----
def directory_tab():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Resident Business Directory")

    df_all = ws_to_df(ws_dir)
    if df_all.empty:
        st.info("No businesses yet. Submit yours below.")
    else:
        # show only approved & not expired
        today = dt.date.today()
        def still_ok(row):
            try:
                eo = dt.date.fromisoformat(row["Expires_On"])
                return (row["Approved"]=="TRUE") and (eo >= today)
            except Exception:
                return (row["Approved"]=="TRUE")
        mask = df_all.apply(still_ok, axis=1)
        df = df_all[mask].copy()

        # pick one business to see details + rate
        names = df["Business_Name"].tolist() if "Business_Name" in df else []
        if names:
            pick = st.selectbox("Browse businesses:", names, index=0)
            sel  = df[df["Business_Name"]==pick].iloc[0]
            st.write(f"**Category**: {sel['Category']} / {sel['Subcategory']}")
            st.write(f"**Service Type**: {sel['Service_Type']}")
            st.write(f"**Short**: {sel['Short_Description']}")
            with st.expander("More details"):
                st.write(sel.get("Detailed_Description",""))
                cols = st.columns(3)
                for i, col in enumerate(cols, start=1):
                    url = sel.get(f"Image_URL_{i}","").strip()
                    if url:
                        with col: st.image(url, use_column_width=True)

            # ---- Rating block
            st.markdown("---")
            st.write("### Rate this business")
            if not st.session_state.get("member_email"):
                st.info("Sign in as a verified member (top) to rate.")
            else:
                stars = st.radio("Stars", [1,2,3,4,5], horizontal=True, index=4)
                comment = st.text_area("Optional comment")
                if st.button("Submit rating", key="rate_btn"):
                    row = [dt.datetime.utcnow().isoformat(), sel["Listing_ID"], str(stars), comment, st.session_state.member_email]
                    append_row(ws_rate, row)
                    st.success("Thanks! Your rating was recorded.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Submit a business")
    if not st.session_state.get("member_email"):
        st.info("Please verify your email above to submit.")
    else:
        with st.form("dir_submit"):
            business = st.text_input("Business Name *")
            category = st.text_input("Category * (e.g., Food & Beverages)")
            subcat   = st.text_input("Subcategory (e.g., Caterers)")
            service  = st.text_input("Service Type (e.g., Home delivery)")
            short    = st.text_area("Short Description *", max_chars=160)
            detail   = st.text_area("Detailed Description")
            img1     = st.text_input("Image URL 1 (public link)")
            img2     = st.text_input("Image URL 2")
            img3     = st.text_input("Image URL 3")
            duration = st.selectbox("Listing Duration", [7,15,30,45,60,90], index=2)

            submit = st.form_submit_button("Send for approval", type="primary")

        if submit:
            lid = str(uuid.uuid4())
            now = dt.datetime.utcnow()
            expires = (now + dt.timedelta(days=int(duration))).date().isoformat()
            member = st.session_state.member_email

            # fetch member info if exists
            mdf = ws_to_df(ws_members)
            rowm = mdf[mdf["Email"]==member].iloc[0] if not mdf.empty and (mdf["Email"]==member).any() else None
            rtype = rowm["Resident_Type"] if rowm is not None else ""
            phase = rowm["Phase"] if rowm is not None else ""
            wing  = rowm["Wing"] if rowm is not None else ""
            flat  = rowm["Flat_No"] if rowm is not None else ""

            row = [lid, now.isoformat(), "FALSE", member, rtype, phase, wing, flat, business, category, subcat,
                   service, short, detail, img1, img2, img3, str(duration), expires]
            append_row(ws_dir, row)
            st.success("Submitted. Admin will review and approve.")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------- VICINITY VENDORS ------------------
def vendors_tab():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Vicinity Vendors")

    df_all = ws_to_df(ws_ven)
    if not df_all.empty:
        df = df_all[(df_all["Approved"]=="TRUE")]
        with st.expander("Browse approved vendors", expanded=True):
            st.dataframe(df[["Vendor_Name","Area","Category","Phone","Notes"]], use_container_width=True)
    else:
        st.info("No vendors yet.")

    st.markdown("---")
    st.write("### Suggest a vendor")
    if not st.session_state.get("member_email"):
        st.info("Sign in as a verified member (email) in the header before submitting.")
    else:
        with st.form("vendor_form"):
            name  = st.text_input("Vendor Name *")
            area  = st.text_input("Area / Market *")
            phone = st.text_input("Phone")
            cat   = st.text_input("Category")
            notes = st.text_area("Notes")
            duration = st.selectbox("Keep visible for", [7,15,30,45,60,90], index=2)
            submit = st.form_submit_button("Send to Admin", type="primary")
        if submit:
            vid = str(uuid.uuid4())
            now = dt.datetime.utcnow()
            expires = (now + dt.timedelta(days=int(duration))).date().isoformat()
            row = [vid, now.isoformat(), "FALSE", st.session_state.member_email, name, "", phone, area, cat, notes, str(duration), expires]
            append_row(ws_ven, row)
            st.success("Submitted. Admin will approve.")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------- SHOWCASE WALL ---------------------
def showcase_tab():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Showcase Wall")

    df = ws_to_df(ws_show)
    df = df[(df["Approved"]=="TRUE")] if not df.empty else df
    if df.empty:
        st.info("No showcase items yet.")
    else:
        cols = st.columns(3)
        for i, (_,r) in enumerate(df.iterrows()):
            with cols[i%3]:
                st.markdown(f"**{r['Title']}**")
                st.write(r["Type"])
                if r["URL"].startswith(("http://","https://")):
                    st.link_button("Open", r["URL"])
    st.markdown("</div>", unsafe_allow_html=True)

    if is_admin():
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write("### Add to Showcase (Admin)")
        with st.form("show_form"):
            title = st.text_input("Title *")
            typ   = st.selectbox("Type", ["Image","YouTube","Link"])
            url   = st.text_input("Public URL *")
            notes = st.text_input("Notes")
            submit = st.form_submit_button("Add", type="primary")
        if submit:
            now = dt.datetime.utcnow().isoformat()
            row = [now, "TRUE", title, typ, url, APP_USERNAME, notes]
            append_row(ws_show, row)
            st.success("Added to wall.")
        st.markdown("</div>", unsafe_allow_html=True)

# -------------------- SUPPORT TICKETS -------------------
def support_tab():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Support")
    st.caption("Replies may take 7–15 days.")

    with st.form("support"):
        email = st.text_input("Your Email")
        subject = st.text_input("Subject")
        msg = st.text_area("Message")
        submit = st.form_submit_button("Create Ticket", type="primary")
    if submit:
        tid = str(uuid.uuid4())
        row = [tid, dt.datetime.utcnow().isoformat(), email, subject, msg, "OPEN"]
        append_row(ws_supp, row)
        st.success("Ticket submitted.")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------- ADMIN PANEL -----------------------
def admin_tab():
    admin_login_ui()
    if not is_admin():
        st.stop()

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Approvals & Exports")

    # ---- Members
    st.write("#### Members (view only)")
    mdf = ws_to_df(ws_members)
    st.dataframe(mdf, use_container_width=True, height=250)

    # ---- Business approvals
    st.write("#### Business Listings — Pending")
    ddf = ws_to_df(ws_dir)
    pend = ddf[(ddf["Approved"]!="TRUE")] if not ddf.empty else ddf
    if pend.empty:
        st.info("Nothing pending.")
    else:
        for _, r in pend.iterrows():
            with st.expander(f"{r['Business_Name']} — {r['Member_Email']}"):
                st.write(r.to_dict())
                c1,c2,c3 = st.columns(3)
                with c1:
                    if st.button("Approve", key=f"ap_{r['Listing_ID']}"):
                        ws_dir.update_cell(int(_)+2, ddf.columns.get_loc("Approved")+1, "TRUE")  # fallback if index unknown
                        st.success("Approved.")
                        _safe_rerun()
                with c2:
                    if st.button("Reject", key=f"rej_{r['Listing_ID']}"):
                        ws_dir.update_cell(int(_)+2, ddf.columns.get_loc("Approved")+1, "REJECTED")
                        st.warning("Rejected.")
                        _safe_rerun()
                with c3:
                    ext = st.number_input("Extend days", 0, 365, 0, key=f"ex_{r['Listing_ID']}")
                    if st.button("Apply extension", key=f"exbtn_{r['Listing_ID']}"):
                        try:
                            eo = dt.date.fromisoformat(r["Expires_On"])
                            eo2 = (eo + dt.timedelta(days=int(ext))).isoformat()
                            ws_dir.update_cell(int(_)+2, ddf.columns.get_loc("Expires_On")+1, eo2)
                            st.success("Extended.")
                        except Exception:
                            st.error("Invalid Expires_On date.")

    # ---- Vendor approvals
    st.write("#### Vendors — Pending")
    vdf = ws_to_df(ws_ven)
    vpend = vdf[(vdf["Approved"]!="TRUE")] if not vdf.empty else vdf
    if vpend.empty:
        st.info("Nothing pending.")
    else:
        for _, r in vpend.iterrows():
            with st.expander(f"{r['Vendor_Name']} — {r['Member_Email']}"):
                st.write(r.to_dict())
                c1,c2 = st.columns(2)
                with c1:
                    if st.button("Approve", key=f"vap_{r['Vendor_ID']}"):
                        ws_ven.update_cell(int(_)+2, vdf.columns.get_loc("Approved")+1, "TRUE")
                        st.success("Approved.")
                        _safe_rerun()
                with c2:
                    if st.button("Reject", key=f"vrej_{r['Vendor_ID']}"):
                        ws_ven.update_cell(int(_)+2, vdf.columns.get_loc("Approved")+1, "REJECTED")
                        st.warning("Rejected.")
                        _safe_rerun()

    st.markdown("---")
    st.write("#### Export CSV")
    col1,col2,col3 = st.columns(3)
    with col1:
        st.download_button("Businesses.csv", ddf.to_csv(index=False).encode(), "businesses.csv")
    with col2:
        st.download_button("Vendors.csv", vdf.to_csv(index=False).encode(), "vendors.csv")
    with col3:
        st.download_button("Members.csv", mdf.to_csv(index=False).encode(), "members.csv")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------- MAIN ------------------------------
# 1) Member verify box appears on every page (top)
member_verify_box()

tab_show, tab_dir, tab_ven, tab_sup, tab_admin = st.tabs(
    ["📣 Showcase Wall", "🏪 Directory (Residents)", "🧭 Vicinity Vendors", "🛟 Support", "🛠 Admin"]
)

with tab_show:
    showcase_tab()
with tab_dir:
    directory_tab()
with tab_ven:
    vendors_tab()
with tab_sup:
    support_tab()
with tab_admin:
    admin_tab()




