import pytest
from django.contrib.auth import get_user_model

from apps.appointments.models import Appointment, TimeSlot
from apps.doctors.models import Specialty
from apps.users.models import Role
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    MedicalNoteFactory,
    PatientFactory,
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

    def test_create_time_slot(self, db):
        """Test creating a time slot."""
        slot = TimeSlotFactory()
        assert slot.id is not None
        assert slot.status == TimeSlot.Status.AVAILABLE
        assert slot.start_datetime < slot.end_datetime

    def test_time_slot_str(self, db):
        """Test __str__ returns doctor name and datetime."""
        slot = TimeSlotFactory()
        assert str(slot).startswith("Dr.")
        assert str(slot.status) == "available"


class TestAppointmentModel:
    """Test Appointment model — creation and state machine."""

    def test_create_appointment(self, db):
        """Test creating an appointment with pending status."""
        appointment = AppointmentFactory()
        assert appointment.id is not None
        assert appointment.status == Appointment.Status.PENDING

    def test_appointment_str(self, db):
        """Test __str__ returns patient, doctor and datetime."""
        appointment = AppointmentFactory()
        result = str(appointment)
        assert "↔" in result

    # ------------------------------------------------------------------
    # Status machine — can_* checks
    # ------------------------------------------------------------------

    def test_can_confirm_from_pending(self, db):
        """Test can_be_confirmed is True when pending."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appointment.can_be_confirmed() is True

    def test_cannot_confirm_from_confirmed(self, db):
        """Test can_be_confirmed is False when already confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appointment.can_be_confirmed() is False

    def test_can_cancel_from_pending(self, db):
        """Test can_be_cancelled is True when pending."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appointment.can_be_cancelled() is True

    def test_can_cancel_from_confirmed(self, db):
        """Test can_be_cancelled is True when confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appointment.can_be_cancelled() is True

    def test_cannot_cancel_from_completed(self, db):
        """Test can_be_cancelled is False when completed."""
        appointment = AppointmentFactory(status=Appointment.Status.COMPLETED)
        assert appointment.can_be_cancelled() is False

    def test_cannot_cancel_from_no_show(self, db):
        """Test can_be_cancelled is False when no_show."""
        appointment = AppointmentFactory(status=Appointment.Status.NO_SHOW)
        assert appointment.can_be_cancelled() is False

    def test_can_complete_from_confirmed(self, db):
        """Test can_be_completed is True when confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appointment.can_be_completed() is True

    def test_cannot_complete_from_pending(self, db):
        """Test can_be_completed is False when pending."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appointment.can_be_completed() is False

    def test_cannot_complete_from_cancelled(self, db):
        """Test can_be_completed is False when cancelled."""
        appointment = AppointmentFactory(status=Appointment.Status.CANCELLED)
        assert appointment.can_be_completed() is False

    def test_can_mark_no_show_from_confirmed(self, db):
        """Test can_be_marked_no_show is True when confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        assert appointment.can_be_marked_no_show() is True

    def test_cannot_mark_no_show_from_pending(self, db):
        """Test can_be_marked_no_show is False when pending."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        assert appointment.can_be_marked_no_show() is False

    # ------------------------------------------------------------------
    # Status machine — transitions
    # ------------------------------------------------------------------

    def test_confirm_transition(self, db):
        """Test confirm changes status from pending to confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        appointment.confirm()
        appointment.refresh_from_db()
        assert appointment.status == Appointment.Status.CONFIRMED

    def test_confirm_wrong_status_raises(self, db):
        """Test confirm raises ValueError when not pending."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        with pytest.raises(ValueError, match="Cannot confirm"):
            appointment.confirm()

    def test_cancel_transition(self, db):
        """Test cancel changes status to cancelled."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        appointment.cancel()
        appointment.refresh_from_db()
        assert appointment.status == Appointment.Status.CANCELLED

    def test_cancel_wrong_status_raises(self, db):
        """Test cancel raises ValueError when not cancellable."""
        appointment = AppointmentFactory(status=Appointment.Status.COMPLETED)
        with pytest.raises(ValueError, match="Cannot cancel"):
            appointment.cancel()

    def test_complete_transition(self, db):
        """Test complete changes status from confirmed to completed."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        appointment.complete()
        appointment.refresh_from_db()
        assert appointment.status == Appointment.Status.COMPLETED

    def test_complete_wrong_status_raises(self, db):
        """Test complete raises ValueError when not confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        with pytest.raises(ValueError, match="Cannot complete"):
            appointment.complete()

    def test_mark_no_show_transition(self, db):
        """Test mark_no_show changes status from confirmed to no_show."""
        appointment = AppointmentFactory(status=Appointment.Status.CONFIRMED)
        appointment.mark_no_show()
        appointment.refresh_from_db()
        assert appointment.status == Appointment.Status.NO_SHOW

    def test_mark_no_show_wrong_status_raises(self, db):
        """Test mark_no_show raises ValueError when not confirmed."""
        appointment = AppointmentFactory(status=Appointment.Status.PENDING)
        with pytest.raises(ValueError, match="Cannot mark no-show"):
            appointment.mark_no_show()


class TestMedicalNoteModel:
    """Test MedicalNote model."""

    def test_create_medical_note(self, db):
        """Test creating a medical note."""
        note = MedicalNoteFactory()
        assert note.id is not None
        assert note.content != ""

    def test_medical_note_str(self, db):
        """Test __str__ returns author email and appointment ref."""
        note = MedicalNoteFactory()
        result = str(note)
        assert note.author.email in result
        """Test slug must be unique at DB level."""
        SpecialtyFactory(slug="unique-slug")
        with pytest.raises(Exception):
            Specialty.objects.create(name="Duplicate", slug="unique-slug")
