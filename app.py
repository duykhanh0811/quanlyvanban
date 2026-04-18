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
        role TEXT
    )
    """)

    # thêm cột nếu thiếu
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS lecturer_id TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS department TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS position TEXT")

    # REPORTS
    cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    sender TEXT,
    content TEXT,
    reply TEXT,
    status TEXT,
    created_at TEXT
)
""")

    # DOCUMENTS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY
    )
    """)

    # thêm cột nếu thiếu
    columns = [
        "code TEXT",
        "number TEXT",
        "title TEXT",
        "field TEXT",
        "agency TEXT",
        "doc_type TEXT",
        "created_at TEXT",
        "effective_date TEXT",
        "urgency TEXT",
        "security TEXT",
        "filename TEXT",
        "sender TEXT",
        "status TEXT",
        "current_handler TEXT"
    ]

    for col in columns:
        name = col.split()[0]
        cur.execute(f"ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col}")

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
            session["department"] = result.get("department", "")
            session["position"] = result.get("position", "")
            return redirect("/dashboard")
        else:
            error = "Sai tài khoản hoặc mật khẩu!"

    return render_template("login.html", error=error)

@app.route("/admin/add_user", methods=["GET","POST"])
def add_user():
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    if request.method == "POST":
        db = get_db()
        cur = db.cursor()

        cur.execute("""
INSERT INTO users (username, password, role, full_name, lecturer_id, department, position)
VALUES (%s,%s,%s,%s,%s,%s,%s)
""", (
    request.form["username"],
    request.form["password"],
    request.form["role"],
    request.form.get("full_name"),
    request.form.get("lecturer_id"),
    request.form.get("department"),
    request.form.get("position")
))


        db.commit()
        cur.close()
        db.close()

        return "Tạo tài khoản thành công!"

    return render_template("add_user.html")

@app.route("/create", methods=["GET","POST"])
def create_doc():
    if "user" not in session:
        return redirect("/")

    if request.method == "POST":
        db = get_db()
        cur = db.cursor()

        file = request.files.get("file")

        filename = ""
        if file:
            filename = file.filename
            file.save(os.path.join(UPLOAD_FOLDER, filename))

        cur.execute("""
        INSERT INTO documents
        (code, number, title, field, agency, doc_type,
         created_at, effective_date, urgency, security,
         filename, sender, status, current_handler)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["code"],
            request.form["number"],
            request.form["title"],
            request.form["field"],
            request.form["agency"],
            request.form["doc_type"],
            request.form["created_at"],
            request.form["effective_date"],
            request.form["urgency"],
            request.form["security"],
            filename,
            session["user"],
            "Chờ văn thư",
            "staff"
        ))

        db.commit()
        cur.close()
        db.close()

        return redirect("/library")

    return render_template("create.html")

@app.route("/library")
def library():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    search = request.args.get("search", "")

    try:
        if search:
            cur.execute("""
                SELECT * FROM documents
                WHERE 
                    title ILIKE %s OR 
                    doc_type ILIKE %s OR
                    COALESCE(code,'') ILIKE %s OR
                    COALESCE(number,'') ILIKE %s OR
                    COALESCE(agency,'') ILIKE %s
                ORDER BY id DESC
            """, (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            ))
        else:
            cur.execute("SELECT * FROM documents ORDER BY id DESC")

        docs = cur.fetchall()

    except Exception as e:
        return f"Lỗi search: {e}"   # 🔥 HIỆN LỖI THẬT

    cur.close()
    db.close()

    return render_template("library.html", docs=docs, search=search)
# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    role = session["role"]
    user = session["user"]

    try:
        if role == "lecturer":
            cur.execute("SELECT * FROM documents WHERE sender=%s", (user,))
            docs = cur.fetchall()
        elif role == "staff":
            cur.execute("SELECT * FROM documents WHERE current_handler='staff'")
            docs = cur.fetchall()
        else:
            cur.execute("SELECT * FROM documents")
            docs = cur.fetchall()

        cur.execute("""
            SELECT * FROM documents 
            WHERE status IN ('Đã duyệt','Từ chối','Đã duyệt (văn thư)')
        """)
        done_docs = cur.fetchall()

    except Exception as e:
        return f"Lỗi dashboard: {e}"

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
(code, number, title, field, agency, doc_type,
 created_at, effective_date, urgency, security,
 filename, sender, status, current_handler)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", (
    "",  # code
    "",  # number
    title,
    "",  # field
    "",  # agency
    doc_type,
    datetime.now().strftime("%d/%m/%Y %H:%M"),
    "",  # effective_date
    "",  # urgency
    "",  # security
    filename,
    session["user"],
    "Chờ văn thư",
    "staff"
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

@app.route("/admin/reports")
def view_reports():
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT * FROM reports ORDER BY id DESC")
    reports = cur.fetchall()

    cur.close()
    db.close()

    return render_template("reports.html", reports=reports)

@app.route("/reply/<int:id>", methods=["POST"])
def reply(id):
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    UPDATE reports 
    SET reply=%s, status='Đã phản hồi'
    WHERE id=%s
    """, (
        request.form["reply"],
        id
    ))

    db.commit()
    cur.close()
    db.close()

    return redirect("/admin/reports")

@app.route("/admin/users")
def manage_users():
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT * FROM users ORDER BY id DESC")
    users = cur.fetchall()

    cur.close()
    db.close()

    return render_template("users.html", users=users)

@app.route("/admin/edit_user/<int:id>", methods=["GET","POST"])
def edit_user(id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    if request.method == "POST":
        cur.execute("""
        UPDATE users 
        SET username=%s, role=%s, department=%s, position=%s
        WHERE id=%s
        """, (
            request.form["username"],
            request.form["role"],
            request.form["department"],
            request.form["position"],
            id
        ))
        db.commit()
        return redirect("/admin/users")

    cur.execute("SELECT * FROM users WHERE id=%s", (id,))
    user_data = cur.fetchone()

    cur.close()
    db.close()

    return render_template("edit_user.html", u=user_data)

@app.route("/admin/delete_user/<int:id>")
def delete_user(id):
    if "user" not in session or session["role"] != "admin":
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    cur.execute("DELETE FROM users WHERE id=%s", (id,))
    db.commit()

    cur.close()
    db.close()

    return redirect("/admin/users")

# ================= FILE =================
@app.route("/file/<name>")
def file(name):
    path = os.path.join(UPLOAD_FOLDER, name)

    if not name or not os.path.exists(path):
        return "File không tồn tại!"

    return send_from_directory(UPLOAD_FOLDER, name)

@app.route("/report", methods=["POST"])
def report():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()

    cur.execute("""
    INSERT INTO reports (sender, content, status, created_at)
    VALUES (%s,%s,%s,%s)
    """, (
        session["user"],
        request.form["content"],
        "Chờ xử lý",
        datetime.now().strftime("%d/%m/%Y %H:%M")
    ))

    db.commit()
    cur.close()
    db.close()

    return redirect("/dashboard")

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