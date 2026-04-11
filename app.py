from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Worker, Attendance, Project, Client
from datetime import datetime, timedelta

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:301365@localhost:5432/labourlink'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'super_secret_key_for_labourlink' # Required for session memory

db.init_app(app)

with app.app_context():
    db.create_all()

# --- SECURITY: THE GATEKEEPER ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("⚠️ Access Denied. Please log in to view your dashboard.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    return render_template('home.html')

# --- ROLE SELECTION ROUTE ---
# This opens the page with the "Builder" and "Contractor" cards (auth/signup.html)
@app.route('/select-role')
def select_role():
    return render_template('auth/signup.html') 

# --- AUTHENTICATION ROUTES ---
# --- THE ACTUAL SIGNUP FORM ROUTE ---
@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if request.method == 'POST': 
        username = request.form.get('username')
        password = request.form.get('password') # <-- ADDED THIS: Grab the password
        
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash("User already exists! Please log in.")
            return redirect(url_for('login'))

        # <-- ADDED THIS: Save the password to the database
        new_user = User(username=username, password=password, role=role) 
        db.session.add(new_user)
        db.session.commit()
        
        flash("Account created successfully! Please log in.")
        return redirect(url_for('login'))
        
    return render_template('auth/signup_form.html', role=role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password: 
            session['user_id'] = user.id 
            session['username'] = user.username
            session['role'] = user.role # <-- NEW: Save role for navigation logic
            if user.role == 'contractor':
                return redirect(url_for('contractor_dashboard'))
            else:
                return redirect(url_for('builder_dashboard'))
        
        flash("⚠️ Invalid Username or Password.") 
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None) 
    session.pop('username', None) # <-- NEW: Clear the username on logout
    flash("You have been successfully logged out.")
    return redirect(url_for('login'))

# --- CONTRACTOR ROUTES (SECURED) ---
@app.route('/contractor/dashboard')
@login_required
def contractor_dashboard():
    user_id = session.get('user_id')
    
    # 1. Get the last 7 days (including today)
    today = datetime.utcnow().date()
    dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    
    # Format labels for the chart (e.g., 'Mon', 'Tue')
    labels = [d.strftime('%a') for d in dates] 
    
    # 2. Get all workers belonging to this contractor
    workers = Worker.query.filter_by(contractor_id=user_id).all()
    worker_ids = [w.id for w in workers]
    
    # 3. Count 'Present' attendance for each of those 7 days
    attendance_counts = []
    if worker_ids: # Only query if the contractor actually has workers
        for d in dates:
            count = Attendance.query.filter(
                Attendance.worker_id.in_(worker_ids),
                Attendance.date == d,
                Attendance.status == 'Present'
            ).count()
            attendance_counts.append(count)
    else:
        attendance_counts = [0] * 7 # Fill with zeros if no workers

    # 4. Stat counts for the summary strip
    total_workers = len(workers)
    total_clients = Client.query.filter_by(contractor_id=user_id).count()
    today_present = Attendance.query.filter(
        Attendance.worker_id.in_(worker_ids) if worker_ids else False,
        Attendance.date == today,
        Attendance.status == 'Present'
    ).count() if worker_ids else 0

    return render_template(
        'contractor/dashboard.html', 
        labels=labels, 
        attendance_data=attendance_counts,
        total_workers=total_workers,
        total_clients=total_clients,
        today_present=today_present
    )

@app.route('/builder/my-profile')
@login_required
def builder_profile():
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    projects = Project.query.filter_by(builder_id=user_id).all()
    return render_template('builder/my_profile.html', user=user, projects=projects)

@app.route('/contractor/attendance', methods=['GET', 'POST'])
@login_required
def contractor_attendance():
    user_id = session.get('user_id')
    today_date = datetime.utcnow().date()
    
    # Fetch all workers registered under this contractor
    workers = Worker.query.filter_by(contractor_id=user_id).all()
    
    if request.method == 'POST':
        # Loop through every worker to get their radio button status from the form
        for worker in workers:
            status = request.form.get(f'status_{worker.id}')
            
            if status:
                # Check if attendance is already marked for today to prevent duplicate rows
                existing_record = Attendance.query.filter_by(
                    worker_id=worker.id, 
                    date=today_date
                ).first()
                
                if existing_record:
                    # Update existing record if they changed their mind
                    existing_record.status = status
                else:
                    # Create a brand new attendance record
                    new_attendance = Attendance(
                        worker_id=worker.id,
                        date=today_date,
                        status=status
                    )
                    db.session.add(new_attendance)
        
        # Commit all the new attendance records to PostgreSQL at once
        db.session.commit()
        flash("✅ Daily attendance has been saved successfully!")
        return redirect(url_for('contractor_dashboard'))

    # If it's a GET request, just show the page with the current date formatted nicely
    formatted_date = today_date.strftime("%B %d, %Y")
    return render_template('contractor/attendance.html', workers=workers, date=formatted_date)

@app.route('/contractor/manage-clients')
@login_required
def manage_clients():
    user_id = session.get('user_id')
    # DATA ISOLATION: Fetch only this user's clients
    clients = Client.query.filter_by(contractor_id=user_id).all() 
    return render_template('contractor/manage_clients.html', clients=clients)

@app.route('/contractor/add-client', methods=['GET', 'POST'])
@login_required
def add_client():
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        if name:
            new_client = Client(
                name=name, 
                location=location,
                contractor_id=session.get('user_id') # TAGGING OWNERSHIP
            )
            db.session.add(new_client)
            db.session.commit()
            flash("✅ New site added successfully!")
            return redirect(url_for('manage_clients'))
    return render_template('contractor/add_client.html')

@app.route('/contractor/manage-workers/<int:client_id>')
@login_required
def manage_workers(client_id):
    user_id = session.get('user_id')
    client = Client.query.get_or_404(client_id)
    
    # BOUNDARY CHECK: Does this client belong to this user?
    if client.contractor_id != user_id:
        flash("⛔ Unauthorized Access: You do not own this site registry.")
        return redirect(url_for('manage_clients'))
        
    workers = Worker.query.filter_by(client_id=client_id).all()
    return render_template('contractor/manage_workers.html', workers=workers, client=client)

@app.route('/contractor/register-worker', methods=['GET', 'POST'])
@login_required
def register_worker():
    user_id = session.get('user_id')
    clients = Client.query.filter_by(contractor_id=user_id).all() 
    
    if request.method == 'POST':
        phone = request.form.get('phone')
        aadhar = request.form.get('aadhar')
        client_id = request.form.get('client_id')
        role = request.form.get('role')
        
        if role == 'Other':
            role = request.form.get('other_role')

        if not phone or not phone.isdigit() or len(phone) != 10:
            flash("⚠️ Phone number must be exactly 10 digits (0-9).")
            return redirect(url_for('register_worker'))
            
        if not aadhar or not aadhar.isdigit() or len(aadhar) != 12:
            flash("⚠️ Aadhar number must be exactly 12 digits (0-9).")
            return redirect(url_for('register_worker'))

        if not client_id:
            flash("⚠️ Please select a Client Site for this worker.")
            return redirect(url_for('register_worker'))

        try:
            new_worker = Worker(
                name=request.form.get('name'),
                role=role,
                aadhar_no=aadhar,
                city=request.form.get('city'),
                phone=phone,
                gender=request.form.get('gender'),
                client_id=client_id,
                contractor_id=user_id # TAGGING OWNERSHIP
            )
            db.session.add(new_worker)
            db.session.commit()
            flash(f"✅ Worker successfully assigned to site.")
            return redirect(url_for('manage_clients'))
            
        except Exception as e:
            db.session.rollback()
            flash("⚠️ Error: Aadhar number might already be registered.")
            return redirect(url_for('register_worker'))
            
    return render_template('contractor/register.html', clients=clients)

@app.route('/contractor/my-profile')
@login_required
def contractor_profile():
    user_id = session.get('user_id')
    
    # 1. Fetch the logged-in user's details
    user = User.query.get_or_404(user_id)
    
    # 2. Fetch all clients tied to this contractor
    clients = Client.query.filter_by(contractor_id=user_id).all()
    
    return render_template('contractor/my_profile.html', user=user, clients=clients)

@app.route('/contractor/worker/<int:worker_id>')
@login_required
def worker_profile(worker_id):
    user_id = session.get('user_id')
    worker = Worker.query.get_or_404(worker_id)
    
    # BOUNDARY CHECK: Ensure the worker belongs to the logged-in contractor
    if worker.contractor_id != user_id:
        flash("⛔ Unauthorized Access.")
        return redirect(url_for('manage_clients'))
        
    return render_template('contractor/worker_profile.html', worker=worker)

# --- BUILDER ROUTES (SECURED) ---
@app.route('/builder/dashboard')
@login_required
def builder_dashboard():
    user_id = session.get('user_id')
    projects = Project.query.filter_by(builder_id=user_id).all()
    return render_template('builder/dashboard.html', projects=projects)

@app.route('/builder/jobs/new', methods=['GET', 'POST'])
@login_required
def builder_post_job():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        if title:
            new_project = Project(
                builder_id=session.get('user_id'),
                title=title,
                description=description,
                status='Open'
            )
            db.session.add(new_project)
            db.session.commit()
            return redirect(url_for('builder_dashboard'))
    return render_template('builder/post_job.html')

@app.route('/builder/chat')
@login_required
def builder_chat():
    # You will need to create this template file later
    return render_template('builder/chat.html')

if __name__ == '__main__':
    app.run(debug=True)