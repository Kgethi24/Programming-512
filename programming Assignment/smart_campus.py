import sqlite3
import hashlib
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox

DB_NAME = "smart_campus.db"

CAMPUS_POLICIES = {
    "Main Campus":  {"max_duration": 4, "open_hour": 7, "close_hour": 20},
    "North Campus": {"max_duration": 3, "open_hour": 8, "close_hour": 18},
    "South Campus": {"max_duration": 2, "open_hour": 9, "close_hour": 17},
}


def hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def db():
    return sqlite3.connect(DB_NAME)


def campus_id(name):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM campuses WHERE name=?", (name,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def campus_name(cid):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM campuses WHERE id=?", (cid,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def policy_text(campus):
    p = CAMPUS_POLICIES[campus]
    return (f"Policy for {campus}: max {p['max_duration']} hour(s), "
            f"booking hours {p['open_hour']:02d}:00-{p['close_hour']:02d}:00")


# ----------------------------- OOP roles -----------------------------
class User:
    def __init__(self, uid, username, role, campus_id):
        self.uid = uid
        self.username = username
        self.role = role
        self.campus_id = campus_id

    def can_manage_resources(self):
        return False

    def can_view_all_campuses(self):
        return False


class Lecturer(User):
    pass


class CampusAdministrator(User):
    def can_manage_resources(self):
        return True


class SystemOperator(User):
    def can_manage_resources(self):
        return True

    def can_view_all_campuses(self):
        return True


def make_user(row):
    uid, username, role, cid = row
    if role == "Lecturer":
        return Lecturer(uid, username, role, cid)
    if role == "Campus Administrator":
        return CampusAdministrator(uid, username, role, cid)
    if role == "System Operator":
        return SystemOperator(uid, username, role, cid)
    return User(uid, username, role, cid)


# ----------------------------- DB setup -----------------------------
def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS campuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        campus_id INTEGER,
        FOREIGN KEY(campus_id) REFERENCES campuses(id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        campus_id INTEGER NOT NULL,
        FOREIGN KEY(campus_id) REFERENCES campuses(id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        campus_id INTEGER NOT NULL,
        booking_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        duration INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active',
        FOREIGN KEY(resource_id) REFERENCES resources(id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(campus_id) REFERENCES campuses(id))""")

    for name in CAMPUS_POLICIES:
        cur.execute("INSERT OR IGNORE INTO campuses(name) VALUES(?)", (name,))
    conn.commit()

    def cid(name):
        cur.execute("SELECT id FROM campuses WHERE name=?", (name,))
        return cur.fetchone()[0]

    seeds = [
        ("admin_main",  hash_pw("admin123"),    "Campus Administrator", cid("Main Campus")),
        ("admin_north", hash_pw("admin123"),    "Campus Administrator", cid("North Campus")),
        ("admin_south", hash_pw("admin123"),    "Campus Administrator", cid("South Campus")),
        ("operator",    hash_pw("operator123"), "System Operator",      None),
    ]
    for username, pw_hash, role, cid_value in seeds:
        cur.execute("INSERT OR IGNORE INTO users(username,password_hash,role,campus_id) "
                    "VALUES(?,?,?,?)", (username, pw_hash, role, cid_value))

    sample_resources = {
        "Main Campus": [
            ("MC-LAB1",  "Computer Lab 1",     "Computer Laboratory"),
            ("MC-PROJ1", "Projector A",        "Multimedia Projector"),
            ("MC-SEM1",  "Seminar Room 1",     "Seminar Room"),
        ],
        "North Campus": [
            ("NC-LAB1",  "Computer Lab 1",     "Computer Laboratory"),
            ("NC-PROJ1", "Projector A",        "Multimedia Projector"),
        ],
        "South Campus": [
            ("SC-SEM1",  "Seminar Room 1",     "Seminar Room"),
            ("SC-PROJ1", "Projector A",        "Multimedia Projector"),
        ],
    }
    for name, items in sample_resources.items():
        c = cid(name)
        for code, rname, rtype in items:
            cur.execute("INSERT OR IGNORE INTO resources(code,name,type,campus_id) "
                        "VALUES(?,?,?,?)", (code, rname, rtype, c))

    conn.commit()
    conn.close()


# ----------------------------- validation helpers -----------------------------
def parse_booking(date_s, start_s, dur_s):
    try:
        d = datetime.strptime(date_s, "%Y-%m-%d").date()
        t = datetime.strptime(start_s, "%H:%M").time()
        dur = int(dur_s)
    except ValueError:
        return None, None, None, "Use date YYYY-MM-DD, time HH:MM, duration as whole hours."
    return d, t, dur, None


def validate_rules(campus, d, t, dur):
    p = CAMPUS_POLICIES[campus]
    if d < date.today():
        return False, "Booking date cannot be in the past."
    if dur <= 0:
        return False, "Duration must be positive."
    if dur > p["max_duration"]:
        return False, f"Maximum duration for {campus} is {p['max_duration']} hour(s)."
    start_min = t.hour * 60 + t.minute
    end_min = start_min + dur * 60
    if start_min < p["open_hour"] * 60:
        return False, f"Booking cannot start before {p['open_hour']:02d}:00."
    if end_min > p["close_hour"] * 60:
        return False, f"Booking must end by {p['close_hour']:02d}:00."
    return True, ""


def has_overlap(resource_id, date_s, start_s, dur, exclude_id=None):
    conn = db()
    cur = conn.cursor()
    q = ("SELECT id, start_time, duration FROM bookings "
         "WHERE resource_id=? AND booking_date=? AND status='Active'")
    params = [resource_id, date_s]
    if exclude_id is not None:
        q += " AND id<>?"
        params.append(exclude_id)
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()

    st = datetime.strptime(start_s, "%H:%M")
    new_start = st.hour * 60 + st.minute
    new_end = new_start + dur * 60

    for _, existing_start_s, existing_dur in rows:
        et = datetime.strptime(existing_start_s, "%H:%M")
        existing_start = et.hour * 60 + et.minute
        existing_end = existing_start + existing_dur * 60
        if new_start < existing_end and new_end > existing_start:
            return True
    return False


# ----------------------------- App -----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Campus Resource Booking System")
        self.geometry("1150x720")
        self.user = None
        self.campus_var = None
        self.show_login()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def current_campus(self):
        return self.campus_var.get()

    # ------------------- login / register -------------------
    def show_login(self):
        self.clear()
        frame = ttk.Frame(self, padding=40)
        frame.pack(expand=True)
        ttk.Label(frame, text="Smart Campus Resource Booking System",
                  font=("Arial", 18, "bold")).pack(pady=10)

        ttk.Label(frame, text="Username").pack(anchor="w")
        self.login_user = tk.StringVar()
        ttk.Entry(frame, textvariable=self.login_user, width=35).pack(pady=4)

        ttk.Label(frame, text="Password").pack(anchor="w")
        self.login_pass = tk.StringVar()
        ttk.Entry(frame, textvariable=self.login_pass, show="*", width=35).pack(pady=4)

        ttk.Button(frame, text="Login", command=self.do_login).pack(pady=10, fill="x")
        ttk.Button(frame, text="Register Lecturer", command=self.show_register).pack(fill="x")
        ttk.Label(frame, text="Default admin: admin_main / admin123\n"
                              "Default operator: operator / operator123",
                  foreground="gray").pack(pady=15)

    def do_login(self):
        username = self.login_user.get().strip()
        password = self.login_pass.get().strip()
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash, role, campus_id "
                    "FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        conn.close()
        if not row or row[2] != hash_pw(password):
            messagebox.showerror("Login failed", "Invalid username or password.")
            return
        self.show_main((row[0], row[1], row[3], row[4]))

    def show_register(self):
        self.clear()
        frame = ttk.Frame(self, padding=40)
        frame.pack(expand=True)
        ttk.Label(frame, text="Register Lecturer Account",
                  font=("Arial", 16, "bold")).pack(pady=10)

        ttk.Label(frame, text="Username").pack(anchor="w")
        reg_user = tk.StringVar()
        ttk.Entry(frame, textvariable=reg_user, width=35).pack(pady=4)

        ttk.Label(frame, text="Password").pack(anchor="w")
        reg_pass = tk.StringVar()
        ttk.Entry(frame, textvariable=reg_pass, show="*", width=35).pack(pady=4)

        ttk.Label(frame, text="Campus").pack(anchor="w")
        reg_campus = tk.StringVar(value=list(CAMPUS_POLICIES.keys())[0])
        ttk.Combobox(frame, textvariable=reg_campus,
                     values=list(CAMPUS_POLICIES.keys()),
                     state="readonly", width=33).pack(pady=4)

        def register():
            username = reg_user.get().strip()
            password = reg_pass.get().strip()
            campus = reg_campus.get()
            if not username or not password:
                messagebox.showerror("Error", "Username and password are required.")
                return
            if len(password) < 4:
                messagebox.showerror("Error", "Password must be at least 4 characters.")
                return
            conn = db()
            cur = conn.cursor()
            try:
                cur.execute("INSERT INTO users(username,password_hash,role,campus_id) "
                            "VALUES(?,?,?,?)",
                            (username, hash_pw(password), "Lecturer", campus_id(campus)))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", "Lecturer account created. You can now log in.")
                self.show_login()
            except sqlite3.IntegrityError:
                conn.close()
                messagebox.showerror("Error", "That username already exists.")

        ttk.Button(frame, text="Register", command=register).pack(pady=10, fill="x")
        ttk.Button(frame, text="Back to Login", command=self.show_login).pack(fill="x")

    # ------------------- main window -------------------
    def show_main(self, user_row):
        self.clear()
        self.user = make_user(user_row)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text=f"Logged in: {self.user.username} ({self.user.role})",
                  font=("Arial", 11, "bold")).pack(side="left", padx=8)
        ttk.Label(top, text="Active Campus:").pack(side="left", padx=(25, 5))

        if self.user.role == "Campus Administrator":
            allowed = [campus_name(self.user.campus_id)]
        else:
            allowed = list(CAMPUS_POLICIES.keys())

        self.campus_var = tk.StringVar(value=allowed[0])
        combo = ttk.Combobox(top, textvariable=self.campus_var, values=allowed,
                             state="readonly", width=22)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_all())
        ttk.Button(top, text="Logout", command=self.show_login).pack(side="right", padx=8)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        if self.user.role == "Lecturer":
            self.build_lecturer_tabs()
        elif self.user.role == "Campus Administrator":
            self.build_admin_tabs()
        elif self.user.role == "System Operator":
            self.build_operator_tabs()

    # ------------------- lecturer -------------------
    def build_lecturer_tabs(self):
        book_frame = ttk.Frame(self.notebook)
        self.notebook.add(book_frame, text="Book Resource")
        self.build_book_tab(book_frame)

        my_frame = ttk.Frame(self.notebook)
        self.notebook.add(my_frame, text="My Bookings")
        self.build_my_bookings_tab(my_frame)

    def build_book_tab(self, frame):
        self.book_policy_lbl = ttk.Label(frame, text=policy_text(self.current_campus()),
                                         font=("Arial", 10, "bold"))
        self.book_policy_lbl.pack(anchor="w", padx=8, pady=6)

        columns = ("code", "name", "type", "status")
        self.resource_tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col in columns:
            self.resource_tree.heading(col, text=col.title())
            self.resource_tree.column(col, width=180)
        self.resource_tree.pack(fill="both", expand=True, padx=8, pady=6)

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=6)
        ttk.Label(form, text="Date YYYY-MM-DD").grid(row=0, column=0, padx=4)
        self.book_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form, textvariable=self.book_date, width=14).grid(row=1, column=0, padx=4)

        ttk.Label(form, text="Start HH:MM").grid(row=0, column=1, padx=4)
        self.book_start = tk.StringVar(value="09:00")
        ttk.Entry(form, textvariable=self.book_start, width=10).grid(row=1, column=1, padx=4)

        ttk.Label(form, text="Duration (hours)").grid(row=0, column=2, padx=4)
        self.book_duration = tk.StringVar(value="1")
        ttk.Entry(form, textvariable=self.book_duration, width=10).grid(row=1, column=2, padx=4)

        ttk.Button(form, text="Refresh Availability",
                   command=self.refresh_resource_availability).grid(row=1, column=3, padx=8)
        ttk.Button(form, text="Book Selected Resource",
                   command=self.create_booking).grid(row=1, column=4, padx=8)

        self.refresh_resource_availability()

    def refresh_resource_availability(self):
        if not hasattr(self, "resource_tree"):
            return
        self.book_policy_lbl.config(text=policy_text(self.current_campus()))
        for item in self.resource_tree.get_children():
            self.resource_tree.delete(item)

        date_s = self.book_date.get().strip()
        start_s = self.book_start.get().strip()
        dur_s = self.book_duration.get().strip()

        try:
            d = datetime.strptime(date_s, "%Y-%m-%d").date()
            datetime.strptime(start_s, "%H:%M")
            dur = int(dur_s)
            check_ok = d >= date.today() and dur > 0
        except ValueError:
            check_ok = False

        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, type FROM resources "
                    "WHERE campus_id=? ORDER BY code",
                    (campus_id(self.current_campus()),))
        resources = cur.fetchall()
        conn.close()

        for rid, code, name, typ in resources:
            status = "-"
            if check_ok:
                status = "Booked" if has_overlap(rid, date_s, start_s, dur) else "Available"
            self.resource_tree.insert("", "end", values=(code, name, typ, status))

    def create_booking(self):
        selected = self.resource_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Select a resource first.")
            return
        code = self.resource_tree.item(selected[0])["values"][0]
        date_s = self.book_date.get().strip()
        start_s = self.book_start.get().strip()
        dur_s = self.book_duration.get().strip()

        d, t, dur, err = parse_booking(date_s, start_s, dur_s)
        if err:
            messagebox.showerror("Invalid input", err)
            return
        ok, msg = validate_rules(self.current_campus(), d, t, dur)
        if not ok:
            messagebox.showerror("Booking rule", msg)
            return

        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM resources WHERE code=? AND campus_id=?",
                    (code, campus_id(self.current_campus())))
        row = cur.fetchone()
        conn.close()
        if not row:
            messagebox.showerror("Error", "Resource not found.")
            return
        resource_id = row[0]

        if has_overlap(resource_id, date_s, start_s, dur):
            messagebox.showerror("Unavailable",
                                 "This resource is already booked for that time.")
            return

        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT INTO bookings(resource_id, user_id, campus_id, "
                    "booking_date, start_time, duration, status) "
                    "VALUES(?,?,?,?,?,?,'Active')",
                    (resource_id, self.user.uid, campus_id(self.current_campus()),
                     date_s, start_s, dur))
        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Booking created successfully.")
        self.refresh_resource_availability()
        if hasattr(self, "my_bookings_tree"):
            self.refresh_my_bookings()

    def build_my_bookings_tab(self, frame):
        columns = ("id", "resource", "campus", "date", "start", "duration", "status")
        self.my_bookings_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        for col in columns:
            self.my_bookings_tree.heading(col, text=col.title())
            self.my_bookings_tree.column(col, width=140)
        self.my_bookings_tree.pack(fill="both", expand=True, padx=8, pady=8)

        btn = ttk.Frame(frame)
        btn.pack(fill="x", padx=8, pady=6)
        ttk.Button(btn, text="Refresh", command=self.refresh_my_bookings).pack(side="left", padx=4)
        ttk.Button(btn, text="Cancel Selected Booking",
                   command=self.cancel_my_booking).pack(side="left", padx=4)
        self.refresh_my_bookings()

    def refresh_my_bookings(self):
        if not hasattr(self, "my_bookings_tree"):
            return
        for item in self.my_bookings_tree.get_children():
            self.my_bookings_tree.delete(item)
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT b.id, r.code || ' - ' || r.name, c.name,
                              b.booking_date, b.start_time, b.duration, b.status
                       FROM bookings b
                       JOIN resources r ON b.resource_id = r.id
                       JOIN campuses c ON b.campus_id = c.id
                       WHERE b.user_id=?
                       ORDER BY b.booking_date DESC, b.start_time DESC""",
                    (self.user.uid,))
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            self.my_bookings_tree.insert("", "end", values=row)

    def cancel_my_booking(self):
        selected = self.my_bookings_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Select a booking first.")
            return
        booking_id = self.my_bookings_tree.item(selected[0])["values"][0]
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT user_id, booking_date, start_time, status "
                    "FROM bookings WHERE id=?", (booking_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            messagebox.showerror("Error", "Booking not found.")
            return
        uid, date_s, start_s, status = row
        if uid != self.user.uid:
            conn.close()
            messagebox.showerror("Error", "You can only cancel your own bookings.")
            return
        if status != "Active":
            conn.close()
            messagebox.showerror("Error", "Only active bookings can be cancelled.")
            return
        try:
            booking_dt = datetime.strptime(f"{date_s} {start_s}", "%Y-%m-%d %H:%M")
        except ValueError:
            conn.close()
            messagebox.showerror("Error", "Invalid booking date/time in database.")
            return
        if booking_dt <= datetime.now():
            conn.close()
            messagebox.showerror("Error", "Only future bookings can be cancelled.")
            return
        cur.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id,))
        conn.commit()
        conn.close()
        messagebox.showinfo("Cancelled", "Booking cancelled.")
        self.refresh_my_bookings()
        self.refresh_resource_availability()

    # ------------------- admin -------------------
    def build_admin_tabs(self):
        res_frame = ttk.Frame(self.notebook)
        self.notebook.add(res_frame, text="Manage Resources")
        self.build_manage_resources_tab(res_frame)

        avail_frame = ttk.Frame(self.notebook)
        self.notebook.add(avail_frame, text="Availability Monitor")
        self.build_availability_tab(avail_frame)

        bookings_frame = ttk.Frame(self.notebook)
        self.notebook.add(bookings_frame, text="Campus Bookings")
        self.build_campus_bookings_tab(bookings_frame)

        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Campus Reports")
        self.build_campus_reports_tab(reports_frame)

    def build_manage_resources_tab(self, frame):
        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=8)
        ttk.Label(form, text="Code").grid(row=0, column=0, padx=4)
        self.res_code = tk.StringVar()
        ttk.Entry(form, textvariable=self.res_code, width=15).grid(row=1, column=0, padx=4)
        ttk.Label(form, text="Name").grid(row=0, column=1, padx=4)
        self.res_name = tk.StringVar()
        ttk.Entry(form, textvariable=self.res_name, width=25).grid(row=1, column=1, padx=4)
        ttk.Label(form, text="Type").grid(row=0, column=2, padx=4)
        self.res_type = tk.StringVar()
        ttk.Entry(form, textvariable=self.res_type, width=20).grid(row=1, column=2, padx=4)
        ttk.Button(form, text="Add", command=self.add_resource).grid(row=1, column=3, padx=4)
        ttk.Button(form, text="Update Selected",
                   command=self.update_resource).grid(row=1, column=4, padx=4)
        ttk.Button(form, text="Delete Selected",
                   command=self.delete_resource).grid(row=1, column=5, padx=4)

        columns = ("id", "code", "name", "type")
        self.admin_resource_tree = ttk.Treeview(frame, columns=columns,
                                                show="headings", height=14)
        for col in columns:
            self.admin_resource_tree.heading(col, text=col.title())
            self.admin_resource_tree.column(col, width=180)
        self.admin_resource_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh_admin_resources()

    def refresh_admin_resources(self):
        if not hasattr(self, "admin_resource_tree"):
            return
        for item in self.admin_resource_tree.get_children():
            self.admin_resource_tree.delete(item)
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, type FROM resources "
                    "WHERE campus_id=? ORDER BY code",
                    (campus_id(self.current_campus()),))
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            self.admin_resource_tree.insert("", "end", values=row)

    def add_resource(self):
        code = self.res_code.get().strip()
        name = self.res_name.get().strip()
        typ = self.res_type.get().strip()
        if not code or not name or not typ:
            messagebox.showerror("Error", "Code, name and type are required.")
            return
        conn = db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO resources(code,name,type,campus_id) VALUES(?,?,?,?)",
                        (code, name, typ, campus_id(self.current_campus())))
            conn.commit()
            messagebox.showinfo("Success", "Resource added.")
            self.refresh_admin_resources()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "A resource with that code already exists.")
        finally:
            conn.close()

    def update_resource(self):
        selected = self.admin_resource_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Select a resource to update.")
            return
        rid = self.admin_resource_tree.item(selected[0])["values"][0]
        code = self.res_code.get().strip()
        name = self.res_name.get().strip()
        typ = self.res_type.get().strip()
        if not code or not name or not typ:
            messagebox.showerror("Error", "Code, name and type are required.")
            return
        conn = db()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE resources SET code=?, name=?, type=? "
                        "WHERE id=? AND campus_id=?",
                        (code, name, typ, rid, campus_id(self.current_campus())))
            conn.commit()
            messagebox.showinfo("Updated", "Resource updated.")
            self.refresh_admin_resources()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate", "That resource code is already used.")
        finally:
            conn.close()

    def delete_resource(self):
        selected = self.admin_resource_tree.selection()
        if not selected:
            messagebox.showerror("Error", "Select a resource to delete.")
            return
        rid = self.admin_resource_tree.item(selected[0])["values"][0]
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bookings WHERE resource_id=?", (rid,))
        count = cur.fetchone()[0]
        if count > 0:
            conn.close()
            messagebox.showerror("Error", "Cannot delete a resource that has bookings.")
            return
        cur.execute("DELETE FROM resources WHERE id=? AND campus_id=?",
                    (rid, campus_id(self.current_campus())))
        conn.commit()
        conn.close()
        messagebox.showinfo("Deleted", "Resource deleted.")
        self.refresh_admin_resources()

    def build_availability_tab(self, frame):
        self.avail_policy_lbl = ttk.Label(frame, text=policy_text(self.current_campus()),
                                          font=("Arial", 10, "bold"))
        self.avail_policy_lbl.pack(anchor="w", padx=8, pady=6)

        form = ttk.Frame(frame)
        form.pack(fill="x", padx=8, pady=6)
        ttk.Label(form, text="Date YYYY-MM-DD").grid(row=0, column=0, padx=4)
        self.avail_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form, textvariable=self.avail_date, width=14).grid(row=1, column=0, padx=4)
        ttk.Label(form, text="Start HH:MM").grid(row=0, column=1, padx=4)
        self.avail_start = tk.StringVar(value="09:00")
        ttk.Entry(form, textvariable=self.avail_start, width=10).grid(row=1, column=1, padx=4)
        ttk.Label(form, text="Duration (hours)").grid(row=0, column=2, padx=4)
        self.avail_dur = tk.StringVar(value="1")
        ttk.Entry(form, textvariable=self.avail_dur, width=10).grid(row=1, column=2, padx=4)
        ttk.Button(form, text="Check Availability",
                   command=self.refresh_availability_tab).grid(row=1, column=3, padx=8)

        columns = ("code", "name", "type", "status", "active_bookings")
        self.avail_tree = ttk.Treeview(frame, columns=columns, show="headings", height=13)
        for col in columns:
            self.avail_tree.heading(col, text=col.replace("_", " ").title())
            self.avail_tree.column(col, width=170)
        self.avail_tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh_availability_tab()

    def refresh_availability_tab(self):
        if not hasattr(self, "avail_tree"):
            return
        self.avail_policy_lbl.config(text=policy_text(self.current_campus()))
        for item in self.avail_tree.get_children():
            self.avail_tree.delete(item)

        date_s = self.avail_date.get().strip()
        start_s = self.avail_start.get().strip()
        dur_s = self.avail_dur.get().strip()
        try:
            datetime.strptime(date_s, "%Y-%m-%d")
            datetime.strptime(start_s, "%H:%M")
            valid_slot = int(dur_s) > 0
        except ValueError:
            valid_slot = False

        cid = campus_id(self.current_campus())
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, type FROM resources "
                    "WHERE campus_id=? ORDER BY code", (cid,))
        resources = cur.fetchall()
        cur.execute("SELECT resource_id FROM bookings "
                    "WHERE campus_id=? AND status='Active'", (cid,))
        counts = {}
        for (rid,) in cur.fetchall():
            counts[rid] = counts.get(rid, 0) + 1
        conn.close()

        booked_ids = set()
        if valid_slot:
            booked_ids = {rid for rid, *_ in resources
                          if has_overlap(rid, date_s, start_s, int(dur_s))}

        for rid, code, name, typ in resources:
            status = "-" if not valid_slot else ("Booked" if rid in booked_ids else "Available")
            self.avail_tree.insert("", "end",
                                   values=(code, name, typ, status, counts.get(rid, 0)))

    def build_campus_bookings_tab(self, frame):
        columns = ("id", "user", "resource", "date", "start", "duration", "status")
        self.campus_bookings_tree = ttk.Treeview(frame, columns=columns,
                                                 show="headings", height=15)
        for col in columns:
            self.campus_bookings_tree.heading(col, text=col.title())
            self.campus_bookings_tree.column(col, width=140)
        self.campus_bookings_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(frame, text="Refresh",
                   command=self.refresh_campus_bookings).pack(pady=6)
        self.refresh_campus_bookings()

    def refresh_campus_bookings(self):
        if not hasattr(self, "campus_bookings_tree"):
            return
        for item in self.campus_bookings_tree.get_children():
            self.campus_bookings_tree.delete(item)
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT b.id, u.username, r.code || ' - ' || r.name,
                              b.booking_date, b.start_time, b.duration, b.status
                       FROM bookings b
                       JOIN users u ON b.user_id = u.id
                       JOIN resources r ON b.resource_id = r.id
                       WHERE b.campus_id=?
                       ORDER BY b.booking_date DESC, b.start_time DESC""",
                    (campus_id(self.current_campus()),))
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            self.campus_bookings_tree.insert("", "end", values=row)

    def build_campus_reports_tab(self, frame):
        ttk.Button(frame, text="Generate Campus Report",
                   command=self.generate_campus_report).pack(pady=8)
        self.campus_report_text = tk.Text(frame, height=20, width=100)
        self.campus_report_text.pack(fill="both", expand=True, padx=8, pady=8)

    def generate_campus_report(self):
        cid = campus_id(self.current_campus())
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bookings WHERE campus_id=? AND status='Active'", (cid,))
        total = cur.fetchone()[0]
        cur.execute("SELECT AVG(duration) FROM bookings WHERE campus_id=? AND status='Active'", (cid,))
        avg = cur.fetchone()[0]
        cur.execute("""SELECT r.code, r.name, COUNT(*) AS uses
                       FROM bookings b JOIN resources r ON b.resource_id = r.id
                       WHERE b.campus_id=? AND b.status='Active'
                       GROUP BY r.id ORDER BY uses DESC LIMIT 5""", (cid,))
        most_used = cur.fetchall()
        conn.close()

        lines = [f"Campus Report: {self.current_campus()}", "=" * 45,
                 f"Total active bookings: {total}",
                 f"Average booking duration: {avg:.2f} hour(s)" if avg else
                 "Average booking duration: 0.00 hour(s)",
                 "", "Most frequently used resources:"]
        if most_used:
            for code, name, uses in most_used:
                lines.append(f"  - {code} / {name}: {uses} booking(s)")
        else:
            lines.append("  No bookings yet.")

        self.campus_report_text.delete("1.0", "end")
        self.campus_report_text.insert("end", "\n".join(lines))

    # ------------------- operator -------------------
    def build_operator_tabs(self):
        all_frame = ttk.Frame(self.notebook)
        self.notebook.add(all_frame, text="All Bookings")
        self.build_all_bookings_tab(all_frame)

        res_frame = ttk.Frame(self.notebook)
        self.notebook.add(res_frame, text="All Resources")
        self.build_all_resources_tab(res_frame)

        cross_frame = ttk.Frame(self.notebook)
        self.notebook.add(cross_frame, text="Cross-Campus Reports")
        self.build_cross_campus_reports_tab(cross_frame)

    def build_all_bookings_tab(self, frame):
        columns = ("id", "campus", "user", "resource", "date", "start", "duration", "status")
        self.all_bookings_tree = ttk.Treeview(frame, columns=columns,
                                              show="headings", height=15)
        for col in columns:
            self.all_bookings_tree.heading(col, text=col.title())
            self.all_bookings_tree.column(col, width=125)
        self.all_bookings_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(frame, text="Refresh",
                   command=self.refresh_all_bookings).pack(pady=6)
        self.refresh_all_bookings()

    def refresh_all_bookings(self):
        if not hasattr(self, "all_bookings_tree"):
            return
        for item in self.all_bookings_tree.get_children():
            self.all_bookings_tree.delete(item)
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT b.id, c.name, u.username, r.code || ' - ' || r.name,
                              b.booking_date, b.start_time, b.duration, b.status
                       FROM bookings b
                       JOIN campuses c ON b.campus_id = c.id
                       JOIN users u ON b.user_id = u.id
                       JOIN resources r ON b.resource_id = r.id
                       ORDER BY c.name, b.booking_date DESC, b.start_time DESC""")
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            self.all_bookings_tree.insert("", "end", values=row)

    def build_all_resources_tab(self, frame):
        columns = ("id", "campus", "code", "name", "type", "active_bookings")
        self.all_resources_tree = ttk.Treeview(frame, columns=columns,
                                               show="headings", height=15)
        for col in columns:
            self.all_resources_tree.heading(col, text=col.replace("_", " ").title())
            self.all_resources_tree.column(col, width=160)
        self.all_resources_tree.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Button(frame, text="Refresh",
                   command=self.refresh_all_resources).pack(pady=6)
        self.refresh_all_resources()

    def refresh_all_resources(self):
        if not hasattr(self, "all_resources_tree"):
            return
        for item in self.all_resources_tree.get_children():
            self.all_resources_tree.delete(item)
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT r.id, c.name, r.code, r.name, r.type,
                              COALESCE(SUM(CASE WHEN b.status='Active' THEN 1 ELSE 0 END), 0)
                       FROM resources r
                       JOIN campuses c ON r.campus_id = c.id
                       LEFT JOIN bookings b ON b.resource_id = r.id
                       GROUP BY r.id
                       ORDER BY c.name, r.code""")
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            self.all_resources_tree.insert("", "end", values=row)

    def build_cross_campus_reports_tab(self, frame):
        ttk.Button(frame, text="Generate Cross-Campus Comparison",
                   command=self.generate_cross_campus_report).pack(pady=8)
        self.cross_report_text = tk.Text(frame, height=20, width=100)
        self.cross_report_text.pack(fill="both", expand=True, padx=8, pady=8)

    def generate_cross_campus_report(self):
        lines = ["Cross-Campus Comparison", "=" * 60, ""]
        summary = []
        conn = db()
        cur = conn.cursor()
        for campus in CAMPUS_POLICIES:
            p = CAMPUS_POLICIES[campus]
            cid = campus_id(campus)
            cur.execute("SELECT COUNT(*), AVG(duration) FROM bookings "
                        "WHERE campus_id=? AND status='Active'", (cid,))
            total, avg = cur.fetchone()
            avg = avg or 0
            cur.execute("""SELECT r.code, r.name, COUNT(*) AS uses
                           FROM bookings b JOIN resources r ON b.resource_id = r.id
                           WHERE b.campus_id=? AND b.status='Active'
                           GROUP BY r.id ORDER BY uses DESC LIMIT 1""", (cid,))
            top = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM bookings "
                        "WHERE campus_id=? AND status='Active' AND duration=?",
                        (cid, p["max_duration"]))
            at_limit = cur.fetchone()[0]
            lines += [
                campus,
                f"  Policy in effect: max {p['max_duration']}h, "
                f"hours {p['open_hour']:02d}:00-{p['close_hour']:02d}:00",
                f"  Total active bookings: {total}",
                f"  Average duration: {avg:.2f}h (limit {p['max_duration']}h)",
                f"  Bookings at the campus maximum duration: {at_limit}",
                "  Most used resource: " + (f"{top[0]} / {top[1]} ({top[2]} booking(s))"
                                           if top else "none"),
                "",
            ]
            summary.append((campus, total, avg, at_limit))
        conn.close()

        if summary:
            busiest = max(summary, key=lambda s: s[1])
            longest = max(summary, key=lambda s: s[2])
            most_capped = max(summary, key=lambda s: s[3])
            lines += [
                "Trend comparison (effect of campus-specific rules):",
                f"  Busiest campus: {busiest[0]} ({busiest[1]} bookings)",
                f"  Longest average booking: {longest[0]} ({longest[2]:.2f}h)",
                f"  Most bookings hitting the policy cap: {most_capped[0]} ({most_capped[3]})",
            ]

        self.cross_report_text.delete("1.0", "end")
        self.cross_report_text.insert("end", "\n".join(lines))

    # ------------------- refresh -------------------
    def refresh_all(self):
        try:
            if hasattr(self, "resource_tree"):
                self.refresh_resource_availability()
            if hasattr(self, "my_bookings_tree"):
                self.refresh_my_bookings()
            if hasattr(self, "admin_resource_tree"):
                self.refresh_admin_resources()
            if hasattr(self, "avail_tree"):
                self.refresh_availability_tab()
            if hasattr(self, "campus_bookings_tree"):
                self.refresh_campus_bookings()
            if hasattr(self, "all_bookings_tree"):
                self.refresh_all_bookings()
            if hasattr(self, "all_resources_tree"):
                self.refresh_all_resources()
        except tk.TclError:
            pass


if __name__ == "__main__":
    init_db()
    App().mainloop()

