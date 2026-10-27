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
- [x] Cada arranque o deploy en Render deja slots disponibles para los próximos 14 días (28 desde el Paso 26). Confirmado en los logs de Render tras el Paso 33: `Done. 432 new slots generated across 17 schedule(s).`
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
| 33 | Datos demo: comando `seed_demo` idempotente (doctores y horarios), activado en Render con `MEDBOOK_DEMO_DATA`. Va antes del 29 | #147 | #155 | ✅ |
| 27 | Reservar cita (services de booking, manejo de conflictos) | #137 | #153 | ✅ |
| 28 | Mis citas y cancelación; selector de visibilidad compartido con la API | #138 | #154 | ✅ |
| 29 | Páginas de error, accesibilidad, docs y verificación en Render | #139 | #156 | ✅ |
| 34 | **Bug**: email sin distinguir mayúsculas en el login (API y web) y unicidad case-insensitive en la DB. Independiente | #151 | #160 | ✅ |
| 35 | **Bug**: el paciente no puede cancelar una cita que ya empezó (API y web). Independiente | #157 | #161 | ✅ |
| 36 | Trato Dr./Dra. según el médico (campo traducible; las tres doctoras demo). Va antes del 37 | #158 | — | ⏳ |
| 37 | **Bug**: correos en español y con la hora de Chile (hoy en inglés y en UTC). Va después del 36 | #159 | — | ⬜ |

---

## Checklist acumulativo — Semana 5

- [x] Un horario de 09:00–17:00 se ve como 09:00–17:00 en Chile, en verano y en invierno
- [x] Flujo completo en la web: registro → login → doctores → reserva → mis citas → cancelación (verificado en local con Chrome en el Paso 29, con teclado y a 375 px, y en Render el 2026-10-26)
- [x] UI en español por defecto y en inglés con el selector; la API sigue respondiendo en inglés
- [x] Ninguna view web accede al ORM: todo pasa por services o selectors (revisado en el Paso 29: cada `get_queryset` de `apps/web/views.py` llama a un service)
- [x] Build de Tailwind en Render, Docker y CI; `.mo` al día (chequeo en CI)
- [x] Gate de coverage ≥ 95% branch se mantiene (99.6%)
- [x] Páginas 403, 404 y 500 con el layout; navegación con teclado, foco en los modales y en los swaps, región viva para los lectores de pantalla y contraste AA en los botones (Paso 29)

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
- "Mis citas" separa por fecha: Próximas son las que no han empezado, en cualquier estado, y Pasadas las que ya empezaron. Una cita cancelada sigue en Próximas con su badge, también si la canceló el médico. Reservar ahora lleva a "Mis citas"; en el Paso 27 volvía al médico porque la página no existía (Paso 28).
- El filtrado por rol del `AppointmentViewSet` pasó a `appointments_visible_to(user)`, que comparten la API y la web. Con los tres roles la API responde igual (sus tests no cambiaron); un usuario anónimo o con un rol desconocido ya no ve todas las citas, no ve ninguna (Paso 28).
- Al cancelar con HTMX, la respuesta reemplaza el bloque de estado (`#appointment-<pk>-status`: badge y botón), que está en la fila de la lista y en el detalle, vía `HX-Retarget`. El mensaje entra fuera de banda a `#messages`, que ahora siempre está en la página (región `role="status"`). `booking-dialog.js` pasó a ser `dialog.js`: abre el `<dialog>` cuando HTMX le pone contenido y lo cierra cuando un form de adentro actualiza algo de afuera. `htmx:afterSwap` se dispara sobre el target, no sobre el form, así que el script usa `event.detail.requestConfig.elt` (Paso 28).
- Las etiquetas de `Appointment.Status` son `gettext_lazy`, sin migración (`makemigrations --check` limpio). `/api/schema/` sigue en inglés gracias a `EnglishApiMiddleware`; `manage.py spectacular` desde la consola no tiene request y describe los estados en español (`LANGUAGE_CODE`) (Paso 28).
- `seed_demo` crea los 6 doctores de `apps/doctors/demo.py` solo con `MEDBOOK_DEMO_DATA=true`, que `render.yaml` define para producción. Un doctor demo cuenta como existente si su email (sin importar mayúsculas) o su licencia ya están usados, y las filas existentes nunca se modifican. Así un doctor parecido creado en el admin no lo hace fallar, y en la DB de dev (los 6 del Paso 27 ya tienen `DEMO-001`…`DEMO-006`) no crea nada. `create_user()` sin contraseña guarda una inutilizable, sin escribir ninguna credencial. El horario sabatino de Felipe Araya en dev pasó en la demo a martes y jueves de 15:00 a 18:00, para quedar de lunes a viernes como pedía el #147 (Paso 33).
- `test_render_blueprint.py` ahora lee `render.yaml` con PyYAML en vez de buscar con regex en el texto, y verifica que `seed_demo` corra antes de `generate_slots` y en su subshell. PyYAML venía solo como dependencia de drf-spectacular; ahora está declarado en `requirements/local.txt` (Paso 33).
- Un merge que cambia `render.yaml` dispara dos deploys en Render: primero el auto-deploy con la configuración anterior y después el del Blueprint con la nueva. Para confirmar un cambio de `startCommand`, hay que mirar el log del segundo (Paso 33).
- La página 500 se renderiza sin contexto: no hay request, ni `user`, ni la variable `LANGUAGE_CODE` del context processor. `base.html` lee el idioma con `{% get_current_language %}` y `500.html` vacía el bloque `nav`. Con `DEBUG = True`, que es lo que usan `local.py` y `test.py`, Django muestra sus páginas de debug, así que `test_web_errors.py` pone `DEBUG = False` y sus tests de la 500 corren sin acceso a la DB (Paso 29).
- `{% translate %}` no escapa el texto del template: el apóstrofo de "don't" sale tal cual, no como `&#x27;`. Un test que esperaba el escape falló en el GREEN y se corrigió el test (Paso 29).
- `#messages` y `#live-status` se actualizan fuera de banda con `hx-swap-oob="innerHTML"`. Con `"true"` HTMX reemplazaba el nodo de la región viva, y muchos lectores de pantalla no anuncian una región recién insertada (Paso 29).
- Los links de semana, pestañas y paginación están dentro del contenido que reemplazan. En Chrome, el foco caía a `<body>` al usarlos con teclado (el siguiente Tab seguía desde el bloque nuevo, pero el lector de pantalla no tenía dónde quedarse). htmx 2 devuelve el foco al elemento con el mismo `id` en el contenido nuevo, así que esos links ahora tienen un `id` fijo (`week-next`, `tab-past`, `doctors-next`…). Si el link desaparece (la última semana o la última página), el foco vuelve a caer al body. Se detectó al revisar la web en Chrome (Paso 29).
- Las capturas de `docs/screenshots/` salen de la DB de dev con una paciente de prueba ficticia: 1088×735 en escritorio y 375×812 en móvil. La ventana de Chrome estaba maximizada y no se podía achicar, así que las de escritorio son un recorte del área del contenido y la de móvil, un iframe de 375 px del mismo origen. Ese iframe necesitó `X_FRAME_OPTIONS = "SAMEORIGIN"` en un settings temporal que no se versiona (Paso 29).
- El login ignora las mayúsculas del email desde el Paso 34. Las tres vías (web, admin y `/api/v1/token/`) pasan por `ModelBackend`, que llama a `UserManager.get_by_natural_key`; con `email__iexact` ahí se arreglan las tres. En Postgres `iexact` usa `UPPER()`, así que no aprovecha el índice de `Lower("email")`; a esta escala no importa, porque la restricción está por integridad. Antes de la migración no había duplicados posibles en producción: el registro y `seed_demo` revisan `email__iexact` desde que existen, y el admin no se había usado (Paso 34).
- `DUPLICATE_EMAIL_MESSAGE` pasó de `users/services.py` a `users/models.py`, porque la restricción lo usa como `violation_error_message`. Sin eso, el admin mostraría el mensaje genérico de Django, "Constraint “unique_user_email_ci” is violated.". `services` lo reexporta (Paso 34).
- `test_auth_api.py` no limpiaba la caché del throttle de login (5/minuto por IP). Con los tests nuevos superaba el límite y `test_token_refresh` recibía 429. Ahora tiene el mismo fixture `clear_throttle_cache` que `test_web_auth.py` (Paso 34).
- `test_returns_available_slots_for_doctor` fallaba los lunes después de las 16:30. `ScheduleFactory` es de lunes y la señal genera 7 días desde hoy, así que un lunes en la tarde todos sus slots ya habían empezado y la API los omite (Paso 30). `test_reserved_slots_are_excluded` tenía el mismo problema, pero lo ocultaba con un `if slot:`. Los dos usan ahora un horario del día de mañana (Paso 34).
- `can_be_cancelled()` ahora lee `self.slot`. La API y la web ya traen el slot en la misma consulta (`appointments_visible_to` hace `select_related("slot__schedule")`), así que el `can_cancel` de la lista no agrega consultas (Paso 35).
- El `InvalidTransition` de una cita que ya empezó dice "Cannot cancel an appointment that has already started.", en inglés como los demás mensajes del modelo. El issue pedía `gettext_lazy`, pero la API siempre responde en inglés y la web muestra su propio `CANNOT_CANCEL_MESSAGE` traducido, así que una traducción del modelo no la vería nadie (Paso 35).
- Las etiquetas de `Doctor.Title` usan el mismo msgid "Dr." con dos contextos de `pgettext_lazy` ("doctor title" y "female doctor title"): en español salen "Dr." y "Dra.", y en inglés las dos dicen "Dr.". Por eso el admin en inglés muestra "Dr." dos veces en el selector; el `help_text` del campo lo explica (Paso 36).
- La data migration `0006_demo_doctors_title` busca a las doctoras por licencia (`DEMO-001`, `DEMO-003`, `DEMO-005`) y no importa `demo.py`, porque una migración no debe depender de código que puede cambiar. `test_matches_the_demo_data` compara esas licencias con las de `demo.py` (Paso 36).

### Pendientes por decidir

- **Idioma de la API**: decidido, se mantiene en inglés (`EnglishApiMiddleware`, ADR 0002). La API la consumen desarrolladores y clientes, y todo su contrato (rutas, campos, estados, `code`, Swagger) está en inglés. Los mensajes que ve el paciente salen de la web, que los traduce (por ejemplo, el login web dice "Correo o contraseña incorrectos." y `/api/v1/token/` responde el mensaje en inglés de SimpleJWT). Si aparece un cliente en español, se evalúa respetar `Accept-Language` con inglés por defecto.
- **Email sensible a mayúsculas en el login**: `normalize_email` solo baja a minúsculas el dominio y el login busca el email exacto, así que quien se registró como `Ana@example.com` no entra con `ana@example.com` (ni en la API ni en la web). La unicidad sí es case-insensitive. Viene de antes del sprint. Decidido: no distinguir mayúsculas, se corrige en el Paso 34 (#151). **Resuelto en el Paso 34**: `get_by_natural_key` busca con `email__iexact` y la restricción `unique_user_email_ci` (sobre `Lower("email")`) impide dos cuentas con el mismo email.
- **Correo de confirmación en inglés y en UTC** (detectado en el Paso 27): `send_appointment_created` arma el texto en inglés y formatea la hora con `strftime("%Y-%m-%d %H:%M UTC")`, así que una hora de las 10:00 en Chile dice "13:00 UTC". Pasa lo mismo con los correos de confirmación y cancelación. Viene de antes de la web. Propuesta: correos en el idioma de la web (español por defecto) y con la hora de Chile. Va en el Paso 37 (#159).
- **Sesión expirada con el modal de reserva abierto** (detectado en el Paso 27): HTMX sigue el redirect al login y metería la página de login dentro del modal. Propuesta: que `RoleRequiredMixin` responda `HX-Redirect` al login cuando el request es HTMX. **Resuelto en el Paso 29**: un request HTMX anónimo recibe `HX-Redirect` a `/login/?next=<página donde estaba>`. La página sale de `HX-Current-URL`, y se ignora si es de otro origen.
- **Paciente sin perfil** (detectado en el Paso 27): un usuario con rol paciente creado desde el admin sin su `Patient` da 500 al reservar, en la web y en la API (`request.user.patient_profile`). El registro público siempre crea el perfil. Propuesta: crearlo también desde el admin, o responder un error claro. **Resuelto en el Paso 29**: `UserAdmin.save_model` llama a `ensure_patient_profile`, que crea el `Patient` cuando el usuario se agrega como paciente o pasa a ese rol.
- **"Dr." para todas las médicas** (detectado en el Paso 27): `Doctor.__str__` antepone "Dr." siempre, así que la web muestra "Dr. Carla Soto"; los correos hacen lo mismo. El modelo no guarda cómo tratar a cada médico. Propuesta: un campo de tratamiento (Dr./Dra.) traducible, o mostrar solo el nombre. Va en el Paso 36 (#158). Decidido: el campo `Doctor.title` (`dr`/`dra`, default `dr`), con una data migration para las doctoras demo que ya existían y sin exponerlo en la API. **Resuelto en el Paso 36**: la web en español muestra "Dra. Carla Soto" y en inglés "Dr. Carla Soto". Los correos siguen con "Dr." fijo hasta el Paso 37.
- **Cancelar una cita que ya pasó** (detectado en el Paso 28): `cancel_appointment` solo revisa el estado, así que la API (y la URL de cancelar de la web) dejan cancelar una cita `pending` o `confirmed` que ya ocurrió, y liberan un slot del pasado. La web oculta el botón en las citas que ya empezaron. Propuesta: que el paciente solo pueda cancelar antes de la hora, y el médico siempre. Va en el Paso 35 (#157). Decidido: nadie cancela una cita que ya empezó, ni el paciente ni el médico, que la cierra como completada o inasistencia. **Resuelto en el Paso 35**: `can_be_cancelled()` exige que el slot no haya empezado, así que la API responde 400 y la URL de la web muestra el mensaje, en el modal y sin JS.
- **Foco después de cancelar** (detectado en el Paso 28): al cerrarse el modal, el link que lo abrió ya no existe y el foco queda en `<body>`. El mensaje se anuncia (región `role="status"`), pero conviene mover el foco al estado de la cita. **Resuelto en el Paso 29**: el bloque de estado tiene `tabindex="-1"` y `dialog.js` le pasa el foco al cerrar el modal.
