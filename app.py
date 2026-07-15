from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import init_db, get_db, close_db
from functools import wraps
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'trek_secret_key'
app.permanent_session_lifetime = timedelta(days=30)
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

def valid_phone(phone):
    return phone == '' or (phone.isdigit() and len(phone) == 10)

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
            session.permanent = bool(request.form.get('remember'))
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
        if not valid_phone(phone):
            flash('Phone number must be 10 digits.')
            return render_template('register.html')
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
    recent_bookings = db.execute('''SELECT b.*, u.name as user_name, t.name as trek_name
                                    FROM bookings b JOIN users u ON b.user_id=u.id
                                    JOIN treks t ON b.trek_id=t.id
                                    ORDER BY b.id DESC LIMIT 5''').fetchall()
    return render_template('admin/dashboard.html', treks=treks, users=users, staff=staff, bookings=bookings, recent_bookings=recent_bookings)

@app.route('/admin/treks', methods=['GET', 'POST'])
@login_required('admin')
def admin_treks():
    db = get_db()
    if request.method == 'POST':
        db.execute('''INSERT INTO treks (name, location, difficulty, duration, slots, start_date, end_date, status, staff_id, description)
                      VALUES (?,?,?,?,?,?,?,?,?,?)''',
                   (request.form['name'], request.form['location'], request.form['difficulty'],
                    request.form['duration'], request.form['slots'], request.form['start_date'],
                    request.form['end_date'], request.form.get('status', 'Pending'),
                    request.form.get('staff_id') or None, request.form.get('description', '')))
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

@app.route('/admin/treks/add', methods=['GET', 'POST'])
@login_required('admin')
def admin_add_trek():
    db = get_db()
    if request.method == 'POST':
        return admin_treks()
    all_staff = db.execute('SELECT id, name FROM users WHERE role="staff" AND status="active"').fetchall()
    return render_template('admin/edit_trek.html', trek=None, all_staff=all_staff, title='Add New Trek')

@app.route('/admin/treks/edit/<int:tid>', methods=['GET', 'POST'])
@login_required('admin')
def admin_edit_trek(tid):
    db = get_db()
    if request.method == 'POST':
        db.execute('''UPDATE treks SET name=?, location=?, difficulty=?, duration=?, slots=?,
                      start_date=?, end_date=?, status=?, staff_id=?, description=? WHERE id=?''',
                   (request.form['name'], request.form['location'], request.form['difficulty'],
                    request.form['duration'], request.form['slots'], request.form['start_date'],
                    request.form['end_date'], request.form['status'], request.form.get('staff_id') or None,
                    request.form.get('description', ''), tid))
        db.commit()
        flash('Trek updated.')
        return redirect(url_for('admin_treks'))
    trek = db.execute('SELECT * FROM treks WHERE id=?', (tid,)).fetchone()
    all_staff = db.execute('SELECT id, name FROM users WHERE role="staff" AND status="active"').fetchall()
    return render_template('admin/edit_trek.html', trek=trek, all_staff=all_staff, title='Edit Trek')

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
    staff_id = request.form.get('staff_id')
    staff = db.execute('SELECT id FROM users WHERE id=? AND role="staff" AND status="active"', (staff_id,)).fetchone()
    if not staff:
        flash('Select an approved staff member.')
        return redirect(url_for('admin_treks'))
    db.execute('UPDATE treks SET staff_id=?, status="Approved" WHERE id=?', (staff_id, tid))
    db.commit()
    flash('Staff assigned and trek approved.')
    return redirect(url_for('admin_treks'))

@app.route('/admin/staff')
@login_required('admin')
def admin_staff():
    db = get_db()
    q = request.args.get('q', '')
    status = request.args.get('status', 'pending')
    counts = {r['status']: r['c'] for r in db.execute('SELECT status, COUNT(*) c FROM users WHERE role="staff" GROUP BY status')}
    base = 'SELECT * FROM users WHERE role="staff"'
    params = []
    if status:
        base += ' AND status=?'
        params.append(status)
    if q:
        base += ' AND (name LIKE ? OR CAST(id AS TEXT) LIKE ?)'
        params += [f'%{q}%', f'%{q}%']
    staff = db.execute(base, params).fetchall()
    return render_template('admin/staff.html', staff=staff, q=q, status=status, counts=counts)

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
        users = db.execute('SELECT * FROM users WHERE role="user" AND (name LIKE ? OR CAST(id AS TEXT) LIKE ?)', (f'%{q}%', f'%{q}%')).fetchall()
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

@app.route('/admin/search')
@login_required('admin')
def admin_search():
    db = get_db()
    q = request.args.get('q', '')
    like = f'%{q}%'
    treks = users = staff = []
    if q:
        treks = db.execute('SELECT * FROM treks WHERE name LIKE ? OR location LIKE ? OR CAST(id AS TEXT) LIKE ?', (like, like, like)).fetchall()
        users = db.execute('SELECT * FROM users WHERE role="user" AND (name LIKE ? OR username LIKE ? OR CAST(id AS TEXT) LIKE ?)', (like, like, like)).fetchall()
        staff = db.execute('SELECT * FROM users WHERE role="staff" AND (name LIKE ? OR username LIKE ? OR CAST(id AS TEXT) LIKE ?)', (like, like, like)).fetchall()
    return render_template('admin/search.html', q=q, treks=treks, users=users, staff=staff)

@app.route('/admin/reports')
@login_required('admin')
def admin_reports():
    db = get_db()
    popular = db.execute('''SELECT t.name, t.location, COUNT(b.id) total
                            FROM treks t LEFT JOIN bookings b ON b.trek_id=t.id
                            GROUP BY t.id ORDER BY total DESC, t.name LIMIT 5''').fetchall()
    history = db.execute('''SELECT b.*, u.name user_name, t.name trek_name, t.start_date, t.end_date
                            FROM bookings b JOIN users u ON u.id=b.user_id
                            JOIN treks t ON t.id=b.trek_id
                            WHERE b.status IN ("Completed","Cancelled")
                            ORDER BY b.booking_date DESC''').fetchall()
    return render_template('admin/reports.html', popular=popular, history=history)

@app.route('/admin/settings')
@login_required('admin')
def admin_settings():
    db = get_db()
    admin = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    counts = {r['role']: r['c'] for r in db.execute('SELECT role, COUNT(*) c FROM users GROUP BY role')}
    trek_status = {r['status']: r['c'] for r in db.execute('SELECT status, COUNT(*) c FROM treks GROUP BY status')}
    return render_template('admin/settings.html', admin=admin, counts=counts, trek_status=trek_status)

# ---- STAFF ROUTES ----
@app.route('/staff/dashboard')
@login_required('staff')
def staff_dashboard(active='dashboard'):
    db = get_db()
    treks = db.execute('''SELECT t.*, COUNT(b.id) participants
                          FROM treks t LEFT JOIN bookings b ON b.trek_id=t.id AND b.status="Booked"
                          WHERE t.staff_id=? GROUP BY t.id''', (session['user_id'],)).fetchall()
    total_participants = sum(t['participants'] for t in treks)
    open_treks = sum(1 for t in treks if t['status'] == 'Open')
    return render_template('staff/dashboard.html', treks=treks, total_participants=total_participants, open_treks=open_treks, active=active)

@app.route('/staff/treks')
@login_required('staff')
def staff_treks():
    return staff_dashboard('treks')

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
        if request.form['status'] == 'Completed':
            db.execute('UPDATE bookings SET status="Completed" WHERE trek_id=? AND status="Booked"', (tid,))
        db.commit()
        flash('Trek updated.')
    participants = db.execute('''SELECT u.name, u.email, u.phone, b.booking_date, b.status
                                 FROM bookings b JOIN users u ON b.user_id=u.id
                                 WHERE b.trek_id=?''', (tid,)).fetchall()
    trek = db.execute('SELECT * FROM treks WHERE id=?', (tid,)).fetchone()
    return render_template('staff/trek.html', trek=trek, participants=participants)

@app.route('/staff/participants')
@login_required('staff')
def staff_participants():
    db = get_db()
    participants = db.execute('''SELECT t.name trek_name, u.name, u.email, u.phone, b.booking_date, b.status
                                 FROM bookings b JOIN users u ON b.user_id=u.id
                                 JOIN treks t ON b.trek_id=t.id
                                 WHERE t.staff_id=? ORDER BY t.name, u.name''', (session['user_id'],)).fetchall()
    return render_template('staff/participants.html', participants=participants)

@app.route('/staff/profile', methods=['GET', 'POST'])
@login_required('staff')
def staff_profile():
    db = get_db()
    if request.method == 'POST':
        if not valid_phone(request.form['phone']):
            flash('Phone number must be 10 digits.')
            return redirect(url_for('staff_profile'))
        db.execute('UPDATE users SET name=?, email=?, phone=? WHERE id=?',
                   (request.form['name'], request.form['email'], request.form['phone'], session['user_id']))
        db.commit()
        flash('Profile updated.')
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    return render_template('staff/profile.html', user=user)

# ---- USER ROUTES ----
@app.route('/user/dashboard')
@login_required('user')
def user_dashboard():
    db = get_db()
    difficulty = request.args.get('difficulty', '')
    location = request.args.get('location', '')
    query, params = 'SELECT * FROM treks WHERE status="Open"', []
    if difficulty:
        query += ' AND difficulty=?'
        params.append(difficulty)
    if location:
        query += ' AND location=?'
        params.append(location)
    treks = db.execute(query, params).fetchall()
    locations = db.execute('SELECT DISTINCT location FROM treks WHERE status="Open" AND location!=""').fetchall()
    bookings = db.execute('''SELECT b.*, t.name as trek_name, t.location, t.start_date, t.status as trek_status
                             FROM bookings b JOIN treks t ON b.trek_id=t.id
                             WHERE b.user_id=?''', (session['user_id'],)).fetchall()
    return render_template('user/dashboard.html', treks=treks, bookings=bookings, difficulty=difficulty, location=location, locations=locations)

@app.route('/user/bookings')
@login_required('user')
def user_bookings():
    db = get_db()
    bookings = db.execute('''SELECT b.*, t.name trek_name, t.start_date, t.end_date, t.location
                             FROM bookings b JOIN treks t ON b.trek_id=t.id
                             WHERE b.user_id=? AND b.status!="Completed" ORDER BY b.id DESC''', (session['user_id'],)).fetchall()
    return render_template('user/bookings.html', bookings=bookings)

@app.route('/user/history')
@login_required('user')
def user_history():
    db = get_db()
    bookings = db.execute('''SELECT b.*, t.name trek_name, t.start_date, t.end_date
                             FROM bookings b JOIN treks t ON b.trek_id=t.id
                             WHERE b.user_id=? AND (b.status="Completed" OR t.status="Completed")
                             ORDER BY t.end_date DESC''', (session['user_id'],)).fetchall()
    return render_template('user/history.html', bookings=bookings)

@app.route('/user/trek/<int:tid>')
@login_required('user')
def user_trek_detail(tid):
    db = get_db()
    trek = db.execute('SELECT * FROM treks WHERE id=?', (tid,)).fetchone()
    if not trek:
        flash('Trek not found.')
        return redirect(url_for('user_treks'))
    return render_template('user/trek_detail.html', trek=trek)

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
        if not valid_phone(request.form['phone']):
            flash('Phone number must be 10 digits.')
            return redirect(url_for('user_profile'))
        db.execute('UPDATE users SET name=?, email=?, phone=? WHERE id=?',
                   (request.form['name'], request.form['email'], request.form['phone'], session['user_id']))
        db.commit()
        flash('Profile updated.')
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    return render_template('user/profile.html', user=user)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
