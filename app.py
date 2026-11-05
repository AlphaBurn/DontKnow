import os
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, TableStatus, AnonymousPing, User, TableAttendee

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///opentable.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'tækniskólinn2026')

db.init_app(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day"])

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_timing_status(start, end):
    now = datetime.utcnow()
    if now < start: return "Scheduled"
    if now > end: return "Ended"
    return "Live Now"

# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    username = session.get('username')
    return render_template('index.html', username=username)

@app.route('/set_username', methods=['POST'])
def set_username():
    name = request.json.get('username', '').strip()
    if name:
        user = User.query.filter_by(username=name).first()
        if not user:
            user = User(username=name)
            db.session.add(user)
            db.session.commit()
        session['username'] = name
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/users/search', methods=['GET'])
def search_users():
    """Returns a list of usernames matching the search query for autocomplete."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    
    # ilike handles case-insensitive matching, allowing 'arna' to find 'ArnarXD'
    users = User.query.filter(User.username.ilike(f"{q}%")).limit(10).all()
    return jsonify([u.username for u in users])

@app.route('/api/status', methods=['GET'])
def get_status():
    tables = TableStatus.query.filter_by(is_active=True).all()
    tables_data = []
    
    for t in tables:
        present = [a.user.username for a in t.attendees if a.status == 'present']
        interested = [a.user.username for a in t.attendees if a.status == 'interested']
        
        tables_data.append({
            'id': t.id,
            'location': t.location,
            'timing_status': get_timing_status(t.start_time, t.end_time),
            'time_range': f"{t.start_time.strftime('%H:%M')} - {t.end_time.strftime('%H:%M')}",
            'ongoing_game': t.ongoing_game,
            'match_state': t.match_state,
            'present': present,
            'interested': interested
        })
        
    leaderboard = User.query.order_by(User.wins.desc()).limit(10).all()
    ldb_data = [{'username': u.username, 'wins': u.wins, 'losses': u.losses} for u in leaderboard]
    
    return jsonify({'tables': tables_data, 'leaderboard': ldb_data})

@app.route('/join_table/<int:table_id>', methods=['POST'])
def join_table(table_id):
    username = session.get('username')
    if not username: return jsonify({"error": "No username"}), 403
    
    user = User.query.filter_by(username=username).first()
    existing = TableAttendee.query.filter_by(table_id=table_id, user_id=user.id).first()
    
    if not existing:
        db.session.add(TableAttendee(table_id=table_id, user_id=user.id, status='interested'))
        db.session.commit()
    return jsonify({"status": "success"})

# --- ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
    return render_template('admin.html')

@app.route('/admin', methods=['GET'])
@login_required
def admin_dashboard():
    tables = TableStatus.query.filter_by(is_active=True).all()
    all_users = User.query.order_by(User.username).all()
    return render_template('admin.html', tables=tables, all_users=all_users)

@app.route('/admin/add_table', methods=['POST'])
@login_required
def add_table():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    start_dt = datetime.strptime(f"{today} {request.form.get('start_time')}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{today} {request.form.get('end_time')}", "%Y-%m-%d %H:%M")
    
    # Ensure the host exists in the User DB so their stats track properly if they play
    host_name = request.form.get('host_name').strip()
    host_user = User.query.filter_by(username=host_name).first()
    if not host_user:
        db.session.add(User(username=host_name))
        db.session.commit()
    
    new_table = TableStatus(
        location=request.form.get('location'),
        host_name=host_name,
        start_time=start_dt,
        end_time=end_dt,
        ongoing_game=request.form.get('ongoing_game')
    )
    db.session.add(new_table)
    db.session.commit()
    
    # Automatically add the host to the table as 'present'
    host_user = User.query.filter_by(username=host_name).first()
    db.session.add(TableAttendee(table_id=new_table.id, user_id=host_user.id, status='present'))
    db.session.commit()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/attendee/<int:att_id>/<action>', methods=['POST'])
@login_required
def manage_attendee(att_id, action):
    att = TableAttendee.query.get_or_404(att_id)
    if action == 'accept':
        att.status = 'present'
    elif action == 'remove':
        db.session.delete(att)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/table/<int:table_id>/manual_add', methods=['POST'])
@login_required
def manual_add(table_id):
    user_id = request.form.get('user_id')
    if user_id:
        existing = TableAttendee.query.filter_by(table_id=table_id, user_id=user_id).first()
        if not existing:
            db.session.add(TableAttendee(table_id=table_id, user_id=user_id, status='present'))
        else:
            existing.status = 'present'
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/table/<int:table_id>/match', methods=['POST'])
@login_required
def match_state(table_id):
    table = TableStatus.query.get_or_404(table_id)
    action = request.form.get('action')
    
    if action == 'start':
        table.match_state = "Ongoing"
    elif action == 'end':
        # Handles 1 winner, multiple winners (ties/co-op), or 0 winners
        winner_names = request.form.getlist('winner_names')
        attendees = [a for a in table.attendees if a.status == 'present']
        
        for att in attendees:
            if att.user.username in winner_names:
                att.user.wins += 1
            else:
                att.user.losses += 1
                
        table.match_state = "Waiting"
    
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/table/<int:table_id>/close', methods=['POST'])
@login_required
def close_table(table_id):
    table = TableStatus.query.get_or_404(table_id)
    table.is_active = False
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)