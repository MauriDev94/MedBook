# Sprint — Semana 2: Core API

> **Objetivo:** Modelos de appointments, máquina de estados, permissions RBAC, ViewSets core, services layer y signal de generación de slots.
> Timeline estimado: 5–8 PRs.

---

## Estado

| Paso | Descripción | Issue | PR | Estado |
|------|-------------|-------|----|--------|
| — | CI/CD workflows + Docker Compose + secrets | #11 | #12 | ✅ |
| 0 | Deuda técnica (3 fixes menores) | #13 | — | ⏳ |
| 1 | Modelos de Appointments (TimeSlot, Appointment, MedicalNote) | #14 | — | ⬜ |
| 2 | Permissions RBAC (8 clases) | #15 | — | ⬜ |
| 3 | Tests de permissions (TDD: positivo + negativo por clase) | #16 | — | ⬜ |
| 4 | Services layer + tests | #17 | — | ⬜ |
| 5 | Signal post_save en Schedule + tests | #18 | — | ⬜ |
| 6 | Management command `generate_slots` + tests | #19 | — | ⬜ |
| 7 | ViewSets + Serializers | #20 | — | ⬜ |
| 8 | Tests de integración + TimeSlotFactory + AppointmentFactory | #21 | — | ⬜ |

---

## Checklist acumulativo — Semana 2

- [ ] `python manage.py migrate` corre sin errores
- [ ] Migraciones de appointments aplicadas
- [ ] `pytest tests/ -v` pasa al 100%
- [ ] Cobertura `apps/appointments/services.py` ≥ 90%
- [ ] Cobertura `apps/core/permissions.py` = 100%
- [ ] Cobertura `apps/appointments/models.py` ≥ 90%
- [ ] Flujo completo: POST /api/token/ → POST /api/appointments/ → POST /api/appointments/{id}/confirm/
- [ ] `python manage.py generate_slots` corre sin errores
- [ ] Signal genera slots al crear un Schedule
- [ ] GET /api/doctors/{id}/available-slots/ retorna slots disponibles
- [ ] Ningún ViewSet accede al ORM directamente (todo via services o queryset)
- [ ] Cobertura `apps/users/models.py` ≥ 85% (UserManager)

---

## Deuda técnica registrada

- [ ] `users/models.py` al 65% — UserManager sin cobertura (líneas 21-27, 31-40)
- [ ] `skip_postgeneration_save = True` en `UserFactory.Meta` y `DoctorFactory.Meta` (warning de FactoryBoy)
