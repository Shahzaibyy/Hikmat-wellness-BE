from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domains.auth.schemas import TokenResponse
from app.domains.hakeem.exceptions import InvalidHakeemApplicationError
from app.domains.hakeem.schemas import (
    HakeemPublicProfileResponse,
    HakeemSignupRequest,
    VerificationDocumentUploadResponse,
)
from app.domains.hakeem.service import HakeemService
from app.utils.object_storage import (
    ALLOWED_CONTENT_TYPES,
    MAX_UPLOAD_BYTES,
    get_object_storage,
)

router = APIRouter(tags=["hakeem"])


def get_hakeem_service(session: AsyncSession = Depends(get_db_session)) -> HakeemService:
    return HakeemService(session)


@router.post("/auth/signup/hakeem", response_model=TokenResponse, tags=["auth"])
async def signup_hakeem(
    payload: HakeemSignupRequest,
    service: HakeemService = Depends(get_hakeem_service),
) -> TokenResponse:
    return await service.apply(payload)


@router.get("/hakeems/{user_id}/profile", response_model=HakeemPublicProfileResponse)
async def get_hakeem_public_profile(
    user_id: UUID,
    service: HakeemService = Depends(get_hakeem_service),
) -> HakeemPublicProfileResponse:
    return await service.get_public_profile(user_id)


@router.post(
    "/uploads/verification-document",
    response_model=VerificationDocumentUploadResponse,
    tags=["uploads"],
)
async def upload_verification_document(
    document_type: str = Form(..., description="national_id | license"),
    file: UploadFile = File(...),
) -> VerificationDocumentUploadResponse:
    """Upload a private verification document; returns a non-public storage URL for signup."""
    if document_type not in {"national_id", "license"}:
        raise InvalidHakeemApplicationError(
            "document_type must be 'national_id' or 'license'.",
            field="document_type",
            value=document_type,
        )
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidHakeemApplicationError(
            "Only JPEG, PNG, or PDF documents are allowed.",
            field="file",
            value=content_type,
        )
    data = await file.read()
    if not data:
        raise InvalidHakeemApplicationError("Empty file.", field="file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidHakeemApplicationError(
            f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB).",
            field="file",
        )
    storage = get_object_storage()
    try:
        url = storage.upload_private(
            data=data,
            filename=file.filename or "document",
            content_type=content_type,
            prefix="hakeem-verification",
        )
    except ValueError as exc:
        raise InvalidHakeemApplicationError(str(exc), field="file") from exc
    return VerificationDocumentUploadResponse(
        document_url=url,
        document_type=document_type,
        key=storage.resolve_key(url),
    )
