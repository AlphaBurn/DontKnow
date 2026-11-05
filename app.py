import os
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, TableStatus, AnonymousPing, User, TableAttendee, UserGameStat, UniqueLocation, UniqueGame

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///opentable.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'taekno')

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

def calculate_points(n_players, placement):
    if n_players <= 1: return 0
    center = (n_players + 1) / 2.0
    raw_score = center - placement
    if n_players % 2 == 0:
        return int(raw_score + 0.5) if raw_score > 0 else int(raw_score - 0.5)
    return int(raw_score)

# --- PUBLIC ROUTES & APIs ---
@app.route('/')
def index():
    return render_template('index.html', username=session.get('username'))

@app.route('/set_username', methods=['POST'])
def set_username():
    name = request.json.get('username', '').strip()
    if name:
        if not User.query.filter_by(username=name).first():
            db.session.add(User(username=name))
            db.session.commit()
        session['username'] = name
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/search/<resource>', methods=['GET'])
def search_autocomplete(resource):
    q = request.args.get('q', '').strip()
    if not q: return jsonify([])
    
    if resource == 'users':
        results = User.query.filter(User.username.ilike(f"%{q}%")).limit(10).all()
        return jsonify([r.username for r in results])
    elif resource == 'locations':
        results = UniqueLocation.query.filter(UniqueLocation.name.ilike(f"%{q}%")).limit(10).all()
        return jsonify([r.name for r in results])
    elif resource == 'games':
        results = UniqueGame.query.filter(UniqueGame.name.ilike(f"%{q}%")).limit(10).all()
        return jsonify([r.name for r in results])
    return jsonify([])

@app.route('/api/status', methods=['GET'])
def get_status():
    username = session.get('username')
    tables_data = []
    
    # 1. Active Tables Data
    for t in TableStatus.query.filter_by(is_active=True).all():
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
        
    # 2. Global & Segmented Leaderboards
    ldb = {"Global": []}
    for u in User.query.order_by(User.points.desc(), User.wins.desc()).all():
        ldb["Global"].append({'username': u.username, 'wins': u.wins, 'losses': u.losses, 'points': u.points})
        
    for stat in UserGameStat.query.all():
        if stat.game_name not in ldb: ldb[stat.game_name] = []
        ldb[stat.game_name].append({
            'username': stat.user.username, 'wins': stat.wins, 'losses': stat.losses, 'points': stat.points
        })
        
    for game in ldb:
        ldb[game] = sorted(ldb[game], key=lambda x: (x['points'], x['wins']), reverse=True)

    # 3. Current User Profile Stats
    user_stats = None
    if username:
        user = User.query.filter_by(username=username).first()
        if user:
            rank = next((i+1 for i, u in enumerate(ldb["Global"]) if u['username'] == username), "-")
            wl_ratio = round(user.wins / user.losses, 2) if user.losses > 0 else user.wins
            user_stats = {'rank': rank, 'points': user.points, 'wl_ratio': wl_ratio}
            
    return jsonify({'tables': tables_data, 'leaderboards': ldb, 'user_stats': user_stats})

@app.route('/join_table/<int:table_id>', methods=['POST'])
def join_table(table_id):
    username = session.get('username')
    if not username: return jsonify({"error": "No username"}), 403
    
    user = User.query.filter_by(username=username).first()
    existing = TableAttendee.query.filter_by(table_id=table_id, user_id=user.id).first()
    
    # Toggle Logic: If they are already interested, remove them (Undo)
    if existing:
        if existing.status == 'interested':
            db.session.delete(existing)
            db.session.commit()
    else:
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

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

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
    
    host_name = request.form.get('host_name').strip()
    location_name = request.form.get('location').strip()
    game_name = request.form.get('ongoing_game').strip()
    
    # Ensure Host, Location, and Game exist in dictionaries
    host_user = User.query.filter_by(username=host_name).first()
    if not host_user:
        host_user = User(username=host_name)
        db.session.add(host_user)
        
    if not UniqueLocation.query.filter_by(name=location_name).first():
        db.session.add(UniqueLocation(name=location_name))
        
    if not UniqueGame.query.filter_by(name=game_name).first():
        db.session.add(UniqueGame(name=game_name))
        
    db.session.commit()
    
    new_table = TableStatus(location=location_name, host_name=host_name, start_time=start_dt, end_time=end_dt, ongoing_game=game_name)
    db.session.add(new_table)
    db.session.commit()
    
    db.session.add(TableAttendee(table_id=new_table.id, user_id=host_user.id, status='present'))
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
        present_attendees = [a for a in table.attendees if a.status == 'present']
        n_players = len(present_attendees)
        
        for att in present_attendees:
            # Get placement from dynamically generated form inputs
            placement_str = request.form.get(f'placement_{att.user.id}')
            if not placement_str: continue
            
            placement = int(placement_str)
            pts = calculate_points(n_players, placement)
            
            # Update Global User Stats
            att.user.points += pts
            if placement == 1: att.user.wins += 1
            else: att.user.losses += 1
            
            # Update Segmented Game Stats
            g_stat = UserGameStat.query.filter_by(user_id=att.user.id, game_name=table.ongoing_game).first()
            if not g_stat:
                g_stat = UserGameStat(user_id=att.user.id, game_name=table.ongoing_game, points=0, wins=0, losses=0)
                db.session.add(g_stat)
            g_stat.points += pts
            if placement == 1: g_stat.wins += 1
            else: g_stat.losses += 1
            
        table.match_state = "Waiting"
    
    db.session.commit()
    return redirect(url_for('admin_dashboard'))



@app.route('/api/users/search', methods=['GET'])
def search_users():
    """Returns a list of usernames matching the search query for autocomplete."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    
    # ilike handles case-insensitive matching, allowing 'arna' to find 'ArnarXD'
    users = User.query.filter(User.username.ilike(f"{q}%")).limit(10).all()
    return jsonify([u.username for u in users])






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


@app.route('/admin/table/<int:table_id>/close', methods=['POST'])
@login_required
def close_table(table_id):
    table = TableStatus.query.get_or_404(table_id)
    table.is_active = False
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)