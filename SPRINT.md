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
| 23 | Horarios en hora de Chile (`TIME_ZONE`, generación de slots, data migration) | #133 | #143 | ✅ |
| 24 | Base web: `apps/web`, layout, Tailwind (`django-tailwind-cli`), HTMX, i18n es/en; Dockerfile Alpine | #134 | #148 | ✅ |
| 25 | Login, logout y registro web con sesión; RBAC web compartido con DRF | #135 | #149 | ✅ |
| 26 | Catálogo de doctores y slots disponibles (HTMX) | #136 | #150 | ✅ |
| 30 | **Bug**: re-reservar un slot liberado por cancelación (`OneToOne` → FK + unique parcial) y rechazar slots que ya empezaron. Va antes del 27 | #142 | #152 | ✅ |
| 31 | Render como Blueprint: `render.yaml` adopta el servicio `MedBook` (auto-sync). Va antes de mergear el 23 | #144 | #146 | ✅ |
| 32 | Producción en Docker Alpine (servicio nuevo vía Blueprint). Va después del 24 | #145 | — | ⬜ |
| 33 | Datos demo: comando `seed_demo` idempotente (doctores y horarios), activado en Render con `MEDBOOK_DEMO_DATA`. Va antes del 29 | #147 | — | ⬜ |
| 27 | Reservar cita (services de booking, manejo de conflictos) | #137 | — | ⏳ |
| 28 | Mis citas y cancelación; selector de visibilidad compartido con la API | #138 | — | ⬜ |
| 29 | Páginas de error, accesibilidad, docs y verificación en Render | #139 | — | ⬜ |
| 34 | **Bug**: email sin distinguir mayúsculas en el login (API y web) y unicidad case-insensitive en la DB. Independiente | #151 | — | ⬜ |

---

## Checklist acumulativo — Semana 5

- [x] Un horario de 09:00–17:00 se ve como 09:00–17:00 en Chile, en verano y en invierno
- [ ] Flujo completo en la web: registro → login → doctores → reserva → mis citas → cancelación
- [x] UI en español por defecto y en inglés con el selector; la API sigue respondiendo en inglés
- [ ] Ninguna view web accede al ORM: todo pasa por services o selectors
- [x] Build de Tailwind en Render, Docker y CI; `.mo` al día (chequeo en CI)
- [ ] Gate de coverage ≥ 95% branch se mantiene

---

## Notas técnicas registradas — Semana 5

- Windows no trae gettext: `winget install mlocati.GetText` (o correr `makemessages` dentro de Docker). Render no lo necesita porque los `.mo` se versionan.
- `django-tailwind-cli` descarga el binario de Tailwind en el primer `tailwind build`; en Render ocurre durante el `buildCommand`. No detecta musl: el Dockerfile Alpine (Paso 24) baja `tailwindcss-linux-<arch>-musl`, lo verifica con el sha256 del release y lo usa vía `TAILWIND_CLI_PATH`. Ese binario (Bun) necesita `libstdc++`, que solo se instala en la etapa builder.
- `makemessages` en Windows escribe rutas `.\apps\...` en los comentarios de ubicación, y en Linux saldrían con `/`: por eso se usa `--no-location` y CI compara el resultado ignorando solo `POT-Creation-Date`. El `.mo` compilado con gettext 1.0 (Windows) y 0.21 (Ubuntu 24.04) es idéntico byte a byte (verificado).
- `production.py` redefinía `MIDDLEWARE` completo: `LocaleMiddleware` y `HtmxMiddleware` no habrían llegado a producción. Ahora inserta WhiteNoise en la lista de `base.py` (test en `tests/unit/test_production_settings.py`).
- El stack de `docker compose up` corre gunicorn con settings locales y sin WhiteNoise, así que no sirve estáticos (ni el CSS de la web ni el del admin). Se resuelve en el Paso 32, cuando la imagen pase a ser la de producción.
- El servicio de Render se creó a mano (sin Blueprint), así que `render.yaml` se ignoraba. El Paso 31 lo convierte en Blueprint (adopción por nombre: misma URL y mismos secretos) y desde ahí manda el archivo.
- Django no desactiva el idioma que activó un request, así que se filtraba entre tests del mismo hilo. `tests/conftest.py` lo resetea antes y después de cada test (Paso 25).
- El login web y el de la API comparten presupuesto por IP: `ThrottleMixin` usa las mismas clases DRF (`LoginRateThrottle`, `RegisterRateThrottle`), con el mismo scope y la misma cache key (Paso 25).
- GitGuardian marcó passwords escritos en los tests del PR #149 (3 valores, 7 ocurrencias). Se reescribió la rama para sacarlos y se limpió el repo entero: los tests generan passwords con `tests.factories.random_password()`, CI y el Dockerfile generan su `SECRET_KEY`, y compose y `local.py` leen todo desde `.env` sin defaults. Regla en `CLAUDE.md`: nunca escribir un password ni un secreto, ni siquiera uno falso.
- Las especialidades sembradas por `0003_data_specialties` están en inglés en la DB. La web muestra `Specialty.display_name` (`gettext` del nombre; los msgids se marcan con `gettext_noop` en `apps/doctors/models.py`) y la API mantiene el nombre guardado. Una especialidad creada en el admin se ve tal cual hasta que se agregue su traducción (Paso 26).
- El `TransactionTestCase` de la concurrencia de reservas vacía las tablas, así que con `--reuse-db` los datos de las data migrations (las especialidades) pueden no estar. Los tests crean lo que usan (Paso 26).
- El endpoint `available-slots` de la API filtraba por fecha y devolvía también los slots de hoy que ya empezaron. La web (`get_available_slots_week`) filtra por `start_datetime > now` desde el Paso 26; la API y la validación de reservas, desde el Paso 30.
- La web deja navegar 4 semanas de slots (`BOOKING_WEEKS_AHEAD`), así que el arranque en Render pasa de `generate_slots --days=14` a `--days=28`. `tests/unit/test_render_blueprint.py` falla si `render.yaml` vuelve a quedar por debajo (Paso 26).
- Re-reservar un slot cancelado no daba 500 en la API, como decía el #142, sino 400 ("appointment with this slot already exists"): DRF agrega solo un `UniqueValidator` para un `OneToOneField`. Llamando al service, como lo hará la web, sí era un `IntegrityError` (500). Con el `ForeignKey` y el índice único parcial ya no hay validador automático: el service da 400 y un conflicto da 409 (Paso 30, ADR 0004).
- Los tests de la data migration 0002 la llamaban con los modelos actuales, y se rompieron cuando `TimeSlot.appointment` pasó a `appointments`. Ahora usan el estado histórico de la migración, igual que `migrate` (Paso 30).
- Desde el 2026-10-24, Smart App Control de Windows bloquea el `python.exe` sin firma que uv escribe dentro de un venv (os error 4551). El `.venv` se recrea con `python -m venv` y pip, que es lo que pide este repo de todos modos (Paso 30).
- La confirmación de la reserva es un `<dialog>` nativo: el slot lo carga con HTMX y `web/js/booking-dialog.js` (un listener de 6 líneas) llama a `showModal()` en `htmx:afterSwap`. Cerrar no necesita JS: Esc y los `<form method="dialog">`. El preflight de Tailwind le quita el `margin: auto` al `<dialog>`, por eso lleva `m-auto`. "Cancelar" usa `form="booking-dialog-cancel"` porque un `<form method="dialog">` dentro del formulario de la reserva sería un form anidado. Sin JS, el mismo link abre la página completa de confirmación (Paso 27).
- Los errores de `validate_appointment_booking` eran strings en inglés. Ahora son `gettext_lazy`: la web los muestra en español y la API sigue en inglés gracias a `EnglishApiMiddleware` (test en `test_api_language.py`). Un error en el modal lo vuelve a renderizar con el mensaje y refresca la semana de atrás con `hx-swap-oob`; una reserva exitosa responde `HX-Redirect` a la semana del slot (Paso 27).
- `ScheduleFactory` (lunes) dispara la señal que genera 7 días de slots. Si el test corre un domingo, "mañana 10:00" ya existe y un `TimeSlotFactory` a esa hora choca con `unique_slot_per_schedule_start`. `test_web_booking.py` usa `bare_schedule()`, que borra los slots de la señal (Paso 27).

### Pendientes por decidir

- **Idioma de la API**: decidido, se mantiene en inglés (`EnglishApiMiddleware`, ADR 0002). La API la consumen desarrolladores y clientes, y todo su contrato (rutas, campos, estados, `code`, Swagger) está en inglés. Los mensajes que ve el paciente salen de la web, que los traduce (por ejemplo, el login web dice "Correo o contraseña incorrectos." y `/api/v1/token/` responde el mensaje en inglés de SimpleJWT). Si aparece un cliente en español, se evalúa respetar `Accept-Language` con inglés por defecto.
- **Email sensible a mayúsculas en el login**: `normalize_email` solo baja a minúsculas el dominio y el login busca el email exacto, así que quien se registró como `Ana@example.com` no entra con `ana@example.com` (ni en la API ni en la web). La unicidad sí es case-insensitive. Viene de antes del sprint. Decidido: no distinguir mayúsculas, se corrige en el Paso 34 (#151).
- **Correo de confirmación en inglés y en UTC** (detectado en el Paso 27): `send_appointment_created` arma el texto en inglés y formatea la hora con `strftime("%Y-%m-%d %H:%M UTC")`, así que una hora de las 10:00 en Chile dice "13:00 UTC". Pasa lo mismo con los correos de confirmación y cancelación. Viene de antes de la web. Propuesta: correos en el idioma de la web (español por defecto) y con la hora de Chile. Sin paso asignado.
- **Sesión expirada con el modal de reserva abierto** (detectado en el Paso 27): HTMX sigue el redirect al login y metería la página de login dentro del modal. Propuesta: que `RoleRequiredMixin` responda `HX-Redirect` al login cuando el request es HTMX. Va en el Paso 29.
- **Paciente sin perfil** (detectado en el Paso 27): un usuario con rol paciente creado desde el admin sin su `Patient` da 500 al reservar, en la web y en la API (`request.user.patient_profile`). El registro público siempre crea el perfil. Propuesta: crearlo también desde el admin, o responder un error claro. Va en el Paso 29.
- **"Dr." para todas las médicas** (detectado en el Paso 27): `Doctor.__str__` antepone "Dr." siempre, así que la web muestra "Dr. Carla Soto"; los correos hacen lo mismo. El modelo no guarda cómo tratar a cada médico. Propuesta: un campo de tratamiento (Dr./Dra.) traducible, o mostrar solo el nombre. Sin paso asignado.
