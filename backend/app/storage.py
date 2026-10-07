import os
from urllib.parse import quote

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
SUPABASE_STORAGE_BUCKET = os.getenv(
    "SUPABASE_STORAGE_BUCKET",
    "case-documents",
).strip()

REQUEST_TIMEOUT_SECONDS = 30.0


def _require_configuration() -> None:
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_STORAGE_BUCKET:
        missing.append("SUPABASE_STORAGE_BUCKET")

    if missing:
        raise RuntimeError(
            "Supabase Storage is not configured. Missing: "
            + ", ".join(missing)
        )


def _headers(content_type: str | None = None) -> dict[str, str]:
    _require_configuration()

    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _object_url(path: str) -> str:
    encoded_bucket = quote(SUPABASE_STORAGE_BUCKET, safe="")
    encoded_path = quote(path, safe="/")
    return f"{SUPABASE_URL}/storage/v1/object/{encoded_bucket}/{encoded_path}"


def upload_object(path: str, content: bytes, content_type: str) -> None:
    headers = _headers(content_type)
    headers["x-upsert"] = "false"

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(
            _object_url(path),
            content=content,
            headers=headers,
        )

    if response.status_code not in {200, 201}:
        raise RuntimeError(
            f"Supabase Storage upload failed ({response.status_code}): "
            f"{response.text}"
        )


def create_signed_url(path: str, expires_in: int = 60) -> str:
    """Create a temporary signed URL for a private Supabase Storage object.

    Supabase may return either a complete URL or a relative signed path.
    Relative responses such as
    /object/sign/<bucket>/<object>?token=...
    must be resolved below /storage/v1.
    """
    encoded_bucket = quote(SUPABASE_STORAGE_BUCKET, safe="")
    encoded_path = quote(path, safe="/")

    url = (
        f"{SUPABASE_URL}/storage/v1/object/sign/"
        f"{encoded_bucket}/{encoded_path}"
    )

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(
            url,
            json={"expiresIn": expires_in},
            headers=_headers("application/json"),
        )

    if response.status_code not in {200, 201}:
        raise RuntimeError(
            f"Supabase Storage signed URL failed ({response.status_code}): "
            f"{response.text}"
        )

    payload = response.json()
    signed_url = payload.get("signedURL") or payload.get("signedUrl")

    if not signed_url:
        raise RuntimeError("Supabase Storage returned no signed URL")

    # Supabase can return an already complete signed URL.
    if signed_url.startswith("http://") or signed_url.startswith("https://"):
        return signed_url

    # Some Supabase versions/responses already include /storage/v1.
    if signed_url.startswith("/storage/v1/"):
        return f"{SUPABASE_URL}{signed_url}"

    # Common response:
    # /object/sign/<bucket>/<object>?token=...
    # It must be resolved below the Storage API prefix.
    if not signed_url.startswith("/"):
        signed_url = f"/{signed_url}"

    return f"{SUPABASE_URL}/storage/v1{signed_url}"


def delete_object(path: str) -> None:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.delete(
            _object_url(path),
            headers=_headers(),
        )

    if response.status_code not in {200, 204, 404}:
        raise RuntimeError(
            f"Supabase Storage delete failed ({response.status_code}): "
            f"{response.text}"
        )


def download_object(path: str) -> bytes:
    """Download a private object for backend processing."""
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(
            _object_url(path),
            headers=_headers(),
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Supabase Storage download failed ({response.status_code}): "
            f"{response.text}"
        )

    return response.content
