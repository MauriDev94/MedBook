# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

MedBook is a medical appointment booking REST API (portfolio project) built with Django + DRF (versions pinned in `requirements/base.txt`), PostgreSQL 16, Python 3.12. Default branch: `master`.

The JSON API is complete. Sprint "Semana 5" in `SPRINT.md` (Pasos 23–29, issues #133–#139) builds the patient-facing web UI. Done so far: the base (Paso 24: layout, Tailwind, HTMX, es/en i18n), session auth (Paso 25: login, logout, patient sign-up), the doctor catalog (Paso 26) and the fix that makes cancelled slots bookable again (Paso 30, `docs/adr/0004-slot-appointment-history.md`). Booking flows come next. The sprint's web decisions are recorded in two ADRs:
- `docs/adr/0002-server-rendered-web-frontend.md`: Django templates + HTMX in a new `apps/web` app, session auth reusing the service layer, Tailwind 4 via `django-tailwind-cli` (no Node), Spanish/English i18n with the JSON API kept in English, no Alpine.js.
- `docs/adr/0003-clinic-time-zone.md`: schedules are interpreted in `America/Santiago` (`TIME_ZONE`), and slots are built with `make_aware` instead of hard-coded UTC. Implemented in Paso 23. The API serialises datetimes with the Chilean offset and `__date` filters use Chilean dates. Never hard-code UTC when combining dates with schedule times.

Sources of truth: `README.md` (endpoints, RBAC matrix, setup), `docs/architecture.md` (decision log with trade-offs), `docs/adr/`, `SPRINT.md` (historical sprint plan), `docs/REMEDIATION-PLAN.md` (post-audit work). There is no `PRD.md` or `AGENT.md` in the repo.

## Environment

This project uses **pip + venv and `requirements/*.txt`**, not uv (unlike the workspace default).

```powershell
& "$env:APPDATA\uv\python\cpython-3.12-windows-x86_64-none\python.exe" -m venv .venv   # once per clone
.venv\Scripts\activate
$env:DJANGO_SETTINGS_MODULE='config.settings.local'
pip install -r requirements/local.txt   # once per clone
pre-commit install                      # ruff --fix + ruff-format on commit
```

Make the venv with the standard library's `venv` and Python 3.12, never `uv venv`: on this machine Windows Smart App Control blocks the unsigned `python.exe` launcher that uv writes into a venv (os error 4551, "Una directiva de Control de aplicaciones bloqueó este archivo"). The `python` on the PATH is 3.13, so the block above calls uv's 3.12 interpreter by its path; Smart App Control allows that one.

Never use `Start-Process` to launch Django on Windows — run `python manage.py runserver` in a dedicated terminal with env vars already set.

GNU gettext (needed only for `makemessages`/`compilemessages`) is installed on this machine with `winget install mlocati.GetText`, in `%LOCALAPPDATA%\Programs\gettext-iconv\bin` (on the user PATH; a shell opened before the install needs it prepended).

Settings modules: `config.settings.local` (dev), `config.settings.test` (pytest, set in `pytest.ini`), `config.settings.production` (Render). Config is read with `python-decouple` from `.env`; `.env.example` lists the keys.

Databases (Docker):
- Both compose files need `SECRET_KEY` / `POSTGRES_PASSWORD` / `POSTGRES_TEST_PASSWORD` in `.env` (no defaults; compose stops naming the missing one). Existing volumes keep the password they were created with.
- Dev: `docker compose up` starts Postgres on host port **5435** plus the app on 8000 (runs `migrate` then gunicorn with local settings). `docker compose up db` for just the DB.
- Tests: `docker compose -f docker-compose.test.yml up -d` starts Postgres on host port **5436**, which is the default `DATABASE_URL` in `config/settings/test.py`. An optional `.env.test` overrides it (loaded in `test.py`, not `conftest.py`, because pytest-django imports settings first).

## Commands

```bash
# Lint (CI runs both)
ruff check . && ruff format --check .

# Tests — always against PostgreSQL, never SQLite
pytest                                   # full suite, --reuse-db, branch coverage, fails under 95%
pytest tests/unit/ --no-cov
pytest tests/integration/test_appointments_api.py::TestClass::test_name --no-cov -x
pytest --create-db                       # after changing migrations (because of --reuse-db)

# Migrations (CI fails if any are missing)
python manage.py makemigrations --check --dry-run
python manage.py makemigrations && python manage.py migrate

# OpenAPI schema validation (PYTHONIOENCODING needed on Windows)
PYTHONIOENCODING=utf-8 python manage.py spectacular --validate --fail-on-warn

# Project management commands
python manage.py generate_slots [--days=30] [--doctor-id=<uuid>]
python manage.py ensure_superuser        # idempotent, used by the Render start command

# Web UI assets
python manage.py tailwind build          # → static/css/tailwind.css (generated, gitignored)
python manage.py tailwind watch          # rebuild on template changes, next to runserver

# Translations (needs gettext). Commit both .po and .mo; CI fails if stale
python manage.py makemessages -l es --no-location --no-obsolete
python manage.py compilemessages -l es --ignore=.venv
```

Translations: source strings are English (`{% translate %}` / `gettext_lazy`) and only `locale/es` has a catalog; English needs none because it falls back to the msgid. `--no-location` keeps Windows paths out of the `.po`, so CI's Linux run produces the same file. `--ignore=.venv` stops `compilemessages` from walking the virtualenv.

`pytest.ini` addopts include `--cov-fail-under=95`, so any partial run without `--no-cov` will "fail" on coverage even when every test passes. The `fail_under = 85` in `pyproject.toml` is overridden by that flag.

CI (`.github/workflows/ci.yml`): ruff lint + format, then two jobs. "Assets" runs `tailwind build` + `collectstatic` with production settings and checks that `makemessages`/`compilemessages` leave no diff. "Tests" runs the missing-migrations check, pytest on Postgres 16 and Codecov.

Deploy: the production Render service (`MedBook`, https://medbook-oiio.onrender.com, free plan, auto-deploy from `master`) is managed by a Render **Blueprint**: `render.yaml` is the source of truth and auto-syncs on every merge to `master` (Paso 31, #144). Change build or start commands, health check or non-secret env vars there, never in the dashboard. Secrets (`SECRET_KEY`, `DATABASE_URL`, `DJANGO_SUPERUSER_*`) are deliberately absent from the file and live only in the dashboard. The Python version comes from `.python-version`; do not add `PYTHON_VERSION`. A Blueprint never deletes resources. Confirm a deploy from the log line `==> Running '…'`. The free plan has no pre-deploy command and no cron jobs. The `buildCommand` runs `tailwind build` before `collectstatic`, because the manifest storage fails without the CSS. The `Dockerfile` is already `python:3.12-alpine`: django-tailwind-cli does not detect musl, so the builder fetches the musl Tailwind CLI (pinned sha256) and sets `TAILWIND_CLI_PATH`. Keep its `TAILWIND_VERSION` in sync with `TAILWIND_CLI_VERSION` in `base.py`. Moving production to that image is Paso 32 (#145) and needs a new service.

## Architecture

Apps under `apps/`: `core` (shared base model, permissions, exception handler, pagination, throttling, health check), `users` (custom `AbstractBaseUser` with email login and a `role` field: admin/doctor/patient; JWT views), `doctors` (Doctor, Specialty M2M, weekly Schedule), `patients`, `appointments` (TimeSlot, Appointment, MedicalNote), `notifications` (email senders). All models use UUID primary keys.

Key flows that span multiple apps:

- **Slot generation**: creating a `Schedule` fires a `post_save` signal (`apps/doctors/signals.py`) that calls `appointments.services.generate_slots_for_schedule` (7 days ahead). The service skips slots that already exist and returns only the ones it inserted; `bulk_create(ignore_conflicts=True)` only guards concurrent runs, and its return value cannot be trusted as "created". In production the `generate_slots --days=28` command runs on every Render boot (`startCommand`, inside a subshell so a failure never blocks gunicorn), since the free plan has no cron jobs. 28 days are the four weeks patients can browse on the web (`BOOKING_WEEKS_AHEAD`); `tests/unit/test_render_blueprint.py` keeps the two in step. The signal swallows errors so the Schedule save always succeeds. `TimeSlot` deliberately lives in `appointments` and is imported lazily from `doctors` to avoid a circular import — see `docs/adr/0001-timeslot-boundary.md`.
- **Booking**: `AppointmentCreateSerializer.validate()` calls `validate_appointment_booking` (slot available and not started yet, no overlapping patient appointment via `Q`/range filters → 400). `create_appointment` then reserves the slot with an atomic conditional `UPDATE ... WHERE status=available`; losing the race raises `SlotConflict` (409). The doctor is always derived from `slot.schedule.doctor`. `Appointment.slot` is a `ForeignKey`: a slot keeps its cancelled and completed appointments (`slot.appointments`), and the partial unique index `one_active_appointment_per_slot` allows one pending or confirmed appointment per slot. An insert that hits it also becomes `SlotConflict`, and any other `IntegrityError` propagates (`docs/adr/0004-slot-appointment-history.md`). Slot listings (`get_available_slots`, `get_available_slots_week`) skip slots that already started.
- **State machine**: transition methods live on `Appointment` (`confirm()`, `cancel()`, `complete()`, `mark_no_show()`) and raise `InvalidTransition` on illegal moves. Service functions wrap them in `@transaction.atomic`, write an audit line to the `medbook.audit` logger, free the slot on cancel, and send emails via `transaction.on_commit` (never inline).
- **Errors**: `apps/core/exceptions.custom_exception_handler` normalises every error to `{detail, code, field_errors?}` and maps Django `ValidationError` / `InvalidTransition` to 400. Keep this shape when adding errors.
- **Routing**: everything is under `/api/v1/` (`config/urls.py`); JWT at `/api/v1/token/`, `token/refresh/`, `token/blacklist/`; medical notes are nested manually at `/api/v1/appointments/<id>/notes/`. Swagger at `/api/docs/`, `/health/` for Render. Admin path comes from `DJANGO_ADMIN_URL`. The web UI owns `/` (`apps.web.urls`, included last) and `/i18n/setlang/` switches its language.
- **Web UI** (`apps/web`, ADR 0002): templates, views and later forms; no models and no business logic. Views call services, like the API. The layout (`web/base.html`) loads `{% tailwind_css %}` and the vendored `static/vendor/htmx-<version>.min.js`, and sends the CSRF token on every HTMX request via `hx-headers` on `<body>`. `django_htmx` provides `request.htmx`. Tailwind only scans `apps/web` (`apps/web/styles/tailwind.css` uses `source(none)` + `@source`), so class names must appear literally there. Language: `LANGUAGE_CODE = "es"`, `LocaleMiddleware` (cookie first, then `Accept-Language`), no URL prefix. `apps.core.middleware.EnglishApiMiddleware` re-activates English for every `/api/` path, so API messages never change with the visitor's language. `production.py` inserts WhiteNoise into base's `MIDDLEWARE` instead of redefining it; add new middleware in `base.py` only.
- **Web auth and RBAC** (Paso 25): Django session auth at `/login/`, `/logout/` (POST only) and `/signup/`; `LOGIN_URL = "web:login"`. `landing_url_for(user)` sends patients to `/` and doctors/admins to `/panel/`, a notice page until their panel exists; a safe `?next=` wins. Role checks for both paths live in `apps/core/roles.py` (`is_patient`, `is_doctor`, `is_admin`): the DRF permission classes call them, and so do the web mixins (`PatientRequiredMixin`, `StaffRequiredMixin` in `apps/web/mixins.py`: anonymous → login redirect, wrong role → 403) and the `apps.web.context_processors.roles` context processor (`user_is_patient`, …). Never compare `user.role` in templates or views. HTMX views use `HtmxPartialMixin` (`partial_template_name` for HTMX requests, the full page for plain requests and history restores, `Vary: HX-Request`); the fragment is a template under `partials/` that the full page includes. `ThrottleMixin` applies the API's DRF throttle classes to web POSTs, so the web login/sign-up and their API endpoints share one budget per IP (same scope, same cache key). Form widgets get Tailwind classes from `StyledFormMixin` in `apps/web/forms.py`.
- **Auth/security**: SimpleJWT with 15-min access, 1-day refresh, rotation + blacklist; global anon/user throttles plus `login`/`refresh`/`register` scopes; `NUM_PROXIES=1` in production.
- **Registration**: patients self-register through `apps/users/services.register_patient` (User with role=patient + Patient profile in one transaction; case-insensitive email uniqueness; Django password validators; field-keyed `ValidationError`). `POST /api/v1/users/register/` is public, skips authentication and returns the profile only, never tokens. The web `SignupForm` calls `validate_patient_registration` in `clean()` and the view calls `register_patient`, like the API serializer. `DUPLICATE_EMAIL_MESSAGE` is `gettext_lazy`: Spanish on the web, English in the API. Doctors and admins are still created via the admin.

## Non-negotiable rules

Layer responsibilities:

| Layer | Owns | Must not contain |
|---|---|---|
| `models.py` | Fields, relations, simple state transitions | Complex business logic |
| `serializers.py` | Input validation, output shape | Direct ORM queries, business rules, `request.user` (pass via `context`) |
| `views.py` | HTTP: auth, permissions, serialization, status codes | Direct ORM (beyond `get_queryset`), business rules |
| `services.py` | All business logic | HTTP, serializers |
| `permissions.py` | One check per class | Business logic |

- **15-line rule**: any `validate_*`, ViewSet action or model method beyond ~15 lines gets extracted to `services.py`.
- One serializer per action when logic diverges (`get_serializer_class` switching on `self.action`).
- ORM: `select_related` in every `get_queryset()` with FKs, `prefetch_related` for Doctor → specialties, `annotate()`/`Count()` for stats, `Q()` for schedule conflicts, `save(update_fields=[..., "updated_at"])` on partial saves. Filter in the ORM, never in Python loops.
- Catch specific exceptions, never bare `except Exception` (the signal handler's last-resort `logger.exception` is the documented exception).
- Never log passwords, tokens or Authorization headers.
- Never hardcode a password or secret, not even a fake one. GitGuardian scans every PR and flagged test literals in PR #149. Each place has its own source:
  - Tests use `tests.factories.random_password()`, `short_password()` (fails the minimum length) and `UserFactory().raw_password`; a wrong password is just another `random_password()`.
  - CI gets a random `SECRET_KEY` from `.github/actions/setup-django`, and the Dockerfile generates its build-time key inside the `RUN`.
  - `docker-compose*.yml` and `config/settings/local.py` read `SECRET_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_TEST_PASSWORD` and `DATABASE_URL` from `.env`, with no defaults.
  - GitGuardian also flags a custom message in compose's `${VAR:?message}` and any `${...}` in the password slot of a connection URL. Use a bare `${VAR:?}`, and pass the DB password to the `web` service as `PGPASSWORD`, which libpq reads.
  - Docs use `<placeholders>` or shell-generated values.

## Testing

Strict TDD (red → green → refactor): write the failing test before the implementation.

- `tests/unit/` — models, services, permissions, commands, signals (DB allowed via `@pytest.mark.django_db`, no HTTP).
- `tests/integration/` — full HTTP stack: `APIClient` for the API, pytest-django's `client` for the web UI (`headers={"Accept-Language": ...}`, `{"HX-Request": "true"}`, `client.force_login(user)`).
- All test data via `factory_boy` (`tests/factories.py`); no JSON/YAML fixtures. Shared fixtures (`api_client`, `user_patient`, `user_doctor`, `user_admin`, `doctor_profile`, …) are in `tests/conftest.py`, which also resets `mail.outbox` and the active language before each test. Django never deactivates the language a request activated, so without that reset a request in one test would decide the language of the next one. With no request, messages come out in Spanish (`LANGUAGE_CODE`); use `translation.override("en")` to assert English.
- Data migrations are tested by calling their forward function with the historical app registry (`MigrationLoader(None, ignore_no_migrations=True).project_state((app, migration)).apps`), the models `migrate` hands them. The live registry drifts as models change; see `tests/unit/test_migrations.py`.
- Throttled endpoints (API or web) need `cache.clear()` around each test; see `tests/integration/test_throttling.py` and `test_web_auth.py`.
- Every permission class and every web role mixin needs a positive and a negative test.
- Coverage targets: models + services 90%, views + serializers 80%, permissions 100%, management commands 70%; the global branch-coverage gate is 95%.

## Workflow

- One branch and one PR per numbered step; PRs reference their issue (`Closes #N`). Recent branches use `audit/<area>-<desc>`; sprint work used `semana{N}/paso-{N}-<desc>`. Conventional Commits (`feat|fix|refactor|docs|test|chore(scope): …`).
- Pause and show full output (and wait for confirmation) after: any `makemigrations` (show the generated file), any `migrate`, a full test run (counts + coverage), and each completed numbered step.
- On a failing command or an unexpected test failure, report the full traceback/diff and ask before changing the implementation — do not iterate silently.
- If an architecture decision is not covered by the docs or this file, ask first.
- For Django/DRF work, load the `django-drf-patterns` skill; for tests, `python-testing-patterns`. (The `.agent/skills/` paths referenced in `.atl/skill-registry.md` point to an old machine and do not exist here.)
