"""LangSmith tracing configuration — env vars only, no client object."""

import os

from app.core.config import Settings


def configure_langsmith(settings: Settings) -> None:
    """Set the SDK's env vars from Settings; tracing also needs an actual key.

    Empty key still fires a real (always-401) network call per traced call —
    harmless but unwanted in local/tests. `_deployed_is_locked_down` already
    requires a key outside `local` when tracing is on.
    """
    tracing = settings.langsmith_tracing and bool(settings.langsmith_api_key.strip())
    os.environ["LANGSMITH_TRACING"] = "true" if tracing else "false"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
