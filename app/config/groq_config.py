"""
Groq API Configuration with Fallback Support
Handles multiple API keys with automatic failover
"""

import os
import re
import time
import logging
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class GroqAPIKey:
    """Represents a Groq API key with metadata"""
    key: str
    name: str
    is_active: bool = True
    usage_count: int = 0
    last_used: Optional[str] = None
    error_count: int = 0
    # Epoch seconds until which this key is known to be rate limited. Groq
    # tells us exactly how long to wait, so there is no point retrying before
    # then - the key is skipped entirely until the clock runs out.
    cooldown_until: float = 0.0

    @property
    def cooling(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def cooldown_remaining(self) -> int:
        return max(0, int(self.cooldown_until - time.time()))

    @property
    def usable(self) -> bool:
        return self.is_active and not self.cooling and self.error_count < 3


def parse_retry_after(message: str) -> float:
    """
    Pull the wait time out of a Groq 429 body.

    Groq says e.g. "Please try again in 1h2m15.071999999s". Falls back to a
    conservative 60s when the message cannot be parsed.
    """
    match = re.search(
        r'try again in\s*(?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?',
        message,
        re.IGNORECASE,
    )
    if not match:
        return 60.0
    hours = float(match.group(1) or 0)
    minutes = float(match.group(2) or 0)
    seconds = float(match.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total if total > 0 else 60.0


def is_daily_quota_error(message: str) -> bool:
    """True for tokens-per-day exhaustion, which no amount of waiting fixes today."""
    low = message.lower()
    return "tokens per day" in low or "tpd" in low

class GroqConfigManager:
    """Manages multiple Groq API keys with automatic failover"""
    
    def __init__(self):
        self.api_keys: List[GroqAPIKey] = []
        self.current_key_index = 0
        self.max_errors_per_key = 3  # Switch key after 3 consecutive errors
        self._load_api_keys()
    
    def _load_api_keys(self):
        """
        Load API keys from the environment.

        Scans GROQ_API_KEY, then GROQ_API_KEY_2 .. GROQ_API_KEY_10, so adding
        another key is an .env line rather than a code change. Duplicates are
        skipped - the same key twice would just fail twice in a row and waste
        the retry budget.

        Note: Groq rate limits are per ORGANISATION. Extra keys only add
        capacity if they belong to genuinely different accounts; two keys on
        one account share a single daily quota.
        """
        env_names = ['GROQ_API_KEY'] + [f'GROQ_API_KEY_{i}' for i in range(2, 11)]
        seen = set()

        for index, env_name in enumerate(env_names):
            raw = os.getenv(env_name)
            if not raw:
                continue

            key = raw.strip().strip('"').strip("'")
            if not key:
                continue

            if key in seen:
                logger.warning("%s duplicates an earlier key - skipping", env_name)
                continue
            seen.add(key)

            name = "primary" if index == 0 else f"key{index + 1}"
            self.api_keys.append(GroqAPIKey(key=key, name=name, is_active=True))
            logger.info("Loaded Groq API key '%s' from %s", name, env_name)

        if not self.api_keys:
            logger.warning("No Groq API keys found in environment variables")
        else:
            logger.info(
                "Loaded %d Groq API key(s): %s",
                len(self.api_keys), ", ".join(k.name for k in self.api_keys),
            )
    
    def get_current_api_key(self) -> Optional[str]:
        """Get the current usable API key, skipping any that are cooling down."""
        if not self.api_keys:
            return None

        for i in range(len(self.api_keys)):
            key_index = (self.current_key_index + i) % len(self.api_keys)
            api_key = self.api_keys[key_index]
            if api_key.usable:
                if key_index != self.current_key_index:
                    self.current_key_index = key_index
                return api_key.key

        # Every key is cooling or errored. Return the one that frees up soonest
        # so the caller gets a coherent error rather than None.
        soonest = min(self.api_keys, key=lambda k: k.cooldown_until)
        logger.warning(
            "All Groq keys unavailable; soonest is '%s' in %ds",
            soonest.name, soonest.cooldown_remaining,
        )
        return soonest.key

    def all_keys_exhausted(self) -> bool:
        """True when no key can currently serve a request."""
        return not any(k.usable for k in self.api_keys)

    def seconds_until_available(self) -> int:
        """How long until the earliest key frees up."""
        if not self.api_keys:
            return 0
        if any(k.usable for k in self.api_keys):
            return 0
        return min(k.cooldown_remaining for k in self.api_keys)

    def mark_key_rate_limited(self, retry_after: float, daily: bool = False):
        """
        A 429 means this key is spent. Put it on ice and move on immediately.

        This is deliberately different from mark_key_error: a rate limit is an
        unambiguous signal about *this* key, so waiting for a three-strike
        counter just wastes the caller's retry budget on a key we already know
        will fail. That mismatch - three strikes required, but only
        len(keys) attempts available - is why rotation never fired with two
        keys configured.
        """
        if not self.api_keys:
            return

        current = self.api_keys[self.current_key_index]
        # Daily token quotas do not recover in minutes; park the key properly.
        current.cooldown_until = time.time() + max(retry_after, 60.0)
        label = "daily token quota" if daily else "rate limit"
        logger.warning(
            "Groq key '%s' hit %s - cooling down for %ds",
            current.name, label, current.cooldown_remaining,
        )
        self._switch_to_next_key()

    def mark_key_error(self, error_type: str = "general"):
        """Mark the current key as having a non-rate-limit error."""
        if not self.api_keys:
            return

        current_key = self.api_keys[self.current_key_index]
        current_key.error_count += 1

        logger.warning(
            f"API key '{current_key.name}' error count: "
            f"{current_key.error_count}/{self.max_errors_per_key}"
        )

        if current_key.error_count >= self.max_errors_per_key:
            current_key.is_active = False
            logger.error(f"API key '{current_key.name}' disabled due to too many errors")
            self._switch_to_next_key()
    
    def mark_key_success(self):
        """Mark the current key as successful (reset error count)"""
        if not self.api_keys:
            return
        
        current_key = self.api_keys[self.current_key_index]
        current_key.error_count = 0
        current_key.usage_count += 1
        current_key.is_active = True
    
    def _switch_to_next_key(self):
        """Switch to the next usable API key."""
        if not self.api_keys:
            return

        for i in range(1, len(self.api_keys) + 1):
            next_index = (self.current_key_index + i) % len(self.api_keys)
            api_key = self.api_keys[next_index]

            if api_key.usable:
                self.current_key_index = next_index
                logger.info(f"Switched to API key '{api_key.name}' (index {next_index})")
                return

        # Nothing usable. Clear stale error counts, but preserve cooldowns -
        # those came from the API telling us exactly how long to wait, and
        # resetting them would just produce another immediate 429.
        logger.warning("No usable API keys; clearing error counts (cooldowns kept)")
        for api_key in self.api_keys:
            api_key.error_count = 0
            api_key.is_active = True
    
    def get_status(self) -> dict:
        """Get the current status of all API keys"""
        return {
            "total_keys": len(self.api_keys),
            "active_keys": len([k for k in self.api_keys if k.is_active]),
            "current_key_index": self.current_key_index,
            "current_key_name": self.api_keys[self.current_key_index].name if self.api_keys else None,
            "keys": [
                {
                    "name": key.name,
                    "is_active": key.is_active,
                    "error_count": key.error_count,
                    "usage_count": key.usage_count,
                    "last_used": key.last_used
                }
                for key in self.api_keys
            ]
        }
    
    def reset_all_keys(self):
        """Reset all API keys (useful for testing or manual reset)"""
        for api_key in self.api_keys:
            api_key.error_count = 0
            api_key.is_active = True
        self.current_key_index = 0
        logger.info("Reset all API keys")

# ---------------------------------------------------------------------------
# Model selection
#
# Groq rate limits are per MODEL as well as per organisation - the 429 body
# says "Rate limit reached for model `X` ... on tokens per day". So running the
# orchestrator and the generators on DIFFERENT models gives each its own daily
# bucket, roughly doubling capacity on the same key.
#
# The split also matches the work. The orchestrator only decides "converse or
# call a tool, and with which arguments", but it carries the tool schemas on
# every request - about 80% of the per-message token cost. That is easy work
# being billed at a large-model rate. The generators, which actually write
# recipes and workout plans, are where quality matters.
#
# Both are env-overridable because Groq retires models on a rolling basis, and
# a retired model returns an immediate 400 that key rotation cannot recover
# from. (llama-3.1-8b-instant was deprecated for free tier on 2026-06-17.)
# ---------------------------------------------------------------------------

GENERATOR_MODEL_ID = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
ORCHESTRATOR_MODEL_ID = os.getenv("GROQ_ORCHESTRATOR_MODEL", GENERATOR_MODEL_ID)


def get_model_id() -> str:
    """Model for the specialist agents that generate recipes, plans, workouts."""
    return GENERATOR_MODEL_ID


def get_orchestrator_model() -> str:
    """
    Model for the conversation orchestrator (routing + tool selection).

    Defaults to the generator model so behaviour is unchanged until
    GROQ_ORCHESTRATOR_MODEL is set - opting in is a one-line env change.
    """
    return ORCHESTRATOR_MODEL_ID


# Global instance
groq_config = GroqConfigManager()

def get_groq_api_key() -> Optional[str]:
    """Get the current Groq API key with fallback support"""
    return groq_config.get_current_api_key()

def handle_groq_error(error: Exception):
    """Handle a Groq API error, rotating keys when appropriate."""
    raw = str(error)
    error_msg = raw.lower()

    if any(phrase in error_msg for phrase in [
        "rate_limit_exceeded",
        "rate limit",
        "quota exceeded",
        "too many requests",
        "high usage",
        "429",
    ]):
        retry_after = parse_retry_after(raw)
        daily = is_daily_quota_error(raw)
        # Rotate immediately rather than counting to three - see
        # mark_key_rate_limited for why the counter was the wrong mechanism.
        groq_config.mark_key_rate_limited(retry_after, daily=daily)
    else:
        logger.warning(f"API error detected: {error}")
        groq_config.mark_key_error("general")

def mark_groq_success():
    """Mark the current API key as successful"""
    groq_config.mark_key_success()
