# Dyscalculia Detection System

## Setup
1. Set environment variables:
   - DATABASE_URL — your PostgreSQL connection string
   - SECRET_KEY — a random secret string

2. Place your model files in the `models/` folder:
   - models/model.pkl
   - models/label_encoder.pkl

3. Run: gunicorn app:app

## Test Flow
Student login → Start Assessment → Symbolic (10 trials) → ANS (10 trials) → Working Memory (adaptive) → Result

## Debug
Visit /debug_model to confirm model feature names and class labels.
