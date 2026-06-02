"""Email notification services for MedBook.

All functions receive a fully hydrated Appointment instance and send
a transactional email to the patient via Django's email backend.

Backends per environment:
  - local:  django.core.mail.backends.console.EmailBackend  (prints to stdout)
  - test:   django.core.mail.backends.locmem.EmailBackend   (mail.outbox)
  - prod:   anymail.backends.resend.EmailBackend            (Resend API)

Note on transactions: these functions are called inside @transaction.atomic
service wrappers. If email sending raises, the transaction rolls back. In
practice the locmem/console backends never raise, and in production
fail_silently=True is the recommended default for non-critical notifications.
A production-hardened approach would use transaction.on_commit() to defer
the send until the DB transaction commits.
"""

from django.conf import settings
from django.core.mail import send_mail

from apps.core.utils import get_display_name


def send_appointment_created(appointment) -> None:
    """Notify the patient that their appointment booking has been received.

    Triggered by: appointments.services.create_appointment()
    """
    patient_email = appointment.patient.user.email
    patient_name = appointment.patient.user.first_name or "there"
    doctor_name = get_display_name(appointment.doctor.user)
    slot_dt = appointment.slot.start_datetime.strftime("%Y-%m-%d %H:%M UTC")

    send_mail(
        subject="Appointment booking received — MedBook",
        message=(
            f"Hi {patient_name},\n\n"
            f"Your appointment booking with Dr. {doctor_name} has been received.\n"
            f"Date and time: {slot_dt}\n\n"
            f"We will notify you once your appointment is confirmed.\n\n"
            f"— MedBook"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[patient_email],
        fail_silently=False,
    )


def send_appointment_confirmed(appointment) -> None:
    """Notify the patient that their appointment has been confirmed.

    Triggered by: appointments.services.confirm_appointment()
    """
    patient_email = appointment.patient.user.email
    patient_name = appointment.patient.user.first_name or "there"
    doctor_name = get_display_name(appointment.doctor.user)
    slot_dt = appointment.slot.start_datetime.strftime("%Y-%m-%d %H:%M UTC")

    send_mail(
        subject="Appointment confirmed — MedBook",
        message=(
            f"Hi {patient_name},\n\n"
            f"Your appointment with Dr. {doctor_name} has been confirmed.\n"
            f"Date and time: {slot_dt}\n\n"
            f"Please arrive 10 minutes early.\n\n"
            f"— MedBook"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[patient_email],
        fail_silently=False,
    )


def send_appointment_cancelled(appointment) -> None:
    """Notify the patient that their appointment has been cancelled.

    Triggered by: appointments.services.cancel_appointment()
    """
    patient_email = appointment.patient.user.email
    patient_name = appointment.patient.user.first_name or "there"
    doctor_name = get_display_name(appointment.doctor.user)
    slot_dt = appointment.slot.start_datetime.strftime("%Y-%m-%d %H:%M UTC")

    send_mail(
        subject="Appointment cancelled — MedBook",
        message=(
            f"Hi {patient_name},\n\n"
            f"Your appointment with Dr. {doctor_name} on {slot_dt} has been cancelled.\n\n"
            f"You can book a new appointment at any time through MedBook.\n\n"
            f"— MedBook"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[patient_email],
        fail_silently=False,
    )
