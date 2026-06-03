# MedBook API

> REST API for medical appointment booking — Django 5.1 + DRF 3.15  
> Portfolio project demonstrating production-grade Django patterns.

[![Tests](https://img.shields.io/badge/tests-270%20passing-brightgreen)](./tests)
[![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)](./tests)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Django](https://img.shields.io/badge/django-5.1-green)](https://djangoproject.com)

**[Leer en Español →](./README.es.md)**

---

## What is MedBook?

MedBook is a REST API for managing medical appointments. It covers the full booking lifecycle: doctors publish their weekly schedules, the system generates concrete time slots, patients book them, and appointments move through a state machine (pending → confirmed → completed / cancelled / no-show).

The goal is to demonstrate real-world Django competency: complex ORM queries, RBAC permissions, atomic transactions, TDD, custom admin, and clean architecture — the kind of things that come up in senior backend interviews.

---

## Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Framework | Django | 5.1.15 |
| REST | Django REST Framework | 3.15.2 |
| Auth | djangorestframework-simplejwt | 5.3.1 |
| Filtering | django-filter | 24.x |
| API docs | drf-spectacular (OpenAPI 3) | 0.27.2 |
| Email | django-anymail (Resend) | 10.3 |
| CORS | django-cors-headers | 4.9.0 |
| Database | PostgreSQL 16 | — |
| Tests | pytest-django + factory-boy | — |
| Lint | ruff | — |

---

## Architecture

```
medbook/
├── apps/
│   ├── core/           # Shared: permissions, exceptions, pagination, throttling
│   ├── users/          # Custom User model (AbstractBaseUser) + JWT auth
│   ├── doctors/        # Doctor, Specialty, Schedule models + signals
│   ├── patients/       # Patient model
│   ├── appointments/   # TimeSlot, Appointment, MedicalNote + state machine
│   └── notifications/  # Email notification services
├── config/
│   ├── settings/       # base.py / local.py / test.py / production.py
│   └── urls.py
└── tests/
    ├── unit/           # Pure logic: models, services (no HTTP)
    └── integration/    # Full HTTP stack: URL → ViewSet → DB
```

### Layer responsibilities

| Layer | Responsibility | What does NOT go here |
|---|---|---|
| `models.py` | Fields, relationships, state transitions | Business logic |
| `serializers.py` | Input validation, output formatting | ORM queries, business rules |
| `views.py` | HTTP: auth, permissions, serialization, status codes | ORM direct, business rules |
| `services.py` | All business logic | Anything HTTP-related |
| `permissions.py` | One check per class | Business logic |

### The 15-line rule

If a `validate_*` method, a ViewSet action, or a model method exceeds ~15 lines → extract to `services.py`. No exceptions.

---

## Domain model

```
User (AbstractBaseUser)
 ├── Doctor ──── Specialty (M2M)
 │        └──── Schedule (weekly availability)
 │                   └──── TimeSlot (concrete bookable slots)
 └── Patient
           └──── Appointment ──── TimeSlot (OneToOne)
                      └──── MedicalNote
```

### Appointment state machine

```
pending ──────────► confirmed ──────────► completed
   │                    │
   │                    ▼
   └──────────────► cancelled              no_show (from confirmed)
```

Valid transitions:
- `pending → confirmed` (doctor confirms)
- `pending → cancelled` (patient or doctor cancels)
- `confirmed → completed` (doctor marks complete)
- `confirmed → cancelled` (patient or doctor cancels)
- `confirmed → no_show` (doctor marks no-show)

Any other transition raises `ValueError`.

---

## API Endpoints

Base URL: `/api/`  
Auth: `Bearer <access_token>` header  
Docs: `GET /api/docs/` (Swagger UI)

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/token/` | Login → `{access, refresh}` |
| POST | `/api/token/refresh/` | Refresh access token |
| POST | `/api/token/blacklist/` | Logout (invalidate refresh token) |

### Users
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/users/me/` | Authenticated user profile | Any |
| PATCH | `/api/users/me/` | Update first_name, last_name | Any |

### Doctors
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/doctors/` | List doctors (filter: `?specialty=cardiology`) | Any |
| GET | `/api/doctors/{id}/` | Doctor detail with specialties | Any |
| GET | `/api/doctors/{id}/available-slots/` | Available time slots | Any |

### Schedules
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/schedules/` | List schedules (doctor: own; admin: all) | Doctor/Admin |
| POST | `/api/schedules/` | Create schedule | Doctor |
| GET | `/api/schedules/{id}/` | Schedule detail | Doctor/Admin |
| PUT/PATCH | `/api/schedules/{id}/` | Update schedule | Owner/Admin |
| DELETE | `/api/schedules/{id}/` | Soft-delete (is_active=False) | Owner/Admin |

### Appointments
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/appointments/` | List (patient: own; doctor: own; admin: all) | Any |
| POST | `/api/appointments/` | Book appointment | Patient |
| GET | `/api/appointments/{id}/` | Detail | Owner/Admin |
| PATCH | `/api/appointments/{id}/` | Update reason | Owner/Admin |
| DELETE | `/api/appointments/{id}/` | Hard delete | Admin |
| POST | `/api/appointments/{id}/confirm/` | Confirm (pending → confirmed) | Doctor (owner) |
| POST | `/api/appointments/{id}/cancel/` | Cancel | Patient or Doctor (owner) |
| POST | `/api/appointments/{id}/complete/` | Complete (confirmed → completed) | Doctor (owner) |
| POST | `/api/appointments/{id}/no_show/` | Mark no-show (confirmed → no_show) | Doctor (owner) |

### Medical Notes
| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/appointments/{id}/notes/` | List notes | Doctor (owner)/Admin |
| POST | `/api/appointments/{id}/notes/` | Create note | Doctor (owner) |
| GET | `/api/appointments/{id}/notes/{nid}/` | Note detail | Doctor (owner)/Admin |

### Filters available
```
GET /api/doctors/?specialty=cardiology
GET /api/appointments/?status=pending
GET /api/appointments/?date_from=2025-01-01&date_to=2025-12-31
GET /api/schedules/?day_of_week=0&is_active=true
```

---

## RBAC — Permission matrix

| Permission class | Rule |
|---|---|
| `IsDoctor` | `user.role == 'doctor'` |
| `IsPatient` | `user.role == 'patient'` |
| `IsAdminRole` | `user.role == 'admin'` |
| `IsOwnerOrAdmin` | `obj.user == request.user` or admin |
| `IsDoctorOfAppointment` | `appointment.doctor == user.doctor_profile` |
| `IsPatientOfAppointment` | `appointment.patient == user.patient_profile` |
| `IsPatientOrDoctor` | role in ('patient', 'doctor') |
| `ReadOnly` | `request.method in SAFE_METHODS` |

---

## Local setup

### Prerequisites
- Python 3.12
- PostgreSQL 16 (via Docker or local install)
- Git

### 1. Clone and create virtualenv
```bash
git clone https://github.com/MauriDev94/MedBook.git
cd MedBook
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows PowerShell
```

### 2. Install dependencies
```bash
pip install -r requirements/local.txt
pre-commit install
```

### 3. Environment variables
```bash
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL and SECRET_KEY
```

`.env` example:
```env
SECRET_KEY=dev-local-secret-key-any-value-works
DEBUG=True
DATABASE_URL=postgres://postgres:postgres@localhost:5432/medbook
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### 4. Start PostgreSQL and run migrations
```bash
# With Docker
docker run -d --name medbook-db -p 5432:5432 \
  -e POSTGRES_DB=medbook \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  postgres:16-alpine

# Apply migrations
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py migrate

# Create admin user
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py createsuperuser
```

### 5. Start the server
```bash
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver
```

Open **http://localhost:8000/api/docs/** for the interactive Swagger UI.

---

## Running tests

Tests run against a real PostgreSQL database (same as production).

```bash
# Full suite with coverage
pytest

# Only unit tests (fast)
pytest tests/unit/

# Only integration tests
pytest tests/integration/

# With verbose output
pytest -v

# Stop on first failure
pytest -x

# Specific test file
pytest tests/integration/test_appointments_api.py
```

### Test database setup
```bash
# Create test PostgreSQL database (first time only)
createdb medbook_test          # or via Docker on port 5436
# See .env.test.example for configuration
```

Current stats: **270 tests · 99% coverage · 0 failures**

---

## Key architectural decisions

See [`docs/architecture.md`](./docs/architecture.md) for full decision log with tradeoffs.

Quick summary:

- **Custom `AbstractBaseUser`** instead of Django's default — email as username, explicit `role` field, no unused fields
- **Services layer** for all business logic — ViewSets are thin HTTP handlers, services own the rules
- **`@transaction.atomic` + atomic UPDATE** to prevent race conditions on slot booking
- **State machine on the model** — transition methods (`confirm()`, `cancel()`) with explicit `ValueError` guards
- **`select_related` everywhere** — zero N+1 queries by convention
- **factory_boy** for all test data — zero JSON/YAML fixtures
- **locmem email backend** in tests — `mail.outbox` assertions, no real SMTP needed
- **`AnonRateThrottle`** on login endpoint — brute-force protection without throttling the entire API

---

## Project conventions

```bash
# Lint (auto-runs on commit via pre-commit)
ruff check . && ruff format --check .

# Generate slots for next 30 days
python manage.py generate_slots --days=30

# Validate OpenAPI schema
PYTHONIOENCODING=utf-8 python manage.py spectacular --validate --fail-on-warn
```

Commit format: `feat|fix|refactor|docs|test(scope): description`

---

## License

MIT
