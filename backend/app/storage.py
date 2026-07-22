import os
from urllib.parse import quote

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "case-documents")


def _headers(content_type: str | None = None) -> dict[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "Supabase Storage is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY on the backend."
        )

    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def upload_object(path: str, content: bytes, content_type: str) -> None:
    encoded_path = quote(path, safe="/")
    url = (
        f"{SUPABASE_URL}/storage/v1/object/"
        f"{quote(SUPABASE_STORAGE_BUCKET, safe='')}/{encoded_path}"
    )
    headers = _headers(content_type)
    headers["x-upsert"] = "false"

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, content=content, headers=headers)

    if response.status_code not in {200, 201}:
        raise RuntimeError(
            f"Supabase Storage upload failed ({response.status_code}): "
            f"{response.text}"
        )


def download_object(path: str) -> tuple[bytes, str]:
    encoded_path = quote(path, safe="/")
    url = (
        f"{SUPABASE_URL}/storage/v1/object/"
        f"{quote(SUPABASE_STORAGE_BUCKET, safe='')}/{encoded_path}"
    )

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, headers=_headers())

    if response.status_code != 200:
        raise FileNotFoundError(
            f"Supabase Storage download failed ({response.status_code})"
        )

    return response.content, response.headers.get(
        "content-type", "application/octet-stream"
    )
