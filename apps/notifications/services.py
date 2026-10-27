"""Email notification services for MedBook.

All functions receive a fully hydrated Appointment instance and send
a transactional email to the patient via Django's email backend.

Backends per environment:
  - local:  django.core.mail.backends.console.EmailBackend  (prints to stdout)
  - test:   django.core.mail.backends.locmem.EmailBackend   (mail.outbox)
  - prod:   anymail.backends.resend.EmailBackend            (Resend API)

appointments.services calls them through transaction.on_commit(), so an
email failure never rolls back the booking, confirmation or cancellation.

Language and time (Paso 37): every email is in the clinic's language
(LANGUAGE_CODE, Spanish), whatever language the request that triggered it
had. The API always runs in English (EnglishApiMiddleware), and the doctor
confirms through it. The time is Chilean (TIME_ZONE, ADR 0003). The text
lives in templates/notifications/*.txt.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from apps.core.utils import moment_of

CREATED_SUBJECT = _("Booking received — MedBook")
CONFIRMED_SUBJECT = _("Appointment confirmed — MedBook")
CANCELLED_SUBJECT = _("Appointment cancelled — MedBook")


def send_appointment_created(appointment) -> None:
    """Notify the patient that their appointment booking has been received.

    Triggered by: appointments.services.create_appointment()
    """
    _send_to_patient(
        appointment, CREATED_SUBJECT, "notifications/appointment_created.txt"
    )


def send_appointment_confirmed(appointment) -> None:
    """Notify the patient that their appointment has been confirmed.

    Triggered by: appointments.services.confirm_appointment()
    """
    _send_to_patient(
        appointment, CONFIRMED_SUBJECT, "notifications/appointment_confirmed.txt"
    )


def send_appointment_cancelled(appointment) -> None:
    """Notify the patient that their appointment has been cancelled.

    Triggered by: appointments.services.cancel_appointment()
    """
    _send_to_patient(
        appointment, CANCELLED_SUBJECT, "notifications/appointment_cancelled.txt"
    )


def _send_to_patient(appointment, subject, template_name) -> None:
    """Render one email in the clinic's language and send it to the patient."""
    user = appointment.patient.user
    with translation.override(settings.LANGUAGE_CODE):
        context = {
            "patient_name": user.first_name,
            "doctor": str(appointment.doctor),
            "moment": moment_of(appointment.slot),
        }
        send_mail(
            subject=str(subject),
            message=render_to_string(template_name, context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
