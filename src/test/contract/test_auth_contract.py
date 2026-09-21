"""Who gets past the front door.

Every route except /health is behind Depends(current_user). The rest of the
suite runs with that dependency overridden, so these tests are the only ones
that exercise the real one — each clears the override first.

No test here talks to Supabase: the valid-token case mints its own JWT with a
throwaway secret, which is enough to drive the real jwt.decode.
"""

import jwt

from closetllm import api

from fastapi.testclient import TestClient


def test_no_token_is_401(data_paths):
    api.app.dependency_overrides.clear()          # use the real dependency for this one
    client = TestClient(api.app)
    assert client.get("/garments").status_code == 401


def test_garbage_token_is_401(data_paths):
    api.app.dependency_overrides.clear()
    client = TestClient(api.app)
    response = client.get("/garments", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_a_valid_token_gets_past_auth(monkeypatch, data_paths):
    # 32+ bytes only to keep PyJWT from warning about a short HMAC key; the value
    # itself is throwaway and never leaves this test.
    secret = "test-secret-padded-to-32-bytes-min"
    monkeypatch.setattr("closetllm.auth.jwt_secret", secret)
    token = jwt.encode({"sub": "user-123", "aud": "authenticated"}, secret, algorithm="HS256")
    api.app.dependency_overrides.clear()
    client = TestClient(api.app)
    response = client.get("/garments", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code in (200, 404)     # 404 = empty store, not an auth failure


def test_health_stays_open():
    api.app.dependency_overrides.clear()
    assert TestClient(api.app).get("/health").status_code == 200
