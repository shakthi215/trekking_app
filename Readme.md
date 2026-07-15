# TrekManager — Trekking Management Application

A role-based web application built with Flask, Jinja2, Bootstrap, and SQLite.

---

## Tech Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | Python 3, Flask                   |
| Frontend   | Jinja2 templates, HTML, Bootstrap 5 |
| Database   | SQLite (file: `trekking.db`)      |
| Icons      | Bootstrap Icons (CDN)             |

No JavaScript is used for any core feature. No external database server is required.

---

## Setup Instructions

### Step 1 — Create a virtual environment
```
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### Step 2 — Install dependencies
```
pip install -r requirements.txt
```

### Step 3 — Run the application
```
python app.py
```

### Step 4 — Open in browser
```
http://127.0.0.1:5000
```

The database file `trekking.db` is created automatically on first run.
You do not need to install or configure any database server.

---

## Default Login

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | admin    | admin123  |

Staff and Users must self-register at `/register`.
Staff accounts require admin approval before login is permitted.

---

## Roles & Features

### Admin
- Dashboard with total counts (treks, users, staff, bookings)
- Add, edit, delete treks
- Assign approved staff to treks (sets status to Approved)
- Approve or blacklist staff registrations
- View and blacklist/reactivate user accounts
- Search treks, staff, users by name or ID
- View all bookings across the system

### Trek Staff
- Self-register and await admin approval
- View assigned treks on dashboard
- Update trek slot count and status (Open / Closed / Completed)
- View participant list for assigned treks

### User (Trekker)
- Self-register and login immediately
- Browse all Open treks
- Search and filter treks by name, location, difficulty
- Book treks (overbooking is prevented automatically)
- Cancel active bookings
- View booking history with statuses
- Edit personal profile

---

## Key Rules Enforced

- Users can only book treks with status `Open`
- Slots are decremented on booking and restored on cancellation
- Overbooking is blocked — slot check happens before INSERT
- Staff can only manage treks assigned to them
- Blacklisted accounts cannot log in
- Admin account is pre-seeded; no admin registration exists

---

## Database Schema

### users
| Column   | Type    | Notes                              |
|----------|---------|------------------------------------|
| id       | INTEGER | Primary key, autoincrement         |
| username | TEXT    | Unique                             |
| password | TEXT    |                                    |
| name     | TEXT    |                                    |
| email    | TEXT    |                                    |
| phone    | TEXT    |                                    |
| role     | TEXT    | admin / staff / user               |
| status   | TEXT    | active / pending / blacklisted     |

### treks
| Column     | Type    | Notes                                        |
|------------|---------|----------------------------------------------|
| id         | INTEGER | Primary key                                  |
| name       | TEXT    |                                              |
| location   | TEXT    |                                              |
| difficulty | TEXT    | Easy / Moderate / Hard                       |
| duration   | INTEGER | Days                                         |
| slots      | INTEGER | Available slots remaining                    |
| staff_id   | INTEGER | FK → users.id                                |
| status     | TEXT    | Pending / Approved / Open / Closed / Completed |
| start_date | TEXT    |                                              |
| end_date   | TEXT    |                                              |

### bookings
| Column       | Type    | Notes                          |
|--------------|---------|--------------------------------|
| id           | INTEGER | Primary key                    |
| user_id      | INTEGER | FK → users.id                  |
| trek_id      | INTEGER | FK → treks.id                  |
| booking_date | TEXT    | Defaults to current date       |
| status       | TEXT    | Booked / Cancelled / Completed |

---

## How SQLite Works (No Server Needed)

SQLite is a file-based database engine built into Python's standard library.
There is no separate process to start. `sqlite3.connect('trekking.db')` creates
the file if it does not exist, and Python handles all SQL reads and writes
directly to that file. This is why no database installation is required.