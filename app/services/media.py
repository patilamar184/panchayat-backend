import io
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.models import Complaint, ComplaintMedia, ComplaintStatus

# extension -> (declared content type, Pillow format)
ALLOWED = {
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".png": ("image/png", "PNG"),
    ".webp": ("image/webp", "WEBP"),
}
MAX_PIXELS = 50_000_000
CHUNK = 64 * 1024


def _read_limited(upload: UploadFile, limit: int) -> bytes:
    buf = bytearray()
    while chunk := upload.file.read(CHUNK):
        buf.extend(chunk)
        if len(buf) > limit:
            raise DomainError(413, f"File is too large (maximum {limit // (1024 * 1024)} MB)")
    if not buf:
        raise DomainError(400, "The uploaded file is empty")
    return bytes(buf)


def validate_image(filename: str, declared_type: str | None, data_loader) -> tuple[str, bytes, int, int]:
    """Check extension, declared content type and the decoded image format.

    Returns (content_type, data, width, height).
    """
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise DomainError(415, "Only JPEG, PNG and WEBP images are allowed (.jpg, .jpeg, .png, .webp)")
    expected_type, expected_format = ALLOWED[ext]
    if (declared_type or "").split(";")[0].strip().lower() != expected_type:
        raise DomainError(415, "The declared content type does not match the file extension")

    data = data_loader()
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            actual_format = probe.format
            width, height = probe.size
            probe.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError):
        raise DomainError(400, "The file is not a valid image") from None
    if actual_format != expected_format:
        raise DomainError(415, "The image content does not match its extension or content type")
    return expected_type, data, width, height


def _complaint_dir(complaint_id: int) -> Path:
    return get_settings().media_root / "complaints" / str(complaint_id)


def file_path(media: ComplaintMedia) -> Path:
    return _complaint_dir(media.complaint_id) / media.stored_filename


def save_upload(db: Session, complaint: Complaint, uploader_id: int, upload: UploadFile) -> ComplaintMedia:
    s = get_settings()
    if complaint.status == ComplaintStatus.closed:
        raise DomainError(409, "Images cannot be added to a closed complaint")
    count = db.scalar(
        select(func.count()).select_from(ComplaintMedia).where(ComplaintMedia.complaint_id == complaint.id)
    )
    if (count or 0) >= s.max_images_per_complaint:
        raise DomainError(409, f"A complaint can have at most {s.max_images_per_complaint} images")

    original = os.path.basename((upload.filename or "image").replace("\\", "/"))[:255] or "image"
    content_type, data, width, height = validate_image(
        original, upload.content_type, lambda: _read_limited(upload, s.max_upload_bytes)
    )

    stored = f"{uuid.uuid4().hex}{Path(original).suffix.lower()}"
    directory = _complaint_dir(complaint.id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / stored
    path.write_bytes(data)

    media = ComplaintMedia(
        complaint_id=complaint.id,
        uploaded_by_id=uploader_id,
        original_filename=original,
        stored_filename=stored,
        content_type=content_type,
        size_bytes=len(data),
        width=width,
        height=height,
    )
    db.add(media)
    try:
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(media)
    return media


def get_owned_media(db: Session, citizen_id: int, media_id: int) -> ComplaintMedia:
    media = db.get(ComplaintMedia, media_id)
    if media is None or media.complaint.citizen_id != citizen_id:
        raise DomainError(404, "Image not found")
    return media


def delete_media(db: Session, media: ComplaintMedia) -> None:
    path = file_path(media)
    db.delete(media)
    db.commit()
    path.unlink(missing_ok=True)
