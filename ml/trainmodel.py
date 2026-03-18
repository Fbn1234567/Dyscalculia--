"""
Train 7 age-group-specific dyscalculia detection models.
Uses the base dataset + age-calibrated synthetic augmentation.
Run from project root: python ml/trainmodel.py
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "ml", "dataset.xlsx")
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

FEATURES = ["Mean_ACC_ANS", "Mean_RTs_ANS", "wm_K", "Accuracy_SymbolicComp", "RTs_SymbolicComp"]

AGE_GROUPS = [
    {"name": "age_6_7",    "wm_range": (2, 4),  "acc_range": (0.40, 0.70), "rt_mult": 2.2, "sym_rt_mult": 2500},
    {"name": "age_8_9",    "wm_range": (3, 5),  "acc_range": (0.50, 0.75), "rt_mult": 1.9, "sym_rt_mult": 2100},
    {"name": "age_10_11",  "wm_range": (3, 6),  "acc_range": (0.55, 0.80), "rt_mult": 1.6, "sym_rt_mult": 1800},
    {"name": "age_12_13",  "wm_range": (4, 7),  "acc_range": (0.60, 0.85), "rt_mult": 1.3, "sym_rt_mult": 1500},
    {"name": "age_14_15",  "wm_range": (5, 8),  "acc_range": (0.65, 0.90), "rt_mult": 1.1, "sym_rt_mult": 1300},
    {"name": "age_16_17",  "wm_range": (5, 9),  "acc_range": (0.70, 0.92), "rt_mult": 1.0, "sym_rt_mult": 1200},
    {"name": "age_18plus", "wm_range": (6, 10), "acc_range": (0.75, 0.95), "rt_mult": 0.9, "sym_rt_mult": 1100},
]

np.random.seed(42)


def generate_age_data(ag, n=300):
    rows = []
    for label in ["DD", "contr"]:
        for _ in range(n // 2):
            if label == "DD":
                acc_ans = np.clip(np.random.uniform(ag["acc_range"][0] - 0.1, ag["acc_range"][0] + 0.1), 0, 1)
                rt_ans  = np.random.uniform(1.5, 3.5) * ag["rt_mult"]
                wm_k    = max(1, np.random.randint(ag["wm_range"][0] - 1, ag["wm_range"][0] + 1))
                acc_sym = np.clip(np.random.uniform(ag["acc_range"][0] - 0.1, ag["acc_range"][0] + 0.1), 0, 1)
                rt_sym  = np.random.uniform(1.2, 2.5) * ag["sym_rt_mult"]
            else:
                acc_ans = np.clip(np.random.uniform(ag["acc_range"][1] - 0.1, ag["acc_range"][1] + 0.1), 0, 1)
                rt_ans  = np.random.uniform(0.5, 1.5) * ag["rt_mult"]
                wm_k    = max(1, np.random.randint(ag["wm_range"][1] - 1, ag["wm_range"][1] + 1))
                acc_sym = np.clip(np.random.uniform(ag["acc_range"][1] - 0.1, ag["acc_range"][1] + 0.1), 0, 1)
                rt_sym  = np.random.uniform(0.6, 1.2) * ag["sym_rt_mult"]
            rows.append([acc_ans, rt_ans, wm_k, acc_sym, rt_sym, label])
    return pd.DataFrame(rows, columns=FEATURES + ["group"])


def train_all():
    df       = pd.read_excel(DATA_PATH)
    df_clean = df[FEATURES + ["group"]].dropna()

    for ag in AGE_GROUPS:
        syn   = generate_age_data(ag, n=300)
        combined = pd.concat([df_clean, syn], ignore_index=True)

        X = combined[FEATURES].values
        y = combined["group"].values

        le    = LabelEncoder()
        y_enc = le.fit_transform(y)

        X_tr, X_te, y_tr, y_te = train_test_split(X, y_enc, test_size=0.2, random_state=42)
        clf = RandomForestClassifier(n_estimators=200, random_state=42)
        clf.fit(X_tr, y_tr)

        acc = accuracy_score(y_te, clf.predict(X_te))
        print(f"✓ {ag['name']:12s}  accuracy={acc:.3f}")
        print(classification_report(y_te, clf.predict(X_te), target_names=le.classes_))

        pickle.dump(clf, open(os.path.join(MODEL_DIR, f"model_{ag['name']}.pkl"), "wb"))
        pickle.dump(le,  open(os.path.join(MODEL_DIR, f"label_encoder_{ag['name']}.pkl"), "wb"))

    print("\n✅ All 7 models saved to models/")


if __name__ == "__main__":
    train_all()
