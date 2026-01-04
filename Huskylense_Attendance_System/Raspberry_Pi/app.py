# File: raspberry_pi/app.py

import os
import csv
import io
import time
import threading
import sqlite3
from datetime import datetime, date

from flask import Flask, request, redirect, render_template_string, send_file, abort

# =========================
# CONFIG
# =========================
DB_PATH = os.getenv("ATTENDANCE_DB", "attendance.db")
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyACM0")
BAUDRATE = int(os.getenv("BAUDRATE", "115200"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN", "60"))  # once per minute per student
SERVER_HOST = os.getenv("HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", "5000"))

LOGO_URL = os.getenv(
    "LOGO_URL",
    "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSX95UhXWQGJcPeddBEhfzVy1us7TLm1hCyUg&s",
)

# =========================
# OPTIONAL SERIAL (Arduino)
# =========================
ser = None
SERIAL_OK = False
SERIAL_ERROR = ""

try:
    import serial  # pyserial
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
    SERIAL_OK = True
except Exception as e:
    SERIAL_OK = False
    SERIAL_ERROR = str(e)

# =========================
# DATABASE
# =========================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS classes (
    classname TEXT PRIMARY KEY
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    class TEXT NOT NULL,
    UNIQUE(name COLLATE NOCASE)
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER,
    name TEXT,
    class TEXT,
    time TEXT
);
""")

conn.commit()

db_lock = threading.Lock()

# =========================
# APP
# =========================
app = Flask(__name__)

# Anti-spam cooldown (per Face ID)
last_seen = {}  # {id: epoch_seconds}


# =========================
# UI (Professional Style)
# =========================
CSS = f"""
<style>
:root {{
  --bg: #0b1220;
  --card: #111a2b;
  --card2: #0f1729;
  --border: rgba(255,255,255,.08);
  --muted: rgba(255,255,255,.65);
  --text: rgba(255,255,255,.92);

  --blue: #2563eb;
  --blue2: #1d4ed8;
  --blue3: #0b3b91;

  --danger: #ef4444;
  --danger2: #dc2626;

  --success: #22c55e;
  --success2: #16a34a;

  --warn: #f59e0b;
  --shadow: 0 14px 35px rgba(0,0,0,.35);
}}

* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; }}
body {{
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Helvetica Neue", Helvetica, sans-serif;
  background: radial-gradient(1000px 600px at 20% 0%, rgba(37,99,235,.25), transparent 60%),
              radial-gradient(900px 500px at 90% 10%, rgba(34,197,94,.14), transparent 55%),
              radial-gradient(800px 500px at 50% 100%, rgba(245,158,11,.12), transparent 60%),
              var(--bg);
  color: var(--text);
}}

.container {{
  width: 92%;
  max-width: 1050px;
  margin: 34px auto;
}}

.topbar {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  margin-bottom:16px;
}}

.brand {{
  display:flex;
  align-items:center;
  gap:12px;
}}

.brand img {{
  width: 44px;
  height: 44px;
  border-radius: 12px;
  object-fit: cover;
  background: rgba(255,255,255,.06);
  border: 1px solid var(--border);
}}

.brand h1 {{
  margin:0;
  font-size: 18px;
  letter-spacing: .2px;
}}

.brand .sub {{
  margin:0;
  color: var(--muted);
  font-size: 12px;
}}

.pill {{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 8px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.04);
  color: var(--muted);
  font-size: 12px;
}}

.grid {{
  display:grid;
  grid-template-columns: 1.2fr .8fr;
  gap: 14px;
}}

@media (max-width: 900px) {{
  .grid {{
    grid-template-columns: 1fr;
  }}
}}

.card {{
  background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.03));
  border: 1px solid var(--border);
  border-radius: 18px;
  box-shadow: var(--shadow);
  overflow:hidden;
}}

.card .header {{
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap: 12px;
}}

.card .header h2 {{
  margin:0;
  font-size: 14px;
  letter-spacing: .3px;
  color: rgba(255,255,255,.88);
}}

.card .body {{
  padding: 16px;
}}

.stats {{
  display:grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}}

.stat {{
  background: rgba(0,0,0,.18);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 12px;
}}

.stat .k {{
  margin:0;
  font-size: 11px;
  color: var(--muted);
}}
.stat .v {{
  margin:6px 0 0 0;
  font-size: 22px;
  font-weight: 750;
}}

.actions {{
  display:flex;
  flex-wrap:wrap;
  gap: 10px;
  justify-content: center; /* center buttons */
}}

.btn {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: 14px;
  text-decoration:none;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.06);
  color: rgba(255,255,255,.92);
  font-size: 14px;
  cursor:pointer;
  transition: transform .08s ease, background .15s ease, border-color .15s ease;
  min-width: 170px;
}}

.btn:hover {{
  background: rgba(255,255,255,.09);
  transform: translateY(-1px);
  border-color: rgba(255,255,255,.14);
}}

.btn.primary {{
  background: linear-gradient(180deg, rgba(37,99,235,.95), rgba(29,78,216,.95));
  border-color: rgba(37,99,235,.55);
}}
.btn.primary:hover {{
  background: linear-gradient(180deg, rgba(37,99,235,1), rgba(29,78,216,1));
}}

.btn.success {{
  background: linear-gradient(180deg, rgba(34,197,94,.95), rgba(22,163,74,.95));
  border-color: rgba(34,197,94,.50);
}}
.btn.danger {{
  background: linear-gradient(180deg, rgba(239,68,68,.95), rgba(220,38,38,.95));
  border-color: rgba(239,68,68,.50);
}}

.btn.small {{
  min-width: auto;
  padding: 8px 10px;
  border-radius: 12px;
  font-size: 13px;
}}

hr.sep {{
  border: none;
  border-top: 1px solid var(--border);
  margin: 14px 0;
}}

.table-wrap {{
  display:flex;
  justify-content:center; /* center table */
}}

table {{
  width: 100%;
  border-collapse: collapse;
  overflow:hidden;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(0,0,0,.18);
}}

thead th {{
  background: linear-gradient(180deg, rgba(11,59,145,.95), rgba(8,44,110,.95)); /* darker than buttons */
  color: rgba(255,255,255,.95);
  padding: 12px 12px;
  font-size: 12px;
  letter-spacing: .25px;
  text-transform: uppercase;
  border-bottom: 1px solid rgba(255,255,255,.10);
}}

tbody td {{
  padding: 11px 12px;
  border-bottom: 1px solid rgba(255,255,255,.08);
  color: rgba(255,255,255,.92);
  font-size: 14px;
}}

tbody tr:hover {{
  background: rgba(37,99,235,.08);
}}

.badge {{
  display:inline-flex;
  align-items:center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.05);
  color: rgba(255,255,255,.88);
}}

.muted {{
  color: var(--muted);
  font-size: 13px;
}}

.form {{
  display:grid;
  gap: 10px;
}}

label {{
  font-size: 12px;
  color: var(--muted);
}}

input[type=text], select {{
  width: 100%;
  padding: 12px 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(0,0,0,.25);
  color: rgba(255,255,255,.92);
  outline: none;
}}

input[type=text]:focus, select:focus {{
  border-color: rgba(37,99,235,.55);
}}

.notice {{
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.05);
  color: rgba(255,255,255,.90);
  font-size: 13px;
}}

.notice.good {{
  border-color: rgba(34,197,94,.40);
  background: rgba(34,197,94,.08);
}}
.notice.bad {{
  border-color: rgba(239,68,68,.45);
  background: rgba(239,68,68,.08);
}}
.notice.warn {{
  border-color: rgba(245,158,11,.45);
  background: rgba(245,158,11,.08);
}}

.footer {{
  text-align:center;
  margin-top: 14px;
  color: rgba(255,255,255,.45);
  font-size: 12px;
}}
</style>
"""

BASE_TOP = """
<div class="topbar">
  <div class="brand">
    <img src="{logo}" alt="Logo">
    <div>
      <h1>Attendance System</h1>
      <p class="sub">HuskyLens • Arduino Mega • Raspberry Pi • Flask • SQLite</p>
    </div>
  </div>
  <div class="pill">
    <span>Serial:</span>
    {serial_badge}
  </div>
</div>
"""

def serial_badge_html():
    if SERIAL_OK:
        return '<span class="badge">✅ Connected</span>'
    return f'<span class="badge">⚠ Not connected</span>'

def page_wrap(inner_html: str) -> str:
    top = BASE_TOP.format(logo=LOGO_URL, serial_badge=serial_badge_html())
    return CSS + f'<div class="container">{top}{inner_html}<div class="footer">AI Attendance • Local Network Dashboard</div></div>'


# =========================
# HELPERS
# =========================
def get_classes():
    with db_lock:
        cur.execute("SELECT classname FROM classes ORDER BY classname")
        return [r["classname"] for r in cur.fetchall()]

def ensure_default_classes():
    # Only insert if empty
    with db_lock:
        cur.execute("SELECT COUNT(*) AS c FROM classes")
        c = cur.fetchone()["c"]
        if c == 0:
            cur.executemany("INSERT OR IGNORE INTO classes(classname) VALUES (?)", [
                ("Class A",),
                ("Class B",),
            ])
            conn.commit()

def normalize_name(name: str) -> str:
    return " ".join((name or "").strip().split())

def is_duplicate_name(name: str, exclude_id: int | None = None) -> bool:
    with db_lock:
        if exclude_id is None:
            cur.execute("SELECT 1 FROM users WHERE name = ? COLLATE NOCASE LIMIT 1", (name,))
        else:
            cur.execute("SELECT 1 FROM users WHERE name = ? COLLATE NOCASE AND id != ? LIMIT 1", (name, exclude_id))
        return cur.fetchone() is not None

def get_user_by_id(uid: int):
    with db_lock:
        cur.execute("SELECT * FROM users WHERE id=?", (uid,))
        return cur.fetchone()

def today_prefix():
    return date.today().strftime("%Y-%m-%d")


ensure_default_classes()


# =========================
# PAGES
# =========================
@app.route("/")
def home():
    today = today_prefix()

    with db_lock:
        cur.execute("SELECT COUNT(*) AS c FROM users")
        total_users = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM records WHERE time LIKE ?", (today + "%",))
        total_today = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM records")
        total_all = cur.fetchone()["c"]

        cur.execute("SELECT * FROM records ORDER BY time DESC LIMIT 8")
        recent = cur.fetchall()

    status_note = ""
    if not SERIAL_OK:
        status_note = f"""
        <div class="notice warn">
          <b>Serial not connected.</b> The web dashboard still works, but attendance will not auto-log until Arduino is connected.<br>
          <span class="muted">Error: {SERIAL_ERROR}</span>
        </div>
        """

    inner = f"""
    <div class="grid">
      <div class="card">
        <div class="header">
          <h2>Dashboard</h2>
          <span class="badge">Today: {today}</span>
        </div>
        <div class="body">
          {status_note}
          <div class="stats">
            <div class="stat">
              <p class="k">Total Registered Users</p>
              <p class="v">{total_users}</p>
            </div>
            <div class="stat">
              <p class="k">Check-ins Today</p>
              <p class="v">{total_today}</p>
            </div>
            <div class="stat">
              <p class="k">Total Attendance Records</p>
              <p class="v">{total_all}</p>
            </div>
            <div class="stat">
              <p class="k">Cooldown Rule</p>
              <p class="v">{COOLDOWN_SECONDS}s</p>
            </div>
          </div>

          <hr class="sep">

          <div class="actions">
            <a class="btn primary" href="/attendance">📄 View Attendance</a>
            <a class="btn primary" href="/register">📝 Register Student</a>
            <a class="btn" href="/users">👥 User List</a>
            <a class="btn" href="/classes">🏫 Manage Classes</a>
            <a class="btn" href="/analytics">📊 Analytics</a>
            <a class="btn success" href="/export_csv">⬇ Export CSV</a>
          </div>

          <hr class="sep">

          <div class="actions">
            <form action="/reset_ids" method="post" style="margin:0;">
              <button class="btn danger" type="submit"
                onclick="return confirm('Are you sure you want to RESET ALL REGISTERED IDs? This will delete all users.');">
                ❌ Reset Registered IDs
              </button>
            </form>

            <form action="/reset_attendance" method="post" style="margin:0;">
              <button class="btn danger" type="submit"
                onclick="return confirm('Are you sure you want to CLEAR ALL ATTENDANCE RECORDS? This cannot be undone.');">
                🗑 Reset Attendance Records
              </button>
            </form>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="header">
          <h2>Recent Check-ins</h2>
          <span class="badge">Last 8</span>
        </div>
        <div class="body">
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Name</th><th>Class</th><th>Time</th></tr>
              </thead>
              <tbody>
                {''.join([f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['class']}</td><td>{r['time']}</td></tr>" for r in recent]) or "<tr><td colspan='4' class='muted'>No records yet.</td></tr>"}
              </tbody>
            </table>
          </div>
          <p class="muted" style="margin-top:10px;">Tip: If you see “Unknown ID” in terminal, register that Face ID in the dashboard.</p>
        </div>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/attendance")
def attendance():
    cls = (request.args.get("class") or "").strip()
    classes = get_classes()

    with db_lock:
        if cls and cls != "ALL":
            cur.execute("SELECT * FROM records WHERE class=? ORDER BY time DESC", (cls,))
        else:
            cur.execute("SELECT * FROM records ORDER BY time DESC")
        rows = cur.fetchall()

    options = ['<option value="ALL">ALL</option>'] + [
        f'<option value="{c}" {"selected" if c==cls else ""}>{c}</option>' for c in classes
    ]

    inner = f"""
    <div class="card">
      <div class="header">
        <h2>Attendance Records</h2>
        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
          <form method="get" action="/attendance" style="margin:0; display:flex; gap:10px; align-items:center;">
            <label style="margin:0;">Filter by class</label>
            <select name="class" onchange="this.form.submit()">
              {''.join(options)}
            </select>
          </form>
          <a class="btn small success" href="/export_csv{('?class=' + cls) if (cls and cls!='ALL') else ''}">⬇ Export CSV</a>
          <a class="btn small" href="/">⬅ Back</a>
        </div>
      </div>
      <div class="body">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Name</th><th>Class</th><th>Timestamp</th></tr>
            </thead>
            <tbody>
              {''.join([f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['class']}</td><td>{r['time']}</td></tr>" for r in rows]) or "<tr><td colspan='4' class='muted'>No records found.</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/register", methods=["GET", "POST"])
def register():
    classes = get_classes()
    if not classes:
        classes = ["Class A"]

    msg = ""
    msg_cls = "notice"

    if request.method == "POST":
        try:
            uid = int(request.form["id"])
        except Exception:
            uid = -1
        name = normalize_name(request.form.get("name", ""))
        cls = (request.form.get("class") or "").strip()

        if uid < 0:
            msg = "Invalid Face ID."
            msg_cls = "notice bad"
        elif not name:
            msg = "Name cannot be empty."
            msg_cls = "notice bad"
        elif not cls:
            msg = "Class is required."
            msg_cls = "notice bad"
        elif is_duplicate_name(name):
            msg = f'Duplicate name blocked: "{name}". Use a different name.'
            msg_cls = "notice bad"
        else:
            with db_lock:
                # Insert or replace by Face ID, but must also respect UNIQUE name
                try:
                    cur.execute("INSERT OR REPLACE INTO users(id, name, class) VALUES (?,?,?)", (uid, name, cls))
                    conn.commit()
                    return redirect("/users")
                except sqlite3.IntegrityError:
                    msg = f'Duplicate name blocked: "{name}".'
                    msg_cls = "notice bad"

    options = "".join([f'<option value="{c}">{c}</option>' for c in classes])

    inner = f"""
    <div class="card">
      <div class="header">
        <h2>Register Student</h2>
        <a class="btn small" href="/">⬅ Back</a>
      </div>
      <div class="body">
        <div class="{msg_cls}" style="{'' if msg else 'display:none;'}">{msg}</div>

        <form class="form" action="/register" method="post" autocomplete="off">
          <div>
            <label>Face ID (from HuskyLens)</label>
            <input type="text" name="id" placeholder="Example: 1" required>
          </div>
          <div>
            <label>Student Name</label>
            <input type="text" name="name" placeholder="Example: Ryan" required>
          </div>
          <div>
            <label>Class</label>
            <select name="class" required>
              {options}
            </select>
          </div>
          <button class="btn primary" type="submit">✅ Save Registration</button>
          <p class="muted">Rule: exact duplicate names are blocked (case-insensitive).</p>
        </form>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/users")
def users():
    with db_lock:
        cur.execute("SELECT * FROM users ORDER BY class, id")
        rows = cur.fetchall()

    inner = f"""
    <div class="card">
      <div class="header">
        <h2>Registered Users</h2>
        <div style="display:flex; gap:10px; align-items:center;">
          <a class="btn small primary" href="/register">➕ Register</a>
          <a class="btn small" href="/">⬅ Back</a>
        </div>
      </div>
      <div class="body">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Name</th><th>Class</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {''.join([
                f"<tr>"
                f"<td>{u['id']}</td>"
                f"<td>{u['name']}</td>"
                f"<td>{u['class']}</td>"
                f"<td style='white-space:nowrap;'>"
                f"<a class='btn small' href='/edit_user/{u['id']}'>Edit</a> "
                f"<form action='/delete_user/{u['id']}' method='post' style='display:inline;margin:0;'>"
                f"<button class='btn small danger' type='submit' onclick=\"return confirm('Delete user {u['name']} (ID {u['id']})?');\">Delete</button>"
                f"</form>"
                f"</td>"
                f"</tr>"
                for u in rows
              ]) or "<tr><td colspan='4' class='muted'>No users registered yet.</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/edit_user/<int:uid>", methods=["GET", "POST"])
def edit_user(uid):
    user = get_user_by_id(uid)
    if not user:
        abort(404)

    classes = get_classes()
    msg = ""
    msg_cls = "notice"

    if request.method == "POST":
        name = normalize_name(request.form.get("name", ""))
        cls = (request.form.get("class") or "").strip()

        if not name:
            msg = "Name cannot be empty."
            msg_cls = "notice bad"
        elif not cls:
            msg = "Class is required."
            msg_cls = "notice bad"
        elif is_duplicate_name(name, exclude_id=uid):
            msg = f'Duplicate name blocked: "{name}".'
            msg_cls = "notice bad"
        else:
            with db_lock:
                try:
                    cur.execute("UPDATE users SET name=?, class=? WHERE id=?", (name, cls, uid))
                    conn.commit()
                    return redirect("/users")
                except sqlite3.IntegrityError:
                    msg = f'Duplicate name blocked: "{name}".'
                    msg_cls = "notice bad"

    opts = "".join([f'<option value="{c}" {"selected" if c==user["class"] else ""}>{c}</option>' for c in classes])

    inner = f"""
    <div class="card">
      <div class="header">
        <h2>Edit User (ID {uid})</h2>
        <a class="btn small" href="/users">⬅ Back</a>
      </div>
      <div class="body">
        <div class="{msg_cls}" style="{'' if msg else 'display:none;'}">{msg}</div>

        <form class="form" action="/edit_user/{uid}" method="post" autocomplete="off">
          <div>
            <label>Student Name</label>
            <input type="text" name="name" value="{user['name']}" required>
          </div>
          <div>
            <label>Class</label>
            <select name="class" required>
              {opts}
            </select>
          </div>
          <button class="btn primary" type="submit">💾 Save Changes</button>
          <p class="muted">Rule: exact duplicate names are blocked (case-insensitive).</p>
        </form>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/delete_user/<int:uid>", methods=["POST"])
def delete_user(uid):
    with db_lock:
        cur.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
    return redirect("/users")


@app.route("/classes", methods=["GET", "POST"])
def classes():
    msg = ""
    msg_cls = "notice"

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        classname = (request.form.get("classname") or "").strip()
        if action == "add":
            if not classname:
                msg = "Class name cannot be empty."
                msg_cls = "notice bad"
            else:
                with db_lock:
                    cur.execute("INSERT OR IGNORE INTO classes(classname) VALUES (?)", (classname,))
                    conn.commit()
                msg = f'Class added: {classname}'
                msg_cls = "notice good"
        elif action == "delete":
            if not classname:
                msg = "Missing class name."
                msg_cls = "notice bad"
            else:
                with db_lock:
                    # Optional safety: do not delete if any users exist in that class
                    cur.execute("SELECT COUNT(*) AS c FROM users WHERE class=?", (classname,))
                    c = cur.fetchone()["c"]
                    if c > 0:
                        msg = f"Cannot delete '{classname}' because {c} user(s) are still assigned to it."
                        msg_cls = "notice bad"
                    else:
                        cur.execute("DELETE FROM classes WHERE classname=?", (classname,))
                        conn.commit()
                        msg = f"Class deleted: {classname}"
                        msg_cls = "notice good"
        else:
            msg = "Invalid action."
            msg_cls = "notice bad"

    classes = get_classes()

    inner = f"""
    <div class="card">
      <div class="header">
        <h2>Manage Classes</h2>
        <a class="btn small" href="/">⬅ Back</a>
      </div>
      <div class="body">
        <div class="{msg_cls}" style="{'' if msg else 'display:none;'}">{msg}</div>

        <div class="grid" style="grid-template-columns: 1fr 1fr;">
          <div class="card" style="box-shadow:none;">
            <div class="header"><h2>Add Class</h2></div>
            <div class="body">
              <form class="form" method="post">
                <input type="hidden" name="action" value="add">
                <div>
                  <label>Class name</label>
                  <input type="text" name="classname" placeholder="Example: 5A" required>
                </div>
                <button class="btn success" type="submit">➕ Add</button>
              </form>
            </div>
          </div>

          <div class="card" style="box-shadow:none;">
            <div class="header"><h2>Existing Classes</h2></div>
            <div class="body">
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Class</th><th>Action</th></tr></thead>
                  <tbody>
                    {''.join([
                      f"<tr><td>{c}</td>"
                      f"<td>"
                      f"<form method='post' style='margin:0;'>"
                      f"<input type='hidden' name='action' value='delete'>"
                      f"<input type='hidden' name='classname' value='{c}'>"
                      f"<button class='btn small danger' type='submit' onclick=\"return confirm('Delete class {c}? (Only allowed if no users are assigned)');\">Delete</button>"
                      f"</form>"
                      f"</td></tr>"
                      for c in classes
                    ]) or "<tr><td colspan='2' class='muted'>No classes found.</td></tr>"}
                  </tbody>
                </table>
              </div>
              <p class="muted" style="margin-top:10px;">Tip: You cannot delete a class while users are assigned to it.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/analytics")
def analytics():
    today = today_prefix()

    classes = get_classes()

    # Per-class: registered count, today's check-ins, total check-ins
    with db_lock:
        cur.execute("SELECT class, COUNT(*) AS cnt FROM users GROUP BY class ORDER BY class")
        reg_map = {r["class"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT class, COUNT(*) AS cnt FROM records WHERE time LIKE ? GROUP BY class ORDER BY class", (today + "%",))
        today_map = {r["class"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT class, COUNT(*) AS cnt FROM records GROUP BY class ORDER BY class")
        total_map = {r["class"]: r["cnt"] for r in cur.fetchall()}

        # Student status today (checked in or not)
        cur.execute("SELECT id, name, class FROM users ORDER BY class, name")
        users = cur.fetchall()

        cur.execute("SELECT DISTINCT id FROM records WHERE time LIKE ?", (today + "%",))
        checked_ids = {r["id"] for r in cur.fetchall()}

    rows_html = ""
    for c in classes:
        reg = reg_map.get(c, 0)
        td = today_map.get(c, 0)
        tot = total_map.get(c, 0)
        rows_html += f"<tr><td>{c}</td><td>{reg}</td><td>{td}</td><td>{tot}</td><td><a class='btn small success' href='/export_csv?class={c}'>Export</a></td></tr>"

    student_html = ""
    for u in users:
        ok = "✅ Checked" if u["id"] in checked_ids else "— Not yet"
        badge = '<span class="badge">✅ Checked</span>' if u["id"] in checked_ids else '<span class="badge">⏳ Not yet</span>'
        student_html += f"<tr><td>{u['id']}</td><td>{u['name']}</td><td>{u['class']}</td><td>{badge}</td></tr>"

    inner = f"""
    <div class="card">
      <div class="header">
        <h2>Analytics</h2>
        <div style="display:flex; gap:10px; align-items:center;">
          <span class="badge">Today: {today}</span>
          <a class="btn small" href="/">⬅ Back</a>
        </div>
      </div>
      <div class="body">
        <div class="grid" style="grid-template-columns: 1fr;">
          <div class="card" style="box-shadow:none;">
            <div class="header"><h2>Per-class Summary</h2></div>
            <div class="body">
              <div class="table-wrap">
                <table>
                  <thead><tr><th>Class</th><th>Registered</th><th>Today</th><th>Total</th><th>Export</th></tr></thead>
                  <tbody>
                    {rows_html or "<tr><td colspan='5' class='muted'>No classes found.</td></tr>"}
                  </tbody>
                </table>
              </div>
              <p class="muted" style="margin-top:10px;">Export button downloads CSV filtered by class.</p>
            </div>
          </div>

          <div class="card" style="box-shadow:none; margin-top:14px;">
            <div class="header"><h2>Student Status (Today)</h2></div>
            <div class="body">
              <div class="table-wrap">
                <table>
                  <thead><tr><th>ID</th><th>Name</th><th>Class</th><th>Status</th></tr></thead>
                  <tbody>
                    {student_html or "<tr><td colspan='4' class='muted'>No registered users.</td></tr>"}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
    """
    return render_template_string(page_wrap(inner))


@app.route("/reset_ids", methods=["POST"])
def reset_ids():
    with db_lock:
        cur.execute("DELETE FROM users")
        conn.commit()
    return redirect("/")


@app.route("/reset_attendance", methods=["POST"])
def reset_attendance():
    with db_lock:
        cur.execute("DELETE FROM records")
        conn.commit()
    return redirect("/")


@app.route("/export_csv")
def export_csv():
    cls = (request.args.get("class") or "").strip()

    with db_lock:
        if cls and cls != "ALL":
            cur.execute("SELECT * FROM records WHERE class=? ORDER BY time DESC", (cls,))
        else:
            cur.execute("SELECT * FROM records ORDER BY time DESC")
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Class", "Timestamp"])
    for r in rows:
        writer.writerow([r["id"], r["name"], r["class"], r["time"]])

    filename = "attendance.csv" if not (cls and cls != "ALL") else f"attendance_{cls.replace(' ', '_')}.csv"

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


# =========================
# SERIAL READER THREAD
# =========================
def record_attendance(face_id: int):
    # cooldown per ID
    now = time.time()
    if face_id in last_seen and now - last_seen[face_id] < COOLDOWN_SECONDS:
        return

    last_seen[face_id] = now

    with db_lock:
        cur.execute("SELECT name, class FROM users WHERE id=?", (face_id,))
        row = cur.fetchone()

        if not row:
            print(f"Unknown ID: {face_id}")
            return

        name = row["name"]
        cls = row["class"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("INSERT INTO records(id, name, class, time) VALUES (?,?,?,?)", (face_id, name, cls, timestamp))
        conn.commit()

    print(f"RECORDED: {name} ({face_id}) [{cls}] @ {timestamp}")

def reader():
    if not SERIAL_OK or ser is None:
        return

    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
        except Exception:
            time.sleep(0.2)
            continue

        if not line:
            continue

        # We only care about FACE:<ID> lines (Arduino prints these)
        if line.startswith("FACE:"):
            try:
                face_id = int(line.split(":", 1)[1].strip())
            except Exception:
                continue

            # optional: ignore ID 0
            if face_id == 0:
                continue

            record_attendance(face_id)

# Start reader thread if serial is OK
if SERIAL_OK:
    threading.Thread(target=reader, daemon=True).start()


# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    print(f"[INFO] DB: {DB_PATH}")
    if SERIAL_OK:
        print(f"[OK] Serial connected: {SERIAL_PORT} @ {BAUDRATE}")
    else:
        print(f"[WARN] Serial not connected: {SERIAL_PORT} ({SERIAL_ERROR})")

    app.run(host=SERVER_HOST, port=SERVER_PORT)
