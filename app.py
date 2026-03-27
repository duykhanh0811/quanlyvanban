from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "123"

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ================= DATABASE =================
def get_db():
    return psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor,
        sslmode='require'
    )

def init_db():
    db = get_db()
    cur = db.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        student_id TEXT,
        class TEXT
    )
    """)

    # DOCUMENTS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        title TEXT,
        filename TEXT,
        status TEXT,
        sender TEXT,
        receiver TEXT,
        current_handler TEXT,
        doc_type TEXT,
        created_at TEXT,
        target_class TEXT
    )
    """)

    db.commit()
    cur.close()
    db.close()

init_db()

# tạo admin
def create_admin():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT * FROM users WHERE role='admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
            ('admin', '123', 'admin')
        )
        db.commit()

    cur.close()
    db.close()

create_admin()

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]

        db = get_db()
        cur = db.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (user, pw)
        )

        result = cur.fetchone()
        cur.close()
        db.close()

        if result:
            session["user"] = user
            session["role"] = result["role"]
            session["class"] = result["class"]
            return redirect("/dashboard")
        else:
            error = "Sai tài khoản hoặc mật khẩu!"

    return render_template("login.html", error=error)

# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor()

        user = request.form["username"]
        pw = request.form["password"]
        role = request.form["role"]

        cur.execute("SELECT * FROM users WHERE username=%s", (user,))
        if cur.fetchone():
            return "Tài khoản đã tồn tại"

        if role == "admin":
            return "Không được tạo admin"

        cur.execute("""
        INSERT INTO users (username, password, role, student_id, class)
        VALUES (%s,%s,%s,%s,%s)
        """, (
            user, pw, role,
            request.form.get("student_id"),
            request.form.get("class")
        ))

        db.commit()
        cur.close()
        db.close()

        return redirect("/")

    return render_template("register.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    role = session["role"]
    user = session["user"]

    # SINH VIÊN
    if role == "student":
        cur.execute("SELECT * FROM documents WHERE sender=%s", (user,))
        docs = cur.fetchall()

    # VĂN THƯ
    elif role == "staff":
        cur.execute("SELECT * FROM documents WHERE current_handler='staff'")
        docs = cur.fetchall()

    # ADMIN
    else:
        cur.execute("SELECT * FROM documents")
        docs = cur.fetchall()

    cur.execute("""
        SELECT * FROM documents 
        WHERE status IN ('Đã duyệt','Từ chối','Đã duyệt (văn thư)')
    """)
    done_docs = cur.fetchall()

    cur.close()
    db.close()

    return render_template("dashboard.html", docs=docs, done_docs=done_docs, role=role)

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    title = request.form["title"]
    doc_type = request.form["doc_type"]

    if file and "user" in session:
        filename = file.filename
        file.save(os.path.join(UPLOAD_FOLDER, filename))

        db = get_db()
        cur = db.cursor()

        cur.execute("""
        INSERT INTO documents 
        (title, filename, status, sender, current_handler, doc_type, created_at, target_class)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            title,
            filename,
            "Chờ văn thư",
            session["user"],
            "staff",
            doc_type,
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            session.get("class")
        ))

        db.commit()
        cur.close()
        db.close()

    return redirect("/dashboard")

# ================= STAFF =================
@app.route("/staff_approve/<int:id>")
def staff_approve(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("UPDATE documents SET status='Đã duyệt (văn thư)', current_handler='done' WHERE id=%s", (id,))
    db.commit()

    cur.close()
    db.close()
    return redirect("/dashboard")

@app.route("/to_leader/<int:id>")
def to_leader(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("UPDATE documents SET status='Chờ lãnh đạo', current_handler='admin' WHERE id=%s", (id,))
    db.commit()

    cur.close()
    db.close()
    return redirect("/dashboard")

# ================= ADMIN =================
@app.route("/approve/<int:id>")
def approve(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("UPDATE documents SET status='Đã duyệt', current_handler='done' WHERE id=%s", (id,))
    db.commit()

    cur.close()
    db.close()
    return redirect("/dashboard")

@app.route("/reject/<int:id>")
def reject(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("UPDATE documents SET status='Từ chối', current_handler='done' WHERE id=%s", (id,))
    db.commit()

    cur.close()
    db.close()
    return redirect("/dashboard")

# ================= FILE =================
@app.route("/file/<name>")
def file(name):
    return send_from_directory(UPLOAD_FOLDER, name)

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/stats")
def stats():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    # Tổng văn bản
    cur.execute("SELECT COUNT(*) FROM documents")
    total = cur.fetchone()["count"]

    # Đã xử lý (đã duyệt + từ chối)
    cur.execute("""
        SELECT COUNT(*) FROM documents 
        WHERE status IN ('Đã duyệt','Từ chối','Đã duyệt (văn thư)')
    """)
    done = cur.fetchone()["count"]

    # Đang chờ
    cur.execute("""
        SELECT COUNT(*) FROM documents 
        WHERE status NOT IN ('Đã duyệt','Từ chối','Đã duyệt (văn thư)')
    """)
    pending = cur.fetchone()["count"]

    # Từ chối
    cur.execute("SELECT COUNT(*) FROM documents WHERE status='Từ chối'")
    reject = cur.fetchone()["count"]

    # 5 văn bản gần nhất
    cur.execute("""
        SELECT * FROM documents 
        ORDER BY id DESC 
        LIMIT 5
    """)
    recent = cur.fetchall()

    cur.close()
    db.close()

    return render_template(
        "stats.html",
        total=total,
        done=done,
        pending=pending,
        reject=reject,
        recent=recent
    )
# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)