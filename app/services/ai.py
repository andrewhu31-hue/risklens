"""Thin wrapper around the Anthropic Messages API used by /refresh and /ask.

Errors are turned into RuntimeError with a message a user can act on (the API
layer maps them to HTTP 503); the raw cause is logged, never the key.
"""
import logging
import os

import anthropic
from anthropic import Anthropic

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5-5"
# Vercel stops the function at 60 s (vercel.json maxDuration), so give up
# before that and return a readable error instead of a platform timeout.
REQUEST_TIMEOUT_SECONDS = 40
MAX_RETRIES = 1

_client: Anthropic | None = None
_client_key: str | None = None


def clean_api_key(raw: str | None) -> str:
    """Strip what commonly sneaks in when a key is pasted into a dashboard:
    surrounding whitespace/newlines and wrapping quotes. A key with whitespace
    inside it can't be valid and makes the HTTP client refuse to send the
    request at all (it surfaces as a bare "Connection error.")."""
    key = (raw or "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        key = key[1:-1].strip()
    return key


def model_name() -> str:
    return clean_api_key(os.getenv("ANTHROPIC_MODEL")) or DEFAULT_MODEL


def _thinking_params(model: str) -> dict:
    """Claude 5.5-generation models think by default, which spends part of
    max_tokens before any text and adds latency. These are short, grounded
    answers, so turn it off there ({"type": "disabled"} is a 400 on those
    models; "between_tools" with no tools means no thinking). Older models
    don't think unless asked, so they get nothing extra."""
    return {"thinking": {"type": "between_tools"}} if model.endswith("-5-5") else {}


def key_status() -> str:
    """'missing', 'malformed' or 'present' — for /health; never the key itself."""
    key = clean_api_key(os.getenv("ANTHROPIC_API_KEY"))
    if not key:
        return "missing"
    if any(c.isspace() for c in key) or not key.isascii():
        return "malformed"
    return "present"


def _get_client() -> Anthropic:
    global _client, _client_key
    key = clean_api_key(os.getenv("ANTHROPIC_API_KEY"))
    if not key:
        raise RuntimeError(
            "The AI assistant isn't set up on this server yet: add an ANTHROPIC_API_KEY environment variable"
        )
    if any(c.isspace() for c in key) or not key.isascii():
        raise RuntimeError(
            "The ANTHROPIC_API_KEY on this server is malformed (it contains spaces, line breaks or "
            "non-ASCII characters). Paste the key again in the hosting settings and redeploy."
        )
    if _client is None or key != _client_key:
        _client = Anthropic(api_key=key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
        _client_key = key
    return _client


def ask_claude(system: str, prompt: str, max_tokens: int = 1200) -> str:
    client = _get_client()
    model = model_name()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            **_thinking_params(model),
        )
    except anthropic.AuthenticationError as e:
        raise RuntimeError(
            "The ANTHROPIC_API_KEY on this server was rejected by Anthropic. Check it is a current key "
            "from console.anthropic.com, update it in the hosting settings and redeploy."
        ) from e
    except anthropic.PermissionDeniedError as e:
        raise RuntimeError("This Anthropic API key doesn't have access to the configured model.") from e
    except anthropic.NotFoundError as e:
        raise RuntimeError(f"The configured AI model '{model_name()}' was not found.") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("The AI service is busy or the account's rate limit was reached. Try again shortly.") from e
    except anthropic.APITimeoutError as e:
        raise RuntimeError("The AI service took too long to answer. Try again.") from e
    except anthropic.APIConnectionError as e:
        log.warning("Anthropic connection failed: %r (cause: %r)", e, e.__cause__)
        raise RuntimeError("Couldn't reach the AI service from the server. Try again in a moment.") from e
    except anthropic.APIStatusError as e:
        message = e.body.get("error", {}).get("message") if isinstance(e.body, dict) else str(e)
        if e.status_code == 400 and "credit" in (message or "").lower():
            raise RuntimeError("The Anthropic account has no remaining credit. Add credit at console.anthropic.com.") from e
        raise RuntimeError(f"AI service error ({e.status_code}): {message}") from e
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise RuntimeError("The AI service returned an empty answer. Try rephrasing the question.")
    return text
