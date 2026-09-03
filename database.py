"""
SQLite database layer for AUTO_SCHEDULER.
No PostgreSQL required — everything stored in auto_scheduler.db (auto-created).
"""
import sqlite3
import os
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_scheduler.db")


# ── Connection helpers ──────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _row(row) -> Optional[Dict]:
    return dict(row) if row else None

def _rows(rows) -> List[Dict]:
    return [dict(r) for r in rows]

def _get(query: str, params: tuple = ()) -> Optional[Dict]:
    conn = _conn()
    r = conn.execute(query, params).fetchone()
    conn.close()
    return _row(r)

def _all(query: str, params: tuple = ()) -> List[Dict]:
    conn = _conn()
    rs = conn.execute(query, params).fetchall()
    conn.close()
    return _rows(rs)

def _run(query: str, params: tuple = ()) -> int:
    conn = _conn()
    cur = conn.execute(query, params)
    last_id = cur.lastrowid
    conn.commit()
    conn.close()
    return last_id

def _run_many(statements: list) -> None:
    """Run a list of (query, params) tuples in one transaction."""
    conn = _conn()
    for q, p in statements:
        conn.execute(q, p)
    conn.commit()
    conn.close()


# ── Schema ─────────────────────────────────────────────────────────────────

def init_db() -> None:
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            username                TEXT UNIQUE NOT NULL,
            email                   TEXT UNIQUE NOT NULL,
            hashed_password         TEXT NOT NULL,
            full_name               TEXT NOT NULL,
            role                    TEXT NOT NULL DEFAULT 'employee',
            receive_shift_requests  INTEGER NOT NULL DEFAULT 1,
            is_active               INTEGER NOT NULL DEFAULT 1,
            created_at              TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS business_hours (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL UNIQUE,
            open_time   TEXT NOT NULL,
            close_time  TEXT NOT NULL,
            is_closed   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS availability (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            day_of_week   INTEGER,
            specific_date TEXT,
            start_time    TEXT NOT NULL,
            end_time      TEXT NOT NULL,
            notes         TEXT
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT NOT NULL,
            start_time       TEXT NOT NULL,
            end_time         TEXT NOT NULL,
            type             TEXT NOT NULL DEFAULT 'regular',
            label            TEXT,
            status           TEXT NOT NULL DEFAULT 'open',
            assigned_user_id INTEGER REFERENCES users(id),
            created_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS shift_coverage_requests (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id            INTEGER NOT NULL REFERENCES shifts(id),
            requesting_user_id  INTEGER NOT NULL REFERENCES users(id),
            reason              TEXT,
            partial_start       TEXT,
            partial_end         TEXT,
            status              TEXT NOT NULL DEFAULT 'pending',
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS shift_coverage_offers (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            coverage_request_id INTEGER NOT NULL REFERENCES shift_coverage_requests(id),
            offering_user_id    INTEGER NOT NULL REFERENCES users(id),
            covers_start        TEXT NOT NULL,
            covers_end          TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'pending',
            responded_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS time_off_requests (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL REFERENCES users(id),
            type           TEXT NOT NULL,
            start_datetime TEXT NOT NULL,
            end_datetime   TEXT,
            reason         TEXT,
            status         TEXT NOT NULL DEFAULT 'pending',
            admin_note     TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            title      TEXT NOT NULL,
            message    TEXT NOT NULL,
            deep_link  TEXT,
            is_read    INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Users ───────────────────────────────────────────────────────────────────

def count_users() -> int:
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n

def create_user(username: str, email: str, hashed_password: str, full_name: str) -> Dict:
    role = "admin" if count_users() == 0 else "employee"
    uid = _run(
        "INSERT INTO users (username, email, hashed_password, full_name, role) VALUES (?,?,?,?,?)",
        (username, email, hashed_password, full_name, role),
    )
    return get_user_by_id(uid)

def get_user_by_username(username: str) -> Optional[Dict]:
    return _get("SELECT * FROM users WHERE username=?", (username,))

def get_user_by_id(uid: int) -> Optional[Dict]:
    return _get("SELECT * FROM users WHERE id=?", (uid,))

def get_all_users() -> List[Dict]:
    return _all("SELECT * FROM users ORDER BY full_name")

def update_user(uid: int, **fields) -> None:
    allowed = {"full_name", "email", "receive_shift_requests", "is_active", "role"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    clauses = ", ".join(f"{k}=?" for k in updates)
    _run(f"UPDATE users SET {clauses} WHERE id=?", (*updates.values(), uid))


# ── Business Hours ──────────────────────────────────────────────────────────

def get_business_hours() -> List[Dict]:
    rows = _all("SELECT * FROM business_hours ORDER BY day_of_week")
    if not rows:
        # Seed defaults (open Tue–Sun 11am–11pm, closed Mon)
        defaults = [
            (0, "11:00", "23:00", 1),  # Mon closed
            (1, "11:00", "23:00", 0),
            (2, "11:00", "23:00", 0),
            (3, "11:00", "23:00", 0),
            (4, "11:00", "23:00", 0),
            (5, "11:00", "23:00", 0),
            (6, "11:00", "23:00", 0),
        ]
        stmts = [
            ("INSERT OR IGNORE INTO business_hours (day_of_week, open_time, close_time, is_closed) VALUES (?,?,?,?)", d)
            for d in defaults
        ]
        _run_many(stmts)
        rows = _all("SELECT * FROM business_hours ORDER BY day_of_week")
    return rows

def save_business_hours(hours: List[Dict]) -> None:
    stmts = [
        (
            "INSERT INTO business_hours (day_of_week, open_time, close_time, is_closed) VALUES (?,?,?,?) "
            "ON CONFLICT(day_of_week) DO UPDATE SET open_time=excluded.open_time, "
            "close_time=excluded.close_time, is_closed=excluded.is_closed",
            (h["day_of_week"], h["open_time"], h["close_time"], int(h.get("is_closed", 0))),
        )
        for h in hours
    ]
    _run_many(stmts)


# ── Availability ────────────────────────────────────────────────────────────

def get_user_availability(user_id: int) -> List[Dict]:
    return _all(
        "SELECT * FROM availability WHERE user_id=? ORDER BY day_of_week, specific_date",
        (user_id,),
    )

def create_availability(user_id: int, day_of_week, specific_date, start_time: str, end_time: str, notes: str) -> int:
    return _run(
        "INSERT INTO availability (user_id, day_of_week, specific_date, start_time, end_time, notes) VALUES (?,?,?,?,?,?)",
        (user_id, day_of_week, specific_date, start_time, end_time, notes or None),
    )

def delete_availability(entry_id: int, user_id: int) -> None:
    _run("DELETE FROM availability WHERE id=? AND user_id=?", (entry_id, user_id))


# ── Shifts ──────────────────────────────────────────────────────────────────

def get_shifts(start_date: str = None, end_date: str = None, user_id: int = None) -> List[Dict]:
    q = """
        SELECT s.*, u.full_name as assigned_name
        FROM shifts s
        LEFT JOIN users u ON s.assigned_user_id = u.id
        WHERE 1=1
    """
    params: list = []
    if start_date:
        q += " AND s.date >= ?"
        params.append(start_date)
    if end_date:
        q += " AND s.date <= ?"
        params.append(end_date)
    if user_id:
        q += " AND s.assigned_user_id = ?"
        params.append(user_id)
    q += " ORDER BY s.date, s.start_time"
    return _all(q, tuple(params))

def get_shift_by_id(shift_id: int) -> Optional[Dict]:
    return _get(
        "SELECT s.*, u.full_name as assigned_name FROM shifts s LEFT JOIN users u ON s.assigned_user_id=u.id WHERE s.id=?",
        (shift_id,),
    )

def create_shift(date: str, start_time: str, end_time: str, type_: str, label: str, assigned_user_id) -> int:
    return _run(
        "INSERT INTO shifts (date, start_time, end_time, type, label, assigned_user_id) VALUES (?,?,?,?,?,?)",
        (date, start_time, end_time, type_, label or None, assigned_user_id or None),
    )

def update_shift(shift_id: int, **fields) -> None:
    allowed = {"date", "start_time", "end_time", "type", "label", "status", "assigned_user_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    clauses = ", ".join(f"{k}=?" for k in updates)
    _run(f"UPDATE shifts SET {clauses} WHERE id=?", (*updates.values(), shift_id))

def delete_shift(shift_id: int) -> None:
    _run("DELETE FROM shifts WHERE id=?", (shift_id,))


# ── Coverage Requests ────────────────────────────────────────────────────────

def get_open_coverage_requests(exclude_user_id: int) -> List[Dict]:
    return _all(
        """
        SELECT r.*, s.date, s.start_time as shift_start, s.end_time as shift_end,
               u.full_name as requester_name
        FROM shift_coverage_requests r
        JOIN shifts s ON r.shift_id = s.id
        JOIN users u ON r.requesting_user_id = u.id
        WHERE r.status IN ('pending','partially_filled')
          AND r.requesting_user_id != ?
        ORDER BY r.created_at DESC
        """,
        (exclude_user_id,),
    )

def get_my_coverage_requests(user_id: int) -> List[Dict]:
    return _all(
        """
        SELECT r.*, s.date, s.start_time as shift_start, s.end_time as shift_end
        FROM shift_coverage_requests r
        JOIN shifts s ON r.shift_id = s.id
        WHERE r.requesting_user_id = ?
        ORDER BY r.created_at DESC
        """,
        (user_id,),
    )

def get_coverage_request_by_id(req_id: int) -> Optional[Dict]:
    return _get(
        """
        SELECT r.*, s.date, s.start_time as shift_start, s.end_time as shift_end,
               u.full_name as requester_name
        FROM shift_coverage_requests r
        JOIN shifts s ON r.shift_id = s.id
        JOIN users u ON r.requesting_user_id = u.id
        WHERE r.id=?
        """,
        (req_id,),
    )

def get_offer_for_request(req_id: int) -> List[Dict]:
    return _all(
        """
        SELECT o.*, u.full_name as offerer_name
        FROM shift_coverage_offers o
        JOIN users u ON o.offering_user_id = u.id
        WHERE o.coverage_request_id = ?
        ORDER BY o.id
        """,
        (req_id,),
    )

def create_coverage_request(shift_id: int, requesting_user_id: int, reason: str,
                             partial_start: str, partial_end: str,
                             requested_duration: int = None) -> int:
    return _run(
        "INSERT INTO shift_coverage_requests (shift_id, requesting_user_id, reason, partial_start, partial_end, requested_duration) VALUES (?,?,?,?,?,?)",
        (shift_id, requesting_user_id, reason or None, partial_start or None, partial_end or None, requested_duration),
    )

def get_coverage_request_skills(req_id: int) -> List[Dict]:
    return _all(
        """
        SELECT rsk.*, s.name, s.color
        FROM shift_coverage_request_skills rsk
        JOIN skills s ON rsk.skill_id = s.id
        WHERE rsk.coverage_request_id = ?
        ORDER BY s.name
        """,
        (req_id,),
    )

def add_coverage_request_skill(req_id: int, skill_id: int, required: int = 0) -> None:
    _run(
        "INSERT OR IGNORE INTO shift_coverage_request_skills (coverage_request_id, skill_id, required) VALUES (?,?,?)",
        (req_id, skill_id, required),
    )

def remove_coverage_request_skill(req_id: int, skill_id: int) -> None:
    _run(
        "DELETE FROM shift_coverage_request_skills WHERE coverage_request_id=? AND skill_id=?",
        (req_id, skill_id),
    )

def create_coverage_offer(req_id: int, offering_user_id: int, covers_start: str, covers_end: str) -> int:
    return _run(
        "INSERT INTO shift_coverage_offers (coverage_request_id, offering_user_id, covers_start, covers_end) VALUES (?,?,?,?)",
        (req_id, offering_user_id, covers_start, covers_end),
    )

def accept_coverage_offer(offer_id: int, req_id: int) -> None:
    """Accept one offer, decline others, fill the request, and reassign the shift."""
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    conn = _conn()
    conn.execute(
        "UPDATE shift_coverage_offers SET status='accepted', responded_at=? WHERE id=?",
        (now, offer_id),
    )
    conn.execute(
        "UPDATE shift_coverage_offers SET status='declined', responded_at=? WHERE coverage_request_id=? AND id!=?",
        (now, req_id, offer_id),
    )
    conn.execute("UPDATE shift_coverage_requests SET status='filled' WHERE id=?", (req_id,))
    # Reassign the shift to the offerer
    offer = dict(conn.execute("SELECT * FROM shift_coverage_offers WHERE id=?", (offer_id,)).fetchone())
    req   = dict(conn.execute("SELECT * FROM shift_coverage_requests WHERE id=?", (req_id,)).fetchone())
    conn.execute("UPDATE shifts SET assigned_user_id=? WHERE id=?", (offer["offering_user_id"], req["shift_id"]))
    conn.commit()
    conn.close()

def get_all_coverage_requests_admin() -> List[Dict]:
    return _all(
        """
        SELECT r.*, s.date, s.start_time as shift_start, s.end_time as shift_end,
               u.full_name as requester_name
        FROM shift_coverage_requests r
        JOIN shifts s ON r.shift_id = s.id
        JOIN users u ON r.requesting_user_id = u.id
        ORDER BY r.created_at DESC
        """,
    )


# ── Time Off ─────────────────────────────────────────────────────────────────

def create_time_off_request(user_id: int, type_: str, start_datetime: str,
                             end_datetime: str, reason: str) -> int:
    return _run(
        "INSERT INTO time_off_requests (user_id, type, start_datetime, end_datetime, reason) VALUES (?,?,?,?,?)",
        (user_id, type_, start_datetime, end_datetime or None, reason or None),
    )

def get_time_off_requests(user_id: int = None) -> List[Dict]:
    if user_id:
        return _all(
            "SELECT r.*, u.full_name, u.username FROM time_off_requests r JOIN users u ON r.user_id=u.id WHERE r.user_id=? ORDER BY r.created_at DESC",
            (user_id,),
        )
    return _all(
        "SELECT r.*, u.full_name, u.username FROM time_off_requests r JOIN users u ON r.user_id=u.id ORDER BY r.created_at DESC"
    )

def update_time_off_status(req_id: int, status: str, admin_note: str) -> None:
    _run(
        "UPDATE time_off_requests SET status=?, admin_note=? WHERE id=?",
        (status, admin_note or None, req_id),
    )


# ── Notifications ─────────────────────────────────────────────────────────────

def create_notification(user_id: int, title: str, message: str, deep_link: str = None) -> None:
    _run(
        "INSERT INTO notifications (user_id, title, message, deep_link) VALUES (?,?,?,?)",
        (user_id, title, message, deep_link),
    )

def get_notifications(user_id: int, limit: int = 30) -> List[Dict]:
    return _all(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )

def get_unread_count(user_id: int) -> int:
    conn = _conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user_id,)
    ).fetchone()[0]
    conn.close()
    return n

def mark_all_read(user_id: int) -> None:
    _run("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (user_id,))

def mark_one_read(notif_id: int, user_id: int) -> None:
    _run("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notif_id, user_id))


# ── Fan-out helpers ───────────────────────────────────────────────────────────

def fan_out_coverage_request(req_id: int, requesting_user_id: int) -> List[Dict]:
    """Notify all opt-in employees (except the requester). Returns list for email sending."""
    req = get_coverage_request_by_id(req_id)
    if not req:
        return []
    recipients = [
        u for u in get_all_users()
        if u["is_active"] and u["receive_shift_requests"] and u["id"] != requesting_user_id
    ]
    for u in recipients:
        create_notification(
            u["id"],
            "Shift Coverage Request",
            f"{req['requester_name']} needs coverage for {req['date']} "
            f"({_fmt12(req['shift_start'])}–{_fmt12(req['shift_end'])}).",
            deep_link=f"requests:{req_id}",
        )
    return recipients

def blast_shift(shift_id: int) -> List[Dict]:
    """Notify all opt-in employees of a new cleaning/event shift. Returns list for email sending."""
    shift = get_shift_by_id(shift_id)
    if not shift:
        return []
    recipients = [u for u in get_all_users() if u["is_active"] and u["receive_shift_requests"]]
    label = shift.get("label") or shift["type"].title()
    for u in recipients:
        create_notification(
            u["id"],
            f"Extra Shift: {label}",
            f"A {shift['type']} slot is available on {shift['date']} "
            f"({_fmt12(shift['start_time'])}–{_fmt12(shift['end_time'])}).",
            deep_link="schedule",
        )
    return recipients


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt12(t: str) -> str:
    """Windows-safe 12-hour format."""
    if not t:
        return ""
    try:
        h, m = t[:5].split(":")
        h = int(h)
        suffix = "AM" if h < 12 else "PM"
        return f"{h % 12 or 12}:{m} {suffix}"
    except Exception:
        return t


# ══════════════════════════════════════════════════════════════════════════════
# Phase 2 — Advanced scheduling features
# ══════════════════════════════════════════════════════════════════════════════

def _has_table(table: str) -> bool:
    c = _conn()
    exists = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None
    c.close()
    return exists


def _has_column(table: str, column: str) -> bool:
    c = _conn()
    cols = [row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()]
    c.close()
    return column in cols


def migrate_db() -> None:
    """Safely add Phase 2 columns and tables to an existing database."""
    for col, defn in [
        ("hourly_rate",          "REAL    DEFAULT 15.0"),
        ("priority_rank",        "INTEGER DEFAULT 100"),
        ("desired_weekly_hours", "INTEGER DEFAULT 20"),
    ]:
        if not _has_column("users", col):
            _run(f"ALTER TABLE users ADD COLUMN {col} {defn}")

    if _has_table("recurring_shifts") and not _has_column("recurring_shifts", "created_by"):
        _run("ALTER TABLE recurring_shifts ADD COLUMN created_by INTEGER REFERENCES users(id)")

    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS skills (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT UNIQUE NOT NULL,
            color TEXT NOT NULL DEFAULT '#6b7280'
        );

        CREATE TABLE IF NOT EXISTS employee_skills (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            skill_id    INTEGER NOT NULL REFERENCES skills(id),
            proficiency INTEGER NOT NULL DEFAULT 1,
            UNIQUE(user_id, skill_id)
        );

        CREATE TABLE IF NOT EXISTS recurring_shifts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            start_time  TEXT NOT NULL,
            end_time    TEXT NOT NULL,
            type        TEXT NOT NULL DEFAULT 'regular',
            label       TEXT,
            min_staff   INTEGER NOT NULL DEFAULT 1,
            max_staff   INTEGER NOT NULL DEFAULT 3,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_by  INTEGER REFERENCES users(id),
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS recurring_shift_skills (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            recurring_shift_id INTEGER NOT NULL REFERENCES recurring_shifts(id),
            skill_id           INTEGER NOT NULL REFERENCES skills(id),
            required           INTEGER NOT NULL DEFAULT 0,
            UNIQUE(recurring_shift_id, skill_id)
        );

        CREATE TABLE IF NOT EXISTS admin_availability_overrides (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            override_type TEXT NOT NULL DEFAULT 'block',
            day_of_week   INTEGER,
            specific_date TEXT,
            start_time    TEXT NOT NULL,
            end_time      TEXT NOT NULL,
            reason        TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS employee_compatibility (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_a              INTEGER NOT NULL REFERENCES users(id),
            user_id_b              INTEGER NOT NULL REFERENCES users(id),
            compatibility          TEXT NOT NULL DEFAULT 'neutral',
            hidden_from_each_other INTEGER NOT NULL DEFAULT 0,
            notes                  TEXT,
            UNIQUE(user_id_a, user_id_b)
        );

        CREATE TABLE IF NOT EXISTS shift_duties (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id         INTEGER NOT NULL REFERENCES shifts(id),
            title            TEXT NOT NULL,
            duty_type        TEXT NOT NULL DEFAULT 'task',
            time_slot        TEXT,
            assigned_user_id INTEGER REFERENCES users(id),
            notes            TEXT,
            sort_order       INTEGER NOT NULL DEFAULT 0,
            created_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS shift_duty_completions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            duty_id      INTEGER NOT NULL REFERENCES shift_duties(id) UNIQUE,
            completed_by INTEGER NOT NULL REFERENCES users(id),
            completed_at TEXT NOT NULL DEFAULT (datetime('now')),
            note         TEXT
        );

        CREATE TABLE IF NOT EXISTS schedule_ratings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            shift_id   INTEGER NOT NULL REFERENCES shifts(id),
            rating     INTEGER NOT NULL,
            comment    TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(user_id, shift_id)
        );

        CREATE TABLE IF NOT EXISTS employee_duty_preferences (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            skill_id   INTEGER NOT NULL REFERENCES skills(id),
            preference INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, skill_id)
        );
    """)
    c.commit()
    c.close()

    if not _all("SELECT 1 FROM skills LIMIT 1"):
        for name, color in [
            ("Prep",           "#f59e0b"),
            ("Cooking",        "#ef4444"),
            ("Cleaning",       "#10b981"),
            ("Inventory",      "#8b5cf6"),
            ("Bar",            "#3b82f6"),
            ("Front of House", "#ec4899"),
            ("Opening",        "#14b8a6"),
            ("Closing",        "#6366f1"),
        ]:
            _run("INSERT OR IGNORE INTO skills (name, color) VALUES (?,?)", (name, color))


# ── Skills ────────────────────────────────────────────────────────────────────

def get_skills() -> List[Dict]:
    return _all("SELECT * FROM skills ORDER BY name")

def create_skill(name: str, color: str = "#6b7280") -> int:
    return _run("INSERT INTO skills (name, color) VALUES (?,?)", (name, color))

def delete_skill(skill_id: int) -> None:
    _run("DELETE FROM skills WHERE id=?", (skill_id,))

def get_employee_skills(user_id: int) -> List[Dict]:
    return _all("""
        SELECT es.*, s.name, s.color
        FROM employee_skills es JOIN skills s ON es.skill_id = s.id
        WHERE es.user_id = ? ORDER BY s.name""", (user_id,))

def set_employee_skill(user_id: int, skill_id: int, proficiency: int = 1) -> None:
    _run("""INSERT INTO employee_skills (user_id, skill_id, proficiency) VALUES (?,?,?)
            ON CONFLICT(user_id, skill_id) DO UPDATE SET proficiency=excluded.proficiency""",
         (user_id, skill_id, proficiency))

def remove_employee_skill(user_id: int, skill_id: int) -> None:
    _run("DELETE FROM employee_skills WHERE user_id=? AND skill_id=?", (user_id, skill_id))


# ── Recurring Shifts ──────────────────────────────────────────────────────────

def get_recurring_shifts(active_only: bool = True, created_by: int = None) -> List[Dict]:
    sql = "SELECT * FROM recurring_shifts"
    clauses = []
    params = []
    if active_only:
        clauses.append("is_active=1")
    if created_by is not None:
        clauses.append("created_by=?")
        params.append(created_by)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    return _all(sql + " ORDER BY day_of_week, start_time", tuple(params))

def create_recurring_shift(day_of_week: int, start_time: str, end_time: str,
                            type_: str = "regular", label: str = None,
                            min_staff: int = 1, max_staff: int = 3,
                            created_by: int = None) -> int:
    return _run(
        "INSERT INTO recurring_shifts (day_of_week,start_time,end_time,type,label,min_staff,max_staff,created_by) VALUES (?,?,?,?,?,?,?,?)",
        (day_of_week, start_time, end_time, type_, label or None, min_staff, max_staff, created_by),
    )

def deactivate_recurring_shift(rid: int) -> None:
    _run("UPDATE recurring_shifts SET is_active=0 WHERE id=?", (rid,))

def get_recurring_shift_skills(rid: int) -> List[Dict]:
    return _all("""
        SELECT rss.*, s.name, s.color
        FROM recurring_shift_skills rss JOIN skills s ON rss.skill_id = s.id
        WHERE rss.recurring_shift_id = ?""", (rid,))

def add_recurring_shift_skill(rid: int, skill_id: int, required: int = 0) -> None:
    _run("INSERT OR IGNORE INTO recurring_shift_skills (recurring_shift_id, skill_id, required) VALUES (?,?,?)",
         (rid, skill_id, required))

def remove_recurring_shift_skill(rid: int, skill_id: int) -> None:
    _run("DELETE FROM recurring_shift_skills WHERE recurring_shift_id=? AND skill_id=?", (rid, skill_id))


# ── Admin Availability Overrides ──────────────────────────────────────────────

def get_admin_overrides(user_id: int = None) -> List[Dict]:
    if user_id:
        return _all("""SELECT o.*, u.full_name FROM admin_availability_overrides o
                       JOIN users u ON o.user_id = u.id
                       WHERE o.user_id = ? ORDER BY o.day_of_week, o.specific_date""", (user_id,))
    return _all("""SELECT o.*, u.full_name FROM admin_availability_overrides o
                   JOIN users u ON o.user_id = u.id ORDER BY u.full_name, o.day_of_week""")

def create_admin_override(user_id: int, override_type: str, day_of_week,
                           specific_date, start_time: str, end_time: str,
                           reason: str = None) -> int:
    return _run("""INSERT INTO admin_availability_overrides
                   (user_id,override_type,day_of_week,specific_date,start_time,end_time,reason)
                   VALUES (?,?,?,?,?,?,?)""",
                (user_id, override_type, day_of_week, specific_date, start_time, end_time, reason))

def delete_admin_override(override_id: int) -> None:
    _run("DELETE FROM admin_availability_overrides WHERE id=?", (override_id,))


# ── Employee Compatibility ────────────────────────────────────────────────────

def get_all_compatibility() -> List[Dict]:
    return _all("""
        SELECT ec.*, ua.full_name AS name_a, ub.full_name AS name_b
        FROM employee_compatibility ec
        JOIN users ua ON ec.user_id_a = ua.id
        JOIN users ub ON ec.user_id_b = ub.id
        ORDER BY ua.full_name""")

def set_compatibility(user_id_a: int, user_id_b: int, compatibility: str,
                      hidden: int = 0, notes: str = None) -> None:
    a, b = min(user_id_a, user_id_b), max(user_id_a, user_id_b)
    _run("""INSERT INTO employee_compatibility
              (user_id_a, user_id_b, compatibility, hidden_from_each_other, notes)
            VALUES (?,?,?,?,?)
            ON CONFLICT(user_id_a, user_id_b) DO UPDATE SET
              compatibility=excluded.compatibility,
              hidden_from_each_other=excluded.hidden_from_each_other,
              notes=excluded.notes""",
         (a, b, compatibility, hidden, notes))

def delete_compatibility(compat_id: int) -> None:
    _run("DELETE FROM employee_compatibility WHERE id=?", (compat_id,))

def get_hidden_user_ids(user_id: int) -> set:
    rows = _all("""
        SELECT CASE WHEN user_id_a=? THEN user_id_b ELSE user_id_a END AS other_id
        FROM employee_compatibility
        WHERE (user_id_a=? OR user_id_b=?) AND hidden_from_each_other=1""",
                (user_id, user_id, user_id))
    return {r["other_id"] for r in rows}


# ── Shift Duties ──────────────────────────────────────────────────────────────

def get_shift_duties(shift_id: int) -> List[Dict]:
    return _all("""
        SELECT d.*,
               u.full_name  AS assigned_name,
               c.id         AS completion_id,
               c.completed_by,
               cb.full_name AS completed_by_name,
               c.completed_at,
               c.note       AS completion_note
        FROM shift_duties d
        LEFT JOIN users u  ON d.assigned_user_id = u.id
        LEFT JOIN shift_duty_completions c  ON c.duty_id = d.id
        LEFT JOIN users cb ON cb.id = c.completed_by
        WHERE d.shift_id = ?
        ORDER BY d.sort_order, d.time_slot, d.id""", (shift_id,))

def create_shift_duty(shift_id: int, title: str, duty_type: str = "task",
                       time_slot: str = None, assigned_user_id=None,
                       notes: str = None, sort_order: int = 0) -> int:
    return _run("""INSERT INTO shift_duties
                   (shift_id,title,duty_type,time_slot,assigned_user_id,notes,sort_order)
                   VALUES (?,?,?,?,?,?,?)""",
                (shift_id, title, duty_type, time_slot or None,
                 assigned_user_id or None, notes or None, sort_order))

def delete_shift_duty(duty_id: int) -> None:
    _run("DELETE FROM shift_duties WHERE id=?", (duty_id,))

def toggle_duty_completion(duty_id: int, user_id: int) -> bool:
    existing = _get("SELECT id FROM shift_duty_completions WHERE duty_id=?", (duty_id,))
    if existing:
        _run("DELETE FROM shift_duty_completions WHERE duty_id=?", (duty_id,))
        return False
    _run("INSERT INTO shift_duty_completions (duty_id, completed_by) VALUES (?,?)", (duty_id, user_id))
    return True


# ── Schedule Ratings ──────────────────────────────────────────────────────────

def rate_shift(user_id: int, shift_id: int, rating: int, comment: str = None) -> None:
    _run("""INSERT INTO schedule_ratings (user_id,shift_id,rating,comment) VALUES (?,?,?,?)
            ON CONFLICT(user_id,shift_id) DO UPDATE SET rating=excluded.rating, comment=excluded.comment""",
         (user_id, shift_id, rating, comment))

def remove_rating(user_id: int, shift_id: int) -> None:
    _run("DELETE FROM schedule_ratings WHERE user_id=? AND shift_id=?", (user_id, shift_id))

def get_shift_rating(user_id: int, shift_id: int) -> Optional[Dict]:
    return _get("SELECT * FROM schedule_ratings WHERE user_id=? AND shift_id=?", (user_id, shift_id))

def get_shift_rating_summary(shift_id: int) -> Dict:
    rows = _all("SELECT rating FROM schedule_ratings WHERE shift_id=?", (shift_id,))
    ups   = sum(1 for r in rows if r["rating"] > 0)
    downs = sum(1 for r in rows if r["rating"] < 0)
    return {"thumbs_up": ups, "thumbs_down": downs}


# ── Employee Duty Preferences ─────────────────────────────────────────────────

def get_duty_preferences(user_id: int) -> List[Dict]:
    return _all("""
        SELECT p.*, s.name, s.color
        FROM employee_duty_preferences p JOIN skills s ON p.skill_id = s.id
        WHERE p.user_id = ? ORDER BY s.name""", (user_id,))

def set_duty_preference(user_id: int, skill_id: int, preference: int) -> None:
    _run("""INSERT INTO employee_duty_preferences (user_id, skill_id, preference) VALUES (?,?,?)
            ON CONFLICT(user_id, skill_id) DO UPDATE SET preference=excluded.preference""",
         (user_id, skill_id, preference))


# ── Labor Statistics ──────────────────────────────────────────────────────────

def get_labor_stats(start_date: str, end_date: str) -> Dict:
    shifts = get_shifts(start_date=start_date, end_date=end_date)
    users  = {u["id"]: u for u in _all("SELECT * FROM users")}

    total_hours = 0.0
    total_cost  = 0.0
    by_employee: Dict = {}
    by_day:      Dict = {}
    by_type:     Dict = {}

    for s in shifts:
        uid = s.get("assigned_user_id")
        if not uid:
            continue
        user = users.get(uid)
        if not user:
            continue
        try:
            sh = int(s["start_time"][:2]) * 60 + int(s["start_time"][3:5])
            eh = int(s["end_time"][:2])   * 60 + int(s["end_time"][3:5])
            duration = max(0.0, (eh - sh) / 60.0)
        except Exception:
            duration = 0.0

        rate = user.get("hourly_rate") or 15.0
        cost = duration * rate

        total_hours += duration
        total_cost  += cost

        if uid not in by_employee:
            by_employee[uid] = {"name": user["full_name"], "hours": 0.0, "cost": 0.0, "rate": rate}
        by_employee[uid]["hours"] = round(by_employee[uid]["hours"] + duration, 2)
        by_employee[uid]["cost"]  = round(by_employee[uid]["cost"]  + cost,     2)

        by_day[s["date"]]  = round(by_day.get(s["date"], 0.0)  + cost, 2)
        by_type[s["type"]] = round(by_type.get(s["type"], 0.0) + cost, 2)

    return {
        "total_hours": round(total_hours, 2),
        "total_cost":  round(total_cost,  2),
        "by_employee": by_employee,
        "by_day":      by_day,
        "by_type":     by_type,
        "shift_count": sum(1 for s in shifts if s.get("assigned_user_id")),
    }


# ── Scheduling Algorithm ──────────────────────────────────────────────────────

def _shift_dur(start_time: str, end_time: str) -> float:
    try:
        sh = int(start_time[:2]) * 60 + int(start_time[3:5])
        eh = int(end_time[:2])   * 60 + int(end_time[3:5])
        return max(0.0, (eh - sh) / 60.0)
    except Exception:
        return 4.0


def generate_schedule(week_start: str) -> List[Dict]:
    """
    Generate an optimised weekly schedule from recurring shift templates.

    Scoring per employee per slot (higher score = preferred pick):
      +60   required skills match (proportional)
      +20   preferred skills match (proportional)
      +30   priority rank  (0 = rank 0 → +30; rank 100 → 0)
      +20   hours balance  (remaining desired hours)
      +20   compatibility bonus per "preferred" pair already in shift
      −40   compatibility penalty per "avoid" pair
      −999  "never" pair → hard disqualify
      +10   positive duty preference for relevant skills
      +5×   historical rating bias (avg of last 10 shift ratings × 5)
    """
    import datetime as dt

    week_start_d = dt.date.fromisoformat(week_start)
    employees    = _all("SELECT * FROM users WHERE is_active=1")
    emp_map      = {e["id"]: e for e in employees}
    all_overrides = get_admin_overrides()

    avail_cache: Dict[int, List[Dict]] = {
        e["id"]: _all("SELECT * FROM availability WHERE user_id=?", (e["id"],))
        for e in employees
    }

    compat_map: Dict = {}
    for row in get_all_compatibility():
        key = (min(row["user_id_a"], row["user_id_b"]), max(row["user_id_a"], row["user_id_b"]))
        compat_map[key] = row

    emp_skills_map: Dict[int, set] = {
        e["id"]: {s["skill_id"] for s in get_employee_skills(e["id"])}
        for e in employees
    }

    pref_map: Dict[int, Dict] = {
        e["id"]: {p["skill_id"]: p["preference"] for p in get_duty_preferences(e["id"])}
        for e in employees
    }

    recurring       = get_recurring_shifts(active_only=True)
    hours_week: Dict[int, float] = {e["id"]: 0.0 for e in employees}

    # Pre-process "force" overrides (admin forces specific employee on a date/window)
    forced: Dict[str, List[int]] = {}
    for ov in all_overrides:
        if ov["override_type"] == "force" and ov.get("specific_date"):
            k = f"{ov['specific_date']}|{ov['start_time']}|{ov['end_time']}"
            forced.setdefault(k, []).append(ov["user_id"])

    proposals: List[Dict] = []

    for day_off in range(7):
        day_d  = week_start_d + dt.timedelta(days=day_off)
        date_s = day_d.isoformat()
        dow    = day_d.weekday()

        for tmpl in [r for r in recurring if r["day_of_week"] == dow]:
            st_t = tmpl["start_time"]
            et_t = tmpl["end_time"]
            dur  = _shift_dur(st_t, et_t)

            req_rows  = _all("SELECT * FROM recurring_shift_skills WHERE recurring_shift_id=?", (tmpl["id"],))
            req_sids  = {r["skill_id"] for r in req_rows if r["required"]}
            pref_sids = {r["skill_id"] for r in req_rows if not r["required"]}
            all_sids  = req_sids | pref_sids

            force_key = f"{date_s}|{st_t}|{et_t}"
            selected: List[int] = list(forced.get(force_key, []))
            for fuid in selected:
                hours_week[fuid] = hours_week.get(fuid, 0) + dur

            for _ in range(tmpl["max_staff"] - len(selected)):
                best_score = -9999.0
                best_uid   = None

                for emp in employees:
                    uid = emp["id"]
                    if uid in selected:
                        continue

                    # Admin block check
                    blocked = False
                    for ov in all_overrides:
                        if ov["user_id"] != uid or ov["override_type"] != "block":
                            continue
                        if (ov.get("day_of_week") == dow) or (ov.get("specific_date") == date_s):
                            if ov["start_time"] < et_t and ov["end_time"] > st_t:
                                blocked = True
                                break
                    if blocked:
                        continue

                    # Availability check
                    windows = [w for w in avail_cache.get(uid, [])
                               if w.get("specific_date") == date_s or w.get("day_of_week") == dow]
                    if not any(w["start_time"] <= st_t and w["end_time"] >= et_t for w in windows):
                        continue

                    score = 0.0

                    # Skills
                    emp_s = emp_skills_map.get(uid, set())
                    score += (60.0 * len(req_sids & emp_s) / len(req_sids)) if req_sids else 60.0
                    score += (20.0 * len(pref_sids & emp_s) / len(pref_sids)) if pref_sids else 0.0

                    # Priority rank (lower number = higher priority)
                    score += max(0.0, 30.0 - (emp.get("priority_rank") or 100) * 0.3)

                    # Hours balance
                    desired   = emp.get("desired_weekly_hours") or 20
                    remaining = max(0.0, desired - hours_week.get(uid, 0))
                    score += min(20.0, remaining * 1.5)

                    # Compatibility
                    hard_conflict = False
                    for sel_uid in selected:
                        key = (min(uid, sel_uid), max(uid, sel_uid))
                        compat = compat_map.get(key)
                        if not compat:
                            continue
                        cv = compat["compatibility"]
                        if cv == "never":
                            hard_conflict = True
                            break
                        elif cv == "avoid":
                            score -= 40.0
                        elif cv == "preferred":
                            score += 20.0
                    if hard_conflict:
                        continue

                    # Duty preferences
                    prefs = pref_map.get(uid, {})
                    score += sum(prefs.get(sid, 0) * 5 for sid in all_sids)

                    # Historical ratings for this shift type
                    recent = _all("""
                        SELECT sr.rating FROM schedule_ratings sr
                        JOIN shifts s ON sr.shift_id = s.id
                        WHERE sr.user_id=? AND s.type=?
                        ORDER BY s.date DESC LIMIT 10""", (uid, tmpl["type"]))
                    if recent:
                        score += (sum(r["rating"] for r in recent) / len(recent)) * 5.0

                    if score > best_score:
                        best_score = score
                        best_uid   = uid

                if best_uid is not None:
                    selected.append(best_uid)
                    hours_week[best_uid] = hours_week.get(best_uid, 0) + dur
                else:
                    break

            proposals.append({
                "date":         date_s,
                "template_id":  tmpl["id"],
                "start_time":   st_t,
                "end_time":     et_t,
                "type":         tmpl["type"],
                "label":        tmpl.get("label"),
                "assigned":     selected,
                "understaffed": len(selected) < tmpl["min_staff"],
                "min_staff":    tmpl["min_staff"],
                "max_staff":    tmpl["max_staff"],
            })

    return proposals
