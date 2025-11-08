from flask import Flask, render_template, request, redirect, url_for, flash , session
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
DEFAULT_VIEW = "default"

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
# ------------------- Customer Data Handling (Updated) -------------------

def load_all_data():
    """Loads the entire data dictionary: {view_name: [customers], ...}"""
    if not os.path.exists(DATA_FILE):
        # Initialize with a default view if the file doesn't exist
        return {DEFAULT_VIEW: []} 
    with open(DATA_FILE, "r") as f:
        try:
            data = json.load(f)
            # Ensure the data structure is a dictionary
            return data if isinstance(data, dict) else {DEFAULT_VIEW: []}
        except json.JSONDecodeError:
            return {DEFAULT_VIEW: []}


def save_all_data(data):
    """Saves the entire data dictionary to the file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_view_data(view_name):
    """Loads customer data for a specific view."""
    all_data = load_all_data()
    return all_data.get(view_name, [])


def save_view_data(view_name, view_data):
    """Saves customer data back to a specific view."""
    all_data = load_all_data()
    all_data[view_name] = view_data
    save_all_data(all_data)
    

def get_all_views():
    """Returns a list of all current view names."""
    return list(load_all_data().keys())


def total_people(data):
    """Calculates total people for a given list of customers."""
    return sum(cust["amount"] for cust in data)

# ------------------- Routes -------------------
@app.route("/")
def index():
    # Initialize the session view if it's not set
    if 'current_view' not in session:
        session['current_view'] = DEFAULT_VIEW
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
    view_name = session.get('current_view', DEFAULT_VIEW)
    data = load_view_data(view_name) # Load data for the current view
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
            flash(f"Cannot register: total for '{view_name}' would exceed 50 (current {total_people(data)})", "error")
            return redirect(url_for("register"))

        data.append({
            "name": name,
            "phone": phone,
            "room": room,
            "amount": amount,
            "arrived": False,
            "second_phone": second_phone or ""
        })
        save_view_data(view_name, data)
        flash("Customer registered successfully!", "success")
        return redirect(url_for("register"))

    return render_template("register.html", total=current_total, current_view=view_name, all_views=get_all_views())

# ---- Arrived ----
@app.route("/arrived", methods=["GET", "POST"])
@login_required
def arrived():
    view_name = session.get('current_view', DEFAULT_VIEW)
    data = load_view_data(view_name)
    if request.method == "POST":
        selected = request.form.getlist("arrived") or []

        for cust in data:
            cust["arrived"] = cust.get("name") in selected

        save_view_data(view_name, data)
        flash(f"Arrived status updated for view: {view_name}!", "success")
        return redirect(url_for("arrived"))

    return render_template("arrived.html", customers=data, current_view=view_name, all_views=get_all_views())

# ---- Delete All ----
@app.route("/delete_all", methods=["POST"])
@login_required
def delete_all():
    view_name = session.get('current_view', DEFAULT_VIEW)
    save_view_data(view_name, [])
    flash(f"All customer data for view '{view_name}' deleted!", "success")
    return redirect(url_for("register"))

# ---- View Management ----
@app.route("/views/manage", methods=["GET", "POST"])
@login_required
def manage_views():
    all_data = load_all_data()
    all_views = list(all_data.keys())
    
    if request.method == "POST":
        view_name = request.form.get("view_name", "").strip()
        action = request.form.get("action")

        if not view_name:
            flash("View name cannot be empty.", "error")
            return redirect(url_for("manage_views"))

        if action == "create":
            if view_name in all_views:
                flash(f"View '{view_name}' already exists.", "error")
            else:
                all_data[view_name] = []
                save_all_data(all_data)
                flash(f"View '{view_name}' created successfully.", "success")
        
        elif action == "delete":
            if view_name in all_data and view_name != DEFAULT_VIEW:
                del all_data[view_name]
                save_all_data(all_data)
                # If the deleted view was active, switch to default
                if session.get('current_view') == view_name:
                    session['current_view'] = DEFAULT_VIEW
                flash(f"View '{view_name}' deleted successfully.", "success")
            elif view_name == DEFAULT_VIEW:
                flash("Cannot delete the default view.", "error")
            else:
                flash(f"View '{view_name}' not found.", "error")

        return redirect(url_for("manage_views"))

    return render_template("manage_views.html", views=all_views, default_view=DEFAULT_VIEW)


# New Route: `/views/select` (To Switch Views)
@app.route("/views/select/<view_name>")
@login_required
def select_view(view_name):
    all_views = get_all_views()
    if view_name in all_views:
        session['current_view'] = view_name
        flash(f"Switched to view: {view_name}", "success")
    else:
        flash(f"View '{view_name}' not found.", "error")
    
    return redirect(url_for("register"))

# ------------------- Run -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
