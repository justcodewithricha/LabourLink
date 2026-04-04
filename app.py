from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import session, flash
app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
# Replace 'admin123' with the simple password you set in pgAdmin/DBeaver
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:new123@127.0.0.1:5432/labourlink'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'builder' or 'contractor'

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50)) 
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

# Create tables automatically
with app.app_context():
    db.create_all()

# Secret key is required for sessions (login memory)
app.secret_key = 'super_secret_key_for_labourlink'


# --- ROUTES ---

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/builder/enroll')
def builder_enroll():
    return "<h1>Builder Registration Page</h1><p>Working on this soon!</p>"



@app.route('/contractor/dashboard')
def contractor_dashboard():
    # Currently fetching all workers (In future, filter by logged-in contractor)
    workers = Worker.query.all()
    return render_template('contractor/dashboard.html', workers=workers)

@app.route('/contractor/enroll', methods=['GET', 'POST'])
def contractor_enroll():
    if request.method == 'POST':
        username = request.form.get('username')
        # In a real app, we would hash the password!
        
        # Save to PostgreSQL User table
        new_user = User(username=username, role='contractor')
        db.session.add(new_user)
        db.session.commit()
        
        return redirect(url_for('contractor_dashboard'))
        
    return render_template('contractor/enroll.html')

@app.route('/contractor/register-worker', methods=['GET', 'POST'])
def register_worker():
    if request.method == 'POST':
        # Collect data from form
        new_worker = Worker(
            name=request.form.get('name'),
            role=request.form.get('role'),
            aadhar_no=request.form.get('aadhar'),
            city=request.form.get('city'),
            phone=request.form.get('phone'),
            gender=request.form.get('gender'),
            contractor_id=session.get('user_id') # Links worker to logged-in contractor
        )
        db.session.add(new_worker)
        db.session.commit()
        return redirect(url_for('manage_workers'))
        
    return render_template('contractor/register.html')

@app.route('/contractor/attendance', methods=['GET', 'POST'])
def track_attendance():
    today = datetime.today().date()
    workers = Worker.query.all()

    if request.method == 'POST':
        for worker in workers:
            status = request.form.get(f"status_{worker.id}")
            if status:
                new_entry = Attendance(worker_id=worker.id, date=today, status=status)
                db.session.add(new_entry)
        db.session.commit()
        return redirect(url_for('contractor_dashboard'))

    return render_template('contractor/attendance.html', workers=workers, date=today)

@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if user exists
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            return "User already exists! <a href='/login'>Login here</a>"

        # Create user
        new_user = User(username=username, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        print(f"DEBUG: New {role} created: {username}")
        return redirect(url_for('login'))
        
    return render_template('auth/signup.html', role=role)
@app.route('/contractor/manage-workers')
def manage_workers():
    workers = Worker.query.all()
    return render_template('contractor/manage_workers.html', workers=workers)

@app.route('/contractor/worker/<int:worker_id>')
def worker_profile(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    return render_template('contractor/worker_profile.html', worker=worker)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"DEBUG: User {username} logged in as {user.role}")
            if user.role == 'contractor':
                return redirect(url_for('contractor_dashboard'))
            else:
                return "Builder Dashboard coming soon!"
        
        return "Invalid Username. <a href='/login'>Try again</a>"
    
    
    
    # If it's a GET request, we MUST show the login page
    return render_template('auth/login.html')



# --- START THE SERVER ---
if __name__ == '__main__':
    app.run(debug=True)