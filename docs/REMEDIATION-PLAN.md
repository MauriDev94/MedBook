# MedBook — Plan de Remediación (post-auditoría)

> Deriva de `docs/AUDIT-production-readiness.md`.
> Decisiones tomadas: hacer **todos** los hallazgos, **seccionados** como los bloques, divididos si son extensos, en orden lógico con **quick-wins primero**.
> Diseño: **M1** → documentar · **O6** → agregar Dockerfile · **S3** (CORS explícito) → **NO** se aplica por decisión del owner (se mantiene `CORS_ALLOW_ALL_ORIGINS=True`, se documenta el bajo riesgo).
> Flujo: 1 issue (plantilla `tarea.md`) → branch → TDD → PR (`Closes #N`, plantilla PR) → review.
> Convención de branch propuesta: `audit/{dimensión}-{desc}`. Commits: `fix|refactor|feat|chore|test|docs(scope): …`.

---

## FASE 1 — Quick wins (alto impacto, esfuerzo bajo) ← EMPEZAR ACÁ

### Issue #1 — `fix(security): throttling global + proxy-aware + rotación de refresh`
Cubre **S1 + S2 + S4**.
- `DEFAULT_THROTTLE_CLASSES` = Anon + User; rates `anon`/`user`/`login`; throttle en `token/refresh/`.
- Resolución de IP real tras proxy de Render (`NUM_PROXIES` / `X-Forwarded-For`).
- `ROTATE_REFRESH_TOKENS = True` (activa el `BLACKLIST_AFTER_ROTATION` ya presente).
- Tests: extender `tests/integration/test_throttling.py`; test de rotación + token viejo blacklisteado.
- Branch: `audit/seguridad-hardening-fase1`

### Issue #2 — `fix(appointments): diferir emails con transaction.on_commit`
Cubre **A1**.
- `transaction.on_commit(...)` en `create_appointment` / `confirm` / `cancel`.
- Test: email NO se envía si la transacción hace rollback; SÍ tras commit.
- ⚠️ Hacer ANTES de cablear Resend (O5).
- Branch: `audit/arquitectura-email-oncommit`

### Issue #3 — `chore: limpiar código muerto + endurecer gate de coverage`
Cubre **B1 + T3 + T2**.
- Borrar `IsOwnerOrAdmin` y `ReadOnly` (`core/permissions.py`) + sus tests.
- Subir `--cov-fail-under` de 85 → 95 en `pytest.ini`.
- Branch: `audit/cleanup-coverage`

---

## FASE 2 — Impacto medio (esfuerzo medio)

### Issue #4 — `feat(observability): logging config + error tracking + audit trail`
Cubre **O1**. **Dividir si crece:**
- #4a — `LOGGING` dict explícito (handlers, formatters, niveles) + Sentry (`sentry-sdk[django]`).
- #4b — Audit log de transiciones de estado usando los `confirmed_by`/`cancelled_by` que ya viajan por los services (hoy se ignoran).
- Branch: `audit/observabilidad-logging`, `audit/observabilidad-audit`

### Issue #5 — `feat(api): versionado de URL /api/v1/`
Cubre **O2**.
- `URLPathVersioning`; mover rutas bajo `/api/v1/`; actualizar spectacular y URLs en tests.
- Branch: `audit/api-versioning`

### Issue #6 — `test(appointments): concurrencia real en reserva de slot`
Cubre **T1**.
- `TransactionTestCase` con threads: dos `create_appointment` concurrentes sobre el mismo slot → solo uno gana.
- Branch: `audit/testing-concurrency`

---

## FASE 3 — Refinamiento (esfuerzo bajo-medio, cosmético/calidad)

### Issue #7 — `refactor(notes): extraer autorización de notas a permission class`
Cubre **M2**. Uniformar estrategia RBAC (sacar el branching inline de `MedicalNoteViewSet._get_appointment`).
Branch: `audit/notes-permission-class`

### Issue #8 — `refactor(core): centralizar mapeo de ValueError en el exception handler`
Cubre **T4**. Una sola regla para todas las familias de error.
Branch: `audit/exceptions-valueerror`

### Issue #9 — `feat(api): 409 para conflicto de slot + devolver detail en create`
Cubre **O3 + O4**.
Branch: `audit/api-semantics`

### Issue #10 — `refactor(appointments): limpiezas menores`
Cubre **B2** (servicios pass-through) + **B3** (lógica en serializer create). Opcional.
Branch: `audit/minor-refactors`

### Issue #11 — `chore(security): endurecimiento menor`
Cubre **S5** (password validators) + **S6** (path admin) + **S7** (documentar claims JWT).
Branch: `audit/security-minor`

---

## FASE 4 — Decisiones de diseño + DevOps

### Issue #12 — `docs: documentar decisión de frontera de TimeSlot`
Cubre **M1**. Documentar por qué `TimeSlot` vive en `appointments` y el lazy import es intencional (refactor a `scheduling` descartado por over-engineering para este tamaño).
Branch: `audit/docs-timeslot-boundary`

### Issue #13 — `chore(devops): Dockerfile multi-stage non-root + slim`
Cubre **O6**. Dockerfile de app (además del deploy Render-native) para portabilidad y demostrar DevOps.
Branch: `audit/devops-dockerfile`

### Issue #14 — `chore(ci): mejoras del flujo de GitHub`
Codecov en PRs (quitar el `if: master`), `bug_report.md`, `CODEOWNERS`, `dependabot.yml`. Opcional.
Branch: `audit/ci-improvements`

---

## Fuera de alcance (por decisión / no requieren código)
- **S3** — CORS `allow-all` en prod: se mantiene (riesgo bajo por auth en header). Se documenta.
- **O5** — `EMAIL_BACKEND=console` en prod: se resuelve al cablear Resend; precondición = Issue #2 (A1) ya hecho.
- **O7** — Render plan free: nota de awareness, sin acción.

---

## Resumen de fases
| Fase | Issues | Hallazgos | Foco |
|------|--------|-----------|------|
| 1 | #1-#3 | S1,S2,S4,A1,B1,T2,T3 | Quick wins alto impacto |
| 2 | #4-#6 | O1,O2,T1 | Impacto medio |
| 3 | #7-#11 | M2,T4,O3,O4,B2,B3,S5,S6,S7 | Refinamiento |
| 4 | #12-#14 | M1,O6 + CI | Diseño + DevOps |
