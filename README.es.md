# MedBook API

> API REST para reservas médicas — Django 5.2 LTS + DRF 3.18  
> Proyecto de portafolio hecho con TDD: máquina de estados de citas, RBAC a nivel de objeto y reservas sin race conditions.

[![Tests](https://img.shields.io/badge/tests-668%20passing-brightgreen)](./tests)
[![Coverage](https://img.shields.io/badge/branch%20coverage-99.6%25-brightgreen)](./tests)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Django](https://img.shields.io/badge/django-5.2%20LTS-green)](https://djangoproject.com)

**[Read in English →](./README.md)**

---

## ¿Qué es MedBook?

MedBook es una API REST para gestionar reservas médicas. Cubre el ciclo completo: los médicos publican sus horarios semanales, el sistema genera slots concretos, los pacientes los reservan y las citas avanzan a través de una máquina de estados (pending → confirmed → completed / cancelled / no-show).

El objetivo es demostrar competencia real con Django: queries ORM complejas, permisos RBAC, transacciones atómicas, TDD, admin personalizado y arquitectura limpia — exactamente lo que aparece en entrevistas técnicas senior.

Los pacientes también tienen una web server-rendered (templates de Django + HTMX, en español e inglés) sobre la misma capa de servicios, según el [ADR 0002](./docs/adr/0002-server-rendered-web-frontend.md). Pueden registrarse, buscar un médico por especialidad, reservar una hora y administrar sus citas. La demo, con seis doctores ficticios, está en **https://medbook-oiio.onrender.com**. Corre en el plan gratuito de Render, así que la primera visita después de un rato sin uso puede tardar cerca de un minuto.

### Capturas

La web está en español, su idioma por defecto; el inglés está a un clic en el menú.

| Catálogo de médicos | Reservar una hora |
|---|---|
| ![Catálogo con seis médicos y el filtro por especialidad](./docs/screenshots/doctors.jpg) | ![Modal de reserva sobre la semana de horas de un médico](./docs/screenshots/booking.jpg) |
| **Mis citas** | **Cancelar una cita** |
| ![Mis citas con tres citas próximas](./docs/screenshots/appointments.jpg) | ![Modal que confirma la cancelación de una cita](./docs/screenshots/cancel.jpg) |

<img src="./docs/screenshots/mobile.jpg" alt="La semana de horas de un médico en una pantalla de teléfono de 375 px" width="250">

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
| Web | Templates de Django + HTMX (vendorizado) + django-htmx | 2.0.11 / 1.29 |
| CSS | Tailwind CSS vía django-tailwind-cli (CLI standalone, sin Node) | 4.3.3 / 4.8 |
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
│   ├── notifications/  # Servicios de email
│   └── web/            # Web server-rendered: templates, views, fuente de Tailwind (sin modelos)
├── config/
│   ├── settings/       # base.py / local.py / test.py / production.py
│   └── urls.py
├── locale/es/          # Catálogo en español de la web (.po + .mo compilado)
├── static/             # JS vendorizado (HTMX) + CSS de Tailwind compilado (generado)
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
           └──── Appointment ──── TimeSlot (FK: historial, una cita activa)
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
Fechas: ISO 8601 en hora de Chile con su desfase, por ejemplo `2026-01-14T09:00:00-03:00` (se guardan en UTC). Los horarios de los doctores se interpretan en `America/Santiago` (ver [ADR 0003](./docs/adr/0003-clinic-time-zone.md)).

### Auth
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/v1/token/` | Login → `{access, refresh}`. El email no distingue mayúsculas: `Ana@example.com` y `ana@example.com` son la misma cuenta |
| POST | `/api/v1/token/refresh/` | Refrescar access token |
| POST | `/api/v1/token/blacklist/` | Logout (invalida refresh token) |

### Usuarios
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/users/me/` | Perfil del usuario autenticado | Cualquiera |
| PATCH | `/api/v1/users/me/` | Actualizar first_name, last_name | Cualquiera |
| POST | `/api/v1/users/register/` | Registro de paciente → 201 con el perfil (sin tokens; el login va por `/api/v1/token/`). Un email ya usado, con cualquier combinación de mayúsculas → 400. Límite de 10/hora por IP | Público |

### Doctores
| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/v1/doctors/` | Listar doctores (filtro: `?specialty=cardiology`) | Cualquiera |
| GET | `/api/v1/doctors/{id}/` | Detalle con specialties | Cualquiera |
| GET | `/api/v1/doctors/{id}/available-slots/` | Slots disponibles que no han empezado | Cualquiera |

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

### Páginas web
Server-rendered con sesión de Django (la API sigue con JWT). En español por defecto e inglés con el selector.

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| GET | `/` | Home | Público |
| GET, POST | `/signup/` | Registro de pacientes; deja la sesión iniciada. Comparte el límite `register` de la API (10/hora por IP) | Anónimo |
| GET, POST | `/login/` | Correo (con cualquier combinación de mayúsculas) + contraseña. Comparte el límite `login` de la API (5/minuto por IP) | Anónimo |
| POST | `/logout/` | Cerrar sesión | Con sesión |
| GET | `/panel/` | Aviso para doctores y admins hasta que llegue su panel | Doctor, admin |
| GET | `/doctors/` | Catálogo de doctores, filtro `?specialty=<slug>` (HTMX cambia solo la lista), 10 por página | Paciente |
| GET | `/doctors/<id>/` | Perfil del doctor y una semana de slots disponibles y futuros en hora de Chile; `?week=0–3` (HTMX cambia solo la semana) | Paciente |
| GET, POST | `/slots/<id>/book/` | Confirmar y reservar un slot con un motivo opcional. HTMX lo carga en un modal; sin JS es una página completa. Al reservar lleva a Mis citas; si el slot ya no se puede reservar, vuelve al perfil del doctor, en la semana del slot | Paciente |
| GET | `/appointments/` | Mis citas: `?tab=upcoming` (por defecto: las que no han empezado, en cualquier estado) o `?tab=past`, 10 por página, badge de estado traducido (HTMX cambia solo la lista) | Paciente |
| GET | `/appointments/<id>/` | Una cita del paciente: doctor, fecha, hora, estado y motivo. La de otro paciente da 404 | Paciente |
| GET, POST | `/appointments/<id>/cancel/` | Confirmar y cancelar: libera el slot y avisa por correo. Con HTMX es un modal y el estado se actualiza en su lugar; sin JS, una página completa que después lleva a la cita | Paciente |
| POST | `/i18n/setlang/` | Selector de idioma (guarda una cookie) | Público |

**Páginas de error.** Las páginas 403, 404 y 500 usan el layout del sitio y el idioma del visitante. La 500 se arma sin el request ni la base de datos, porque cualquiera de los dos puede ser lo que falló, así que su menú no tiene links de cuenta. Si la sesión expira mientras el visitante está en un modal, la página completa va al login, que después lo devuelve a la misma página (`HX-Redirect`).

**Accesibilidad.**
- Un skip link salta el menú y lleva al `<main>` de la página.
- Todo funciona con teclado. Los modales son `<dialog>` nativos: Esc los cierra y el foco vuelve al link que los abrió. Después de cancelar, el foco pasa al nuevo estado de la cita. Los links de semana, pestaña y página mantienen el foco cuando HTMX reemplaza el contenido que los rodea.
- Cada actualización con HTMX anuncia un resumen corto a los lectores de pantalla en una región viva "polite", por ejemplo "Se encontraron 6 médicos." o "2 de noviembre – 8 de noviembre: 16 horas disponibles.". Los mensajes van en una región `role="status"`.
- Los links que se repiten llevan contexto oculto, como "Ver horas disponibles: Dr. Carla Soto" o "lunes 26 de octubre, 10:00".
- Los botones principales usan texto blanco sobre teal-700 (contraste 5,4:1, WCAG AA). El diseño funciona desde 375 px de ancho.

---

## RBAC — Matriz de permisos

Los chequeos de rol viven en `apps/core/roles.py` (`is_patient`, `is_doctor`, `is_admin`) y los comparten estas clases de DRF y los mixins de la web (`PatientRequiredMixin` / `StaffRequiredMixin`), así los dos caminos de RBAC no pueden divergir. Qué citas ve cada usuario también es una sola regla: `appointments_visible_to(user)` en `apps/appointments/services.py` (el paciente las suyas, el doctor las suyas, el admin todas, nadie más ninguna), que usan el `AppointmentViewSet` de la API y Mis citas en la web.

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
```

Completar los valores vacíos de `.env` (nunca se versiona): `SECRET_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_TEST_PASSWORD` y `DATABASE_URL` (formato en `.env.example`, con el mismo password que `POSTGRES_PASSWORD`). Ningún password ni clave queda escrito en el repo, ni siquiera para desarrollo local; se generan:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"   # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(16))"   # passwords de la DB (seguros para URL)
```

Si falta alguno, Django y `docker compose` se detienen con un error que nombra la variable.

### 4. Levantar PostgreSQL y migrar
```bash
# Postgres en el puerto 5435 con las credenciales de tu .env
docker compose up -d db

# Aplicar migraciones
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py migrate

# Crear usuario admin
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py createsuperuser
```

### 5. Levantar el servidor
```bash
# Compilar el CSS una vez (la primera corrida descarga el CLI de Tailwind fijado)
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py tailwind build
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver
```

Abrir **http://localhost:8000/** para la web y **http://localhost:8000/api/docs/** para el Swagger interactivo.

### Web: CSS y traducciones

- **Tailwind**: mientras se editan templates, correr `python manage.py tailwind watch` en otra terminal, o `python manage.py tailwind runserver` para tener el watcher y el servidor en una sola. La fuente es `apps/web/styles/tailwind.css` y solo escanea `apps/web`, así que las clases tienen que aparecer ahí de forma literal (nunca armadas con strings). La salida `static/css/tailwind.css` se genera y no se versiona. Render, CI y el Dockerfile la compilan en el build.
- **Idioma**: el español es el idioma por defecto. El selector del menú hace POST a `/i18n/setlang/`, que guarda la elección en una cookie; sin cookie decide el `Accept-Language` del navegador. Las fechas usan el formato del idioma activo y la hora de Chile. Toda ruta `/api/` vuelve al inglés, así que la API JSON no cambia con el idioma del visitante.
- **Traducciones**: los textos de la web se escriben en inglés y se traducen al español (idioma por defecto) en `locale/es/LC_MESSAGES/django.po`. Se versionan el `.po` y el `.mo` compilado, porque producción no tiene gettext; CI falla si quedan desactualizados. La API JSON responde siempre en inglés. Para actualizarlos hace falta GNU gettext:
  - Windows: `winget install mlocati.GetText` (y abrir una terminal nueva)
  - macOS: `brew install gettext` · Debian/Ubuntu: `sudo apt install gettext`

  ```bash
  python manage.py makemessages -l es --no-location --no-obsolete
  # traducir los msgstr nuevos y luego:
  python manage.py compilemessages -l es --ignore=.venv
  ```

### Datos demo

`python manage.py seed_demo` crea seis doctores ficticios que cubren las cinco especialidades, con horario de lunes a viernes en hora de Chile. Solo actúa con `MEDBOOK_DEMO_DATA=true`; si no, avisa y no hace nada. Para llenar una base local:

```bash
MEDBOOK_DEMO_DATA=true python manage.py seed_demo   # o definirla en .env
python manage.py generate_slots --days=28           # las cuatro semanas que muestra la web
```

- Los datos están en [`apps/doctors/demo.py`](./apps/doctors/demo.py): emails en el dominio reservado `medbook.example` y licencias `DEMO-`.
- Los doctores demo no tienen contraseña utilizable, así que no pueden iniciar sesión (el panel del doctor llega en un sprint posterior). No se crea ni se versiona ninguna credencial.
- No crea pacientes: quien prueba la demo se registra en la web, que es justo el flujo a mostrar.
- Es idempotente. Un doctor demo ya existe si su email (sin importar mayúsculas) o su licencia están usados, y las filas que ya existen nunca se modifican, así que lo editado en el admin se mantiene.

---

## Deploy

Producción corre en **Render** y se gestiona como infraestructura como código: [`render.yaml`](./render.yaml) es un **Blueprint** de Render con auto-sync, así que cualquier cambio que llegue a `master` se aplica solo al servicio (comandos de build y arranque, health check en `/health/`, variables no secretas). Los secretos (`SECRET_KEY`, `DATABASE_URL`, credenciales del superusuario) quedan fuera del archivo y viven solo en el dashboard de Render. La versión de Python sale de [`.python-version`](./.python-version).

El build corre `tailwind build` antes de `collectstatic`, porque el storage con manifest necesita el CSS compilado. Las traducciones no se compilan ahí: los `.mo` están versionados.

El [`Dockerfile`](./Dockerfile) multi-stage sobre **Alpine** es una alternativa portable al deploy nativo de Render (producción pasa a esa imagen en el Paso 32, [#145](https://github.com/MauriDev94/MedBook/issues/145)). El builder instala las dependencias (todas tienen wheels musllinux), baja la build musl del CLI de Tailwind (verificada con el sha256 del release, porque django-tailwind-cli no detecta musl), compila el CSS y corre `collectstatic`. La etapa final no lleva herramientas de build y corre con un usuario sin privilegios.

### Generación de slots en producción

El plan free de Render no tiene cron jobs, así que el `startCommand` corre `python manage.py generate_slots --days=28` en cada arranque. La instancia free duerme tras 15 minutos sin tráfico y vuelve a arrancar con el siguiente request y en cada deploy, así que los slots se completan mientras la API se esté usando.

- El comando es idempotente: solo inserta los slots que faltan y en una segunda corrida reporta `0 new slots`.
- Corre en un subshell. Si falla, deja una línea `WARNING` en el log y gunicorn arranca igual; en cambio, si falla `migrate` o `ensure_superuser`, el arranque se detiene.
- En un plan pago, reemplazarlo por un cron job de Render (`type: cron`, diario, `python manage.py generate_slots --days=28`; mínimo USD 1/mes) y sacarlo del `startCommand`.

Producción es también la demo del portfolio: `render.yaml` define `MEDBOOK_DEMO_DATA=true`, así que el `startCommand` corre `seed_demo` justo antes de `generate_slots`, en su propio subshell. El primer arranque crea los [doctores demo](#datos-demo) y los siguientes reportan `Done. 0 demo doctor(s) created.`

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
- **Índice único parcial** (`one_active_appointment_per_slot`): un slot guarda sus citas canceladas y se puede volver a reservar, pero nunca tiene dos activas ([ADR 0004](./docs/adr/0004-slot-appointment-history.md))
- **Máquina de estados en el modelo** — métodos de transición con guardas `ValueError` explícitos
- **`select_related` en todos lados** — cero queries N+1 por convención
- **factory_boy** para todos los datos de test — cero fixtures JSON/YAML
- **Backend locmem de email** en tests — assertions con `mail.outbox`, sin SMTP real
- **`AnonRateThrottle`** en login — protección brute-force sin throttlear toda la API
- **WhiteNoise** para static files en producción — sirve CSS/JS desde Gunicorn sin Nginx, con compresión Brotli y cache-busting automático
- **Web server-rendered** — templates de Django + HTMX y Tailwind sin Node, que llaman a los mismos servicios que la API; un único script pequeño para los modales ([ADR 0002](./docs/adr/0002-server-rendered-web-frontend.md))

---

## Convenciones del proyecto

```bash
# Lint (corre automático en cada commit vía pre-commit)
ruff check . && ruff format --check .

# Generar slots para los próximos 30 días
python manage.py generate_slots --days=30

# Crear los doctores demo (requiere MEDBOOK_DEMO_DATA=true)
python manage.py seed_demo

# Validar schema OpenAPI
PYTHONIOENCODING=utf-8 python manage.py spectacular --validate --fail-on-warn
```

Formato de commits: `feat|fix|refactor|docs|test(scope): descripción`

---

## Licencia

MIT
