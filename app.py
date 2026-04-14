from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Worker, Attendance, Project, Client, Message
from datetime import datetime, timedelta

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:new123@localhost:5432/labourlink'
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
            flash("[!] Access Denied. Please log in to view your dashboard.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    return render_template('home.html')

# --- ROLE SELECTION ROUTE ---
@app.route('/select-role')
def select_role():
    return render_template('auth/signup.html') 

# --- AUTHENTICATION ROUTES ---
@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if request.method == 'POST': 
        username = request.form.get('username')
        password = request.form.get('password') 
        
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash("[!] User already exists! Please log in.")
            return redirect(url_for('login'))

        # Explicitly set contractors to available upon creation
        if role == 'contractor':
            new_user = User(username=username, password=password, role=role, is_available=True)
        else:
            new_user = User(username=username, password=password, role=role)
            
        db.session.add(new_user)
        db.session.commit()
        
        flash("[+] Account created successfully! Please log in.")
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
            session['role'] = user.role 
            if user.role == 'contractor':
                return redirect(url_for('contractor_dashboard'))
            else:
                return redirect(url_for('builder_dashboard'))
        
        flash("[!] Invalid Username or Password.") 
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None) 
    session.pop('username', None) 
    flash("[+] You have been successfully logged out.")
    return redirect(url_for('login'))

# --- CONTRACTOR ROUTES (SECURED) ---
@app.route('/contractor/dashboard')
@login_required
def contractor_dashboard():
    user_id = session.get('user_id')
    
    # 1. Get the last 7 days (including today)
    today = datetime.utcnow().date()
    dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    
    # Format labels for the chart
    labels = [d.strftime('%a') for d in dates] 
    
    # 2. Get all workers belonging to this contractor
    workers = Worker.query.filter_by(contractor_id=user_id).all()
    worker_ids = [w.id for w in workers]
    
    # 3. Count 'Present' attendance for each of those 7 days
    attendance_counts = []
    if worker_ids:
        for d in dates:
            count = Attendance.query.filter(
                Attendance.worker_id.in_(worker_ids),
                Attendance.date == d,
                Attendance.status == 'Present'
            ).count()
            attendance_counts.append(count)
    else:
        attendance_counts = [0] * 7 

    # 4. Stat counts for the summary strip
    total_workers = len(workers)
    total_clients = Client.query.filter_by(contractor_id=user_id).count()
    today_present = Attendance.query.filter(
        Attendance.worker_id.in_(worker_ids) if worker_ids else False,
        Attendance.date == today,
        Attendance.status == 'Present'
    ).count() if worker_ids else 0

    # 5. Fetch assigned project details
    user = User.query.get(user_id)
    assigned_project = None
    if user.assigned_project_id:
        assigned_project = Project.query.get(user.assigned_project_id)

    # [+] NEW LOGIC ADDED HERE: Fetch pending project details
    pending_project = None
    if user.pending_project_id:
        pending_project = Project.query.get(user.pending_project_id)

    return render_template(
        'contractor/dashboard.html', 
        labels=labels, 
        attendance_data=attendance_counts,
        total_workers=total_workers,
        total_clients=total_clients,
        today_present=today_present,
        assigned_project=assigned_project,
        pending_project=pending_project # [+] PASSED TO TEMPLATE HERE
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
    
    workers = Worker.query.filter_by(contractor_id=user_id).all()
    
    if request.method == 'POST':
        for worker in workers:
            status = request.form.get(f'status_{worker.id}')
            
            if status:
                existing_record = Attendance.query.filter_by(
                    worker_id=worker.id, 
                    date=today_date
                ).first()
                
                if existing_record:
                    existing_record.status = status
                else:
                    new_attendance = Attendance(
                        worker_id=worker.id,
                        date=today_date,
                        status=status
                    )
                    db.session.add(new_attendance)
        
        db.session.commit()
        flash("[+] Daily attendance has been saved successfully!")
        return redirect(url_for('contractor_dashboard'))

    formatted_date = today_date.strftime("%B %d, %Y")
    return render_template('contractor/attendance.html', workers=workers, date=formatted_date)

@app.route('/contractor/manage-clients')
@login_required
def manage_clients():
    user_id = session.get('user_id')
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
                contractor_id=session.get('user_id') 
            )
            db.session.add(new_client)
            db.session.commit()
            flash("[+] New site added successfully!")
            return redirect(url_for('manage_clients'))
    return render_template('contractor/add_client.html')

@app.route('/contractor/manage-workers/<int:client_id>')
@login_required
def manage_workers(client_id):
    user_id = session.get('user_id')
    client = Client.query.get_or_404(client_id)
    
    if client.contractor_id != user_id:
        flash("[!] Unauthorized Access: You do not own this site registry.")
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
            flash("[!] Phone number must be exactly 10 digits (0-9).")
            return redirect(url_for('register_worker'))
            
        if not aadhar or not aadhar.isdigit() or len(aadhar) != 12:
            flash("[!] Aadhar number must be exactly 12 digits (0-9).")
            return redirect(url_for('register_worker'))

        if not client_id:
            flash("[!] Please select a Client Site for this worker.")
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
                contractor_id=user_id 
            )
            db.session.add(new_worker)
            db.session.commit()
            flash("[+] Worker successfully assigned to site.")
            return redirect(url_for('manage_clients'))
            
        except Exception as e:
            db.session.rollback()
            flash("[!] Error: Aadhar number might already be registered.")
            return redirect(url_for('register_worker'))
            
    return render_template('contractor/register.html', clients=clients)

@app.route('/contractor/my-profile')
@login_required
def contractor_profile():
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    clients = Client.query.filter_by(contractor_id=user_id).all()
    
    return render_template('contractor/my_profile.html', user=user, clients=clients)

@app.route('/contractor/worker/<int:worker_id>')
@login_required
def worker_profile(worker_id):
    user_id = session.get('user_id')
    worker = Worker.query.get_or_404(worker_id)
    
    if worker.contractor_id != user_id:
        flash("[!] Unauthorized Access.")
        return redirect(url_for('manage_clients'))
        
    return render_template('contractor/worker_profile.html', worker=worker)

@app.route('/contractor/toggle-availability', methods=['POST'])
@login_required
def toggle_availability():
    user = User.query.get(session['user_id'])
    user.is_available = not user.is_available 
    db.session.commit()
    
    status = "Available" if user.is_available else "Unavailable"
    flash(f"[+] Your status is now set to {status}.")
    return redirect(url_for('contractor_profile'))

@app.route('/contractor/respond-request/<int:project_id>/<action>', methods=['POST'])
@login_required
def respond_request(project_id, action):
    user = User.query.get(session['user_id'])
    
    # Ensure they actually have a pending request for this project
    if user.pending_project_id == project_id:
        if action == 'accept':
            user.assigned_project_id = project_id
            user.pending_project_id = None
            user.is_available = False # Take them off the market
            flash("[+] You have accepted the site assignment.")
        elif action == 'reject':
            user.pending_project_id = None
            flash("[+] You have declined the site assignment.")
            
        db.session.commit()
        
    return redirect(url_for('contractor_dashboard'))

# --- BUILDER ROUTES (SECURED) ---
@app.route('/builder/dashboard')
@login_required
def builder_dashboard():
    user_id = session.get('user_id')
    projects = Project.query.filter_by(builder_id=user_id).all()
    
    # Query to fetch only contractors marked as available
    available_contractors = User.query.filter_by(role='contractor', is_available=True).all()
    
    # [+] NEW LOGIC ADDED HERE: Map contractors to projects so we can easily display them on the cards
    all_contractors = User.query.filter_by(role='contractor').all()
    assigned_map = {c.assigned_project_id: c for c in all_contractors if c.assigned_project_id}
    pending_map = {c.pending_project_id: c for c in all_contractors if c.pending_project_id}
    
    return render_template(
        'builder/dashboard.html', 
        projects=projects, 
        available_contractors=available_contractors,
        assigned_map=assigned_map, # [+] PASSED TO TEMPLATE HERE
        pending_map=pending_map    # [+] PASSED TO TEMPLATE HERE
    )

@app.route('/builder/jobs/new', methods=['GET', 'POST'])
@login_required
def builder_post_job():
    if request.method == 'POST':
        title = request.form.get('title')
        site_name = request.form.get('site_name') # [+] Grab site name
        description = request.form.get('description')
        
        if title:
            new_project = Project(
                builder_id=session.get('user_id'),
                title=title,
                site_name=site_name, # [+] Save to database
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
    user_id = session.get('user_id')
    
    # 1. Find all projects owned by this builder
    my_projects = Project.query.filter_by(builder_id=user_id).all()
    project_ids = [p.id for p in my_projects]
    
    # 2. Find contractors assigned to those specific projects
    active_contractors = []
    if project_ids:
        active_contractors = User.query.filter(
            User.role == 'contractor',
            User.assigned_project_id.in_(project_ids)
        ).all()
        
    return render_template('builder/chat.html', contractors=active_contractors)

@app.route('/builder/assign-contractor', methods=['POST'])
@login_required
def assign_contractor():
    contractor_id = request.form.get('contractor_id')
    project_id = request.form.get('project_id')
    
    contractor = User.query.get(contractor_id)
    if contractor and contractor.role == 'contractor':
        # [+] Send request instead of instant assignment
        contractor.pending_project_id = project_id 
        db.session.commit()
        flash(f"[+] Request sent to {contractor.username}.")
    else:
        flash("[!] Error sending request.")
        
    return redirect(url_for('builder_dashboard'))

#------------Message routes-----------------------

# 1. Route to render the main chat interface
@app.route('/chat/<int:partner_id>')
def chat_panel(partner_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('chat_panel.html', partner_id=partner_id)

# 2. API Route to fetch messages (used by JavaScript for polling)
@app.route('/api/chat/<int:partner_id>', methods=['GET'])
def get_messages(partner_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    current_user_id = session['user_id']
    last_msg_id = request.args.get('last_id', 0, type=int)

    # Only fetch messages newer than the last message the client has seen
    messages = Message.query.filter(
        Message.id > last_msg_id,
        db.or_(
            db.and_(Message.sender_id == current_user_id, Message.receiver_id == partner_id),
            db.and_(Message.sender_id == partner_id, Message.receiver_id == current_user_id)
        )
    ).order_by(Message.timestamp.asc()).all()

    message_data = [{
        'id': msg.id,
        'sender_id': msg.sender_id,
        'content': msg.content,
        'timestamp': msg.timestamp.strftime('%H:%M')
    } for msg in messages]

    return jsonify(message_data)

# 3. API Route to handle sending new messages asynchronously
@app.route('/api/chat/send', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    partner_id = data.get('partner_id')
    content = data.get('content')

    if partner_id and content and content.strip():
        new_message = Message(
            sender_id=session['user_id'],
            receiver_id=partner_id,
            content=content.strip()
        )
        db.session.add(new_message)
        db.session.commit()
        return jsonify({'success': True}), 200

    return jsonify({'error': 'Invalid data'}), 400

if __name__ == '__main__':
    app.run(debug=True)