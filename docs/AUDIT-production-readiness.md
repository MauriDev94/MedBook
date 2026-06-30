# MedBook — Auditoría de Production-Readiness

> Auditoría por arquitecto senior, 4 bloques (Arquitectura · Seguridad · Testing · Operación).
> Vara de medición: estándar Django/DRF (NO FastAPI/hexagonal puro).
> Metodología: lectura del código real, hallazgos citados con `archivo:línea`. No se modificó código.
> Persistido también en engram: `audit/arquitectura`, `audit/seguridad`, `audit/testing`, `audit/operacion`.

---

## Veredicto global

**MedBook es un proyecto sólido y production-ready en lo esencial.** La arquitectura respeta la separación de capas de Django de verdad, el control de acceso (RBAC) es genuino y multicapa, el testing es excelente y honesto (coverage real, no inflado), y el ORM está optimizado y hasta testeado contra N+1.

**No se encontró ningún hallazgo 🔴 Crítico.** Los gaps están en el **perímetro operacional** (rate limiting, observabilidad), no en el núcleo del dominio.

| Severidad | Cantidad |
|-----------|----------|
| 🔴 Crítico | 0 |
| 🟠 Alto | 3 |
| 🟡 Medio | 7 |
| 🔵 Bajo | 11 |

Las 3 dimensiones más fuertes: **Testing**, **Performance**, **RBAC/Control de acceso**.
La dimensión más débil: **Observabilidad**.

---

## Hallazgos 🟠 Alto (atacar primero)

### A1 — Side-effects (email) dentro de `@transaction.atomic`
- **Ubicación:** `apps/appointments/services.py:59-61` (y `confirm` :106, `cancel` :135)
- **Problema:** `send_appointment_*` se llama dentro de la transacción atómica con `fail_silently=False`. Si el backend de email falla, la reserva hace rollback.
- **Por qué importa:** acopla un side-effect NO crítico al éxito de una transacción crítica. El propio docstring (`notifications/services.py:11-17`) ya reconoce que debería usar `transaction.on_commit()`.
- **Recomendación:** `transaction.on_commit(lambda: send_appointment_created(appointment))`.
- **Esfuerzo:** Bajo (3 líneas). **Nota:** hoy está DORMIDO en prod (EMAIL_BACKEND=console nunca lanza) — pero arreglar ANTES de cablear Resend.

### S1 — Rate limiting casi ausente
- **Ubicación:** `config/settings/base.py:149-153`
- **Problema:** solo el login tiene throttle. No hay `DEFAULT_THROTTLE_CLASSES` global → `token/refresh/`, `token/blacklist/` y TODO el CRUD quedan sin límite.
- **Por qué importa:** abuso de recursos / scraping / DoS. OWASP API4:2023 (Unrestricted Resource Consumption).
- **Recomendación:** `DEFAULT_THROTTLE_CLASSES` con `AnonRateThrottle` + `UserRateThrottle` y rates `anon`/`user`; throttle propio en refresh.
- **Esfuerzo:** Bajo (settings).

### O1 — Sin estrategia de observabilidad
- **Ubicación:** todo `config/settings/` (no existe dict `LOGGING`); único logger en `apps/doctors/signals.py:15`
- **Problema:** sin `LOGGING` config, sin niveles, sin request logging, sin error tracking (Sentry), sin audit trail de transiciones clínicas (quién confirmó/canceló).
- **Por qué importa:** en una API médica, la trazabilidad clínica no es lujo. Render captura stdout (no es cero observabilidad) pero no hay estrategia.
- **Recomendación:** dict `LOGGING` explícito + Sentry + audit log de transiciones (los ganchos `confirmed_by`/`cancelled_by` ya viajan por los services `services.py:89,113` — solo falta usarlos, hoy se ignoran).
- **Esfuerzo:** Medio.

---

## Hallazgos 🟡 Medio

### S2 — El throttle de login probablemente NO funciona tras el proxy de Render
- **Ubicación:** `apps/core/throttling.py:10` + `config/settings/production.py:31`
- **Problema:** `AnonRateThrottle` limita por IP vía `REMOTE_ADDR`, pero detrás del proxy de Render sin `NUM_PROXIES` configurado, esa IP es la del proxy. O todos comparten bucket (auto-DoS) o no ve la IP real del atacante.
- **Recomendación:** configurar resolución de IP real (`NUM_PROXIES` / parseo confiable de `X-Forwarded-For`). **Se resuelve junto con S1.**

### S3 — `CORS_ALLOW_ALL_ORIGINS = True` en producción
- **Ubicación:** `config/settings/production.py:64`
- **Problema:** producción permite cualquier origen. **Mitigado:** auth es JWT en header (no cookies) → explotabilidad BAJA.
- **Recomendación:** `CORS_ALLOWED_ORIGINS` explícito, o documentar por qué acá el riesgo es bajo.

### S4 — Refresh tokens sin rotación
- **Ubicación:** `config/settings/base.py:161-162`
- **Problema:** `ROTATE_REFRESH_TOKENS=False` → refresh de 1 día reusable; `BLACKLIST_AFTER_ROTATION=True` queda como config muerta.
- **Recomendación:** `ROTATE_REFRESH_TOKENS=True`. **Esfuerzo:** Bajo (1 línea).

### M1 — Acoplamiento bidireccional `doctors` ↔ `appointments` (TimeSlot)
- **Ubicación:** `doctors/services.py:7`, `doctors/views.py:15`, `doctors/signals.py:35`, `appointments/management/commands/generate_slots.py:15`
- **Problema:** `TimeSlot` (concepto de scheduling) vive en `appointments` pero su ciclo lo maneja `doctors.Schedule`. Ciclo latente mitigado con lazy import.
- **Recomendación:** o bounded context `scheduling` (probablemente over-engineering para este tamaño), o **documentar** la decisión y por qué el lazy import es intencional.

### M2 — Autorización inline en notas médicas (inconsistente)
- **Ubicación:** `apps/appointments/views.py:186-198`
- **Problema:** todo el RBAC usa permission classes EXCEPTO `MedicalNoteViewSet._get_appointment()` que hace branching por rol inline.
- **Recomendación:** extraer a una permission class para uniformar la estrategia.

### T1 — Race condition no testeado bajo concurrencia real
- **Ubicación:** `tests/unit/test_services.py:403`
- **Problema:** se testea el guard de forma secuencial (slot RESERVED → create raises), no dos transacciones concurrentes. Grep confirma: cero `Thread`/`TransactionTestCase`/`select_for_update` en la suite.
- **Por qué importa:** el código es correcto (UPDATE atómico), pero el test da falsa sensación de "concurrencia testeada" y se lista como feature.
- **Recomendación:** `TransactionTestCase` con threads, o documentar que el test secuencial es proxy y la garantía real es el UPDATE atómico a nivel DB.

### T2 — Gate de coverage flojo vs real
- **Ubicación:** `pytest.ini:12`
- **Problema:** `--cov-fail-under=85` pero el real es 98.7% → 13.7 pts sin proteger.
- **Recomendación:** subir gate a ~95 para que el número exhibido sea garantía, no foto. **Esfuerzo:** Bajo (1 línea).

### O2 — Sin versionado de API
- **Ubicación:** `config/urls.py` (solo `"VERSION":"1.0.0"` en spectacular, que es metadata de doc)
- **Problema:** rutas sin `/api/v1/` ni `DEFAULT_VERSIONING_CLASS` → breaking changes pegan a todos los clientes.
- **Recomendación:** `URLPathVersioning` con prefijo `/api/v1/`.

---

## Hallazgos 🔵 Bajo

| ID | Hallazgo | Ubicación |
|----|----------|-----------|
| B1 | Permission classes muertas (`IsOwnerOrAdmin`, `ReadOnly`) — YAGNI | `core/permissions.py:55,101` |
| B2 | Servicios pass-through sin lógica (`complete`/`mark_no_show`) | `appointments/services.py:142,156` |
| B3 | Pizca de lógica en serializer `create()` (infiere doctor, lee request.user) | `appointments/serializers.py:51-63` |
| S5 | Password validators mínimos (sin `UserAttributeSimilarity`) — superficie baja, sin registro público | `base.py:108-112` |
| S6 | `/admin/` expuesto en path estándar | `config/urls.py:31` |
| S7 | JWT claims llevan email/full_name (base64-legible, info no sensible) | `users/serializers.py:13-16` |
| T3 | Tests de código muerto (cubren las permission classes no usadas) | `tests/unit/test_permissions.py:127,224` |
| T4 | Mapeo de errores partido: `ValidationError` central pero `ValueError` por decorator | `core/exceptions.py:30` + `views.py:37` |
| O3 | Status codes: conflicto de slot devuelve 400, no 409; falta 409/422 | `appointments/` |
| O4 | POST create devuelve solo `{slot,reason}`, no el appointment completo | `appointments/serializers.py:38-40` |
| O5 | `EMAIL_BACKEND=console` en prod → notificaciones no se envían (+ A1 dormido) | `render.yaml` |
| O6 | Sin Dockerfile (deploy Render-native) — gap de portabilidad/portfolio | `render.yaml` |
| O7 | Render plan free: cold start, Postgres efímero | `render.yaml` |

---

## Lo que está MUY bien (no tocar)

- **RBAC genuino:** permisos leen `request.user.role` de la DB (no del token), `get_queryset()` filtra por rol (defense-in-depth que mata IDOR), notas médicas blindadas (pacientes bloqueados, doctores acotados a sus citas).
- **Mass-assignment cerrado:** serializers exponen solo campos seguros → escalada de privilegios estructuralmente imposible.
- **Testing honesto:** coverage real (branch=true, excludes honestos), permisos 100% (positivo+negativo), máquina de estados con transiciones válidas E inválidas, exception handler exhaustivo, factories que hashean passwords, test honesto de N+1 con `CaptureQueriesContext`.
- **Performance:** `select_related`/`prefetch_related` en todos los listados, índices en campos filtrados/ordenados, paginación global, `@transaction.atomic` + UPDATE atómico anti doble-booking.
- **Seguridad de config:** secretos en env (SECRET_KEY sin default), headers de prod completos (HSTS, SSL redirect, secure cookies), DEBUG=False forzado, ALLOWED_HOSTS obligatorio.
- **CI/CD robusto:** ruff + tests + gate de coverage + migration check + Codecov + PostgreSQL service. Settings separados por entorno con herencia limpia.

---

## Plan de remediación priorizado (impacto × esfuerzo)

### Fase 1 — Quick wins de alto impacto (esfuerzo bajo, 1 PR)
1. **A1** — `transaction.on_commit()` para emails
2. **S1 + S2** — `DEFAULT_THROTTLE_CLASSES` global + resolución de IP tras proxy
3. **S4** — `ROTATE_REFRESH_TOKENS=True`
4. **T2** — subir `--cov-fail-under` a ~95
5. **B1** — borrar permission classes muertas (+ sus tests T3)

### Fase 2 — Impacto alto, esfuerzo medio
6. **O1** — `LOGGING` config + Sentry + audit log de transiciones
7. **O2** — versionado `/api/v1/`
8. **T1** — test de concurrencia real (o documentar el proxy)

### Fase 3 — Refinamiento
9. **M2** — permission class para notas médicas
10. **S3** — CORS explícito en prod
11. **T4** — centralizar mapeo de `ValueError`
12. **O3 / O4** — 409 para conflicto + devolver detail en create
13. **M1** — documentar/refactorizar frontera de `TimeSlot`

> Nota de orden: arreglar **A1 antes de cablear Resend** (O5), porque hoy el riesgo de rollback está dormido por el backend console.
