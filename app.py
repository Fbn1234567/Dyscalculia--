from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
import random
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")
bcrypt = Bcrypt(app)

# ─────────────────────────────────────────────────────────────
# DATABASE — Supabase (PostgreSQL)
#
# In your .env or hosting dashboard, set ONE of these:
#
#   Option A — Supabase "URI" connection string (recommended):
#     DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
#
#   Option B — individual Supabase vars (set all five):
#     SUPABASE_HOST     = aws-0-[region].pooler.supabase.com
#     SUPABASE_PORT     = 6543
#     SUPABASE_DB       = postgres
#     SUPABASE_USER     = postgres.[project-ref]
#     SUPABASE_PASSWORD = your-db-password
#
# Find these in: Supabase Dashboard → Project Settings → Database → Connection string
# ─────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

# ─────────────────────────────
# AGE GROUP CONFIG
# ─────────────────────────────
AGE_GROUPS = [
    {"name": "age_6_7",    "label": "Ages 6–7",    "min": 6,  "max": 7},
    {"name": "age_8_9",    "label": "Ages 8–9",    "min": 8,  "max": 9},
    {"name": "age_10_11",  "label": "Ages 10–11",  "min": 10, "max": 11},
    {"name": "age_12_13",  "label": "Ages 12–13",  "min": 12, "max": 13},
    {"name": "age_14_15",  "label": "Ages 14–15",  "min": 14, "max": 15},
    {"name": "age_16_17",  "label": "Ages 16–17",  "min": 16, "max": 17},
    {"name": "age_18plus", "label": "Ages 18+",    "min": 18, "max": 999},
]

# Test difficulty per age group
TEST_CONFIG = {
    "age_6_7":    {"sym_range": (1, 20),  "ans_range": (3, 12),  "wm_start": 2, "sym_trials": 8,  "ans_trials": 8},
    "age_8_9":    {"sym_range": (1, 30),  "ans_range": (4, 15),  "wm_start": 3, "sym_trials": 10, "ans_trials": 10},
    "age_10_11":  {"sym_range": (1, 40),  "ans_range": (5, 18),  "wm_start": 3, "sym_trials": 10, "ans_trials": 10},
    "age_12_13":  {"sym_range": (1, 50),  "ans_range": (5, 20),  "wm_start": 3, "sym_trials": 12, "ans_trials": 12},
    "age_14_15":  {"sym_range": (1, 60),  "ans_range": (5, 25),  "wm_start": 4, "sym_trials": 12, "ans_trials": 12},
    "age_16_17":  {"sym_range": (1, 75),  "ans_range": (5, 30),  "wm_start": 4, "sym_trials": 15, "ans_trials": 15},
    "age_18plus": {"sym_range": (1, 99),  "ans_range": (5, 40),  "wm_start": 4, "sym_trials": 15, "ans_trials": 15},
}

def get_age_group(age):
    for g in AGE_GROUPS:
        if g["min"] <= age <= g["max"]:
            return g["name"]
    return "age_18plus"

def get_test_config():
    ag = session.get("age_group", "age_10_11")
    return TEST_CONFIG.get(ag, TEST_CONFIG["age_10_11"])

# ─────────────────────────────
# DB
# ─────────────────────────────
def get_db_connection():
    # Supabase URLs may already include SSL params — avoid conflict by only
    # appending sslmode=require if not already present in the URL.
    url = DATABASE_URL
    if url and "sslmode" not in url:
        url = url + ("&" if "?" in url else "?") + "sslmode=require"
    return psycopg2.connect(url)

# ─────────────────────────────
# MODEL LOADING (lazy, cached per age group)
# ─────────────────────────────
_model_cache = {}

def load_model(age_group=None):
    import pickle
    global _model_cache
    if age_group is None:
        age_group = session.get("age_group", "age_10_11")
    if age_group not in _model_cache:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        m_path  = os.path.join(BASE_DIR, "models", f"model_{age_group}.pkl")
        le_path = os.path.join(BASE_DIR, "models", f"label_encoder_{age_group}.pkl")
        # fallback to generic if age-specific doesn't exist
        if not os.path.exists(m_path):
            m_path  = os.path.join(BASE_DIR, "models", "model.pkl")
            le_path = os.path.join(BASE_DIR, "models", "label_encoder.pkl")
        _model_cache[age_group] = (
            pickle.load(open(m_path, "rb")),
            pickle.load(open(le_path, "rb"))
        )
    return _model_cache[age_group]

# ─────────────────────────────
# HOME
# ─────────────────────────────
@app.route("/")
def home():
    return redirect("/login")

# ─────────────────────────────
# LOGIN
# ─────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close(); conn.close()
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = user["email"]
            session["role"] = user["role"]
            session["age"]  = user.get("age", 10)
            session["age_group"] = get_age_group(user.get("age", 10))
            return redirect("/dashboard")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# ─────────────────────────────
# REGISTER
# ─────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id,email FROM users WHERE role='Teacher'")
    teachers = cur.fetchall()
    cur.execute("SELECT id,email FROM users WHERE role='Parent'")
    parents = cur.fetchall()
    if request.method == "POST":
        email     = request.form["email"]
        password  = request.form["password"]
        role      = request.form["role"]
        age       = int(request.form.get("age", 10))
        teacher_id = request.form.get("teacher_id")
        parent_id  = request.form.get("parent_id")
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        if role == "Student":
            cur.execute(
                "INSERT INTO users(email,password,role,age,teacher_id,parent_id) VALUES(%s,%s,%s,%s,%s,%s)",
                (email, hashed, role, age, teacher_id, parent_id)
            )
        else:
            cur.execute(
                "INSERT INTO users(email,password,role,age) VALUES(%s,%s,%s,%s)",
                (email, hashed, role, age)
            )
        conn.commit(); cur.close(); conn.close()
        return redirect("/login")
    cur.close(); conn.close()
    return render_template("register.html", teachers=teachers, parents=parents, age_groups=AGE_GROUPS)

# ─────────────────────────────
# DASHBOARD
# ─────────────────────────────
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    role = session["role"]
    cfg  = get_test_config()
    if role == "Student":
        return render_template("student_dashboard.html", user=session["user"],
                               age=session.get("age", "?"),
                               age_group_label=next((g["label"] for g in AGE_GROUPS if g["name"]==session.get("age_group")), ""),
                               cfg=cfg)
    if role == "Teacher":
        return render_template("teacher_dashboard.html", user=session["user"])
    if role == "Parent":
        return render_template("parent_dashboard.html", user=session["user"])
    if role == "Admin":
        return render_template("admin_dashboard.html", user=session["user"])

# ─────────────────────────────
# LOGOUT
# ─────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ─────────────────────────────
# CREATE TEACHER (Admin only)
# ─────────────────────────────
@app.route("/create_teacher", methods=["GET", "POST"])
def create_teacher():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]
        hashed   = bcrypt.generate_password_hash(password).decode("utf-8")
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("INSERT INTO users(email,password,role) VALUES(%s,%s,'Teacher')", (email, hashed))
        conn.commit(); cur.close(); conn.close()
        return redirect("/dashboard")
    return render_template("create_teacher.html")

# ─────────────────────────────
# START COGNITIVE TEST
# ─────────────────────────────
@app.route("/start_cognitive")
def start_cognitive():
    if "user" not in session:
        return redirect("/login")
    return redirect("/symbolic_test")

# ═══════════════════════════════════════════
# SYMBOLIC TEST (age-calibrated)
# ═══════════════════════════════════════════
@app.route("/symbolic_test")
def symbolic_test():
    session["symbolic_data"]  = []
    session["symbolic_trial"] = 0
    return redirect("/symbolic_trial")

@app.route("/symbolic_trial")
def symbolic_trial():
    cfg   = get_test_config()
    trial = session.get("symbolic_trial", 0)
    if trial >= cfg["sym_trials"]:
        return redirect("/finish_symbolic")
    lo, hi = cfg["sym_range"]
    left   = random.randint(lo, hi)
    right  = random.randint(lo, hi)
    while left == right:
        right = random.randint(lo, hi)
    session["left"]  = left
    session["right"] = right
    return render_template("symbolic_test.html", left=left, right=right,
                           trial=trial+1, total=cfg["sym_trials"])

@app.route("/submit_symbolic", methods=["POST"])
def submit_symbolic():
    choice = request.form["choice"]
    rt     = float(request.form["response_time"])
    left   = session["left"]
    right  = session["right"]
    correct = "left" if left > right else "right"
    session["symbolic_data"].append({"correct": 1 if choice == correct else 0, "rt": rt})
    session["symbolic_trial"] += 1
    return redirect("/symbolic_trial")

@app.route("/finish_symbolic")
def finish_symbolic():
    trials   = session["symbolic_data"]
    accuracy = sum(t["correct"] for t in trials) / len(trials)
    mean_rt  = sum(t["rt"] for t in trials) / len(trials)
    session["Accuracy_SymbolicComp"] = accuracy
    session["RTs_SymbolicComp"]      = mean_rt
    return redirect("/ans_test")

# ═══════════════════════════════════════════
# ANS TEST (age-calibrated)
# ═══════════════════════════════════════════
@app.route("/ans_test")
def ans_test():
    session["ans_data"]  = []
    session["ans_trial"] = 0
    return redirect("/ans_trial")

@app.route("/ans_trial")
def ans_trial():
    cfg   = get_test_config()
    trial = session["ans_trial"]
    if trial >= cfg["ans_trials"]:
        return redirect("/finish_ans")
    lo, hi = cfg["ans_range"]
    left   = random.randint(lo, hi)
    right  = random.randint(lo, hi)
    while left == right:
        right = random.randint(lo, hi)
    session["ans_left"]  = left
    session["ans_right"] = right
    return render_template("ans_test.html", left=left, right=right,
                           trial=trial+1, total=cfg["ans_trials"])

@app.route("/submit_ans", methods=["POST"])
def submit_ans():
    choice = request.form["choice"]
    rt     = float(request.form["response_time"])
    left   = session["ans_left"]
    right  = session["ans_right"]
    correct = "left" if left > right else "right"
    session["ans_data"].append({"correct": 1 if choice == correct else 0, "rt": rt})
    session["ans_trial"] += 1
    return redirect("/ans_trial")

@app.route("/finish_ans")
def finish_ans():
    trials   = session["ans_data"]
    accuracy = sum(t["correct"] for t in trials) / len(trials)
    mean_rt  = sum(t["rt"] for t in trials) / len(trials)
    session["Mean_ACC_ANS"] = accuracy
    session["Mean_RTs_ANS"] = mean_rt
    return redirect("/wm_test")

# ═══════════════════════════════════════════
# WORKING MEMORY TEST (age-calibrated)
# ═══════════════════════════════════════════
@app.route("/wm_test")
def wm_test():
    cfg = get_test_config()
    session["wm_level"] = cfg["wm_start"]
    session["wm_data"]  = []
    return redirect("/wm_trial")

@app.route("/wm_trial")
def wm_trial():
    level    = session["wm_level"]
    sequence = [str(random.randint(1, 9)) for _ in range(level)]
    session["sequence"] = sequence
    return render_template("wm_test.html", sequence=" ".join(sequence), level=level)

@app.route("/submit_wm", methods=["POST"])
def submit_wm():
    answer      = request.form["answer"].replace(" ", "")
    correct_seq = "".join(session["sequence"])
    correct     = 1 if answer == correct_seq else 0
    session["wm_data"].append({"level": session["wm_level"], "correct": correct})
    if correct:
        session["wm_level"] += 1
        return redirect("/wm_trial")
    return redirect("/finish_wm")

@app.route("/finish_wm")
def finish_wm():
    data   = session["wm_data"]
    scores = [d["level"] for d in data if d["correct"] == 1]
    session["wm_K"] = max(scores) if scores else session.get("wm_level", 3) - 1
    return redirect("/final_prediction")

# ═══════════════════════════════════════════
# FINAL ML PREDICTION (age-group model)
# ═══════════════════════════════════════════
@app.route("/final_prediction")
def final_prediction():
    import numpy as np
    age_group = session.get("age_group", "age_10_11")
    model, label_encoder = load_model(age_group)

    features = np.array([[
        session["Mean_ACC_ANS"],
        session["Mean_RTs_ANS"],
        session["wm_K"],
        session["Accuracy_SymbolicComp"],
        session["RTs_SymbolicComp"],
    ]])

    prediction  = model.predict(features)
    probability = model.predict_proba(features)
    label       = label_encoder.inverse_transform(prediction)[0].lower()
    confidence  = round(max(probability[0]) * 100, 2)

    # Map model label to risk + recommendation
    if label in ["dd", "dyscalculia"]:
        risk = "Dyscalculia Detected"
        if confidence >= 85:
            severity = "High Likelihood"
            rec = ("Immediate professional evaluation is strongly recommended.\n"
                   "Consider referral to an educational psychologist or specialist.\n"
                   "Individualized learning plans and targeted math interventions are advised.")
        elif confidence >= 65:
            severity = "Moderate Likelihood"
            rec = ("Additional structured math support and practice is recommended.\n"
                   "Monitor progress closely with regular re-assessment.\n"
                   "Consider consulting an educational specialist.")
        else:
            severity = "Borderline"
            rec = ("Some difficulties detected. Provide reinforcement activities.\n"
                   "Re-assess in 4–6 weeks after targeted practice.")
    else:
        risk = "No Dyscalculia Detected"
        severity = "Low Risk"
        rec = ("Performance is within the typical range for this age group.\n"
               "Continue with normal learning activities.\n"
               "Re-assess periodically as part of regular monitoring.")

    # Save result
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO results(student_email,age,age_group,ans_acc,ans_rt,wm_k,sym_acc,sym_rt,risk_level,severity,confidence)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (session["user"], session.get("age", 0), age_group,
         session["Mean_ACC_ANS"], session["Mean_RTs_ANS"], session["wm_K"],
         session["Accuracy_SymbolicComp"], session["RTs_SymbolicComp"],
         risk, severity, confidence)
    )
    conn.commit(); cur.close(); conn.close()

    return render_template("final_result.html", risk=risk, severity=severity,
                           confidence=confidence, recommendations=rec,
                           age_group_label=next((g["label"] for g in AGE_GROUPS if g["name"]==age_group), ""))

# ─────────────────────────────
# HISTORY (student's own)
# ─────────────────────────────
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")
    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT * FROM results WHERE student_email=%s ORDER BY created_at DESC",
        (session["user"],)
    )
    results = cur.fetchall()
    cur.close(); conn.close()
    return render_template("history.html", results=results)

# ─────────────────────────────
# TEACHER RESULTS
# ─────────────────────────────
@app.route("/teacher_results")
def teacher_results():
    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM results ORDER BY created_at DESC")
    results = cur.fetchall()
    cur.close(); conn.close()
    return render_template("teacher_results.html", results=results)

# ─────────────────────────────
# PARENT VIEW (own child only)
# ─────────────────────────────
@app.route("/parent_results")
def parent_results():
    if "user" not in session or session["role"] != "Parent":
        return redirect("/login")
    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    # Get children linked to this parent
    cur.execute(
        "SELECT email FROM users WHERE parent_id=(SELECT id FROM users WHERE email=%s)",
        (session["user"],)
    )
    children = [r["email"] for r in cur.fetchall()]
    results  = []
    for child in children:
        cur.execute("SELECT * FROM results WHERE student_email=%s ORDER BY created_at DESC", (child,))
        results += cur.fetchall()
    cur.close(); conn.close()
    return render_template("parent_results.html", results=results, children=children)

# ─────────────────────────────
# RUN
# ─────────────────────────────
if __name__ == "__main__":
    app.run(debug=False)
