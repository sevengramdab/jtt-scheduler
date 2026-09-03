"""Refresh demo data in the live auto_scheduler.db for the boss demo.

- Resets all account passwords to demo1234 (owner forgot theirs)
- Generates this week's + next week's shifts from the recurring templates
- Adds bar duties (incl. inventory) to this week's shifts
- Adds a few unread notifications so the app feels alive

Rerunnable: skips shifts that already exist for a given date+time.
Run: D:/claw source code/claw-code-parity/.venv/Scripts/python.exe refresh_demo_data.py
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

import bcrypt

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_scheduler.db")
PASSWORD = "demo1234"

con = sqlite3.connect(DB)
cur = con.cursor()

# --- 1. Password resets ---
pw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
cur.execute("UPDATE users SET hashed_password = ?", (pw,))
print(f"Password reset to '{PASSWORD}' for {cur.rowcount} account(s)")

users = cur.execute("SELECT id, username, full_name, role FROM users ORDER BY id").fetchall()
print("Accounts:", [(u[1], u[3]) for u in users])
ids = {row[1]: row[0] for row in users}
owner = ids.get("ORBstudio")
john = ids.get("johnsmith")

# --- 2. Shifts from recurring templates: this week + next week ---
templates = cur.execute(
    "SELECT day_of_week, start_time, end_time, type, label FROM recurring_shifts WHERE is_active = 1"
).fetchall()
today = date.today()
monday = today - timedelta(days=today.weekday())
rotation = [u for u in [john, owner, ids.get("test")] if u]

created = 0
for week in (0, 1):
    for dow, start, end, stype, label in templates:
        d = monday + timedelta(days=dow + 7 * week)
        exists = cur.execute(
            "SELECT 1 FROM shifts WHERE date = ? AND start_time = ?", (d.isoformat(), start)
        ).fetchone()
        if exists:
            continue
        # Leave next week's Friday open so there is a claimable shift.
        if week == 1 and dow == 4:
            assignee, status = None, "open"
        else:
            assignee = rotation[(dow + week) % len(rotation)]
            status = "filled"
        cur.execute(
            "INSERT INTO shifts (date, start_time, end_time, type, label, status, assigned_user_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (d.isoformat(), start, end, stype, label, status, assignee, datetime.now().isoformat()),
        )
        created += 1
print(f"Created {created} shifts for weeks of {monday} and {monday + timedelta(days=7)}")

# --- 3. Duties on this week's shifts (incl. inventory) ---
DUTIES = [
    ("Prep garnishes & restock bar", "prep", "11:30"),
    ("Count keg & bottle inventory", "inventory", "14:00"),
    ("Clean tap lines", "cleaning", "16:30"),
]
week_shift_ids = [
    r[0]
    for r in cur.execute(
        "SELECT id FROM shifts WHERE date BETWEEN ? AND ? ORDER BY date",
        (monday.isoformat(), (monday + timedelta(days=4)).isoformat()),
    )
]
added = 0
for i, sid in enumerate(week_shift_ids):
    for j, (title, dtype, slot) in enumerate(DUTIES):
        if (i + j) % 2 == 0:  # spread duties across the week
            dup = cur.execute(
                "SELECT 1 FROM shift_duties WHERE shift_id = ? AND title = ?", (sid, title)
            ).fetchone()
            if not dup:
                cur.execute(
                    "INSERT INTO shift_duties (shift_id, title, duty_type, time_slot, assigned_user_id, notes, sort_order, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (sid, title, dtype, slot, john, "", j, datetime.now().isoformat()),
                )
                added += 1
print(f"Added {added} shift duties")

# --- 4. Notifications ---
NOTIFS = [
    (owner, "Schedule updated", f"New shifts were posted for the weeks of {monday:%b %d} and {monday + timedelta(days=7):%b %d}.", None),
    (owner, "Open shift", "Friday closing week next week is still unassigned.", None),
    (john, "New shifts assigned", f"You have new shifts on the {monday:%b %d} schedule. Check your duties.", None),
]
added_n = 0
for uid, title, msg, link in NOTIFS:
    if uid is None:
        continue
    dup = cur.execute(
        "SELECT 1 FROM notifications WHERE user_id = ? AND title = ?", (uid, title)
    ).fetchone()
    if not dup:
        cur.execute(
            "INSERT INTO notifications (user_id, title, message, deep_link, is_read, created_at)"
            " VALUES (?,?,?,?,0,?)",
            (uid, title, msg, link, datetime.now().isoformat()),
        )
        added_n += 1
print(f"Added {added_n} notifications")

con.commit()
con.close()
print("Done.")
