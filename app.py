from flask import Flask, render_template, request, redirect, session, send_from_directory
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "123"

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db():
    return sqlite3.connect("database.db")

def init_db():
    db = get_db()

    # bảng users
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT,
        role TEXT,
        student_id TEXT,
        class TEXT,
        department_id TEXT,
        position TEXT
    )""")

    # 👇 DÁN Ở ĐÂY
    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        title TEXT,
        filename TEXT,
        status TEXT,
        sender TEXT,
        current_handler TEXT,
        type TEXT
    )""")

    db.commit()

    db.execute("""CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        title TEXT,
        filename TEXT,
        status TEXT,
        sender TEXT,
        current_handler TEXT
    )""")

    db.commit()

init_db()
def create_admin():
    db = get_db()

    check = db.execute("SELECT * FROM users WHERE role='admin'").fetchone()

    if not check:
        db.execute("""
        INSERT INTO users 
        VALUES (NULL,'admin','123','admin',NULL,NULL,NULL,NULL)
        """)
        db.commit()

create_admin()
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
            session["role"] = result[3]
            return redirect("/dashboard")

    return render_template("login.html")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]
        role = request.form["role"]

        student_id = request.form.get("student_id")
        class_name = request.form.get("class")
        department_id = request.form.get("department_id")
        position = request.form.get("position")

        db = get_db()

        check = db.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
        if check:
            return "Tài khoản đã tồn tại!"

        # ❗ Không cho tạo admin
        if role == "admin":
            return "Không được tạo tài khoản lãnh đạo!"

        db.execute("""INSERT INTO users 
        VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)""",
        (user, pw, role, student_id, class_name, department_id, position))

        db.commit()
        return redirect("/")

    return render_template("register.html")
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    title = request.form["title"]

    if file:
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))

        db = get_db()
        db.execute("""INSERT INTO documents 
            VALUES (NULL, ?, ?, ?, ?, ?)""",
            (title, file.filename, "Chờ văn thư", session["user"], "staff"))
        db.commit()

    return redirect("/dashboard")
@app.route("/to_leader/<int:id>")
def to_leader(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Chờ lãnh đạo', current_handler='admin' WHERE id=?", (id,))
    db.commit()
    return redirect("/dashboard")

@app.route("/approve/<int:id>")
def approve(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Đã duyệt', current_handler='done' WHERE id=?", (id,))
    db.commit()
    return redirect("/dashboard")

@app.route("/reject/<int:id>")
def reject(id):
    db = get_db()
    db.execute("UPDATE documents SET status='Từ chối', current_handler='done' WHERE id=?", (id,))
    db.commit()
    return redirect("/dashboard")
@app.route("/file/<name>")
def file(name):
    return send_from_directory(UPLOAD_FOLDER, name)
@app.route("/dashboard")
def dashboard():
    db = get_db()

    role = session.get("role")
    user = session.get("user")

    if role == "student":
        docs = db.execute("SELECT * FROM documents WHERE sender=?", (user,)).fetchall()
    else:
        docs = db.execute("SELECT * FROM documents WHERE current_handler=?", (role,)).fetchall()

    done_docs = db.execute("SELECT * FROM documents WHERE current_handler='done'").fetchall()

    return render_template("dashboard.html", docs=docs, done_docs=done_docs, role=role)
if __name__ == "__main__":
    app.run()