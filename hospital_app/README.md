# 🏥 Medi Care Hospital Management System

A full-stack AI-powered Hospital Management System built with Python Flask, SQLite, and vanilla HTML/CSS/JS.

---

## 🚀 Setup Instructions

### Step 1 — Install Python
Make sure Python 3.8+ is installed.
```
python --version
```

### Step 2 — Create Virtual Environment (Recommended)
```
cd hospital_app
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### Step 3 — Install Dependencies
```
pip install -r requirements.txt
```

### Step 4 — Run the Application
```
python app.py
```

### Step 5 — Open in Browser
```
http://localhost:5000
```

---

## 🔑 Login Credentials

### Admin Login
- Username: `admin`
- Password: `admin123`

### Patient Login
- Sign up with any email and password

---

## 📁 Project Structure

```
hospital_app/
├── app.py                    ← Main Flask application
├── requirements.txt
├── hospital.db               ← SQLite DB (auto-created on first run)
├── templates/
│   ├── base.html             ← Layout with navbar + sidebar
│   ├── login.html            ← Login + Signup page
│   ├── dashboard.html        ← Patient dashboard
│   ├── chatbot.html          ← AI chatbot page
│   ├── appointment.html      ← Book appointment
│   ├── appointments.html     ← View all appointments
│   ├── prescriptions.html    ← View prescriptions
│   ├── billing.html          ← View bills + download
│   ├── admin_dashboard.html  ← Admin overview
│   ├── admin_patients.html   ← Manage patients
│   └── admin_appointments.html ← Manage appointments
└── static/
    ├── css/
    │   ├── main.css          ← Global styles + glassmorphism
    │   ├── auth.css          ← Login/signup styles
    │   └── chatbot.css       ← Chatbot UI styles
    └── js/
        ├── main.js           ← Utilities, toast, theme
        └── chatbot.js        ← AI chatbot logic

```

---

## ✨ Features

### Patient Features
- ✅ Signup / Login with session management
- ✅ Patient dashboard with profile card
- ✅ AI chatbot for symptom analysis (9 symptoms)
- ✅ Book appointments with auto time-slot assignment
- ✅ View all appointments
- ✅ Auto-generated prescriptions
- ✅ Billing with downloadable text bill

### Admin Features
- ✅ Admin dashboard with summary stats
- ✅ View & search all patients
- ✅ View & search all appointments
- ✅ Delete patient/appointment records
- ✅ Revenue tracking

### AI Chatbot (Rule-Based)
Handles: Fever, Cough, Headache, Chest Pain, Stomach Pain, Cold, Back Pain, Dizziness, Anxiety
- Follow-up questions for accurate diagnosis
- Emergency detection with 108 alert
- Medicine recommendations
- Doctor's advice

### UI/UX
- 🌙 Dark/Light mode toggle
- 🎨 Glassmorphism design
- ✨ Animated backgrounds
- 🔔 Toast notifications
- 📱 Responsive layout
- 💫 Smooth transitions & hover effects
- 🚨 Emergency floating button

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python Flask |
| Database | SQLite3 |
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Fonts | Syne + DM Sans (Google Fonts) |
| Auth | SHA-256 password hashing |
| AI | Rule-based symptom engine |

---

## 📌 Notes
- No external AI API required — fully offline symptom engine
- Database is auto-created on first run
- All bills can be downloaded as `.txt` files
