# MedBook — Guía de Pruebas E2E

> Paso a paso para probar TODOS los flujos de la API.  
> Usa curl o el Swagger UI en http://localhost:8000/api/docs/

---

## Antes de empezar

### Levanta el servidor local

```powershell
# Windows PowerShell
$env:DJANGO_SETTINGS_MODULE='config.settings.local'
$env:SECRET_KEY='dev-local-secret-key-medbook'
python manage.py runserver
```

```bash
# Linux / Mac
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver
```

El servidor queda en: **http://localhost:8000**  
Swagger UI: **http://localhost:8000/api/docs/**  
Admin: **http://localhost:8000/admin/**

---

## Paso 0 — Crear datos de prueba

Los usuarios no se crean vía API (no hay endpoint de registro público). Se crean desde Django Admin o desde la shell.

### 0.1 Crear superusuario (admin)

```bash
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py createsuperuser
# Email: admin@medbook.com
# Password: Admin1234!
```

### 0.2 Crear doctor y paciente desde Django Shell

```bash
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py shell
```

```python
from apps.users.models import User, Role
from apps.doctors.models import Doctor, Specialty
from apps.patients.models import Patient

# --- Doctor ---
doctor_user = User.objects.create_user(
    email="dr.garcia@medbook.com",
    password="Doctor1234!",
    role=Role.DOCTOR,
    first_name="Carlos",
    last_name="García",
)
cardiology = Specialty.objects.get(slug="cardiology")
doctor = Doctor.objects.create(
    user=doctor_user,
    license_number="MED-001",
    consultation_duration=30,
    bio="Cardiologist with 15 years of experience.",
)
doctor.specialties.add(cardiology)
print("Doctor creado:", doctor.user.email)

# --- Paciente ---
patient_user = User.objects.create_user(
    email="juan.perez@gmail.com",
    password="Patient1234!",
    role=Role.PATIENT,
    first_name="Juan",
    last_name="Pérez",
)
Patient.objects.create(
    user=patient_user,
    phone="+56912345678",
)
print("Paciente creado:", patient_user.email)
exit()
```

### 0.3 Crear horario del doctor (genera slots automáticamente)

```bash
DJANGO_SETTINGS_MODULE=config.settings.local python manage.py shell
```

```python
from apps.doctors.models import Doctor, Schedule

doctor = Doctor.objects.get(user__email="dr.garcia@medbook.com")

import datetime
Schedule.objects.create(
    doctor=doctor,
    day_of_week=0,  # 0=Lunes, 1=Martes ... 6=Domingo
    start_time=datetime.time(9, 0),
    end_time=datetime.time(17, 0),
    is_active=True,
)
# El signal post_save genera automáticamente los slots para los próximos 7 días

from apps.appointments.models import TimeSlot
count = TimeSlot.objects.filter(schedule__doctor=doctor).count()
print(f"Slots generados: {count}")
exit()
```

O también puedes crear el horario desde el **Admin** en http://localhost:8000/admin/doctors/schedule/

---

## Flujo 1 — Autenticación

### 1.1 Login

```bash
curl -s -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "dr.garcia@medbook.com", "password": "Doctor1234!"}' \
  | python -m json.tool
```

**Respuesta esperada:**
```json
{
  "access": "eyJhbGci...",
  "refresh": "eyJhbGci...",
  "role": "doctor",
  "email": "dr.garcia@medbook.com"
}
```

Guarda el `access` token — lo usarás en todos los requests.

```bash
# Guardar en variable (Linux/Mac)
TOKEN=$(curl -s -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "dr.garcia@medbook.com", "password": "Doctor1234!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access'])")

echo "Token: $TOKEN"
```

### 1.2 Ver perfil

```bash
curl -s http://localhost:8000/api/users/me/ \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

**Respuesta esperada:**
```json
{
  "id": "uuid...",
  "email": "dr.garcia@medbook.com",
  "role": "doctor",
  "full_name": "Carlos García",
  "first_name": "Carlos",
  "last_name": "García",
  "created_at": "2025-..."
}
```

### 1.3 Actualizar perfil

```bash
curl -s -X PATCH http://localhost:8000/api/users/me/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "Carlos Eduardo"}' \
  | python -m json.tool
```

### 1.4 Logout (invalidar token)

```bash
REFRESH_TOKEN="eyJhbGci..."  # tu refresh token

curl -s -X POST http://localhost:8000/api/token/blacklist/ \
  -H "Content-Type: application/json" \
  -d "{\"refresh\": \"$REFRESH_TOKEN\"}"
```

**Respuesta esperada:** `{}` con status 200.

### 1.5 Verificar rate limiting en login

```bash
# Después de 5 intentos fallidos en menos de 1 minuto:
for i in $(seq 1 6); do
  echo "Intento $i:"
  curl -s -X POST http://localhost:8000/api/token/ \
    -H "Content-Type: application/json" \
    -d '{"email": "nadie@test.com", "password": "wrong"}' \
    -w "  → HTTP %{http_code}\n" -o /dev/null
  sleep 0.5
done
# El 6to debe devolver HTTP 429
```

---

## Flujo 2 — Doctores y specialties

### 2.1 Listar especialidades

```bash
curl -s http://localhost:8000/api/specialties/ \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

**Respuesta esperada:**
```json
{
  "count": 5,
  "results": [
    {"id": "...", "name": "Cardiology", "slug": "cardiology"},
    {"id": "...", "name": "Dermatology", "slug": "dermatology"},
    ...
  ]
}
```

### 2.2 Listar doctores

```bash
curl -s http://localhost:8000/api/doctors/ \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

### 2.3 Filtrar por especialidad

```bash
curl -s "http://localhost:8000/api/doctors/?specialty=cardiology" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

### 2.4 Ver slots disponibles del doctor

```bash
# Necesitas el ID del doctor
DOCTOR_ID="uuid-del-doctor-aqui"

curl -s "http://localhost:8000/api/doctors/$DOCTOR_ID/available-slots/" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool

# Especificar ventana de días (default: 7)
curl -s "http://localhost:8000/api/doctors/$DOCTOR_ID/available-slots/?days=14" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

### 2.5 Verificar validación de ?days=

```bash
# ?days= con valor no numérico debe devolver 400
curl -s "http://localhost:8000/api/doctors/$DOCTOR_ID/available-slots/?days=abc" \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

**Esperado:**
```json
{
  "detail": "Invalid input.",
  "code": "validation_error",
  "field_errors": {
    "days": ["Must be an integer."]
  }
}
```

**Respuesta esperada:**
```json
{
  "count": 14,
  "results": [
    {
      "id": "uuid-del-slot",
      "start_datetime": "2025-06-09T09:00:00Z",
      "end_datetime": "2025-06-09T09:30:00Z",
      "status": "available"
    },
    ...
  ]
}
```

Guarda el `id` de un slot — lo usarás para crear la cita.

---

## Flujo 3 — Schedules (solo doctor)

### 3.1 Crear horario (como doctor)

```bash
# Loguéate como doctor primero
DOCTOR_TOKEN="..."

curl -s -X POST http://localhost:8000/api/schedules/ \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "day_of_week": 2,
    "start_time": "10:00:00",
    "end_time": "15:00:00",
    "is_active": true
  }' \
  | python -m json.tool
```

**Respuesta esperada:** `201 Created` con el schedule creado. En la consola del servidor vas a ver el signal generando los slots.

### 3.2 Listar horarios propios

```bash
curl -s http://localhost:8000/api/schedules/ \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

### 3.3 Desactivar horario (soft delete)

```bash
SCHEDULE_ID="uuid-del-schedule"

curl -s -X DELETE "http://localhost:8000/api/schedules/$SCHEDULE_ID/" \
  -H "Authorization: Bearer $DOCTOR_TOKEN"
# 204 No Content — el schedule queda con is_active=False
```

### 3.4 Verificar que paciente no puede crear schedules

```bash
PATIENT_TOKEN="..."  # token del paciente

curl -s -X POST http://localhost:8000/api/schedules/ \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"day_of_week": 1, "start_time": "09:00:00", "end_time": "12:00:00"}' \
  -w "\nHTTP %{http_code}"
# Esperado: HTTP 403 Forbidden
```

---

## Flujo 4 — Reserva de cita (flujo core)

### 4.1 Login como paciente

```bash
PATIENT_TOKEN=$(curl -s -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "juan.perez@gmail.com", "password": "Patient1234!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access'])")
```

### 4.2 Reservar cita

```bash
SLOT_ID="uuid-del-slot-disponible"  # obtenido en 2.4

curl -s -X POST http://localhost:8000/api/appointments/ \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"slot\": \"$SLOT_ID\",
    \"reason\": \"Dolor de pecho intermitente hace 3 días\"
  }" \
  | python -m json.tool
```

**Respuesta esperada:**
```json
{
  "id": "uuid-de-la-cita",
  "patient": {...},
  "doctor": {...},
  "slot": {...},
  "reason": "Dolor de pecho intermitente hace 3 días",
  "status": "pending",
  "created_at": "..."
}
```

En la **consola del servidor** deberías ver el email de notificación al paciente.

### 4.3 Guardar el ID de la cita

```bash
APPOINTMENT_ID="uuid-de-la-cita-recien-creada"
```

### 4.4 Ver la cita creada

```bash
curl -s "http://localhost:8000/api/appointments/$APPOINTMENT_ID/" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -m json.tool
```

### 4.5 Intentar reservar el mismo slot (debe fallar)

```bash
curl -s -X POST http://localhost:8000/api/appointments/ \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"slot\": \"$SLOT_ID\", \"reason\": \"Otro intento\"}" \
  | python -m json.tool
```

**Respuesta esperada:** `400 Bad Request`
```json
{
  "detail": "This time slot is no longer available.",
  "code": "validation_error"
}
```

---

## Flujo 5 — Confirmación y transiciones de estado

### 5.1 Confirmar cita (como doctor)

```bash
curl -s -X POST "http://localhost:8000/api/appointments/$APPOINTMENT_ID/confirm/" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

**Respuesta esperada:**
```json
{
  "id": "...",
  "status": "confirmed",
  ...
}
```

Email de confirmación al paciente aparece en consola del servidor.

### 5.2 Verificar que el paciente no puede confirmar

```bash
curl -s -X POST "http://localhost:8000/api/appointments/$APPOINTMENT_ID/confirm/" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  -w "\nHTTP %{http_code}"
# Esperado: HTTP 403
```

### 5.3 Marcar como completada

```bash
curl -s -X POST "http://localhost:8000/api/appointments/$APPOINTMENT_ID/complete/" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

**Respuesta esperada:** `status: "completed"`

### 5.4 Intentar cancelar una cita completada (debe fallar)

```bash
curl -s -X POST "http://localhost:8000/api/appointments/$APPOINTMENT_ID/cancel/" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -m json.tool
```

**Respuesta esperada:** `400 Bad Request`
```json
{
  "detail": "Cannot cancel appointment in status 'completed'.",
  "code": "error"
}
```

---

## Flujo 6 — Cancelación

### 6.1 Crear una nueva cita para cancelar

```bash
# Necesitas un slot diferente — obtén uno nuevo
NEW_SLOT_ID="otro-slot-disponible"

curl -s -X POST http://localhost:8000/api/appointments/ \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"slot\": \"$NEW_SLOT_ID\", \"reason\": \"Chequeo de rutina\"}" \
  | python -m json.tool

NEW_APPOINTMENT_ID="uuid-nueva-cita"
```

### 6.2 Paciente cancela su propia cita

```bash
curl -s -X POST "http://localhost:8000/api/appointments/$NEW_APPOINTMENT_ID/cancel/" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -m json.tool
```

**Respuesta esperada:** `status: "cancelled"`. Email de cancelación en consola.

### 6.3 Verificar que el slot quedó disponible de nuevo

```bash
curl -s "http://localhost:8000/api/doctors/$DOCTOR_ID/available-slots/" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -c "import sys,json; slots = json.load(sys.stdin)['results']; print([s['id'] for s in slots if s['id'] == '$NEW_SLOT_ID'])"
# El slot cancelado debe aparecer en la lista
```

### 6.4 Marcar como no-show (inasistencia)

```bash
# Necesitas una cita en status "confirmed"
CONFIRMED_APPOINTMENT_ID="uuid-cita-confirmada"

curl -s -X POST "http://localhost:8000/api/appointments/$CONFIRMED_APPOINTMENT_ID/no_show/" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
# status: "no_show"
```

---

## Flujo 7 — Notas médicas

### 7.1 Agregar nota médica (como doctor)

```bash
# Necesitas una cita completada o confirmada
COMPLETED_APPOINTMENT_ID="uuid-cita-completada"

curl -s -X POST "http://localhost:8000/api/appointments/$COMPLETED_APPOINTMENT_ID/notes/" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Paciente presenta dolor precordial atípico. ECG normal. Se indica Holter 24h y control en 2 semanas."
  }' \
  | python -m json.tool
```

**Respuesta esperada:**
```json
{
  "id": "uuid-nota",
  "content": "Paciente presenta...",
  "author_name": "Carlos García",
  "created_at": "..."
}
```

### 7.2 Listar notas de la cita

```bash
curl -s "http://localhost:8000/api/appointments/$COMPLETED_APPOINTMENT_ID/notes/" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

### 7.3 Verificar que paciente NO puede ver notas

```bash
curl -s "http://localhost:8000/api/appointments/$COMPLETED_APPOINTMENT_ID/notes/" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  -w "\nHTTP %{http_code}"
# Esperado: HTTP 403
```

### 7.4 Verificar que otro doctor NO puede ver notas ajenas

```bash
OTHER_DOCTOR_TOKEN="..."  # token de otro doctor

curl -s "http://localhost:8000/api/appointments/$COMPLETED_APPOINTMENT_ID/notes/" \
  -H "Authorization: Bearer $OTHER_DOCTOR_TOKEN" \
  -w "\nHTTP %{http_code}"
# Esperado: HTTP 404 (no sabe que la cita existe)
```

---

## Flujo 8 — Filtros

### 8.1 Filtrar citas por status

```bash
# Como paciente — solo ve las propias
curl -s "http://localhost:8000/api/appointments/?status=pending" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -m json.tool

# Como admin — ve todas las pending
curl -s "http://localhost:8000/api/appointments/?status=pending" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python -m json.tool
```

### 8.2 Filtrar por rango de fechas

```bash
curl -s "http://localhost:8000/api/appointments/?date_from=2025-06-01&date_to=2025-06-30" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

### 8.3 Filtrar schedules por día de semana

```bash
# 0=lunes, 1=martes, ... 6=domingo
curl -s "http://localhost:8000/api/schedules/?day_of_week=0" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

### 8.4 Filtrar doctores por especialidad

```bash
curl -s "http://localhost:8000/api/doctors/?specialty=cardiology" \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -m json.tool
```

### 8.5 Ordenar citas (ordering)

```bash
# Citas ordenadas por fecha de creación (más nuevas primero)
curl -s "http://localhost:8000/api/appointments/?ordering=-created_at" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool

# Citas ordenadas por fecha del slot (más próximas primero)
curl -s "http://localhost:8000/api/appointments/?ordering=slot__start_datetime" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool

# Combinar filtro + ordering
curl -s "http://localhost:8000/api/appointments/?status=pending&ordering=slot__start_datetime" \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  | python -m json.tool
```

El prefijo `-` invierte el orden (descendente). Campos disponibles: `created_at`, `slot__start_datetime`.

---

## Flujo 9 — Admin Django

Abre http://localhost:8000/admin/ con el superusuario (`admin@medbook.com`).

### Cosas a verificar en el Admin:

**Appointments:**
- Los badges de status tienen colores (pending=amarillo, confirmed=verde, cancelled=rojo, completed=azul)
- El bulk action "Mark as no-show" solo afecta citas en status `confirmed`
- Las notas médicas aparecen como inline bajo cada cita

**Doctors:**
- Los schedules del doctor aparecen como inline en la edición del doctor
- El campo `specialties` tiene un selector horizontal (filter_horizontal)

**MedBook Administration:**
- El header dice "MedBook Administration" (no el genérico de Django)

---

## Flujo 10 — Verificar errores normalizados

Todos los errores siguen el formato `{detail, code, [field_errors]}`.

### Error de validación de campo

```bash
curl -s -X POST http://localhost:8000/api/schedules/ \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"day_of_week": 0, "start_time": "17:00:00", "end_time": "09:00:00"}' \
  | python -m json.tool
```

**Esperado:**
```json
{
  "detail": "Invalid input.",
  "code": "validation_error",
  "field_errors": {
    "end_time": ["end_time must be after start_time."]
  }
}
```

### Error de autenticación

```bash
curl -s http://localhost:8000/api/appointments/ | python -m json.tool
```

**Esperado:**
```json
{
  "detail": "Authentication credentials were not provided.",
  "code": "not_authenticated"
}
```

### Recurso no encontrado

```bash
curl -s http://localhost:8000/api/appointments/00000000-0000-0000-0000-000000000000/ \
  -H "Authorization: Bearer $PATIENT_TOKEN" \
  | python -m json.tool
```

**Esperado:**
```json
{
  "detail": "No Appointment matches the given query.",
  "code": "not_found"
}
```

---

## Resumen de flujos y status esperados

| Flujo | Acción | Actor | Status esperado |
|---|---|---|---|
| Login correcto | POST /api/token/ | Cualquiera | 200 + tokens |
| Login incorrecto | POST /api/token/ | Cualquiera | 401 |
| Rate limit | POST /api/token/ 6 veces | Cualquiera | 429 en el 6to |
| Ver perfil | GET /api/users/me/ | Autenticado | 200 |
| Listar doctores | GET /api/doctors/ | Autenticado | 200 |
| Ver slots | GET /api/doctors/{id}/available-slots/ | Autenticado | 200 |
| Crear schedule | POST /api/schedules/ | Doctor | 201 |
| Crear schedule | POST /api/schedules/ | Paciente | 403 |
| Reservar cita | POST /api/appointments/ | Paciente | 201 |
| Reservar cita | POST /api/appointments/ | Doctor | 403 |
| Slot ya reservado | POST /api/appointments/ | Paciente | 400 |
| Confirmar cita | POST /api/appointments/{id}/confirm/ | Doctor dueño | 200 |
| Confirmar cita | POST /api/appointments/{id}/confirm/ | Otro doctor | 403 |
| Confirmar cita | POST /api/appointments/{id}/confirm/ | Paciente | 403 |
| Cancelar cita | POST /api/appointments/{id}/cancel/ | Paciente dueño | 200 |
| Completar cita | POST /api/appointments/{id}/complete/ | Doctor dueño | 200 |
| Cancelar completada | POST /api/appointments/{id}/cancel/ | Cualquiera | 400 |
| No-show | POST /api/appointments/{id}/no_show/ | Doctor dueño | 200 |
| Crear nota | POST /api/appointments/{id}/notes/ | Doctor dueño | 201 |
| Ver notas | GET /api/appointments/{id}/notes/ | Paciente | 403 |
| Ver notas | GET /api/appointments/{id}/notes/ | Otro doctor | 404 |
| Eliminar cita | DELETE /api/appointments/{id}/ | Admin | 204 |
| Eliminar cita | DELETE /api/appointments/{id}/ | Paciente | 403 |
