"""Section 5 — authentication, authorization, validation and rate limiting.

These run against the real FastAPI app over HTTP semantics (TestClient). The
same checks are repeated with real curl against a live uvicorn server by
tests/stress_suite/live_curl_checks.sh.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.models.database import SessionLocal, User
from app.services.auth import JWT_ALGORITHM, _get_secret

from .conftest import make_portfolio, register

PROTECTED = [
    ("GET", "/portfolios/{pid}", None),
    ("POST", "/portfolios/{pid}/holdings", [{"ticker": "OLD2", "shares": 1}]),
    ("POST", "/portfolios/{pid}/holdings/csv", "CSV"),
    ("POST", "/portfolios/{pid}/refresh", None),
    ("GET", "/portfolios/{pid}/risk", None),
    ("GET", "/portfolios/{pid}/factors", None),
    ("GET", "/portfolios/{pid}/correlation", None),
    ("GET", "/portfolios/{pid}/optimize", None),
    ("GET", "/portfolios/{pid}/stress", None),
    ("POST", "/portfolios/{pid}/ask", {"question": "hi"}),
]


def call(client, method, path, body, headers):
    if body == "CSV":
        return client.post(path, files={"file": ("p.csv", "ticker,shares\nOLD2,1\n", "text/csv")}, headers=headers)
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body, headers=headers)


@pytest.fixture
def owned(client, standard_market, frozen_today):
    owner = register(client)
    pid = make_portfolio(client, owner, [{"ticker": "OLD1", "shares": 10}, {"ticker": "OLD2", "shares": 5}])
    return owner, pid


def _token(payload):
    return {"Authorization": "Bearer " + jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)}


def _owner_id(headers):
    tok = headers["Authorization"].split()[1]
    return jwt.decode(tok, _get_secret(), algorithms=[JWT_ALGORITHM])["sub"]


# --- authentication ------------------------------------------------------------

@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_unauthenticated_rejected(client, owned, method, path, body):
    _, pid = owned
    r = call(client, method, path.format(pid=pid), body, {})
    assert r.status_code == 401


def test_create_portfolio_requires_auth(client, owned):
    assert client.post("/portfolios", json={"name": "x"}).status_code == 401


@pytest.mark.parametrize(
    "header",
    [
        "Bearer",
        "Bearer ",
        "Bearer not.a.jwt",
        "Basic dXNlcjpwYXNz",
        "Token abc",
        "Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJ4In0.",
    ],
)
def test_malformed_or_unsigned_tokens_rejected(client, owned, header):
    _, pid = owned
    assert client.get(f"/portfolios/{pid}", headers={"Authorization": header}).status_code == 401


def test_wrong_secret_rejected(client, owned):
    owner, pid = owned
    forged = jwt.encode({"sub": _owner_id(owner), "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "x" * 40, algorithm="HS256")
    assert client.get(f"/portfolios/{pid}", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_rejected(client, owned):
    owner, pid = owned
    h = _token({"sub": _owner_id(owner), "exp": datetime.now(timezone.utc) - timedelta(seconds=5)})
    assert client.get(f"/portfolios/{pid}", headers=h).status_code == 401


def test_token_without_expiry_is_rejected(client, owned):
    owner, pid = owned
    h = _token({"sub": _owner_id(owner)})  # no exp claim -> never expires
    assert client.get(f"/portfolios/{pid}", headers=h).status_code == 401, "token with no exp accepted"


def test_token_without_subject_is_401_not_500(client, owned):
    _, pid = owned
    h = _token({"exp": datetime.now(timezone.utc) + timedelta(hours=1)})
    assert client.get(f"/portfolios/{pid}", headers=h).status_code == 401


def test_token_for_deleted_user_rejected(client, owned):
    ghost = register(client)
    uid = _owner_id(ghost)
    s = SessionLocal()
    s.delete(s.get(User, uid))
    s.commit()
    s.close()
    assert client.post("/portfolios", json={"name": "x"}, headers=ghost).status_code == 401


# --- authorization (cross-user) ---------------------------------------------------

@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_other_user_cannot_access_or_detect_portfolio(client, owned, method, path, body):
    _, pid = owned
    intruder = register(client)
    r = call(client, method, path.format(pid=pid), body, intruder)
    assert r.status_code in (400, 404), f"{method} {path}: HTTP {r.status_code}"
    assert r.json()["detail"] == "portfolio not found", r.json()


@pytest.mark.parametrize("method,path,body", PROTECTED)
def test_not_found_status_is_consistent_404(client, owned, method, path, body):
    _, pid = owned
    intruder = register(client)
    r = call(client, method, path.format(pid=pid), body, intruder)
    assert r.status_code == 404, f"{method} {path}: 'portfolio not found' returned as HTTP {r.status_code}"


def test_cross_user_write_did_not_modify_portfolio(client, owned):
    owner, pid = owned
    intruder = register(client)
    client.post(f"/portfolios/{pid}/holdings", json=[{"ticker": "OLD2", "shares": 999}], headers=intruder)
    holdings = client.get(f"/portfolios/{pid}", headers=owner).json()["holdings"]
    assert all(h["shares"] != 999 for h in holdings)


def test_nonexistent_and_foreign_ids_indistinguishable(client, owned):
    _, pid = owned
    intruder = register(client)
    a = client.get(f"/portfolios/{pid}", headers=intruder)
    b = client.get("/portfolios/00000000-0000-0000-0000-000000000000", headers=intruder)
    assert (a.status_code, a.json()) == (b.status_code, b.json())


@pytest.mark.parametrize("method", ["DELETE", "PUT", "PATCH"])
def test_no_unauthenticated_mutation_verbs(client, owned, method):
    _, pid = owned
    r = client.request(method, f"/portfolios/{pid}")
    assert r.status_code in (401, 404, 405)


# --- validation --------------------------------------------------------------------

@pytest.mark.parametrize(
    "body",
    [{}, {"email": "not-an-email", "password": "longenough"}, {"email": "a@b.com", "password": "short"}, {"email": "a@b.com"}, {"email": "a@b.com", "password": "x" * 129}],
)
def test_register_body_validation(client, body):
    assert client.post("/auth/register", json=body).status_code == 422


def test_long_password_within_limit_does_not_500(client):
    # Field allows up to 128 chars; bcrypt only accepts 72 bytes.
    r = client.post("/auth/register", json={"email": "longpw@example.com", "password": "p" * 100})
    assert r.status_code != 500, "100-char password (allowed by schema) -> HTTP 500"


def test_multibyte_password_does_not_500(client):
    r = client.post("/auth/register", json={"email": "emoji@example.com", "password": "🔒" * 30})  # 30 chars, 120 bytes
    assert r.status_code != 500, "30-char emoji password -> HTTP 500"


def test_email_is_case_insensitive(client):
    register(client, email="Case@Example.com")
    assert client.post("/auth/register", json={"email": "case@example.com", "password": "longenough1"}).status_code == 409


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "x" * 101}, {"name": "ok", "benchmark": "spy; drop"}, {"benchmark": "SPY"}])
def test_create_portfolio_validation(client, body):
    h = register(client)
    assert client.post("/portfolios", json=body, headers=h).status_code == 422


def test_cors_rejects_unlisted_origin(client):
    r = client.options("/portfolios", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") is None


# --- rate limits ---------------------------------------------------------------------

@pytest.mark.parametrize("path,limit", [("/auth/login", 10), ("/auth/register", 10)])
def test_auth_rate_limits(client, path, limit):
    codes = [client.post(path, json={"email": f"rl{i}@example.com", "password": "wrong-password"}).status_code for i in range(limit + 1)]
    assert 429 not in codes[:limit] and codes[limit] == 429, codes


@pytest.mark.parametrize("endpoint,limit", [("risk", 60), ("stress", 60), ("optimize", 60)])
def test_expensive_analytics_are_rate_limited(client, owned, endpoint, limit):
    owner, pid = owned
    codes = [client.get(f"/portfolios/{pid}/{endpoint}", headers=owner).status_code for _ in range(limit + 1)]
    assert codes[-1] == 429, f"{endpoint}: request #{limit + 1} returned {codes[-1]}"


def test_ask_rate_limit(client, owned, monkeypatch):
    import app.api.ask as ask_mod

    monkeypatch.setattr(ask_mod, "answer_question", lambda ctx, q: "stub")
    owner, pid = owned
    codes = [client.post(f"/portfolios/{pid}/ask", json={"question": "q"}, headers=owner).status_code for _ in range(21)]
    assert codes[:20].count(200) == 20 and codes[20] == 429, codes


def test_ask_limit_cannot_be_bypassed_by_switching_portfolio(client, owned, monkeypatch):
    """slowapi's default key_style is "url", so the /ask and /refresh buckets are
    per (IP, portfolio URL). A user who hits 20/min on one portfolio gets a
    fresh 20/min on every other portfolio they create -> unbounded LLM spend."""
    import app.api.ask as ask_mod

    monkeypatch.setattr(ask_mod, "answer_question", lambda ctx, q: "stub")
    owner, pid = owned
    for _ in range(20):
        client.post(f"/portfolios/{pid}/ask", json={"question": "q"}, headers=owner)
    extra = [make_portfolio(client, owner, [{"ticker": "OLD1", "shares": 1}], name=f"p{i}") for i in range(3)]
    codes = [client.post(f"/portfolios/{p}/ask", json={"question": "q"}, headers=owner).status_code for p in extra]
    assert codes.count(429) == 3, f"same user, new portfolio URLs -> {codes} (limit bypassed)"
