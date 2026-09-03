"""
AUTO_SCHEDULER — Employee Scheduling Portal
Streamlit + SQLite, no extra services required.

Run: streamlit run AUTO_SCHEDULER/streamlit_app/app.py
"""
import base64, os, sys
from datetime import date, datetime, timedelta

import bcrypt
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database as db

# ── Optional email (SendGrid) ─────────────────────────────────────────────────
try:
    import sendgrid
    from sendgrid.helpers.mail import Mail as SGMail
    _SG_KEY  = os.environ.get("SENDGRID_API_KEY", "")
    _SG_FROM = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@justthetap.com")
    _APP_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501")
    _EMAIL_OK = bool(_SG_KEY)
except ImportError:
    _EMAIL_OK = False


def _send_email(to: str, subject: str, html: str) -> None:
    if not _EMAIL_OK:
        return
    sg = sendgrid.SendGridAPIClient(api_key=_SG_KEY)
    sg.send(SGMail(from_email=_SG_FROM, to_emails=to, subject=subject, html_content=html))


_btn_style = (
    "background:#1e3a5f;color:white;padding:10px 20px;border-radius:6px;"
    "text-decoration:none;display:inline-block;font-family:sans-serif;font-weight:600;"
)

def email_coverage_request(to_email: str, name: str, requester: str, date_s: str, time_s: str, req_id: int) -> None:
    link = f"{_APP_URL}?page=requests&id={req_id}"
    _send_email(to_email, f"Shift Coverage Needed — {date_s}", f"""
    <div style="font-family:sans-serif;max-width:580px;margin:0 auto;padding:24px">
      <h2 style="color:#1e3a5f">AUTO_SCHEDULER</h2>
      <p>Hi {name}, <strong>{requester}</strong> needs coverage for:<br>
      <strong>{date_s}</strong> · {time_s}</p>
      <p><a href="{link}" style="{_btn_style}">View &amp; Accept Shift</a></p>
    </div>""")

def email_time_off_update(to_email: str, name: str, req_type: str, status: str, note: str) -> None:
    color = "#16a34a" if status == "approved" else "#dc2626"
    note_html = f"<p><em>Manager note: {note}</em></p>" if note else ""
    _send_email(to_email, f"Your {req_type} request — {status}", f"""
    <div style="font-family:sans-serif;max-width:580px;margin:0 auto;padding:24px">
      <h2 style="color:#1e3a5f">AUTO_SCHEDULER</h2>
      <p>Hi {name}, your <strong>{req_type}</strong> request has been
      <strong style="color:{color}">{status}</strong>.</p>{note_html}
    </div>""")

def email_shift_blast(to_email: str, name: str, label: str, type_: str, date_s: str, time_s: str) -> None:
    link = f"{_APP_URL}?page=schedule"
    _send_email(to_email, f"Extra Shift Available — {label}", f"""
    <div style="font-family:sans-serif;max-width:580px;margin:0 auto;padding:24px">
      <h2 style="color:#1e3a5f">AUTO_SCHEDULER</h2>
      <p>Hi {name}, a <strong>{type_}</strong> slot is available:<br>
      <strong>{label}</strong> — {date_s} · {time_s}</p>
      <p><a href="{link}" style="{_btn}">View Schedule</a></p>
    </div>""")


# ── Auth helpers ──────────────────────────────────────────────────────────────

def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_pw(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Time helpers ──────────────────────────────────────────────────────────────

def fmt12(t: str) -> str:
    """Convert 'HH:MM' or 'HH:MM:SS' to '3:00 PM'."""
    if not t:
        return ""
    try:
        return datetime.strptime(t[:5], "%H:%M").strftime("%I:%M %p").lstrip("0")
    except Exception:
        return t

DAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAYS_LONG  = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TYPE_EMOJI = {"regular": "🔵", "cleaning": "🟡", "event": "🟣"}

TYPE_LABELS_OFF = {
    "vacation":      "Vacation / Day Off",
    "early_release": "Early Release",
    "adjust_hours":  "Adjust Weekly Hours",
}
STATUS_COLORS = {
    "pending":          ("🟡", "#fef3c7", "#92400e"),
    "approved":         ("✅", "#d1fae5", "#065f46"),
    "denied":           ("❌", "#fee2e2", "#991b1b"),
    "open":             ("🔵", "#dbeafe", "#1e40af"),
    "filled":           ("✅", "#d1fae5", "#065f46"),
    "partially_filled": ("🟡", "#fef3c7", "#92400e"),
    "cancelled":        ("⚫", "#f3f4f6", "#374151"),
    "accepted":         ("✅", "#d1fae5", "#065f46"),
}

def badge(status: str) -> str:
    emoji, bg, fg = STATUS_COLORS.get(status, ("⚪", "#f3f4f6", "#374151"))
    label = status.replace("_", " ").title()
    return f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:999px;font-size:0.75rem;font-weight:600">{emoji} {label}</span>'

def card(content: str) -> None:
    st.markdown(
        f'<div style="background:white;border-radius:12px;padding:20px;margin:8px 0;'
        f'box-shadow:0 1px 4px rgba(0,0,0,.08);border:1px solid #e5e7eb">{content}</div>',
        unsafe_allow_html=True,
    )


# ── CSS ───────────────────────────────────────────────────────────────────────

def _logo_path() -> str:
    """Return path to logo.png inside assets/, or empty string if not found."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
    return p if os.path.exists(p) else ""


def inject_css() -> None:
    st.markdown("""
    <style>
    /* Hide streamlit default top bar chrome — but keep the sidebar toggle visible */
    #MainMenu {visibility:hidden}
    footer {visibility:hidden}
    /* Hide decorative header content but NOT the sidebar collapse button */
    header[data-testid="stHeader"] { background: transparent !important; }
    /* Do NOT hide header children — the sidebar toggle lives there in Streamlit 1.56+ */
    [data-testid="stToolbar"] { visibility: hidden; }
    /* Keep sidebar toggle arrow always visible — cover all known testids */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarNavItems"],
    button[kind="header"] { visibility: visible !important; display: flex !important; }

    /* Ensure sidebar is always rendered and not collapsed away */
    [data-testid="stSidebar"][aria-expanded="false"] { display: block !important; width: 21rem !important; }
    [data-testid="stSidebar"] { display: block !important; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg,#1e3a5f 0%,#152c4a 100%) !important;
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] .stRadio > label { color: #93c5fd !important; font-size:.8rem; font-weight:600; letter-spacing:.05em; text-transform:uppercase; }
    [data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,.1) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,.2) !important;
        border-radius: 8px !important;
        width: 100% !important;
        text-align: left !important;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,.2) !important;
    }

    /* Main background — stone texture applied dynamically below if present */
    .stApp { background-color: #f3f4f6 !important; }
    .block-container { padding-top: 1.5rem !important; }

    /* Inputs */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 8px !important;
        border-color: #d1d5db !important;
    }
    .stTextInput > div > div > input:focus { border-color: #1e3a5f !important; box-shadow: 0 0 0 2px rgba(30,58,95,.2) !important; }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background: #1e3a5f !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover { background: #2a5282 !important; }

    /* Form submit */
    .stForm .stButton button {
        background: #1e3a5f !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
    }

    /* Metric */
    [data-testid="metric-container"] {
        background: white;
        border-radius: 12px;
        padding: 16px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,.06);
    }

    /* Shift calendar cells */
    .shift-cell {
        border-radius: 8px;
        padding: 6px 8px;
        margin: 3px 0;
        font-size: 0.75rem;
        font-weight: 500;
        line-height: 1.4;
    }
    .shift-regular  { background:#dbeafe; color:#1e40af; }
    .shift-cleaning { background:#fef3c7; color:#92400e; }
    .shift-event    { background:#ede9fe; color:#5b21b6; }
    .day-header { font-weight:700; font-size:.9rem; color:#374151; margin-bottom:4px; }
    .day-number { font-size:1.2rem; font-weight:800; color:#1f2937; }
    .today-col  { background:#fefce8; border:2px solid #fbbf24; border-radius:10px; padding:6px; }

    /* Table */
    .jtap-table { width:100%; border-collapse:collapse; font-size:.875rem; }
    .jtap-table th { background:#f9fafb; text-align:left; padding:10px 12px; color:#6b7280; font-size:.75rem; text-transform:uppercase; letter-spacing:.05em; border-bottom:1px solid #e5e7eb; }
    .jtap-table td { padding:10px 12px; border-bottom:1px solid #f3f4f6; color:#374151; }
    .jtap-table tr:hover td { background:#f9fafb; }
    </style>
    """, unsafe_allow_html=True)


# ════════════════════════ PAGE FUNCTIONS ═════════════════════════════════════

# ── Auth pages ────────────────────────────────────────────────────────────────

def page_login() -> None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        logo = _logo_path()
        if logo:
            lcol1, lcol2, lcol3 = st.columns([1, 2, 1])
            with lcol2:
                st.image(logo, use_container_width=True)
        else:
            st.markdown('<h1 style="color:#1e3a5f;text-align:center;margin-bottom:0">AUTO_SCHEDULER</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color:#6b7280;text-align:center;margin-top:4px">Staff Scheduling Portal</p>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        tab_login, tab_reg = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
            if submitted:
                u = db.get_user_by_username(username.strip())
                if u and u["is_active"] and verify_pw(password, u["hashed_password"]):
                    st.session_state.user = u
                    st.session_state.page = "admin_overview" if u["role"] == "admin" else "dashboard"
                    st.rerun()
                else:
                    st.error("Incorrect username or password, or account is inactive.")

        with tab_reg:
            with st.form("register_form"):
                full_name = st.text_input("Full Name")
                reg_user  = st.text_input("Username")
                reg_email = st.text_input("Email")
                reg_pw    = st.text_input("Password (min 8 chars)", type="password")
                reg_pw2   = st.text_input("Confirm Password", type="password")
                reg_sub   = st.form_submit_button("Create Account", use_container_width=True)
            if reg_sub:
                errs = []
                if not full_name.strip(): errs.append("Full name is required.")
                if not reg_user.strip():  errs.append("Username is required.")
                if not reg_email.strip(): errs.append("Email is required.")
                if len(reg_pw) < 8:       errs.append("Password must be at least 8 characters.")
                if reg_pw != reg_pw2:     errs.append("Passwords do not match.")
                if db.get_user_by_username(reg_user.strip()):
                    errs.append("Username already taken.")
                if errs:
                    for e in errs: st.error(e)
                else:
                    db.create_user(reg_user.strip(), reg_email.strip(), hash_pw(reg_pw), full_name.strip())
                    st.success("Account created! Please sign in.")
                    if db.count_users() == 1:
                        st.info("You are the first user — your account has been set as admin.")


# ── Sidebar ───────────────────────────────────────────────────────────────────

def show_sidebar() -> None:
    u = st.session_state.user
    with st.sidebar:
        logo = _logo_path()
        if logo:
            st.image(logo, width=140)
        else:
            st.markdown(f'<h2 style="color:#f59e0b;margin:0 0 4px 0">AUTO_SCHEDULER</h2>', unsafe_allow_html=True)
        st.markdown(f'<p style="color:#93c5fd;font-size:.85rem;margin:0 0 16px 0">👤 {u["full_name"]}</p>', unsafe_allow_html=True)

        # Unread notifications
        unread = db.get_unread_count(u["id"])
        if unread:
            st.markdown(f'<div style="background:#f59e0b;color:#1e3a5f;border-radius:8px;padding:6px 12px;font-size:.8rem;font-weight:700;margin-bottom:12px">🔔 {unread} unread notification{"s" if unread != 1 else ""}</div>', unsafe_allow_html=True)

        st.markdown("---")

        if u["role"] == "admin":
            pages = {
                "admin_overview":       "📊  Overview",
                "admin_shifts":         "📅  Shifts",
                "admin_recurring":      "🔁  Recurring Shifts",
                "admin_auto_schedule":  "🤖  Auto Schedule",
                "admin_labor_stats":    "💰  Labor Stats",
                "admin_employees":      "👥  Employees",
                "admin_skills":         "🎯  Skills & Roles",
                "admin_compatibility":  "🔗  Compatibility",
                "admin_overrides":      "🚫  Availability Blocks",
                "admin_business_hours": "🕐  Business Hours",
                "admin_requests":       "📋  Request Queue",
            }
        else:
            pages = {
                "dashboard":    "🏠  Dashboard",
                "schedule":     "📅  My Schedule",
                "availability": "🗓  Availability",
                "requests":     "🔄  Shift Requests",
                "duties":       "✅  My Duties",
                "time_off":     "✈️  Time Off",
                "recurring":    "🔁  Recurring Shifts",
            }

        current = st.session_state.get("page", list(pages.keys())[0])
        for key, label in pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()

        st.markdown("---")
        if st.button("🔔  Notifications", use_container_width=True):
            st.session_state.page = "notifications"
            st.rerun()
        if st.button("⚙️  Profile", use_container_width=True):
            st.session_state.page = "profile"
            st.rerun()
        if st.button("🚪  Sign Out", use_container_width=True):
            del st.session_state["user"]
            st.session_state.page = "login"
            st.rerun()


# ── Dashboard ─────────────────────────────────────────────────────────────────

def page_dashboard() -> None:
    u = st.session_state.user
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    hcol_logo, hcol_text = st.columns([1, 6])
    with hcol_logo:
        logo = _logo_path()
        if logo:
            st.image(logo, width=80)
    with hcol_text:
        st.markdown(f'<h1 style="color:#1e3a5f;margin-bottom:0">Welcome back, {u["full_name"].split()[0]} 👋</h1>', unsafe_allow_html=True)
        st.caption(f"Week of {week_start.strftime('%B %d')} – {week_end.strftime('%B %d, %Y')}")

    my_shifts = db.get_shifts(
        start_date=week_start.isoformat(),
        end_date=week_end.isoformat(),
        user_id=u["id"],
    )
    open_reqs = db.get_open_coverage_requests(u["id"])

    col1, col2 = st.columns([2, 1], gap="medium")

    with col1:
        st.markdown("### 🕐 My Shifts This Week")
        if not my_shifts:
            card("<p style='color:#9ca3af'>No shifts scheduled this week.</p>")
        else:
            for s in my_shifts:
                d_obj = date.fromisoformat(s["date"])
                emoji = TYPE_EMOJI.get(s["type"], "⚪")
                card(f"""
                <div style="display:flex;justify-content:space-between;align-items:center">
                  <div>
                    <p style="margin:0;font-weight:600;color:#1f2937">{d_obj.strftime('%A, %B %d')}</p>
                    <p style="margin:0;color:#6b7280;font-size:.875rem">{fmt12(s['start_time'])} – {fmt12(s['end_time'])}{(' · ' + s['label']) if s['label'] else ''}</p>
                  </div>
                  <span>{emoji} {s['type'].title()}</span>
                </div>""")

    with col2:
        st.markdown(f"### 🔄 Coverage Needed ({len(open_reqs)})")
        if not open_reqs:
            card("<p style='color:#9ca3af'>No open requests.</p>")
        else:
            for req in open_reqs[:5]:
                d_obj = date.fromisoformat(req["date"])
                card(f"""
                <p style="margin:0;font-weight:600;color:#1f2937">{req['requester_name']}</p>
                <p style="margin:0;color:#6b7280;font-size:.8rem">{d_obj.strftime('%b %d')} · {fmt12(req['shift_start'])}–{fmt12(req['shift_end'])}</p>
                <p style="margin:4px 0 0 0"><a style="color:#1e3a5f;font-size:.8rem;font-weight:600" href="?page=requests&id={req['id']}">View & Respond →</a></p>""")


# ── Schedule ──────────────────────────────────────────────────────────────────

def page_schedule(admin: bool = False) -> None:
    u = st.session_state.user
    today = date.today()

    if "sched_offset" not in st.session_state:
        st.session_state.sched_offset = 0

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=st.session_state.sched_offset)
    week_end   = week_start + timedelta(days=6)

    st.markdown(f'<h1 style="color:#1e3a5f">{"All Shifts" if admin else "My Schedule"}</h1>', unsafe_allow_html=True)

    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 3, 1, 1])
    with nav_col1:
        if st.button("◀ Prev"):
            st.session_state.sched_offset -= 1
            st.rerun()
    with nav_col2:
        st.markdown(f'<p style="text-align:center;font-weight:600;color:#374151;padding-top:6px">{week_start.strftime("%b %d")} – {week_end.strftime("%b %d, %Y")}</p>', unsafe_allow_html=True)
    with nav_col3:
        if st.button("Next ▶"):
            st.session_state.sched_offset += 1
            st.rerun()
    with nav_col4:
        if st.button("Today"):
            st.session_state.sched_offset = 0
            st.rerun()

    uid = None if admin else u["id"]
    shifts = db.get_shifts(start_date=week_start.isoformat(), end_date=week_end.isoformat(), user_id=uid)

    # Visibility: hide employees that should not see each other
    hidden_ids: set = set()
    if not admin:
        hidden_ids = db.get_hidden_user_ids(u["id"])

    cols = st.columns(7)
    for i, col in enumerate(cols):
        day = week_start + timedelta(days=i)
        is_today = (day == today)
        day_shifts = [s for s in shifts if s["date"] == day.isoformat()]

        with col:
            header_style = "border:2px solid #fbbf24;border-radius:10px;padding:8px;background:#fefce8;" if is_today else "border:1px solid #e5e7eb;border-radius:10px;padding:8px;background:white;"
            st.markdown(f'<div style="{header_style}min-height:130px">', unsafe_allow_html=True)
            st.markdown(f'<p class="day-header">{DAYS_SHORT[i]}</p><p class="day-number" style="color:{"#d97706" if is_today else "#1f2937"}">{day.day}</p>', unsafe_allow_html=True)
            if not day_shifts:
                st.markdown('<p style="color:#d1d5db;font-size:.75rem">—</p>', unsafe_allow_html=True)
            for s in day_shifts:
                cls = f"shift-{s['type']}"
                assigned_id = s.get("assigned_user_id")
                if not admin and assigned_id and assigned_id != u["id"] and assigned_id in hidden_ids:
                    name_part = ""
                else:
                    name_part = f"<br><span style='opacity:.7'>{s['assigned_name'] or ''}</span>" if (admin or True) and s.get("assigned_name") else ""
                st.markdown(
                    f'<div class="shift-cell {cls}">{fmt12(s["start_time"])}<br>{fmt12(s["end_time"])}{name_part}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    lcol, mcol, rcol = st.columns(3)
    with lcol: st.markdown("🔵 Regular")
    with mcol: st.markdown("🟡 Cleaning")
    with rcol: st.markdown("🟣 Event")

    # Rating section — employees rate their own assigned shifts
    if not admin:
        my_week_shifts = [s for s in shifts if s.get("assigned_user_id") == u["id"]]
        if my_week_shifts:
            st.markdown("---")
            st.markdown("### 👍👎 Rate Your Shifts")
            st.caption("Your ratings help improve future schedules.")
            for s in my_week_shifts:
                existing = db.get_shift_rating(u["id"], s["id"])
                current_rating = existing["rating"] if existing else 0
                d_obj = date.fromisoformat(s["date"])
                rc1, rc2, rc3, rc4 = st.columns([3, 1, 1, 1])
                with rc1:
                    st.markdown(f"**{d_obj.strftime('%a %b %d')}** · {fmt12(s['start_time'])}–{fmt12(s['end_time'])}")
                with rc2:
                    if st.button("👍", key=f"up_{s['id']}", help="Good shift / keep me on this",
                                 type="primary" if current_rating == 1 else "secondary"):
                        db.rate_shift(u["id"], s["id"], 1)
                        st.rerun()
                with rc3:
                    if st.button("👎", key=f"dn_{s['id']}", help="Not a good fit for me",
                                 type="primary" if current_rating == -1 else "secondary"):
                        db.rate_shift(u["id"], s["id"], -1)
                        st.rerun()
                with rc4:
                    if current_rating != 0 and st.button("✕", key=f"clr_{s['id']}", help="Clear rating"):
                        db.remove_rating(u["id"], s["id"])
                        st.rerun()


# ── Availability ──────────────────────────────────────────────────────────────

def page_availability() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">My Availability</h1>', unsafe_allow_html=True)

    entries = db.get_user_availability(u["id"])

    with st.expander("➕ Add Availability", expanded=True):
        with st.form("avail_form"):
            mode = st.radio("Type", ["Recurring weekly", "Specific date"], horizontal=True)
            if mode == "Recurring weekly":
                day_idx = st.selectbox("Day of Week", range(7), format_func=lambda i: DAYS_LONG[i])
                spec_date = None
            else:
                spec_date = st.date_input("Date")
                day_idx = None
            c1, c2 = st.columns(2)
            with c1: start_t = st.time_input("Available from", value=datetime.strptime("09:00", "%H:%M").time())
            with c2: end_t   = st.time_input("Available until", value=datetime.strptime("17:00", "%H:%M").time())
            notes = st.text_input("Notes (optional)", placeholder="e.g. prefer morning shifts")
            if st.form_submit_button("Save Availability", use_container_width=True):
                if start_t >= end_t:
                    st.error("End time must be after start time.")
                else:
                    db.create_availability(
                        u["id"],
                        day_idx,
                        spec_date.isoformat() if spec_date else None,
                        start_t.strftime("%H:%M"),
                        end_t.strftime("%H:%M"),
                        notes,
                    )
                    st.success("Availability saved!")
                    st.rerun()

    recurring = [e for e in entries if e["day_of_week"] is not None]
    specific  = [e for e in entries if e["specific_date"] is not None]

    st.markdown("### 📅 Weekly Recurring")
    if not recurring:
        st.caption("No recurring availability set.")
    else:
        for e in sorted(recurring, key=lambda x: x["day_of_week"]):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{DAYS_LONG[e['day_of_week']]}** — {fmt12(e['start_time'])} – {fmt12(e['end_time'])}" + (f" · {e['notes']}" if e['notes'] else ""))
            with c2:
                if st.button("🗑", key=f"del_avail_{e['id']}"):
                    db.delete_availability(e["id"], u["id"])
                    st.rerun()

    st.markdown("### 📌 Specific Dates")
    if not specific:
        st.caption("No specific date overrides.")
    else:
        for e in specific:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{e['specific_date']}** — {fmt12(e['start_time'])} – {fmt12(e['end_time'])}" + (f" · {e['notes']}" if e['notes'] else ""))
            with c2:
                if st.button("🗑", key=f"del_specific_{e['id']}"):
                    db.delete_availability(e["id"], u["id"])
                    st.rerun()


# ── Shift Requests ────────────────────────────────────────────────────────────

def page_requests() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">Shift Requests</h1>', unsafe_allow_html=True)

    # Deep-link: land on a specific request
    focus_id = None
    params = st.query_params
    if "id" in params:
        try: focus_id = int(params["id"])
        except Exception: pass

    my_reqs  = db.get_my_coverage_requests(u["id"])
    open_reqs = db.get_open_coverage_requests(u["id"])

    tab_mine, tab_open, tab_new = st.tabs([
        f"My Requests ({len(my_reqs)})",
        f"Available to Cover ({len(open_reqs)})",
        "Request Coverage",
    ])

    # ── My requests ──
    with tab_mine:
        if not my_reqs:
            st.caption("You have no coverage requests.")
        for req in my_reqs:
            d_obj = date.fromisoformat(req["date"])
            win_start = req.get("partial_start") or req["shift_start"]
            win_end   = req.get("partial_end")   or req["shift_end"]
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{d_obj.strftime('%A, %B %d')}** · {fmt12(win_start)} – {fmt12(win_end)}")
                    if req.get("reason"):
                        st.caption(f'"{req["reason"]}"')
                    if req.get("requested_duration"):
                        st.caption(f"Desired duration: {req['requested_duration']} minutes")
                    req_skills = db.get_coverage_request_skills(req["id"])
                    if req_skills:
                        pills = " ".join(
                            f'<span style="background:{s["color"]};color:white;padding:2px 8px;border-radius:999px;font-size:.75rem">{"★ " if s["required"] else ""}{s["name"]}</span>'
                            for s in req_skills
                        )
                        st.markdown(pills, unsafe_allow_html=True)
                with c2:
                    st.markdown(badge(req["status"]), unsafe_allow_html=True)

                offers = db.get_offer_for_request(req["id"])
                if offers:
                    st.markdown(f"**{len(offers)} offer(s):**")
                    for offer in offers:
                        oc1, oc2 = st.columns([4, 1])
                        with oc1:
                            st.markdown(f"👤 {offer['offerer_name']} · {fmt12(offer['covers_start'])}–{fmt12(offer['covers_end'])}")
                        with oc2:
                            if offer["status"] == "pending":
                                if st.button("Accept", key=f"acc_{offer['id']}"):
                                    db.accept_coverage_offer(offer["id"], req["id"])
                                    db.create_notification(
                                        offer["offering_user_id"],
                                        "Coverage Offer Accepted",
                                        "Your offer to cover a shift has been accepted.",
                                    )
                                    st.success("Offer accepted!")
                                    st.rerun()
                            else:
                                st.markdown(badge(offer["status"]), unsafe_allow_html=True)

    # ── Open to cover ──
    with tab_open:
        if not open_reqs:
            st.caption("No open coverage requests right now.")
        for req in open_reqs:
            d_obj = date.fromisoformat(req["date"])
            win_start = req.get("partial_start") or req["shift_start"]
            win_end   = req.get("partial_end")   or req["shift_end"]
            highlighted = (focus_id == req["id"])
            with st.container(border=True):
                if highlighted:
                    st.markdown("⭐ **This request was linked from your email**")
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{req['requester_name']}** · {d_obj.strftime('%b %d')} · {fmt12(win_start)}–{fmt12(win_end)}")
                    if req.get("reason"):
                        st.caption(f'"{req["reason"]}"')
                    if req.get("requested_duration"):
                        st.caption(f"Desired duration: {req['requested_duration']} minutes")
                    req_skills = db.get_coverage_request_skills(req["id"])
                    if req_skills:
                        pills = " ".join(
                            f'<span style="background:{s["color"]};color:white;padding:2px 8px;border-radius:999px;font-size:.75rem">{"★ " if s["required"] else ""}{s["name"]}</span>'
                            for s in req_skills
                        )
                        st.markdown(pills, unsafe_allow_html=True)
                with c2:
                    st.markdown(badge(req["status"]), unsafe_allow_html=True)

                offer_key = f"offer_{req['id']}"
                if st.button("Offer to Cover", key=f"btn_{offer_key}"):
                    st.session_state[offer_key] = True

                if st.session_state.get(offer_key):
                    with st.form(f"form_{offer_key}"):
                        oc1, oc2 = st.columns(2)
                        with oc1: cs = st.time_input("I can cover from", value=datetime.strptime(win_start[:5], "%H:%M").time(), key=f"cs_{req['id']}")
                        with oc2: ce = st.time_input("Until", value=datetime.strptime(win_end[:5], "%H:%M").time(), key=f"ce_{req['id']}")
                        sc1, sc2 = st.columns(2)
                        with sc1: sub = st.form_submit_button("Submit Offer")
                        with sc2: cancel = st.form_submit_button("Cancel")
                    if sub:
                        db.create_coverage_offer(req["id"], u["id"], cs.strftime("%H:%M"), ce.strftime("%H:%M"))
                        db.create_notification(req["requesting_user_id"], "New Coverage Offer",
                            f"{u['full_name']} offered to cover {fmt12(cs.strftime('%H:%M'))}–{fmt12(ce.strftime('%H:%M'))}.",
                            deep_link=f"requests:{req['id']}")
                        st.success("Offer submitted!")
                        del st.session_state[offer_key]
                        st.rerun()
                    if cancel:
                        del st.session_state[offer_key]
                        st.rerun()

    # ── New request ──
    with tab_new:
        my_shifts = db.get_shifts(user_id=u["id"])
        future_shifts = [s for s in my_shifts if s["date"] >= date.today().isoformat()]
        if not future_shifts:
            st.caption("No upcoming shifts to request coverage for.")
        else:
            with st.form("new_req_form"):
                shift_opts = {s["id"]: f"{date.fromisoformat(s['date']).strftime('%a %b %d')} · {fmt12(s['start_time'])}–{fmt12(s['end_time'])}" for s in future_shifts}
                chosen_id = st.selectbox("Select Shift", options=list(shift_opts.keys()), format_func=lambda x: shift_opts[x])
                reason = st.text_input("Reason (optional)", placeholder="e.g. doctor's appointment")
                desired_duration = st.number_input("Desired coverage duration (minutes)", min_value=0, max_value=720, step=15, value=0, help="Optional target duration; actual coverage may vary.")
                skills = db.get_skills()
                skill_ids = [s["id"] for s in skills]
                required_skill_ids = st.multiselect(
                    "Required skills",
                    skill_ids,
                    format_func=lambda i: next((s['name'] for s in skills if s['id'] == i), str(i)),
                    default=[],
                )
                preferred_skill_ids = st.multiselect(
                    "Preferred skills",
                    [s for s in skill_ids if s not in required_skill_ids],
                    format_func=lambda i: next((s['name'] for s in skills if s['id'] == i), str(i)),
                    default=[],
                )
                st.markdown("**Partial coverage only?** (leave blank for full shift)")
                pc1, pc2 = st.columns(2)
                with pc1: partial_start = st.text_input("Coverage needed from (HH:MM)", placeholder="e.g. 14:00")
                with pc2: partial_end   = st.text_input("Until (HH:MM)", placeholder="e.g. 18:00")
                submitted = st.form_submit_button("Send Coverage Request to Team", use_container_width=True)
            if submitted:
                req_id = db.create_coverage_request(
                    chosen_id,
                    u["id"],
                    reason,
                    partial_start or None,
                    partial_end or None,
                    desired_duration or None,
                )
                for sid in required_skill_ids:
                    db.add_coverage_request_skill(req_id, sid, required=1)
                for sid in preferred_skill_ids:
                    db.add_coverage_request_skill(req_id, sid, required=0)
                recipients = db.fan_out_coverage_request(req_id, u["id"])
                chosen_shift = next(s for s in future_shifts if s["id"] == chosen_id)
                for r in recipients:
                    email_coverage_request(
                        r["email"], r["full_name"], u["full_name"],
                        chosen_shift["date"],
                        f"{fmt12(chosen_shift['start_time'])}–{fmt12(chosen_shift['end_time'])}",
                        req_id,
                    )
                st.success(f"Request sent to {len(recipients)} team member(s)!")
                st.rerun()


# ── Time Off ──────────────────────────────────────────────────────────────────

def page_time_off() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">Time Off & Requests</h1>', unsafe_allow_html=True)

    with st.expander("➕ Submit New Request", expanded=True):
        with st.form("timeoff_form"):
            type_ = st.selectbox("Request Type", list(TYPE_LABELS_OFF.keys()), format_func=lambda k: TYPE_LABELS_OFF[k])
            c1, c2 = st.columns(2)
            with c1: start_dt = st.date_input("Start Date")
            with c2: start_time_val = st.time_input("Start Time" if type_ == "early_release" else "Time (optional)", value=datetime.strptime("09:00", "%H:%M").time())
            end_dt = None
            if type_ != "early_release":
                end_dt = st.date_input("End Date (optional, leave same as start for single day)", value=start_dt)
            reason = st.text_area("Reason (optional)", height=80)
            if st.form_submit_button("Submit Request", use_container_width=True):
                start_iso = datetime.combine(start_dt, start_time_val).isoformat()
                end_iso   = end_dt.isoformat() if end_dt and end_dt != start_dt else None
                db.create_time_off_request(u["id"], type_, start_iso, end_iso, reason)
                st.success("Request submitted! Your manager will review it.")
                st.rerun()

    st.markdown("### 📋 My Requests")
    requests = db.get_time_off_requests(user_id=u["id"])
    if not requests:
        st.caption("No requests yet.")
    else:
        for r in requests:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{TYPE_LABELS_OFF.get(r['type'], r['type'])}** — {r['start_datetime'][:10]}" + (f" → {r['end_datetime'][:10]}" if r.get("end_datetime") else ""))
                    if r.get("reason"): st.caption(f'"{r["reason"]}"')
                    if r.get("admin_note"): st.info(f"Manager note: {r['admin_note']}")
                with c2:
                    st.markdown(badge(r["status"]), unsafe_allow_html=True)


# ── Profile ───────────────────────────────────────────────────────────────────

def page_profile() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">My Profile</h1>', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### Profile Information")
        with st.form("profile_form"):
            full_name = st.text_input("Full Name", value=u["full_name"])
            email     = st.text_input("Email", value=u["email"])
            st.text_input("Username", value=u["username"], disabled=True, help="Usernames cannot be changed.")
            if st.form_submit_button("Save Changes"):
                db.update_user(u["id"], full_name=full_name.strip(), email=email.strip())
                st.session_state.user = db.get_user_by_id(u["id"])
                st.success("Profile updated!")
                st.rerun()

    with st.container(border=True):
        st.markdown("#### Notification Preferences")
        st.caption("Turn off to stop receiving shift coverage request emails and alerts.")
        current = bool(u["receive_shift_requests"])
        new_val = st.toggle("Receive shift coverage requests", value=current)
        if new_val != current:
            db.update_user(u["id"], receive_shift_requests=int(new_val))
            st.session_state.user = db.get_user_by_id(u["id"])
            st.success(f"Shift request alerts {'enabled' if new_val else 'disabled'}.")
            st.rerun()

    with st.container(border=True):
        st.markdown("#### Account")
        st.markdown(f"**Role:** {u['role'].title()}")
        st.markdown(f"**Member since:** {u['created_at'][:10]}")

    # Duty / skill preferences
    skills = db.get_skills()
    if skills:
        st.markdown("---")
        st.markdown("### 🎯 Duty Preferences")
        st.caption("Tell the algorithm which duties you enjoy or want to avoid. This nudges your schedule toward your preferred work.")
        prefs = {p["skill_id"]: p["preference"] for p in db.get_duty_preferences(u["id"])}
        PREF_OPTIONS = {1: "👍 Like", 0: "😐 Neutral", -1: "👎 Dislike"}
        for sk in skills:
            cur = prefs.get(sk["id"], 0)
            idx = [1, 0, -1].index(cur)
            col_t, col_sel = st.columns([2, 2])
            with col_t:
                st.markdown(f'<span style="background:{sk["color"]};color:white;padding:2px 10px;border-radius:999px;font-size:.8rem">{sk["name"]}</span>', unsafe_allow_html=True)
            with col_sel:
                new_pref = st.selectbox("", [1, 0, -1], index=idx,
                                         format_func=lambda x: PREF_OPTIONS[x],
                                         key=f"pref_{sk['id']}", label_visibility="collapsed")
                if new_pref != cur:
                    db.set_duty_preference(u["id"], sk["id"], new_pref)
                    st.rerun()


# ── Notifications ─────────────────────────────────────────────────────────────

def page_notifications() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">Notifications</h1>', unsafe_allow_html=True)

    notifs = db.get_notifications(u["id"])
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("Mark all read"):
            db.mark_all_read(u["id"])
            st.rerun()

    if not notifs:
        st.caption("No notifications yet.")
    else:
        for n in notifs:
            bg = "#eff6ff" if not n["is_read"] else "white"
            with st.container(border=True):
                cols = st.columns([5, 1])
                with cols[0]:
                    st.markdown(f'<div style="background:{bg};border-radius:8px;padding:8px"><strong style="color:#1e3a5f">{n["title"]}</strong><br><span style="color:#374151;font-size:.875rem">{n["message"]}</span><br><span style="color:#9ca3af;font-size:.75rem">{n["created_at"][:16].replace("T"," ")}</span></div>', unsafe_allow_html=True)
                with cols[1]:
                    if not n["is_read"]:
                        if st.button("✓", key=f"read_{n['id']}"):
                            db.mark_one_read(n["id"], u["id"])
                            st.rerun()
                    # Handle deep-links
                    if n.get("deep_link"):
                        link = n["deep_link"]
                        if link.startswith("requests:"):
                            req_id = link.split(":")[1]
                            if st.button("→", key=f"link_{n['id']}"):
                                st.session_state.page = "requests"
                                st.query_params["id"] = req_id
                                st.rerun()
                        elif link == "schedule":
                            if st.button("→", key=f"link_{n['id']}"):
                                st.session_state.page = "schedule"
                                st.rerun()


# ════════════════════════ ADMIN PAGES ════════════════════════════════════════

def page_admin_overview() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Admin Overview</h1>', unsafe_allow_html=True)

    users   = db.get_all_users()
    pending = [r for r in db.get_time_off_requests() if r["status"] == "pending"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Staff",     sum(1 for u in users if u["is_active"]))
    c2.metric("Inactive Staff",   sum(1 for u in users if not u["is_active"]))
    c3.metric("Total Employees",  len(users))
    c4.metric("Pending Requests", len(pending), delta=f"{len(pending)} need review" if pending else None,
              delta_color="inverse" if pending else "off")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ⏳ Pending Time-Off Requests")
    if not pending:
        st.caption("No pending requests.")
    else:
        for r in pending[:5]:
            with st.container(border=True):
                st.markdown(f"**{r['full_name']}** (@{r['username']}) · {TYPE_LABELS_OFF.get(r['type'], r['type'])} · {r['start_datetime'][:10]}")
        if len(pending) > 5:
            if st.button(f"View all {len(pending)} requests"):
                st.session_state.page = "admin_requests"
                st.rerun()


def page_admin_shifts() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Shift Management</h1>', unsafe_allow_html=True)
    users = [u for u in db.get_all_users() if u["is_active"]]

    # Schedule view at top
    page_schedule(admin=True)
    st.markdown("---")

    with st.expander("➕ Create New Shift", expanded=False):
        with st.form("create_shift_form"):
            c1, c2, c3 = st.columns(3)
            with c1: shift_date = st.date_input("Date", value=date.today())
            with c2: shift_start = st.time_input("Start Time", value=datetime.strptime("09:00", "%H:%M").time())
            with c3: shift_end   = st.time_input("End Time",   value=datetime.strptime("17:00", "%H:%M").time())
            c4, c5, c6 = st.columns(3)
            with c4:
                shift_type = st.selectbox("Type", ["regular", "cleaning", "event"],
                                          format_func=lambda t: t.title())
                if shift_type in ("cleaning", "event"):
                    st.caption("⚡ All opted-in employees will be notified.")
            with c5: shift_label = st.text_input("Label (optional)", placeholder="e.g. Happy Hour")
            with c6: assigned = st.selectbox("Assign To", [None] + [u["id"] for u in users],
                                              format_func=lambda x: "— Unassigned —" if x is None else next(u["full_name"] for u in users if u["id"] == x))
            if st.form_submit_button("Create Shift", use_container_width=True):
                if shift_start >= shift_end:
                    st.error("End time must be after start time.")
                else:
                    sid = db.create_shift(
                        shift_date.isoformat(),
                        shift_start.strftime("%H:%M"),
                        shift_end.strftime("%H:%M"),
                        shift_type, shift_label, assigned,
                    )
                    if shift_type in ("cleaning", "event"):
                        recipients = db.blast_shift(sid)
                        shift_obj = db.get_shift_by_id(sid)
                        label = shift_label or shift_type.title()
                        for r in recipients:
                            email_shift_blast(
                                r["email"], r["full_name"], label, shift_type,
                                shift_date.isoformat(),
                                f"{fmt12(shift_start.strftime('%H:%M'))}–{fmt12(shift_end.strftime('%H:%M'))}",
                            )
                        st.success(f"Shift created. {len(recipients)} employee(s) notified.")
                    else:
                        st.success("Shift created.")
                    st.rerun()

    st.markdown("### All Shifts")
    filter_date = st.date_input("Filter by date (optional)", value=None, key="shift_filter_date")
    if filter_date:
        shifts = db.get_shifts(start_date=filter_date.isoformat(), end_date=filter_date.isoformat())
    else:
        shifts = db.get_shifts()

    if not shifts:
        st.caption("No shifts found.")
    else:
        rows_html = "".join(f"""
            <tr>
              <td>{date.fromisoformat(s['date']).strftime('%a, %b %d')}</td>
              <td>{fmt12(s['start_time'])} – {fmt12(s['end_time'])}</td>
              <td>{TYPE_EMOJI.get(s['type'],'⚪')} {(s.get('label') or s['type']).title()}</td>
              <td>{s.get('assigned_name') or '<span style="color:#9ca3af">Unassigned</span>'}</td>
              <td>{badge(s['status'])}</td>
            </tr>"""
        for s in shifts)
        st.markdown(f'<table class="jtap-table"><thead><tr><th>Date</th><th>Time</th><th>Type</th><th>Assigned To</th><th>Status</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

    st.markdown("---")
    page_admin_shift_duties()


def page_admin_employees() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Employee Management</h1>', unsafe_allow_html=True)
    users = db.get_all_users()
    all_skills = db.get_skills()

    tab_list, tab_edit, tab_rank, tab_skills = st.tabs(["📋 All Staff", "✏️ Edit", "⭐ Priority Ranking", "🎯 Skills"])

    with tab_list:
        rows_html = ""
        for u in users:
            opacity = "" if u["is_active"] else "opacity:.45;"
            rate = u.get("hourly_rate") or 15.0
            rank = u.get("priority_rank") or 100
            rows_html += f"""
            <tr style="{opacity}">
              <td><strong>{u['full_name']}</strong></td>
              <td style="color:#6b7280">@{u['username']}</td>
              <td>{'<span style="background:#1e3a5f;color:white;padding:2px 8px;border-radius:999px;font-size:.75rem">Admin</span>' if u['role']=='admin' else '<span style="background:#f3f4f6;font-size:.75rem;padding:2px 8px;border-radius:999px">Employee</span>'}</td>
              <td>${rate:.2f}/hr</td>
              <td>#{rank}</td>
              <td>{badge('approved' if u['is_active'] else 'cancelled').replace('Approved','Active').replace('Cancelled','Inactive')}</td>
            </tr>"""
        st.markdown(f'<table class="jtap-table"><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Rate</th><th>Priority</th><th>Status</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

    with tab_edit:
        user_opts = {u["id"]: f"{u['full_name']} (@{u['username']})" for u in users}
        sel_id = st.selectbox("Select employee", options=list(user_opts.keys()), format_func=lambda x: user_opts[x])
        sel_user = next(u for u in users if u["id"] == sel_id)
        with st.form("edit_emp_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_role   = st.selectbox("Role", ["employee", "admin"], index=0 if sel_user["role"] == "employee" else 1)
                new_active = st.selectbox("Status", [True, False], format_func=lambda x: "Active" if x else "Inactive",
                                          index=0 if sel_user["is_active"] else 1)
            with c2:
                new_rate  = st.number_input("Hourly Rate ($)", min_value=0.0, value=float(sel_user.get("hourly_rate") or 15.0), step=0.25)
                new_hours = st.number_input("Desired Weekly Hours", min_value=0, max_value=168, value=int(sel_user.get("desired_weekly_hours") or 20))
            if st.form_submit_button("Save Changes", use_container_width=True):
                db.update_user(sel_id, role=new_role, is_active=int(new_active),
                               hourly_rate=new_rate, desired_weekly_hours=new_hours)
                st.success("Employee updated.")
                st.rerun()

    with tab_rank:
        st.caption("Lower rank number = higher priority in the scheduling algorithm. Rank 1 = your best/most-trusted employee.")
        sorted_users = sorted(users, key=lambda x: (x.get("priority_rank") or 100))
        for u in sorted_users:
            rc1, rc2 = st.columns([4, 2])
            with rc1:
                st.markdown(f"**{u['full_name']}** — current rank: **{u.get('priority_rank') or 100}**")
            with rc2:
                new_rank = st.number_input("Rank", min_value=1, max_value=9999,
                                            value=int(u.get("priority_rank") or 100),
                                            key=f"rank_{u['id']}", label_visibility="collapsed")
                if new_rank != (u.get("priority_rank") or 100):
                    db.update_user(u["id"], priority_rank=new_rank)
                    st.rerun()

    with tab_skills:
        user_opts2 = {u["id"]: f"{u['full_name']} (@{u['username']})" for u in users}
        sel_id2 = st.selectbox("Select employee to manage skills", options=list(user_opts2.keys()),
                                format_func=lambda x: user_opts2[x], key="skills_emp_sel")
        emp_skills = {s["skill_id"]: s for s in db.get_employee_skills(sel_id2)}
        PROF = {1: "Basic", 2: "Competent", 3: "Expert"}
        st.markdown("**Assigned Skills:**")
        if not emp_skills:
            st.caption("No skills assigned yet.")
        for skill_id, s in emp_skills.items():
            sc1, sc2, sc3 = st.columns([3, 2, 1])
            with sc1:
                st.markdown(f'<span style="background:{s["color"]};color:white;padding:2px 10px;border-radius:999px;font-size:.8rem">{s["name"]}</span>', unsafe_allow_html=True)
            with sc2:
                new_prof = st.selectbox("", [1, 2, 3], index=s["proficiency"] - 1,
                                         format_func=lambda x: PROF[x],
                                         key=f"prof_{sel_id2}_{skill_id}", label_visibility="collapsed")
                if new_prof != s["proficiency"]:
                    db.set_employee_skill(sel_id2, skill_id, new_prof)
                    st.rerun()
            with sc3:
                if st.button("✕", key=f"rmskill_{sel_id2}_{skill_id}"):
                    db.remove_employee_skill(sel_id2, skill_id)
                    st.rerun()

        unassigned = [sk for sk in all_skills if sk["id"] not in emp_skills]
        if unassigned:
            st.markdown("**Add Skill:**")
            ac1, ac2 = st.columns([3, 1])
            with ac1:
                add_skill_id = st.selectbox("Skill to add", [sk["id"] for sk in unassigned],
                                             format_func=lambda x: next(s["name"] for s in unassigned if s["id"] == x),
                                             key="add_skill_sel")
            with ac2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Add Skill", key="add_skill_btn"):
                    db.set_employee_skill(sel_id2, add_skill_id, 1)
                    st.rerun()


def page_admin_business_hours() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Business Hours</h1>', unsafe_allow_html=True)
    hours = db.get_business_hours()

    with st.form("biz_hours_form"):
        updated = []
        for h in hours:
            c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
            with c1: st.markdown(f"**{DAYS_LONG[h['day_of_week']]}**")
            with c2: is_closed = st.checkbox("Closed", value=bool(h["is_closed"]), key=f"closed_{h['day_of_week']}")
            if not is_closed:
                with c3: ot = st.time_input("Open", value=datetime.strptime(h["open_time"], "%H:%M").time(), key=f"open_{h['day_of_week']}")
                with c4: ct = st.time_input("Close", value=datetime.strptime(h["close_time"], "%H:%M").time(), key=f"close_{h['day_of_week']}")
                updated.append({"day_of_week": h["day_of_week"], "open_time": ot.strftime("%H:%M"), "close_time": ct.strftime("%H:%M"), "is_closed": 0})
            else:
                updated.append({"day_of_week": h["day_of_week"], "open_time": h["open_time"], "close_time": h["close_time"], "is_closed": 1})
        if st.form_submit_button("Save Business Hours", use_container_width=True):
            db.save_business_hours(updated)
            st.success("Business hours saved!")
            st.rerun()


def page_admin_requests() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Request Queue</h1>', unsafe_allow_html=True)
    users_map = {u["id"]: u for u in db.get_all_users()}

    filter_status = st.radio("Filter", ["pending", "approved", "denied", "all"], horizontal=True)
    all_requests = db.get_time_off_requests()
    visible = [r for r in all_requests if filter_status == "all" or r["status"] == filter_status]

    if not visible:
        st.caption(f"No {filter_status if filter_status != 'all' else ''} requests.")
    else:
        for r in visible:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{r['full_name']}** (@{r['username']})")
                    st.markdown(f"{TYPE_LABELS_OFF.get(r['type'], r['type'])} · {r['start_datetime'][:10]}" + (f" → {r['end_datetime'][:10]}" if r.get("end_datetime") else ""))
                    if r.get("reason"): st.caption(f'"{r["reason"]}"')
                with c2:
                    st.markdown(badge(r["status"]), unsafe_allow_html=True)

                if r["status"] == "pending":
                    with st.form(f"approve_form_{r['id']}"):
                        note = st.text_input("Note to employee (optional)", key=f"note_{r['id']}")
                        ac1, ac2, _ = st.columns([1, 1, 3])
                        with ac1: approve = st.form_submit_button("Approve ✅")
                        with ac2: deny    = st.form_submit_button("Deny ❌")
                    user_obj = users_map.get(r["user_id"])
                    if approve:
                        db.update_time_off_status(r["id"], "approved", note)
                        db.create_notification(r["user_id"], f"{TYPE_LABELS_OFF.get(r['type'], r['type'])} Approved ✅", "Your request has been approved.")
                        if user_obj: email_time_off_update(user_obj["email"], user_obj["full_name"], r["type"], "approved", note)
                        st.success("Approved.")
                        st.rerun()
                    if deny:
                        db.update_time_off_status(r["id"], "denied", note)
                        db.create_notification(r["user_id"], f"{TYPE_LABELS_OFF.get(r['type'], r['type'])} Denied", "Your request has been denied.")
                        if user_obj: email_time_off_update(user_obj["email"], user_obj["full_name"], r["type"], "denied", note)
                        st.success("Denied.")
                        st.rerun()
                elif r.get("admin_note"):
                    st.caption(f'Note sent: "{r["admin_note"]}"')


# ════════════════════════ MAIN ════════════════════════════════════════════════

def page_admin_recurring() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Recurring Shifts</h1>', unsafe_allow_html=True)
    st.caption("Recurring shifts are templates the Auto Scheduler uses to build each week's schedule.")
    all_skills = db.get_skills()

    with st.expander("➕ Add Recurring Shift Template", expanded=True):
        with st.form("rec_form"):
            c1, c2, c3 = st.columns(3)
            with c1: r_day  = st.selectbox("Day of Week", range(7), format_func=lambda i: DAYS_LONG[i])
            with c2: r_st   = st.time_input("Start Time", value=datetime.strptime("11:00", "%H:%M").time())
            with c3: r_et   = st.time_input("End Time",   value=datetime.strptime("19:00", "%H:%M").time())
            c4, c5, c6, c7 = st.columns(4)
            with c4: r_type  = st.selectbox("Type", ["regular", "cleaning", "event"], format_func=str.title)
            with c5: r_label = st.text_input("Label", placeholder="e.g. Dinner Service")
            with c6: r_min   = st.number_input("Min Staff", 1, 20, 1)
            with c7: r_max   = st.number_input("Max Staff", 1, 20, 3)
            if st.form_submit_button("Create Template", use_container_width=True):
                if r_st >= r_et:
                    st.error("End time must be after start time.")
                else:
                    db.create_recurring_shift(
                        r_day,
                        r_st.strftime("%H:%M"),
                        r_et.strftime("%H:%M"),
                        r_type,
                        r_label,
                        r_min,
                        r_max,
                        created_by=st.session_state.user["id"],
                    )
                    st.success("Recurring shift created!")
                    st.rerun()

    recurring = db.get_recurring_shifts(active_only=True)
    users_map = {u['id']: u for u in db.get_all_users()}
    st.markdown(f"### Active Templates ({len(recurring)})")
    if not recurring:
        st.caption("No recurring shift templates yet.")
    else:
        for r in recurring:
            with st.container(border=True):
                hc1, hc2, hc3 = st.columns([4, 2, 1])
                with hc1:
                    st.markdown(f"**{DAYS_LONG[r['day_of_week']]}** · {fmt12(r['start_time'])} – {fmt12(r['end_time'])}")
                    st.caption(f"{TYPE_EMOJI.get(r['type'],'⚪')} {r.get('label') or r['type'].title()} · {r['min_staff']}–{r['max_staff']} staff")
                with hc2:
                    if r.get("created_by"):
                        creator = users_map.get(r["created_by"], {}).get("full_name", "Unknown")
                        st.caption(f"Created by {creator}")
                    r_skills = db.get_recurring_shift_skills(r["id"])
                    if r_skills:
                        pills = " ".join(
                            f'<span style="background:{s["color"]};color:white;padding:1px 8px;border-radius:999px;font-size:.7rem">{"★ " if s["required"] else ""}{s["name"]}</span>'
                            for s in r_skills
                        )
                        st.markdown(pills, unsafe_allow_html=True)
                    else:
                        st.caption("No skill requirements")
                with hc3:
                    if st.button("🗑", key=f"del_rec_{r['id']}", help="Deactivate"):
                        db.deactivate_recurring_shift(r["id"])
                        st.rerun()

                # Skill assignment
                with st.expander("Manage required skills"):
                    assigned_skill_ids = {s["skill_id"] for s in db.get_recurring_shift_skills(r["id"])}
                    unassigned = [sk for sk in all_skills if sk["id"] not in assigned_skill_ids]
                    for s in db.get_recurring_shift_skills(r["id"]):
                        sc1, sc2 = st.columns([4, 1])
                        with sc1:
                            req_label = "Required" if s["required"] else "Preferred"
                            st.markdown(f'<span style="background:{s["color"]};color:white;padding:2px 8px;border-radius:999px;font-size:.75rem">{s["name"]}</span> <span style="font-size:.75rem;color:#6b7280">{req_label}</span>', unsafe_allow_html=True)
                        with sc2:
                            if st.button("✕", key=f"rmrs_{r['id']}_{s['skill_id']}"):
                                db.remove_recurring_shift_skill(r["id"], s["skill_id"])
                                st.rerun()
                    if unassigned:
                        ac1, ac2, ac3 = st.columns([3, 2, 1])
                        with ac1: add_sid = st.selectbox("Skill", [s["id"] for s in unassigned],
                                                           format_func=lambda x: next(s["name"] for s in unassigned if s["id"] == x),
                                                           key=f"rsk_sel_{r['id']}")
                        with ac2: req_flag = st.selectbox("Level", [0, 1], format_func=lambda x: "Required" if x else "Preferred",
                                                            key=f"rsk_req_{r['id']}")
                        with ac3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("Add", key=f"rsk_add_{r['id']}"):
                                db.add_recurring_shift_skill(r["id"], add_sid, req_flag)
                                st.rerun()


def page_employee_recurring() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">Recurring Shifts</h1>', unsafe_allow_html=True)
    st.caption("Create recurring shift templates for the Auto Scheduler and manage skill requirements.")
    all_skills = db.get_skills()

    with st.expander("➕ Add Recurring Shift Template", expanded=True):
        with st.form("employee_rec_form"):
            c1, c2, c3 = st.columns(3)
            with c1: r_day  = st.selectbox("Day of Week", range(7), format_func=lambda i: DAYS_LONG[i])
            with c2: r_st   = st.time_input("Start Time", value=datetime.strptime("11:00", "%H:%M").time())
            with c3: r_et   = st.time_input("End Time",   value=datetime.strptime("19:00", "%H:%M").time())
            c4, c5, c6, c7 = st.columns(4)
            with c4: r_type  = st.selectbox("Type", ["regular", "cleaning", "event"], format_func=str.title)
            with c5: r_label = st.text_input("Label", placeholder="e.g. Dinner Service")
            with c6: r_min   = st.number_input("Min Staff", 1, 20, 1)
            with c7: r_max   = st.number_input("Max Staff", 1, 20, 3)
            if st.form_submit_button("Create Template", use_container_width=True):
                if r_st >= r_et:
                    st.error("End time must be after start time.")
                else:
                    db.create_recurring_shift(
                        r_day,
                        r_st.strftime("%H:%M"),
                        r_et.strftime("%H:%M"),
                        r_type,
                        r_label,
                        r_min,
                        r_max,
                        created_by=u["id"],
                    )
                    st.success("Recurring shift created!")
                    st.rerun()

    recurring = db.get_recurring_shifts(active_only=True, created_by=u["id"])
    st.markdown(f"### My Templates ({len(recurring)})")
    if not recurring:
        st.caption("No recurring shift templates yet.")
    else:
        for r in recurring:
            with st.container(border=True):
                hc1, hc2, hc3 = st.columns([4, 2, 1])
                with hc1:
                    st.markdown(f"**{DAYS_LONG[r['day_of_week']]}** · {fmt12(r['start_time'])} – {fmt12(r['end_time'])}")
                    st.caption(f"{TYPE_EMOJI.get(r['type'],'⚪')} {r.get('label') or r['type'].title()} · {r['min_staff']}–{r['max_staff']} staff")
                with hc2:
                    r_skills = db.get_recurring_shift_skills(r["id"])
                    if r_skills:
                        pills = " ".join(
                            f'<span style="background:{s["color"]};color:white;padding:1px 8px;border-radius:999px;font-size:.7rem">{"★ " if s["required"] else ""}{s["name"]}</span>'
                            for s in r_skills
                        )
                        st.markdown(pills, unsafe_allow_html=True)
                    else:
                        st.caption("No skill requirements")
                with hc3:
                    if st.button("🗑", key=f"del_emp_rec_{r['id']}", help="Deactivate"):
                        db.deactivate_recurring_shift(r["id"])
                        st.rerun()

                with st.expander("Manage required skills"):
                    assigned_skill_ids = {s["skill_id"] for s in db.get_recurring_shift_skills(r["id"])}
                    unassigned = [sk for sk in all_skills if sk["id"] not in assigned_skill_ids]
                    for s in db.get_recurring_shift_skills(r["id"]):
                        sc1, sc2 = st.columns([4, 1])
                        with sc1:
                            req_label = "Required" if s["required"] else "Preferred"
                            st.markdown(f'<span style="background:{s["color"]};color:white;padding:2px 8px;border-radius:999px;font-size:.75rem">{s["name"]}</span> <span style="font-size:.75rem;color:#6b7280">{req_label}</span>', unsafe_allow_html=True)
                        with sc2:
                            if st.button("✕", key=f"rmemp_{r['id']}_{s['skill_id']}"):
                                db.remove_recurring_shift_skill(r["id"], s["skill_id"])
                                st.rerun()
                    if unassigned:
                        ac1, ac2, ac3 = st.columns([3, 2, 1])
                        with ac1: add_sid = st.selectbox("Skill", [s["id"] for s in unassigned],
                                                           format_func=lambda x: next(s["name"] for s in unassigned if s["id"] == x),
                                                           key=f"reemp_sel_{r['id']}")
                        with ac2: req_flag = st.selectbox("Level", [0, 1], format_func=lambda x: "Required" if x else "Preferred",
                                                            key=f"reemp_req_{r['id']}")
                        with ac3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("Add", key=f"reemp_add_{r['id']}"):
                                db.add_recurring_shift_skill(r["id"], add_sid, req_flag)
                                st.rerun()


def page_admin_auto_schedule() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Auto Schedule</h1>', unsafe_allow_html=True)
    st.caption("The algorithm assigns employees to each recurring shift slot based on availability, skills, priority ranking, compatibility, preferences, and rating history.")

    today = date.today()
    default_week = today - timedelta(days=today.weekday())
    c1, c2 = st.columns([2, 1])
    with c1:
        week_start = st.date_input("Week starting (Monday)", value=default_week)
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🤖 Generate Schedule", use_container_width=True)

    if not db.get_recurring_shifts():
        st.warning("No recurring shift templates found. Add them on the **Recurring Shifts** page first.")
        return

    if run_btn or st.session_state.get("auto_proposals"):
        if run_btn:
            with st.spinner("Running scheduling algorithm..."):
                proposals = db.generate_schedule(week_start.isoformat())
            st.session_state["auto_proposals"]    = proposals
            st.session_state["auto_week_start"]   = week_start.isoformat()
            st.session_state["auto_modifications"] = {}

        proposals  = st.session_state.get("auto_proposals", [])
        week_str   = st.session_state.get("auto_week_start", week_start.isoformat())
        week_d     = date.fromisoformat(week_str)
        mods       = st.session_state.get("auto_modifications", {})
        all_emp    = db.get_all_users()
        emp_map    = {u["id"]: u for u in all_emp}
        active_emp = [u for u in all_emp if u["is_active"]]

        if not proposals:
            st.info("No shifts generated — check that employees have availability set for this week.")
            return

        under_count = sum(1 for p in proposals if p["understaffed"])
        col1, col2, col3 = st.columns(3)
        col1.metric("Shift Slots", len(proposals))
        col2.metric("Understaffed", under_count, delta=f"{under_count} need attention" if under_count else None, delta_color="inverse")
        col3.metric("Total Assignments", sum(len(p["assigned"]) for p in proposals))

        st.markdown("---")
        st.markdown("### Proposed Assignments")
        st.caption("You can swap employees before confirming. ★ = understaffed slot.")

        for i, p in enumerate(proposals):
            d_obj = date.fromisoformat(p["date"])
            warn = "⚠️ " if p["understaffed"] else ""
            with st.container(border=True):
                pc1, pc2 = st.columns([3, 2])
                with pc1:
                    st.markdown(f"{warn}**{d_obj.strftime('%a %b %d')}** · {fmt12(p['start_time'])}–{fmt12(p['end_time'])}  {TYPE_EMOJI.get(p['type'],'⚪')} {p.get('label') or p['type'].title()}")
                    st.caption(f"Staff: {p['min_staff']}–{p['max_staff']} needed")
                with pc2:
                    assigned_this = mods.get(i, p["assigned"])
                    for uid in assigned_this:
                        emp = emp_map.get(uid)
                        if emp:
                            st.markdown(f"👤 {emp['full_name']}")

                with st.expander("Modify assignment"):
                    current_assigned = mods.get(i, list(p["assigned"]))
                    new_assigned = st.multiselect(
                        "Assign employees",
                        options=[e["id"] for e in active_emp],
                        default=current_assigned,
                        format_func=lambda x: emp_map.get(x, {}).get("full_name", str(x)),
                        key=f"mod_assign_{i}",
                    )
                    if new_assigned != current_assigned:
                        mods[i] = new_assigned
                        st.session_state["auto_modifications"] = mods
                        st.rerun()

        st.markdown("---")
        if st.button("✅ Confirm & Create All Shifts", use_container_width=True, type="primary"):
            created = 0
            for i, p in enumerate(proposals):
                final_assigned = mods.get(i, p["assigned"])
                if not final_assigned:
                    sid = db.create_shift(p["date"], p["start_time"], p["end_time"],
                                          p["type"], p.get("label"), None)
                    created += 1
                else:
                    for uid in final_assigned:
                        sid = db.create_shift(p["date"], p["start_time"], p["end_time"],
                                              p["type"], p.get("label"), uid)
                    created += len(final_assigned)
            del st.session_state["auto_proposals"]
            st.session_state.pop("auto_modifications", None)
            st.success(f"✅ Created {created} shift assignment(s) for the week of {week_str}!")
            st.rerun()


def page_admin_labor_stats() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Labor Statistics</h1>', unsafe_allow_html=True)

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    c1, c2 = st.columns(2)
    with c1: start_d = st.date_input("From", value=week_start)
    with c2: end_d   = st.date_input("To",   value=week_start + timedelta(days=6))

    stats = db.get_labor_stats(start_d.isoformat(), end_d.isoformat())

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Total Hours",    f"{stats['total_hours']:.1f} hrs")
    mc2.metric("Total Labor Cost", f"${stats['total_cost']:.2f}")
    mc3.metric("Shifts Covered",  stats["shift_count"])
    mc4.metric("Avg Cost/Shift",
               f"${stats['total_cost']/max(stats['shift_count'],1):.2f}")

    if not stats["by_employee"]:
        st.info("No assigned shifts in this date range.")
        return

    st.markdown("---")
    st.markdown("### 👥 By Employee")
    emp_rows = sorted(stats["by_employee"].values(), key=lambda x: -x["hours"])
    rows_html = "".join(f"""
        <tr>
          <td><strong>{r['name']}</strong></td>
          <td>${r['rate']:.2f}/hr</td>
          <td>{r['hours']:.1f} hrs</td>
          <td><strong>${r['cost']:.2f}</strong></td>
          <td>
            <div style="background:#e5e7eb;border-radius:8px;height:12px;width:120px">
              <div style="background:#1e3a5f;border-radius:8px;height:12px;width:{min(120,int(r['hours']/max(e['hours'] for e in emp_rows)*120))}px"></div>
            </div>
          </td>
        </tr>"""
        for r in emp_rows)
    st.markdown(f'<table class="jtap-table"><thead><tr><th>Employee</th><th>Rate</th><th>Hours</th><th>Cost</th><th>Hours Bar</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📅 Cost by Day")
        if stats["by_day"]:
            import pandas as pd
            day_data = {date.fromisoformat(k).strftime("%a %b %d"): v for k, v in sorted(stats["by_day"].items())}
            st.bar_chart(pd.DataFrame(day_data.values(), index=day_data.keys(), columns=["Cost ($)"]))

    with col2:
        st.markdown("### 🏷 Cost by Shift Type")
        if stats["by_type"]:
            import pandas as pd
            type_data = {k.title(): v for k, v in stats["by_type"].items()}
            st.bar_chart(pd.DataFrame(type_data.values(), index=type_data.keys(), columns=["Cost ($)"]))


def page_admin_skills() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Skills & Roles</h1>', unsafe_allow_html=True)
    st.caption("Skills tag what employees are good at. The scheduler uses these when assigning recurring shifts.")

    skills = db.get_skills()
    PRESET_COLORS = ["#ef4444","#f59e0b","#10b981","#3b82f6","#8b5cf6","#ec4899","#14b8a6","#6366f1","#f97316","#84cc16"]

    with st.expander("➕ Add New Skill", expanded=not bool(skills)):
        with st.form("add_skill_form"):
            sc1, sc2, sc3 = st.columns([3, 2, 1])
            with sc1: sk_name  = st.text_input("Skill Name", placeholder="e.g. Barista")
            with sc2: sk_color = st.selectbox("Color", PRESET_COLORS,
                                               format_func=lambda c: c)
            with sc3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("Add"):
                    if sk_name.strip():
                        db.create_skill(sk_name.strip(), sk_color)
                        st.success(f"Skill '{sk_name}' added!")
                        st.rerun()

    st.markdown("### Existing Skills")
    if not skills:
        st.caption("No skills yet. Add some above.")
    else:
        all_users = db.get_all_users()
        for sk in skills:
            emp_count = sum(1 for u in all_users if any(
                s["skill_id"] == sk["id"] for s in db.get_employee_skills(u["id"])))
            sc1, sc2, sc3 = st.columns([3, 2, 1])
            with sc1:
                st.markdown(f'<span style="background:{sk["color"]};color:white;padding:4px 14px;border-radius:999px;font-weight:600">{sk["name"]}</span>', unsafe_allow_html=True)
            with sc2:
                st.caption(f"{emp_count} employee(s) have this skill")
            with sc3:
                if st.button("🗑", key=f"del_sk_{sk['id']}", help="Delete skill"):
                    db.delete_skill(sk["id"])
                    st.rerun()


def page_admin_compatibility() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Employee Compatibility</h1>', unsafe_allow_html=True)
    st.caption("Controls whether employees are scheduled together and whether they can see each other on the schedule.")
    users = [u for u in db.get_all_users() if u["is_active"]]

    COMPAT_OPTS = {
        "preferred": ("💚 Preferred",  "Schedule together when possible"),
        "neutral":   ("⚪ Neutral",    "No preference"),
        "avoid":     ("🟡 Avoid",      "Try not to schedule together"),
        "never":     ("🔴 Never",      "Hard constraint — never schedule together"),
    }

    with st.expander("➕ Set Compatibility Between Two Employees", expanded=True):
        with st.form("compat_form"):
            emp_ids = [u["id"] for u in users]
            emp_fmt = {u["id"]: u["full_name"] for u in users}
            c1, c2 = st.columns(2)
            with c1: uid_a = st.selectbox("Employee A", emp_ids, format_func=lambda x: emp_fmt[x])
            with c2: uid_b = st.selectbox("Employee B", emp_ids, format_func=lambda x: emp_fmt[x])
            cc1, cc2, cc3 = st.columns(3)
            with cc1: compat = st.selectbox("Compatibility", list(COMPAT_OPTS.keys()),
                                             format_func=lambda k: COMPAT_OPTS[k][0])
            with cc2: hidden = st.checkbox("Hide from each other on schedule", value=False)
            with cc3: notes  = st.text_input("Notes (private)")
            if st.form_submit_button("Save", use_container_width=True):
                if uid_a == uid_b:
                    st.error("Select two different employees.")
                else:
                    db.set_compatibility(uid_a, uid_b, compat, int(hidden), notes)
                    st.success("Compatibility saved!")
                    st.rerun()

    st.markdown("### Current Settings")
    compat_list = db.get_all_compatibility()
    if not compat_list:
        st.caption("No compatibility settings yet.")
    else:
        rows_html = "".join(f"""
            <tr>
              <td><strong>{r['name_a']}</strong></td>
              <td><strong>{r['name_b']}</strong></td>
              <td>{COMPAT_OPTS.get(r['compatibility'], (r['compatibility'],''))[0]}</td>
              <td>{"🙈 Hidden" if r['hidden_from_each_other'] else "👁 Visible"}</td>
              <td>{r.get('notes') or ''}</td>
            </tr>"""
            for r in compat_list)
        st.markdown(f'<table class="jtap-table"><thead><tr><th>Employee A</th><th>Employee B</th><th>Compatibility</th><th>Visibility</th><th>Notes</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

        del_id = st.selectbox("Remove a setting", [None] + [r["id"] for r in compat_list],
                               format_func=lambda x: "— select to remove —" if x is None else
                               next(f"{r['name_a']} / {r['name_b']}" for r in compat_list if r["id"] == x))
        if del_id and st.button("Remove selected compatibility rule"):
            db.delete_compatibility(del_id)
            st.rerun()


def page_admin_overrides() -> None:
    st.markdown('<h1 style="color:#1e3a5f">Availability Blocks</h1>', unsafe_allow_html=True)
    st.caption("Override an employee's self-set availability. Block = do not schedule them. Force = always schedule them for this slot.")
    users = [u for u in db.get_all_users() if u["is_active"]]

    with st.expander("➕ Add Override", expanded=True):
        with st.form("override_form"):
            emp_ids = [u["id"] for u in users]
            emp_fmt = {u["id"]: u["full_name"] for u in users}
            c1, c2 = st.columns(2)
            with c1: ov_uid  = st.selectbox("Employee", emp_ids, format_func=lambda x: emp_fmt[x])
            with c2: ov_type = st.selectbox("Override Type", ["block", "force"],
                                             format_func=lambda x: "🚫 Block (do not schedule)" if x == "block" else "📌 Force (always schedule)")
            ov_mode = st.radio("Apply to", ["Recurring day of week", "Specific date"], horizontal=True)
            if ov_mode == "Recurring day of week":
                ov_dow  = st.selectbox("Day of Week", range(7), format_func=lambda i: DAYS_LONG[i])
                ov_date = None
            else:
                ov_date = st.date_input("Date")
                ov_dow  = None
            oc1, oc2 = st.columns(2)
            with oc1: ov_st = st.time_input("From", value=datetime.strptime("00:00", "%H:%M").time())
            with oc2: ov_et = st.time_input("Until", value=datetime.strptime("23:59", "%H:%M").time())
            ov_reason = st.text_input("Reason / note (shown to admins only)")
            if st.form_submit_button("Save Override", use_container_width=True):
                db.create_admin_override(
                    ov_uid, ov_type, ov_dow,
                    ov_date.isoformat() if ov_date else None,
                    ov_st.strftime("%H:%M"), ov_et.strftime("%H:%M"), ov_reason,
                )
                st.success("Override saved!")
                st.rerun()

    st.markdown("### Active Overrides")
    overrides = db.get_admin_overrides()
    if not overrides:
        st.caption("No overrides set.")
    else:
        rows_html = "".join(f"""
            <tr>
              <td><strong>{r['full_name']}</strong></td>
              <td>{"🚫 Block" if r['override_type']=='block' else "📌 Force"}</td>
              <td>{DAYS_LONG[r['day_of_week']] if r.get('day_of_week') is not None else (r.get('specific_date') or '—')}</td>
              <td>{fmt12(r['start_time'])} – {fmt12(r['end_time'])}</td>
              <td>{r.get('reason') or ''}</td>
            </tr>"""
            for r in overrides)
        st.markdown(f'<table class="jtap-table"><thead><tr><th>Employee</th><th>Type</th><th>Day/Date</th><th>Time Window</th><th>Reason</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

        del_id = st.selectbox("Remove an override", [None] + [r["id"] for r in overrides],
                               format_func=lambda x: "— select to remove —" if x is None else
                               next(f"{r['full_name']} — {DAYS_LONG[r['day_of_week']] if r.get('day_of_week') is not None else r.get('specific_date','?')} {fmt12(r['start_time'])}–{fmt12(r['end_time'])}" for r in overrides if r["id"] == x))
        if del_id and st.button("Remove selected override"):
            db.delete_admin_override(del_id)
            st.rerun()


def page_duties() -> None:
    u = st.session_state.user
    st.markdown('<h1 style="color:#1e3a5f">My Duties & Checklists</h1>', unsafe_allow_html=True)

    today = date.today()
    week_end = today + timedelta(days=7)
    my_shifts = db.get_shifts(start_date=today.isoformat(), end_date=week_end.isoformat(), user_id=u["id"])

    if not my_shifts:
        st.info("No upcoming shifts this week.")
        return

    for s in my_shifts:
        d_obj = date.fromisoformat(s["date"])
        duties = db.get_shift_duties(s["id"])
        completed_count = sum(1 for d in duties if d.get("completion_id"))

        with st.container(border=True):
            hc1, hc2 = st.columns([3, 1])
            with hc1:
                st.markdown(f"**{d_obj.strftime('%A, %B %d')}** · {fmt12(s['start_time'])} – {fmt12(s['end_time'])}  {TYPE_EMOJI.get(s['type'],'⚪')}")
            with hc2:
                if duties:
                    pct = int(completed_count / len(duties) * 100)
                    st.markdown(f'<div style="text-align:right;font-size:.8rem;color:#6b7280">{completed_count}/{len(duties)} done ({pct}%)</div>', unsafe_allow_html=True)

            if not duties:
                st.caption("No duties assigned for this shift.")
            else:
                DUTY_COLORS = {"task": "#6366f1", "prep": "#f59e0b", "cleaning": "#10b981",
                               "inventory": "#8b5cf6", "note": "#6b7280"}
                for duty in duties:
                    done = bool(duty.get("completion_id"))
                    dc1, dc2, dc3 = st.columns([1, 5, 2])
                    with dc1:
                        if st.checkbox("", value=done, key=f"duty_{duty['id']}"):
                            if not done:
                                db.toggle_duty_completion(duty["id"], u["id"])
                                st.rerun()
                        else:
                            if done:
                                db.toggle_duty_completion(duty["id"], u["id"])
                                st.rerun()
                    with dc2:
                        color = DUTY_COLORS.get(duty["duty_type"], "#6b7280")
                        text = f'<s>{duty["title"]}</s>' if done else duty["title"]
                        time_tag = f'<span style="color:{color};font-weight:600;font-size:.75rem">[{fmt12(duty["time_slot"])}] </span>' if duty.get("time_slot") else ""
                        type_tag = f'<span style="background:{color};color:white;padding:1px 6px;border-radius:999px;font-size:.7rem;margin-left:4px">{duty["duty_type"]}</span>'
                        assigned_tag = f' · <span style="color:#6b7280;font-size:.8rem">@{duty["assigned_name"]}</span>' if duty.get("assigned_name") and duty.get("assigned_user_id") != u["id"] else ""
                        note_tag = f'<br><span style="color:#9ca3af;font-size:.75rem;font-style:italic">{duty["notes"]}</span>' if duty.get("notes") else ""
                        st.markdown(f'{time_tag}{text}{type_tag}{assigned_tag}{note_tag}', unsafe_allow_html=True)
                    with dc3:
                        if done and duty.get("completed_by_name"):
                            st.caption(f'✓ {duty["completed_by_name"]}')


def page_admin_shift_duties(shift_id: int = None) -> None:
    """Inline duty editor embedded into the Shifts admin page."""
    st.markdown("#### 📋 Shift Duties / Checklist")
    shifts = db.get_shifts()
    if not shifts:
        st.caption("No shifts yet.")
        return

    sel_id = shift_id
    if not sel_id:
        sel_id = st.selectbox("Select shift to manage duties",
                               [s["id"] for s in shifts],
                               format_func=lambda x: next(
                                   f"{date.fromisoformat(s['date']).strftime('%a %b %d')} {fmt12(s['start_time'])}–{fmt12(s['end_time'])} ({s.get('assigned_name') or 'unassigned'})"
                                   for s in shifts if s["id"] == x))

    active_users = [u for u in db.get_all_users() if u["is_active"]]
    DUTY_TYPES = ["task", "prep", "cleaning", "inventory", "note"]

    with st.form(f"add_duty_form_{sel_id}"):
        dc1, dc2, dc3, dc4 = st.columns([3, 1, 1, 1])
        with dc1: d_title   = st.text_input("Duty / task title", placeholder="e.g. Wipe down bar top")
        with dc2: d_type    = st.selectbox("Type", DUTY_TYPES, format_func=str.title)
        with dc3: d_time    = st.text_input("Time (HH:MM, optional)", placeholder="14:30")
        with dc4: d_assign  = st.selectbox("Assign to", [None] + [u["id"] for u in active_users],
                                            format_func=lambda x: "Anyone" if x is None else next(u["full_name"] for u in active_users if u["id"] == x))
        d_notes = st.text_input("Note (optional)")
        if st.form_submit_button("Add Duty", use_container_width=True):
            if d_title.strip():
                db.create_shift_duty(sel_id, d_title.strip(), d_type, d_time.strip() or None, d_assign, d_notes.strip() or None)
                st.success("Duty added!")
                st.rerun()

    duties = db.get_shift_duties(sel_id)
    if duties:
        for duty in duties:
            done = bool(duty.get("completion_id"))
            rc1, rc2 = st.columns([6, 1])
            with rc1:
                status = "✅" if done else "⬜"
                time_s = f" [{fmt12(duty['time_slot'])}]" if duty.get("time_slot") else ""
                assigned_s = f" → {duty['assigned_name']}" if duty.get("assigned_name") else ""
                note_s = f"\n   *{duty['notes']}*" if duty.get("notes") else ""
                st.markdown(f"{status} **{duty['duty_type'].title()}**{time_s} {duty['title']}{assigned_s}{note_s}")
                if done:
                    st.caption(f"Completed by {duty.get('completed_by_name', '?')} at {(duty.get('completed_at') or '')[:16]}")
            with rc2:
                if st.button("🗑", key=f"del_duty_{duty['id']}"):
                    db.delete_shift_duty(duty["id"])
                    st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="AUTO_SCHEDULER — Staff Portal",
        page_icon="🍺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    db.init_db()
    db.migrate_db()

    # Handle email deep-link query params
    params = st.query_params
    if "page" in params and "user" in st.session_state:
        st.session_state.page = params["page"]

    if "user" not in st.session_state:
        page_login()
        return

    # Refresh user data on each load (captures new columns from migrate_db)
    fresh_user = db.get_user_by_id(st.session_state.user["id"])
    if fresh_user:
        st.session_state.user = fresh_user

    show_sidebar()

    page = st.session_state.get("page", "dashboard")

    page_map = {
        "dashboard":            page_dashboard,
        "schedule":             page_schedule,
        "availability":         page_availability,
        "requests":             page_requests,
        "duties":               page_duties,
        "time_off":             page_time_off,
        "profile":              page_profile,
        "notifications":        page_notifications,
        "recurring":            page_employee_recurring,
        "admin_overview":       page_admin_overview,
        "admin_shifts":         page_admin_shifts,
        "admin_recurring":      page_admin_recurring,
        "admin_auto_schedule":  page_admin_auto_schedule,
        "admin_labor_stats":    page_admin_labor_stats,
        "admin_employees":      page_admin_employees,
        "admin_skills":         page_admin_skills,
        "admin_compatibility":  page_admin_compatibility,
        "admin_overrides":      page_admin_overrides,
        "admin_business_hours": page_admin_business_hours,
        "admin_requests":       page_admin_requests,
    }

    fn = page_map.get(page)
    if fn:
        fn()
    else:
        page_dashboard()


if __name__ == "__main__":
    main()
