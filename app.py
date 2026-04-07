from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import session, flash

from models import db, User, Worker, Attendance, Project, Client

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:new123@127.0.0.1:5432/labourlink'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Create tables automatically
with app.app_context():
    db.create_all()

# Secret key is required for sessions (login memory)
app.secret_key = 'super_secret_key_for_labourlink'


# --- ROUTES ---

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/builder/dashboard')
def builder_dashboard():
    projects = Project.query.all()
    return render_template('builder/dashboard.html', projects=projects)

@app.route('/builder/jobs/new', methods=['GET', 'POST'])
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
def builder_chat():
    return render_template('builder/chat.html')


# --- CONTRACTOR ROUTES ---

@app.route('/contractor/dashboard')
def contractor_dashboard():
    return render_template('contractor/dashboard.html')

@app.route('/contractor/manage-clients')
def manage_clients():
    clients = Client.query.all()
    return render_template('contractor/manage_clients.html', clients=clients)

@app.route('/contractor/add-client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        name = request.form.get('name')
        location = request.form.get('location')
        if name:
            new_client = Client(name=name, location=location)
            db.session.add(new_client)
            db.session.commit()
            return redirect(url_for('manage_clients'))
    return render_template('contractor/add_client.html')



@app.route('/contractor/register-worker', methods=['GET', 'POST'])
def register_worker():
    clients = Client.query.all()

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        aadhar = request.form.get('aadhar')
        client_id = request.form.get('client_id')

        # Phone Validation: Must be numeric and exactly 10 digits
        if not phone or not phone.isdigit() or len(phone) != 10:
            flash("Phone number must be exactly 10 digits (0-9).")
            return redirect(url_for('register_worker'))

        # Aadhar Validation: Must be numeric and exactly 12 digits
        if not aadhar or not aadhar.isdigit() or len(aadhar) != 12:
            flash("Aadhar number must be exactly 12 digits (0-9).")
            return redirect(url_for('register_worker'))

        # Site Selection Validation
        if not client_id:
            flash("Please select a Client Site for this worker.")
            return redirect(url_for('register_worker'))

        try:
            new_worker = Worker(
                name=name,
                role=request.form.get('role'),
                aadhar_no=aadhar,
                city=request.form.get('city'),
                phone=phone,
                gender=request.form.get('gender'),
                client_id=client_id,
                contractor_id=session.get('user_id')
            )
            db.session.add(new_worker)
            db.session.commit()
            flash(f"Worker {name} successfully assigned to site.")
            return redirect(url_for('manage_clients'))

        except Exception as e:
            db.session.rollback()
            flash("Error: Aadhar number might already be registered.")
            return redirect(url_for('register_worker'))

    return render_template('contractor/register.html', clients=clients)

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

@app.route('/contractor/manage-workers/<int:client_id>')
def manage_workers(client_id):
    client = Client.query.get_or_404(client_id)
    workers = Worker.query.filter_by(client_id=client_id).all()
    return render_template('contractor/manage_workers.html', workers=workers, client=client)

@app.route('/contractor/worker/<int:worker_id>')
def worker_profile(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    return render_template('contractor/worker_profile.html', worker=worker)

# --- AUTH ROUTES ---

@app.route('/signup', methods=['GET'])
def signup_selection():
    return render_template('auth/role_selection.html')

@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')  # 1. We get it here...

        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash("User already exists!")
            return redirect(url_for('login'))

        # 2. THE FIX: You must add password=password inside the parentheses below!
        new_user = User(username=username, password=password, role=role)
        
        db.session.add(new_user)
        db.session.commit()

        print(f"DEBUG: New {role} created: {username}")
        return redirect(url_for('login'))

    return render_template('auth/signup.html', role=role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_id = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=login_id).first()

        if user and user.password == password:
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('contractor_dashboard') if user.role == 'contractor' else url_for('builder_dashboard'))
        
        else:
            # This "flashes" the message to the next page load
            flash("Invalid Login ID or Password. Access Denied!", "danger")
            return redirect(url_for('login'))

    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))



# --- START THE SERVER ---
if __name__ == '__main__':
    app.run(debug=True)