from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user' # Good practice to name your table
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # ADD THIS LINE
    role = db.Column(db.String(20), nullable=False)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    contractor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Relationship: One Client can have many Workers
    workers = db.relationship('Worker', backref='client_site', lazy=True)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    contractor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Relationship: One Client can have many Workers
    workers = db.relationship('Worker', backref='client_site', lazy=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    builder_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    progress = db.Column(db.Integer, default=0) # 0-100 percentage
    status = db.Column(db.String(20), default='Open') # 'Open', 'In Progress', 'Completed'

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50)) # e.g., Mason, Plumber
    aadhar_no = db.Column(db.String(12), unique=True, nullable=False)
    city = db.Column(db.String(50))
    phone = db.Column(db.String(15))
    gender = db.Column(db.String(10))
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    contractor_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'))
    date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(10)) # 'Present' or 'Absent'