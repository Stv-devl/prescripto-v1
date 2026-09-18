"""Application settings, loaded and validated at import time.

DEV_SEED_EMAIL is the seeded developer account: main.py creates it and
effective_admin_emails() grants it admin in local. Kept here so main.py
imports the same constant instead of a second spelling.
"""

import ipaddress
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

DEV_SEED_EMAIL = "dev@prescripto.fr"

_PLACEHOLDER_SECRETS = frozenset(
    {
        "change-me-in-production-min-32-chars",
        "your_secret_key_min_32_chars",
        "changeme",
        "secret",
    }
)


class Settings(BaseSettings):
    environment: Literal["local", "staging", "production"] = Field(
        default="production",
        description=(
            '"local" is the only value that unlocks developer shortcuts. '
            "Defaults to production so a missing variable can never open the API."
        ),
    )

    database_url: str = Field(
        default="postgresql+asyncpg://prescripto:prescripto_dev_local@localhost:5432/prescripto",
        description=(
            "Defaults to the local docker-compose stack; staging and "
            "production must override it (enforced below)."
        ),
    )

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = Field(
        default="",
        description="Required by Qdrant Cloud; the local docker-compose instance has no auth.",
    )

    retrieval_mode: Literal["baseline", "v1"] = Field(
        default="baseline",
        description=(
            "Selects the Qdrant collection: baseline -> 'documents', "
            "v1 -> 'documents_v1'. The sprint A/B switch (sprint/PLAN-SPRINT.md "
            "§ 2) — both stay runnable at any time, the baseline collection is "
            "never overwritten by a v1 re-ingestion."
        ),
    )

    mistral_api_key: str
    pixtral_large_model: str = "pixtral-large-latest"
    pixtral_small_model: str = "pixtral-12b-2409"
    vision_dpi: int = 200
    vision_plan_dpi: int = 400
    max_vision_pages: int = 50

    jwt_secret_key: str = Field(
        description="No default: a fallback secret would be a published secret."
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@prescripto.fr"

    admin_emails: str = Field(
        default="",
        description=(
            "A string, not list[str]: pydantic-settings parses a list field as "
            "strict JSON, so both 'a@b.fr,c@d.fr' and an empty ADMIN_EMAILS= "
            "would raise SettingsError while Settings() is built, before "
            "logging exists. An empty variable is a normal deployment."
        ),
    )

    rate_limit_auth_per_minute: int = Field(
        default=10, description="Buckets live in core/ratelimit.py."
    )

    rate_limit_reset_per_window: int = Field(
        default=10,
        description=(
            "Window is shorter than the reset token's own 30 minutes on "
            "purpose: someone who mistypes five times restarts the whole flow "
            "instead of an hour-long refusal that would also lock out every "
            "colleague behind a firm's single public address. Failed attempts "
            "count like successful ones."
        ),
    )
    rate_limit_reset_window_seconds: int = 900

    forwarded_allow_ips: str = Field(
        default="",
        description=(
            "The variable uvicorn itself reads to honour X-Forwarded-For. "
            "Declared here so the validator below can check the real thing: a "
            "boolean 'trust the proxy' flag could be set without this one, "
            "and the rate limit's key depends on nothing else."
        ),
    )

    app_url: str = "https://prescripto.fr"
    api_url: str = "https://api.prescripto.fr"
    cors_origins: list[str] = ["https://prescripto.fr", "http://localhost:5173"]

    langsmith_tracing: bool = Field(
        default=True,
        description="Active partout, y compris production (J1) — voir langsmith_api_key.",
    )
    langsmith_api_key: str = Field(
        default="",
        description="Required when langsmith_tracing is true outside local (enforced below).",
    )
    langsmith_project: str = "prescripto"
    langsmith_endpoint: str = Field(
        default="https://eu.api.smith.langchain.com",
        description=(
            "This workspace is EU-hosted (confirmed 2026-09-18) — the SDK's "
            "own default (api.smith.langchain.com) is US-only and 403s a "
            "valid key/project pair silently."
        ),
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def dev_mode(self) -> bool:
        """Developer shortcuts (auth bypass, dev seeding) — local environment only."""
        return self.environment == "local"

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_weak_secret(cls, value: str) -> str:
        if value.strip().lower() in _PLACEHOLDER_SECRETS:
            raise ValueError(
                "JWT_SECRET_KEY is still a placeholder. Generate one: openssl rand -hex 32"
            )
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return value

    @model_validator(mode="after")
    def _deployed_is_locked_down(self) -> "Settings":
        if self.environment == "local":
            return self
        if "localhost" in self.database_url:
            raise ValueError(f"DATABASE_URL still points at localhost in {self.environment}")
        if not self.qdrant_api_key:
            raise ValueError(
                f"QDRANT_API_KEY is required in {self.environment}: Qdrant Cloud rejects "
                "unauthenticated requests, and a missing key would only fail at the first "
                "real search, not at boot"
            )
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError(f"CORS_ORIGINS must be an explicit list in {self.environment}")
        if self.langsmith_tracing and not self.langsmith_api_key.strip():
            raise ValueError(
                f"LANGSMITH_API_KEY is required in {self.environment} when "
                "LANGSMITH_TRACING is true: tracing would silently fail at the first "
                "real call, not at boot"
            )
        return self

    @model_validator(mode="after")
    def _rate_limiting_has_a_real_client_key(self) -> "Settings":
        """Refuse to start deployed while every visitor would share one counter.

        uvicorn honours X-Forwarded-For only from FORWARDED_ALLOW_IPS, whose
        default is 127.0.0.1 — never the reverse proxy reaching this container.
        Left unset, request.client.host is the proxy's address for everyone,
        so the first burst locks every client out at once.

        A refusal, not a warning: main.py is excluded from coverage, so a log
        line here would be a promise nothing keeps.
        """
        if self.environment == "local":
            return self

        entries = [part.strip() for part in self.forwarded_allow_ips.split(",") if part.strip()]
        if not entries:
            raise ValueError(
                f"FORWARDED_ALLOW_IPS must name the reverse proxy in {self.environment}, "
                "e.g. the Docker subnet it reaches this container from (172.18.0.0/16): "
                "left unset, every client shares one rate-limit counter and the first "
                "burst locks all of them out"
            )

        for entry in entries:
            if entry == "*":
                raise ValueError(
                    "FORWARDED_ALLOW_IPS='*' trusts X-Forwarded-For from anyone, so the "
                    "rate-limit key becomes whatever the caller writes: the limit stops "
                    "applying to them and starts applying to the address they name"
                )
            try:
                network = ipaddress.ip_network(entry, strict=False)
            except ValueError as malformed:
                raise ValueError(
                    f"FORWARDED_ALLOW_IPS entry {entry!r} is neither an address nor a network"
                ) from malformed
            if network.prefixlen == 0:
                raise ValueError(
                    f"FORWARDED_ALLOW_IPS entry {entry!r} covers every host, which trusts "
                    "X-Forwarded-For from anyone — see the '*' case above"
                )
            if network.network_address.is_loopback:
                raise ValueError(
                    f"FORWARDED_ALLOW_IPS entry {entry!r} is uvicorn's own default, and a "
                    "reverse proxy reaching a container is never the loopback: the header "
                    "would be ignored and every client would share one counter"
                )
        return self


def _as_pydantic_stores_it(address: str) -> str:
    """Lower the domain and leave the local part alone.

    This mirrors what `EmailStr` does to every address at signup (pydantic
    2.13): 'Boss@X.FR' is stored as 'Boss@x.fr'. Normalising only one side
    would let an entry like ops@CABINET.FR match nothing and promote nobody.

    The local part stays case-sensitive because users.email is stored as
    typed: folding it would let Boss@x.fr be promoted by boss@x.fr.
    """
    local, at, domain = address.rpartition("@")
    return f"{local}@{domain.lower()}" if at else address


def effective_admin_emails(s: Settings) -> frozenset[str]:
    """The addresses that must hold role='admin' once startup has reconciled.

    Separators are comma and semicolon; blanks are trimmed and empty segments
    dropped, so a variable set to "" yields an empty set rather than one empty
    address.
    """
    listed = {
        _as_pydantic_stores_it(part.strip()) for part in s.admin_emails.replace(";", ",").split(",")
    }
    listed.discard("")
    if s.dev_mode:
        listed.add(DEV_SEED_EMAIL)
    return frozenset(listed)


def email_delivery_warning(s: Settings) -> str | None:
    """The startup warning to emit, or None when email delivery is configured.

    Deliberately not a validator: Settings() is built at import time, before
    main.py calls logging.basicConfig(), so a warning raised from a validator
    would fall to logging's last-resort handler. The lifespan emits this one.
    """
    if s.environment == "local" or s.smtp_host:
        return None
    return (
        f"SMTP is not configured in {s.environment}: password reset is inoperative. "
        "/auth/forgot-password accepts requests and no email is ever sent."
    )


settings = Settings()
