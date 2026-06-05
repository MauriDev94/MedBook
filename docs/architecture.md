# MedBook — Architecture & Decision Log

> This document explains **why** each technical decision was made, what alternatives were considered, and what the tradeoffs are. Written for study and interview preparation.

---

## 1. Custom User model — `AbstractBaseUser` vs `AbstractUser`

### Decision
Extend `AbstractBaseUser` instead of Django's default `AbstractUser`.

### Why
`AbstractUser` ships with `username`, `first_name`, `last_name`, `email`, date fields, and a boolean permission system. We don't need a `username` field — email is the login identifier — and we don't need Django's `groups`/`permissions` M2M tables (we roll our own `role` field).

Using `AbstractBaseUser` gives us a clean slate: we define exactly the fields we need.

```python
# apps/users/models.py
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = "email"   # login with email, not username
    REQUIRED_FIELDS = []
```

### Tradeoff
More boilerplate (custom `UserManager`, explicit `has_perm`, etc.). But for any serious project, `AbstractBaseUser` is the right choice — trying to strip fields from `AbstractUser` is harder than adding the ones you need.

### Critical rule
**The custom User model must be defined before the first `migrate` run.** Changing it after the fact is painful (requires resetting migrations or using complex data migrations). This is why it's Semana 1, Step 1 in the sprint.

---

## 2. UUID primary keys everywhere

### Decision
All models use `UUIDField(primary_key=True, default=uuid.uuid4)`.

### Why
- **Security:** Sequential integer IDs expose information. `GET /api/appointments/42/` tells the attacker there are at least 42 appointments. UUIDs are unguessable.
- **Distributed systems:** UUIDs are safe to generate client-side without coordinating with the DB. Useful if you ever need to pre-generate IDs before inserting.
- **No IDOR leakage:** A patient can't enumerate other patients' appointments by incrementing IDs.

### Tradeoff
Slightly larger storage (16 bytes vs 4 bytes for int). Slightly slower index lookups (random UUIDs fragment B-tree indexes). For a medical booking system at any reasonable scale, this is irrelevant.

---

## 3. Role-based access via field, not Django groups

### Decision
A single `role` CharField on User (`admin | doctor | patient`) instead of Django's `groups`/`permissions` system.

### Why
Django's groups system is designed for fine-grained object-level permissions with a generic content-type framework. For this domain, we have three clear roles with well-defined privileges. A `role` field is explicit, readable, and directly queryable:

```python
# In any permission class or service:
if request.user.role == Role.DOCTOR:
    ...
```

### Tradeoff
Can't mix roles (a user is either a doctor or a patient, never both). This is intentional for this domain. If the requirement changed (e.g., a doctor who is also a patient in another clinic), you'd need a pivot table.

---

## 4. Services layer — the 15-line rule

### Decision
Business logic lives in `services.py` functions. ViewSets call service functions. ViewSets never touch the ORM for anything beyond `get_queryset()`.

### Why
This is DIP (Dependency Inversion Principle) adapted to Django. The ViewSet depends on an abstraction (the service function), not on a concrete ORM implementation. This has three concrete benefits:

1. **Testability:** You can unit-test `confirm_appointment()` without spinning up an HTTP stack. Just call the function with a mocked appointment.
2. **Reuse:** The same `create_appointment()` function can be called from a management command, an admin action, or an API endpoint.
3. **Clarity:** When you look at a ViewSet action and it's 5 lines, you know exactly where the logic lives.

```python
# ❌ Fat ViewSet — untestable, logic coupled to HTTP
@action(detail=True, methods=["post"])
def confirm(self, request, pk=None):
    appointment = self.get_object()
    if appointment.status != "pending":
        return Response({"error": "..."}, status=400)
    appointment.status = "confirmed"
    appointment.save()
    appointment.slot.save()
    # send email...
    return Response(...)

# ✅ Thin ViewSet — calls service, HTTP only
@action(detail=True, methods=["post"])
def confirm(self, request, pk=None):
    appointment = self.get_object()
    try:
        services.confirm_appointment(appointment, confirmed_by=request.user)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(AppointmentDetailSerializer(appointment).data)
```

---

## 5. Atomic transaction for slot booking — preventing race conditions

### Decision
`create_appointment()` uses `@transaction.atomic` with an atomic `UPDATE ... WHERE status='available'` instead of read-then-write.

### Why
Classic race condition: two patients simultaneously check that slot X is available. Both see `status=AVAILABLE`. Both proceed to create an appointment. Both succeed. Now one slot has two appointments.

The fix is to make the availability check and the reservation atomic:

```python
# ❌ Read-then-write — race condition
slot = TimeSlot.objects.get(pk=slot_id)
if slot.status == "available":       # Thread A checks here
    # ... Thread B also checks here and sees "available"
    slot.status = "reserved"         # Thread A writes
    slot.save()                      # Thread B writes — both succeed!

# ✅ Atomic UPDATE — only one thread can win
@transaction.atomic
def create_appointment(patient, doctor, slot, reason=""):
    updated = TimeSlot.objects.filter(
        id=slot.id,
        status=TimeSlot.Status.AVAILABLE   # condition in the UPDATE
    ).update(
        status=TimeSlot.Status.RESERVED,
        updated_at=timezone.now()
    )
    if not updated:   # 0 rows updated = someone else got there first
        raise ValidationError("This time slot is no longer available.")

    slot.refresh_from_db()
    return Appointment.objects.create(patient=patient, doctor=doctor, slot=slot, reason=reason)
```

At the database level, `UPDATE ... WHERE status='available'` is atomic. Exactly one thread's `UPDATE` will match and return 1. The other will return 0. No slot can be double-booked.

### Why `@transaction.atomic` on top?
The function creates two DB records: updates the slot AND creates the appointment. If the appointment creation fails for any reason, the slot update should also roll back. The decorator guarantees both operations succeed or both fail together.

---

## 6. State machine on the model

### Decision
Appointment state transitions are methods on the `Appointment` model: `confirm()`, `cancel()`, `complete()`, `mark_no_show()`. Each method validates the current state before transitioning.

### Why
The model is the right place for invariants about its own data. A state machine on the model means:

- The constraint lives with the data — impossible to forget to check it
- Any code that touches the model gets the validation for free
- Tests for the state machine don't need HTTP

```python
# apps/appointments/models.py
class Appointment(models.Model):
    def can_be_confirmed(self) -> bool:
        return self.status == self.Status.PENDING

    def confirm(self) -> None:
        if not self.can_be_confirmed():
            raise ValueError(f"Cannot confirm appointment in status '{self.status}'.")
        self.status = self.Status.CONFIRMED
        self.save(update_fields=["status", "updated_at"])
```

### Tradeoff
The service `confirm_appointment()` just calls `appointment.confirm()` — it looks like an unnecessary wrapper. But the service exists for two reasons: 1) it's `@transaction.atomic`, and 2) it's where you'd add cross-entity logic (like sending a notification or updating a counter) without bloating the model.

---

## 7. ORM optimization — N+1 queries

### Decision
Every `get_queryset()` method uses `select_related()` for FK relationships and `prefetch_related()` for M2M.

### Why
Without `select_related`, a list of 20 appointments triggers 21 queries: 1 for the list + 1 per appointment to load the patient + 1 per appointment for the doctor + ... This is the N+1 problem, and it's invisible unless you measure it.

```python
# ❌ N+1 — triggers 1 + 3N queries for N appointments
def get_queryset(self):
    return Appointment.objects.all()

# In serializer:
# appointment.patient.user.email  → extra query per appointment
# appointment.doctor.user.email   → extra query per appointment
# appointment.slot.start_datetime → extra query per appointment

# ✅ select_related — joins in one query
def get_queryset(self):
    return Appointment.objects.select_related(
        "patient__user",
        "doctor__user",
        "slot__schedule",
    )
```

`select_related` does a SQL JOIN. `prefetch_related` does a separate query but batches all IDs. Use `select_related` for FK (one-to-one, many-to-one), `prefetch_related` for M2M (like Doctor → specialties).

---

## 8. Signals for slot generation — when to use signals

### Decision
Use a `post_save` signal on `Schedule` to generate slots automatically when a new schedule is created.

### Why
Signals are the right tool here because:
- The slot generation is a **side effect** of schedule creation, not core business logic
- The sender (`doctors.Schedule`) shouldn't need to know about slot generation
- This is a reactive pattern: "when X happens, do Y"

```python
# apps/doctors/signals.py
@receiver(post_save, sender=Schedule)
def generate_initial_slots(sender, instance, created, **kwargs):
    if not created:
        return   # only on creation, not updates
    from apps.appointments.services import generate_slots_for_schedule
    try:
        generate_slots_for_schedule(instance, days_ahead=7)
    except Exception:
        logger.exception("Failed to generate slots for schedule %s", instance.id)
```

The `try/except` is intentional: we NEVER want slot generation to break the schedule save. The schedule is the primary operation; slots are secondary.

### When NOT to use signals
We deliberately do NOT use signals for appointment notifications. Signals are fire-and-forget and hard to trace. For business-critical emails (confirm, cancel), the call is explicit in the service function. You can `grep` for it. Signals are invisible.

---

## 9. factory_boy instead of fixtures

### Decision
All test data is created with factory_boy factories. Zero JSON/YAML fixtures.

### Why
Fixtures have three problems:
1. **Coupling:** change a model field → all fixtures break
2. **Opacity:** you can't tell at a glance what data a test needs
3. **Maintenance:** fixtures accumulate and nobody knows what they're for

factory_boy solves all three:

```python
# tests/factories.py
class AppointmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Appointment

    patient = factory.SubFactory(PatientFactory)   # creates a Patient
    doctor = factory.SubFactory(DoctorFactory)     # creates a Doctor
    slot = factory.SubFactory(TimeSlotFactory)     # creates a TimeSlot
    reason = factory.Faker("sentence")
    status = Appointment.Status.PENDING

# In a test:
appointment = AppointmentFactory(status="confirmed")   # explicit
appointment = AppointmentFactory(patient=my_patient)   # override specific fields
```

Each test creates exactly the data it needs, nothing more.

---

## 10. Email notification architecture

### Decision
Notification functions in `apps/notifications/services.py`, called directly from `apps/appointments/services.py`.

### Alternatives considered

**Option A — Django signals:**
```python
# post_save on Appointment
@receiver(post_save, sender=Appointment)
def on_appointment_change(sender, instance, created, **kwargs):
    if created:
        send_appointment_created(instance)
```
Problem: fires on EVERY save, including admin edits and management commands. Needs careful `created` and status-comparison logic. Hard to test.

**Option B — Direct call from service (chosen):**
```python
@transaction.atomic
def confirm_appointment(appointment, confirmed_by):
    appointment.confirm()
    from apps.notifications.services import send_appointment_confirmed
    send_appointment_confirmed(appointment)
    return appointment
```
Explicit, greppable, easy to test with `mail.outbox`.

**Option C — `transaction.on_commit`:**
```python
transaction.on_commit(lambda: send_appointment_confirmed(appointment))
```
Best for production (email only sent if DB transaction commits). Requires `@pytest.mark.django_db(transaction=True)` in tests. A valid upgrade path for when Resend is connected.

### Email backends by environment
```python
# local — prints to console, no setup needed
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# test — mail.outbox in memory, assertions don't need SMTP
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# production — Resend via anymail
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
```

The view/service code never changes. Only the backend is swapped via environment variable.

---

## 11. Custom exception handler

### Decision
A `custom_exception_handler` in `apps/core/exceptions.py` normalizes all DRF errors to `{detail, code, field_errors?}`.

### Why
DRF's default error format is inconsistent:
- `{"detail": "Not found."}` for 404
- `{"email": ["This field is required."]}` for validation errors
- `{"non_field_errors": ["Passwords don't match."]}` for non-field errors

A frontend (or a mobile app) has to handle 3+ different shapes. Our handler normalizes everything:

```json
// 401
{"detail": "Authentication credentials were not provided.", "code": "not_authenticated"}

// 400 (field error)
{
  "detail": "Invalid input.",
  "code": "validation_error",
  "field_errors": {
    "end_time": ["end_time must be after start_time."]
  }
}

// 400 (non-field error)
{"detail": "You already have an appointment at this time.", "code": "validation_error"}
```

One shape. Always. Clients can write one error handler.

---

## 12. Rate limiting — why only on login

### Decision
`LoginRateThrottle` (5 req/min per IP) applied only to `POST /api/token/`. No global throttle on other endpoints.

### Why
The attack vector is brute-force on the login endpoint. Authenticated endpoints are already protected — if your JWT is invalid or expired, you get 401 without any DB query. A global `UserRateThrottle` would:
1. Throttle admin users running scripts
2. Break CI/CD pipelines that make multiple requests
3. Create false positives during normal usage

### Why `AnonRateThrottle` specifically?
The token endpoint is accessed anonymously by definition (you don't have a token yet). `AnonRateThrottle` tracks by IP address, which is the correct dimension for brute-force protection. `UserRateThrottle` would need an authenticated user to track — impossible for a login endpoint.

---

## 13. PostgreSQL from day one

### Decision
No SQLite, ever. PostgreSQL in development, CI, and production.

### Why
SQLite has silent behavioral differences that hide real bugs:
- No `unique_together` enforcement in certain transaction isolation levels
- Different datetime precision
- No `RETURNING` clause (Django's `update()` with `returning=True` won't work)
- No concurrent write locking

A bug that only exists in production (because SQLite masked it) is the worst kind of bug. Using the same DB everywhere eliminates an entire class of "works on my machine" problems.

The Docker Compose setup provides a disposable PostgreSQL with zero friction.

---

## 14. Swagger with drf-spectacular

### Decision
`drf-spectacular` for OpenAPI schema generation, serving at `/api/docs/`.

### Key configuration decisions

**`SERVE_INCLUDE_SCHEMA: False`** — The `/api/schema/` endpoint itself is excluded from the schema (meta-endpoint, no need to document it).

**`COMPONENT_SPLIT_REQUEST: True`** — DRF-spectacular generates separate schemas for request and response bodies. This is important because our serializers behave differently for reads (include auto-generated fields like `id`, `created_at`) and writes (exclude them). Without this, the Swagger UI shows misleading schemas.

**`ENUM_NAME_OVERRIDES`** — Both `Appointment.Status` and `TimeSlot.Status` have a field named `status`. Without this, drf-spectacular generates collision names like `Status728Enum`. The override gives them meaningful names: `AppointmentStatusEnum` and `TimeSlotStatusEnum`.

**`swagger_fake_view` guard** — Every `get_queryset()` that accesses `request.user.role` needs this guard, because drf-spectacular calls `get_queryset()` with an `AnonymousUser` to introspect the schema:

```python
def get_queryset(self):
    if getattr(self, "swagger_fake_view", False):
        return Appointment.objects.none()
    # ... real logic
```

Without it, `AnonymousUser` has no `.role` attribute and spectacular crashes.

---

## 15. Static files in production — WhiteNoise

### Decision
Use `whitenoise[brotli]` to serve static files directly from the Gunicorn process, without Nginx or a CDN.

### Why
Django's development server (`runserver`) serves static files automatically. Gunicorn does not — it is a pure WSGI server that only runs Python. Without a static file solution, the Django admin and Swagger UI ship to production with broken CSS/JS (404 on every asset).

Three options:
- **Nginx as reverse proxy** — the "production" answer for large deployments, but requires a separate process and configuration.
- **CDN (S3 + CloudFront)** — correct for high-traffic apps; overkill for a portfolio project.
- **WhiteNoise** — a middleware that intercepts static file requests before they reach Django's URL router. Zero extra infrastructure.

```python
# config/settings/production.py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # right after SecurityMiddleware
    ...
]

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

`CompressedManifestStaticFilesStorage` adds a content hash to every filename (`base.abc123.css`). This enables `Cache-Control: max-age=31536000` — browsers cache the file for a year, and when the file changes its hash changes, forcing a fresh download. This is the standard cache-busting pattern.

### Tradeoff
WhiteNoise adds a small overhead per request compared to Nginx (which can serve files from kernel buffers). For a portfolio project serving a handful of users, this is irrelevant. For a high-traffic production app, Nginx or a CDN is the right call.

---

## 16. Branch coverage as the honest metric

### Decision
Use `--cov-branch` (branch coverage) instead of line coverage. Enforce a minimum of 85% via `--cov-fail-under=85` in both `pytest.ini` and CI.

### Why line coverage lies

```python
def can_be_confirmed(self) -> bool:
    return self.status == self.Status.PENDING
```

Line coverage says this is 100% covered if the function is called once — even if it always returns `True` and the `False` branch is never exercised. Branch coverage requires both `True` and `False` paths to be tested.

More critically, for conditionals like:

```python
if not updated:  # race condition path
    raise ValidationError("This time slot is no longer available.")
```

Line coverage counts this as covered the moment the `if` is executed. Branch coverage requires both paths: the normal path (updated > 0) AND the race condition path (updated = 0). If you never test the race, line coverage silently inflates to 99%.

### Why 85%, not 100%?

100% branch coverage is theoretically achievable but practically forces you to test `if getattr(self, "swagger_fake_view", False)` guards, `except Exception` handlers in signals, and other defensive code that is unreachable in normal flows. The effort spent writing those tests yields diminishing returns.

85% enforced in CI is a real gate — it means meaningful coverage exists, not just the happy path. The number will drop when new code is added; CI will catch it and force the developer to write the missing tests.

### The `pytest.ini` is the single source of truth

```ini
addopts =
    --cov=apps
    --cov-branch
    --cov-report=term-missing
    --cov-fail-under=85
```

CI adds only `--cov-report=xml` (needed by Codecov). It never overrides `addopts` — that would silently disable the gate.

---

## Summary — Interview-ready decisions

| Question | Answer |
|---|---|
| "Why AbstractBaseUser?" | Email login, no username field, clean slate for role field |
| "How do you prevent double-booking?" | Atomic UPDATE with WHERE status='available' inside @transaction.atomic |
| "Where does business logic live?" | services.py — ViewSets are thin HTTP handlers |
| "How do you handle N+1?" | select_related in every get_queryset(), enforced by code review |
| "Why not signals for notifications?" | Hard to trace, fire-and-forget, prefer explicit calls |
| "How do you test emails?" | locmem backend, assertions on mail.outbox |
| "Why PostgreSQL in tests?" | Eliminate silent differences between dev and production environments |
| "How does the state machine work?" | Methods on the model with explicit ValueError guards |
| "Why factory_boy?" | Fixtures break when models change; factories stay decoupled |
| "How is error format standardized?" | custom_exception_handler normalizes to {detail, code, field_errors?} |
| "How do you serve static files in production?" | WhiteNoise middleware — serves from Gunicorn, no Nginx needed, with Brotli compression + cache-busting hashes |
| "Why branch coverage instead of line coverage?" | Line coverage hides untested if/else branches; branch requires both paths; 85% enforced in CI as a real gate |
