"""Serve short-lived signed downloads for private verification documents (local storage)."""

from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.utils.object_storage import LocalPrivateStorage, get_object_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.get("/signed")
async def download_signed_private_file(
    key: str = Query(...),
    exp: int = Query(...),
    sig: str = Query(...),
) -> FileResponse:
    storage = get_object_storage()
    if not isinstance(storage, LocalPrivateStorage):
        raise HTTPException(
            status_code=400,
            detail="Signed local downloads are only used with local private storage.",
        )
    path = storage.verify_signed_request(unquote(key), exp, sig)
    if path is None:
        raise HTTPException(status_code=403, detail="Invalid or expired signed URL.")
    return FileResponse(path)
