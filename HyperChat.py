from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import random
import string
import os
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "hyperchat_secret_key"
app.permanent_session_lifetime = timedelta(days=30)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "hyperchat.db")

BOT_CODE = "HX-000000"
BOT_NICK = "HyperBot"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT UNIQUE,
        password_hash TEXT,
        hx_code TEXT UNIQUE,
        bio TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_code TEXT,
        receiver_code TEXT,
        message TEXT,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        msg_type TEXT DEFAULT 'text',
        audio_path TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS friends(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_code TEXT,
        friend_code TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_code TEXT,
        from_code TEXT,
        message_id INTEGER,
        is_read INTEGER DEFAULT 0,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cur.fetchall()]
    if "password_hash" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "nickname" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN nickname TEXT")
    if "hx_code" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN hx_code TEXT")
    if "bio" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")

    cur.execute("PRAGMA table_info(messages)")
    msg_cols = [row[1] for row in cur.fetchall()]
    if "msg_type" not in msg_cols:
        cur.execute("ALTER TABLE messages ADD COLUMN msg_type TEXT DEFAULT 'text'")
    if "audio_path" not in msg_cols:
        cur.execute("ALTER TABLE messages ADD COLUMN audio_path TEXT DEFAULT ''")

    cur.execute("SELECT id FROM users WHERE hx_code=?", (BOT_CODE,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(nickname, password_hash, hx_code, bio) VALUES(?,?,?,?)",
            (BOT_NICK, "", BOT_CODE, "I am your test bot.")
        )

    conn.commit()
    conn.close()


init_db()


def generate_hx():
    while True:
        hx = "HX-" + "".join(random.choices(string.digits, k=6))
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE hx_code=?", (hx,))
        exists = cur.fetchone()
        conn.close()
        if not exists:
            return hx


def get_user_by_nickname(nickname):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT nickname, password_hash, hx_code, bio FROM users WHERE nickname=?",
        (nickname,)
    )
    user = cur.fetchone()
    conn.close()
    return user


def current_theme():
    return session.get("theme", "dark")


def current_language():
    return session.get("language", "ru")


@app.route("/")
def home():
    if "hx_code" not in session:
        return redirect("/login")
    return redirect("/friends")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nickname = request.form["nickname"].strip()
        password = request.form["password"].strip()

        if not nickname or not password:
            return render_template("register.html", error="Введите ник и пароль", theme=current_theme(), language=current_language())

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE nickname=?", (nickname,))
        if cur.fetchone():
            conn.close()
            return render_template("register.html", error="Такой ник уже занят", theme=current_theme(), language=current_language())

        hx_code = generate_hx()
        password_hash = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users(nickname, password_hash, hx_code) VALUES(?,?,?)",
            (nickname, password_hash, hx_code)
        )
        conn.commit()
        conn.close()

        session["hx_code"] = hx_code
        session.permanent = True
        return redirect("/friends")

    return render_template("register.html", theme=current_theme(), language=current_language())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nickname = request.form["nickname"].strip()
        password = request.form["password"].strip()
        remember = request.form.get("remember") == "on"

        user = get_user_by_nickname(nickname)
        if not user:
            return render_template("login.html", error="Неверный ник или пароль", theme=current_theme(), language=current_language())

        _, db_password_hash, db_hx_code, _ = user
        if not db_password_hash or not check_password_hash(db_password_hash, password):
            return render_template("login.html", error="Неверный ник или пароль", theme=current_theme(), language=current_language())

        session["hx_code"] = db_hx_code
        session.permanent = remember
        return redirect("/friends")

    return render_template("login.html", theme=current_theme(), language=current_language())


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "hx_code" not in session:
        return redirect("/login")

    if request.method == "POST":
        session["theme"] = request.form.get("theme", "dark")
        session["language"] = request.form.get("language", "ru")
        return redirect("/settings")

    return render_template(
        "settings.html",
        theme=current_theme(),
        language=current_language()
    )


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "hx_code" not in session:
        return redirect("/login")

    hx_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if request.method == "POST":
        bio = request.form["bio"]
        cur.execute("UPDATE users SET bio=? WHERE hx_code=?", (bio, hx_code))
        conn.commit()

    cur.execute("SELECT nickname, hx_code, bio FROM users WHERE hx_code=?", (hx_code,))
    user = cur.fetchone()
    conn.close()

    return render_template("profile.html", user=user, theme=current_theme(), language=current_language())


@app.route("/api/user/<hx_code>")
def api_user(hx_code):
    if "hx_code" not in session:
        return jsonify({"ok": False})

    hx_code = hx_code.strip().upper()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nickname, hx_code, bio FROM users WHERE hx_code=?", (hx_code,))
    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"ok": False})

    return jsonify({
        "ok": True,
        "nickname": user[0],
        "hx_code": user[1],
        "bio": user[2] or ""
    })


@app.route("/add_friend", methods=["POST"])
def add_friend():
    if "hx_code" not in session:
        return redirect("/login")

    owner = session["hx_code"]
    friend_code = request.form.get("friend_code", "").strip().upper()

    if not friend_code or friend_code == owner:
        return redirect("/friends")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT hx_code FROM users WHERE hx_code=?", (friend_code,))
    if not cur.fetchone():
        conn.close()
        return redirect("/friends")

    cur.execute("SELECT id FROM friends WHERE owner_code=? AND friend_code=?", (owner, friend_code))
    if not cur.fetchone():
        cur.execute("INSERT INTO friends(owner_code, friend_code) VALUES(?,?)", (owner, friend_code))
        cur.execute("INSERT INTO friends(owner_code, friend_code) VALUES(?,?)", (friend_code, owner))
        conn.commit()

    conn.close()
    return redirect("/friends")


@app.route("/friends")
def friends():
    if "hx_code" not in session:
        return redirect("/login")

    hx_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT friend_code FROM friends WHERE owner_code=?", (hx_code,))
    rows = cur.fetchall()

    friend_list = []
    for row in rows:
        friend_code = row[0]
        cur.execute("SELECT nickname, hx_code FROM users WHERE hx_code=?", (friend_code,))
        friend = cur.fetchone()
        if friend:
            cur.execute("""
                SELECT COUNT(*)
                FROM notifications
                WHERE user_code=? AND from_code=? AND is_read=0
            """, (hx_code, friend_code))
            unread = cur.fetchone()[0]
            friend_list.append((friend[0], friend[1], unread))

    conn.close()
    return render_template("friends.html", friends=friend_list, theme=current_theme(), language=current_language())


@app.route("/send_ajax", methods=["POST"])
def send_ajax():
    if "hx_code" not in session:
        return jsonify({"ok": False})

    data = request.get_json(silent=True) or {}
    friend_code = str(data.get("friend", "")).strip().upper()
    message = str(data.get("message", "")).strip()
    my_code = session["hx_code"]

    if not friend_code or not message:
        return jsonify({"ok": False})

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages(sender_code, receiver_code, message, msg_type, audio_path) VALUES(?,?,?,?,?)",
        (my_code, friend_code, message, "text", "")
    )
    message_id = cur.lastrowid

    cur.execute(
        "INSERT INTO notifications(user_code, from_code, message_id) VALUES(?,?,?)",
        (friend_code, my_code, message_id)
    )

    if friend_code == BOT_CODE:
        low = message.lower()
        reply = "Сообщение получено."
        if "привет" in low or "hello" in low:
            reply = "Привет! Я HyperBot."
        elif "как дела" in low:
            reply = "У меня всё отлично. Чат работает."

        cur.execute(
            "INSERT INTO messages(sender_code, receiver_code, message, msg_type, audio_path) VALUES(?,?,?,?,?)",
            (BOT_CODE, my_code, reply, "text", "")
        )
        bot_message_id = cur.lastrowid
        cur.execute(
            "INSERT INTO notifications(user_code, from_code, message_id) VALUES(?,?,?)",
            (my_code, BOT_CODE, bot_message_id)
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/messages/<friend_code>")
def get_messages(friend_code):
    if "hx_code" not in session:
        return jsonify([])

    my_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT sender_code, message, msg_type, audio_path
        FROM messages
        WHERE
        (sender_code=? AND receiver_code=?)
        OR
        (sender_code=? AND receiver_code=?)
        ORDER BY id
    """, (my_code, friend_code, friend_code, my_code))
    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {"sender": r[0], "text": r[1], "type": r[2], "audio": r[3]}
        for r in rows
    ])


@app.route("/notifications_count")
def notifications_count():
    if "hx_code" not in session:
        return jsonify({"count": 0})

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_code=? AND is_read=0",
        (session["hx_code"],)
    )
    count = cur.fetchone()[0]
    conn.close()
    return jsonify({"count": count})


@app.route("/notifications_list")
def notifications_list():
    if "hx_code" not in session:
        return jsonify([])

    user_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT n.id, n.from_code, u.nickname, m.message, n.created, n.is_read
        FROM notifications n
        JOIN messages m ON m.id = n.message_id
        LEFT JOIN users u ON u.hx_code = n.from_code
        WHERE n.user_code=?
        ORDER BY n.id DESC
        LIMIT 10
    """, (user_code,))

    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "from_code": r[1],
            "from_name": r[2] if r[2] else r[1],
            "message": r[3],
            "created": r[4],
            "is_read": r[5]
        }
        for r in rows
    ])


@app.route("/mark_notifications_read", methods=["POST"])
def mark_notifications_read():
    if "hx_code" not in session:
        return jsonify({"ok": False})

    data = request.get_json(silent=True) or {}
    from_code = str(data.get("from_code", "")).strip().upper()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE notifications SET is_read=1 WHERE user_code=? AND from_code=? AND is_read=0",
        (session["hx_code"], from_code)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/mark_notification_read", methods=["POST"])
def mark_notification_read():
    if "hx_code" not in session:
        return jsonify({"ok": False})

    data = request.get_json(silent=True) or {}
    notif_id = data.get("id")
    if not notif_id:
        return jsonify({"ok": False})

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE notifications SET is_read=1 WHERE id=? AND user_code=?",
        (notif_id, session["hx_code"])
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/logout")
def logout():
    theme = session.get("theme", "dark")
    language = session.get("language", "ru")
    session.clear()
    session["theme"] = theme
    session["language"] = language
    session.permanent = False
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)