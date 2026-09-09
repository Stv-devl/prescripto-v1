"""Mistral AI client singleton."""

from mistralai import Mistral

from app.core.config import settings

mistral_client = Mistral(api_key=settings.mistral_api_key)
