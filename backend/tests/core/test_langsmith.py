import os

from app.core.config import Settings
from app.core.langsmith import configure_langsmith

_BASE = {
    "database_url": "postgresql+asyncpg://u:p@db.example.test/prescripto",
    "jwt_secret_key": "test-jwt-secret-key-32-characters-min",
    "mistral_api_key": "test-mistral-key-never-called",
    "forwarded_allow_ips": "10.0.0.0/8",
    "qdrant_api_key": "test-qdrant-key-never-called",
}


class TestConfigureLangsmith:
    def test_sets_the_four_env_vars_from_settings(self) -> None:
        s = Settings(
            **_BASE,
            langsmith_tracing=True,
            langsmith_api_key="a-real-key",
            langsmith_project="prescripto-test",
            langsmith_endpoint="https://eu.api.smith.langchain.com",
        )

        configure_langsmith(s)

        assert os.environ["LANGSMITH_TRACING"] == "true"
        assert os.environ["LANGSMITH_API_KEY"] == "a-real-key"
        assert os.environ["LANGSMITH_PROJECT"] == "prescripto-test"
        assert os.environ["LANGSMITH_ENDPOINT"] == "https://eu.api.smith.langchain.com"

    def test_tracing_wanted_but_whitespace_only_key_still_writes_false(self) -> None:
        """A blank-but-non-empty key is truthy in Python — must be stripped."""
        s = Settings(**_BASE, environment="local", langsmith_tracing=True, langsmith_api_key="   ")

        configure_langsmith(s)

        assert os.environ["LANGSMITH_TRACING"] == "false"

    def test_endpoint_defaults_to_the_eu_region(self) -> None:
        """This workspace is EU-hosted — the SDK's own default 403s here."""
        s = Settings(**_BASE, langsmith_api_key="a-real-key")

        configure_langsmith(s)

        assert os.environ["LANGSMITH_ENDPOINT"] == "https://eu.api.smith.langchain.com"

    def test_tracing_disabled_writes_the_string_false(self) -> None:
        s = Settings(**_BASE, langsmith_tracing=False, langsmith_api_key="")

        configure_langsmith(s)

        assert os.environ["LANGSMITH_TRACING"] == "false"

    def test_tracing_wanted_but_no_key_still_writes_false(self) -> None:
        """Avoids a real (always-401) network call per traced call in local/tests.

        environment="local" because _deployed_is_locked_down would otherwise
        refuse this exact combination (tracing on, no key) outside local.
        """
        s = Settings(**_BASE, environment="local", langsmith_tracing=True, langsmith_api_key="")

        configure_langsmith(s)

        assert os.environ["LANGSMITH_TRACING"] == "false"
