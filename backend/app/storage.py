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

    if signed_url.startswith("http://") or signed_url.startswith("https://"):
        return signed_url

    if signed_url.startswith("/storage/v1/"):
        return f"{SUPABASE_URL}{signed_url}"

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
    # A large file may take minutes to transfer; keep connect timeout short but
    # allow slow storage reads. Stream chunks rather than one httpx response body.
    timeout = httpx.Timeout(connect=15.0, read=180.0, write=30.0, pool=30.0)
    chunks: list[bytes] = []
    with httpx.Client(timeout=timeout) as client:
        with client.stream("GET", _object_url(path), headers=_headers()) as response:
            if response.status_code != 200:
                response.read()
                raise RuntimeError(
                    f"Supabase Storage download failed ({response.status_code}): "
                    f"{response.text[:1000]}"
                )
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                chunks.append(chunk)
    # The extractor currently requires bytes; the worker still needs enough RAM
    # for the whole document. Streaming extraction is a separate improvement.
    return b"".join(chunks)


def create_signed_upload_url(path: str) -> str:
    """Issue a short-lived Supabase signed upload URL (no service key in browser)."""
    _require_configuration()
    bucket = quote(SUPABASE_STORAGE_BUCKET, safe="")
    object_path = quote(path, safe="/")
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(
            f"{SUPABASE_URL}/storage/v1/object/upload/sign/{bucket}/{object_path}",
            headers=_headers("application/json"),
            json={},
        )
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"Supabase signed upload failed ({response.status_code}): {response.text}")
    signed = response.json().get("url") or response.json().get("signedURL")
    if not signed:
        raise RuntimeError("Supabase returned no signed upload URL")
    if signed.startswith("https://") or signed.startswith("http://"):
        return signed
    if signed.startswith("/storage/v1/"):
        return f"{SUPABASE_URL}{signed}"
    return f"{SUPABASE_URL}/storage/v1/{signed.lstrip('/')}"


def get_object_size(path: str) -> int | None:
    """Verify an uploaded object exists and read its actual size."""
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.head(_object_url(path), headers=_headers())
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"Supabase object verification failed ({response.status_code}): {response.text}")
    length = response.headers.get("content-length")
    if length is None:
        raise RuntimeError("Supabase object verification returned no content length")
    return int(length)
