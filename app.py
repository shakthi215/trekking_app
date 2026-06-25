from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import init_db, get_db, close_db
from functools import wraps

app = Flask(__name__)
app.secret_key = 'trek_secret_key'
app.teardown_appcontext(close_db)

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Access denied.')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password)).fetchone()
        if user:
            if user['status'] == 'blacklisted':
                flash('Your account has been blacklisted.')
                return render_template('login.html')
            if user['role'] == 'staff' and user['status'] == 'pending':
                flash('Awaiting admin approval.')
                return render_template('login.html')
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['username'] = user['username']
            return redirect(url_for(user['role'] + '_dashboard'))
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        email = request.form['email']
        phone = request.form.get('phone', '')
        role = request.form['role']
        if role not in ('user', 'staff'):
            flash('Invalid role.')
            return render_template('register.html')
        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
        if existing:
            flash('Username already taken.')
            return render_template('register.html')
        status = 'pending' if role == 'staff' else 'active'
        db.execute('INSERT INTO users (username, password, name, email, phone, role, status) VALUES (?,?,?,?,?,?,?)',
                   (username, password, name, email, phone, role, status))
        db.commit()
        flash('Registration successful! Please login.' if role == 'user' else 'Registration submitted. Awaiting admin approval.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---- ADMIN ROUTES ----
@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    db = get_db()
    treks = db.execute('SELECT COUNT(*) as c FROM treks').fetchone()['c']
    users = db.execute('SELECT COUNT(*) as c FROM users WHERE role="user"').fetchone()['c']
    staff = db.execute('SELECT COUNT(*) as c FROM users WHERE role="staff"').fetchone()['c']
    bookings = db.execute('SELECT COUNT(*) as c FROM bookings').fetchone()['c']
    return render_template('admin/dashboard.html', treks=treks, users=users, staff=staff, bookings=bookings)

@app.route('/admin/treks', methods=['GET', 'POST'])
@login_required('admin')
def admin_treks():
    db = get_db()
    if request.method == 'POST':
        db.execute('''INSERT INTO treks (name, location, difficulty, duration, slots, start_date, end_date, status)
                      VALUES (?,?,?,?,?,?,?,?)''',
                   (request.form['name'], request.form['location'], request.form['difficulty'],
                    request.form['duration'], request.form['slots'], request.form['start_date'],
                    request.form['end_date'], 'Pending'))
        db.commit()
        flash('Trek added.')
        return redirect(url_for('admin_treks'))
    q = request.args.get('q', '')
    all_staff = db.execute('SELECT id, name FROM users WHERE role="staff" AND status="active"').fetchall()
    if q:
        treks = db.execute('SELECT t.*, u.name as staff_name FROM treks t LEFT JOIN users u ON t.staff_id=u.id WHERE t.name LIKE ? OR CAST(t.id AS TEXT) LIKE ?',
                           (f'%{q}%', f'%{q}%')).fetchall()
    else:
        treks = db.execute('SELECT t.*, u.name as staff_name FROM treks t LEFT JOIN users u ON t.staff_id=u.id').fetchall()
    return render_template('admin/treks.html', treks=treks, q=q, all_staff=all_staff)

@app.route('/admin/treks/edit/<int:tid>', methods=['GET', 'POST'])
@login_required('admin')
def admin_edit_trek(tid):
    db = get_db()
    if request.method == 'POST':
        db.execute('''UPDATE treks SET name=?, location=?, difficulty=?, duration=?, slots=?,
                      start_date=?, end_date=?, status=? WHERE id=?''',
                   (request.form['name'], request.form['location'], request.form['difficulty'],
                    request.form['duration'], request.form['slots'], request.form['start_date'],
                    request.form['end_date'], request.form['status'], tid))
        db.commit()
        flash('Trek updated.')
        return redirect(url_for('admin_treks'))
    trek = db.execute('SELECT * FROM treks WHERE id=?', (tid,)).fetchone()
    return render_template('admin/edit_trek.html', trek=trek)

@app.route('/admin/treks/delete/<int:tid>')
@login_required('admin')
def admin_delete_trek(tid):
    db = get_db()
    db.execute('DELETE FROM treks WHERE id=?', (tid,))
    db.commit()
    flash('Trek removed.')
    return redirect(url_for('admin_treks'))

@app.route('/admin/treks/assign/<int:tid>', methods=['POST'])
@login_required('admin')
def admin_assign_staff(tid):
    db = get_db()
    db.execute('UPDATE treks SET staff_id=?, status="Approved" WHERE id=?', (request.form['staff_id'], tid))
    db.commit()
    flash('Staff assigned and trek approved.')
    return redirect(url_for('admin_treks'))

@app.route('/admin/staff')
@login_required('admin')
def admin_staff():
    db = get_db()
    q = request.args.get('q', '')
    if q:
        staff = db.execute('SELECT * FROM users WHERE role="staff" AND (name LIKE ? OR id LIKE ?)', (f'%{q}%', f'%{q}%')).fetchall()
    else:
        staff = db.execute('SELECT * FROM users WHERE role="staff"').fetchall()
    return render_template('admin/staff.html', staff=staff, q=q)

@app.route('/admin/staff/approve/<int:uid>')
@login_required('admin')
def admin_approve_staff(uid):
    db = get_db()
    db.execute('UPDATE users SET status="active" WHERE id=?', (uid,))
    db.commit()
    flash('Staff approved.')
    return redirect(url_for('admin_staff'))

@app.route('/admin/users')
@login_required('admin')
def admin_users():
    db = get_db()
    q = request.args.get('q', '')
    if q:
        users = db.execute('SELECT * FROM users WHERE role="user" AND (name LIKE ? OR id LIKE ?)', (f'%{q}%', f'%{q}%')).fetchall()
    else:
        users = db.execute('SELECT * FROM users WHERE role="user"').fetchall()
    return render_template('admin/users.html', users=users, q=q)

@app.route('/admin/blacklist/<int:uid>')
@login_required('admin')
def admin_blacklist(uid):
    db = get_db()
    db.execute('UPDATE users SET status="blacklisted" WHERE id=?', (uid,))
    db.commit()
    flash('User blacklisted.')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/unblacklist/<int:uid>')
@login_required('admin')
def admin_unblacklist(uid):
    db = get_db()
    db.execute('UPDATE users SET status="active" WHERE id=?', (uid,))
    db.commit()
    flash('User reactivated.')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/bookings')
@login_required('admin')
def admin_bookings():
    db = get_db()
    bookings = db.execute('''SELECT b.*, u.name as user_name, t.name as trek_name
                             FROM bookings b JOIN users u ON b.user_id=u.id
                             JOIN treks t ON b.trek_id=t.id''').fetchall()
    return render_template('admin/bookings.html', bookings=bookings)

# ---- STAFF ROUTES ----
@app.route('/staff/dashboard')
@login_required('staff')
def staff_dashboard():
    db = get_db()
    treks = db.execute('SELECT * FROM treks WHERE staff_id=?', (session['user_id'],)).fetchall()
    return render_template('staff/dashboard.html', treks=treks)

@app.route('/staff/trek/<int:tid>', methods=['GET', 'POST'])
@login_required('staff')
def staff_trek(tid):
    db = get_db()
    trek = db.execute('SELECT * FROM treks WHERE id=? AND staff_id=?', (tid, session['user_id'])).fetchone()
    if not trek:
        flash('Access denied.')
        return redirect(url_for('staff_dashboard'))
    if request.method == 'POST':
        db.execute('UPDATE treks SET slots=?, status=? WHERE id=?',
                   (request.form['slots'], request.form['status'], tid))
        db.commit()
        flash('Trek updated.')
    participants = db.execute('''SELECT u.name, u.email, u.phone, b.booking_date, b.status
                                 FROM bookings b JOIN users u ON b.user_id=u.id
                                 WHERE b.trek_id=?''', (tid,)).fetchall()
    trek = db.execute('SELECT * FROM treks WHERE id=?', (tid,)).fetchone()
    return render_template('staff/trek.html', trek=trek, participants=participants)

# ---- USER ROUTES ----
@app.route('/user/dashboard')
@login_required('user')
def user_dashboard():
    db = get_db()
    treks = db.execute('SELECT * FROM treks WHERE status="Open"').fetchall()
    bookings = db.execute('''SELECT b.*, t.name as trek_name, t.location, t.start_date, t.status as trek_status
                             FROM bookings b JOIN treks t ON b.trek_id=t.id
                             WHERE b.user_id=?''', (session['user_id'],)).fetchall()
    return render_template('user/dashboard.html', treks=treks, bookings=bookings)

@app.route('/user/treks')
@login_required('user')
def user_treks():
    db = get_db()
    q = request.args.get('q', '')
    difficulty = request.args.get('difficulty', '')
    location = request.args.get('location', '')
    query = 'SELECT * FROM treks WHERE status="Open"'
    params = []
    if q:
        query += ' AND (name LIKE ? OR location LIKE ?)'
        params += [f'%{q}%', f'%{q}%']
    if difficulty:
        query += ' AND difficulty=?'
        params.append(difficulty)
    if location:
        query += ' AND location LIKE ?'
        params.append(f'%{location}%')
    treks = db.execute(query, params).fetchall()
    return render_template('user/treks.html', treks=treks, q=q, difficulty=difficulty, location=location)

@app.route('/user/book/<int:tid>', methods=['POST'])
@login_required('user')
def user_book(tid):
    db = get_db()
    trek = db.execute('SELECT * FROM treks WHERE id=?', (tid,)).fetchone()
    if not trek or trek['status'] != 'Open':
        flash('Trek not available for booking.')
        return redirect(url_for('user_treks'))
    if trek['slots'] <= 0:
        flash('No slots available.')
        return redirect(url_for('user_treks'))
    existing = db.execute('SELECT id FROM bookings WHERE user_id=? AND trek_id=? AND status="Booked"',
                          (session['user_id'], tid)).fetchone()
    if existing:
        flash('Already booked.')
        return redirect(url_for('user_treks'))
    db.execute('INSERT INTO bookings (user_id, trek_id, status) VALUES (?,?,"Booked")', (session['user_id'], tid))
    db.execute('UPDATE treks SET slots=slots-1 WHERE id=?', (tid,))
    db.commit()
    flash('Trek booked successfully!')
    return redirect(url_for('user_dashboard'))

@app.route('/user/cancel/<int:bid>', methods=['POST'])
@login_required('user')
def user_cancel(bid):
    db = get_db()
    booking = db.execute('SELECT * FROM bookings WHERE id=? AND user_id=?', (bid, session['user_id'])).fetchone()
    if booking and booking['status'] == 'Booked':
        db.execute('UPDATE bookings SET status="Cancelled" WHERE id=?', (bid,))
        db.execute('UPDATE treks SET slots=slots+1 WHERE id=?', (booking['trek_id'],))
        db.commit()
        flash('Booking cancelled.')
    return redirect(url_for('user_dashboard'))

@app.route('/user/profile', methods=['GET', 'POST'])
@login_required('user')
def user_profile():
    db = get_db()
    if request.method == 'POST':
        db.execute('UPDATE users SET name=?, email=?, phone=? WHERE id=?',
                   (request.form['name'], request.form['email'], request.form['phone'], session['user_id']))
        db.commit()
        flash('Profile updated.')
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    return render_template('user/profile.html', user=user)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
