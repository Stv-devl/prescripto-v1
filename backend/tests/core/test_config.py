"""Unit tests for configuration-derived startup warnings.

The lifespan that emits this warning is unreachable from the test harness:
tests/api/test_auth.py builds TestClient(app) without a `with` block, so
starlette never runs it. The pure function is what carries the behaviour, and
what is tested here.
"""

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEV_SEED_EMAIL,
    Settings,
    effective_admin_emails,
    email_delivery_warning,
)

_BASE = {
    "database_url": "postgresql+asyncpg://u:p@db.example.test/prescripto",
    "jwt_secret_key": "test-jwt-secret-key-32-characters-min",
    "mistral_api_key": "test-mistral-key-never-called",
    # Every deployed case below would otherwise fail the rate-limit validator
    # before reaching its own assertion. Its own cases override it.
    "forwarded_allow_ips": "10.0.0.0/8",
    # Same reasoning, for the Qdrant Cloud key validator.
    "qdrant_api_key": "test-qdrant-key-never-called",
    # Same reasoning, for the LangSmith tracing validator (langsmith_tracing
    # defaults to true, cf. TestLangSmithTracing below).
    "langsmith_api_key": "test-langsmith-key-never-called",
}


def _settings(**overrides: object) -> Settings:
    return Settings(**{**_BASE, **overrides})


class TestEmailDeliveryWarning:
    def test_silent_when_smtp_is_configured(self) -> None:
        s = _settings(environment="production", smtp_host="smtp.example.test")

        assert email_delivery_warning(s) is None

    def test_silent_in_local_even_without_smtp(self) -> None:
        """A developer running without SMTP is in a normal state, not a degraded one."""
        s = _settings(environment="local", smtp_host="")

        assert email_delivery_warning(s) is None

    def test_names_the_consequence_when_deployed_without_smtp(self) -> None:
        s = _settings(environment="production", smtp_host="")

        warning = email_delivery_warning(s)

        assert warning is not None
        assert "password reset is inoperative" in warning
        assert "production" in warning


class TestAdminEmailsSurvivesAnEmptyVariable:
    def test_a_variable_set_to_the_empty_string_still_builds_settings(
        self, monkeypatch: object
    ) -> None:
        """The whole reason the field is a str and not a list[str].

        This case only bites through the environment source: passing a keyword
        argument bypasses the JSON decoding entirely. Declared as list[str],
        pydantic-settings raises SettingsError here — while Settings() is being
        built, therefore at import, before logging.basicConfig has run. A
        deployment that sets ADMIN_EMAILS= empty is a normal deployment.
        """
        monkeypatch.setenv("ADMIN_EMAILS", "")

        s = Settings(**_BASE, environment="production")

        assert effective_admin_emails(s) == frozenset()

    def test_an_absent_variable_grants_nobody_when_deployed(self, monkeypatch: object) -> None:
        # Passed as a keyword, not cleared from the environment: Settings also
        # reads backend/.env, which delenv cannot reach, so a developer whose
        # own file names an operator turned this case red for a reason that had
        # nothing to do with the code. The keyword source has priority.
        # The sibling case above is the one that exercises the environment.
        s = _settings(environment="production", admin_emails="")

        assert effective_admin_emails(s) == frozenset()


class TestEffectiveAdminEmails:
    def test_splits_on_comma_and_semicolon_and_trims(self) -> None:
        s = _settings(
            environment="production",
            admin_emails=" boss@cabinet.fr ,  ops@cabinet.fr ; audit@cabinet.fr ",
        )

        assert effective_admin_emails(s) == frozenset(
            {"boss@cabinet.fr", "ops@cabinet.fr", "audit@cabinet.fr"}
        )

    def test_empty_segments_do_not_become_an_empty_address(self) -> None:
        """A trailing separator is a typo, not a request to grant the empty address."""
        s = _settings(environment="production", admin_emails="boss@cabinet.fr,,;  ,")

        assert effective_admin_emails(s) == frozenset({"boss@cabinet.fr"})

    def test_the_domain_is_lowered_and_the_local_part_is_not(self) -> None:
        """The two sides of the comparison must normalise identically.

        EmailStr lowers the domain of every address that reaches signup and
        leaves the local part alone (measured on pydantic 2.13). An entry
        written Boss@Cabinet.FR would otherwise match nothing and promote
        nobody, saying so only in a log line. The local part stays
        case-sensitive: folding it would let an account registered as
        Boss@cabinet.fr be promoted by the entry boss@cabinet.fr.
        """
        s = _settings(environment="production", admin_emails="Boss@Cabinet.FR")

        assert effective_admin_emails(s) == frozenset({"Boss@cabinet.fr"})

    def test_an_entry_with_no_at_sign_is_left_alone_rather_than_crashing(self) -> None:
        """A typo must not take the startup down; it comes back as unknown."""
        s = _settings(environment="production", admin_emails="not-an-address")

        assert effective_admin_emails(s) == frozenset({"not-an-address"})

    def test_the_seeded_developer_account_is_granted_in_local(self) -> None:
        """This is what lets _seed_dev_data stop writing the role itself."""
        s = _settings(environment="local", admin_emails="")

        assert effective_admin_emails(s) == frozenset({DEV_SEED_EMAIL})

    def test_the_seeded_developer_account_is_not_granted_when_deployed(self) -> None:
        s = _settings(environment="production", admin_emails="boss@cabinet.fr")

        assert DEV_SEED_EMAIL not in effective_admin_emails(s)


class TestDeployedRefusesAnUnusableRateLimitKey:
    """The rate limit's key is request.client.host, and nothing else decides it.

    uvicorn honours X-Forwarded-For only from the addresses FORWARDED_ALLOW_IPS
    lists, whose effective default is 127.0.0.1 — never a reverse proxy that
    reaches the app over a container network. Deployed that way, every visitor
    resolves to the proxy's address and the first burst locks all of them out.
    """

    def test_an_unset_variable_refuses_to_start_and_names_itself(self) -> None:
        with pytest.raises(ValidationError) as refusal:
            _settings(environment="production", forwarded_allow_ips="")

        assert "FORWARDED_ALLOW_IPS" in str(refusal.value)

    def test_the_uvicorn_default_is_refused_too(self) -> None:
        """127.0.0.1 is exactly the value that ignores the proxy, not a fix."""
        with pytest.raises(ValidationError):
            _settings(environment="production", forwarded_allow_ips="127.0.0.1")

    def test_a_wildcard_is_refused(self) -> None:
        """Measured: with '*', uvicorn trusts the leftmost X-Forwarded-For, so
        the caller writes the rate-limit key. The limit stops applying to them
        and starts applying to whichever address they name."""
        with pytest.raises(ValidationError):
            _settings(environment="production", forwarded_allow_ips="*")

    def test_a_zero_length_prefix_is_refused(self) -> None:
        """0.0.0.0/0 and ::/0 reach the same uvicorn branch as '*'."""
        for everything in ("0.0.0.0/0", "::/0"):
            with pytest.raises(ValidationError):
                _settings(environment="production", forwarded_allow_ips=everything)

    def test_a_value_that_is_not_an_address_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            _settings(environment="production", forwarded_allow_ips="traefik")

    def test_a_list_of_networks_starts(self) -> None:
        s = _settings(environment="production", forwarded_allow_ips="172.18.0.0/16, 10.0.0.1")

        assert s.forwarded_allow_ips == "172.18.0.0/16, 10.0.0.1"

    def test_a_named_proxy_starts(self) -> None:
        s = _settings(environment="production", forwarded_allow_ips="10.0.0.0/8")

        assert s.forwarded_allow_ips == "10.0.0.0/8"

    def test_local_never_refuses(self) -> None:
        """A developer runs without a proxy at all; the key is already the client."""
        assert _settings(environment="local", forwarded_allow_ips="").environment == "local"


class TestLangSmithTracing:
    """langsmith_tracing defaults to true (J1: active everywhere, including AWS)."""

    def test_tracing_defaults_to_true(self) -> None:
        assert _settings().langsmith_tracing is True

    def test_deployed_without_a_key_refuses_and_names_itself(self) -> None:
        with pytest.raises(ValidationError) as refusal:
            _settings(environment="production", langsmith_api_key="")

        assert "LANGSMITH_API_KEY" in str(refusal.value)

    def test_deployed_with_a_whitespace_only_key_refuses_too(self) -> None:
        """A blank-but-non-empty value (e.g. a templating bug) is truthy in
        Python — the check must strip before judging it present."""
        with pytest.raises(ValidationError):
            _settings(environment="production", langsmith_api_key="   ")

    def test_deployed_with_a_key_starts(self) -> None:
        s = _settings(environment="production", langsmith_api_key="a-real-key")

        assert s.langsmith_api_key == "a-real-key"

    def test_deployed_with_tracing_disabled_does_not_require_a_key(self) -> None:
        s = _settings(environment="production", langsmith_tracing=False, langsmith_api_key="")

        assert s.langsmith_tracing is False

    def test_local_never_refuses_even_without_a_key(self) -> None:
        s = _settings(environment="local", langsmith_api_key="")

        assert s.environment == "local"


class TestRetrievalMode:
    """The sprint A/B switch (sprint/PLAN-SPRINT.md § 2): baseline stays the default."""

    def test_defaults_to_baseline(self) -> None:
        assert _settings().retrieval_mode == "baseline"

    def test_accepts_v1(self) -> None:
        assert _settings(retrieval_mode="v1").retrieval_mode == "v1"

    def test_refuses_an_unknown_mode(self) -> None:
        with pytest.raises(ValidationError):
            _settings(retrieval_mode="not-a-mode")
