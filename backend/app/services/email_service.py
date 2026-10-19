"""Sending email over SMTP.

`smtplib` is blocking, so the async version runs it in a thread.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

import anyio

from app.config import settings


class EmailDeliveryFailed(Exception):
    """The email could not be sent."""


def _send_blocking(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_app_password)
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> None:
    """Send an email without blocking the event loop."""
    try:
        await anyio.to_thread.run_sync(_send_blocking, to, subject, body)
    except Exception as exc:  # noqa: BLE001 - every failure is the same failure here
        raise EmailDeliveryFailed(str(exc)) from exc


def send_email_now(to: str, subject: str, body: str) -> None:
    """Send an email synchronously (for the daily job and background sender)."""
    try:
        _send_blocking(to, subject, body)
    except Exception as exc:  # noqa: BLE001 - every failure is the same failure here
        raise EmailDeliveryFailed(str(exc)) from exc
