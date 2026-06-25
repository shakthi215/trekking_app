import sqlite3
from flask import g
import os

DATABASE = 'trekking.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    if os.path.exists(DATABASE):
        return
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            role TEXT NOT NULL CHECK(role IN ("admin","staff","user")),
            status TEXT DEFAULT "active"
        );

        CREATE TABLE IF NOT EXISTS treks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            difficulty TEXT CHECK(difficulty IN ("Easy","Moderate","Hard")),
            duration INTEGER,
            slots INTEGER DEFAULT 0,
            staff_id INTEGER REFERENCES users(id),
            status TEXT DEFAULT "Pending",
            start_date TEXT,
            end_date TEXT
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            trek_id INTEGER REFERENCES treks(id),
            booking_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT "Booked"
        );

        INSERT OR IGNORE INTO users (username, password, name, email, role, status)
        VALUES ("admin", "admin123", "Admin", "admin@trek.com", "admin", "active");
    ''')
    conn.commit()
    conn.close()

def close_db(e=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
