from typing import Tuple
import re
from app.config import settings
from app.logging import log, _hash_value


PROFANITY = {
    "fuck", "shit", "bitch", "bastard", "asshole", "dick", "cunt",
    "slut", "whore", "motherfucker", "nigger", "fag", "retard",
}

INJECTION_PATTERNS = [
    r"ignore\s+all\s+previous\s+instructions",
    r"disregard\s+prior\s+guidance",
    r"act\s+as\s+system",
    r"you\s+are\s+no\s+longer\s+restricted",
]


class SafetyError(ValueError):
    pass


def _contains_profanity(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in PROFANITY)


def _contains_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pat, lowered) for pat in INJECTION_PATTERNS)


def check_text_safety(kind: str, text: str) -> None:
    """Validate user-provided text for profanity, length, and prompt injection.

    Raises SafetyError when unsafe. Logs a scrubbed entry; never logs raw text.
    """
    if not text:
        return

    if len(text) > settings.MAX_TEXT_CHARS:
        log.warning("safety.length.exceeded", kind=kind, text_hash=_hash_value(text))
        raise SafetyError("Input too long. Please reduce content length.")

    if _contains_profanity(text):
        log.warning("safety.profanity.detected", kind=kind, text_hash=_hash_value(text))
        raise SafetyError("Unsafe content detected. Please remove profanity.")

    if settings.ENABLE_PROMPT_INJECTION_CHECKS and _contains_injection(text):
        log.warning("safety.injection.detected", kind=kind, text_hash=_hash_value(text))
        raise SafetyError("Potential prompt injection detected. Please revise your input.")


def check_prompt_safety(prompt: str) -> None:
    if not prompt:
        return
    if len(prompt) > settings.MAX_PROMPT_CHARS:
        log.warning("safety.prompt.length.exceeded", prompt_hash=_hash_value(prompt))
        raise SafetyError("Prompt too long.")
    if _contains_profanity(prompt):
        log.warning("safety.prompt.profanity", prompt_hash=_hash_value(prompt))
        raise SafetyError("Unsafe prompt content.")
    if settings.ENABLE_PROMPT_INJECTION_CHECKS and _contains_injection(prompt):
        log.warning("safety.prompt.injection", prompt_hash=_hash_value(prompt))
        raise SafetyError("Potential prompt injection.")

