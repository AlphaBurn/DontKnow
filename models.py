from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)

class UserGameStat(db.Model):
    __tablename__ = 'user_game_stat'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_name = db.Column(db.String(100), nullable=False)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    user = db.relationship('User', backref=db.backref('game_stats', lazy=True))

class UniqueLocation(db.Model):
    __tablename__ = 'unique_location'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class UniqueGame(db.Model):
    __tablename__ = 'unique_game'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

class TableStatus(db.Model):
    __tablename__ = 'table_status'
    id = db.Column(db.Integer, primary_key=True)
    is_active = db.Column(db.Boolean, default=True)
    remain_active = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(100), nullable=False)
    host_name = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    ongoing_game = db.Column(db.String(100), nullable=True)
    match_state = db.Column(db.String(20), default="Waiting")
    
    attendees = db.relationship('TableAttendee', backref='table', lazy=True, cascade="all, delete-orphan")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TableAttendee(db.Model):
    __tablename__ = 'table_attendee'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table_status.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='interested')
    user = db.relationship('User')

class AnonymousPing(db.Model):
    __tablename__ = 'anonymous_pings'
    id = db.Column(db.Integer, primary_key=True)
    location_description = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)

class TableComment(db.Model):
    __tablename__ = 'table_comment'
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table_status.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('comments', lazy=True, cascade="all, delete-orphan"))
    table = db.relationship('TableStatus', backref=db.backref('comments', lazy=True, cascade="all, delete-orphan"))
    votes = db.relationship('CommentVote', backref='comment', lazy=True, cascade="all, delete-orphan")

class CommentVote(db.Model):
    __tablename__ = 'comment_vote'
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('table_comment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False) # 'like' or 'dislike'
    
    __table_args__ = (db.UniqueConstraint('comment_id', 'user_id', name='unique_comment_user_vote'),)