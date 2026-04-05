from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'builder' or 'contractor'

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
    aadhar_no = db.Column(db.String(12), unique=True, nullable=False) # Store all 12
    city = db.Column(db.String(50)) # Location
    phone = db.Column(db.String(15))
    gender = db.Column(db.String(10))
    contractor_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'))
    date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(10)) # 'Present' or 'Absent'