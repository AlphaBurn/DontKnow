from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class TableStatus(db.Model):
    __tablename__ = 'table_status'
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=True)
    location = db.Column(db.String(100), nullable=False) 
    host_name = db.Column(db.String(50), nullable=False) 
    people_count = db.Column(db.Integer, default=1) # Host counts as 1 person
    timeframe = db.Column(db.String(50), nullable=True) # e.g., "12:00 - 12:45"
    ongoing_game = db.Column(db.String(100), nullable=True) # e.g., "Minecraft", "Cards"
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AnonymousPing(db.Model):
    __tablename__ = 'anonymous_pings'
    id = db.Column(db.Integer, primary_key=True)
    location_description = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)