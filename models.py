from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)

class TableStatus(db.Model):
    __tablename__ = 'table_status'
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=True)
    location = db.Column(db.String(100), nullable=False)
    host_name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    ongoing_game = db.Column(db.String(100), nullable=True)
    match_state = db.Column(db.String(20), default="Waiting") # 'Waiting' or 'Ongoing'
    
    # Cascade deletes attendees if table is closed
    attendees = db.relationship('TableAttendee', backref='table', lazy=True, cascade="all, delete-orphan")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TableAttendee(db.Model):
    __tablename__ = 'table_attendee'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table_status.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='interested') # 'interested' or 'present'
    user = db.relationship('User')

class AnonymousPing(db.Model):
    __tablename__ = 'anonymous_pings'
    id = db.Column(db.Integer, primary_key=True)
    location_description = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)