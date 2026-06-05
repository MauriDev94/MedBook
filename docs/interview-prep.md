# MedBook — Guía de Preparación para Entrevistas

> Material de estudio interactivo. Cada pregunta tiene una respuesta colapsable.  
> Haz click en ▶ para revelar la respuesta.
>
> **Niveles:** 🟢 Junior · 🟡 Mid · 🔴 Senior

---

## Índice

1. [Dominio y Arquitectura General](#1-dominio-y-arquitectura-general)
2. [Django Internals](#2-django-internals)
3. [Django REST Framework](#3-django-rest-framework)
4. [Principios SOLID y Clean Code](#4-principios-solid-y-clean-code)
5. [TDD y Testing](#5-tdd-y-testing)
6. [Seguridad](#6-seguridad)
7. [Performance y ORM](#7-performance-y-orm)
8. [Producción y CI/CD](#8-producción-y-cicd)
9. [Preguntas de diseño abierto](#9-preguntas-de-diseño-abierto)

---

## 1. Dominio y Arquitectura General

<details>
<summary>🟢 ¿Qué hace MedBook? Describí el dominio en 3 oraciones.</summary>

MedBook es una API REST para reservas médicas. Los médicos publican horarios semanales y el sistema genera slots concretos de tiempo. Los pacientes reservan esos slots, y las citas avanzan por una máquina de estados: `pending → confirmed → completed / cancelled / no_show`.

</details>

---

<details>
<summary>🟢 ¿Cuáles son los modelos principales y cómo se relacionan?</summary>

```
User (AbstractBaseUser — email como username, campo role)
 ├── Doctor ──── Specialty (M2M)
 │        └──── Schedule (disponibilidad semanal por día)
 │                   └──── TimeSlot (slots concretos generados)
 └── Patient
           └──── Appointment ──── TimeSlot (OneToOne — un slot = una cita)
                      └──── MedicalNote
```

Relaciones clave:
- `TimeSlot` tiene FK a `Schedule` (de qué horario viene)
- `Appointment` tiene FK a `Patient`, `Doctor`, y OneToOne a `TimeSlot`
- `Doctor.specialties` es M2M con `Specialty`

</details>

---

<details>
<summary>🟡 ¿Por qué hay una capa de services.py? ¿No es suficiente con los ViewSets?</summary>

La capa de servicios existe para separar **lógica de negocio** (reglas del dominio) de **lógica HTTP** (status codes, serialización, permisos).

Sin services:
- La lógica queda acoplada a HTTP — no podés testear `confirm_appointment()` sin levantar un servidor
- No podés reutilizarla desde un management command, una tarea Celery, o el admin de Django
- El ViewSet se vuelve un lugar donde mezclar todo

Con services:
```python
# ViewSet — solo HTTP
@action(detail=True, methods=["post"])
def confirm(self, request, pk=None):
    appointment = self.get_object()
    try:
        services.confirm_appointment(appointment)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(AppointmentDetailSerializer(appointment).data)

# Service — solo lógica, Python puro
@transaction.atomic
def confirm_appointment(appointment):
    appointment.confirm()          # state machine en el modelo
    send_appointment_confirmed(appointment)  # notificación
    return appointment
```

La **regla de las 15 líneas**: si un método en views/serializers supera ~15 líneas, se extrae a services.

</details>

---

<details>
<summary>🔴 ¿Cómo funciona la máquina de estados? ¿Por qué está en el modelo y no en el service?</summary>

La máquina de estados está en el modelo porque es un **invariante del dato** — el modelo es el responsable de garantizar la consistencia de su propio estado.

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

Transiciones válidas:
```
pending ──► confirmed ──► completed
  │              │
  └──────────► cancelled    no_show (desde confirmed)
```

**¿Por qué NO en el service?** Si la validación estuviera solo en el service, alguien podría llamar `appointment.save()` directamente y saltarse la máquina de estados. En el modelo es imposible olvidar.

**¿Por qué existe el service entonces?** Para dos cosas que el modelo no debería hacer:
1. `@transaction.atomic` — garantiza que el estado y la notificación son atómicos
2. Llamar a `send_appointment_confirmed()` — el modelo no debería saber de emails

</details>

---

## 2. Django Internals

<details>
<summary>🟢 ¿Por qué usar AbstractBaseUser en vez del User de Django por defecto?</summary>

Django's `AbstractUser` incluye `username`, `groups`, `permissions` M2M, y más campos que no necesitamos. Usamos email como identificador — no username.

`AbstractBaseUser` da un **slate limpio**: definís exactamente los campos que necesitás.

```python
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = "email"   # email es el identificador de login
```

**Regla crítica:** el modelo User custom debe definirse antes del primer `migrate`. Cambiarlo después requiere resetear migrations — muy doloroso.

</details>

---

<details>
<summary>🟡 ¿Cómo funcionan los signals en MedBook? ¿Cuándo los usarías y cuándo no?</summary>

**Usamos signals para:** generación automática de slots cuando se crea un Schedule.

```python
@receiver(post_save, sender=Schedule)
def generate_initial_slots(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        generate_slots_for_schedule(instance, days_ahead=7)
    except Exception:
        logger.exception("Failed to generate slots for schedule %s", instance.id)
```

**¿Por qué signal acá?** La generación de slots es un *side effect* de crear un Schedule. El Schedule no debería saber nada de slots — es una separación de responsabilidades. El signal conecta los dos sin acoplarlos.

El `try/except` es **intencional**: nunca queremos que la generación de slots rompa el save del Schedule. El Schedule es la operación primaria; los slots son secundarios. En `DEBUG=True`, el error se re-lanza para no enmascarar bugs en desarrollo.

**¿Cuándo NO usarías signals?**
- Notificaciones de email por cambio de estado de cita → **No**. Los signals se disparan en EVERY save, son invisibles al grep, y difíciles de testear. Preferimos llamadas explícitas en el service.
- Lógica de negocio crítica → **No**. Nunca. Los signals son para side effects no críticos.

</details>

---

<details>
<summary>🟡 ¿Qué es el problema de las migraciones con PostgreSQL vs SQLite?</summary>

SQLite tiene diferencias silenciosas con PostgreSQL que ocultan bugs reales:

| Comportamiento | SQLite | PostgreSQL |
|---|---|---|
| `unique_together` en transacciones | No siempre enforced | Siempre enforced |
| Precisión de datetime | Microsegundos truncados | Completa |
| UPDATE atómico con WHERE | Sin garantía de locking | SELECT FOR UPDATE / UPDATE atómico |
| `RETURNING` clause | No soportado | Soportado |
| Concurrent write locking | Bloquea toda la DB | Row-level locking |

El race condition de `create_appointment()` (UPDATE atómico para reservar slots) **solo funciona correctamente con PostgreSQL**. Con SQLite, dos threads podrían pasar el UPDATE simultáneamente.

Por eso: **PostgreSQL desde el día 1, en dev, test y producción**.

</details>

---

<details>
<summary>🔴 ¿Qué hace exactamente el custom exception handler y por qué existe?</summary>

DRF tiene un formato de error inconsistente por defecto:
```json
// 404
{"detail": "Not found."}

// 400 campo inválido
{"email": ["This field is required."]}

// 400 error no-campo
{"non_field_errors": ["..."]}
```

Un frontend tiene que manejar 3 formas diferentes. El handler centralizado normaliza todo:

```json
{"detail": "...", "code": "...", "field_errors": {...}}
```

**El bug no obvio que resuelve:** `django.core.exceptions.ValidationError` (no la de DRF) lanzada dentro de `serializer.create()` **no es capturada por DRF** — su `exception_handler` retorna `None` → Django responde 500.

Esto pasa en el race condition de slots: el UPDATE atómico falla, lanzamos `DjangoValidationError`, y sin el handler personalizado → 500 en producción.

```python
def custom_exception_handler(exc, context):
    # Interceptar ANTES de DRF — convierte DjangoValidationError → 400
    if isinstance(exc, DjangoValidationError):
        return Response(
            {"detail": exc.messages[0], "code": "validation_error"},
            status=400,
        )
    response = exception_handler(exc, context)  # handler de DRF
    # ... normalizar el resto
```

</details>

---

## 3. Django REST Framework

<details>
<summary>🟢 ¿Cuál es la diferencia entre un ViewSet y una APIView?</summary>

`APIView` es el nivel más bajo: definís exactamente qué hace cada método HTTP.

```python
class AppointmentView(APIView):
    def get(self, request): ...
    def post(self, request): ...
    def patch(self, request, pk): ...
```

`ViewSet` es más abstracto: define acciones (`list`, `create`, `retrieve`, `update`, `destroy`) que el Router mapea automáticamente a URLs.

```python
class AppointmentViewSet(ModelViewSet):
    # Router genera:
    # GET /appointments/        → list()
    # POST /appointments/       → create()
    # GET /appointments/{id}/   → retrieve()
    # PATCH /appointments/{id}/ → partial_update()
    # DELETE /appointments/{id}/→ destroy()
```

`ModelViewSet` agrega acciones custom con `@action`:
```python
@action(detail=True, methods=["post"])
def confirm(self, request, pk=None): ...
# → POST /appointments/{id}/confirm/
```

Cuándo usar cada uno:
- `ModelViewSet` → CRUD estándar (Schedule, Appointment)
- `GenericViewSet` → subset de CRUD (UserViewSet solo tiene `/me/`)
- `APIView` → endpoints muy específicos fuera del patrón REST

</details>

---

<details>
<summary>🟡 ¿Cómo funciona get_serializer_class() y cuándo usarías múltiples serializers?</summary>

Cuando request y response tienen shapes diferentes, necesitás serializers distintos:

```python
def get_serializer_class(self):
    if self.action == "create":
        return AppointmentCreateSerializer   # solo slot + reason como input
    if self.action == "list":
        return AppointmentListSerializer     # datos resumidos, sin notas
    return AppointmentDetailSerializer       # datos completos con slot expandido
```

**¿Por qué no uno solo?** Si el mismo serializer maneja create y read:
- Los campos read-only (id, created_at, status) aparecen en el Swagger de request → confunde al consumidor
- Tenés que poner `read_only=True` en la mitad de los campos → frágil
- `drf-spectacular` genera schemas incorrectos si no separás request/response

**Regla SRP (Single Responsibility):** un serializer por acción cuando la lógica de validación o el shape divergen.

</details>

---

<details>
<summary>🟡 ¿Cómo funciona el sistema de permisos en MedBook? ¿Cuál es la diferencia entre permisos de rol y permisos de objeto?</summary>

**Permisos de rol** — verifican el tipo de usuario:
```python
class IsDoctor(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.user.role == Role.DOCTOR
```
Se usa para: crear schedules (solo doctores), crear citas (solo pacientes), eliminar citas (solo admin).

**Permisos de objeto** — verifican si el usuario es dueño del objeto específico:
```python
class IsDoctorOfAppointment(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        return obj.doctor == request.user.doctor_profile
```
Se usa para: confirmar, completar, marcar no-show (el médico de ESA cita), cancelar (el paciente O médico de ESA cita).

**Composición con `|`:**
```python
# cancel → paciente O médico de la cita específica
[IsAuthenticated(), IsPatientOfAppointment() | IsDoctorOfAppointment()]
```

**¿Por qué object-level y no solo filtrar el queryset?** El queryset filtra qué objetos VES. El permiso de objeto controla qué PODÉS HACER con ellos. Sin el permiso de objeto, cualquier médico podría confirmar citas de otro médico si conoce el UUID.

</details>

---

<details>
<summary>🔴 ¿Por qué AnonRateThrottle en el login y no UserRateThrottle?</summary>

`UserRateThrottle` trackea por usuario autenticado. El endpoint de login es accedido **sin autenticación** — el usuario no tiene token todavía. No hay forma de trackear "por usuario" a alguien que está intentando autenticarse.

`AnonRateThrottle` trackea por **dirección IP** — la dimensión correcta para brute-force. Si alguien prueba 1000 passwords del mismo IP, los limita.

```python
class LoginRateThrottle(AnonRateThrottle):
    scope = "login"   # → DEFAULT_THROTTLE_RATES["login"] = "5/minute"
```

**¿Por qué no throttle global?** Un throttle global `UserRateThrottle` en todos los endpoints:
1. Bloquea scripts legítimos de admins
2. Rompe pipelines de CI/CD que hacen muchos requests
3. Genera falsos positivos para usuarios que navegan rápido

El único endpoint donde el brute-force es un riesgo real es el login. El resto ya requiere JWT válido — si tu token es inválido, el 401 sale antes de tocar la DB.

</details>

---

## 4. Principios SOLID y Clean Code

<details>
<summary>🟢 ¿Cómo aplica SRP (Single Responsibility) en este proyecto?</summary>

**SRP = cada módulo/clase tiene una sola razón para cambiar.**

En MedBook:

| Módulo | Una sola razón para cambiar |
|---|---|
| `models.py` | Cambiar la estructura de datos o las reglas de transición de estado |
| `serializers.py` | Cambiar el formato de input/output de la API |
| `views.py` | Cambiar cómo se manejan los requests HTTP |
| `services.py` | Cambiar las reglas de negocio |
| `permissions.py` | Cambiar quién puede hacer qué |

**En la práctica — múltiples serializers:**
`AppointmentCreateSerializer` cambia cuando cambia el input de creación. `AppointmentListSerializer` cambia cuando cambia cómo listamos. Si fueran uno solo, tendría DOS razones para cambiar → violación de SRP.

</details>

---

<details>
<summary>🟡 ¿Cómo aplica DIP (Dependency Inversion) en los ViewSets?</summary>

DIP dice: los módulos de alto nivel no deberían depender de módulos de bajo nivel. Ambos deberían depender de abstracciones.

**Sin DIP (acoplado):**
```python
@action(detail=True, methods=["post"])
def confirm(self, request, pk=None):
    appointment = self.get_object()
    # ViewSet depende directamente del ORM (detalle de implementación)
    if appointment.status != "pending":
        return Response({"error": "..."}, status=400)
    appointment.status = "confirmed"
    appointment.save()
    # ... lógica mezclada con HTTP
```

**Con DIP:**
```python
@action(detail=True, methods=["post"])
def confirm(self, request, pk=None):
    appointment = self.get_object()
    try:
        # ViewSet depende de una función de servicio (abstracción)
        services.confirm_appointment(appointment)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(AppointmentDetailSerializer(appointment).data)
```

El ViewSet no sabe si `confirm_appointment` usa el ORM, llama a una API externa, o escribe en un archivo. Solo sabe el contrato: recibe un appointment, lanza `ValueError` si hay problema.

**Beneficio concreto:** podés testear `confirm_appointment()` sin HTTP. Y podés testear el ViewSet mockeando el service.

</details>

---

<details>
<summary>🟡 ¿Dónde está la violación de DRY que corregimos y cómo la detectaste?</summary>

`UserSerializer` y `UserUpdateSerializer` eran byte-por-byte idénticos: mismos `fields`, mismos `read_only_fields`, mismo método `get_full_name`.

```python
# ❌ ANTES — copy-paste puro
class UserUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ["id", "email", "role", "full_name", "first_name", "last_name", "created_at"]
        read_only_fields = ["id", "email", "role", "created_at"]
    def get_full_name(self, obj): return obj.full_name
```

El "Update" no restringía nada más que el de lectura. Si alguien modificaba `UserSerializer`, tenía que acordarse de modificar `UserUpdateSerializer` también — la definición de DRY roto.

```python
# ✅ DESPUÉS — propósito real
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]   # lo único editable
```

Y el PATCH responde con el serializer de lectura completo:
```python
serializer.save()
return Response(UserSerializer(request.user).data)  # perfil completo
```

</details>

---

<details>
<summary>🔴 ¿Cómo aplicaste OCP (Open/Closed) con el sistema de permisos?</summary>

OCP dice: abierto para extensión, cerrado para modificación.

**Bien aplicado:** cada permiso nuevo es una clase nueva que extiende `BasePermission`. Nunca modificamos las clases existentes para agregar casos.

```python
# Agregar un nuevo permiso = nueva clase, cero cambios en existentes
class IsNurseOfAppointment(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        return obj.assigned_nurse == request.user.nurse_profile
```

**Composición en vez de condicionales:**
```python
# ❌ Cerrado — hay que modificar la clase para cada caso nuevo
class IsOwnerPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if view.action == "cancel":
            return obj.patient.user == request.user or obj.doctor.user == request.user
        elif view.action == "confirm":
            return obj.doctor.user == request.user
        # ... más casos

# ✅ Abierto — composición con |
get_permissions():
    if self.action == "confirm":
        return [IsDoctorOfAppointment()]
    if self.action == "cancel":
        return [IsPatientOfAppointment() | IsDoctorOfAppointment()]
```

DRF soporta el operador `|` porque `BasePermission.__or__` está implementado.

</details>

---

## 5. TDD y Testing

<details>
<summary>🟢 ¿Qué es TDD y cómo lo aplicaste en este proyecto?</summary>

TDD = Test-Driven Development. El flujo es **RED → GREEN → REFACTOR**:

1. **RED** — escribir un test que falle (el feature no existe todavía)
2. **GREEN** — escribir el mínimo código para hacer pasar el test
3. **REFACTOR** — limpiar el código sin romper los tests

Ejemplo aplicado al fix del race condition (H1):

```python
# RED — test que falla porque da 500 en vez de 400
def test_returns_400_when_slot_taken_by_race(self, patient_client, slot):
    with patch("apps.appointments.services.TimeSlot.objects.filter") as mock_filter:
        mock_filter.return_value.update.return_value = 0  # simula race perdido
        response = patient_client.post(self.url, {"slot": str(slot.id)})
    assert response.status_code == 400  # FALLA → da 500

# GREEN — extender custom_exception_handler para capturar DjangoValidationError
# REFACTOR — asegurar que el shape de error es consistente
```

**¿Por qué primero el test?** Porque un test escrito DESPUÉS del código tiende a testear la implementación existente, no el comportamiento esperado. El test escrito primero define el contrato.

</details>

---

<details>
<summary>🟡 ¿Cuándo usás mocks y cuándo no? ¿Cuál es la regla?</summary>

**Regla: mock solo lo que es irreproducible o impráctica de provocar en un test real.**

| Situación | Técnica |
|---|---|
| Race condition (2 threads simultáneos) | **Mock** — no podés disparar un race real en un test determinístico |
| Throttle rate en tests | **Mock** — no querés esperar 1 minuto entre tests |
| Control de tiempo (`timezone.now()`) | **Mock** con `freezegun` |
| Requests a la DB | **Real PostgreSQL** — mockear la DB es mentir |
| Requests HTTP entre servicios | **Real** (si es tu API) o `responses` library (si es externa) |
| Queries N+1 | **`django_assert_num_queries`** — contar queries reales |
| Emails | **`locmem` backend** — `mail.outbox` sin SMTP real |

```python
# ✅ Mock necesario — race condition no es reproducible deterministamente
with patch("...TimeSlot.objects.filter") as mock_filter:
    mock_filter.return_value.update.return_value = 0

# ✅ Real — la DB existe, no hay razón para mockearla
appointment = AppointmentFactory(status="confirmed")
response = doctor_client.post(f"/api/appointments/{appointment.id}/confirm/")
assert response.status_code == 200
```

**El anti-patrón:** mockear la DB "para que los tests sean más rápidos". Un test que mockea la DB no prueba que tu ORM query funciona — prueba que llamás al mock con los argumentos correctos. Es un test tautológico.

</details>

---

<details>
<summary>🟡 ¿Qué es branch coverage y por qué es más honesto que line coverage?</summary>

**Line coverage** cuenta si cada línea fue ejecutada al menos una vez.

**Branch coverage** cuenta si cada rama de cada condición fue tomada — el `True` Y el `False`.

```python
def can_be_confirmed(self) -> bool:
    return self.status == self.Status.PENDING
    #          ↑ True branch    ↑ False branch
```

Con line coverage: si llamás a esta función una vez (y devuelve `True`), la línea está "cubierta" → 100%.

Con branch coverage: necesitás un test donde devuelve `True` Y otro donde devuelve `False`.

**El caso real en MedBook:**
```python
if not updated:   # ← rama del race condition
    raise ValidationError("This time slot is no longer available.")
```

Line coverage: si `updated > 0` en todos los tests, la línea `if not updated` está "ejecutada" → cubierta. El raise nunca se testea. Line coverage dice 99%.

Branch coverage: falta la rama `True` del `if not updated`. Detecta el agujero.

**¿Por qué 85% y no 100%?** 100% requeriría testear guards defensivos casi imposibles de provocar (`swagger_fake_view`, `except Exception` en signals). 85% es el balance entre cobertura real y esfuerzo razonable.

</details>

---

<details>
<summary>🔴 ¿Por qué factory_boy en vez de fixtures JSON/YAML?</summary>

**Fixtures JSON/YAML tienen 3 problemas:**

1. **Acoplamiento a la estructura:** cambiás un campo en el modelo → todos los fixtures rompen. Y no siempre en forma obvia — pueden fallar en tiempo de load, no en el test.

2. **Opacidad:** para entender qué datos necesita un test, tenés que abrir el fixture JSON y buscar. Los factories están inline.

3. **Mantenimiento:** los fixtures acumulan datos históricos que nadie sabe para qué sirven.

**factory_boy:**
```python
class AppointmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Appointment

    patient = factory.SubFactory(PatientFactory)   # crea un Patient con sus dependencias
    doctor = factory.SubFactory(DoctorFactory)
    slot = factory.SubFactory(TimeSlotFactory)
    status = Appointment.Status.PENDING

# En el test:
appointment = AppointmentFactory(status="confirmed")   # explícito y legible
appointment = AppointmentFactory(patient=mi_paciente)  # override específico
```

Si agregás un campo nuevo al modelo, la factory sigue funcionando (usa defaults). El fixture rompería.

</details>

---

## 6. Seguridad

<details>
<summary>🟢 ¿Cómo funciona la autenticación JWT en MedBook? ¿Cuáles son los 3 endpoints?</summary>

JWT = JSON Web Token. Tres partes: header (algoritmo), payload (claims), firma.

El flow:
1. `POST /api/token/` → cliente envía email + password → recibe `{access, refresh}`
2. Cada request → cliente envía `Authorization: Bearer <access_token>`
3. Access token expira → `POST /api/token/refresh/` con el refresh token → nuevo access
4. Logout → `POST /api/token/blacklist/` → invalida el refresh token

**¿Por qué dos tokens?**
- `access` tiene vida corta (5 min - 1 hora) — si es robado, expira pronto
- `refresh` tiene vida larga (7-30 días) — solo se usa para obtener nuevos access tokens

**El custom claim:**
```python
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role   # el frontend necesita saber el rol
        token["email"] = user.email
        return token
```

</details>

---

<details>
<summary>🔴 ¿Cómo previene MedBook el double-booking? Explicá el race condition.</summary>

**El problema:**

```
Thread A                        Thread B
────────────────────────────────────────
slot = TimeSlot.objects.get(id)
if slot.status == "available":  slot = TimeSlot.objects.get(id)
    slot.status = "reserved"    if slot.status == "available":
    slot.save()                     slot.status = "reserved"
                                    slot.save()
```

Ambos threads leen `available`, ambos escriben `reserved`. El slot queda con dos appointments — el sistema roto.

**La solución — UPDATE atómico:**

```python
@transaction.atomic
def create_appointment(patient, doctor, slot, reason=""):
    updated = TimeSlot.objects.filter(
        id=slot.id,
        status=TimeSlot.Status.AVAILABLE,  # ← condición en el UPDATE
    ).update(
        status=TimeSlot.Status.RESERVED,
        updated_at=timezone.now()
    )
    if not updated:   # ← 0 rows = alguien llegó primero
        raise DjangoValidationError("This time slot is no longer available.")

    slot.refresh_from_db()
    return Appointment.objects.create(...)
```

`UPDATE ... WHERE status='available'` es atómico a nivel de base de datos — PostgreSQL garantiza que exactamente **uno** de los threads va a matchear el WHERE y actualizar. El otro ve 0 rows afectadas.

**¿Por qué `@transaction.atomic` además?** El UPDATE y el INSERT (crear el Appointment) deben ser una unidad. Si el INSERT falla, el UPDATE debe rollbackear también.

</details>

---

<details>
<summary>🟡 ¿Qué es CORS y por qué tiene que ir antes de CommonMiddleware?</summary>

CORS (Cross-Origin Resource Sharing) es un mecanismo del browser que bloquea requests a un dominio diferente al de la página cargada.

Si tu frontend está en `https://medbook-app.vercel.app` y el backend en `https://api.medbook.com`, el browser va a bloquear el request **antes de enviarlo** a menos que el servidor responda con los headers correctos (`Access-Control-Allow-Origin`).

`CorsMiddleware` intercepta el request y agrega esos headers.

**¿Por qué antes de `CommonMiddleware`?** Los browsers envían un **preflight request** (`OPTIONS`) antes de requests con headers custom (como `Authorization: Bearer ...`). Si `CommonMiddleware` procesa ese OPTIONS primero, puede redirigir (e.g., añadir `/`) o rechazarlo antes de que CORS tenga chance de responder correctamente.

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",         # ← antes de Common
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",      # ← después
    ...
]
```

</details>

---

## 7. Performance y ORM

<details>
<summary>🟢 ¿Qué es el problema N+1 y cómo lo previenen en MedBook?</summary>

N+1 = 1 query para obtener N objetos, luego 1 query adicional por cada objeto para resolver una relación. Total: N+1 queries cuando podría ser 1 o 2.

```python
# ❌ N+1 — con 20 appointments = 61 queries
appointments = Appointment.objects.all()
for a in appointments:
    print(a.patient.user.email)    # 1 query por appointment
    print(a.doctor.user.email)     # 1 query por appointment
    print(a.slot.start_datetime)   # 1 query por appointment

# ✅ select_related — 1 query con JOINs
appointments = Appointment.objects.select_related(
    "patient__user",
    "doctor__user",
    "slot__schedule",
)
```

**Regla en MedBook:** `select_related` en todos los `get_queryset()` con FKs. `prefetch_related` para M2M (Doctor → specialties). Convention sobre configuración — si no lo ves, es un bug.

**¿Cómo detectarlo?** Con `django_assert_num_queries`:
```python
def test_list_does_not_n_plus_one(doctor_client, db):
    DoctorFactory.create_batch(3)
    with django_assert_num_queries(3):  # join + prefetch specialties + count
        response = doctor_client.get("/api/doctors/")
    assert response.status_code == 200
```

</details>

---

<details>
<summary>🟡 ¿Cuál es la diferencia entre select_related y prefetch_related?</summary>

**`select_related`** — para ForeignKey y OneToOne. Hace un SQL JOIN en la misma query:

```sql
-- select_related("patient__user", "doctor__user")
SELECT appointments.*, patients.*, users_patient.*,
       doctors.*, users_doctor.*
FROM appointments
JOIN patients ON appointments.patient_id = patients.id
JOIN users users_patient ON patients.user_id = users_patient.id
JOIN doctors ON appointments.doctor_id = doctors.id
JOIN users users_doctor ON doctors.user_id = users_doctor.id
```

Una sola query. Ideal cuando la relación es FK (muchos-a-uno, uno-a-uno).

**`prefetch_related`** — para M2M y reverse FK. Hace queries separadas pero en batch:

```sql
-- prefetch_related("specialties") para 3 doctors
-- Query 1: SELECT * FROM doctors WHERE id IN (1, 2, 3)
-- Query 2: SELECT specialties.*, doctor_specialty.*
--          FROM specialties JOIN doctor_specialty ...
--          WHERE doctor_id IN (1, 2, 3)
```

Dos queries total, no N+1.

**El bug `.count()` sobre M2M:**
```python
# ❌ ignora el cache del prefetch → 1 COUNT(*) por doctor
return obj.specialties.count()

# ✅ usa el cache → 0 queries extra
return len(obj.specialties.all())
```

</details>

---

<details>
<summary>🔴 ¿Qué significa update_fields en los saves y por qué importa?</summary>

`save()` por defecto hace un `UPDATE` con TODOS los campos. Si el modelo tiene 20 campos y solo cambiaste `status`, igual actualiza los 20.

```python
# ❌ UPDATE appointments SET status=..., patient_id=..., doctor_id=...,
#    slot_id=..., reason=..., created_at=..., updated_at=..., ...
appointment.status = "confirmed"
appointment.save()

# ✅ UPDATE appointments SET status=..., updated_at=... WHERE id=...
appointment.status = "confirmed"
appointment.save(update_fields=["status", "updated_at"])
```

**¿Por qué importa?**
1. **Performance:** menos datos transferidos a la DB
2. **Concurrencia:** si dos procesos editan campos distintos del mismo objeto, el `UPDATE` completo puede sobreescribir los cambios del otro. `update_fields` solo toca los campos que cambiaste.
3. **Correctness:** en la máquina de estados, solo querés actualizar `status`. Si alguien modificó `reason` concurrentemente, no querés sobreescribirlo.

</details>

---

## 8. Producción y CI/CD

<details>
<summary>🟢 ¿Para qué sirve separar los settings en base/local/test/production?</summary>

Cada ambiente tiene configuraciones distintas. Un único archivo `settings.py` termina lleno de `if os.environ.get("ENV") == "production": ...` — ilegible y propenso a errores.

```
config/settings/
├── base.py        # común a todos — modelos, apps instaladas, DRF config
├── local.py       # dev local — DEBUG=True, email a consola, vars locales
├── test.py        # tests — email locmem, DB de test, sin throttle
└── production.py  # prod — DEBUG=False, HTTPS, WhiteNoise, variables de entorno
```

**Cada archivo hereda de base:**
```python
# production.py
from .base import *   # trae todo lo común

DEBUG = False
# solo lo que cambia en producción
```

**Las variables secretas nunca están en el código:**
```python
# production.py
SECRET_KEY = config("SECRET_KEY")  # siempre desde env var
DATABASE_URL = dj_database_url.config()
```

Si `SECRET_KEY` está hardcodeada en el repo → cualquiera que tenga acceso puede forjar tokens JWT, firmar sesiones, etc. Nunca en código.

</details>

---

<details>
<summary>🟡 ¿Qué es WhiteNoise y cuándo usarías Nginx en vez?</summary>

**WhiteNoise** es un middleware Python que sirve static files directamente desde el proceso de Django/Gunicorn. Sin configuración extra, sin servidor adicional.

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # intercepta requests de /static/
    ...
]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}
```

`CompressedManifestStaticFilesStorage` genera hashes en los nombres (`base.abc123.css`) → permite cache de 1 año en el browser sin riesgo de servir versiones viejas.

**¿Cuándo usarías Nginx?**
- Alta concurrencia (miles de requests/seg para assets) — Nginx sirve archivos desde buffers del kernel, mucho más eficiente que Python
- Si ya tenés Nginx como reverse proxy (common en servidores propios)
- Assets grandes o streaming de video

Para un portfolio project en Railway/Render con decenas/cientos de usuarios → WhiteNoise es la respuesta correcta. Cero infraestructura extra.

</details>

---

<details>
<summary>🟡 ¿Qué es WSGI vs ASGI? ¿Cuándo usarías cada uno con Django?</summary>

**WSGI (Web Server Gateway Interface)** — estándar síncrono. Un request ocupa un worker thread de principio a fin. Gunicorn es el servidor WSGI estándar para Django.

```
Browser → Nginx → Gunicorn → Django (wsgi.py)
```

**ASGI (Asynchronous Server Gateway Interface)** — soporta async/await, WebSockets, Server-Sent Events. Uvicorn o Daphne son servidores ASGI.

```
Browser → Nginx → Uvicorn → Django (asgi.py)
```

Django genera **ambos archivos** en todo proyecto:
```
config/
├── wsgi.py   ← para Gunicorn
└── asgi.py   ← para Uvicorn/Daphne
```

**¿Cuándo usar ASGI?**
- WebSockets en tiempo real (chat, notificaciones push)
- Long polling o Server-Sent Events
- Views con `async def` que realmente hacen I/O async

**MedBook usa WSGI porque:**
- Es una API REST clásica — request/response, sin conexiones persistentes
- No tiene `async def` en views
- Gunicorn es más simple de configurar y más predecible para debugging

ASGI no es "más rápido siempre" — si tus operaciones son síncronas, async no ayuda. La ganancia es en I/O-bound con muchas conexiones concurrentes esperando (chat, notifications).

</details>

---

<details>
<summary>🔴 ¿Qué garantiza el CI y cuál era el bug en el workflow?</summary>

El CI (`.github/workflows/ci.yml`) corre en cada push/PR a master:

1. **Lint** (`ruff check .` + `ruff format --check .`) — código consistente, sin errores básicos
2. **Migrations check** (`makemigrations --check --dry-run`) — nadie olvidó correr makemigrations
3. **Tests con coverage** — 274 tests, branch coverage ≥ 85%

**El bug:** el workflow tenía `-o "addopts="`:

```yaml
# ❌ Esto anulaba TODO el addopts de pytest.ini
pytest --cov=apps --cov-report=xml -o "addopts=" --tb=short -q
```

`-o "addopts="` le dice a pytest "ignorá el `addopts` del archivo de config y usá cadena vacía". Resultado: `--cov-branch` y `--cov-fail-under=85` **nunca aplicaban en CI**. El gate de coverage solo existía en local.

```yaml
# ✅ pytest.ini es la fuente de verdad — CI solo agrega lo que le falta
pytest --cov-report=xml --tb=short -q
# hereda: --cov=apps --cov-branch --cov-fail-under=85 --strict-markers --reuse-db
```

**Principio:** un único lugar de configuración para los tests (`pytest.ini`). CI agrega solo lo que es específico de ese ambiente (`--cov-report=xml` para Codecov).

</details>

---

## 9. Preguntas de diseño abierto

> Estas no tienen una respuesta única — el objetivo es demostrar razonamiento, no memorizar respuestas.

<details>
<summary>🔴 ¿Qué cambiarías si MedBook tuviera 100.000 usuarios activos?</summary>

**Base de datos:**
- `select_related` ya está — bien
- Agregar índices en campos de filtro frecuente: `TimeSlot.status`, `Appointment.status`, `Appointment.created_at`
- Separar DB de read y write (read replicas) para queries de listado
- Considerar `django-pgbulk` para `bulk_create` masivo de slots

**Email:**
- Mover a cola asíncrona (Celery + Redis) — hoy las notificaciones son síncronas dentro del request. Si Resend tarda, el usuario espera.
- `transaction.on_commit(lambda: send_notification.delay(appointment.id))` — el email se encola solo si la transacción commitea

**Cache:**
- Lista de especialidades → no cambia → perfecta para Redis con `cache.get_or_set`
- Available slots por doctor → TTL corto (30s) para no mostrar slots viejos

**Throttling:**
- Mover del proceso Python a Redis-backed throttle (hoy usa memoria local — no funciona con múltiples workers)

**Deploy:**
- Múltiples workers de Gunicorn (`--workers 4`)
- Health checks en Railway/Render
- Sentry para error tracking

</details>

---

<details>
<summary>🔴 ¿Cómo extenderías el sistema para soportar videollamadas en las citas?</summary>

Esto **requiere ASGI** — las videollamadas necesitan señalización en tiempo real (WebRTC signaling via WebSocket).

El approach:
1. Migrar a ASGI: `gunicorn config.asgi -k uvicorn.workers.UvicornWorker`
2. Agregar `django-channels` para WebSocket support
3. Crear un endpoint WebSocket para señalización WebRTC:
   ```
   ws://api.medbook.com/ws/appointments/{id}/signaling/
   ```
4. El "video" en sí corre peer-to-peer (WebRTC) — el servidor solo ayuda a establecer la conexión

**Alternativa más simple:** integrar Twilio Video, Daily.co, o Zoom SDK → tu backend solo genera tokens de sesión y el proveedor maneja la infraestructura de video. Sin ASGI necesario.

Para un MVP, la segunda opción siempre. Para control total y escala, WebRTC propio.

</details>

---

<details>
<summary>🔴 ¿Cómo diseñarías el sistema de notificaciones si hubiese 10 tipos de eventos?</summary>

Hoy las notificaciones son llamadas directas en los services:
```python
# services.py
confirm_appointment(appointment)
send_appointment_confirmed(appointment)   # llamada explícita
```

Con 10+ tipos de eventos, esto escala mal — cada service tiene que conocer qué notificaciones enviar.

**Diseño para escala:**

```python
# 1. Publicar eventos de dominio (no acoplados a implementación)
from apps.core.events import publish

@transaction.atomic
def confirm_appointment(appointment):
    appointment.confirm()
    publish("appointment.confirmed", appointment_id=appointment.id)

# 2. Handlers que subscriben a eventos
@handler("appointment.confirmed")
def send_confirmation_email(appointment_id):
    appointment = Appointment.objects.get(id=appointment_id)
    send_appointment_confirmed(appointment)

@handler("appointment.confirmed")
def notify_calendar_integration(appointment_id):
    ...  # Google Calendar, etc.
```

**Beneficios:**
- `confirm_appointment` no conoce los canales de notificación
- Agregar un nuevo canal = agregar un handler (OCP)
- Los handlers pueden ser async (Celery) sin cambiar el service
- Fácil de testear cada handler por separado

Librerías: `django-pydantic-event-bus`, `django-simple-events`, o Celery signals.

</details>

---

<details>
<summary>🟡 Si una entrevista te pregunta "¿qué es lo que mejorarías de MedBook?", ¿qué dirías?</summary>

Respuesta honesta que demuestra criterio (no que el código está mal — sino que hay trade-offs conscientes):

1. **Notificaciones síncronas → Celery async.** Hoy si Resend está lento, el usuario espera. En producción real, las notificaciones irían a una cola.

2. **`transaction.on_commit` para emails.** Si la transacción falla después de enviar el email (edge case), el email ya fue. Con `on_commit`, el email sale solo si la DB commitea.

3. **Soft delete en Appointments.** Hoy el admin puede hacer hard delete. En un sistema médico real, los registros son auditables — nunca se borran, solo se marcan.

4. **Refresh de JWT más corto.** El refresh token actual dura 7 días. Para un sistema médico con datos sensibles, consideraría 24 horas con "remember me" opcional.

5. **Endpoint de registro público.** Hoy los usuarios se crean por Django Shell o Admin. Un portafolio real mostraría el onboarding completo.

La clave en la entrevista: no decir "esto está mal". Decir "tomé esta decisión consciente por X razón, y si el scope cambiara haría Y".

</details>

---

## Referencia rápida — Comandos

```bash
# Levantar entorno local
$env:DJANGO_SETTINGS_MODULE='config.settings.local'
python manage.py runserver

# Tests con branch coverage
pytest
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest -k "test_confirm" -v    # filtrar por nombre

# Generar slots
python manage.py generate_slots --days=30
python manage.py generate_slots --doctor-id=<uuid>

# Validar schema OpenAPI
python manage.py spectacular --validate --fail-on-warn

# Lint
ruff check . && ruff format --check .

# Verificar migraciones pendientes
python manage.py makemigrations --check --dry-run
```
