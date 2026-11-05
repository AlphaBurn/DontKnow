import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, TableStatus, AnonymousPing

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///opentable.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'tækniskólinn2026')

db.init_app(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    tables = TableStatus.query.filter_by(is_active=True).all()
    has_pinged = session.get('has_pinged', False)
    return render_template('index.html', tables=tables, has_pinged=has_pinged)

@app.route('/api/status', methods=['GET'])
def get_status():
    tables = TableStatus.query.filter_by(is_active=True).all()
    tables_data = []
    for t in tables:
        tables_data.append({
            'id': t.id,
            'location': t.location,
            'host_name': t.host_name,
            'people_count': t.people_count,
            'timeframe': t.timeframe,
            'ongoing_game': t.ongoing_game
        })
    return jsonify({'tables': tables_data})

@app.route('/ping', methods=['POST'])
@limiter.limit("2 per 10 minutes")
def submit_ping():
    data = request.get_json()
    if data.get('location_description'):
        new_ping = AnonymousPing(location_description=data['location_description'])
        db.session.add(new_ping)
        db.session.commit()
        session['has_pinged'] = True
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 400

# --- ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin.html', error="Invalid credentials.")
    return render_template('admin.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin', methods=['GET'])
@login_required
def admin_dashboard():
    tables = TableStatus.query.filter_by(is_active=True).all()
    pings = AnonymousPing.query.filter_by(resolved=False).order_by(AnonymousPing.timestamp.desc()).all()
    return render_template('admin.html', tables=tables, pings=pings)

@app.route('/admin/add_table', methods=['POST'])
@login_required
def add_table():
    new_table = TableStatus(
        location=request.form.get('location'),
        host_name=request.form.get('host_name'),
        timeframe=request.form.get('timeframe'),
        ongoing_game=request.form.get('ongoing_game'),
        people_count=request.form.get('people_count', 1, type=int),
        is_active=True
    )
    db.session.add(new_table)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/table/<int:table_id>/adjust', methods=['POST'])
@login_required
def adjust_people(table_id):
    table = TableStatus.query.get_or_404(table_id)
    action = request.form.get('action')
    if action == 'add':
        table.people_count += 1
    elif action == 'remove' and table.people_count > 0:
        table.people_count -= 1
    elif action == 'close':
        table.is_active = False
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resolve_ping/<int:ping_id>', methods=['POST'])
@login_required
def resolve_ping(ping_id):
    ping = AnonymousPing.query.get_or_404(ping_id)
    table_id = request.form.get('table_id')
    
    # Mark ping as resolved and add the person to the selected table
    ping.resolved = True
    if table_id:
        table = TableStatus.query.get(table_id)
        if table:
            table.people_count += 1
            
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)