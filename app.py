import os
import zipfile
import shutil
import subprocess
import re

import random
import smtplib

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image
)

from reportlab.lib.styles import getSampleStyleSheet

from reportlab.lib.pagesizes import letter

from datetime import (
    datetime,
    timedelta
)

from email.mime.text import MIMEText

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from flask_mysqldb import MySQL

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

import os

from utils.feature_extraction import extract_features
from utils.predictor import predict_document

# =========================
# FLASK APP
# =========================
app = Flask(__name__)

app.secret_key = 'secret123'

# =========================
# UPLOAD FOLDER
# =========================
UPLOAD_FOLDER = 'static/uploads'
DATASET_FOLDER = 'static/dataset'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATASET_FOLDER'] = DATASET_FOLDER

# =========================
# FILE VALIDATION
# =========================
ALLOWED_EXTENSIONS = {
    'jpg',
    'jpeg',
}

def allowed_file(filename):

    return '.' in filename and \
    filename.rsplit('.', 1)[1].lower() \
    in ALLOWED_EXTENSIONS

# =========================
# MYSQL CONFIG
# =========================
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'fyproject'

mysql = MySQL(app)

# =========================
# SAVE ACTIVITY LOG
# =========================
def save_activity(user_id, activity):

    cursor = mysql.connection.cursor()

    cursor.execute("""
        INSERT INTO activity_logs
        (user_id, activity)

        VALUES (%s, %s)
    """, (
        user_id,
        activity
    ))

    mysql.connection.commit()

    cursor.close()

# =========================
# SEND OTP EMAIL
# =========================
def send_otp_email(to_email, otp):

    smtp_user = "grapesfromheaven@gmail.com"

    smtp_pass = "iavsthuymgrvxajy"

    msg = MIMEText(
        f"Your OTP code is: {otp}\nValid for 5 minutes."
    )

    msg["Subject"] = "Password Reset OTP"

    msg["From"] = smtp_user

    msg["To"] = to_email

    with smtplib.SMTP(
        "smtp.gmail.com",
        587
    ) as server:

        server.starttls()

        server.login(
            smtp_user,
            smtp_pass
        )

        server.send_message(msg)

# =========================
# GENERATE OTP
# =========================
def generate_otp():

    return str(
        random.randint(
            100000,
            999999
        )
    )

# =========================
# HOME
# =========================
@app.route('/')
def home():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # Notifications
    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    # Unread count
    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'index.html',
        username=session['username'],
        notifications=notifications,
        unread_notifications=unread_notifications
    )

# =========================
# USER DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    cursor = mysql.connection.cursor()

    # TOTAL
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=%s
    """, (user_id,))

    total = cursor.fetchone()[0]

    # GENUINE
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=%s
        AND result='Genuine'
    """, (user_id,))

    genuine = cursor.fetchone()[0]

    # FORGED
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=%s
        AND result='Forged'
    """, (user_id,))

    forged = cursor.fetchone()[0]

    # PENDING REVIEW
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE user_id=%s
        AND result='Pending'
    """, (user_id,))

    pending = cursor.fetchone()[0]

    if total > 0:

        genuine_percent = round(
            (genuine / total) * 100
        )

        forged_percent = round(
            (forged / total) * 100
        )

        pending_percent = round(
            (pending / total) * 100
        )

    else:

        genuine_percent = 0
        forged_percent = 0
        pending_percent = 0

    # =========================
    # RECENT ACTIVITY
    # =========================
    cursor.execute("""
        SELECT filename,
        result,
        confidence,
        status,
        uploaded_at

        FROM documents

        WHERE user_id=%s

        ORDER BY uploaded_at DESC

        LIMIT 5
    """, (user_id,))

    recent_activity = cursor.fetchall()

    # =========================
    # LATEST NOTIFICATIONS
    # =========================
    cursor.execute("""
        SELECT message,
        created_at

        FROM notifications

        WHERE user_id=%s

        ORDER BY created_at DESC

        LIMIT 5
    """, (
        session['user_id'],
    ))

    notifications = cursor.fetchall()

    # =========================
    # UNREAD NOTIFICATION COUNT
    # =========================
    cursor.execute("""
        SELECT COUNT(*)

        FROM notifications

        WHERE user_id=%s
        AND is_read=0
    """, (
        session['user_id'],
    ))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'dashboard.html',

        username=session['username'],

        total=total,
        genuine=genuine,
        pending=pending,
        forged=forged,

        genuine_percent= genuine_percent,
        forged_percent= forged_percent,
        pending_percent= pending_percent,

        recent_activity=recent_activity,

        notifications=notifications,
        unread_notifications=unread_notifications
    )

# =========================
# HISTORY
# =========================
@app.route('/history')
def history():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT id,
        filename,
        result,
        confidence,
        status,
        uploaded_at

        FROM documents

        WHERE user_id=%s

        ORDER BY uploaded_at DESC
    """, (
        session['user_id'],
    ))

    documents = cursor.fetchall()

    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'history.html',
        documents=documents,
        username=session['username'],

        notifications=notifications,
        unread_notifications=unread_notifications
    )

# =========================
# PREDICT DOCUMENT
# =========================
@app.route('/predict', methods=['POST'])
def predict():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if 'file' not in request.files:

        return render_template(
            'index.html',
            username=session['username'],
            error='No file uploaded'
        )

    file = request.files['file']

    if file.filename == '':

        return render_template(
            'index.html',
            username=session['username'],
            error='No selected file'
        )

    if not allowed_file(file.filename):

        return render_template(
            'index.html',
            username=session['username'],
            error='Unsupported file type'
        )

    filename = (
    str(int(datetime.now().timestamp()))
    + "_"
    + secure_filename(file.filename)
    )

    filepath = os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename
    )

    file.save(filepath)

    # =========================
    # FEATURE EXTRACTION
    # =========================
    features = extract_features(filepath)

    if features is None:

        return render_template(
            'index.html',
            username=session['username'],
            error='Invalid image'
        )

    # =========================
    # PREDICTION
    # =========================
    result, confidence, process_status = predict_document(features)

    # =========================
    # SAVE TO DATABASE
    # =========================
    cursor = mysql.connection.cursor()

    cursor.execute("""
        INSERT INTO documents
        (user_id, filename,
        result, confidence, status)

        VALUES (%s, %s, %s, %s, %s)
    """, (
        session['user_id'],
        filename,
        result,
        confidence,
        process_status
    ))

    mysql.connection.commit()

    # =========================
    # ADMIN NOTIFICATION
    # =========================
    if result == 'Pending':

        cursor.execute("""
            SELECT id
            FROM users
            WHERE role='admin'
        """)

        admins = cursor.fetchall()

        for admin in admins:

            cursor.execute("""
                INSERT INTO notifications
                (user_id, message)

                VALUES (%s, %s)
            """, (
                admin[0],
                f"New document uploaded by {session['username']} requires manual verification."
            ))

        mysql.connection.commit()

    save_activity(
    session['user_id'],
    f"Uploaded document: {filename}"
    )

    cursor.close()

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    # =========================
    # RETURN SAME PAGE
    # =========================
    return render_template(
    'index.html',

    username=session['username'],

    result=result,
    confidence=confidence,

    status=process_status,

    image=filename,

    notifications=notifications,
    unread_notifications=unread_notifications
)

# =========================
# ADMIN DASHBOARD
# =========================
@app.route('/admin')
def admin_dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))
    

    cursor = mysql.connection.cursor()

    # PENDING
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE result='Pending'
    """)

    pending = cursor.fetchone()[0]

    # GENUINE
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE result='Genuine'
    """)

    genuine = cursor.fetchone()[0]

    # FORGED
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
        WHERE result='Forged'
    """)

    forged = cursor.fetchone()[0]

    # DATASET
    cursor.execute("""
        SELECT COUNT(*)
        FROM documents
    """)

    total_dataset = cursor.fetchone()[0]

    # LATEST PENDING
    cursor.execute("""
        SELECT users.username,
        documents.filename,
        documents.result

        FROM documents

        JOIN users
        ON documents.user_id = users.id

        WHERE documents.result='Pending'

        ORDER BY documents.id DESC

        LIMIT 5
    """)

    latest_documents = cursor.fetchall()

    # =========================
    # LATEST NOTIFICATIONS
    # =========================
    cursor.execute("""
        SELECT message,
        created_at

        FROM notifications

        WHERE user_id=%s

        ORDER BY created_at DESC

        LIMIT 5
    """, (
        session['user_id'],
    ))

    notifications = cursor.fetchall()

    # =========================
    # UNREAD NOTIFICATION COUNT
    # =========================
    cursor.execute("""
        SELECT COUNT(*)

        FROM notifications

        WHERE user_id=%s
        AND is_read=0
    """, (
        session['user_id'],
    ))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'admin_dashboard.html',
        username=session['username'],

        pending=pending,

        genuine=genuine,

        forged=forged,

        total_dataset=total_dataset,

        latest_documents=latest_documents,
        
        notifications=notifications,
        unread_notifications=unread_notifications
    )

# =========================
# ADMIN REVIEWS
@app.route('/admin/reviews')
def admin_reviews():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT documents.id,
        users.username,
        documents.filename,
        documents.result,
        documents.confidence,
        documents.status,
        documents.uploaded_at

        FROM documents

        JOIN users
        ON documents.user_id = users.id

        WHERE documents.result='Pending'

        ORDER BY documents.uploaded_at DESC
    """)

    documents = cursor.fetchall()

    # Notifications
    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    # Unread count
    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'admin_reviews.html',
        documents=documents,
        username=session['username'],
        notifications=notifications,
        unread_notifications=unread_notifications
    )

@app.route('/admin_reviews')
def admin_reviews_redirect():
    return redirect(url_for('admin_reviews'))

@app.route('/admin_dashboard')
def admin_dashboard_redirect():
    return redirect(url_for('admin_dashboard'))

# =========================
# ACTIVITY LOGS
# =========================
@app.route('/admin/activity_logs')
def activity_logs():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT users.username,
        activity_logs.activity,
        activity_logs.created_at

        FROM activity_logs

        JOIN users
        ON activity_logs.user_id = users.id

        ORDER BY activity_logs.created_at DESC
    """)

    logs = cursor.fetchall()

    # =========================
    # LATEST NOTIFICATIONS
    # =========================
    cursor.execute("""
        SELECT message,
        created_at

        FROM notifications

        WHERE user_id=%s

        ORDER BY created_at DESC

        LIMIT 5
    """, (
        session['user_id'],
    ))

    notifications = cursor.fetchall()

    # =========================
    # UNREAD NOTIFICATION COUNT
    # =========================
    cursor.execute("""
        SELECT COUNT(*)

        FROM notifications

        WHERE user_id=%s
        AND is_read=0
    """, (
        session['user_id'],
    ))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'activity_logs.html',

        logs=logs,

        username=session['username'],

        notifications=notifications,

        unread_notifications=unread_notifications
    )

# =========================
# ADMIN DATASET
# =========================
@app.route('/admin/dataset')
def admin_dataset():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    # =========================
    # DATASET PATHS
    # =========================
    genuine_path = 'dataset/genuine'
    forged_path = 'dataset/forged'

    # =========================
    # COUNT GENUINE IMAGES
    # =========================
    genuine_count = 0

    if os.path.exists(genuine_path):

        genuine_count = len([

            file for file in os.listdir(genuine_path)

            if file.lower().endswith(
                ('.jpg')
            )

        ])

    # =========================
    # COUNT FORGED IMAGES
    # =========================
    forged_count = 0

    if os.path.exists(forged_path):

        forged_count = len([

            file for file in os.listdir(forged_path)

            if file.lower().endswith(
                ('.jpg')
            )

        ])
    # =========================
    # NOTIFICATIONS
    # =========================
    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    # =========================
    # RETURN PAGE
    # =========================
    return render_template(
        'admin_dataset.html',

        genuine_count=genuine_count,
        forged_count=forged_count,

        username=session['username'],

        notifications=notifications,
        unread_notifications=unread_notifications
    )

@app.route('/upload_dataset', methods=['POST'])
def upload_dataset():

    # =========================
    # ADMIN CHECK
    # =========================
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    # =========================
    # CHECK FILE
    # =========================
    if 'dataset_zip' not in request.files:
        return redirect(url_for('admin_dataset'))

    zip_file = request.files['dataset_zip']

    if zip_file.filename == '':
        return redirect(url_for('admin_dataset'))

    # =========================
    # CHECK ZIP FILE
    # =========================
    if not zip_file.filename.lower().endswith('.zip'):
        return redirect(url_for('admin_dataset'))

    # =========================
    # REMOVE OLD DATASET
    # =========================
    dataset_folder = 'dataset'

    if os.path.exists(dataset_folder):
        shutil.rmtree(dataset_folder)

    # =========================
    # CREATE NEW DATASET FOLDER
    # =========================
    os.makedirs(dataset_folder, exist_ok=True)

    # =========================
    # SAVE ZIP FILE
    # =========================
    zip_path = os.path.join(
        dataset_folder,
        'temp_dataset.zip'
    )

    zip_file.save(zip_path)

    # =========================
    # EXTRACT ZIP
    # =========================
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(dataset_folder)

    # =========================
    # DELETE ZIP AFTER EXTRACT
    # =========================
    os.remove(zip_path)

    # =========================
    # SUCCESS
    # =========================
    return redirect(
        url_for(
            'admin_dataset',
            msg='uploaded'
        )
    )

def get_dataset_count(category):

    path = os.path.join(
        'dataset',
        category
    )

    if not os.path.exists(path):
        return 0

    return len([

        file for file in os.listdir(path)

        if file.lower().endswith(
            ('.jpg')
        )

    ])

@app.route('/train_model', methods=['POST'])
def train_model():

    # =========================
    # ADMIN CHECK
    # =========================
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    # =========================
    # RUN TRAINING SCRIPT
    # =========================
    result = subprocess.check_output(
        ['python', 'train_model.py']
    ).decode('utf-8')

    # =========================
    # EXTRACT ACCURACY
    # =========================
    match = re.search(
        r'FINAL_ACCURACY:(\d+\.\d+)',
        result
    )

    if not match:
        return redirect(
            url_for(
                'admin_dataset',
                msg='failed'
            )
        )

    accuracy = float(match.group(1))

    # Notifications
    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO model_logs
        (admin_id, accuracy, dataset_size)

        VALUES (%s, %s, %s)
    """, (
        session['user_id'],
        accuracy,
        get_dataset_count('genuine')
        +
        get_dataset_count('forged')
    ))

    mysql.connection.commit()

    cursor.close()

    # =========================
    # CHECK ACCURACY
    # =========================
    if accuracy >= 80:

        return render_template(
        'admin_dataset.html',

        genuine_count=get_dataset_count('genuine'),
        forged_count=get_dataset_count('forged'),

        accuracy=accuracy,
        eligible=True,

        username=session['username'],
        notifications=notifications,
        unread_notifications=unread_notifications
    )

    else:

        return render_template(
        'admin_dataset.html',

        genuine_count=get_dataset_count('genuine'),
        forged_count=get_dataset_count('forged'),

        accuracy=accuracy,
        eligible=False,

        username=session['username'],
        notifications=notifications,
        unread_notifications=unread_notifications
    )
    
@app.route('/update_model', methods=['POST'])
def update_model():

    # =========================
    # ADMIN CHECK
    # =========================
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    # =========================
    # BACKUP CURRENT MODEL
    # =========================
    if os.path.exists('svm_model.pkl'):

        shutil.copy(
            'svm_model.pkl',
            'backup_model.pkl'
        )

    if os.path.exists('scaler.pkl'):

        shutil.copy(
            'scaler.pkl',
            'backup_scaler.pkl'
        )

    # =========================
    # REPLACE WITH TEMP MODEL
    # =========================
    shutil.copy(
        'temp_model.pkl',
        'svm_model.pkl'
    )

    shutil.copy(
        'temp_scaler.pkl',
        'scaler.pkl'
    )

    return redirect(
        url_for(
            'admin_dataset',
            msg='model_updated'
        )
    )

@app.route('/discard_model', methods=['POST'])
def discard_model():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    # delete temp model
    if os.path.exists('temp_model.pkl'):
        os.remove('temp_model.pkl')

    if os.path.exists('temp_scaler.pkl'):
        os.remove('temp_scaler.pkl')

    return redirect(
        url_for(
            'admin_dataset',
            msg='discarded'
        )
    )

@app.route('/approve/<int:document_id>/<decision>')
def approve_document(document_id, decision):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'admin':
        return redirect(url_for('dashboard'))

    if decision not in ('Genuine', 'Forged'):
        return redirect(url_for('admin_reviews'))

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE documents
        SET result=%s, status='Completed'
        WHERE id=%s
    """, (decision, document_id))

    # =========================
    # SAVE ADMIN REVIEW LOG
    # =========================
    cursor.execute("""
        INSERT INTO admin_reviews
        (document_id, admin_id, decision)

        VALUES (%s, %s, %s)
    """, (
        document_id,
        session['user_id'],
        decision
    ))

    # =========================
    # USER NOTIFICATION
    # =========================
    cursor.execute("""
        SELECT user_id
        FROM documents
        WHERE id=%s
    """, (document_id,))

    owner = cursor.fetchone()

    cursor.execute("""
        INSERT INTO notifications
        (user_id, message)

        VALUES (%s, %s)
    """, (
        owner[0],
        f"Your document has been reviewed and marked as {decision}."
    ))

    mysql.connection.commit()

    save_activity(
    session['user_id'],
    f"Reviewed document ID {document_id} as {decision}"
    )

    cursor.close()

    msg = 'approved' if decision == 'Genuine' else 'rejected'
    return redirect(url_for('admin_reviews', msg=msg))


# =========================
# LOGIN
# =========================
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE email=%s
        """, (email,))

        user = cursor.fetchone()

        cursor.close()

        if user:

            stored_password = user[4]

            if check_password_hash(
                stored_password,
                password
            ):

                session['user_id'] = user[0]
                session['username'] = user[2]
                session['role'] = user[5]

                # ADMIN LOGIN
                if user[5] == 'admin':

                    return redirect(
                        url_for('admin_dashboard')
                    )

                # USER LOGIN
                else:

                    return redirect(
                        url_for('dashboard')
                    )

        return render_template(
            'login.html',
            message='Invalid Email or Password'
        )

    return render_template('login.html')

# =========================
# FORGOT PASSWORD
# =========================
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        email = request.form['email']

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE email=%s
        """, (email,))

        user = cursor.fetchone()

        if not user:

            cursor.close()

            return redirect(
                url_for('forgot_password')
            )

        # GENERATE OTP
        otp = str(
            random.randint(
                100000,
                999999
            )
        )

        expires_at = datetime.now() + timedelta(minutes=5)

        cursor.execute("""
            INSERT INTO otp_codes
            (
                email,
                otp,
                purpose,
                expires_at
            )

            VALUES (%s, %s, %s, %s)
        """, (
            email,
            otp,
            'forgot_password',
            expires_at
        ))

        mysql.connection.commit()

        # SAVE SESSION
        session['reset_email'] = email

        # SEND EMAIL
        try:

            send_otp_email(
                email,
                otp
            )

        except Exception as e:

            print(e)

            flash(
                "Failed to send OTP email"
            )

            cursor.close()

            return redirect(
                url_for('forgot_password')
            )

        cursor.close()

        return redirect(
            url_for('reset_password')
        )

    return render_template(
        'forgot_password.html'
    )

# =========================
# RESET PASSWORD
# =========================
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():

    # SESSION CHECK
    if 'reset_email' not in session:

        return redirect(
            url_for('forgot_password')
        )

    if request.method == 'POST':

        otp = request.form['otp']

        new_password = request.form['new_password']

        confirm_password = request.form['confirm_password']

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT * FROM users
            WHERE email=%s
        """, (
            session.get('reset_email'),
        ))

        user = cursor.fetchone()

        # =========================
        # USER CHECK
        # =========================
        if not user:

            cursor.close()

            flash("User not found")

            return redirect(
                url_for('forgot_password')
            )

        # =========================
        # OTP CHECK
        # =========================
        cursor.execute("""
            SELECT *
            FROM otp_codes

            WHERE email=%s
            AND otp=%s
            AND purpose='forgot_password'
            AND is_used=0

            ORDER BY id DESC
            LIMIT 1
        """, (
            session.get('reset_email'),
            otp
        ))

        otp_record = cursor.fetchone()

        if not otp_record:

            cursor.close()

            flash("Invalid OTP")

            return redirect(request.url)

        expires_at = otp_record[6]

        if datetime.now() > expires_at:

            cursor.close()

            flash("OTP expired")

            return redirect(request.url)

        # =========================
        # PASSWORD MATCH
        # =========================
        if new_password != confirm_password:

            cursor.close()

            flash("Passwords do not match")

            return redirect(request.url)

       # =========================
        # STRONG PASSWORD
        # =========================

        if len(new_password) < 12:

            cursor.close()

            flash(
                "Password must be at least 12 characters long."
            )

            return redirect(request.url)

        if not re.search(r"[A-Z]", new_password):

            cursor.close()

            flash(
                "Password must contain at least one uppercase letter."
            )

            return redirect(request.url)

        if not re.search(r"[a-z]", new_password):

            cursor.close()

            flash(
                "Password must contain at least one lowercase letter."
            )

            return redirect(request.url)

        if not re.search(r"[0-9]", new_password):

            cursor.close()

            flash(
                "Password must contain at least one number."
            )

            return redirect(request.url)

        if not re.search(r"[\W_]", new_password):

            cursor.close()

            flash(
                "Password must contain at least one special character."
            )

            return redirect(request.url)

        # =========================
        # HASH PASSWORD
        # =========================
        hashed_password = generate_password_hash(
            new_password
        )

        # =========================
        # UPDATE PASSWORD
        # =========================
        cursor.execute("""
            UPDATE users

            SET password=%s

            WHERE email=%s
        """, (
            hashed_password,
            session['reset_email']
        ))

        # =========================
        # MARK OTP USED
        # =========================
        cursor.execute("""
            UPDATE otp_codes

            SET is_used=1

            WHERE id=%s
        """, (
            otp_record[0],
        ))

        mysql.connection.commit()

        cursor.close()

        # CLEAR SESSION
        session.pop(
            'reset_email',
            None
        )

        flash(
            "Password reset successful"
        )

        return redirect(
            url_for('login')
        )

    return render_template(
        'resetpass.html'
    )
# =========================
# SEND REGISTER OTP
# =========================
@app.route('/send_register_otp', methods=['POST'])
def send_register_otp():

    email = request.form['email']

    otp = generate_otp()

    expires_at = datetime.now() + timedelta(minutes=5)

    cursor = mysql.connection.cursor()

    # DELETE OLD OTP
    cursor.execute("""
        DELETE FROM otp_codes

        WHERE email=%s
        AND purpose='register'
    """, (email,))

    # SAVE NEW OTP
    cursor.execute("""
        INSERT INTO otp_codes
        (
            email,
            otp,
            purpose,
            expires_at
        )

        VALUES (%s, %s, %s, %s)
    """, (
        email,
        otp,
        'register',
        expires_at
    ))

    mysql.connection.commit()

    try:

        send_otp_email(
            email,
            otp
        )

    except Exception as e:

        print(e)

        cursor.close()

        return {
            "status": "error",
            "message": "Failed to send OTP"
        }

    cursor.close()

    return {
        "status": "success",
        "message": "OTP sent successfully"
    }

# =========================
# REGISTER
# =========================
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        full_name = request.form['full_name']

        username = request.form['username']

        email = request.form['email']

        password = request.form['password']

        confirm_password = request.form['confirm_password']

        role = 'user'

        # PASSWORD MATCH
        if password != confirm_password:

            return render_template(
                'register.html',
                message='Passwords do not match'
            )

        # EMAIL FORMAT
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(email_pattern, email):

            return render_template(
                'register.html',
                message='Invalid email format'
            )

        # CHECK PASSWORD STRENGTH
        if len(password) < 12:

            return render_template(
                'register.html',
                message='Password must be at least 12 characters long.'
            )

        cursor = mysql.connection.cursor()

        # CHECK EXISTING EMAIL
        cursor.execute("""
            SELECT *
            FROM users
            WHERE email=%s
        """, (email,))

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()

            return render_template(
                'register.html',
                message='Email already exists'
            )

        # GENERATE OTP
        otp = generate_otp()

        expires_at = datetime.now() + timedelta(minutes=5)

        # SAVE OTP
        cursor.execute("""
            INSERT INTO otp_codes
            (
                email,
                otp,
                purpose,
                expires_at
            )

            VALUES (%s, %s, %s, %s)
        """, (
            email,
            otp,
            'register',
            expires_at
        ))

        mysql.connection.commit()

        cursor.close()

        # SEND OTP EMAIL
        send_otp_email(
            email,
            otp
        )

        # SAVE TEMP SESSION
        session['register_data'] = {
            'full_name': full_name,
            'username': username,
            'email': email,
            'password': password,
            'role': role
        }

        return redirect(
            url_for('verify_register_otp')
        )

    return render_template('register.html')

# =========================
# VERIFY REGISTER OTP
# =========================
@app.route('/verify_register_otp', methods=['GET', 'POST'])
def verify_register_otp():

    if 'register_data' not in session:

        return redirect(url_for('register'))

    if request.method == 'POST':

        entered_otp = request.form['otp']

        register_data = session['register_data']

        cursor = mysql.connection.cursor()

        cursor.execute("""
            SELECT *
            FROM otp_codes

            WHERE email=%s
            AND otp=%s
            AND purpose='register'
            AND is_used=0

            ORDER BY id DESC
            LIMIT 1
        """, (
            register_data['email'],
            entered_otp
        ))

        otp_record = cursor.fetchone()

        if not otp_record:

            cursor.close()

            return render_template(
                'verify_otp.html',
                message='Invalid OTP'
            )

        expires_at = otp_record[6]

        if datetime.now() > expires_at:

            cursor.close()

            return render_template(
                'verify_otp.html',
                message='OTP expired'
            )

        hashed_password = generate_password_hash(
            register_data['password']
        )

        # CREATE ACCOUNT
        cursor.execute("""
            INSERT INTO users
            (
                full_name,
                username,
                email,
                password,
                role,
                is_verified
            )

            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            register_data['full_name'],
            register_data['username'],
            register_data['email'],
            hashed_password,
            register_data['role'],
            1
        ))

        # MARK OTP USED
        cursor.execute("""
            UPDATE otp_codes

            SET is_used=1

            WHERE id=%s
        """, (
            otp_record[0],
        ))

        mysql.connection.commit()

        cursor.close()

        session.pop(
            'register_data',
            None
        )

        return redirect(url_for('login'))

    return render_template('verify_otp.html')

@app.route('/profile')
def profile():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT username,
        email,
        role,
        created_at

        FROM users

        WHERE id=%s
    """, (
        session['user_id'],
    ))

    user = cursor.fetchone()

    # Notifications
    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (session['user_id'],))

    notifications = cursor.fetchall()

    # Unread notification count
    cursor.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id=%s
        AND is_read=0
    """, (session['user_id'],))

    unread_notifications = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        'profile.html',

        user=user,

        notifications=notifications,
        unread_notifications=unread_notifications
    )

@app.route('/change_password', methods=['POST'])
def change_password():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_password = request.form['current_password']

    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT password
        FROM users
        WHERE id=%s
    """, (
        session['user_id'],
    ))

    user = cursor.fetchone()

    stored_password = user[0]

    # PREVENT SAME PASSWORD REUSE
    if check_password_hash(
        stored_password,
        new_password
    ):

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='same'
            )
        )

    # VERIFY CURRENT PASSWORD
    if not check_password_hash(
        stored_password,
        current_password
    ):

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='wrong'
            )
        )
    
    # =========================
    # PASSWORD MATCH
    # =========================
    if new_password != confirm_password:

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='mismatch'
            )
        )

    # =========================
    # STRONG PASSWORD
    # =========================

    if len(new_password) < 12:

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='weak'
            )
        )

    if not re.search(r"[A-Z]", new_password):

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='weak'
            )
        )

    if not re.search(r"[a-z]", new_password):

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='weak'
            )
        )

    if not re.search(r"[0-9]", new_password):

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='weak'
            )
        )

    if not re.search(r"[\W_]", new_password):

        cursor.close()

        return redirect(
            url_for(
                'profile',
                msg='weak'
            )
        )
    
    # HASH NEW PASSWORD
    hashed_password = generate_password_hash(
        new_password
    )

    # UPDATE PASSWORD
    cursor.execute("""
        UPDATE users

        SET password=%s

        WHERE id=%s
    """, (
        hashed_password,
        session['user_id']
    ))

    mysql.connection.commit()

    save_activity(
    session['user_id'],
    "Changed account password"
    )

    cursor.close()

    return redirect(
        url_for(
            'profile',
            msg='success'
        )
    )
# =========================
# GENERATE PDF REPORT
# =========================
@app.route('/generate_report/<int:document_id>')
def generate_report(document_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT filename,
        result,
        confidence,
        status,
        uploaded_at

        FROM documents

        WHERE id=%s
        AND user_id=%s
    """, (
        document_id,
        session['user_id']
    ))

    document = cursor.fetchone()

    cursor.close()

    if not document:
        return "Document not found"

    # ONLY ALLOW COMPLETED REPORT
    if document[3] != 'Completed':
        return "Report not available"

    # PDF FILE NAME
    pdf_filename = f"report_{document_id}.pdf"

    pdf_path = os.path.join(
        'static/reports',
        pdf_filename
    )

    os.makedirs(
        'static/reports',
        exist_ok=True
    )

    # CREATE PDF
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "<b>UTHM Document Verification Report</b>",
        styles['Title']
    )

    elements.append(title)

    elements.append(Spacer(1, 20))

    # DOCUMENT IMAGE
    image_path = os.path.join(
        'static/uploads',
        document[0]
    )

    if os.path.exists(image_path):

        report_image = Image(image_path)

        # KEEP ASPECT RATIO
        report_image._restrictSize(
            400,
            500
        )

        # CENTER IMAGE
        report_image.hAlign = 'CENTER'

        elements.append(report_image)

        elements.append(Spacer(1, 20))

    details = f"""
    <b>Filename:</b> {document[0]}<br/><br/>
    <b>Verification Result:</b> {document[1]}<br/><br/>
    <b>Confidence:</b> {document[2]}%<br/><br/>
    <b>Review Status:</b> {document[3]}<br/><br/>
    <b>Upload Date:</b> {document[4]}<br/><br/>
    <b>Generated Date:</b> {datetime.now()}
    """

    content = Paragraph(
        details,
        styles['BodyText']
    )

    elements.append(content)

    doc.build(elements)

    return redirect(
        url_for(
            'static',
            filename=f'reports/{pdf_filename}'
        )
    )

# =========================
# LOGOUT
# =========================
@app.route('/logout')
def logout():

    session.clear()

    return redirect(url_for('login'))

# =========================
# RUN APP
# =========================
if __name__ == '__main__':

    app.run(debug=True)