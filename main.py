from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
import json
import os

load_dotenv()

# ------------------- App Setup -------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY not found in environment or .env file.")
# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Rate limiter for login
limiter = Limiter(key_func=get_remote_address, app=app)

DATA_FILE = "data.json"
USERS_FILE = "users.json"


# ------------------- User Handling -------------------
class User(UserMixin):
    def __init__(self, username):
        self.id = username


def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def find_user(username):
    for u in load_users():
        if u.get("username") == username:
            return u
    return None


@login_manager.user_loader
def load_user(user_id):
    user = find_user(user_id)
    if user:
        return User(user_id)
    return None


# ------------------- Customer Data Handling -------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def total_people(data):
    return sum(cust["amount"] for cust in data)


# ------------------- Routes -------------------
@app.route("/")
def index():
    return redirect(url_for("register"))


# ---- Login ----
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = find_user(username)

        if user and check_password_hash(user["password_hash"], password):
            login_user(User(username))
            flash("Logged in successfully!", "success")
            return redirect(url_for("register"))
        else:
            flash("Invalid username or password", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


# ---- Logout ----
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


# ---- Register ----
@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    data = load_data()
    current_total = total_people(data)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        room = request.form.get("room", "").strip()
        amount = request.form.get("amount", "").strip()
        second_phone = request.form.get("second_phone", "").strip()

        if not name or not phone or not room or not amount:
            flash("Please fill all required fields!", "error")
            return redirect(url_for("register"))

        try:
            room = int(room)
            amount = int(amount)
        except ValueError:
            flash("Room and Amount must be numbers!", "error")
            return redirect(url_for("register"))

        if amount > 6 and not second_phone:
            flash("Second phone required for groups larger than 6!", "error")
            return redirect(url_for("register"))

        if total_people(data) + amount > 50:
            flash(f"Cannot register: total would exceed 50 (current {total_people(data)})", "error")
            return redirect(url_for("register"))

        data.append({
            "name": name,
            "phone": phone,
            "room": room,
            "amount": amount,
            "arrived": False,
            "second_phone": second_phone or ""
        })
        save_data(data)
        flash("Customer registered successfully!", "success")
        return redirect(url_for("register"))

    return render_template("register.html", total=current_total)


# ---- Arrived ----
@app.route("/arrived", methods=["GET", "POST"])
@login_required
def arrived():
    data = load_data()

    if request.method == "POST":
        selected = request.form.getlist("arrived") or []

        for cust in data:
            cust["arrived"] = cust.get("name") in selected

        save_data(data)
        flash("Arrived status updated!", "success")
        return redirect(url_for("arrived"))

    return render_template("arrived.html", customers=data)


# ---- Delete All ----
@app.route("/delete_all", methods=["POST"])
@login_required
def delete_all():
    save_data([])
    flash("All customer data deleted!", "success")
    return redirect(url_for("register"))


# ------------------- Run -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
