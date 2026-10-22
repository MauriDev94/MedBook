# Sprint — Semana 2: Core API

> **Objetivo:** Modelos de appointments, máquina de estados, permissions RBAC, ViewSets core, services layer y signal de generación de slots.
> Timeline estimado: 5–8 PRs.

---

## Estado

| Paso | Descripción | Issue | PR | Estado |
|------|-------------|-------|----|--------|
| — | CI/CD workflows + Docker Compose + secrets | #11 | #12 | ✅ |
| 0 | Deuda técnica (3 fixes menores) | #13 | #27 | ✅ |
| 1 | Modelos de Appointments (TimeSlot, Appointment, MedicalNote) | #14 | #28 | ✅ |
| 2 | Permissions RBAC (8 clases) | #15 | #29 | ✅ |
| 3 | Tests de permissions (TDD: positivo + negativo por clase) | #16 | #29 | ✅ |
| 4 | Services layer + tests | #17 | #30 | ✅ |
| 5 | Signal post_save en Schedule + tests | #18 | #31 | ✅ |
| 6 | Management command `generate_slots` + tests | #19 | #32 | ✅ |
| 7 | ViewSets + Serializers | #20 | #33 | ✅ |
| 8 | Tests de integración | #21 | #34 | ✅ |
| 9 | Auditoría post-sprint: SOLID, DRY, coverage | #36 | #35 | ✅ |

---

## Checklist acumulativo — Semana 2

- [x] `python manage.py migrate` corre sin errores
- [x] Migraciones de appointments aplicadas
- [x] `pytest tests/ -v` pasa al 100% (169 tests, 99% cobertura)
- [x] Cobertura `apps/appointments/services.py` = 100%
- [x] Cobertura `apps/core/permissions.py` = 100%
- [x] Cobertura `apps/appointments/models.py` = 100%
- [x] Flujo completo: POST /api/token/ → POST /api/appointments/ → POST /api/appointments/{id}/confirm/
- [x] `python manage.py generate_slots` corre sin errores
- [x] Signal genera slots al crear un Schedule
- [x] GET /api/doctors/{id}/available-slots/ retorna slots disponibles
- [x] Ningún ViewSet accede al ORM directamente (todo via services o queryset)
- [x] Cobertura `apps/users/models.py` = 100%

---

## Deuda técnica registrada

- [x] Rate limiting en endpoints de auth → Issue #45 (Semana 3 — Paso 9)
- [x] CORS → Issue #45 (Semana 3 — Paso 9)
- [ ] Soft delete en Appointment para compliance médico — pospuesto a Semana 4

---

# Sprint — Semana 3: Polish + Producción

> **Objetivo:** Endpoints faltantes del PRD, filtros, Swagger, Admin personalizado, notificaciones email, rate limiting y deploy.
> Timeline estimado: 10 PRs.

---

## Estado

| Paso | Descripción | Issue | PR | Estado |
|------|-------------|-------|----|--------|
| 1 | UserViewSet (GET/PATCH /api/users/me/) + logout | #37 | #47 | ✅ |
| 2 | ScheduleViewSet — CRUD completo | #38 | #48 | ✅ |
| 3 | MedicalNoteViewSet — nested bajo appointments | #39 | #49 | ✅ |
| 4 | django-filter en Doctor, Appointment, Schedule | #40 | #50 | ✅ |
| 5 | drf-spectacular → Swagger en /api/docs/ | #41 | #51 | ✅ |
| 6 | Custom exception handler — formato estándar | #42 | #53 | ✅ |
| 7 | Admin personalizado (badge status + inlines) | #43 | #54 | ⏳ |
| 8 | Notificaciones email (3 tipos vía Resend) | #44 | — | ⬜ |
| 9 | Rate limiting en auth + CORS headers | #45 | — | ⬜ |
| 10 | Deploy Railway/Render + README completo | #46 | — | ⬜ |

---

## Checklist acumulativo — Semana 3

- [x] `GET /api/users/me/` retorna perfil del usuario autenticado
- [x] `POST /api/auth/token/blacklist/` invalida el refresh token
- [x] `GET/POST /api/schedules/` funcional con permisos correctos
- [x] `GET/POST /api/appointments/{id}/notes/` funcional (solo doctor dueño)
- [x] `?specialty=cardiology` filtra doctores correctamente
- [x] `?status=pending` filtra appointments correctamente
- [x] `PYTHONIOENCODING=utf-8 python manage.py spectacular --validate --fail-on-warn` sin errores
- [x] Swagger accesible en `/api/docs/` (local)
- [x] Errores de la API con formato `{detail, code, field_errors?}` consistente
- [x] AppointmentAdmin con badge de status en colores
- [x] DoctorAdmin con ScheduleInline
- [ ] Email en console al crear/confirmar/cancelar cita
- [ ] 6to request a `/api/auth/token/` en 1 minuto → 429
- [ ] `pytest --cov=apps` ≥ 85% total
- [ ] API desplegada en URL pública con Swagger accesible

---

## Notas técnicas registradas

- `AUTH_TOKEN_CLASSES` debe ser `"rest_framework_simplejwt.tokens.AccessToken"` (path completo) — PR #52
- `.env` no debe tener dos `DATABASE_URL` — la segunda pisa la primera y apunta a la DB de tests
- `PYTHONIOENCODING=utf-8` necesario en Windows para correr `spectacular` (carácter `→` en docstrings)
- `full_name` es `@property` en nuestro User, no `get_full_name()` (no hereda de `AbstractUser`)

---

# Sprint — Semana 4: Preparación fullstack

> **Objetivo:** Dejar la API lista para el frontend server-rendered (Django templates + HTMX, ver [ADR 0002](./docs/adr/0002-server-rendered-web-frontend.md)): Django LTS, registro público de pacientes y slots generados de forma continua.
> El sprint del frontend (`apps/web`) se planifica al cerrar este.

---

## Estado

| Paso | Descripción | Issue | PR | Estado |
|------|-------------|-------|----|--------|
| 20 | Django 5.2 LTS + DRF 3.18 + bumps de Dependabot (#121–#125) | #126 | #130 | ✅ |
| 21 | Registro público de pacientes (service + `POST /api/v1/users/register/`) | #127 | #131 | ✅ |
| 22 | `generate_slots` al arrancar el servicio en Render | #128 | #132 | ✅ |

---

## Checklist acumulativo — Semana 4

- [x] Django 5.2 LTS en producción, sin PRs de Dependabot pendientes
- [x] `POST /api/v1/users/register/` crea User + Patient y permite login inmediato en `/api/v1/token/`
- [ ] Cada arranque o deploy en Render deja slots disponibles para los próximos 14 días (pendiente: confirmar `Done. N new slots…` en los logs de Render)
- [x] Gate de coverage ≥ 95% branch se mantiene (99.43%)

---

# Sprint — Semana 5: Frontend del paciente

> **Objetivo:** Un paciente puede registrarse, iniciar sesión, buscar doctores, reservar y cancelar citas desde la web (Django templates + HTMX), en español o inglés y con horarios en hora de Chile.
> Decisiones: [ADR 0002](./docs/adr/0002-server-rendered-web-frontend.md) (frontend, Tailwind sin Node, i18n es/en, sin Alpine) y [ADR 0003](./docs/adr/0003-clinic-time-zone.md) (`America/Santiago`).
> El panel del doctor queda para el sprint siguiente.

---

## Estado

| Paso | Descripción | Issue | PR | Estado |
|------|-------------|-------|----|--------|
| 23 | Horarios en hora de Chile (`TIME_ZONE`, generación de slots, data migration) | #133 | — | ⏳ |
| 24 | Base web: `apps/web`, layout, Tailwind (`django-tailwind-cli`), HTMX, i18n es/en | #134 | — | ⬜ |
| 25 | Login, logout y registro web con sesión; RBAC web compartido con DRF | #135 | — | ⬜ |
| 26 | Catálogo de doctores y slots disponibles (HTMX) | #136 | — | ⬜ |
| 30 | **Bug**: re-reservar un slot liberado por cancelación (`OneToOne` → FK + unique parcial). Va antes del 27 | #142 | — | ⬜ |
| 27 | Reservar cita (services de booking, manejo de conflictos) | #137 | — | ⬜ |
| 28 | Mis citas y cancelación; selector de visibilidad compartido con la API | #138 | — | ⬜ |
| 29 | Páginas de error, accesibilidad, docs y verificación en Render | #139 | — | ⬜ |

---

## Checklist acumulativo — Semana 5

- [ ] Un horario de 09:00–17:00 se ve como 09:00–17:00 en Chile, en verano y en invierno
- [ ] Flujo completo en la web: registro → login → doctores → reserva → mis citas → cancelación
- [ ] UI en español por defecto y en inglés con el selector; la API sigue respondiendo en inglés
- [ ] Ninguna view web accede al ORM: todo pasa por services o selectors
- [ ] Build de Tailwind en Render, Docker y CI; `.mo` al día (chequeo en CI)
- [ ] Gate de coverage ≥ 95% branch se mantiene

---

## Notas técnicas registradas — Semana 5

- Windows no trae gettext: `winget install mlocati.GetText` (o correr `makemessages` dentro de Docker). Render no lo necesita porque los `.mo` se versionan.
- `django-tailwind-cli` descarga el binario de Tailwind en el primer `tailwind build`; en Render ocurre durante el `buildCommand`. No detecta musl: en el Dockerfile Alpine (Paso 24) hay que bajar `tailwindcss-linux-x64-musl` y usar `TAILWIND_CLI_PATH`.
- El servicio de Render se creó a mano (sin Blueprint): `render.yaml` es solo referencia. Los cambios de build o start se pegan en el dashboard (ver `CLAUDE.md`).
