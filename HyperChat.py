from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import random
import string
import os

app = Flask(__name__)
app.secret_key = "hyperchat_secret_key"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "hyperchat.db")


# ==========================================
# DATABASE
# ==========================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT,
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

    conn.commit()
    conn.close()


init_db()


# ==========================================
# HELPERS
# ==========================================

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
    cur.execute("SELECT nickname,hx_code,bio FROM users WHERE hx_code=?", (hx_code,))
    user = cur.fetchone()
    conn.close()
    return user


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    if "hx_code" not in session:
        return redirect("/register")
    return redirect("/profile")


# ==========================================
# REGISTER
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nickname = request.form["nickname"]
        hx_code = generate_hx()

        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users(
                nickname,
                hx_code
            )
            VALUES(?,?)
            """,
            (nickname, hx_code)
        )
        conn.commit()
        conn.close()

        session["hx_code"] = hx_code
        return redirect("/profile")

    return render_template("register.html")


# ==========================================
# PROFILE
# ==========================================

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "hx_code" not in session:
        return redirect("/register")

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
        SELECT nickname,
               hx_code,
               bio
        FROM users
        WHERE hx_code=?
        """,
        (hx_code,)
    )
    user = cur.fetchone()
    conn.close()

    return render_template("profile.html", user=user)


# ==========================================
# FRIENDS
# ==========================================

@app.route("/add_friend", methods=["POST"])
def add_friend():
    if "hx_code" not in session:
        return redirect("/register")

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
            """
            INSERT INTO friends(owner_code, friend_code)
            VALUES(?,?)
            """,
            (owner, friend_code)
        )
        cur.execute(
            """
            INSERT INTO friends(owner_code, friend_code)
            VALUES(?,?)
            """,
            (friend_code, owner)
        )
        conn.commit()

    conn.close()
    return redirect("/friends")


@app.route("/friends")
def friends():
    if "hx_code" not in session:
        return redirect("/register")

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
            SELECT nickname,
                   hx_code
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


# ==========================================
# DELETE FRIEND
# ==========================================

@app.route("/delete_friend/<friend_code>")
def delete_friend(friend_code):
    if "hx_code" not in session:
        return redirect("/register")

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


# ==========================================
# CHAT
# ==========================================

@app.route("/chat/<friend_code>")
def chat(friend_code):
    if "hx_code" not in session:
        return redirect("/register")

    my_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT nickname
        FROM users
        WHERE hx_code=?
        """,
        (friend_code,)
    )
    friend = cur.fetchone()

    if not friend:
        conn.close()
        return redirect("/friends")

    cur.execute(
        """
        SELECT sender_code,
               receiver_code,
               message,
               created
        FROM messages
        WHERE
        (sender_code=? AND receiver_code=?)
        OR
        (sender_code=? AND receiver_code=?)
        ORDER BY id
        """,
        (my_code, friend_code, friend_code, my_code)
    )

    messages = cur.fetchall()
    conn.close()

    return render_template(
        "chat.html",
        friend_name=friend[0],
        friend_code=friend_code,
        messages=messages,
        my_code=my_code
    )


@app.route("/send_message/<friend_code>", methods=["POST"])
def send_message(friend_code):
    if "hx_code" not in session:
        return redirect("/register")

    my_code = session["hx_code"]
    text = request.form["message"].strip()

    if text:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO messages(
                sender_code,
                receiver_code,
                message
            )
            VALUES(?,?,?)
            """,
            (my_code, friend_code, text)
        )

        conn.commit()
        conn.close()

    return redirect(f"/chat/{friend_code}")


# ==========================================
# AJAX MESSAGES
# ==========================================

@app.route("/messages/<friend_code>")
def get_messages(friend_code):
    if "hx_code" not in session:
        return jsonify([])

    my_code = session["hx_code"]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT sender_code, message
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
            "text": row[1]
        }
        for row in rows
    ])


@app.route("/send_ajax", methods=["POST"])
def send_ajax():
    if "hx_code" not in session:
        return jsonify({"ok": False})

    data = request.get_json()
    friend_code = data["friend"]
    message = data["message"]
    my_code = session["hx_code"]

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO messages(
            sender_code,
            receiver_code,
            message
        )
        VALUES(?,?,?)
    """,
    (
        my_code,
        friend_code,
        message
    ))

    conn.commit()
    conn.close()

    return jsonify({"ok": True})


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/register")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)