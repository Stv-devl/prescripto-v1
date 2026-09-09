"""Unit tests for the password-reset email service.

Two setup lines appear in every case and neither is optional.

`caplog.set_level(logging.DEBUG, logger=_LOGGER)` — run on its own, this file
sees root=WARNING and app=NOTSET, because `app.main` (which raises the levels)
is not in the conftest import chain. Without it `caplog.records` is empty and
every "nothing was logged" assertion passes on broken code. DEBUG rather than
INFO: the criterion is "at no level", and a leak downgraded to logger.debug
would slip past a capture armed at INFO.

`monkeypatch.setattr(settings, "environment", ...)` — `dev_mode` is a property
with no setter, so it cannot be patched directly, and conftest pins
ENVIRONMENT=local for the whole suite. Moving `environment` is the only way to
reach the deployed branch at all.
"""

import logging
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from app.services.email import send_reset_email

_LOGGER = "app.services.email"
_TOKEN = "secret-token-value"
_URL = f"https://prescripto.fr/reset-password?token={_TOKEN}"
_TO = "eco@cabinet.fr"


class TestWithoutSmtpConfigured:
    async def test_deployed_no_record_carries_the_url_or_the_token(
        self, caplog: object, monkeypatch: object
    ) -> None:
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "smtp_host", "")
        caplog.set_level(logging.DEBUG, logger=_LOGGER)

        await send_reset_email(_TO, _URL)

        assert _URL not in caplog.text
        assert _TOKEN not in caplog.text

    async def test_deployed_an_error_names_the_recipient_and_not_the_link(
        self, caplog: object, monkeypatch: object
    ) -> None:
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "smtp_host", "")
        caplog.set_level(logging.DEBUG, logger=_LOGGER)

        await send_reset_email(_TO, _URL)

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert _TO in errors[0].getMessage()
        assert _TOKEN not in errors[0].getMessage()

    async def test_local_still_logs_the_link(
        self, caplog: object, monkeypatch: object
    ) -> None:
        """The console fallback is how the flow is exercised on a dev machine."""
        monkeypatch.setattr(settings, "environment", "local")
        monkeypatch.setattr(settings, "smtp_host", "")
        caplog.set_level(logging.DEBUG, logger=_LOGGER)

        await send_reset_email(_TO, _URL)

        assert _URL in caplog.text


class TestWithSmtpConfigured:
    async def test_the_message_is_handed_to_the_transport_and_not_logged(
        self, caplog: object, monkeypatch: object
    ) -> None:
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
        caplog.set_level(logging.DEBUG, logger=_LOGGER)

        with patch(
            "app.services.email.aiosmtplib.send", new_callable=AsyncMock
        ) as transport:
            await send_reset_email(_TO, _URL)

        assert transport.await_count == 1
        message = transport.await_args.args[0]
        assert message["To"] == _TO
        body = message.get_payload(0).get_payload(decode=True).decode()
        assert _URL in body
        assert _URL not in caplog.text

    async def test_a_transport_failure_does_not_escape_or_log_the_link(
        self, caplog: object, monkeypatch: object
    ) -> None:
        """An escaping exception would answer 500 for a known address and 200
        for an unknown one — the account-existence oracle, rebuilt one endpoint
        over. The failure is recorded; the link still is not."""
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
        caplog.set_level(logging.DEBUG, logger=_LOGGER)

        with patch(
            "app.services.email.aiosmtplib.send",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("relay down"),
        ):
            await send_reset_email(_TO, _URL)

        assert _TOKEN not in caplog.text
        assert any(r.levelno == logging.ERROR for r in caplog.records)
