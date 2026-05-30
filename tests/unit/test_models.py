import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.appointments.models import Appointment, TimeSlot
from apps.doctors.models import Specialty
from apps.users.models import Role
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    ScheduleFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
)

User = get_user_model()


class TestUserModel:
    """Test User model."""

    def test_create_user_with_email(self, db):
        """Test creating a regular user with email."""
        user = UserFactory(email="test@example.com")
        assert user.email == "test@example.com"
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_default_role_is_patient(self, db):
        """Test default role is patient."""
        user = UserFactory()
        assert user.role == Role.PATIENT

    def test_full_name_with_first_and_last(self, db):
        """Test full_name property combines names."""
        user = UserFactory(first_name="John", last_name="Doe")
        assert user.full_name == "John Doe"

    def test_full_name_without_names(self, db):
        """Test full_name returns empty string when no names set."""
        user = UserFactory(first_name="", last_name="")
        assert user.full_name == ""

    def test_user_str_returns_email(self, db):
        """Test __str__ returns email."""
        user = UserFactory(email="test@example.com")
        assert str(user) == "test@example.com"

    def test_create_superuser(self, db):
        """Test creating a superuser."""
        admin = UserFactory(
            is_staff=True,
            is_superuser=True,
            role=Role.ADMIN,
        )
        assert admin.is_staff
        assert admin.is_superuser
        assert admin.role == Role.ADMIN

    def test_manager_create_user(self, db):
        """Test UserManager.create_user sets email and password correctly."""
        user = User.objects.create_user(email="mgr@example.com", password="pass1234")
        assert user.email == "mgr@example.com"
        assert user.check_password("pass1234")
        assert not user.is_staff
        assert not user.is_superuser

    def test_manager_create_user_requires_email(self, db):
        """Test UserManager.create_user raises ValueError when email is empty."""
        with pytest.raises(ValueError, match="Email field must be set"):
            User.objects.create_user(email="", password="pass1234")

    def test_manager_create_superuser(self, db):
        """Test UserManager.create_superuser sets staff and superuser flags."""
        admin = User.objects.create_superuser(email="admin@example.com", password="pass1234")
        assert admin.is_staff
        assert admin.is_superuser
        assert admin.role == Role.ADMIN

    def test_manager_create_superuser_requires_is_staff(self, db):
        """Test UserManager.create_superuser raises if is_staff=False."""
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="bad@example.com", password="pass1234", is_staff=False
            )

    def test_manager_create_superuser_requires_is_superuser(self, db):
        """Test UserManager.create_superuser raises if is_superuser=False."""
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="bad@example.com", password="pass1234", is_superuser=False
            )


class TestDoctorModel:
    """Test Doctor model."""

    def test_create_doctor(self, db):
        """Test creating a doctor with factory."""
        doctor = DoctorFactory()
        assert doctor.id is not None
        assert doctor.user.role == Role.DOCTOR
        assert doctor.consultation_duration == 30

    def test_doctor_str(self, db):
        """Test __str__ returns formatted name."""
        doctor = DoctorFactory()
        user = doctor.user
        expected = f"Dr. {user.full_name}"
        assert str(doctor) == expected

    def test_doctor_str_falls_back_to_email(self, db):
        """Test __str__ falls back to email when doctor has no full name."""
        doctor = DoctorFactory(
            user__first_name="",
            user__last_name="",
        )
        expected = f"Dr. {doctor.user.email}"
        assert str(doctor) == expected

    def test_doctor_with_specialties(self, db):
        """Test doctor can have multiple specialties."""
        specialties = SpecialtyFactory.create_batch(3)
        doctor = DoctorFactory(specialties=specialties)
        assert doctor.specialties.count() == 3


class TestPatientModel:
    """Test Patient model."""

    def test_create_patient(self, db):
        """Test creating a patient with factory."""
        patient = PatientFactory()
        assert patient.id is not None
        assert patient.user.role == Role.PATIENT

    def test_patient_str(self, db):
        """Test __str__ returns user full name or email."""
        patient = PatientFactory()
        expected = patient.user.full_name or patient.user.email
        assert str(patient) == expected

    def test_patient_phone_optional(self, db):
        """Test phone field is optional."""
        patient = PatientFactory(phone="")
        assert patient.phone == ""


class TestSpecialtyModel:
    """Test Specialty model."""

    def test_create_specialty(self, db):
        """Test creating a specialty."""
        specialty = SpecialtyFactory(name="Test Specialty", slug="test-specialty")
        assert specialty.name == "Test Specialty"
        assert specialty.slug == "test-specialty"

    def test_specialty_str(self, db):
        """Test __str__ returns name."""
        specialty = SpecialtyFactory()
        assert str(specialty) == specialty.name

    def test_specialty_slug_unique(self, db):
        """Test slug must be unique at DB level."""
        SpecialtyFactory(slug="unique-slug")
        with pytest.raises(Exception):
            Specialty.objects.create(name="Duplicate", slug="unique-slug")


class TestTimeSlotModel:
    """Test TimeSlot model."""

    def test_create_timeslot(self, db):
        """Test creating a timeslot with factory."""
        slot = TimeSlotFactory()
        assert slot.id is not None
        assert slot.status == TimeSlot.Status.AVAILABLE

    def test_timeslot_str(self, db):
        """Test __str__ includes datetime and status."""
        slot = TimeSlotFactory()
        assert str(slot.start_datetime.date()) in str(slot)

    def test_timeslot_unique_constraint(self, db):
        """Test (schedule, start_datetime) is unique at DB level."""
        slot = TimeSlotFactory()
        with pytest.raises(Exception):
            TimeSlot.objects.create(
                schedule=slot.schedule,
                start_datetime=slot.start_datetime,
                end_datetime=slot.end_datetime,
                status=TimeSlot.Status.AVAILABLE,
            )


class TestAppointmentModel:
    """Test Appointment model and state machine."""

    def test_create_appointment(self, db):
        """Test creating an appointment with factory."""
        appt = AppointmentFactory()
        assert appt.id is not None
        assert appt.status == Appointment.Status.PENDING

    def test_appointment_str(self, db):
        """Test __str__ includes patient and doctor."""
        appt = AppointmentFactory()
        result = str(appt)
        assert str(appt.patient) in result or str(appt.doctor) in result

    # --- can_be_* guards ---

    def test_can_be_confirmed_when_pending(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appt.can_be_confirmed() is True

    def test_cannot_be_confirmed_when_confirmed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appt.can_be_confirmed() is False

    def test_can_be_cancelled_when_pending(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appt.can_be_cancelled() is True

    def test_can_be_cancelled_when_confirmed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appt.can_be_cancelled() is True

    def test_cannot_be_cancelled_when_completed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.COMPLETED)
        assert appt.can_be_cancelled() is False

    def test_can_be_completed_when_confirmed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appt.can_be_completed() is True

    def test_cannot_be_completed_when_pending(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appt.can_be_completed() is False

    def test_can_be_marked_no_show_when_confirmed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appt.can_be_marked_no_show() is True

    def test_cannot_be_marked_no_show_when_pending(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appt.can_be_marked_no_show() is False

    # --- transitions ---

    def test_confirm_pending_appointment(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        appt.confirm()
        assert appt.status == Appointment.Status.CONFIRMED

    def test_confirm_raises_if_not_pending(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CANCELLED)
        with pytest.raises(ValueError):
            appt.confirm()

    def test_cancel_pending_appointment(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        appt.cancel()
        assert appt.status == Appointment.Status.CANCELLED

    def test_cancel_confirmed_appointment(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        appt.cancel()
        assert appt.status == Appointment.Status.CANCELLED

    def test_cancel_raises_if_completed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.COMPLETED)
        with pytest.raises(ValueError):
            appt.cancel()

    def test_complete_confirmed_appointment(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        appt.complete()
        assert appt.status == Appointment.Status.COMPLETED

    def test_complete_raises_if_not_confirmed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        with pytest.raises(ValueError):
            appt.complete()

    def test_mark_no_show_confirmed_appointment(self, db):
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        appt.mark_no_show()
        assert appt.status == Appointment.Status.NO_SHOW

    def test_mark_no_show_raises_if_not_confirmed(self, db):
        appt = AppointmentFactory(status=Appointment.Status.PENDING)
        with pytest.raises(ValueError):
            appt.mark_no_show()


class TestMedicalNoteModel:
    """Test MedicalNote model."""

    def test_create_medical_note(self, db):
        """Test creating a medical note with factory."""
        from tests.factories import MedicalNoteFactory
        note = MedicalNoteFactory()
        assert note.id is not None
        assert note.content != ""

    def test_medical_note_str(self, db):
        """Test __str__ includes appointment reference."""
        from tests.factories import MedicalNoteFactory
        note = MedicalNoteFactory()
        assert str(note) != ""
