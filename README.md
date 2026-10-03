# 🩸 LifeLink — Real-Time Emergency Blood Donor Coordination

**LifeLink** is a full-stack emergency blood donor coordination platform designed to help people find **potential nearby, compatible blood donors faster** during urgent situations.

The project focuses on turning an unstructured emergency blood request into a structured workflow — from creating a request and finding compatible donors to real-time responses, consent-based contact sharing, and request status tracking.

> ⚠️ **Disclaimer:** LifeLink is a prototype and coordination tool. It does not guarantee blood availability or donor eligibility and is not a replacement for hospitals, blood banks, or emergency medical services. Final donor eligibility and medical decisions must always be handled by qualified medical professionals.

---

## 🚨 Why LifeLink?

During a blood emergency, people often rely on WhatsApp groups, social media posts, phone calls, or manually maintained donor lists.

This creates several problems:

* Difficult to identify compatible donors quickly
* No structured way to find nearby donors
* Donor availability may be unknown
* Personal contact information can get exposed
* No proper real-time response tracking
* Multiple people may coordinate the same emergency independently
* Requesters often have no clear idea whether someone is actually responding

LifeLink explores how a software system can make this coordination more structured and privacy-aware.

---

## ✨ Key Features

### 🩸 Compatibility-Based Matching

LifeLink uses actual **ABO/Rh blood compatibility rules** to identify potentially compatible donors instead of relying on simple blood-group equality.

### 📍 Location-Based Matching

Potential donors are matched based on geographic distance using the **Haversine formula**.

The system progressively expands the search radius:

```text
5 km
 ↓
10 km
 ↓
20 km
```

This helps prioritize nearby donors before expanding the search.

### ⚡ Real-Time Communication

LifeLink uses **FastAPI WebSockets** to provide real-time updates.

Instead of repeatedly asking the server whether something changed, connected clients can receive events as soon as they occur.

```text
Emergency Request
       ↓
Matching Engine
       ↓
Donor Notification
       ↓
Donor Response
       ↓
Live Dashboard Update
```

### 🔐 Privacy-First Donor Interaction

A donor's personal information is not immediately exposed to a requester.

Contact information is shared only after the donor explicitly confirms their willingness to help through a consent step.

### 👤 Unified User Accounts

A user does not have to permanently choose between being a donor or requester.

The same account can:

* Register as a donor
* Become available to donate
* Create an emergency request
* Request blood for themselves or someone else

### 📊 Emergency Request Lifecycle

Requests move through structured states:

```text
OPEN
 ↓
DONOR_RESPONDED
 ↓
HOSPITAL_CONTACTED
 ↓
DONOR_CONFIRMED
 ↓
DONATION_IN_PROGRESS
 ↓
FULFILLED
```

Requests can also be:

```text
EXPIRED
CANCELLED
```

### 🛡️ Anti-Abuse Features

The MVP includes mechanisms such as:

* Request creation limits
* Rate limiting
* Abuse reporting
* Audit logging
* Maximum open-request controls

### 🧪 Demo Mode

A Demo Mode allows the complete emergency workflow to be simulated using realistic seeded data without depending on real donors.

This makes the project easier to demonstrate and test.

---

# 🏗️ Architecture

LifeLink follows a simple full-stack architecture:

```text
┌──────────────────────────────┐
│         Frontend             │
│  Vanilla JS + Tailwind CSS   │
│         + Leaflet            │
└──────────────┬───────────────┘
               │
        REST API / WebSocket
               │
               ▼
┌──────────────────────────────┐
│          FastAPI             │
│                              │
│ Authentication               │
│ Request Management           │
│ Donor Matching               │
│ Notifications                │
│ WebSocket Manager            │
│ Reports / Admin              │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│        SQLAlchemy ORM        │
│                              │
│          SQLite              │
└──────────────────────────────┘
```

---

# 🔄 How It Works

### 1. User creates an emergency request

The requester provides information such as:

* Blood group
* Required quantity
* Location
* Emergency details

### 2. FastAPI validates the request

The backend validates incoming data using **Pydantic schemas** before processing it.

### 3. Matching engine finds potential donors

The matching system considers:

* ABO/Rh compatibility
* Donor availability
* Geographic distance

### 4. Search radius expands if necessary

If insufficient potential donors are found:

```text
5 km → 10 km → 20 km
```

### 5. Donors receive notifications

Compatible donors can receive the emergency notification.

Inactive donors can also choose to become available for the specific emergency.

### 6. Donor responds

A donor can indicate that they are willing to help.

### 7. Consent is requested

Before personal contact information is shared, the donor explicitly confirms the action.

### 8. Request status updates in real time

The requester and relevant users can see the changing state of the emergency through WebSockets.

---

# 🧠 What I Learned

This project started primarily as a **learning-by-building project**, and that ended up being its biggest value.

Before LifeLink, I had worked with individual concepts like APIs, databases and authentication. Building this project helped me understand how these pieces work together in a real application.

One of the most important concepts I learned was the complete request lifecycle:

```text
Frontend
   ↓
HTTP Request
   ↓
FastAPI Endpoint
   ↓
Pydantic Validation
   ↓
Business Logic
   ↓
SQLAlchemy
   ↓
Database
   ↓
Response
   ↓
Frontend Update
```

I also learned and practiced:

* FastAPI
* REST API design
* WebSockets
* SQLAlchemy ORM
* SQLite
* JWT authentication
* Password hashing
* Pydantic validation
* Database relationships
* Geolocation calculations
* Backend architecture
* Authentication & authorization
* Real-time state synchronization
* Privacy-aware application design
* Error handling
* Rate limiting
* Audit logging

The project helped me understand that building an application isn't just about making the UI work — it's also about handling **security, state, validation, failures, privacy and communication between different parts of the system.**

---

# 🛠️ Tech Stack

| Layer             | Technology         |
| ----------------- | ------------------ |
| Backend           | FastAPI            |
| Language          | Python             |
| Database          | SQLite             |
| ORM               | SQLAlchemy         |
| Validation        | Pydantic           |
| Authentication    | JWT + bcrypt       |
| Real-Time         | FastAPI WebSockets |
| Frontend          | Vanilla JavaScript |
| Styling           | Tailwind CSS       |
| Maps              | Leaflet.js         |
| API Documentation | OpenAPI / Swagger  |

---

# 📁 Project Structure

```text
lifelink/
│
├── requirements.txt
├── README.md
├── lifelink.db
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── deps.py
│   ├── compatibility.py
│   ├── geo.py
│   ├── websocket_manager.py
│   ├── matching.py
│   ├── notify.py
│   ├── audit.py
│   │
│   └── routers/
│       ├── auth.py
│       ├── users.py
│       ├── requests.py
│       ├── donations.py
│       ├── notifications.py
│       ├── reports.py
│       ├── admin.py
│       └── public.py
│
└── frontend/
    ├── index.html
    ├── style.css
    ├── background.js
    └── app.js
```

---

# 🚀 Running Locally

### 1. Clone the repository

```bash
git clone YOUR_REPOSITORY_URL
cd lifelink
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start LifeLink

From the project root:

```bash
uvicorn backend.main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

> The SQLite database is automatically created during application startup if required.

---

# 🔌 API & Real-Time Communication

LifeLink uses both traditional REST APIs and WebSockets.

### REST APIs

Used for operations such as:

* Registration
* Login
* Profile management
* Emergency requests
* Donor responses
* Notifications
* Reports
* Administrative operations

### WebSockets

Used for real-time events such as:

* New emergency requests
* Donor responses
* Request status changes
* Notifications
* Live dashboard updates

Conceptually:

```text
Client ──────── HTTP Request ────────► FastAPI
Client ◄─────── HTTP Response ─────── FastAPI


Client ◄══════ WebSocket Event ══════ FastAPI
```

---

# 🔒 Privacy & Safety

LifeLink is designed with privacy in mind.

The MVP avoids publicly exposing:

* Exact donor GPS coordinates
* Donor phone numbers
* Donor personal contact details

Contact information is only revealed after the donor explicitly confirms the interaction.

The system is intended only as a **coordination layer**. It does not determine whether someone is medically eligible to donate.

---

# 🚧 Current Status

### Version 1.0 — MVP

The current version focuses on:

* Core donor matching
* Emergency requests
* Real-time communication
* Privacy
* Authentication
* Request tracking
* Demo functionality

---

# 🔮 LifeLink v2.0 — Planned

The next version will focus on connecting **blood inventory and donor coordination**.

Planned concepts include:

### 🏥 Hospital & Blood Bank Registration

Hospitals and blood banks will be able to register and maintain information about their available blood inventory.

### 🩸 Blood Bank + Donor Fallback

Instead of immediately notifying donors:

```text
Emergency Request
       ↓
Check nearby blood inventory
       ↓
Enough blood available?
   ↙              ↘
 YES              NO
  ↓                ↓
Blood Centre    Calculate shortage
                  ↓
              Find donors
```

### 🧠 Emergency Resolution Engine

For example:

```text
Required: 4 O+

Blood Bank:
3 units available

Remaining:
1 unit

→ Find donor for only 1 unit
```

Once the complete requirement is secured, unnecessary donor notifications can be stopped.

The long-term goal is to evolve LifeLink from a simple donor discovery application into a **real-time emergency blood-resource coordination system.**

---

# 📌 Project Philosophy

LifeLink was built primarily as a **learning project**.

The blood donation problem itself is not new, and existing platforms already address parts of it. The goal of this project was to take a real-world problem and use it to learn how a complete software system is designed, connected and operated.

> **Build something real. Break it. Understand why it broke. Fix it. Learn.**

---

## 👨‍💻 Author

**Aditya Pandey**

B.Tech CSE — Artificial Intelligence

Interested in:

* AI/ML
* Backend Development
* Full-Stack Development
* Building practical software projects

---

## ⭐ If you found the project interesting

Feel free to explore the code, suggest improvements, or use the project as a learning reference.

**LifeLink v1.0 — MVP**

🚀 **v2.0 in progress**
