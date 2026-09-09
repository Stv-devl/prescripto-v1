"""Email service — sends password reset emails via SMTP, console only in local."""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_reset_email(to: str, reset_url: str) -> None:
    """Send a password reset email. Falls back to console logging if SMTP is not configured."""
    if settings.smtp_host:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = "Prescripto — Réinitialisation de votre mot de passe"

        html = (
            "<html><body>"
            "<h2>Réinitialisation de mot de passe</h2>"
            "<p>Vous avez demandé la réinitialisation de votre mot de passe Prescripto.</p>"
            f'<p><a href="{reset_url}">Cliquez ici pour réinitialiser votre mot de passe</a></p>'
            "<p>Ce lien est valable 30 minutes.</p>"
            "<p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>"
            "<br><p>— L'équipe Prescripto</p>"
            "</body></html>"
        )
        msg.attach(MIMEText(html, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                start_tls=True,
            )
        except Exception:
            logger.exception("Reset email delivery failed for %s", to)
            return
        logger.info("Password reset email sent to %s", to)
    elif settings.dev_mode:
        logger.info("PASSWORD RESET LINK for %s: %s", to, reset_url)
    else:
        logger.error("SMTP is not configured: the reset email for %s was not sent", to)
