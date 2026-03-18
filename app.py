from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
import random
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

bcrypt = Bcrypt(app)

DATABASE_URL = os.getenv("DATABASE_URL")

# -----------------------------
# DATABASE CONNECTION (POOL)
# -----------------------------
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set.")
        _pool = SimpleConnectionPool(1, 5, dsn=DATABASE_URL, sslmode="require", connect_timeout=5)
    return _pool

def get_db_connection():
    return get_pool().getconn()

def release_db_connection(conn):
    get_pool().putconn(conn)


# -----------------------------
# ML MODEL LAZY LOADING
# -----------------------------
model = None
label_encoder = None

def load_model():
    global model, label_encoder
    if model is None:
        import pickle
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(BASE_DIR, "models", "model.pkl"), "rb") as f:
            model = pickle.load(f)
        with open(os.path.join(BASE_DIR, "models", "label_encoder.pkl"), "rb") as f:
            label_encoder = pickle.load(f)
    return model, label_encoder


# -----------------------------
# HOME
# -----------------------------
@app.route("/")
def home():
    return redirect("/login")


# -----------------------------
# LOGIN
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            cur.close()
        finally:
            release_db_connection(conn)

        if user and bcrypt.check_password_hash(user["password"], password):
            session["user"] = user["email"]
            session["role"] = user["role"]
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


# -----------------------------
# REGISTER
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    teachers = []
    parents = []
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, email FROM users WHERE role='Teacher'")
        teachers = cur.fetchall()
        cur.execute("SELECT id, email FROM users WHERE role='Parent'")
        parents = cur.fetchall()

        if request.method == "POST":
            email = request.form["email"]
            password = request.form["password"]
            role = request.form["role"]
            teacher_id = request.form.get("teacher_id") or None
            parent_id = request.form.get("parent_id") or None

            hashed = bcrypt.generate_password_hash(password).decode("utf-8")

            if role == "Student":
                cur.execute(
                    "INSERT INTO users(email,password,role,teacher_id,parent_id) VALUES(%s,%s,%s,%s,%s)",
                    (email, hashed, role, teacher_id, parent_id),
                )
            else:
                cur.execute(
                    "INSERT INTO users(email,password,role) VALUES(%s,%s,%s)",
                    (email, hashed, role),
                )

            conn.commit()
            cur.close()
            return redirect("/login")

        cur.close()
    finally:
        release_db_connection(conn)

    return render_template("register.html", teachers=teachers, parents=parents)


# -----------------------------
# DASHBOARD
# -----------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    role = session["role"]

    if role == "Student":
        return render_template("student_dashboard.html", user=session["user"])
    if role == "Teacher":
        return render_template("teacher_dashboard.html", user=session["user"])
    if role == "Parent":
        return render_template("parent_dashboard.html", user=session["user"])
    if role == "Admin":
        return render_template("admin_dashboard.html", user=session["user"])

    return redirect("/login")


# -----------------------------
# LOGOUT
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -----------------------------
# CREATE TEACHER
# -----------------------------
@app.route("/create_teacher", methods=["GET", "POST"])
def create_teacher():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users(email,password,role) VALUES(%s,%s,'Teacher')",
                (email, hashed),
            )
            conn.commit()
            cur.close()
        finally:
            release_db_connection(conn)

        return redirect("/dashboard")

    return render_template("create_teacher.html")


# -----------------------------
# START TEST
# -----------------------------
@app.route("/start_cognitive")
def start_cognitive():
    if "user" not in session:
        return redirect("/login")
    return redirect("/symbolic_test")


# =========================================================
# SYMBOLIC COMPARISON TEST  (10 trials)
# =========================================================

@app.route("/symbolic_test")
def symbolic_test():
    if "user" not in session:
        return redirect("/login")
    session["symbolic_data"] = []
    session["symbolic_trial"] = 0
    session.modified = True
    return redirect("/symbolic_trial")


@app.route("/symbolic_trial")
def symbolic_trial():
    if "user" not in session:
        return redirect("/login")

    trial = session.get("symbolic_trial", 0)
    if trial >= 10:
        return redirect("/finish_symbolic")

    left = random.randint(1, 50)
    right = random.randint(1, 50)
    while left == right:
        right = random.randint(1, 50)

    session["left"] = left
    session["right"] = right
    session.modified = True

    return render_template("symbolic_test.html", left=left, right=right, trial=trial + 1)


@app.route("/submit_symbolic", methods=["POST"])
def submit_symbolic():
    if "user" not in session:
        return redirect("/login")

    choice = request.form["choice"]
    rt = float(request.form.get("response_time", 0))

    correct = "left" if session["left"] > session["right"] else "right"
    val = 1 if choice == correct else 0

    data = session.get("symbolic_data", [])
    data.append({"correct": val, "rt": rt})
    session["symbolic_data"] = data
    session["symbolic_trial"] = session.get("symbolic_trial", 0) + 1
    session.modified = True

    return redirect("/symbolic_trial")


@app.route("/finish_symbolic")
def finish_symbolic():
    if "user" not in session:
        return redirect("/login")

    trials = session.get("symbolic_data", [])
    if not trials:
        session["Accuracy_SymbolicComp"] = 0
        session["RTs_SymbolicComp"] = 0
    else:
        session["Accuracy_SymbolicComp"] = sum(t["correct"] for t in trials) / len(trials)
        session["RTs_SymbolicComp"] = sum(t["rt"] for t in trials) / len(trials)

    session.modified = True
    return redirect("/ans_test")


# =========================================================
# ANS TEST  (10 trials)
# =========================================================

@app.route("/ans_test")
def ans_test():
    if "user" not in session:
        return redirect("/login")
    session["ans_data"] = []
    session["ans_trial"] = 0
    session.modified = True
    return redirect("/ans_trial")


@app.route("/ans_trial")
def ans_trial():
    if "user" not in session:
        return redirect("/login")

    trial = session.get("ans_trial", 0)
    if trial >= 10:
        return redirect("/finish_ans")

    left = random.randint(5, 20)
    right = random.randint(5, 20)
    while left == right:
        right = random.randint(5, 20)

    session["ans_left"] = left
    session["ans_right"] = right
    session.modified = True

    return render_template("ans_test.html", left=left, right=right, trial=trial + 1)


@app.route("/submit_ans", methods=["POST"])
def submit_ans():
    if "user" not in session:
        return redirect("/login")

    choice = request.form["choice"]
    rt = float(request.form.get("response_time", 0))

    correct = "left" if session["ans_left"] > session["ans_right"] else "right"
    val = 1 if choice == correct else 0

    data = session.get("ans_data", [])
    data.append({"correct": val, "rt": rt})
    session["ans_data"] = data
    session["ans_trial"] = session.get("ans_trial", 0) + 1
    session.modified = True

    return redirect("/ans_trial")


@app.route("/finish_ans")
def finish_ans():
    if "user" not in session:
        return redirect("/login")

    trials = session.get("ans_data", [])
    if not trials:
        session["Mean_ACC_ANS"] = 0
        session["Mean_RTs_ANS"] = 0
    else:
        session["Mean_ACC_ANS"] = sum(t["correct"] for t in trials) / len(trials)
        session["Mean_RTs_ANS"] = sum(t["rt"] for t in trials) / len(trials)

    session.modified = True
    return redirect("/wm_test")


# =========================================================
# WORKING MEMORY TEST  (adaptive)
# =========================================================

@app.route("/wm_test")
def wm_test():
    if "user" not in session:
        return redirect("/login")
    session["wm_level"] = 3
    session["wm_data"] = []
    session.modified = True
    return redirect("/wm_trial")


@app.route("/wm_trial")
def wm_trial():
    if "user" not in session:
        return redirect("/login")

    level = session.get("wm_level", 3)
    sequence = [str(random.randint(1, 9)) for _ in range(level)]
    session["sequence"] = sequence
    session.modified = True

    return render_template("wm_test.html", sequence=" ".join(sequence))


@app.route("/submit_wm", methods=["POST"])
def submit_wm():
    if "user" not in session:
        return redirect("/login")

    answer = request.form.get("answer", "").replace(" ", "")
    correct_seq = "".join(session.get("sequence", []))
    correct = 1 if answer == correct_seq else 0

    data = session.get("wm_data", [])
    data.append({"level": session.get("wm_level", 3), "correct": correct})
    session["wm_data"] = data
    session.modified = True

    if correct:
        session["wm_level"] = session.get("wm_level", 3) + 1
        session.modified = True
        return redirect("/wm_trial")

    return redirect("/finish_wm")


@app.route("/finish_wm")
def finish_wm():
    if "user" not in session:
        return redirect("/login")

    data = session.get("wm_data", [])
    scores = [d["level"] for d in data if d["correct"] == 1]
    session["wm_K"] = max(scores) if scores else 0
    session.modified = True

    return redirect("/final_prediction")


# =========================================================
# FINAL PREDICTION
# Uses exactly 5 features the model was trained on:
# Mean_ACC_ANS, Mean_RTs_ANS, wm_K,
# Accuracy_SymbolicComp, RTs_SymbolicComp
# =========================================================

@app.route("/final_prediction")
def final_prediction():
    if "user" not in session:
        return redirect("/login")

    risk = "Unknown"
    rec = ""
    confidence = 0

    try:
        mdl, le = load_model()
        import numpy as np

        ans_acc   = session.get("Mean_ACC_ANS", 0)
        ans_rt    = session.get("Mean_RTs_ANS", 0)
        wm_k      = session.get("wm_K", 0)
        sym_acc   = session.get("Accuracy_SymbolicComp", 0)
        sym_rt    = session.get("RTs_SymbolicComp", 0)

        features = np.array([[ans_acc, ans_rt, wm_k, sym_acc, sym_rt]])

        prediction  = mdl.predict(features)
        probability = mdl.predict_proba(features)

        label      = le.inverse_transform(prediction)[0].lower()
        confidence = round(max(probability[0]) * 100, 2)

        # Log for debugging — visible in Render logs
        print(f"[PREDICTION] label={label} confidence={confidence}%")
        print(f"[FEATURES]   ans_acc={ans_acc:.3f} ans_rt={ans_rt:.3f} wm_k={wm_k} sym_acc={sym_acc:.3f} sym_rt={sym_rt:.3f}")
        print(f"[ALL PROBA]  {dict(zip(le.classes_, probability[0]))}")

        if label in ["dd", "severe", "high", "dyscalculia", "yes"]:
            risk = "Highest Risk"
            rec  = "Immediate professional evaluation recommended. Use visual aids, number lines, and manipulatives. Break problems into smaller steps and allow extra time."
        elif label in ["moderate", "medium"]:
            risk = "Medium Risk"
            rec  = "Provide additional math practice and monitoring. Consider support strategies like structured worksheets and frequent feedback."
        elif label in ["mild", "low"]:
            risk = "Lowest Risk"
            rec  = "Provide reinforcement activities to strengthen numeracy skills."
        else:
            risk = "No Dyscalculia Detected"
            rec  = "Performance is within the typical range. Continue normal learning activities."

        # Save result to DB
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO results(student_email, ans_acc, ans_rt, wm_k, sym_acc, sym_rt, risk_level)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                """,
                (session["user"], ans_acc, ans_rt, wm_k, sym_acc, sym_rt, risk),
            )
            conn.commit()
            cur.close()
        finally:
            release_db_connection(conn)

    except Exception as e:
        print("PREDICTION ERROR:", e)
        risk = "Prediction Error"
        rec  = f"An error occurred: {str(e)}"
        confidence = 0

    return render_template(
        "final_result.html",
        risk=risk,
        confidence=confidence,
        recommendations=rec,
    )


# -----------------------------
# HISTORY
# -----------------------------
@app.route("/history")
def history():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT ans_acc, ans_rt, wm_k, sym_acc, sym_rt, risk_level, created_at
            FROM results
            WHERE student_email=%s
            ORDER BY created_at DESC
            """,
            (session["user"],),
        )
        results = cur.fetchall()
        cur.close()
    except Exception as e:
        print("HISTORY ERROR:", e)
        results = []
    finally:
        release_db_connection(conn)

    return render_template("history.html", results=results)


# -----------------------------
# TEACHER RESULTS
# -----------------------------
@app.route("/teacher_results")
def teacher_results():
    if "user" not in session:
        return redirect("/login")

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT student_email, risk_level, created_at FROM results ORDER BY created_at DESC"
        )
        results = cur.fetchall()
        cur.close()
    finally:
        release_db_connection(conn)

    return render_template("teacher_results.html", results=results)


# -----------------------------
# DEBUG — visit to confirm model details, remove after use
# -----------------------------
@app.route("/debug_model")
def debug_model():
    try:
        mdl, le = load_model()
        import numpy as np
        # Test with worst possible scores
        test = np.array([[0.0, 5.0, 0, 0.0, 5.0]])
        pred = mdl.predict(test)
        proba = mdl.predict_proba(test)
        label = le.inverse_transform(pred)[0]
        return (
            f"<b>Classes:</b> {list(le.classes_)}<br>"
            f"<b>Features ({len(mdl.feature_names_in_)}):</b> {list(mdl.feature_names_in_)}<br><br>"
            f"<b>Test with all-zero/worst scores:</b><br>"
            f"Predicted label: {label}<br>"
            f"Probabilities: {dict(zip(le.classes_, proba[0].round(3)))}"
        )
    except Exception as e:
        return f"Error: {str(e)}"


# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
