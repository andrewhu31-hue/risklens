import os

import anthropic
from anthropic import Anthropic

_client: Anthropic | None = None
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "The AI assistant isn't set up on this server yet: add an ANTHROPIC_API_KEY environment variable"
            )
        _client = Anthropic(api_key=api_key)
    return _client


def ask_claude(system: str, prompt: str, max_tokens: int = 600) -> str:
    client = _get_client()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as e:
        message = e.body.get("error", {}).get("message") if isinstance(e.body, dict) else str(e)
        raise RuntimeError(f"Anthropic API error: {message}") from e
    except anthropic.APIError as e:  # connection errors, timeouts
        raise RuntimeError(f"Anthropic API unavailable: {e}") from e
    return "".join(block.text for block in response.content if block.type == "text")
