"""The Anthropic wrapper: key cleanup, readable errors, no network.

Regression for the live "Anthropic API unavailable: Connection error." — a key
pasted with a trailing newline/space makes httpx refuse to build the
Authorization header, which the SDK reports as a connection error.
"""
import pytest

try:  # anthropic>=2 ships its HTTP stack as httpx2
    import httpx2 as httpx
except ImportError:  # pragma: no cover - older SDKs use httpx
    import httpx

import app.services.ai as ai


def _client_with(handler):
    """Build the real SDK client through _get_client(), then point it at a mock transport."""
    client = ai._get_client()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    monkeypatch.setattr(ai, "_client", None)
    monkeypatch.setattr(ai, "_client_key", None)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("sk-ant-api03-abc\n", "sk-ant-api03-abc"),
        ("  sk-ant-api03-abc  ", "sk-ant-api03-abc"),
        ('"sk-ant-api03-abc"', "sk-ant-api03-abc"),
        ("'sk-ant-api03-abc'\r\n", "sk-ant-api03-abc"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_api_key(raw, clean):
    assert ai.clean_api_key(raw) == clean


@pytest.mark.parametrize(
    "raw,status",
    [(None, "missing"), ("   ", "missing"), ("sk-ant x", "malformed"), ("sk-ant-é", "malformed"), ("sk-ant-api03-abc\n", "present")],
)
def test_key_status(monkeypatch, raw, status):
    if raw is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", raw)
    assert ai.key_status() == status


def test_key_with_trailing_newline_is_sent_cleanly(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-abc\n")
    seen = {}

    def handler(request: httpx.Request):
        auth = request.headers.get("authorization", "")
        seen["key"] = request.headers.get("x-api-key") or auth.removeprefix("Bearer ")
        seen["model"] = __import__("json").loads(request.content)["model"]
        return httpx.Response(
            200,
            json={
                "id": "msg_1", "type": "message", "role": "assistant", "model": "m",
                "content": [{"type": "text", "text": "Concentration in NVDA."}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    _client_with(handler)
    assert ai.ask_claude("sys", "q") == "Concentration in NVDA."
    assert seen["key"] == "sk-ant-api03-abc"
    assert seen["model"] == "claude-sonnet-5-5"


def test_model_can_be_overridden(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", " claude-haiku-5-5 \n")
    assert ai.model_name() == "claude-haiku-5-5"


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}, "was rejected"),
        (404, {"type": "error", "error": {"type": "not_found_error", "message": "model"}}, "was not found"),
        (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}}, "rate limit"),
        (400, {"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}}, "no remaining credit"),
    ],
)
def test_status_errors_are_readable(monkeypatch, status, body, expected):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-abc")
    _client_with(lambda request: httpx.Response(status, json=body))
    with pytest.raises(RuntimeError, match=expected):
        ai.ask_claude("sys", "q")


def test_connection_failure_is_readable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-abc")

    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    _client_with(handler)
    with pytest.raises(RuntimeError, match="Couldn't reach the AI service"):
        ai.ask_claude("sys", "q")


def test_key_with_inner_space_is_reported_not_sent(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant api03")
    with pytest.raises(RuntimeError, match="malformed"):
        ai.ask_claude("sys", "q")
