# MedBook — Project Instructions

> API REST de reservas médicas. Portfolio project para demostrar dominio de Django + DRF.
> PRD.md es la fuente de verdad para features y scope.
> AGENT.md contiene el mismo contenido — este archivo tiene prioridad para Claude Code.

---

## Setup de entorno (Windows PowerShell)

```powershell
.venv\Scripts\activate
$env:DJANGO_SETTINGS_MODULE='config.settings.local'
```

> CRÍTICO: Nunca usar `Start-Process` para levantar Django. Siempre `python manage.py runserver` en terminal dedicada con env vars ya seteadas.

---

## Setup inicial (una sola vez por clon)

```bash
pip install -r requirements/local.txt
pre-commit install   # instala el hook — ruff corre automático en cada commit
```

## Comandos esenciales

```bash
# Lint — correr antes de cada commit (pre-commit lo hace automático)
ruff check . && ruff format --check .

# Tests — siempre contra PostgreSQL (igual que CI)
pytest                                        # suite completa
pytest tests/unit/
pytest tests/integration/
pytest --cov=apps --cov-report=term-missing
pytest -x                                     # detener al primer fallo

# Migraciones
python manage.py makemigrations
python manage.py migrate
python manage.py showmigrations

# Management commands del proyecto
python manage.py generate_slots
python manage.py generate_slots --days=30
python manage.py generate_slots --doctor-id=<uuid>
```

---

## Skills (Auto-load based on context)

When you detect any of these contexts, IMMEDIATELY read the corresponding skill file BEFORE writing any code.

| Context | Read this file |
| ------- | -------------- |
| Django models, serializers, viewsets, permissions, DRF APIs, signals | `.agent/skills/django-drf-patterns/SKILL.md` |
| Python tests, pytest-django, TDD, factory_boy, mocking, coverage | `.agent/skills/django-tdd/SKILL.md` |
| CI/CD, GitHub Actions, migrations in CI, linting, Docker | `.agent/skills/django-cicd/SKILL.md` |

Read skills BEFORE writing code. Apply ALL patterns. Multiple skills can apply simultaneously.

---

## Arquitectura — reglas NO negociables

### Separación de capas

| Capa | Responsabilidad | Lo que NO va aquí |
|---|---|---|
| `models.py` | Campos, relaciones, transiciones de estado simples | Lógica de negocio compleja |
| `serializers.py` | Validación de input, formato de output | Queries ORM directas, lógica de negocio |
| `views.py` | HTTP: auth, permisos, serialización, status codes | ORM directo, reglas de negocio |
| `services.py` | Toda la lógica de negocio | Nada de HTTP, nada de serializers |
| `permissions.py` | Un solo chequeo por clase | Lógica de negocio |

### Regla de 15 líneas

Si un método `validate_*`, acción de ViewSet, o método de modelo supera ~15 líneas → extraer a `services.py`. Sin excepciones.

### SOLID adaptado a Django

- **SRP:** Un serializer por acción cuando la lógica diverge (`AppointmentCreateSerializer`, `AppointmentListSerializer`, etc.)
- **OCP:** Extender `BasePermission`, `ModelViewSet` — nunca modificar DRF internals
- **DIP:** ViewSets llaman service functions, no ORM directamente
- **ISP:** ViewSets enfocados — sin acciones no relacionadas al dominio

---

## TDD — metodología obligatoria

**Red → Green → Refactor. Sin excepciones.**

Antes de escribir cualquier implementación, escribir el test que falla primero.

```
tests/
├── unit/
│   ├── test_models.py      # sin HTTP, sin DB donde sea posible
│   └── test_services.py    # con DB (@pytest.mark.django_db), sin HTTP
└── integration/
    ├── test_auth_api.py
    ├── test_appointments_api.py
    ├── test_doctors_api.py
    └── test_permissions.py  # positivo Y negativo para cada clase
```

**Cobertura mínima:**
- Models + services: 90%
- ViewSets + serializers: 80%
- Permissions: 100% (test positivo + negativo por cada clase)
- Management commands: 70%

**Factories:** todo via `factory_boy`. Cero fixtures JSON/YAML.

---

## Patrones de código obligatorios

### ViewSet con múltiples serializers

```python
def get_serializer_class(self):
    if self.action == 'create':
        return AppointmentCreateSerializer
    if self.action in ['update', 'partial_update']:
        return AppointmentUpdateSerializer
    if self.action == 'list':
        return AppointmentListSerializer
    return AppointmentDetailSerializer
```

### ORM — patrones requeridos

- `select_related` en todos los `get_queryset()` con FK
- `prefetch_related` para M2M (Doctor → specialties)
- `annotate()` + `Count()` para estadísticas
- `Q()` para filtros de conflicto de horario
- `bulk_create(ignore_conflicts=True)` en generación de slots
- `update_fields=['status', 'updated_at']` en todos los `.save()` parciales

### Máquina de estados — Appointment

```
pending ──► confirmed ──► completed
  │              │
  └──────────► cancelled    no_show (desde confirmed)
```

Transiciones como métodos en el modelo: `can_be_confirmed()`, `confirm()`, `cancel()`, `complete()`, `mark_no_show()`.

---

## Checkpoints — pausar y reportar antes de continuar

Detenerse, mostrar output completo y esperar confirmación explícita antes de avanzar en estos casos:

**Siempre pausar después de:**
- Cualquier `makemigrations` — mostrar el archivo de migración generado
- Cualquier `migrate` — mostrar output completo
- Correr la suite de tests — mostrar resultado con conteo y coverage
- Completar cada PASO numerado del sprint activo

**Siempre pausar y reportar (sin intentar fix automático) cuando:**
- Un comando falla con error — mostrar traceback completo, no intentar solucionar solo
- Un test falla inesperadamente — mostrar el diff, preguntar antes de cambiar implementación
- Una decisión de arquitectura no está cubierta por el PRD o este archivo — preguntar

---

## Qué NO hacer

- ❌ ORM directo en views o serializers
- ❌ Lógica de negocio en ViewSet actions (más de 15 líneas → services)
- ❌ `request.user` dentro de `validate()` en serializers — pasar por `context`
- ❌ Loops Python para filtrar querysets — usar ORM `.filter()`, `annotate()`
- ❌ `except Exception` genérico — capturar excepciones específicas
- ❌ JWT tokens almacenados en modelos — usar simplejwt blacklist
- ❌ SQLite en desarrollo o tests oficiales — PostgreSQL siempre
- ❌ Fixtures JSON/YAML — solo factory_boy
- ❌ Escribir implementación antes del test
- ❌ `Start-Process` para levantar Django en Windows
- ❌ Iterar silenciosamente ante errores — siempre reportar y pausar

---

## Flujo de trabajo por sesión

### Al inicio
1. Leer PRD.md para contexto de features
2. Crear un issue en GitHub por cada PASO numerado del sprint
3. Branch: `semana{N}/paso-{N}-{descripcion}`

### Durante el desarrollo
4. Un paso a la vez en su branch
5. Respetar checkpoints
6. TDD estricto: test primero

### Al terminar cada paso
7. Commit: `feat|fix|refactor(scope): descripción`
8. PR que referencia el issue: "Closes #N"
9. Esperar review antes de mergear
