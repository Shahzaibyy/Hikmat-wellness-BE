from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db_session
from app.domains.hakeem.models import HakeemVerificationStatus
from app.domains.hakeem.schemas import HakeemAdminReviewResponse, HakeemReviewDecisionRequest
from app.domains.hakeem.service import HakeemService
from app.domains.users.models import User
from app.utils.pagination import CursorPage

router = APIRouter(prefix="/admin", tags=["admin"])


def get_hakeem_service(session: AsyncSession = Depends(get_db_session)) -> HakeemService:
    return HakeemService(session)


@router.get(
    "/hakeem-applications",
    response_model=CursorPage[HakeemAdminReviewResponse],
)
async def list_hakeem_applications(
    status: HakeemVerificationStatus = Query(default=HakeemVerificationStatus.PENDING),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    _admin: User = Depends(require_admin),
    service: HakeemService = Depends(get_hakeem_service),
) -> CursorPage[HakeemAdminReviewResponse]:
    return await service.list_applications(
        status=status.value, cursor=cursor, limit=limit
    )


@router.get(
    "/hakeem-applications/{application_id}",
    response_model=HakeemAdminReviewResponse,
)
async def get_hakeem_application(
    application_id: UUID,
    _admin: User = Depends(require_admin),
    service: HakeemService = Depends(get_hakeem_service),
) -> HakeemAdminReviewResponse:
    return await service.get_application_for_admin(application_id)


@router.post(
    "/hakeem-applications/{application_id}/approve",
    response_model=HakeemAdminReviewResponse,
)
async def approve_hakeem_application(
    application_id: UUID,
    admin: User = Depends(require_admin),
    service: HakeemService = Depends(get_hakeem_service),
) -> HakeemAdminReviewResponse:
    return await service.approve(application_id, admin)


@router.post(
    "/hakeem-applications/{application_id}/reject",
    response_model=HakeemAdminReviewResponse,
)
async def reject_hakeem_application(
    application_id: UUID,
    payload: HakeemReviewDecisionRequest,
    admin: User = Depends(require_admin),
    service: HakeemService = Depends(get_hakeem_service),
) -> HakeemAdminReviewResponse:
    return await service.reject(application_id, admin, payload)


@router.post(
    "/hakeem-applications/{application_id}/request-more-info",
    response_model=HakeemAdminReviewResponse,
)
async def request_more_info_hakeem_application(
    application_id: UUID,
    payload: HakeemReviewDecisionRequest,
    admin: User = Depends(require_admin),
    service: HakeemService = Depends(get_hakeem_service),
) -> HakeemAdminReviewResponse:
    return await service.request_more_info(application_id, admin, payload)
