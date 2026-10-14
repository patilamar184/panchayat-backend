from fastapi import APIRouter, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.api.deps import CitizenUser, DbSession
from app.core.errors import DomainError
from app.schemas.complaint import MediaRead
from app.services import complaints as complaint_svc
from app.services import media as svc

router = APIRouter(tags=["media"])


@router.post(
    "/complaints/{complaint_id}/media",
    response_model=MediaRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_image(complaint_id: int, file: UploadFile, citizen: CitizenUser, db: DbSession):
    complaint = complaint_svc.get_owned(db, citizen, complaint_id)
    return svc.save_upload(db, complaint, citizen.id, file)


@router.get("/complaints/{complaint_id}/media", response_model=list[MediaRead])
def list_images(complaint_id: int, citizen: CitizenUser, db: DbSession):
    return complaint_svc.get_owned(db, citizen, complaint_id).media


@router.get("/media/{media_id}/file")
def download_image(media_id: int, citizen: CitizenUser, db: DbSession):
    media = svc.get_owned_media(db, citizen.id, media_id)
    path = svc.file_path(media)
    if not path.is_file():
        raise DomainError(404, "Image file is missing")
    return FileResponse(
        path,
        media_type=media.content_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(media_id: int, citizen: CitizenUser, db: DbSession):
    svc.delete_media(db, svc.get_owned_media(db, citizen.id, media_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
