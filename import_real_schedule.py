"""Import the real Summer Schedule (from the uploaded photo) into auto_scheduler.db.

- Creates the 13 real employees (password demo1234 each)
- Deactivates the placeholder accounts (test, johnsmith)
- Replaces generated shifts (2026-08-31 onward) with the real role x day grid,
  this week + next week, with the real per-day hours from the sheet
- Rebuilds recurring_shifts to match the real template, sets business hours
  from the sheet, creates Kitchen/Front/Bar skills and assigns them
- Leaves Joshua's admin account (ORBstudio) untouched

Rerunnable: wipes its own imported range before inserting.
Run: ../../.venv/Scripts/python.exe import_real_schedule.py
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

import bcrypt

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_scheduler.db")
PASSWORD = "demo1234"

# name -> (username, skills)   skills: K=Kitchen F=Front B=Bar
STAFF = {
    "Eve":       ("eve",       "K"),
    "Jacob":     ("jacob",     "KF"),
    "Jade":      ("jade",      "K"),
    "Christine": ("christine", "K"),
    "Josh":      ("josh",      "KF"),
    "Missiel":   ("missiel",   "KF"),
    "Johnny":    ("johnny",    "F"),
    "Jonnet":    ("jonnet",    "F"),
    "Andy":      ("andy",      "F"),
    "Jonathan":  ("jonathan",  "F"),
    "Terry":     ("terry",     "F"),
    "Devane":    ("devane",    "K"),
    "Vito":      ("vito",      "B"),
}

# day index: 0=Mon .. 6=Sun. Times in 24h 'HH:MM'; overnight ends are early AM.
ROLES = ["Open Kitchen", "Close Kitchen", "Open Front", "Close Front",
         "Front Float", "Kitchen Float", "Second Bar"]

GRID = {  # role -> day -> (name, start, end)
    "Open Kitchen": {
        0: ("Eve", "10:00", "17:30"), 1: ("Jacob", "10:00", "17:30"),
        2: ("Jacob", "10:00", "17:30"), 3: ("Jade", "10:00", "16:30"),
        4: ("Eve", "10:00", "19:00"), 5: ("Eve", "09:00", "19:00"),
        6: ("Eve", "10:00", "17:30"),
    },
    "Close Kitchen": {
        0: ("Christine", "16:30", "00:00"), 1: ("Josh", "16:30", "00:00"),
        2: ("Christine", "16:30", "00:00"), 3: ("Missiel", "15:30", "00:00"),
        4: ("Josh", "18:00", "03:30"), 5: ("Christine", "18:00", "06:00"),
        6: ("Christine", "16:30", "00:00"),
    },
    "Open Front": {
        0: ("Jonnet", "10:00", "17:15"), 1: ("Jonnet", "10:00", "17:15"),
        2: ("Johnny", "10:00", "17:15"), 3: ("Jacob", "10:00", "17:15"),
        4: ("Jacob", "10:00", "19:00"), 5: ("Jonathan", "10:00", "19:00"),
        6: ("Terry", "07:00", "16:00"),
    },
    "Close Front": {
        0: ("Johnny", "16:45", "00:00"), 1: ("Andy", "16:45", "00:00"),
        2: ("Jonathan", "16:45", "00:00"), 3: ("Andy", "16:45", "00:00"),
        4: ("Jonathan", "18:30", "04:30"), 5: ("Jonathan", "19:00", "04:30"),
        6: ("Josh", "15:30", "00:00"),
    },
    "Front Float": {
        4: ("Missiel", "18:00", "05:00"), 5: ("Missiel", "18:00", "05:00"),
    },
    "Kitchen Float": {
        4: ("Devane", "18:30", "06:30"), 5: ("Devane", "18:30", "06:30"),
    },
    "Second Bar": {
        4: ("Vito", "22:30", "06:30"), 5: ("Vito", "22:30", "06:30"),
    },
}

# Venue span per the sheet (Fri/Sat run past midnight).
BUSINESS_HOURS = {  # day -> (open, close)
    0: ("10:00", "00:00"), 1: ("10:00", "00:00"), 2: ("10:00", "00:00"),
    3: ("10:00", "00:00"), 4: ("10:00", "06:00"), 5: ("09:00", "06:00"),
    6: ("07:00", "00:00"),
}

con = sqlite3.connect(DB)
cur = con.cursor()
now = datetime.now().isoformat()

# --- Users ---
pw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
cur.execute("UPDATE users SET is_active = 0 WHERE username IN ('test', 'johnsmith')")
user_ids = {}
for full_name, (username, _skills) in STAFF.items():
    row = cur.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if row:
        user_ids[full_name] = row[0]
        cur.execute("UPDATE users SET is_active = 1 WHERE id = ?", (row[0],))
    else:
        cur.execute(
            "INSERT INTO users (username, email, hashed_password, full_name, role,"
            " receive_shift_requests, is_active, created_at) VALUES (?,?,?,?, 'employee', 1, 1, ?)",
            (username, f"{username}@justthetap.com", pw, full_name, now),
        )
        user_ids[full_name] = cur.lastrowid
print(f"Users ready: {len(user_ids)} staff + ORBstudio admin")

# --- Skills ---
SKILLS = {"K": ("Kitchen", "#f97316"), "F": ("Front of House", "#3b82f6"), "B": ("Bar", "#8b5cf6")}
skill_ids = {}
for code, (name, color) in SKILLS.items():
    row = cur.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
    if row:
        skill_ids[code] = row[0]
    else:
        cur.execute("INSERT INTO skills (name, color) VALUES (?,?)", (name, color))
        skill_ids[code] = cur.lastrowid
for full_name, (_u, codes) in STAFF.items():
    for code in codes:
        dup = cur.execute(
            "SELECT 1 FROM employee_skills WHERE user_id = ? AND skill_id = ?",
            (user_ids[full_name], skill_ids[code]),
        ).fetchone()
        if not dup:
            cur.execute(
                "INSERT INTO employee_skills (user_id, skill_id, proficiency) VALUES (?,?,?)",
                (user_ids[full_name], skill_ids[code], 3),
            )
print("Skills assigned:", {c: s[0] for c, s in SKILLS.items()})

# --- Business hours ---
for dow, (o, c) in BUSINESS_HOURS.items():
    cur.execute(
        "UPDATE business_hours SET open_time = ?, close_time = ?, is_closed = 0 WHERE day_of_week = ?",
        (o, c, dow),
    )

# --- Recurring templates: replace with the real grid ---
cur.execute("UPDATE recurring_shifts SET is_active = 0")
owner_id = cur.execute("SELECT id FROM users WHERE username = 'ORBstudio'").fetchone()[0]
for role in ROLES:
    for dow, (name, start, end) in GRID[role].items():
        cur.execute(
            "INSERT INTO recurring_shifts (day_of_week, start_time, end_time, type, label,"
            " min_staff, max_staff, is_active, created_at, created_by) VALUES (?,?,?,?,?,1,1,1,?,?)",
            (dow, start, end, "regular", role, now, owner_id),
        )
print(f"Recurring templates rebuilt: {sum(len(v) for v in GRID.values())} role-days")

# --- Shifts: clear imported range, insert this week + next week ---
today = date.today()
monday = today - timedelta(days=today.weekday())
cur.execute("DELETE FROM shifts WHERE date >= ?", (monday.isoformat(),))
created = 0
for week in (0, 1):
    for role in ROLES:
        for dow, (name, start, end) in GRID[role].items():
            d = monday + timedelta(days=dow + 7 * week)
            cur.execute(
                "INSERT INTO shifts (date, start_time, end_time, type, label, status,"
                " assigned_user_id, created_at) VALUES (?,?,?,?,?, 'filled', ?, ?)",
                (d.isoformat(), start, end, "regular", role, user_ids[name], now),
            )
            created += 1
print(f"Shifts created: {created} ({len(GRID)} roles x 2 weeks)")

# --- Notification for the owner ---
dup = cur.execute(
    "SELECT 1 FROM notifications WHERE user_id = ? AND title = 'Summer schedule imported'",
    (owner_id,),
).fetchone()
if not dup:
    cur.execute(
        "INSERT INTO notifications (user_id, title, message, deep_link, is_read, created_at)"
        " VALUES (?,?,?,?,0,?)",
        (owner_id, "Summer schedule imported",
         f"The real summer schedule is live: {len(STAFF)} staff, {created} shifts across 7 roles.", None, now),
    )

con.commit()
con.close()
print("Done. Real schedule is in.")
