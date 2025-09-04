from __future__ import annotations
import re, time, uuid, math, datetime as dt
from typing import List, Tuple

import pandas as pd
import streamlit as st
import gspread
from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound
from google.oauth2.service_account import Credentials
# Safe rerun helper (works with new + old Streamlit)
def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass
# =========================== BRANDING ===========================
PRIMARY   = "#1B8CD8"
PRIMARY_2 = "#6BC6FF"
INK       = "#0C2A4A"
CARD_BG   = "#0E1C2B"
PAGE_BG   = "#0A1522"
BANNER_GRADIENT = f"linear-gradient(90deg, {PRIMARY} 0%, {PRIMARY_2} 100%)"
LOGO_PATH = "logo.png"
LOGO_URL  = st.secrets.get("LOGO_URL")

st.set_page_config(page_title="Atmosphere — Business Directory", page_icon="🎞️", layout="wide")

st.markdown(f"""
<style>
  .stApp {{ background:{PAGE_BG}; color:#fff; }}
  section[data-testid="stSidebar"] {{ background:{CARD_BG}; }}
  .atm-banner {{ background:{BANNER_GRADIENT}; padding:18px 22px; border-radius:18px; box-shadow:0 10px 35px rgba(0,0,0,.35); margin-bottom:18px; }}
  .atm-title {{ font-weight:800; font-size:42px; letter-spacing:.2px; }}
  .atm-subt {{ opacity:.9; font-size:14px; }}
  .atm-card {{ background:{CARD_BG}; border-radius:16px; padding:16px; border:1px solid rgba(255,255,255,.08); }}
  .atm-grid {{ display:grid; gap:16px; }}
  @media (min-width:1100px) {{ .atm-grid.cols-3 {{ grid-template-columns:repeat(3,1fr); }} }}
  @media (max-width:1099px) {{ .atm-grid.cols-3 {{ grid-template-columns:repeat(1,1fr); }} }}
  .small-dim {{ opacity:.75; font-size:12px; }}
</style>
""", unsafe_allow_html=True)

c1, c2 = st.columns([1,6])
with c1:
    try:
        if LOGO_URL: st.image(LOGO_URL)
        else:        st.image(LOGO_PATH)
    except Exception: pass
with c2:
    st.markdown(f"""
    <div class="atm-banner">
      <div class="atm-title">Atmosphere Society — Community Hub</div>
      <div class="atm-subt">Showcase • Directory • Vendors • Support</div>
    </div>
    """, unsafe_allow_html=True)

# =========================== AUTH ===============================
APP_USERNAME = st.secrets.get("APP_USERNAME", "")
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

def admin_login_ui():
    if is_admin():
        st.success("Admin mode enabled.")
        return
    with st.expander("🔑 Admin Login", expanded=False):
        u = st.text_input("Username", key="adm_u")
        p = st.text_input("Password", type="password", key="adm_p")
        if st.button("Sign in", type="primary"):
            if u.strip() == APP_USERNAME and p == APP_PASSWORD:
                st.session_state.is_admin = True
                st.success("✅ Logged in.")
                _safe_rerun()  # safe helper
            else:
                st.error("❌ Wrong credentials.")
# ====================== GOOGLE SHEETS CLIENT ====================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
@st.cache_resource(show_spinner=False)
def get_gc():
    sa_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    return gspread.authorize(creds)

gc = get_gc()
SHEET_URL = st.secrets.get("SHEET_URL", "https://docs.google.com/spreadsheets/d/1SWVjrtC8qh9fXFhrcXbc_6cgNS39tc87vvPz1PCaeFY/edit#gid=0")
@st.cache_resource(show_spinner=False)
def open_sh(url:str): return gc.open_by_url(url)

def ensure_ws(sh, title:str, headers:List[str]):
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title, rows=1000, cols=max(10,len(headers)))
        ws.append_row(headers)
    vals = ws.get_all_values()
    if not vals: ws.append_row(headers)
    return ws

def ws_to_df(ws) -> pd.DataFrame:
    vals = ws.get_all_values()
    if not vals: return pd.DataFrame()
    if len(vals)==1: return pd.DataFrame(columns=vals[0])
    return pd.DataFrame(vals[1:], columns=vals[0])

def append(ws, row:List[str]): ws.append_row(row)

try:
    sh = open_sh(SHEET_URL)
except SpreadsheetNotFound:
    st.error("Could not open spreadsheet; check SHEET_URL secret & sharing to service account.")
    st.stop()

# ---------- Ensure required sheets (auto-create if missing) ----
MEM_HEADERS = ["Created_At","Phase","Wing","Flat_No","Full_Name","Email",
 "Phone","Is_Tenant","Approved","Admin_Notes"]
DIR_HEADERS = ["Listing_ID","Submitted_At","Approved","Member_Email","Resident_Type","Phase","Wing","Flat_No","Business_Name","Category","Subcategory",
               "Service_Type","Short_Description","Detailed_Description","Image_URL_1","Image_URL_2","Image_URL_3",
               "Duration_Days","Expires_On"]
VEN_HEADERS = ["Vendor_ID","Submitted_At","Approved","Member_Email","Vendor_Name","Contact","Phone","Category","Subcategory","Location",
               "Short_Description","Detailed_Description","Duration_Days","Expires_On"]
SHOW_HEADERS = ["Submitted_At","Approved","Title","Type","URL","Posted_By","Notes"]
RATE_HEADERS = ["When","Type","Target_ID","Stars","Comment","Rater_Email"]
SUPP_HEADERS = ["Ticket_ID","When","Email","Subject","Message","Status"]

ws_members = ensure_ws(sh,"Members",MEM_HEADERS)
ws_dir     = ensure_ws(sh,"Business_Listings",DIR_HEADERS)
ws_ven     = ensure_ws(sh,"Vicinity_Vendors",VEN_HEADERS)
ws_show    = ensure_ws(sh,"Showcase",SHOW_HEADERS)
ws_rate    = ensure_ws(sh,"Ratings",RATE_HEADERS)
ws_supp    = ensure_ws(sh,"Support_Tickets",SUPP_HEADERS)

# ====================== UTILITIES ===============================
def now_str(): return time.strftime("%Y-%m-%d %H:%M:%S")
def add_days(days:int)->str: return (dt.date.today()+dt.timedelta(days=days)).isoformat()

def drive_id(url:str)->str|None:
    pats=[r"drive\.google\.com/file/d/([^/]+)/", r"drive\.google\.com/open\?id=([^&]+)", r"drive\.google\.com/uc\?id=([^&]+)"]
    for p in pats:
        m=re.search(p,url); 
        if m: return m.group(1)
    return None

def to_img(url:str)->str:
    fid=drive_id(url)
    return f"https://drive.google.com/uc?export=view&id={fid}" if fid else url

def to_video(url:str)->str:
    fid=drive_id(url)
    return f"https://drive.google.com/file/d/{fid}/preview" if fid else url

def member_is_approved(email:str)->bool:
    df = ws_to_df(ws_members)
    if df.empty: return False
    df["Email"]=df["Email"].str.strip().str.lower()
    rec = df[df["Email"]==email.strip().lower()]
    if rec.empty: return False
    return rec["Approved"].str.lower().eq("yes").any()

def average_rating(target_type:str, target_id:str)->float:
    df = ws_to_df(ws_rate)
    if df.empty: return 0.0
    sub = df[(df["Type"]==target_type)&(df["Target_ID"]==target_id)]
    if sub.empty: return 0.0
    try:
        stars = pd.to_numeric(sub["Stars"], errors="coerce").dropna()
        return round(float(stars.mean()),1) if len(stars)>0 else 0.0
    except Exception: return 0.0

# ================= TAXONOMY (dropdowns) ========================
PHASES = ["Atmosphere 1","Atmosphere 2"]
RESIDENT_TYPES = ["Resident","Tenant"]

CATEGORIES = {
    "Food & Beverages": ["Catering","Tiffin","Bakery","Snacks","Beverages"],
    "Home Services": ["Plumber","Electrician","Carpenter","Painter","Appliance Repair"],
    "Education": ["Tutoring","Music","Dance","Art","Coaching"],
    "Health & Wellness": ["Yoga","Gym Trainer","Physio","Nutrition","Salon"],
    "Professional": ["CA/CS","Legal","Designer","Developer","Consulting"],
    "Retail": ["Clothing","Gifts","Grocery","Pharmacy","Electronics"],
}

SERVICE_TYPES = ["Product","Service","Both"]

DURATION_CHOICES = {
    "7 days":7, "15 days":15, "1 month (30 days)":30, "45 days":45, "2 months (60 days)":60, "3 months (90 days)":90
}

# ====================== TABS (Showcase first) ==================
tabs = st.tabs([
    "🎞️ Showcase Wall", "📖 Directory", "📝 Submit Business", "🏪 Vicinity Vendors",
    "🧾 Register (Resident/Tenant)", "🎟️ Support", "ℹ️ About", "🛠️ Admin"
])

# ------------------ SHOWCASE (view only; admin posts) ----------
with tabs[0]:
    st.subheader("Showcase Wall — Photos & 10-second Videos")
    df_show = ws_to_df(ws_show)
    if df_show.empty:
        st.info("No items yet. Admin can add in the Admin tab.")
    else:
        approved = df_show[df_show["Approved"].str.lower()=="yes"]
        if approved.empty: st.info("No approved items yet.")
        else:
            st.markdown('<div class="atm-grid cols-3">', unsafe_allow_html=True)
            for _, row in approved.iterrows():
                st.markdown('<div class="atm-card">', unsafe_allow_html=True)
                typ = (row.get("Type","") or "").lower()
                if "video" in typ: st.components.v1.iframe(to_video(row["URL"]), height=260)
                else: st.image(to_img(row["URL"]), use_container_width=True)
                st.markdown(f"**{row.get('Title','')}**  \n<span class='small-dim'>by {row.get('Posted_By','')}</span>", unsafe_allow_html=True)
                if row.get("Notes",""): st.caption(row["Notes"])
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ------------------ DIRECTORY (approved & unexpired) ----------
with tabs[1]:
    st.subheader("Resident Business Listings")
    df = ws_to_df(ws_dir)
    if df.empty:
        st.info("No directory entries yet.")
    else:
        # keep only approved & not expired
        today = dt.date.today()
        def not_expired(x):
            try: return dt.date.fromisoformat(x) >= today
            except: return True
        df = df[df["Approved"].str.lower()=="yes"]
        df = df[df["Expires_On"].apply(not_expired)]

        # filters
        col1,col2,col3,col4 = st.columns(4)
        with col1: phase = st.selectbox("Phase", ["All"] + sorted(list(pd.Series(df["Phase"]).dropna().unique())))
        with col2: cat   = st.selectbox("Category", ["All"] + sorted(list(pd.Series(df["Category"]).dropna().unique())))
        with col3: svc   = st.selectbox("Service Type", ["All"] + sorted(list(pd.Series(df["Service_Type"]).dropna().unique())))
        with col4: txt   = st.text_input("Search name/description")

        mask = pd.Series([True]*len(df))
        if phase!="All": mask &= df["Phase"].eq(phase)
        if cat!="All":   mask &= df["Category"].eq(cat)
        if svc!="All":   mask &= df["Service_Type"].eq(svc)
        if txt: 
            t=txt.lower()
            mask &= (
                df["Business_Name"].str.lower().str.contains(t, na=False) |
                df["Short_Description"].str.lower().str.contains(t, na=False) |
                df["Detailed_Description"].str.lower().str.contains(t, na=False)
            )
        show = df[mask].copy()

        if show.empty:
            st.warning("No listings match your filters.")
        else:
            # append live average rating
            show["Avg_Rating"] = show.apply(lambda r: average_rating("listing", r["Listing_ID"]), axis=1)
            st.dataframe(show, use_container_width=True)

            # simple rating UI
            with st.expander("Rate a listing"):
                listing_ids = show["Listing_ID"].tolist()
                if listing_ids:
                    lid = st.selectbox("Choose Listing ID", listing_ids)
                    stars = st.slider("Stars", 1, 5, 5)
                    comment = st.text_area("Comment (optional)")
                    r_email = st.text_input("Your email (optional)")
                    if st.button("Submit rating"):
                        append(ws_rate, [now_str(),"listing",lid,str(stars),comment,r_email])
                        st.success("Thanks for rating!")

# ------------------ SUBMIT BUSINESS (member-gated) -------------
with tabs[2]:
    st.subheader("Submit Your Business (goes to Admin for approval)")
    email_gate = st.text_input("Enter your registered email")
    if not email_gate:
        st.info("Enter your email used during resident/tenant registration.")
    else:
        if not member_is_approved(email_gate):
            st.error("This email is not registered/approved yet. Please register in '🧾 Register' tab.")
        else:
            with st.form("submit_business"):
                colA,colB,colC = st.columns(3)
                with colA:
                    phase = st.selectbox("Phase", PHASES)
                    rtype = st.selectbox("Resident / Tenant", RESIDENT_TYPES)
                    wing  = st.text_input("Wing")
                    flat  = st.text_input("Flat No (e.g., 1203)")
                with colB:
                    bname = st.text_input("Business Name")
                    category = st.selectbox("Category", list(CATEGORIES.keys()))
                    subcategory = st.selectbox("Subcategory", CATEGORIES[category])
                    svc_type   = st.selectbox("Service Type", SERVICE_TYPES)
                with colC:
                    dur_label = st.selectbox("Listing duration", list(DURATION_CHOICES.keys()))
                    dur_days  = DURATION_CHOICES[dur_label]
                    img1 = st.text_input("Image URL 1 (Google Drive or https)")
                    img2 = st.text_input("Image URL 2 (optional)")
                    img3 = st.text_input("Image URL 3 (optional)")

                short_d = st.text_area("Short Description (<= 120 chars)", max_chars=120)
                detail_d = st.text_area("Detailed Description")
                submitted = st.form_submit_button("Send for Approval")
                if submitted:
                    lid = "BL-" + uuid.uuid4().hex[:8].upper()
                    expires = add_days(dur_days)
                    append(ws_dir, [
                        lid, now_str(), "No", email_gate, rtype, phase, wing, flat,
                        bname, category, subcategory, svc_type, short_d, detail_d,
                        img1, img2, img3, str(dur_days), expires
                    ])
                    st.success("Submitted! Admin will review. Note: listings auto-expire on " + expires)

# ------------------ VICINITY VENDORS (member-gated) -----------
with tabs[3]:
    st.subheader("Suggest a Vicinity Vendor (goes to Admin for approval)")
    email_gate = st.text_input("Your registered email")
    if not email_gate:
        st.info("Enter your registered email to submit a vendor.")
    else:
        if not member_is_approved(email_gate):
            st.error("Email not approved/registered yet. Use '🧾 Register' tab first.")
        else:
            with st.form("vendor_form"):
                col1,col2,col3 = st.columns(3)
                with col1:
                    vname = st.text_input("Vendor Name")
                    contact = st.text_input("Contact Person")
                    phone = st.text_input("Phone")
                with col2:
                    cat = st.selectbox("Category", list(CATEGORIES.keys()))
                    sub = st.selectbox("Subcategory", CATEGORIES[cat])
                    loc = st.text_input("Location / Area")
                with col3:
                    dur_label = st.selectbox("Listing duration", list(DURATION_CHOICES.keys()), key="vdur")
                    dur_days  = DURATION_CHOICES[dur_label]
                short = st.text_area("Short Description (<= 120 chars)", max_chars=120)
                long  = st.text_area("Detailed Description")
                submit_v = st.form_submit_button("Send Vendor for Approval")
                if submit_v:
                    vid = "VV-" + uuid.uuid4().hex[:8].upper()
                    expires = add_days(dur_days)
                    append(ws_ven, [
                        vid, now_str(), "No", email_gate, vname, contact, phone, cat, sub, loc,
                        short, long, str(dur_days), expires
                    ])
                    st.success("Submitted! Admin will review. Auto-expiry on " + expires)

    # Show approved & not expired vendors + rating UI
    st.markdown("---")
    st.subheader("Approved Vendors")
    dfv = ws_to_df(ws_ven)
    if not dfv.empty:
        today = dt.date.today()
        def not_exp(x):
            try: return dt.date.fromisoformat(x) >= today
            except: return True
        dfv = dfv[(dfv["Approved"].str.lower()=="yes") & (dfv["Expires_On"].apply(not_exp))]
        if dfv.empty: st.info("No approved/active vendors currently.")
        else:
            dfv["Avg_Rating"] = dfv.apply(lambda r: average_rating("vendor", r["Vendor_ID"]), axis=1)
            st.dataframe(dfv, use_container_width=True)
            with st.expander("Rate a vendor"):
                vids = dfv["Vendor_ID"].tolist()
                if vids:
                    vid = st.selectbox("Choose Vendor ID", vids)
                    stars = st.slider("Stars", 1, 5, 5, key="vstars")
                    comment = st.text_area("Comment (optional)", key="vcomm")
                    r_email = st.text_input("Your email (optional)", key="vrem")
                    if st.button("Submit vendor rating"):
                        append(ws_rate, [now_str(),"vendor",vid,str(stars),comment,r_email])
                        st.success("Thanks for rating!")

# ------------------ REGISTER MEMBER ---------------------------
with tabs[4]:
    st.subheader("Register as Resident / Tenant")
    st.caption("Admin will approve within 7–15 days.")
    with st.form("register"):
        col1,col2,col3 = st.columns(3)
        with col1:
            rtype = st.selectbox("Resident Type", RESIDENT_TYPES)
            phase = st.selectbox("Phase", PHASES)
        with col2:
            wing  = st.text_input("Wing")
            flat  = st.text_input("Flat No (e.g., 1203)")
        with col3:
            name  = st.text_input("Full Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
        if st.form_submit_button("Submit registration"):
            if not email or not name:
                st.error("Name & Email are required.")
            else:
                mid = "MB-" + uuid.uuid4().hex[:8].upper()
                append(ws_members, [mid, now_str(), "No", rtype, phase, wing, flat, name, email, phone])
                st.success("Registration submitted! You’ll be able to post once approved.")

# ------------------ SUPPORT TICKET ----------------------------
with tabs[5]:
    st.subheader("Support")
    st.info("Please raise a ticket for any query. Reply time: **7–15 days**.")
    with st.form("support"):
        email = st.text_input("Your email")
        subj  = st.text_input("Subject")
        msg   = st.text_area("Message / Query")
        if st.form_submit_button("Submit ticket"):
            if not email or not subj or not msg:
                st.error("All fields are required.")
            else:
                tid = "TK-" + uuid.uuid4().hex[:8].upper()
                append(ws_supp, [tid, now_str(), email, subj, msg, "Open"])
                st.success("Ticket received! We will respond within 7–15 days.")

# ------------------ ABOUT ------------------------------------
with tabs[6]:
    st.subheader("About this app")
    st.markdown("""
**Atmosphere Society Community Hub** helps residents & tenants:

- **Discover** resident-run businesses (only approved, active, and rated by the community).
- **Submit** your own business with photos and a flexible listing duration.
- **Recommend vendors** near Atmosphere (all submissions go to Admin for approval).
- **Watch the Showcase Wall** for community promotions and special updates.
- **Open support tickets** for questions or suggestions.

**How to use**
1. Register once in **🧾 Register** (Resident/Tenant).  
2. After Admin approval, submit your business or vendors.  
3. Listings auto-expire after the selected duration (up to 3 months). You can re-list or ask Admin for an extension.  
4. Rate businesses & vendors you have used to help others.
""")

# ------------------ ADMIN ------------------------------------
with tabs[7]:
    st.subheader("Admin")
    admin_login_ui()
    if not is_admin(): st.stop()

    st.markdown("### Approvals & Expiry")
    df_mem = ws_to_df(ws_members)
    df_dir = ws_to_df(ws_dir)
    df_ven = ws_to_df(ws_ven)
    df_sup = ws_to_df(ws_supp)

    colA,colB,colC = st.columns(3)
    with colA:
        st.markdown("**Pending Members**")
        if df_mem.empty: st.caption("None")
        else: st.dataframe(df_mem[df_mem["Approved"].str.lower()!="yes"], use_container_width=True, height=250)
    with colB:
        st.markdown("**Pending Businesses**")
        if df_dir.empty: st.caption("None")
        else: st.dataframe(df_dir[df_dir["Approved"].str.lower()!="yes"], use_container_width=True, height=250)
    with colC:
        st.markdown("**Pending Vendors**")
        if df_ven.empty: st.caption("None")
        else: st.dataframe(df_ven[df_ven["Approved"].str.lower()!="yes"], use_container_width=True, height=250)

    st.markdown("---")
    st.markdown("### Expiring / Extend")
    today = dt.date.today()

    def expiring(df:pd.DataFrame, id_col:str)->pd.DataFrame:
        if df.empty: return df
        def days_left(x):
            try: return (dt.date.fromisoformat(x) - today).days
            except: return 9999
        df = df.copy()
        df["Days_Left"] = df["Expires_On"].apply(days_left)
        df = df[df["Approved"].str.lower()=="yes"]
        return df.sort_values("Days_Left")

    col1,col2 = st.columns(2)
    with col1:
        st.markdown("**Businesses — expiring soon**")
        e1 = expiring(df_dir, "Listing_ID")
        st.dataframe(e1[e1["Days_Left"]<=15], use_container_width=True, height=280)
        bid = st.text_input("Extend Business by Listing_ID")
        new_date = st.date_input("New expiry date", value=today+dt.timedelta(days=30))
        if st.button("Extend business expiry"):
            if bid:
                ws_dir.update_cell(1, DIR_HEADERS.index("Listing_ID")+1, "Listing_ID")  # ensure header
                cells = ws_dir.findall(bid)
                if cells:
                    row = cells[0].row
                    ws_dir.update_cell(row, DIR_HEADERS.index("Expires_On")+1, new_date.isoformat())
                    st.success("Extended.")
                else: st.error("Listing_ID not found.")
    with col2:
        st.markdown("**Vendors — expiring soon**")
        e2 = expiring(df_ven, "Vendor_ID")
        st.dataframe(e2[e2["Days_Left"]<=15], use_container_width=True, height=280)
        vid = st.text_input("Extend Vendor by Vendor_ID")
        new_date2 = st.date_input("New vendor expiry", value=today+dt.timedelta(days=30), key="vextend")
        if st.button("Extend vendor expiry"):
            if vid:
                cells = ws_ven.findall(vid)
                if cells:
                    row = cells[0].row
                    ws_ven.update_cell(row, VEN_HEADERS.index("Expires_On")+1, new_date2.isoformat())
                    st.success("Extended.")
                else: st.error("Vendor_ID not found.")

    st.markdown("---")
    st.markdown("### Post to Showcase (Admin only)")
    with st.form("show_admin_post"):
        title = st.text_input("Title")
        typ   = st.selectbox("Type", ["Image","Video (<=10s)"])
        url   = st.text_input("Public URL (Google Drive or https)")
        notes = st.text_area("Notes (optional)")
        by    = st.text_input("Posted By", value="Admin")
        if st.form_submit_button("Post"):
            if not title or not url: st.error("Title & URL required.")
            else:
                append(ws_show, [now_str(),"Yes",title,typ.lower(),url,by,notes])
                st.success("Posted to Showcase.")

    st.markdown("---")
    st.markdown("### Exports")
    def dl(df,name):
        if df.empty: st.caption(f"No {name.lower()} yet.")
        else:
            csv = df.to_csv(index=False).encode()
            st.download_button(f"Download {name} CSV", data=csv, file_name=f"{name.replace(' ','_')}.csv", mime="text/csv")
    colx,coly,colz = st.columns(3)
    with colx: dl(ws_to_df(ws_members),"Members")
    with coly: dl(ws_to_df(ws_dir),"Business_Listings")
    with colz: dl(ws_to_df(ws_ven),"Vicinity_Vendors")

    st.markdown("---")
    st.markdown("### Support tickets")
    if df_sup.empty: st.caption("No tickets yet.")
    else: st.dataframe(df_sup, use_container_width=True, height=280)



