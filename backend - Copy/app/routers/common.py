import math
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


def paginate(items, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)) if total else 0,
    }


def clamp_page(page: int | None, page_size: int | None) -> tuple[int, int]:
    page = max(1, page or 1)
    page_size = min(max(1, page_size or 50), 200)
    return page, page_size


def save_upload(file: UploadFile, data: bytes, prefix: str = "file") -> tuple[str, str]:
    """Persist an upload and return (stored_file_name, absolute_path)."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}",
        )
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit.",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    stored = f"{prefix}-{uuid.uuid4().hex[:12]}{suffix}"
    path = Path(settings.UPLOAD_DIR) / stored
    path.write_bytes(data)
    return stored, str(path)
