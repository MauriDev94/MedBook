# MedBook API

> API REST para reservas médicas — Django 5.2 LTS + DRF 3.18  
> Proyecto de portafolio hecho con TDD: máquina de estados de citas, RBAC a nivel de objeto y reservas sin race conditions.

[![Tests](https://img.shields.io/badge/tests-335%20passing-brightgreen)](./tests)
[![Coverage](https://img.shields.io/badge/branch%20coverage-99.4%25-brightgreen)](./tests)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Django](https://img.shields.io/badge/django-5.2%20LTS-green)](https://djangoproject.com)

**[Read in English →](./README.md)**

---

## ¿Qué es MedBook?

MedBook es una API REST para gestionar reservas médicas. Cubre el ciclo completo: los médicos publican sus horarios semanales, el sistema genera slots concretos, los pacientes los reservan y las citas avanzan a través de una máquina de estados (pending → confirmed → completed / cancelled / no-show).

El objetivo es demostrar competencia real con Django: queries ORM complejas, permisos RBAC, transacciones atómicas, TDD, admin personalizado y arquitectura limpia — exactamente lo que aparece en entrevistas técnicas senior.

---

## Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Framework | Django | 5.2 LTS (5.2.18) |
| REST | Django REST Framework | 3.18.3 |
| Auth | djangorestframework-simplejwt | 5.5.1 |
| Filtros | django-filter | 26.x |
| Docs API | drf-spectacular (OpenAPI 3) | 0.30.0 |
| Email | django-anymail (Resend) | 15.x |
| CORS | django-cors-headers | 4.9.0 |
| Static files | whitenoise[brotli] | 6.8 |
| Base de datos | PostgreSQL 16 | — |
| Tests | pytest-django + factory-boy | — |
| Lint | ruff | — |

---

## Arquitectura

```
medbook/
├── apps/
│   ├── core/           # Compartido: permissions, exceptions, pagination, throttling
│   ├── users/          # User model (AbstractBaseUser) + auth JWT
│   ├── doctors/        # Doctor, Specialty, Schedule + signals
│   ├── patients/       # Patient model
│   ├── appointments/   # TimeSlot, Appointment, MedicalNote + máquina de estados
│   └── notifications/  # Servicios de email
├── config/
│   ├── settings/       # base.py / local.py / test.py / production.py
│   └── urls.py
└── tests/
    ├── unit/           # Lógica pura: modelos, services (sin HTTP)
    └── integration/    # Stack HTTP completo: URL → ViewSet → DB
```

### Responsabilidades por capa

| Capa | Responsabilidad | Lo que NO va aquí |
|---|---|---|
| `models.py` | Campos, relaciones, transiciones de estado | Lógica de negocio |
| `serializers.py` | Validación de input, formato de output | Queries ORM, reglas de negocio |
| `views.py` | HTTP: auth, permisos, serialización, status codes | ORM directo, reglas de negocio |
| `services.py` | Toda la lógica de negocio | Nada relacionado a HTTP |
| `permissions.py` | Un chequeo por clase | Lógica de negocio |

### La regla de las 15 líneas

Si un método `validate_*`, una acción de ViewSet o un método de modelo supera ~15 líneas → extraer a `services.py`. Sin excepciones.

---

## Modelo de dominio

```
User (AbstractBaseUser)
 ├── Doctor ──── Specialty (M2M)
 │        └──── Schedule (disponibilidad semanal)
 │                   └──── TimeSlot (slots concretos reservables)
 └── Patient
           └──── Appointment ──── TimeSlot (OneToOne)
                      └──── MedicalNote
```

### Máquina de estados — Appointment

```
pending ──────────► confirmed ──────────► completed
   │                    │
   │                    ▼
   └──────────────► cancelled              no_show (desde confirmed)
```

Transiciones válidas:
- `pending → confirmed` (el médico confirma)
- `pending → cancelled` (el paciente o médico cancela)
- `confirmed → completed` (el médico marca completada)
- `confirmed → cancelled` (el paciente o médico cancela)
- `confirmed → no_show` (el médico marca inasistencia)

Cualquier otra transición lanza `ValueError`.

---

## Endpoints de la API

Base URL: `/api/v1/`  
Auth: header `Bearer <access_token>`  
Docs: `GET /api/docs/` (Swagger UI)

### Auth
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/v1/token/` | Login → `{access, refresh}` |
| POST | `/api/v1/token/refresh/` | Refrescar access token |
| POST | `/api/v1/token/blacklist/` | Logout (invalida refresh token) |

### Usuarios
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/users/me/` | Perfil del usuario autenticado | Cualquiera |
| PATCH | `/api/v1/users/me/` | Actualizar first_name, last_name | Cualquiera |
| POST | `/api/v1/users/register/` | Registro de paciente → 201 con el perfil (sin tokens; el login va por `/api/v1/token/`). Límite de 10/hora por IP | Público |

### Doctores
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/doctors/` | Listar doctores (filtro: `?specialty=cardiology`) | Cualquiera |
| GET | `/api/v1/doctors/{id}/` | Detalle con specialties | Cualquiera |
| GET | `/api/v1/doctors/{id}/available-slots/` | Slots disponibles | Cualquiera |

### Schedules (Horarios)
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/schedules/` | Lista (doctor: propios; admin: todos) | Doctor/Admin |
| POST | `/api/v1/schedules/` | Crear horario | Doctor |
| GET | `/api/v1/schedules/{id}/` | Detalle | Doctor/Admin |
| PUT/PATCH | `/api/v1/schedules/{id}/` | Actualizar | Dueño/Admin |
| DELETE | `/api/v1/schedules/{id}/` | Soft-delete (is_active=False) | Dueño/Admin |

### Appointments (Citas)
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/appointments/` | Lista filtrada por rol automáticamente | Cualquiera |
| POST | `/api/v1/appointments/` | Reservar cita | Paciente |
| GET | `/api/v1/appointments/{id}/` | Detalle | Dueño/Admin |
| PATCH | `/api/v1/appointments/{id}/` | Actualizar motivo | Dueño/Admin |
| DELETE | `/api/v1/appointments/{id}/` | Eliminar | Solo Admin |
| POST | `/api/v1/appointments/{id}/confirm/` | Confirmar (pending → confirmed) | Médico (dueño) |
| POST | `/api/v1/appointments/{id}/cancel/` | Cancelar | Paciente o Médico (dueño) |
| POST | `/api/v1/appointments/{id}/complete/` | Completar (confirmed → completed) | Médico (dueño) |
| POST | `/api/v1/appointments/{id}/no_show/` | Marcar inasistencia | Médico (dueño) |

### Notas Médicas
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/appointments/{id}/notes/` | Listar notas | Médico (dueño)/Admin |
| POST | `/api/v1/appointments/{id}/notes/` | Crear nota | Médico (dueño) |
| GET | `/api/v1/appointments/{id}/notes/{nid}/` | Detalle de nota | Médico (dueño)/Admin |

### Filtros disponibles
```
GET /api/v1/doctors/?specialty=cardiology
GET /api/v1/appointments/?status=pending
GET /api/v1/appointments/?date_from=2025-01-01&date_to=2025-12-31
GET /api/v1/schedules/?day_of_week=0&is_active=true
```

---

## RBAC — Matriz de permisos

| Clase de permiso | Regla |
|---|---|
**Cableadas a endpoints:**

| Clase de permiso | Regla | Usada por |
|---|---|---|
| `IsDoctor` | `user.role == 'doctor'` | Crear schedule |
| `IsPatient` | `user.role == 'patient'` | Crear cita |
| `IsAdminRole` | `user.role == 'admin'` | Eliminar cita |
| `IsDoctorOfAppointment` | `appointment.doctor == user.doctor_profile` | confirm / complete / no_show / cancel |
| `IsPatientOfAppointment` | `appointment.patient == user.patient_profile` | cancel |

---

## Setup local

### Prerequisitos
- Python 3.12
- PostgreSQL 16 (vía Docker o instalación local)
- Git

### 1. Clonar y crear virtualenv
```bash
git clone https://github.com/MauriDev94/MedBook.git
cd MedBook
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows PowerShell
```

### 2. Instalar dependencias
```bash
pip install -r requirements/local.txt
pre-commit install
```

### 3. Variables de entorno
```bash
cp .env.example .env
# Editar .env — mínimo: DATABASE_URL y SECRET_KEY
```

Ejemplo de `.env`:
```env
SECRET_KEY=dev-local-secret-key-cualquier-valor
DEBUG=True
DATABASE_URL=postgres://postgres:postgres@localhost:5432/medbook
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### 4. Levantar PostgreSQL y migrar
```bash
# Con Docker
docker run -d --name medbook-db -p 5432:5432 \
  -e POSTGRES_DB=medbook \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  postgres:16-alpine

# Aplicar migraciones
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py migrate

# Crear usuario admin
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py createsuperuser
```

### 5. Levantar el servidor
```bash
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver
```

Abrir **http://localhost:8000/api/docs/** para el Swagger interactivo.

---

## Deploy

El deploy de producción es **nativo de Render**: ver [`render.yaml`](./render.yaml) para los comandos de build y arranque (gunicorn, archivos estáticos con WhiteNoise, Postgres administrado).

### Generación de slots en producción

El plan free de Render no tiene cron jobs, así que el `startCommand` corre `python manage.py generate_slots --days=14` en cada arranque. La instancia free duerme tras 15 minutos sin tráfico y vuelve a arrancar con el siguiente request y en cada deploy, así que los slots se completan mientras la API se esté usando.

- El comando es idempotente: solo inserta los slots que faltan y en una segunda corrida reporta `0 new slots`.
- Corre en un subshell. Si falla, deja una línea `WARNING` en el log y gunicorn arranca igual; en cambio, si falla `migrate` o `ensure_superuser`, el arranque se detiene.
- En un plan pago, reemplazarlo por un cron job de Render (`type: cron`, diario, `python manage.py generate_slots --days=14`; mínimo USD 1/mes) y sacarlo del `startCommand`.

---

## Correr los tests

Los tests corren contra PostgreSQL real (igual que producción) usando **branch coverage** como estándar — no solo cobertura de líneas. Branch coverage detecta caminos `if/else` sin testear que el coverage de líneas oculta.

```bash
# Suite completa con cobertura
pytest

# Solo tests unitarios (rápido)
pytest tests/unit/

# Solo tests de integración
pytest tests/integration/

# Con output verbose
pytest -v

# Detener al primer fallo
pytest -x
```

Estado actual: **335 tests · 99.4% branch coverage · 0 fallos**

---

## Decisiones de arquitectura

Ver [`docs/architecture.md`](./docs/architecture.md) para el log completo de decisiones con tradeoffs.

Resumen rápido:

- **`AbstractBaseUser` custom** — email como username, campo `role` explícito, sin campos innecesarios
- **Capa de services** para toda la lógica de negocio — ViewSets son handlers HTTP delgados
- **`@transaction.atomic` + UPDATE atómico** para prevenir race conditions en reserva de slots
- **Máquina de estados en el modelo** — métodos de transición con guardas `ValueError` explícitos
- **`select_related` en todos lados** — cero queries N+1 por convención
- **factory_boy** para todos los datos de test — cero fixtures JSON/YAML
- **Backend locmem de email** en tests — assertions con `mail.outbox`, sin SMTP real
- **`AnonRateThrottle`** en login — protección brute-force sin throttlear toda la API
- **WhiteNoise** para static files en producción — sirve CSS/JS desde Gunicorn sin Nginx, con compresión Brotli y cache-busting automático

---

## Convenciones del proyecto

```bash
# Lint (corre automático en cada commit vía pre-commit)
ruff check . && ruff format --check .

# Generar slots para los próximos 30 días
python manage.py generate_slots --days=30

# Validar schema OpenAPI
PYTHONIOENCODING=utf-8 python manage.py spectacular --validate --fail-on-warn
```

Formato de commits: `feat|fix|refactor|docs|test(scope): descripción`

---

## Licencia

MIT
