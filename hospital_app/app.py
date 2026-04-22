from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import hashlib
import random
import string
from datetime import datetime, date, timedelta
import os

app = Flask(__name__)
app.secret_key = 'hospital_secret_key_2024'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'hospital.db')

# ─── DB INIT ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout = 10000')
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        phone TEXT,
        dob TEXT,
        blood_group TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        patient_name TEXT,
        doctor TEXT,
        department TEXT,
        date TEXT,
        time_slot TEXT,
        symptoms TEXT,
        status TEXT DEFAULT 'Scheduled',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        appointment_id TEXT,
        diagnosis TEXT,
        medicines TEXT,
        instructions TEXT,
        doctor TEXT,
        issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        appointment_id TEXT,
        consultation_fee INTEGER DEFAULT 200,
        medicine_cost INTEGER DEFAULT 0,
        total INTEGER DEFAULT 200,
        status TEXT DEFAULT 'Pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT NOT NULL,
        max_patients_per_day INTEGER DEFAULT 8,
        slot_duration_minutes INTEGER DEFAULT 30,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS consultation_chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appointment_id TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        status TEXT DEFAULT 'open',
        opened_at TEXT,
        expires_at TEXT,
        last_message_at TEXT,
        request_deadline TEXT,
        last_access_request_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS consultation_chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        sender_role TEXT NOT NULL,
        sender_id INTEGER,
        message TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        is_reported INTEGER DEFAULT 0,
        reported_by_role TEXT,
        reported_by_id INTEGER,
        reported_reason TEXT,
        reported_at TEXT,
        FOREIGN KEY(session_id) REFERENCES consultation_chat_sessions(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS consultation_chat_access_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        requested_by_user_id INTEGER NOT NULL,
        request_note TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        reviewed_by_admin TEXT,
        reviewed_at TEXT,
        review_note TEXT,
        FOREIGN KEY(session_id) REFERENCES consultation_chat_sessions(id),
        FOREIGN KEY(requested_by_user_id) REFERENCES users(id)
    )''')

    appointment_columns = [row['name'] for row in c.execute("PRAGMA table_info(appointments)").fetchall()]
    if 'doctor_id' not in appointment_columns:
        c.execute('ALTER TABLE appointments ADD COLUMN doctor_id INTEGER')
    if 'completed_at' not in appointment_columns:
        c.execute('ALTER TABLE appointments ADD COLUMN completed_at TEXT')

    doctor_columns = [row['name'] for row in c.execute("PRAGMA table_info(doctors)").fetchall()]
    if 'max_patients_per_day' not in doctor_columns:
        c.execute('ALTER TABLE doctors ADD COLUMN max_patients_per_day INTEGER DEFAULT 8')
    if 'slot_duration_minutes' not in doctor_columns:
        c.execute('ALTER TABLE doctors ADD COLUMN slot_duration_minutes INTEGER DEFAULT 30')

    # Seed 10 doctor accounts if they are missing.
    seed_doctors = [
        ('Dr. Priya Sharma', 'priya.general@medicare.com', 'General'),
        ('Dr. Kiran Reddy', 'kiran.general@medicare.com', 'General'),
        ('Dr. Arjun Mehta', 'arjun.cardio@medicare.com', 'Cardiology'),
        ('Dr. Sunita Rao', 'sunita.cardio@medicare.com', 'Cardiology'),
        ('Dr. Vikram Singh', 'vikram.ortho@medicare.com', 'Orthopedics'),
        ('Dr. Anjali Patel', 'anjali.ortho@medicare.com', 'Orthopedics'),
        ('Dr. Rohit Bose', 'rohit.neuro@medicare.com', 'Neurology'),
        ('Dr. Meera Nair', 'meera.neuro@medicare.com', 'Neurology'),
        ('Dr. Deepa Gupta', 'deepa.pediatrics@medicare.com', 'Pediatrics'),
        ('Dr. Ramesh Iyer', 'ramesh.ent@medicare.com', 'ENT'),
    ]
    default_password_hash = hashlib.sha256('doctor123'.encode()).hexdigest()
    for name, email, department in seed_doctors:
        c.execute('''INSERT OR IGNORE INTO doctors (name, email, password, department, is_active)
                     VALUES (?, ?, ?, ?, 1)''',
                  (name, email, default_password_hash, department))

    c.execute('''UPDATE doctors
                 SET max_patients_per_day = COALESCE(max_patients_per_day, ?),
                     slot_duration_minutes = COALESCE(slot_duration_minutes, ?)
                 WHERE max_patients_per_day IS NULL OR slot_duration_minutes IS NULL''',
              (8, 30))

    conn.commit()
    conn.close()

# Ensure tables exist for both `python app.py` and `flask run` startup modes.
init_db()

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_appointment_id():
    return 'APT-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

DEFAULT_SLOT_DURATION_MINUTES = 30
DEFAULT_MAX_PATIENTS_PER_DAY = 8
BOOKING_OPEN_HOUR = 7
BOOKING_CLOSE_HOUR = 21
WORKING_WINDOWS = [('07:00', '21:00')]
CONSULTATION_CHAT_OPEN_MINUTES = 3
CONSULTATION_CHAT_REQUEST_WINDOW_MINUTES = 60
DOCTOR_LUNCH_WINDOWS = [
    (12 * 60, 13 * 60),  # First doctor in department: 12 PM to 1 PM.
    (13 * 60, 14 * 60),  # Second doctor in department: 1 PM to 2 PM.
]

CHAT_REPORTED_BY_LABELS = {
    'admin': 'Admin',
    'doctor': 'Doctor'
}


def now_db_string(now=None):
    current = now or datetime.now()
    return current.strftime('%Y-%m-%d %H:%M:%S')


def parse_db_datetime(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def upsert_consultation_chat_session(conn, apt):
    now = datetime.now()
    opened_at = now_db_string(now)
    expires_at = now_db_string(now + timedelta(minutes=CONSULTATION_CHAT_OPEN_MINUTES))
    request_deadline = now_db_string(now + timedelta(minutes=CONSULTATION_CHAT_REQUEST_WINDOW_MINUTES))

    existing = conn.execute(
        'SELECT id FROM consultation_chat_sessions WHERE appointment_id=?',
        (apt['appointment_id'],)
    ).fetchone()

    if existing:
        conn.execute(
            '''UPDATE consultation_chat_sessions
               SET status='open', opened_at=?, expires_at=?, request_deadline=?,
                   last_message_at=NULL, updated_at=?, last_access_request_at=NULL
               WHERE id=?''',
            (opened_at, expires_at, request_deadline, opened_at, existing['id'])
        )
        return existing['id']

    conn.execute(
        '''INSERT INTO consultation_chat_sessions
           (appointment_id, user_id, doctor_id, status, opened_at, expires_at, request_deadline, created_at, updated_at)
           VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)''',
        (
            apt['appointment_id'],
            apt['user_id'],
            apt['doctor_id'],
            opened_at,
            expires_at,
            request_deadline,
            opened_at,
            opened_at,
        )
    )
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def sync_consultation_chat_status(conn, chat_session):
    if not chat_session or chat_session['status'] != 'open':
        return chat_session

    expires_at = parse_db_datetime(chat_session['expires_at'])
    now = datetime.now()
    if expires_at and now >= expires_at:
        updated_at = now_db_string(now)
        conn.execute(
            "UPDATE consultation_chat_sessions SET status='paused', updated_at=? WHERE id=?",
            (updated_at, chat_session['id'])
        )
        return conn.execute('SELECT * FROM consultation_chat_sessions WHERE id=?', (chat_session['id'],)).fetchone()

    return chat_session


def get_actor_context():
    if session.get('is_admin'):
        return 'admin', None
    if session.get('is_doctor') and session.get('doctor_id'):
        return 'doctor', session['doctor_id']
    if session.get('user_id'):
        return 'patient', session['user_id']
    return None, None


def load_chat_for_actor(conn, appointment_id, actor_role, actor_id):
    apt = conn.execute(
        '''SELECT a.*, p.diagnosis, p.medicines, p.instructions
           FROM appointments a
           LEFT JOIN prescriptions p ON p.appointment_id = a.appointment_id
           WHERE a.appointment_id=?''',
        (appointment_id,)
    ).fetchone()

    if not apt:
        return None, None

    if actor_role == 'patient' and apt['user_id'] != actor_id:
        return None, None
    if actor_role == 'doctor' and apt['doctor_id'] != actor_id:
        return None, None
    if actor_role not in ('patient', 'doctor', 'admin'):
        return None, None

    chat_session = conn.execute(
        'SELECT * FROM consultation_chat_sessions WHERE appointment_id=?',
        (appointment_id,)
    ).fetchone()

    if not chat_session and apt['status'] == 'Completed':
        chat_id = upsert_consultation_chat_session(conn, apt)
        chat_session = conn.execute('SELECT * FROM consultation_chat_sessions WHERE id=?', (chat_id,)).fetchone()

    return apt, chat_session


def build_chat_state_payload(conn, apt, chat_session, actor_role):
    chat_session = sync_consultation_chat_status(conn, chat_session)
    if chat_session:
        conn.commit()

    messages = []
    pending_request = None
    if chat_session:
        messages = conn.execute(
            '''SELECT * FROM consultation_chat_messages
               WHERE session_id=?
               ORDER BY id ASC''',
            (chat_session['id'],)
        ).fetchall()

        pending_request = conn.execute(
            '''SELECT * FROM consultation_chat_access_requests
               WHERE session_id=? AND status='pending'
               ORDER BY id DESC
               LIMIT 1''',
            (chat_session['id'],)
        ).fetchone()

    can_request_access = False
    request_deadline = chat_session['request_deadline'] if chat_session else None
    if actor_role == 'patient' and chat_session:
        deadline_dt = parse_db_datetime(request_deadline)
        can_request_access = (
            chat_session['status'] != 'open'
            and deadline_dt is not None
            and datetime.now() <= deadline_dt
            and pending_request is None
        )

    return {
        'appointment': {
            'appointment_id': apt['appointment_id'],
            'patient_name': apt['patient_name'],
            'doctor': apt['doctor'],
            'department': apt['department'],
            'diagnosis': apt['diagnosis'],
            'medicines': apt['medicines'],
            'instructions': apt['instructions']
        },
        'chat_session': {
            'id': chat_session['id'] if chat_session else None,
            'status': chat_session['status'] if chat_session else 'unavailable',
            'opened_at': chat_session['opened_at'] if chat_session else None,
            'expires_at': chat_session['expires_at'] if chat_session else None,
            'request_deadline': request_deadline,
            'last_message_at': chat_session['last_message_at'] if chat_session else None,
            'can_send': bool(chat_session and chat_session['status'] == 'open' and actor_role in ('patient', 'doctor')),
            'can_request_access': can_request_access,
            'pending_request': bool(pending_request),
        },
        'messages': [
            {
                'id': m['id'],
                'sender_role': m['sender_role'],
                'message': m['message'],
                'created_at': m['created_at'],
                'is_reported': bool(m['is_reported']),
                'reported_by': m['reported_by_role'],
                'reported_reason': m['reported_reason'],
                'can_report': actor_role in ('doctor', 'admin') and not m['is_reported'] and m['sender_role'] == 'patient'
            }
            for m in messages
        ]
    }

def _format_time_12h(hour_24, minute):
    suffix = 'AM' if hour_24 < 12 else 'PM'
    display_hour = hour_24 % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour:02d}:{minute:02d} {suffix}"


def slot_to_minutes(slot_label):
    try:
        hm, period = slot_label.strip().split(' ')
        hh, mm = map(int, hm.split(':'))
    except (ValueError, AttributeError):
        return None

    if period.upper() == 'PM' and hh != 12:
        hh += 12
    if period.upper() == 'AM' and hh == 12:
        hh = 0
    return hh * 60 + mm


def get_department_lunch_window(conn, department, doctor_id):
    dept_doctors = conn.execute(
        '''SELECT id
           FROM doctors
           WHERE department=? AND is_active=1
           ORDER BY name''',
        (department,)
    ).fetchall()

    if not dept_doctors:
        return None

    ordered_ids = [row['id'] for row in dept_doctors]
    if doctor_id not in ordered_ids:
        return None

    lunch_index = ordered_ids.index(doctor_id) % len(DOCTOR_LUNCH_WINDOWS)
    return DOCTOR_LUNCH_WINDOWS[lunch_index]


def filter_slots_for_constraints(conn, department, doctor_id, slot_labels, apt_date):
    lunch_window = get_department_lunch_window(conn, department, doctor_id)
    apt_date_obj = datetime.strptime(apt_date, '%Y-%m-%d').date()
    today = date.today()
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute

    available = []
    for slot in slot_labels:
        slot_minutes = slot_to_minutes(slot)
        if slot_minutes is None:
            continue

        # Keep each doctor unavailable in their allocated lunch hour.
        if lunch_window and lunch_window[0] <= slot_minutes < lunch_window[1]:
            continue

        # For same-day bookings, prevent assigning a slot that already passed.
        if apt_date_obj == today and slot_minutes <= now_minutes:
            continue

        available.append(slot)

    return available


def is_within_booking_hours(now=None):
    current = now or datetime.now()
    return BOOKING_OPEN_HOUR <= current.hour < BOOKING_CLOSE_HOUR


def next_booking_date_string(now=None):
    current = now or datetime.now()
    target = current.date()
    if not is_within_booking_hours(current):
        target = current.date() + timedelta(days=1)
    return target.strftime('%Y-%m-%d')

def build_time_slots(slot_duration_minutes):
    duration = max(15, int(slot_duration_minutes or DEFAULT_SLOT_DURATION_MINUTES))
    slots = []
    for start_str, end_str in WORKING_WINDOWS:
        start_h, start_m = map(int, start_str.split(':'))
        end_h, end_m = map(int, end_str.split(':'))
        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m
        t = start_total
        while t < end_total:
            hh = t // 60
            mm = t % 60
            slots.append(_format_time_12h(hh, mm))
            t += duration
    return slots

TIME_SLOTS = build_time_slots(DEFAULT_SLOT_DURATION_MINUTES)

DOCTORS = {
    'General': ['Dr. Priya Sharma', 'Dr. Kiran Reddy'],
    'Cardiology': ['Dr. Arjun Mehta', 'Dr. Sunita Rao'],
    'Orthopedics': ['Dr. Vikram Singh', 'Dr. Anjali Patel'],
    'Neurology': ['Dr. Rohit Bose', 'Dr. Meera Nair'],
    'Pediatrics': ['Dr. Deepa Gupta', 'Dr. Suresh Kumar'],
    'ENT': ['Dr. Ramesh Iyer', 'Dr. Kavitha Menon'],
}

CONSULTATION_FEES = {
    'General': 200,
    'Cardiology': 500,
    'Orthopedics': 400,
    'Neurology': 550,
    'Pediatrics': 300,
    'ENT': 350,
}

def get_active_doctors_by_department(conn, department):
    return conn.execute(
        '''SELECT id, name, department, max_patients_per_day, slot_duration_minutes
           FROM doctors
           WHERE department=? AND is_active=1
           ORDER BY name''',
        (department,)
    ).fetchall()

def pick_doctor_and_slot(conn, department, apt_date):
    doctors = get_active_doctors_by_department(conn, department)

    # Real-world constraint: assignment should happen only to active doctor accounts.
    if not doctors:
        return None, None, None, None

    candidates = []
    for doctor in doctors:
        rows = conn.execute(
            'SELECT time_slot FROM appointments WHERE date=? AND department=? AND doctor=?',
            (apt_date, department, doctor['name'])
        ).fetchall()
        booked_slots = {row['time_slot'] for row in rows}
        doctor_slots = build_time_slots(doctor['slot_duration_minutes'])
        available_slots = [slot for slot in doctor_slots if slot not in booked_slots]
        available_slots = filter_slots_for_constraints(
            conn,
            department,
            doctor['id'],
            available_slots,
            apt_date
        )
        if not available_slots:
            continue

        load_count = conn.execute(
            'SELECT COUNT(*) FROM appointments WHERE date=? AND department=? AND doctor=?',
            (apt_date, department, doctor['name'])
        ).fetchone()[0]

        max_patients = int(doctor['max_patients_per_day'])
        if load_count >= max_patients:
            continue

        candidates.append({
            'doctor_id': doctor['id'],
            'doctor_name': doctor['name'],
            'load_count': load_count,
            'available_slots': available_slots,
            'slot_duration_minutes': doctor['slot_duration_minutes'],
        })

    if not candidates:
        return None, None, None, None

    min_load = min(item['load_count'] for item in candidates)
    min_load_candidates = [item for item in candidates if item['load_count'] == min_load]
    selected = random.choice(min_load_candidates)
    return selected['doctor_id'], selected['doctor_name'], selected['available_slots'][0], selected['slot_duration_minutes']

# ─── AI CHATBOT LOGIC ─────────────────────────────────────────────────────────

SYMPTOM_DB = {
    'fever': {
        'follow_up': 'How long have you had fever? (a) Less than 2 days  (b) 2-5 days  (c) More than 5 days',
        'key': 'fever_duration',
        'responses': {
            'a': {
                'diagnosis': 'Likely Viral Fever (early stage)',
                'medicines': ['Paracetamol 500mg – twice daily', 'ORS Sachets – after meals'],
                'advice': 'Rest well, drink plenty of fluids. Avoid cold foods.',
                'severity': 'low'
            },
            'b': {
                'diagnosis': 'Probable Viral/Bacterial Fever',
                'medicines': ['Paracetamol 650mg – thrice daily', 'Vitamin C tablet – once daily'],
                'advice': 'Monitor temperature. Visit a doctor if fever exceeds 102°F.',
                'severity': 'medium'
            },
            'c': {
                'diagnosis': 'Persistent Fever – Needs Evaluation',
                'medicines': ['Consult doctor before taking medicines'],
                'advice': '⚠️ Fever lasting more than 5 days needs blood tests. Please visit a doctor.',
                'severity': 'high'
            }
        }
    },
    'cough': {
        'follow_up': 'Is your cough: (a) Dry  (b) With phlegm/mucus  (c) With blood',
        'key': 'cough_type',
        'responses': {
            'a': {
                'diagnosis': 'Dry Cough / Throat Irritation',
                'medicines': ['Dextromethorphan cough syrup – 10ml thrice daily', 'Honey + Ginger tea – twice daily'],
                'advice': 'Avoid cold drinks and dusty environments. Gargle with warm salt water.',
                'severity': 'low'
            },
            'b': {
                'diagnosis': 'Productive Cough / Possible Bronchitis',
                'medicines': ['Ambroxol syrup – 10ml thrice daily', 'Steam inhalation – twice daily'],
                'advice': 'Stay hydrated. See a doctor if it persists more than 7 days.',
                'severity': 'medium'
            },
            'c': {
                'diagnosis': '🚨 URGENT: Blood in Cough',
                'medicines': ['Do NOT self-medicate'],
                'advice': '🚨 Coughing blood (hemoptysis) is a medical emergency. Go to the ER immediately.',
                'severity': 'emergency'
            }
        }
    },
    'headache': {
        'follow_up': 'Where is the pain? (a) Forehead/temples  (b) Back of head  (c) Entire head / throbbing',
        'key': 'headache_location',
        'responses': {
            'a': {
                'diagnosis': 'Tension Headache / Sinusitis',
                'medicines': ['Ibuprofen 400mg – after food', 'Nasal decongestant if blocked nose'],
                'advice': 'Rest in a quiet dark room. Apply cold/warm compress on forehead.',
                'severity': 'low'
            },
            'b': {
                'diagnosis': 'Cervicogenic Headache / Hypertension',
                'medicines': ['Paracetamol 500mg – twice daily'],
                'advice': 'Check your blood pressure. Avoid stress. Sleep on a proper pillow.',
                'severity': 'medium'
            },
            'c': {
                'diagnosis': 'Migraine / Severe Headache',
                'medicines': ['Sumatriptan 50mg (consult doctor)', 'Rest in dark silent room'],
                'advice': 'Avoid triggers like bright lights, loud noise. Track headache patterns.',
                'severity': 'medium'
            }
        }
    },
    'chest pain': {
        'follow_up': None,
        'immediate': True,
        'diagnosis': '🚨 EMERGENCY: Chest Pain Detected',
        'medicines': ['Call emergency services immediately'],
        'advice': '🚨 Chest pain can indicate a heart attack. CALL 108 / 112 IMMEDIATELY. Do not drive yourself.',
        'severity': 'emergency'
    },
    'stomach pain': {
        'follow_up': 'How would you describe it? (a) Cramps/bloating  (b) Sharp pain  (c) Pain with vomiting',
        'key': 'stomach_type',
        'responses': {
            'a': {
                'diagnosis': 'Gastritis / IBS / Indigestion',
                'medicines': ['Omeprazole 20mg – before breakfast', 'Antacid gel – after meals'],
                'advice': 'Eat light meals. Avoid spicy and oily food. Drink warm water.',
                'severity': 'low'
            },
            'b': {
                'diagnosis': 'Possible Appendicitis / Ulcer',
                'medicines': ['Do not take painkillers without diagnosis'],
                'advice': '⚠️ Sharp abdominal pain needs urgent doctor evaluation. Could be appendicitis.',
                'severity': 'high'
            },
            'c': {
                'diagnosis': 'Gastroenteritis / Food Poisoning',
                'medicines': ['ORS Solution – every 2 hours', 'Domperidone 10mg – before meals', 'Probiotics – once daily'],
                'advice': 'Stay hydrated. Eat BRAT diet (banana, rice, applesauce, toast).',
                'severity': 'medium'
            }
        }
    },
    'cold': {
        'follow_up': None,
        'immediate': True,
        'diagnosis': 'Common Cold / Rhinitis',
        'medicines': ['Cetirizine 10mg – at night', 'Nasal saline spray', 'Vitamin C 500mg – once daily'],
        'advice': 'Rest and drink warm fluids. Steam inhalation helps. Wash hands frequently.',
        'severity': 'low'
    },
    'back pain': {
        'follow_up': 'When does the pain occur? (a) After sitting long  (b) During movement  (c) Always / radiating to legs',
        'key': 'back_type',
        'responses': {
            'a': {
                'diagnosis': 'Postural Back Pain',
                'medicines': ['Ibuprofen gel – apply topically', 'Muscle relaxant (consult doctor)'],
                'advice': 'Improve posture. Use ergonomic chair. Do stretching exercises.',
                'severity': 'low'
            },
            'b': {
                'diagnosis': 'Muscular Back Pain / Strain',
                'medicines': ['Diclofenac 50mg – after food', 'Hot compress – twice daily'],
                'advice': 'Rest for 2-3 days. Avoid heavy lifting.',
                'severity': 'low'
            },
            'c': {
                'diagnosis': 'Sciatica / Disc Problem',
                'medicines': ['Consult an orthopedic specialist'],
                'advice': '⚠️ Radiating pain to legs could be nerve compression. Get an MRI done.',
                'severity': 'high'
            }
        }
    },
    'dizziness': {
        'follow_up': None,
        'immediate': True,
        'diagnosis': 'Vertigo / Low BP / Inner Ear Issue',
        'medicines': ['Meclizine 25mg for vertigo', 'ORS if dehydrated'],
        'advice': 'Sit/lie down immediately when dizzy. Avoid driving. Check blood pressure.',
        'severity': 'medium'
    },
    'anxiety': {
        'follow_up': None,
        'immediate': True,
        'diagnosis': 'Anxiety / Stress / Panic Attack',
        'medicines': ['No self-medication – consult a psychiatrist'],
        'advice': 'Practice deep breathing (4-7-8 technique). Reduce caffeine. Consider counseling.',
        'severity': 'medium'
    },
}

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '').lower().strip()
    context = data.get('context', {})
    step = data.get('step', 'initial')

    # Handle follow-up answers
    if step == 'followup':
        symptom = context.get('symptom')
        if symptom and symptom in SYMPTOM_DB:
            s = SYMPTOM_DB[symptom]
            if 'responses' in s:
                answer = message.strip().lower()
                if answer not in ['a', 'b', 'c']:
                    # try to match text
                    for k in ['a', 'b', 'c']:
                        if k in message:
                            answer = k
                            break
                result = s['responses'].get(answer, s['responses']['a'])
                return jsonify(build_response(result, symptom))

    # Detect symptom
    for symptom, info in SYMPTOM_DB.items():
        if symptom in message:
            if info.get('immediate'):
                result = {
                    'diagnosis': info['diagnosis'],
                    'medicines': info['medicines'],
                    'advice': info['advice'],
                    'severity': info['severity']
                }
                return jsonify(build_response(result, symptom))
            else:
                return jsonify({
                    'type': 'followup',
                    'message': f"I see you mentioned **{symptom}**. Let me ask a follow-up question to better understand.\n\n{info['follow_up']}",
                    'symptom': symptom,
                    'step': 'followup'
                })

    # Greetings
    greetings = ['hello', 'hi', 'hey', 'good morning', 'good evening', 'namaste']
    if any(g in message for g in greetings):
        return jsonify({
            'type': 'greeting',
            'message': "Hello! 👋 I'm **MediBot**, your AI health assistant.\n\nI can help you analyze symptoms like:\n- 🤒 Fever\n- 😷 Cough\n- 🤕 Headache\n- 💔 Chest Pain\n- 🤢 Stomach Pain\n- 🔄 Dizziness\n- 😰 Anxiety\n\nTell me what symptoms you're experiencing!"
        })

    # Help
    if 'help' in message or 'what can you do' in message:
        return jsonify({
            'type': 'help',
            'message': "I can analyze these symptoms:\n\n🤒 **Fever** | 😷 **Cough** | 🤕 **Headache**\n💔 **Chest Pain** | 🤢 **Stomach Pain** | 🔙 **Back Pain**\n🤧 **Cold** | 🔄 **Dizziness** | 😰 **Anxiety**\n\nJust describe your symptoms in simple words!"
        })

    # Emergency keywords
    emergency_words = ['emergency', 'unconscious', 'not breathing', 'heart attack', 'stroke', 'bleeding heavily']
    if any(e in message for e in emergency_words):
        return jsonify({
            'type': 'emergency',
            'message': '🚨 **EMERGENCY DETECTED!**\n\nPlease call **108** (Ambulance) or **112** (Emergency) IMMEDIATELY!\n\nDo not wait. This could be life-threatening.',
            'severity': 'emergency'
        })

    return jsonify({
        'type': 'unknown',
        'message': "I couldn't identify a specific symptom from your message. Please try describing your symptoms like:\n- \"I have **fever** for 2 days\"\n- \"I have **chest pain**\"\n- \"I have **headache**\"\n\nOr type **help** to see what I can analyze."
    })

def build_response(result, symptom):
    severity_colors = {'low': '🟢', 'medium': '🟡', 'high': '🔴', 'emergency': '🚨'}
    icon = severity_colors.get(result['severity'], '🔵')
    meds = '\n'.join([f"• {m}" for m in result['medicines']])
    return {
        'type': 'diagnosis',
        'message': f"**Diagnosis:** {result['diagnosis']}\n\n**Recommended Medicines:**\n{meds}\n\n**Advice:** {result['advice']}",
        'severity': result['severity'],
        'icon': icon,
        'disclaimer': True
    }

# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        # Admin login
        if email == 'admin' and password == 'admin123':
            session['user_id'] = 0
            session.pop('doctor_id', None)
            session['user_name'] = 'Administrator'
            session['is_admin'] = True
            session['is_doctor'] = False
            return redirect(url_for('admin_dashboard'))

        hashed = hash_password(password)
        conn = get_db()

        doctor = conn.execute(
            'SELECT * FROM doctors WHERE email=? AND password=? AND is_active=1',
            (email, hashed)
        ).fetchone()
        if doctor:
            conn.close()
            session.pop('user_id', None)
            session['doctor_id'] = doctor['id']
            session['user_name'] = doctor['name']
            session['doctor_department'] = doctor['department']
            session['is_admin'] = False
            session['is_doctor'] = True
            return redirect(url_for('doctor_dashboard'))

        user = conn.execute('SELECT * FROM users WHERE email=? AND password=?', (email, hashed)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session.pop('doctor_id', None)
            session['user_name'] = user['name']
            session['is_admin'] = False
            session['is_doctor'] = False
            return redirect(url_for('dashboard'))
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        return api_signup()

    return render_template('signup.html')

@app.route('/api/signup', methods=['POST'])
def api_signup():
    payload = request.get_json(silent=True) if request.is_json else request.form

    name = (payload.get('name') or '').strip()
    email = (payload.get('email') or '').strip().lower()
    password = (payload.get('password') or '').strip()
    phone = (payload.get('phone') or '').strip()
    dob = (payload.get('dob') or '').strip()
    blood_group = (payload.get('blood_group') or '').strip()

    if not all([name, email, password]):
        return jsonify({'success': False, 'message': 'Please fill all required fields'}), 400

    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400

    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'success': False, 'message': 'Please enter a valid email'}), 400

    hashed = hash_password(password)
    conn = None

    try:
        conn = get_db()

        existing_user = conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if existing_user:
            return jsonify({'success': False, 'message': 'Email already registered'}), 409

        cursor = conn.execute(
            'INSERT INTO users (name, email, password, phone, dob, blood_group) VALUES (?,?,?,?,?,?)',
            (name, email, hashed, phone, dob, blood_group)
        )
        conn.commit()

        session['user_id'] = cursor.lastrowid
        session.pop('doctor_id', None)
        session['user_name'] = name
        session['is_admin'] = False
        session['is_doctor'] = False

        return jsonify({
            'success': True,
            'message': 'Account created successfully!',
            'redirect': url_for('dashboard')
        }), 201
    except sqlite3.OperationalError:
        return jsonify({'success': False, 'message': 'Database is busy. Please try again in a moment.'}), 503
    except Exception:
        return jsonify({'success': False, 'message': 'Could not create account right now. Please try again.'}), 500
    finally:
        if conn is not None:
            conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── USER ROUTES ──────────────────────────────────────────────────────────────

def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('is_admin') or session.get('is_doctor'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def require_doctor(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_doctor') or 'doctor_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/dashboard')
@require_login
def dashboard():
    user_id = session['user_id']
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    appointments = conn.execute('SELECT * FROM appointments WHERE user_id=? ORDER BY created_at DESC LIMIT 3', (user_id,)).fetchall()
    prescriptions = conn.execute('SELECT * FROM prescriptions WHERE user_id=? ORDER BY issued_at DESC LIMIT 3', (user_id,)).fetchall()
    bills = conn.execute('SELECT * FROM bills WHERE user_id=? ORDER BY created_at DESC LIMIT 3', (user_id,)).fetchall()
    conn.close()
    return render_template('dashboard.html', user=user, appointments=appointments, prescriptions=prescriptions, bills=bills)

@app.route('/chatbot')
@require_login
def chatbot():
    return render_template('chatbot.html')

@app.route('/book-appointment', methods=['GET', 'POST'])
@require_login
def book_appointment():
    if request.method == 'POST':
        user_id = session['user_id']
        department = (request.form.get('department') or '').strip()
        symptoms = (request.form.get('symptoms') or '').strip()
        apt_date = (request.form.get('date') or '').strip()

        if not department or not symptoms or not apt_date:
            return jsonify({'success': False, 'message': 'Please fill all required fields'}), 400

        try:
            apt_date_obj = datetime.strptime(apt_date, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid appointment date format'}), 400

        today = date.today()
        now = datetime.now()
        if apt_date_obj < today:
            return jsonify({'success': False, 'message': 'Past dates are not allowed'}), 400

        if apt_date_obj == today and not is_within_booking_hours(now):
            suggested_date = next_booking_date_string(now)
            return jsonify({
                'success': False,
                'message': 'Doctors are not available at this time today. Please book for tomorrow.',
                'suggested_date': suggested_date
            }), 409

        conn = None
        try:
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not user:
                session.clear()
                return jsonify({'success': False, 'message': 'Session expired. Please login again.'}), 401

            doctor_id, doctor, time_slot, slot_duration_minutes = pick_doctor_and_slot(conn, department, apt_date)
            if not doctor or not time_slot:
                message = 'All doctors are fully booked for this date'
                if apt_date_obj == today:
                    message = 'Doctors are not available at this time today. Please choose another slot or book for tomorrow.'
                return jsonify({'success': False, 'message': message}), 409

            apt_id = generate_appointment_id()
            consultation_fee = CONSULTATION_FEES.get(department, 200)

            conn.execute('''INSERT INTO appointments (appointment_id, user_id, patient_name, doctor_id, doctor, department, date, time_slot, symptoms)
                            VALUES (?,?,?,?,?,?,?,?,?)''',
                         (apt_id, user_id, user['name'], doctor_id, doctor, department, apt_date, time_slot, symptoms))

            # At booking time only consultation fee is generated.
            conn.execute('''INSERT INTO bills (user_id, appointment_id, consultation_fee, medicine_cost, total)
                            VALUES (?,?,?,?,?)''',
                         (user_id, apt_id, consultation_fee, 0, consultation_fee))

            conn.commit()

            return jsonify({
                'success': True,
                'appointment_id': apt_id,
                'doctor': doctor,
                'time_slot': time_slot,
                'slot_duration_minutes': slot_duration_minutes,
                'date': apt_date,
                'department': department,
                'consultation_fee': consultation_fee
            })
        finally:
            if conn is not None:
                conn.close()

    return render_template(
        'appointment.html',
        departments=list(DOCTORS.keys()),
        consultation_fees=CONSULTATION_FEES,
        default_slot_duration=DEFAULT_SLOT_DURATION_MINUTES
    )

def generate_prescription(symptoms):
    symptoms_lower = symptoms.lower() if symptoms else ''
    if 'fever' in symptoms_lower:
        return 'Viral Fever', 'Paracetamol 500mg (BD), ORS Sachets (TID)', 'Rest, drink fluids, avoid cold food'
    elif 'cough' in symptoms_lower:
        return 'Upper Respiratory Infection', 'Ambroxol 30mg syrup (TID), Cetirizine 10mg (OD at night)', 'Steam inhalation, warm fluids'
    elif 'headache' in symptoms_lower:
        return 'Tension Headache', 'Ibuprofen 400mg (BD after food)', 'Rest, avoid screen time'
    elif 'stomach' in symptoms_lower or 'abdomen' in symptoms_lower:
        return 'Gastritis', 'Omeprazole 20mg (OD before breakfast), Antacid gel (TID after meals)', 'Light diet, avoid spicy food'
    elif 'cold' in symptoms_lower:
        return 'Common Cold', 'Cetirizine 10mg (OD), Vitamin C 500mg (OD)', 'Steam inhalation, warm fluids'
    elif 'back' in symptoms_lower:
        return 'Lumbar Strain', 'Diclofenac 50mg (BD after food), Muscle relaxant', 'Rest, hot compress, light stretching'
    else:
        return 'General Checkup', 'Multivitamin tablet (OD), Calcium supplement', 'Balanced diet, regular exercise, adequate sleep'

def apply_consultation_completion(conn, apt, medicine_cost, diagnosis=None, medicines=None, instructions=None):
    if not diagnosis or not medicines or not instructions:
        auto_diagnosis, auto_medicines, auto_instructions = generate_prescription(apt['symptoms'] or '')
        diagnosis = diagnosis or auto_diagnosis
        medicines = medicines or auto_medicines
        instructions = instructions or auto_instructions
    existing_pres = conn.execute('SELECT id FROM prescriptions WHERE appointment_id=?',
                                 (apt['appointment_id'],)).fetchone()

    if existing_pres:
        conn.execute('''UPDATE prescriptions
                        SET diagnosis=?, medicines=?, instructions=?, doctor=?, issued_at=CURRENT_TIMESTAMP
                        WHERE id=?''',
                     (diagnosis, medicines, instructions, apt['doctor'], existing_pres['id']))
    else:
        conn.execute('''INSERT INTO prescriptions (user_id, appointment_id, diagnosis, medicines, instructions, doctor)
                        VALUES (?,?,?,?,?,?)''',
                     (apt['user_id'], apt['appointment_id'], diagnosis, medicines, instructions, apt['doctor']))

    bill = conn.execute('SELECT id, consultation_fee FROM bills WHERE appointment_id=?',
                        (apt['appointment_id'],)).fetchone()
    consultation_fee = bill['consultation_fee'] if bill and bill['consultation_fee'] else CONSULTATION_FEES.get(apt['department'], 200)
    total = consultation_fee + medicine_cost

    if bill:
        conn.execute('''UPDATE bills
                        SET consultation_fee=?, medicine_cost=?, total=?, status='Pending'
                        WHERE id=?''',
                     (consultation_fee, medicine_cost, total, bill['id']))
    else:
        conn.execute('''INSERT INTO bills (user_id, appointment_id, consultation_fee, medicine_cost, total, status)
                        VALUES (?,?,?,?,?,'Pending')''',
                     (apt['user_id'], apt['appointment_id'], consultation_fee, medicine_cost, total))

    completed_at = now_db_string()
    conn.execute("UPDATE appointments SET status='Completed', completed_at=? WHERE id=?", (completed_at, apt['id']))
    upsert_consultation_chat_session(conn, apt)

@app.route('/doctor')
@require_doctor
def doctor_dashboard():
    conn = get_db()
    doctor = conn.execute('SELECT * FROM doctors WHERE id=?', (session['doctor_id'],)).fetchone()
    appointments = conn.execute('''SELECT * FROM appointments
                                   WHERE doctor_id=?
                                   ORDER BY date ASC, time_slot ASC, created_at DESC''',
                                (session['doctor_id'],)).fetchall()
    conn.close()
    return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments)

@app.route('/doctor/consultation/<int:aid>', methods=['GET', 'POST'])
@require_doctor
def doctor_consultation_form(aid):
    conn = get_db()
    try:
        apt = conn.execute('SELECT * FROM appointments WHERE id=? AND doctor_id=?',
                           (aid, session['doctor_id'])).fetchone()
        if not apt:
            return redirect(url_for('doctor_dashboard'))

        existing_pres = conn.execute('SELECT * FROM prescriptions WHERE appointment_id=?',
                                     (apt['appointment_id'],)).fetchone()
        existing_bill = conn.execute('SELECT * FROM bills WHERE appointment_id=?',
                                     (apt['appointment_id'],)).fetchone()

        error_message = None
        if request.method == 'POST':
            diagnosis = (request.form.get('diagnosis') or '').strip()
            medicines = (request.form.get('medicines') or '').strip()
            instructions = (request.form.get('instructions') or '').strip()
            medicine_cost_raw = (request.form.get('medicine_cost') or '').strip()

            if not diagnosis or not medicines or not instructions:
                error_message = 'Please fill diagnosis, medicines, and instructions'
                return render_template('doctor_consultation_form.html', appointment=apt, prescription=existing_pres, bill=existing_bill, error_message=error_message)

            if not medicine_cost_raw.isdigit():
                error_message = 'Enter a valid medicine cost'
                return render_template('doctor_consultation_form.html', appointment=apt, prescription=existing_pres, bill=existing_bill, error_message=error_message)

            apply_consultation_completion(conn, apt, int(medicine_cost_raw), diagnosis, medicines, instructions)
            conn.commit()
            return redirect(url_for('doctor_dashboard'))

        return render_template('doctor_consultation_form.html', appointment=apt, prescription=existing_pres, bill=existing_bill, error_message=error_message)
    finally:
        conn.close()

@app.route('/doctor/complete-consultation/<int:aid>', methods=['POST'])
@require_doctor
def doctor_complete_consultation(aid):
    medicine_cost_raw = (request.form.get('medicine_cost') or '').strip()
    if not medicine_cost_raw.isdigit():
        return jsonify({'success': False, 'message': 'Enter a valid medicine cost'}), 400

    medicine_cost = int(medicine_cost_raw)
    conn = get_db()
    try:
        apt = conn.execute('SELECT * FROM appointments WHERE id=? AND doctor_id=?',
                           (aid, session['doctor_id'])).fetchone()
        if not apt:
            return jsonify({'success': False, 'message': 'Appointment not found for this doctor'}), 404

        apply_consultation_completion(conn, apt, medicine_cost)
        conn.commit()
        return jsonify({'success': True, 'message': 'Consultation completed and medicine bill generated'})
    finally:
        conn.close()

@app.route('/appointments')
@require_login
def appointments():
    conn = get_db()
    apts = conn.execute('SELECT * FROM appointments WHERE user_id=? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('appointments.html', appointments=apts)

@app.route('/prescriptions')
@require_login
def prescriptions():
    conn = get_db()
    presc = conn.execute('''SELECT p.*, a.department FROM prescriptions p
                            LEFT JOIN appointments a ON p.appointment_id = a.appointment_id
                            WHERE p.user_id=? ORDER BY p.issued_at DESC''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('prescriptions.html', prescriptions=presc)

@app.route('/billing')
@require_login
def billing():
    conn = get_db()
    bills = conn.execute('''SELECT b.*, a.department, a.doctor, a.date FROM bills b
                            LEFT JOIN appointments a ON b.appointment_id = a.appointment_id
                            WHERE b.user_id=? ORDER BY b.created_at DESC''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('billing.html', bills=bills)

@app.route('/download-bill/<int:bill_id>')
@require_login
def download_bill(bill_id):
    conn = get_db()
    bill = conn.execute('''SELECT b.*, a.department, a.doctor, a.date, u.name, u.email, u.phone
                           FROM bills b
                           LEFT JOIN appointments a ON b.appointment_id = a.appointment_id
                           LEFT JOIN users u ON b.user_id = u.id
                           WHERE b.id=? AND b.user_id=?''', (bill_id, session['user_id'])).fetchone()
    conn.close()
    if not bill:
        return "Bill not found", 404

    content = f"""
╔══════════════════════════════════════════════╗
║         MEDI CARE HOSPITAL - BILL            ║
╚══════════════════════════════════════════════╝

Patient Name  : {bill['name']}
Email         : {bill['email']}
Phone         : {bill['phone'] or 'N/A'}
Appointment ID: {bill['appointment_id']}
Department    : {bill['department'] or 'N/A'}
Doctor        : {bill['doctor'] or 'N/A'}
Date          : {bill['date'] or 'N/A'}

──────────────────────────────────────────────
            BILLING DETAILS
──────────────────────────────────────────────
Consultation Fee  :  ₹{bill['consultation_fee']}
Medicine Cost     :  ₹{bill['medicine_cost']}
──────────────────────────────────────────────
TOTAL AMOUNT      :  ₹{bill['total']}
Payment Status    :  {bill['status']}
──────────────────────────────────────────────

Generated on: {datetime.now().strftime('%d %B %Y, %I:%M %p')}

Thank you for choosing Medi Care Hospital!
For queries: support@medicarehospital.com
"""
    from flask import Response
    return Response(
        content,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment;filename=Bill_{bill["appointment_id"]}.txt'}
    )


@app.route('/consultation-chat/<appointment_id>')
@require_login
def patient_consultation_chat(appointment_id):
    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, 'patient', session['user_id'])
        if not apt:
            return redirect(url_for('prescriptions'))

        if apt['status'] != 'Completed':
            return redirect(url_for('prescriptions'))

        payload = build_chat_state_payload(conn, apt, chat_session, 'patient')
        return render_template('consultation_chat.html', view_role='patient', chat_data=payload)
    finally:
        conn.close()


@app.route('/doctor/chat/<appointment_id>')
@require_doctor
def doctor_consultation_chat(appointment_id):
    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, 'doctor', session['doctor_id'])
        if not apt:
            return redirect(url_for('doctor_dashboard'))

        payload = build_chat_state_payload(conn, apt, chat_session, 'doctor')
        return render_template('consultation_chat.html', view_role='doctor', chat_data=payload)
    finally:
        conn.close()


@app.route('/admin/chat/<appointment_id>')
def admin_consultation_chat(appointment_id):
    if not session.get('is_admin'):
        return redirect(url_for('login'))

    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, 'admin', None)
        if not apt:
            return redirect(url_for('admin_chats'))

        payload = build_chat_state_payload(conn, apt, chat_session, 'admin')
        return render_template('consultation_chat.html', view_role='admin', chat_data=payload)
    finally:
        conn.close()


@app.route('/api/consultation-chat/<appointment_id>/state')
def consultation_chat_state(appointment_id):
    actor_role, actor_id = get_actor_context()
    if actor_role is None:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, actor_role, actor_id)
        if not apt:
            return jsonify({'success': False, 'message': 'Chat not found'}), 404

        payload = build_chat_state_payload(conn, apt, chat_session, actor_role)
        return jsonify({'success': True, 'data': payload})
    finally:
        conn.close()


@app.route('/api/consultation-chat/<appointment_id>/message', methods=['POST'])
def consultation_chat_send_message(appointment_id):
    actor_role, actor_id = get_actor_context()
    if actor_role not in ('patient', 'doctor'):
        return jsonify({'success': False, 'message': 'Only patient or doctor can send messages'}), 403

    if actor_role == 'doctor' and not session.get('is_doctor'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if actor_role == 'patient' and 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    message = (request.json or {}).get('message', '') if request.is_json else (request.form.get('message') or '')
    message = (message or '').strip()
    if not message:
        return jsonify({'success': False, 'message': 'Message cannot be empty'}), 400
    if len(message) > 500:
        return jsonify({'success': False, 'message': 'Message is too long'}), 400

    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, actor_role, actor_id)
        if not apt or not chat_session:
            return jsonify({'success': False, 'message': 'Chat unavailable'}), 404

        chat_session = sync_consultation_chat_status(conn, chat_session)
        if chat_session['status'] != 'open':
            conn.commit()
            return jsonify({'success': False, 'message': 'Chat is paused. Request access from admin.'}), 409

        now = datetime.now()
        created_at = now_db_string(now)
        expires_at = now_db_string(now + timedelta(minutes=CONSULTATION_CHAT_OPEN_MINUTES))
        conn.execute(
            '''INSERT INTO consultation_chat_messages (session_id, sender_role, sender_id, message, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            (chat_session['id'], actor_role, actor_id, message, created_at)
        )

        conn.execute(
            '''UPDATE consultation_chat_sessions
               SET last_message_at=?, expires_at=?, updated_at=?
               WHERE id=?''',
            (created_at, expires_at, created_at, chat_session['id'])
        )
        conn.commit()

        return jsonify({'success': True})
    finally:
        conn.close()


@app.route('/api/consultation-chat/<appointment_id>/request-access', methods=['POST'])
@require_login
def consultation_chat_request_access(appointment_id):
    note = (request.json or {}).get('note', '') if request.is_json else (request.form.get('note') or '')
    note = (note or '').strip()
    if len(note) > 300:
        return jsonify({'success': False, 'message': 'Request note is too long'}), 400

    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, 'patient', session['user_id'])
        if not apt or not chat_session:
            return jsonify({'success': False, 'message': 'Chat not found'}), 404

        chat_session = sync_consultation_chat_status(conn, chat_session)
        if chat_session['status'] == 'open':
            conn.commit()
            return jsonify({'success': False, 'message': 'Chat is already open'}), 409

        deadline = parse_db_datetime(chat_session['request_deadline'])
        if not deadline or datetime.now() > deadline:
            conn.commit()
            return jsonify({'success': False, 'message': 'Access request window closed (1 hour limit).'}), 409

        existing_pending = conn.execute(
            '''SELECT id FROM consultation_chat_access_requests
               WHERE session_id=? AND status='pending'
               ORDER BY id DESC LIMIT 1''',
            (chat_session['id'],)
        ).fetchone()
        if existing_pending:
            conn.commit()
            return jsonify({'success': False, 'message': 'You already have a pending request'}), 409

        now = now_db_string()
        conn.execute(
            '''INSERT INTO consultation_chat_access_requests
               (session_id, requested_by_user_id, request_note, status, created_at)
               VALUES (?, ?, ?, 'pending', ?)''',
            (chat_session['id'], session['user_id'], note, now)
        )
        conn.execute(
            'UPDATE consultation_chat_sessions SET last_access_request_at=?, updated_at=? WHERE id=?',
            (now, now, chat_session['id'])
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Access request sent to admin'})
    finally:
        conn.close()


@app.route('/api/consultation-chat/<appointment_id>/report-message', methods=['POST'])
def consultation_chat_report_message(appointment_id):
    actor_role, actor_id = get_actor_context()
    if actor_role not in ('doctor', 'admin'):
        return jsonify({'success': False, 'message': 'Only doctor/admin can report messages'}), 403

    payload = request.json or {}
    message_id = payload.get('message_id')
    reason = (payload.get('reason') or '').strip()
    if not message_id:
        return jsonify({'success': False, 'message': 'Message ID is required'}), 400
    if len(reason) > 240:
        return jsonify({'success': False, 'message': 'Reason is too long'}), 400

    conn = get_db()
    try:
        apt, chat_session = load_chat_for_actor(conn, appointment_id, actor_role, actor_id)
        if not apt or not chat_session:
            return jsonify({'success': False, 'message': 'Chat not found'}), 404

        msg = conn.execute(
            'SELECT * FROM consultation_chat_messages WHERE id=? AND session_id=?',
            (message_id, chat_session['id'])
        ).fetchone()
        if not msg:
            return jsonify({'success': False, 'message': 'Message not found'}), 404
        if msg['is_reported']:
            return jsonify({'success': False, 'message': 'Already reported'}), 409

        now = now_db_string()
        conn.execute(
            '''UPDATE consultation_chat_messages
               SET is_reported=1, reported_by_role=?, reported_by_id=?, reported_reason=?, reported_at=?
               WHERE id=?''',
            (actor_role, actor_id, reason, now, message_id)
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'Message reported for review'})
    finally:
        conn.close()


def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ─── ADMIN ROUTES ─────────────────────────────────────────────────────────────

@app.route('/admin')
@require_admin
def admin_dashboard():
    conn = get_db()
    total_patients = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_appointments = conn.execute('SELECT COUNT(*) FROM appointments').fetchone()[0]
    total_prescriptions = conn.execute('SELECT COUNT(*) FROM prescriptions').fetchone()[0]
    total_revenue = conn.execute('SELECT SUM(total) FROM bills').fetchone()[0] or 0
    recent_apts = conn.execute('''SELECT a.*, u.email FROM appointments a
                                  LEFT JOIN users u ON a.user_id = u.id
                                  ORDER BY a.created_at DESC LIMIT 5''').fetchall()
    conn.close()
    return render_template('admin_dashboard.html',
                           total_patients=total_patients,
                           total_appointments=total_appointments,
                           total_prescriptions=total_prescriptions,
                           total_revenue=total_revenue,
                           recent_apts=recent_apts)

@app.route('/admin/patients')
@require_admin
def admin_patients():
    search = request.args.get('search', '')
    conn = get_db()
    if search:
        patients = conn.execute("SELECT * FROM users WHERE name LIKE ? OR email LIKE ?",
                                (f'%{search}%', f'%{search}%')).fetchall()
    else:
        patients = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin_patients.html', patients=patients, search=search)

@app.route('/admin/doctors')
@require_admin
def admin_doctors():
    conn = get_db()
    doctors = conn.execute('''SELECT d.*, 
                                     COUNT(a.id) AS total_appointments,
                                     SUM(CASE WHEN a.status='Completed' THEN 1 ELSE 0 END) AS completed_appointments
                              FROM doctors d
                              LEFT JOIN appointments a ON a.doctor_id = d.id
                              GROUP BY d.id
                              ORDER BY d.department, d.name''').fetchall()
    conn.close()
    return render_template('admin_doctors.html', doctors=doctors)


@app.route('/admin/doctors/<int:did>')
@require_admin
def admin_doctor_profile(did):
    conn = get_db()
    try:
        doctor = conn.execute(
            '''SELECT d.*,
                      COUNT(a.id) AS total_appointments,
                      SUM(CASE WHEN a.status='Completed' THEN 1 ELSE 0 END) AS completed_appointments,
                      SUM(CASE WHEN a.date=? THEN 1 ELSE 0 END) AS today_appointments
               FROM doctors d
               LEFT JOIN appointments a ON a.doctor_id=d.id
               WHERE d.id=?
               GROUP BY d.id''',
            (date.today().strftime('%Y-%m-%d'), did)
        ).fetchone()

        if not doctor:
            return redirect(url_for('admin_doctors'))

        appointments = conn.execute(
            '''SELECT a.*,
                      u.email AS patient_email,
                      p.diagnosis,
                      p.medicines
               FROM appointments a
               LEFT JOIN users u ON u.id = a.user_id
               LEFT JOIN prescriptions p ON p.appointment_id = a.appointment_id
               WHERE a.doctor_id=?
               ORDER BY a.date DESC, a.time_slot DESC, a.created_at DESC
               LIMIT 25''',
            (did,)
        ).fetchall()

        lunch_window = get_department_lunch_window(conn, doctor['department'], doctor['id'])
        lunch_label = 'Not assigned'
        if lunch_window:
            start_h, start_m = divmod(lunch_window[0], 60)
            end_h, end_m = divmod(lunch_window[1], 60)
            lunch_label = f"{_format_time_12h(start_h, start_m)} - {_format_time_12h(end_h, end_m)}"

        return render_template('admin_doctor_profile.html', doctor=doctor, appointments=appointments, lunch_label=lunch_label)
    finally:
        conn.close()

@app.route('/admin/doctors/create', methods=['POST'])
@require_admin
def admin_create_doctor():
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    department = (request.form.get('department') or '').strip()
    password = (request.form.get('password') or 'doctor123').strip()
    max_patients_raw = (request.form.get('max_patients_per_day') or str(DEFAULT_MAX_PATIENTS_PER_DAY)).strip()
    slot_duration_raw = (request.form.get('slot_duration_minutes') or str(DEFAULT_SLOT_DURATION_MINUTES)).strip()

    if not all([name, email, department, password]):
        return redirect(url_for('admin_doctors'))

    if not max_patients_raw.isdigit() or not slot_duration_raw.isdigit():
        return redirect(url_for('admin_doctors'))

    max_patients = max(1, int(max_patients_raw))
    slot_duration = max(15, int(slot_duration_raw))
    hashed = hash_password(password)

    conn = get_db()
    try:
        conn.execute('''INSERT INTO doctors (name, email, password, department, max_patients_per_day, slot_duration_minutes, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)''',
                     (name, email, hashed, department, max_patients, slot_duration))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

    return redirect(url_for('admin_doctors'))

@app.route('/admin/doctors/<int:did>/update', methods=['POST'])
@require_admin
def admin_update_doctor(did):
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    department = (request.form.get('department') or '').strip()
    max_patients_raw = (request.form.get('max_patients_per_day') or '').strip()
    slot_duration_raw = (request.form.get('slot_duration_minutes') or '').strip()

    if not all([name, email, department, max_patients_raw, slot_duration_raw]):
        return redirect(url_for('admin_doctors'))

    if not max_patients_raw.isdigit() or not slot_duration_raw.isdigit():
        return redirect(url_for('admin_doctors'))

    conn = get_db()
    try:
        conn.execute('''UPDATE doctors
                        SET name=?, email=?, department=?, max_patients_per_day=?, slot_duration_minutes=?
                        WHERE id=?''',
                     (name, email, department, max(1, int(max_patients_raw)), max(15, int(slot_duration_raw)), did))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('admin_doctors'))

@app.route('/admin/doctors/<int:did>/toggle-active', methods=['POST'])
@require_admin
def admin_toggle_doctor_active(did):
    conn = get_db()
    try:
        doctor = conn.execute('SELECT is_active FROM doctors WHERE id=?', (did,)).fetchone()
        if doctor:
            next_state = 0 if doctor['is_active'] else 1
            conn.execute('UPDATE doctors SET is_active=? WHERE id=?', (next_state, did))
            conn.commit()
    finally:
        conn.close()

    return redirect(url_for('admin_doctors'))

@app.route('/admin/doctors/<int:did>/reset-password', methods=['POST'])
@require_admin
def admin_reset_doctor_password(did):
    new_password = (request.form.get('new_password') or 'doctor123').strip()
    if len(new_password) < 6:
        new_password = 'doctor123'

    conn = get_db()
    try:
        conn.execute('UPDATE doctors SET password=? WHERE id=?', (hash_password(new_password), did))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('admin_doctors'))

@app.route('/admin/appointments')
@require_admin
def admin_appointments():
    search = request.args.get('search', '')
    conn = get_db()
    if search:
        apts = conn.execute('''SELECT a.*, u.email, p.diagnosis, p.medicines FROM appointments a
                               LEFT JOIN users u ON a.user_id=u.id
                               LEFT JOIN prescriptions p ON p.appointment_id = a.appointment_id
                               WHERE a.patient_name LIKE ? OR a.appointment_id LIKE ? OR a.department LIKE ?
                               ORDER BY a.created_at DESC''',
                            (f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        apts = conn.execute('''SELECT a.*, u.email, p.diagnosis, p.medicines FROM appointments a
                               LEFT JOIN users u ON a.user_id=u.id
                               LEFT JOIN prescriptions p ON p.appointment_id = a.appointment_id
                               ORDER BY a.created_at DESC''').fetchall()
    conn.close()
    return render_template('admin_appointments.html', appointments=apts, search=search)


@app.route('/admin/chats')
@require_admin
def admin_chats():
    conn = get_db()
    try:
        sessions = conn.execute(
            '''SELECT s.*, a.patient_name, a.doctor, a.department, a.status AS appointment_status,
                      (SELECT COUNT(*) FROM consultation_chat_messages m WHERE m.session_id=s.id) AS message_count,
                      (SELECT message FROM consultation_chat_messages m2 WHERE m2.session_id=s.id ORDER BY m2.id DESC LIMIT 1) AS last_message,
                      (SELECT COUNT(*) FROM consultation_chat_access_requests r WHERE r.session_id=s.id AND r.status='pending') AS pending_requests
               FROM consultation_chat_sessions s
               LEFT JOIN appointments a ON a.appointment_id = s.appointment_id
               ORDER BY s.updated_at DESC, s.id DESC'''
        ).fetchall()

        pending_requests = conn.execute(
            '''SELECT r.*, s.appointment_id, a.patient_name, a.doctor, a.department
               FROM consultation_chat_access_requests r
               LEFT JOIN consultation_chat_sessions s ON s.id=r.session_id
               LEFT JOIN appointments a ON a.appointment_id=s.appointment_id
               WHERE r.status='pending'
               ORDER BY r.created_at DESC'''
        ).fetchall()

        return render_template('admin_chats.html', sessions=sessions, pending_requests=pending_requests)
    finally:
        conn.close()


@app.route('/admin/chat-request/<int:request_id>/<decision>', methods=['POST'])
@require_admin
def admin_chat_request_decision(request_id, decision):
    if decision not in ('approve', 'reject'):
        return redirect(url_for('admin_chats'))

    review_note = (request.form.get('review_note') or '').strip()
    if len(review_note) > 300:
        review_note = review_note[:300]

    conn = get_db()
    try:
        req = conn.execute(
            "SELECT * FROM consultation_chat_access_requests WHERE id=? AND status='pending'",
            (request_id,)
        ).fetchone()
        if not req:
            return redirect(url_for('admin_chats'))

        now = datetime.now()
        now_str = now_db_string(now)
        final_status = 'approved' if decision == 'approve' else 'rejected'

        conn.execute(
            '''UPDATE consultation_chat_access_requests
               SET status=?, reviewed_by_admin=?, reviewed_at=?, review_note=?
               WHERE id=?''',
            (final_status, session.get('user_name', 'admin'), now_str, review_note, request_id)
        )

        if decision == 'approve':
            expires_at = now_db_string(now + timedelta(minutes=CONSULTATION_CHAT_OPEN_MINUTES))
            conn.execute(
                '''UPDATE consultation_chat_sessions
                   SET status='open', expires_at=?, updated_at=?
                   WHERE id=?''',
                (expires_at, now_str, req['session_id'])
            )

        conn.commit()
        return redirect(url_for('admin_chats'))
    finally:
        conn.close()

@app.route('/admin/complete-consultation/<int:aid>', methods=['POST'])
@require_admin
def complete_consultation(aid):
    medicine_cost_raw = (request.form.get('medicine_cost') or '').strip()
    if not medicine_cost_raw.isdigit():
        return jsonify({'success': False, 'message': 'Enter a valid medicine cost'}), 400

    medicine_cost = int(medicine_cost_raw)
    conn = get_db()

    try:
        apt = conn.execute('SELECT * FROM appointments WHERE id=?', (aid,)).fetchone()
        if not apt:
            return jsonify({'success': False, 'message': 'Appointment not found'}), 404

        apply_consultation_completion(conn, apt, medicine_cost)
        conn.commit()

        return jsonify({'success': True, 'message': 'Consultation completed and medicine bill generated'})
    finally:
        conn.close()

@app.route('/admin/delete-patient/<int:pid>', methods=['POST'])
@require_admin
def delete_patient(pid):
    conn = get_db()
    sessions = conn.execute('SELECT id FROM consultation_chat_sessions WHERE user_id=?', (pid,)).fetchall()
    session_ids = [row['id'] for row in sessions]
    for sid in session_ids:
        conn.execute('DELETE FROM consultation_chat_access_requests WHERE session_id=?', (sid,))
        conn.execute('DELETE FROM consultation_chat_messages WHERE session_id=?', (sid,))
    conn.execute('DELETE FROM consultation_chat_sessions WHERE user_id=?', (pid,))
    conn.execute('DELETE FROM bills WHERE user_id=?', (pid,))
    conn.execute('DELETE FROM prescriptions WHERE user_id=?', (pid,))
    conn.execute('DELETE FROM appointments WHERE user_id=?', (pid,))
    conn.execute('DELETE FROM users WHERE id=?', (pid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/admin/delete-appointment/<int:aid>', methods=['POST'])
@require_admin
def delete_appointment(aid):
    conn = get_db()
    apt = conn.execute('SELECT appointment_id FROM appointments WHERE id=?', (aid,)).fetchone()
    if apt:
        apt_id = apt['appointment_id']
        chat_session = conn.execute('SELECT id FROM consultation_chat_sessions WHERE appointment_id=?', (apt_id,)).fetchone()
        if chat_session:
            conn.execute('DELETE FROM consultation_chat_access_requests WHERE session_id=?', (chat_session['id'],))
            conn.execute('DELETE FROM consultation_chat_messages WHERE session_id=?', (chat_session['id'],))
            conn.execute('DELETE FROM consultation_chat_sessions WHERE id=?', (chat_session['id'],))
        conn.execute('DELETE FROM bills WHERE appointment_id=?', (apt_id,))
        conn.execute('DELETE FROM prescriptions WHERE appointment_id=?', (apt_id,))
        conn.execute('DELETE FROM appointments WHERE id=?', (aid,))
        conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
