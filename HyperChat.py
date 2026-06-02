from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import string
import os

app = Flask(__name__)
app.secret_key = "hyperchat_secret_key"

DB_NAME = "hyperchat.db"


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
    return "HX-" + "".join(
        random.choices(string.digits, k=6)
    )


def get_user(hx_code):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "SELECT nickname,hx_code,bio FROM users WHERE hx_code=?",
        (hx_code,)
    )

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
            (
                nickname,
                hx_code
            )
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
            (
                bio,
                hx_code
            )
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

    return render_template(
        "profile.html",
        user=user
    )


# ==========================================
# FRIENDS
# ==========================================

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

    return render_template(
        "friends.html",
        friends=friend_list
    )


# ==========================================
# ADD FRIEND
# ==========================================

@app.route("/add_friend", methods=["POST"])
def add_friend():

    if "hx_code" not in session:
        return redirect("/register")

    owner = session["hx_code"]

    friend_code = request.form["friend_code"]

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM users
        WHERE hx_code=?
        """,
        (friend_code,)
    )

    user = cur.fetchone()

    if user:

        cur.execute(
            """
            INSERT INTO friends(
                owner_code,
                friend_code
            )
            VALUES(?,?)
            """,
            (
                owner,
                friend_code
            )
        )

        conn.commit()

    conn.close()

    return redirect("/friends")


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
        (
            owner,
            friend_code
        )
    )

    conn.commit()
    conn.close()

    return redirect("/friends")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/register")


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )