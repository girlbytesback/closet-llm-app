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

from helpers import jpeg_bytes


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


def test_an_upload_with_no_token_is_401(data_paths):
    # the upload routes declare auth as a handler argument rather than a route
    # dependency, because they need the id and not just the 401. Same front
    # door either way — this is what says so.
    api.app.dependency_overrides.clear()
    client = TestClient(api.app)

    for route in ("/upload-garments", "/upload-palettes"):
        response = client.post(route, files={"file": ("shirt.jpeg", b"", "image/jpeg")})
        assert response.status_code == 401, route


def test_an_upload_with_a_valid_token_runs_as_that_user(monkeypatch, data_paths, upload_paths, fake_model):
    # the id in the token is the owner of the row, not a constant
    secret = "test-secret-padded-to-32-bytes-min"
    monkeypatch.setattr("closetllm.auth.jwt_secret", secret)
    token = jwt.encode({"sub": "user-123", "aud": "authenticated"}, secret, algorithm="HS256")
    fake_model({"item": "shirt", "color": "#B5C29A"})
    api.app.dependency_overrides.clear()
    client = TestClient(api.app)

    response = client.post(
        "/upload-garments",
        files={"file": ("shirt.jpeg", jpeg_bytes(), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert upload_paths.db.garments("user-123") == {"shirt.jpeg": ["#B5C29A"]}


def test_health_stays_open():
    api.app.dependency_overrides.clear()
    assert TestClient(api.app).get("/health").status_code == 200
