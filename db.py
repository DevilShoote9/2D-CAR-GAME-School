# db.py
import sqlite3 as sq
import hashlib
from datetime import datetime
import os

DB = 'car_game.db'

def init_db():
    if not os.path.exists(DB):
        con = sq.connect(DB)
        c = con.cursor()
        c.execute('''
            CREATE TABLE users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                selected_car TEXT DEFAULT 'player1.png'
            )
        ''')
        c.execute('''
            CREATE TABLE scores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                score INTEGER,
                difficulty TEXT,
                created_at TEXT
            )
        ''')
        con.commit()
        con.close()
    else:
        # ensure tables exist if DB file exists
        con = sq.connect(DB)
        c = con.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                selected_car TEXT DEFAULT 'player1.png'
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS scores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                score INTEGER,
                difficulty TEXT,
                created_at TEXT
            )
        ''')
        con.commit()
        con.close()

def _hash(username, password):
    # simple salted hash: pbkdf2 with username as salt
    salt = username.encode('utf-8')
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000).hex()

def add_user(username, password):
    h = _hash(username, password)
    con = sq.connect(DB)
    c = con.cursor()
    try:
        c.execute('INSERT INTO users(username,password) VALUES (?,?)', (username, h))
        con.commit()
        return True
    except sq.IntegrityError:
        return False
    finally:
        con.close()

def verify_user(username, password):
    h = _hash(username, password)
    con = sq.connect(DB)
    c = con.cursor()
    c.execute('SELECT id, selected_car FROM users WHERE username=? AND password=?', (username, h))
    r = c.fetchone()
    con.close()
    return r  # None or (id, selected_car)

def set_user_car(user_id, filename):
    con = sq.connect(DB)
    c = con.cursor()
    c.execute('UPDATE users SET selected_car=? WHERE id=?', (filename, user_id))
    con.commit()
    con.close()

def save_score(user_id, score, difficulty):
    con = sq.connect(DB)
    c = con.cursor()
    c.execute('INSERT INTO scores (user_id, score, difficulty, created_at) VALUES (?,?,?,?)',
              (user_id, score, difficulty, datetime.utcnow().isoformat()))
    con.commit()
    con.close()

def top_scores(limit=10):
    con = sq.connect(DB)
    c = con.cursor()
    c.execute('''
        SELECT u.username, s.score, s.difficulty, s.created_at
        FROM scores s JOIN users u ON s.user_id = u.id
        ORDER BY s.score DESC LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    con.close()
    return rows
