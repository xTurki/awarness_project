"""Outbound mail, sent inline but off the event loop.

`smtplib` blocks, so calling it directly would stall every other request for its
duration. A worker thread keeps it off the loop while remaining inline, so the
person sees the outcome rather than being sent to a page waiting for a code that
never left (research R8).

This module raises a domain exception and knows nothing about HTTP (Principle II).
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

import anyio

from app.config import settings


class EmailDeliveryFailed(Exception):
    """The message did not go. The caller must surface this, never swallow it."""


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
    """Bounded by the SMTP timeout, so a mail outage is reported in seconds
    rather than leaving the person waiting (FR-021)."""
    try:
        await anyio.to_thread.run_sync(_send_blocking, to, subject, body)
    except Exception as exc:  # noqa: BLE001 - every failure is the same failure here
        raise EmailDeliveryFailed(str(exc)) from exc
