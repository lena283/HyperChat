from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import random
import string
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "hyperchat_secret_key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "hyperchat.db")


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
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS friends(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_code TEXT,
        friend_code TEXT
    )
    """)

    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]

    if "password_hash" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

    if "nickname" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN nickname TEXT")

    if "hx_code" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN hx_code TEXT")

    if "bio" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")

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


def get_user(hx_code):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT nickname, hx_code, bio FROM users WHERE hx_code=?", (hx_code,))
    user = cur.fetchone()
    conn.close()
    return user


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
            return render_template("register.html", error="Введите ник и пароль")

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE nickname=?", (nickname,))
        exists = cur.fetchone()
        if exists:
            conn.close()
            return render_template("register.html", error="Такой ник уже занят")

        hx_code = generate_hx()
        password_hash = generate_password_hash(password)

        cur.execute(
            """
            INSERT INTO users(nickname, password_hash, hx_code)
            VALUES(?,?,?)
            """,
            (nickname, password_hash, hx_code)
        )

        conn.commit()
        conn.close()

        session["hx_code"] = hx_code
        return redirect("/friends")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nickname = request.form["nickname"].strip()
        password = request.form["password"].strip()

        user = get_user_by_nickname(nickname)
        if not user:
            return render_template("login.html", error="Неверный ник или пароль")

        db_nickname, db_password_hash, db_hx_code, db_bio = user

        if not db_password_hash or not check_password_hash(db_password_hash, password):
            return render_template("login.html", error="Неверный ник или пароль")

        session["hx_code"] = db_hx_code
        return redirect("/friends")

    return render_template("login.html")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "hx_code" not in session:
        return redirect("/login")

    hx_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if request.method == "POST":
        bio = request.form["bio"]
        cur.execute(
            """
            UPDATE users
            SET bio=?
            WHERE hx_code=?
            """,
            (bio, hx_code)
        )
        conn.commit()

    cur.execute(
        """
        SELECT nickname, hx_code, bio
        FROM users
        WHERE hx_code=?
        """,
        (hx_code,)
    )
    user = cur.fetchone()
    conn.close()

    return render_template("profile.html", user=user)


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
    user = cur.fetchone()

    if not user:
        conn.close()
        return redirect("/friends")

    cur.execute(
        """
        SELECT id
        FROM friends
        WHERE owner_code=?
        AND friend_code=?
        """,
        (owner, friend_code)
    )
    exists = cur.fetchone()

    if not exists:
        cur.execute(
            "INSERT INTO friends(owner_code, friend_code) VALUES(?,?)",
            (owner, friend_code)
        )
        cur.execute(
            "INSERT INTO friends(owner_code, friend_code) VALUES(?,?)",
            (friend_code, owner)
        )
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

    cur.execute(
        """
        SELECT friend_code
        FROM friends
        WHERE owner_code=?
        """,
        (hx_code,)
    )

    rows = cur.fetchall()
    friend_list = []

    for row in rows:
        cur.execute(
            """
            SELECT nickname, hx_code
            FROM users
            WHERE hx_code=?
            """,
            (row[0],)
        )
        friend = cur.fetchone()
        if friend:
            friend_list.append(friend)

    conn.close()
    return render_template("friends.html", friends=friend_list)


@app.route("/delete_friend/<friend_code>")
def delete_friend(friend_code):
    if "hx_code" not in session:
        return redirect("/login")

    owner = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM friends
        WHERE owner_code=?
        AND friend_code=?
        """,
        (owner, friend_code)
    )

    conn.commit()
    conn.close()
    return redirect("/friends")


@app.route("/messages/<friend_code>")
def get_messages(friend_code):
    if "hx_code" not in session:
        return jsonify([])

    my_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT sender_code, message, created
        FROM messages
        WHERE
        (sender_code=? AND receiver_code=?)
        OR
        (sender_code=? AND receiver_code=?)
        ORDER BY id
    """,
    (
        my_code,
        friend_code,
        friend_code,
        my_code
    ))

    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {
            "sender": row[0],
            "text": row[1],
            "created": row[2]
        }
        for row in rows
    ])


@app.route("/send_ajax", methods=["POST"])
def send_ajax():
    if "hx_code" not in session:
        return jsonify({"ok": False})

    data = request.get_json()
    friend_code = data["friend"]
    message = data["message"].strip()
    my_code = session["hx_code"]

    if not message:
        return jsonify({"ok": False})

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO messages(sender_code, receiver_code, message)
        VALUES(?,?,?)
        """,
        (my_code, friend_code, message)
    )

    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)