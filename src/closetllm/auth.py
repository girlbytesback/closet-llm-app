import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Request

from closetllm.config import jwt_secret, supabase_url

# DOWNLOADS SUPABASE PUBLIC KEYS AND CACHES
jwks = PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")

COOKIE = "closetllm_session"

# first, we check for cookies saved in browser. if no cookie, read token.

def current_user(request: Request) -> str:
    # Supabase sends the access token as "Authorization: Bearer <jwt>". Only the
    # part after the scheme is the token, so the header is split rather than
    # decoded whole — a missing or differently-schemed header is "not signed in".
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() != "bearer" or not token:
        token = request.cookies.get(COOKIE, "")

    if not token:
        raise HTTPException(status_code=401, detail="user not signed in")
    return verify(token)["sub"]

# read header
def verify(token: str) -> dict:
    try:
        signing_key = jwks.get_signing_key_from_jwt(token)
        return jwt.decode(
            token, 
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="bad token")
