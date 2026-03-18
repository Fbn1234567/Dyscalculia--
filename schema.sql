-- Dyscalculia Detection System — Database Schema
-- Run once on your PostgreSQL database (Heroku or local)

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,
    role        VARCHAR(50)  NOT NULL DEFAULT 'Student',
    age         INTEGER      DEFAULT 10,
    teacher_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    parent_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS results (
    id             SERIAL PRIMARY KEY,
    student_email  VARCHAR(255) NOT NULL,
    age            INTEGER,
    age_group      VARCHAR(30),
    ans_acc        FLOAT,
    ans_rt         FLOAT,
    wm_k           FLOAT,
    sym_acc        FLOAT,
    sym_rt         FLOAT,
    risk_level     VARCHAR(100),
    severity       VARCHAR(50),
    confidence     FLOAT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default admin account (change password after first login!)
-- Password hash below is for "Admin@1234" — regenerate with bcrypt before production use
-- INSERT INTO users(email,password,role) VALUES('admin@school.com','<bcrypt_hash>','Admin');
