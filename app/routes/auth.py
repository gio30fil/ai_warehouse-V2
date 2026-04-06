from flask import Blueprint, render_template, request, session, redirect, url_for
from werkzeug.security import check_password_hash
from app.database import get_connection

auth = Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.permanent = True
            session["user"] = username
            session["role"] = user["role"]
            return redirect(url_for("search.home"))

        return render_template("login.html", error="Λάθος στοιχεία σύνδεσης")

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
