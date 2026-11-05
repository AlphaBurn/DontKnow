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
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'tækniskólinn2026') # Change in .env

db.init_app(app)

# Mitigate spam by limiting pings to 1 per 10 minutes per IP
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

with app.app_context():
    db.create_all()

# --- AUTH DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ADMIN ROUTES ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid credentials."
    return render_template('admin.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin', methods=['GET'])
@login_required
def admin_dashboard():
    tables = TableStatus.query.order_by(TableStatus.is_active.desc()).all()
    pings = AnonymousPing.query.filter_by(resolved=False).order_by(AnonymousPing.timestamp.desc()).all()
    return render_template('admin.html', tables=tables, pings=pings)

@app.route('/admin/add_table', methods=['POST'])
@login_required
def add_table():
    location = request.form.get('location')
    host_name = request.form.get('host_name')
    if location and host_name:
        new_table = TableStatus(location=location, host_name=host_name, is_active=True, signup_count=0)
        db.session.add(new_table)
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/resolve_ping/<int:ping_id>', methods=['POST'])
@login_required
def resolve_ping(ping_id):
    ping = AnonymousPing.query.get_or_404(ping_id)
    ping.resolved = True
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/')
def index():
    status = TableStatus.query.first()
    # Check if this specific device has already sent an unresolved ping
    has_pinged = session.get('has_pinged', False)
    return render_template('index.html', status=status, has_pinged=has_pinged)

@app.route('/api/status', methods=['GET'])
def get_status():
    """Endpoint for the JavaScript frontend to poll every 30 seconds."""
    status = TableStatus.query.first()
    return jsonify({
        'is_active': status.is_active,
        'location': status.location,
        'host_name': status.host_name
    })

@app.route('/ping', methods=['POST'])
@limiter.limit("1 per 10 minutes")
def submit_ping():
    data = request.get_json()
    location_desc = data.get('location_description')
    
    if location_desc:
        new_ping = AnonymousPing(location_description=location_desc)
        db.session.add(new_ping)
        db.session.commit()
        
        # Drop a session cookie to hide the form on the frontend
        session['has_pinged'] = True
        return jsonify({"status": "success", "message": "Ping sent!"}), 200
        
    return jsonify({"status": "error", "message": "Location required."}), 400

@app.route('/admin/update', methods=['POST'])
def update_status():
    # In production, wrap this in a basic auth decorator or check a shared secret
    data = request.get_json()
    status = TableStatus.query.first()
    
    status.is_active = data.get('is_active', False)
    status.location = data.get('location', '')
    status.host_name = data.get('host_name', '')
    
    db.session.commit()
    return jsonify({"status": "updated"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
