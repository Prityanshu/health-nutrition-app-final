"""
Groq model with automatic API-key fallback.

WHY THIS IS A SUBCLASS (and not a wrapper):
The previous implementation was a wrapper class that put its retry logic in a
method called `run()`, and delegated everything else via `__getattr__`.
But agno's Agent never calls `model.run()` - it calls `model.response()`,
`model.aresponse()`, `model.response_stream()` and `model.aresponse_stream()`
(see agno/agent/agent.py). Those calls fell straight through `__getattr__` to
the underlying Groq client, so the retry/key-rotation code never executed and
a rate-limited key would simply raise.

Subclassing agno's Groq and overriding the four real entry points means the
fallback fires on the path the Agent actually uses.
"""

import logging
from typing import Any, Dict, List

from agno.models.groq import Groq

from app.config.groq_config import (
    get_model_id,
    groq_config,
    handle_groq_error,
    mark_groq_success,
)

logger = logging.getLogger(__name__)

# Error substrings that indicate "this key is exhausted, try the next one".
# Anything not in this list is a genuine error and is raised immediately
# rather than burning through every key for nothing.
_RETRYABLE = (
    "rate_limit_exceeded",
    "rate limit",
    "quota exceeded",
    "too many requests",
    "high usage",
    "429",
    "unauthorized",
    "invalid api key",
    "invalid_api_key",
    "authentication",
)


def _is_retryable(error: Exception) -> bool:
    msg = str(error).lower()
    return any(phrase in msg for phrase in _RETRYABLE)


class GroqWithFallback(Groq):
    """Groq model that rotates through configured API keys on rate-limit errors."""

    def __init__(self, id: str = None, **kwargs):
        id = id or get_model_id()
        api_key = groq_config.get_current_api_key()
        if not api_key:
            raise ValueError(
                "No Groq API keys available. Set GROQ_API_KEY (and optionally "
                "GROQ_API_KEY_2 / GROQ_API_KEY_3) in your environment."
            )
        super().__init__(id=id, api_key=api_key, **kwargs)

    def _apply_current_key(self) -> bool:
        """
        Point this model at whatever key groq_config currently considers active.

        Returns True if the key changed. Clearing `client` / `async_client` is
        required because agno's Groq caches the constructed client and would
        otherwise keep using the old key.
        """
        new_key = groq_config.get_current_api_key()
        if not new_key:
            raise ValueError("No active Groq API keys available")

        if new_key != self.api_key:
            self.api_key = new_key
            self.client = None
            self.async_client = None
            logger.info("Rotated to Groq API key: %s", self._current_key_name())
            return True
        return False

    def _current_key_name(self) -> str:
        try:
            return groq_config.api_keys[groq_config.current_key_index].name
        except (IndexError, AttributeError):
            return "unknown"

    def _attempts(self) -> int:
        return max(1, len(groq_config.api_keys))

    # ---- sync paths -----------------------------------------------------

    def response(self, *args, **kwargs):
        last_error = None
        for attempt in range(self._attempts()):
            try:
                self._apply_current_key()
                result = super().response(*args, **kwargs)
                mark_groq_success()
                return result
            except Exception as e:
                last_error = e
                if not _is_retryable(e):
                    logger.error("Non-retryable Groq error: %s", e)
                    raise
                logger.warning(
                    "Groq key '%s' failed (attempt %d/%d): %s",
                    self._current_key_name(), attempt + 1, self._attempts(), e,
                )
                handle_groq_error(e)
        logger.error("All Groq API keys exhausted. Last error: %s", last_error)
        raise last_error

    def response_stream(self, *args, **kwargs):
        last_error = None
        for attempt in range(self._attempts()):
            try:
                self._apply_current_key()
                # Materialise lazily but surface auth/rate errors on first chunk
                yield from super().response_stream(*args, **kwargs)
                mark_groq_success()
                return
            except Exception as e:
                last_error = e
                if not _is_retryable(e):
                    raise
                logger.warning("Groq stream key failure (attempt %d): %s", attempt + 1, e)
                handle_groq_error(e)
        raise last_error

    # ---- async paths ----------------------------------------------------

    async def aresponse(self, *args, **kwargs):
        last_error = None
        for attempt in range(self._attempts()):
            try:
                self._apply_current_key()
                result = await super().aresponse(*args, **kwargs)
                mark_groq_success()
                return result
            except Exception as e:
                last_error = e
                if not _is_retryable(e):
                    logger.error("Non-retryable Groq error: %s", e)
                    raise
                logger.warning(
                    "Groq key '%s' failed (attempt %d/%d): %s",
                    self._current_key_name(), attempt + 1, self._attempts(), e,
                )
                handle_groq_error(e)
        logger.error("All Groq API keys exhausted. Last error: %s", last_error)
        raise last_error

    async def aresponse_stream(self, *args, **kwargs):
        last_error = None
        for attempt in range(self._attempts()):
            try:
                self._apply_current_key()
                async for chunk in super().aresponse_stream(*args, **kwargs):
                    yield chunk
                mark_groq_success()
                return
            except Exception as e:
                last_error = e
                if not _is_retryable(e):
                    raise
                logger.warning("Groq stream key failure (attempt %d): %s", attempt + 1, e)
                handle_groq_error(e)
        raise last_error

    # ---- introspection helpers (kept from the previous API) -------------

    def get_status(self) -> Dict[str, Any]:
        return groq_config.get_status()

    def reset_keys(self) -> None:
        groq_config.reset_all_keys()
        self._apply_current_key()
