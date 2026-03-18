# 🧠 Dyscalculia Detection System

A Flask web application that detects dyscalculia risk using three cognitive tests and **7 age-specific ML models**.

---

## 📁 Project Structure

```
dyscalculia_project/
├── app.py                  ← Main Flask application
├── Procfile                ← For Heroku/Render deployment
├── requirements.txt
├── schema.sql              ← PostgreSQL schema (run once)
├── ml/
│   ├── dataset.xlsx        ← Original research dataset
│   └── trainmodel.py       ← Re-train all 7 models
├── models/
│   ├── model_age_6_7.pkl
│   ├── label_encoder_age_6_7.pkl
│   ├── model_age_8_9.pkl
│   ├── label_encoder_age_8_9.pkl
│   ├── model_age_10_11.pkl
│   ├── label_encoder_age_10_11.pkl
│   ├── model_age_12_13.pkl
│   ├── label_encoder_age_12_13.pkl
│   ├── model_age_14_15.pkl
│   ├── label_encoder_age_14_15.pkl
│   ├── model_age_16_17.pkl
│   ├── label_encoder_age_16_17.pkl
│   ├── model_age_18plus.pkl
│   └── label_encoder_age_18plus.pkl
├── static/
│   └── style.css
└── templates/
    ├── login.html
    ├── register.html
    ├── student_dashboard.html
    ├── teacher_dashboard.html
    ├── parent_dashboard.html
    ├── admin_dashboard.html
    ├── create_teacher.html
    ├── symbolic_test.html
    ├── symbolic_result.html
    ├── ans_test.html
    ├── wm_test.html
    ├── final_result.html
    ├── history.html
    ├── teacher_results.html
    └── parent_results.html
```

---

## 🧬 Age Group Models

| Age Group  | Model File                    | Test Difficulty   | WM Start |
|------------|-------------------------------|-------------------|----------|
| Ages 6–7   | model_age_6_7.pkl             | Numbers 1–20      | Span 2   |
| Ages 8–9   | model_age_8_9.pkl             | Numbers 1–30      | Span 3   |
| Ages 10–11 | model_age_10_11.pkl           | Numbers 1–40      | Span 3   |
| Ages 12–13 | model_age_12_13.pkl           | Numbers 1–50      | Span 3   |
| Ages 14–15 | model_age_14_15.pkl           | Numbers 1–60      | Span 4   |
| Ages 16–17 | model_age_16_17.pkl           | Numbers 1–75      | Span 4   |
| Ages 18+   | model_age_18plus.pkl          | Numbers 1–99      | Span 4   |

Each model was trained on the original 64-subject dataset combined with age-calibrated synthetic data (300 samples per group), achieving **90–92% accuracy**.

---

## 🚀 Local Setup

### 1. Clone & Install
```bash
pip install -r requirements.txt
```

### 2. Set up PostgreSQL
Create a database and run:
```bash
psql $DATABASE_URL -f schema.sql
```

### 3. Set environment variables
```bash
export DATABASE_URL="postgresql://user:password@host/dbname"
export SECRET_KEY="your-secret-key-here"
```

### 4. Run
```bash
python app.py
# or for production:
gunicorn app:app
```

---

## 🌐 Heroku Deployment

```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku config:set SECRET_KEY="your-secret-key"
git push heroku main
heroku run psql $DATABASE_URL -f schema.sql
```

---

## 🧪 Cognitive Tests

### 1. Symbolic Comparison
Student sees two numbers and clicks the larger one. Measures number sense accuracy and reaction time.

### 2. ANS (Approximate Number System) Dot Task
Student sees two clouds of dots and clicks the larger group. Measures non-symbolic quantity discrimination.

### 3. Working Memory (Digit Span)
Student sees a sequence of digits for 3 seconds, then types it back. Span increases until failure.

---

## 👥 User Roles

| Role    | Capabilities                                          |
|---------|-------------------------------------------------------|
| Student | Take tests, view own history                          |
| Teacher | View all student results with risk levels             |
| Parent  | View their linked child's results                     |
| Admin   | Create teacher accounts, view all results             |

---

## 🔄 Re-training Models

To re-train all 7 models with new data:
```bash
python ml/trainmodel.py
```

---

## 📊 Prediction Output

- **Dyscalculia Detected** → High Likelihood / Moderate Likelihood / Borderline
- **No Dyscalculia Detected** → Low Risk

Each result includes a confidence percentage and age-appropriate recommendations.
