from flask import Flask, render_template, request, redirect, session, send_from_directory, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "123"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= DB =================
def get_db():
    conn = sqlite3.connect("database_new.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()

    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT,
        student_id TEXT,
        class TEXT,
        department_id TEXT,
        position TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        filename TEXT,
        status TEXT,
        sender TEXT,
        current_handler TEXT,
        doc_type TEXT,
        created_at TEXT
    )""")

    db.commit()

init_db()

def create_admin():
    db = get_db()
    check = db.execute("SELECT * FROM users WHERE role='admin'").fetchone()
    if not check:
        db.execute("INSERT INTO users (username, password, role) VALUES ('admin','123','admin')")
        db.commit()

create_admin()

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        db = get_db()
        result = db.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (user, pw)
        ).fetchone()

        if result:
            session["user"] = user
            session["role"] = result["role"]
            return redirect(url_for("dashboard"))

    return render_template("login.html")

# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]
        role = request.form["role"]

        db = get_db()
        check = db.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()

        if check:
            return "Tài khoản đã tồn tại!"

        if role == "admin":
            return "Không được tạo tài khoản lãnh đạo!"

        db.execute("""
        INSERT INTO users (username, password, role, student_id, class, department_id, position)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user, pw, role,
            request.form.get("student_id"),
            request.form.get("class"),
            request.form.get("department_id"),
            request.form.get("position")
        ))

        db.commit()
        return redirect(url_for("login"))

    return render_template("register.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    db = get_db()
    role = session["role"]
    user = session["user"]

    if role == "student":
        docs = db.execute("SELECT * FROM documents WHERE sender=?", (user,)).fetchall()
    else:
        docs = db.execute("SELECT * FROM documents WHERE current_handler=?", (role,)).fetchall()

    done_docs = db.execute("SELECT * FROM documents WHERE status IN ('Đã duyệt','Từ chối')").fetchall()

    return render_template("dashboard.html", docs=docs, done_docs=done_docs, role=role)

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    title = request.form["title"]
    doc_type = request.form["doc_type"]

    if file and "user" in session:
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))

        db = get_db()
        db.execute("""
        INSERT INTO documents (title, filename, status, sender, current_handler, doc_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            file.filename,
            "Chờ văn thư",
            session["user"],
            "staff",
            doc_type,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        db.commit()

    return redirect(url_for("dashboard"))

# ================= VĂN THƯ =================
@app.route("/staff_approve/<int:id>")
def staff_approve(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Đã duyệt', current_handler='done' WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("dashboard"))

@app.route("/to_leader/<int:id>")
def to_leader(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Chờ lãnh đạo', current_handler='admin' WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("dashboard"))

# ================= LÃNH ĐẠO =================
@app.route("/approve/<int:id>")
def approve(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Đã duyệt', current_handler='done' WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("dashboard"))

@app.route("/reject/<int:id>")
def reject(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Từ chối', current_handler='done' WHERE id=?", (id,))
    db.commit()
    return redirect(url_for("dashboard"))

# ================= FILE =================
@app.route("/file/<name>")
def download_file(name):
    return send_from_directory(UPLOAD_FOLDER, name)

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)