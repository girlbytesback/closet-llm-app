import mimetypes
from pathlib import Path

from supabase import create_client

from closetllm.config import supabase_secret_key, supabase_url

# One client for the whole process, created at import (like db.engine).
_client = create_client(supabase_url, supabase_secret_key)
_bucket = _client.storage.from_("photos")

# How long a signed link works. An hour covers a browsing session; the UI
# re-fetches /color-matches on reload, which mints fresh links.
LINK_SECONDS = 3600


def put_file(key: str, path: Path) -> None:
    """Store the file at path under key; content type guessed from the name."""
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    put(key, path.read_bytes(), content_type)

def put(key: str, data: bytes, content_type: str) -> None:
    """Store bytes under key. Fails if the key already exists."""
    _bucket.upload(key, data, {"content-type": content_type})


def delete(key: str) -> None:
    """Remove the file at key. Used to undo a half-finished upload."""
    _bucket.remove([key])


def signed_urls(keys: list[str]) -> dict[str, str]:
    """A temporary link for each key, in ONE request. {key: url}."""
    if not keys:
        return {}
    results = _bucket.create_signed_urls(keys, LINK_SECONDS)
    return {r["path"]: r["signedURL"] for r in results if r.get("signedURL")}