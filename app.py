from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, send
from uuid import uuid4
from collections import defaultdict
import json
import os

# Constants and file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------------
# In-memory data
# ------------------------

skills_data = [
    {"id": 1, "name": "Riya", "role": "Mentor", "desc": "Python developer and AI enthusiast.", "tags": ["Python", "AI", "Machine Learning"]},
    {"id": 2, "name": "Karan", "role": "Learner", "desc": "Aspiring frontend developer.", "tags": ["JavaScript", "React", "CSS"]},
    {"id": 3, "name": "Neha", "role": "Mentor", "desc": "Graphic designer and illustrator.", "tags": ["Photoshop", "Illustrator", "Design"]},
    {"id": 4, "name": "Sahil", "role": "Learner", "desc": "Interested in backend development.", "tags": ["Node.js", "Express", "Databases"]},
    {"id": 5, "name": "Meera", "role": "Mentor", "desc": "Fullstack developer and mentor.", "tags": ["Python", "Django", "React"]},
    {"id": 6, "name": "Amit", "role": "Learner", "desc": "Learning DevOps and cloud.", "tags": ["AWS", "Docker", "Kubernetes"]}
]

# friend_requests: key = to_user_id, value = set of from_user_ids (pending requests)
friend_requests = defaultdict(set)
# friends: key = user_id, value = set of friend_user_ids
friends = defaultdict(set)

chat_requests = {}
chat_sessions = {}
user_sessions = defaultdict(list)

# ---------- User Helpers ----------

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return []
            return json.loads(data)
    except (json.JSONDecodeError, ValueError) as e:
        print("[ERROR] Error loading users.json:", e)
        return []

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        print("[DEBUG] Users saved successfully.")
    except Exception as e:
        print("[ERROR] Error saving users.json:", e)

def find_user_by_email(email):
    users = load_users()
    for user in users:
        if user.get("email").lower() == email.lower():
            return user
    return None

def find_user_by_name(name):
    for user in skills_data:
        if user['name'].lower() == name.lower():
            return user
    return None

def find_user_by_id(user_id):
    for user in skills_data:
        if user['id'] == user_id:
            return user
    return None

def update_user_skills(email, new_skill):
    users = load_users()
    for user in users:
        if user.get("email") == email:
            user.setdefault("skills", [])
            if new_skill not in user["skills"]:
                user["skills"].append(new_skill)
            save_users(users)
            return True
    return False

def update_user_bio(email, new_bio):
    users = load_users()
    for user in users:
        if user.get("email") == email:
            user["bio"] = new_bio
            save_users(users)
            return True
    return False

# ---------- Routes ----------

@app.route("/")
def home():
    # Fix redirect loop: If logged in to skill_data user, redirect to skills page, else login page
    if "user_id" in session:
        return redirect(url_for("skills"))
    elif "email" in session:
        return redirect(url_for("home"))
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email_or_name = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = find_user_by_email(email_or_name)
        if user and user.get("password") == password:
            session["user"] = user.get("fullname")
            session["email"] = user.get("email")
            flash("Login successful.", "success")
            return redirect(url_for("profile"))

        user_by_name = find_user_by_name(email_or_name)
        # For skill_data users, allow login without password
        if user_by_name and password == "":
            session["user_id"] = user_by_name["id"]
            session["username"] = user_by_name["name"]
            flash(f"Login successful as {user_by_name['name']}.", "success")
            return redirect(url_for("skills"))

        flash("Invalid email/name or password!", "error")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not fullname or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match!", "error")
            return redirect(url_for("signup"))

        if find_user_by_email(email):
            flash("Email already registered!", "error")
            return redirect(url_for("signup"))

        users = load_users()
        users.append({
            "fullname": fullname,
            "email": email,
            "password": password,
            "skills": [],
            "bio": ""
        })

        save_users(users)
        flash("Account created! Please login.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/profile")
def profile():
    if "email" not in session:
        flash("Please login to view your profile.", "error")
        return redirect(url_for("login"))

    email = session.get("email")
    user = find_user_by_email(email)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        name=user.get("fullname"),
        email=user.get("email"),
        skills=user.get("skills", []),
        bio=user.get("bio", "")
    )

@app.route("/edit-skills", methods=["GET", "POST"])
def edit_skills():
    if "email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    user = find_user_by_email(session["email"])
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        new_skill = request.form.get("skill", "").strip()
        if new_skill:
            update_user_skills(user["email"], new_skill)
            flash("Skill added!", "success")
        return redirect(url_for("profile"))

    return render_template("edit_skills.html", name=user["fullname"], skills=user.get("skills", []))

@app.route("/edit-bio", methods=["GET", "POST"])
def edit_bio():
    if "email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    user = find_user_by_email(session["email"])
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        update_user_bio(user["email"], bio)
        flash("Bio updated!", "success")
        return redirect(url_for("profile"))

    return render_template("edit_bio.html", name=user["fullname"], bio=user.get("bio", ""))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/skills")
def skills():
    user_id = session.get('user_id')
    print("Current session user_id:", user_id)  # Debug print
    if not user_id:
        if "email" in session:
            return redirect(url_for("profile"))
        return redirect(url_for("login"))

    user = find_user_by_id(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    return render_template('skills.html', user_id=user_id, username=user['name'], skills=skills_data)

# Friend Requests API
# ---------------------------

@app.route('/friend_data/<int:user_id>')
def friend_data(user_id):
    incoming_reqs = list(friend_requests.get(user_id, set()))
    user_friends = list(friends.get(user_id, set()))
    return jsonify({'friend_requests': incoming_reqs, 'friends': user_friends})

@app.route('/send_friend_request', methods=['POST'])
def send_friend_request():
    data = request.json
    from_user = session.get('user_id')
    to_user = data.get('to_user')

    if from_user is None:
        return jsonify({'status': 'user not logged in'}), 401

    if from_user == to_user:
        return jsonify({'status': 'cannot send request to yourself'}), 400

    # Validate user exists
    if to_user not in [u['id'] for u in skills_data]:
        return jsonify({'status': 'user not found'}), 404

    # Check if already friends
    if to_user in friends.get(from_user, set()):
        return jsonify({'status': 'already friends'}), 400

    # Check if request already sent
    if from_user in friend_requests.get(to_user, set()):
        return jsonify({'status': 'request already sent'}), 400

    friend_requests[to_user].add(from_user)
    return jsonify({'status': 'request sent'})

@app.route('/respond_friend_request', methods=['POST'])
def respond_friend_request():
    data = request.json
    from_user = data.get('from_user')
    to_user = session.get('user_id')
    accept = data.get('accept')

    if to_user is None:
        return jsonify({'status': 'user not logged in'}), 401

    if from_user not in friend_requests.get(to_user, set()):
        return jsonify({'status': 'no request found'}), 404

    friend_requests[to_user].remove(from_user)

    if accept:
        friends[to_user].add(from_user)
        friends[from_user].add(to_user)
        return jsonify({'status': 'accepted'})
    else:
        return jsonify({'status': 'rejected'})

# ✅ NEWLY ADDED
@app.route("/get_user/<int:user_id>")
def get_user(user_id):
    user = find_user_by_id(user_id)
    if user:
        return jsonify({"id": user_id, "name": user["name"]})
    return jsonify({"error": "User not found"}), 404

# ---------------------------
# Other Pages
# ---------------------------

@app.route('/search')
def search():
    if "user" not in session and "user_id" not in session:
        flash("Please login to use the search.", "error")
        return redirect(url_for("login"))
    return render_template("search.html")

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/chatsystem')
def chatsystem():
    if "user" not in session and "user_id" not in session:
        flash("Please login to access chat system.", "error")
        return redirect(url_for("login"))
    return render_template('chatsystem.html')

@app.route('/notifications.html')
def notifications():
    if "user" not in session and "user_id" not in session:
        flash("Please login to access notifications.", "error")
        return redirect(url_for("login"))
    return render_template('notifications.html')

@app.route('/connections.html')
def connections():
    if "user" not in session and "user_id" not in session:
        flash("Please login to access connections.", "error")
        return redirect(url_for("login"))
    return render_template('connections.html')


# ---------------------------
# SocketIO Events
# ---------------------------

@socketio.on('message')
def handle_message(msg):
    print(f"[SocketIO] Message received: {msg}")
    send(msg, broadcast=True)

# ---------------------------
# Run App
# ---------------------------

if __name__ == '__main__':
    socketio.run(app, debug=True)
