from . import db # Use relative import from the current package
from flask_login import UserMixin
from datetime import datetime
import pytz

# Helper to get current time in UTC for consistent storage
def get_utc_now():
    return datetime.now(pytz.utc)

# Sao Paulo timezone object for conversions
sao_paulo_tz = pytz.timezone('America/Sao_Paulo')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False) # Store hashed passwords
    is_admin = db.Column(db.Boolean, default=True) # All users are admin for now

    def __repr__(self):
        return f'<User {self.username}>'

class RegisteredPerson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    person_id_system = db.Column(db.String(50), unique=True, nullable=False) # System specific ID
    photo_path = db.Column(db.String(200), nullable=True) # Path to the stored photo
    face_encoding_path = db.Column(db.String(200), nullable=True) # Path to the stored face encoding
    other_data = db.Column(db.Text, nullable=True) # For any other textual data
    created_at = db.Column(db.DateTime, default=get_utc_now) # Store UTC
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now) # Store UTC

    # Relationship to access logs
    access_logs = db.relationship('AccessLog', backref='person', lazy=True)

    def __repr__(self):
        return f'<RegisteredPerson {self.name} - {self.person_id_system}>'

class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('registered_person.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=get_utc_now, nullable=False) # Store UTC
    event_type = db.Column(db.String(10), nullable=False) # 'entry' or 'exit'

    # Denormalized for easier querying on the tracking page, but could be joined
    person_name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        # Display in Sao Paulo time for __repr__ as well, assuming timestamp is UTC
        timestamp_sp = self.timestamp.replace(tzinfo=pytz.utc).astimezone(sao_paulo_tz)
        return f'<AccessLog {self.person_name} - {self.event_type} at {timestamp_sp.strftime("%Y-%m-%d %H:%M:%S %Z")}>'

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Import login_manager from __init__.py
from . import login_manager
