import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone, translation

from apps.appointments.models import Appointment, InvalidTransition, TimeSlot
from apps.doctors.models import Doctor, Specialty
from apps.users.models import Role
from tests.factories import (
    AppointmentFactory,
    DoctorFactory,
    PatientFactory,
    SpecialtyFactory,
    TimeSlotFactory,
    UserFactory,
    random_password,
)

User = get_user_model()


class TestUserModel:
    """Test User model."""

    def test_create_user_with_email(self, db):
        """Test creating a regular user with email."""
        user = UserFactory(email="test@example.com")
        assert user.email == "test@example.com"
        assert user.check_password(user.raw_password)
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
        password = random_password()
        user = User.objects.create_user(email="mgr@example.com", password=password)
        assert user.email == "mgr@example.com"
        assert user.check_password(password)
        assert not user.is_staff
        assert not user.is_superuser

    def test_manager_create_user_requires_email(self, db):
        """Test UserManager.create_user raises ValueError when email is empty."""
        with pytest.raises(ValueError, match="Email field must be set"):
            User.objects.create_user(email="", password=random_password())

    def test_manager_create_superuser(self, db):
        """Test UserManager.create_superuser sets staff and superuser flags."""
        admin = User.objects.create_superuser(
            email="admin@example.com", password=random_password()
        )
        assert admin.is_staff
        assert admin.is_superuser
        assert admin.role == Role.ADMIN

    def test_manager_create_superuser_requires_is_staff(self, db):
        """Test UserManager.create_superuser raises if is_staff=False."""
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="bad@example.com", password=random_password(), is_staff=False
            )

    def test_manager_create_superuser_requires_is_superuser(self, db):
        """Test UserManager.create_superuser raises if is_superuser=False."""
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="bad@example.com", password=random_password(), is_superuser=False
            )


@pytest.mark.django_db
class TestUserEmailCase:
    """An email is one account whatever its case (Paso 34).

    The login looks the user up with get_by_natural_key, and the database
    enforces one user per lower-cased email. The email is stored as typed.
    """

    def test_natural_key_lookup_ignores_case(self):
        user = UserFactory(email="ana@example.com")

        assert User.objects.get_by_natural_key("ANA@Example.com") == user

    def test_email_is_stored_as_typed_with_a_lowercase_domain(self):
        user = User.objects.create_user(
            email="Ana.Perez@Example.COM", password=random_password()
        )

        assert user.email == "Ana.Perez@example.com"

    def test_database_rejects_the_same_email_in_another_case(self):
        UserFactory(email="ana@example.com")

        with pytest.raises(IntegrityError), transaction.atomic():
            UserFactory(email="ANA@example.com")


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

    def test_title_defaults_to_dr(self, db):
        """Existing doctors keep the "Dr." they always had (Paso 36)."""
        assert DoctorFactory().title == Doctor.Title.DR

    @pytest.mark.parametrize(
        ("title", "spanish", "english"),
        [
            ("dr", "Dr. Carla Soto", "Dr. Carla Soto"),
            ("dra", "Dra. Carla Soto", "Dr. Carla Soto"),
        ],
    )
    def test_str_uses_the_title_in_the_active_language(
        self, db, title, spanish, english
    ):
        """Spanish tells Dr. from Dra.; English says Dr. for both."""
        doctor = DoctorFactory(
            title=title, user__first_name="Carla", user__last_name="Soto"
        )

        assert str(doctor) == spanish
        with translation.override("en"):
            assert str(doctor) == english

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

    def test_display_name_translates_seeded_names(self, db):
        """Seeded names are stored in English; the web shows them translated."""
        cardiology = SpecialtyFactory(name="Cardiology", slug="cardiology")

        assert cardiology.display_name == "Cardiología"
        with translation.override("en"):
            assert cardiology.display_name == "Cardiology"

    def test_display_name_falls_back_to_stored_name(self, db):
        specialty = SpecialtyFactory(name="Sleep Medicine", slug="sleep-medicine")

        assert specialty.display_name == "Sleep Medicine"


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

    @pytest.mark.parametrize(
        ("minutes", "started"),
        [(-1, True), (1, False)],
        ids=["a-minute-ago", "in-a-minute"],
    )
    def test_has_started(self, db, minutes, started):
        """A slot has started once its start time is not in the future."""
        slot = TimeSlotFactory(
            start_datetime=timezone.now() + datetime.timedelta(minutes=minutes)
        )

        assert slot.has_started is started


def started_slot():
    """A slot that started a minute ago."""
    return TimeSlotFactory(
        start_datetime=timezone.now() - datetime.timedelta(minutes=1)
    )


class TestAppointmentModel:
    """Test Appointment model and state machine."""

    def test_create_appointment(self, db):
        """Test creating an appointment with factory."""
        appt = AppointmentFactory()
        assert appt.id is not None
        assert appt.status == Appointment.Status.PENDING

    @pytest.mark.parametrize(
        "status", [Appointment.Status.PENDING, Appointment.Status.CONFIRMED]
    )
    def test_slot_holds_one_active_appointment_at_most(self, db, status):
        """The DB rejects a second pending/confirmed appointment on a slot."""
        active = AppointmentFactory(status=Appointment.Status.CONFIRMED)

        with pytest.raises(IntegrityError), transaction.atomic():
            AppointmentFactory(slot=active.slot, status=status)

    @pytest.mark.parametrize(
        "status",
        [
            Appointment.Status.CANCELLED,
            Appointment.Status.COMPLETED,
            Appointment.Status.NO_SHOW,
        ],
    )
    def test_slot_keeps_the_history_of_inactive_appointments(self, db, status):
        """Inactive appointments stay linked to the slot and do not hold it."""
        old = AppointmentFactory(status=status)
        another_old = AppointmentFactory(slot=old.slot, status=status)

        new = AppointmentFactory(slot=old.slot, status=Appointment.Status.PENDING)

        assert set(old.slot.appointments.all()) == {old, another_old, new}

    @pytest.mark.parametrize(
        ("status", "spanish", "english"),
        [
            (Appointment.Status.PENDING, "Pendiente", "Pending"),
            (Appointment.Status.CONFIRMED, "Confirmada", "Confirmed"),
            (Appointment.Status.CANCELLED, "Cancelada", "Cancelled"),
            (Appointment.Status.COMPLETED, "Completada", "Completed"),
            (Appointment.Status.NO_SHOW, "No asistió", "No Show"),
        ],
    )
    def test_status_label_follows_the_active_language(
        self, db, status, spanish, english
    ):
        """The web shows the status translated; the stored value never changes."""
        appt = AppointmentFactory(status=status)

        assert appt.get_status_display() == spanish
        with translation.override("en"):
            assert appt.get_status_display() == english

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

    @pytest.mark.parametrize(
        "status", [Appointment.Status.PENDING, Appointment.Status.CONFIRMED]
    )
    def test_cannot_be_cancelled_once_its_slot_started(self, db, status):
        """It ends with complete() or mark_no_show() instead (Paso 35)."""
        appt = AppointmentFactory(slot=started_slot(), status=status)
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

    def test_cancel_raises_once_its_slot_started(self, db):
        appt = AppointmentFactory(
            slot=started_slot(), status=Appointment.Status.CONFIRMED
        )
        with pytest.raises(InvalidTransition, match="already started"):
            appt.cancel()
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CONFIRMED

    def test_cancel_of_a_closed_appointment_names_its_status(self, db):
        """Completed after it started: the status is the reason, not the time."""
        appt = AppointmentFactory(
            slot=started_slot(), status=Appointment.Status.COMPLETED
        )
        with pytest.raises(InvalidTransition, match="status 'completed'"):
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

    # --- COMPLETED is a terminal state ---

    def test_confirm_raises_if_completed(self, db):
        """COMPLETED appointment cannot be confirmed."""
        appt = AppointmentFactory(status=Appointment.Status.COMPLETED)
        with pytest.raises(ValueError):
            appt.confirm()

    def test_complete_raises_if_completed(self, db):
        """COMPLETED appointment cannot be completed again."""
        appt = AppointmentFactory(status=Appointment.Status.COMPLETED)
        with pytest.raises(ValueError):
            appt.complete()

    def test_mark_no_show_raises_if_completed(self, db):
        """COMPLETED appointment cannot be marked no-show."""
        appt = AppointmentFactory(status=Appointment.Status.COMPLETED)
        with pytest.raises(ValueError):
            appt.mark_no_show()

    # --- NO_SHOW is a terminal state ---

    def test_confirm_raises_if_no_show(self, db):
        """NO_SHOW appointment cannot be confirmed."""
        appt = AppointmentFactory(status=Appointment.Status.NO_SHOW)
        with pytest.raises(ValueError):
            appt.confirm()

    def test_cancel_raises_if_no_show(self, db):
        """NO_SHOW appointment cannot be cancelled."""
        appt = AppointmentFactory(status=Appointment.Status.NO_SHOW)
        with pytest.raises(ValueError):
            appt.cancel()

    def test_complete_raises_if_no_show(self, db):
        """NO_SHOW appointment cannot be completed."""
        appt = AppointmentFactory(status=Appointment.Status.NO_SHOW)
        with pytest.raises(ValueError):
            appt.complete()

    def test_mark_no_show_raises_if_already_no_show(self, db):
        """NO_SHOW appointment cannot be marked no-show again."""
        appt = AppointmentFactory(status=Appointment.Status.NO_SHOW)
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
