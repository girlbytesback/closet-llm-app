"""Who gets past the front door.

Every route except /health is behind Depends(current_user). The rest of the
suite runs with that dependency overridden, so these tests are the only ones
that exercise the real one — each clears the override first.

No test here talks to Supabase: the valid-token case mints its own ES256 JWT
with a throwaway key pair and swaps the JWKS client for one that hands back the
matching public key, which is enough to drive the real jwt.decode.
"""

from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from closetllm import api

from fastapi.testclient import TestClient

from helpers import jpeg_bytes


@pytest.fixture
def mint_token(monkeypatch):
    # stands in for Supabase: a fresh P-256 key signs the token, and the JWKS
    # lookup returns its public half instead of fetching the real key set
    private_key = ec.generate_private_key(ec.SECP256R1())
    fake_jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    monkeypatch.setattr("closetllm.auth.jwks", fake_jwks)

    def mint(sub):
        return jwt.encode({"sub": sub, "aud": "authenticated"}, private_key, algorithm="ES256")

    return mint


def test_no_token_is_401(data_paths):
    api.app.dependency_overrides.clear()          # use the real dependency for this one
    client = TestClient(api.app)
    assert client.get("/garments").status_code == 401


def test_garbage_token_is_401(data_paths):
    api.app.dependency_overrides.clear()
    client = TestClient(api.app)
    response = client.get("/garments", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_a_valid_token_gets_past_auth(mint_token, data_paths, fake_db):
    # fake_db because /garments reads rows: without it the request gets past
    # auth and then dies on the real engine, which looks the same from here.
    token = mint_token("user-123")
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


def test_an_upload_with_a_valid_token_runs_as_that_user(mint_token, data_paths, upload_paths, fake_model):
    # the id in the token is the owner of the row, not a constant
    token = mint_token("user-123")
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
