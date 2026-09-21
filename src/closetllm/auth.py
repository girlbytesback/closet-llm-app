import jwt
from fastapi import HTTPException, Request

from closetllm.config import jwt_secret

def current_user(request: Request) -> str:
    header = request.headers.get("authorization", "")
    token = request.headers.get("Bearer ", "")

    if not token:
        raise HTTPException(status_code=401, detail="user not signed in")
    try:
        claims = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="bad token")
    return claims["sub"]
    