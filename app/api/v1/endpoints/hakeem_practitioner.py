from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_hakeem
from app.db.session import get_db_session
from app.domains.hakeem.availability_service import AvailabilityService
from app.domains.hakeem.dashboard_schemas import (
    CalendarMonthResponse,
    DateAvailabilityPatchRequest,
    DateAvailabilityResponse,
    HakeemDashboardResponse,
    HakeemMeProfileResponse,
    HakeemMeProfileUpdateRequest,
    WeeklyDefaultRequest,
    WeeklySlotResponse,
)
from app.domains.hakeem.dashboard_service import HakeemDashboardService
from app.domains.hakeem.service import HakeemService
from app.domains.connections.service import ConnectionsService
from app.domains.payments.schemas import (
    EarningsSummaryResponse,
    PayoutHistoryItem,
    RequestPayoutResponse,
)
from app.domains.payments.service import PaymentsService
from app.domains.users.models import User
from app.utils.pagination import CursorPage

router = APIRouter(prefix="/hakeem", tags=["hakeem"])


def get_dashboard_service(
    session: AsyncSession = Depends(get_db_session),
) -> HakeemDashboardService:
    return HakeemDashboardService(session)


def get_availability_service(
    session: AsyncSession = Depends(get_db_session),
) -> AvailabilityService:
    return AvailabilityService(session)


def get_hakeem_service(session: AsyncSession = Depends(get_db_session)) -> HakeemService:
    return HakeemService(session)


def get_payments_service(
    session: AsyncSession = Depends(get_db_session),
) -> PaymentsService:
    return PaymentsService(session)


def get_connections_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionsService:
    return ConnectionsService(session)


@router.get("/dashboard", response_model=HakeemDashboardResponse)
async def get_hakeem_dashboard(
    current_user: User = Depends(require_hakeem),
    service: HakeemDashboardService = Depends(get_dashboard_service),
) -> HakeemDashboardResponse:
    return await service.get_today_overview(current_user.id)


@router.get("/availability", response_model=CalendarMonthResponse)
async def get_availability_calendar(
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    current_user: User = Depends(require_hakeem),
    service: AvailabilityService = Depends(get_availability_service),
) -> CalendarMonthResponse:
    return await service.get_calendar_month(current_user.id, year, month)


@router.put("/availability/weekly-default", response_model=list[WeeklySlotResponse])
async def put_weekly_default(
    payload: WeeklyDefaultRequest,
    current_user: User = Depends(require_hakeem),
    service: AvailabilityService = Depends(get_availability_service),
) -> list[WeeklySlotResponse]:
    return await service.set_weekly_default(current_user.id, payload)


@router.patch("/availability/{day}", response_model=DateAvailabilityResponse)
async def patch_availability_date(
    day: date,
    payload: DateAvailabilityPatchRequest,
    current_user: User = Depends(require_hakeem),
    service: AvailabilityService = Depends(get_availability_service),
) -> DateAvailabilityResponse:
    return await service.patch_date(current_user.id, day, payload)

@router.get("/earnings/summary", response_model=EarningsSummaryResponse)
async def get_earnings_summary(
    current_user: User = Depends(require_hakeem),
    service: PaymentsService = Depends(get_payments_service),
) -> EarningsSummaryResponse:
    return await service.get_earnings_summary(current_user.id)


@router.get("/earnings/payout-history", response_model=CursorPage[PayoutHistoryItem])
async def get_payout_history(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(require_hakeem),
    service: PaymentsService = Depends(get_payments_service),
) -> CursorPage[PayoutHistoryItem]:
    return await service.list_payout_history(
        current_user.id, cursor=cursor, limit=limit
    )


@router.post("/earnings/request-payout", response_model=RequestPayoutResponse)
async def request_payout(
    current_user: User = Depends(require_hakeem),
    service: PaymentsService = Depends(get_payments_service),
) -> RequestPayoutResponse:
    return await service.request_payout(current_user.id)


@router.get("/me/profile", response_model=HakeemMeProfileResponse)
async def get_my_hakeem_profile(
    current_user: User = Depends(require_hakeem),
    hakeem_service: HakeemService = Depends(get_hakeem_service),
    connections: ConnectionsService = Depends(get_connections_service),
) -> HakeemMeProfileResponse:
    patients = await connections.count_accepted_for_user(current_user.id)
    return await hakeem_service.get_me_profile(
        current_user, patients_count=patients
    )


@router.patch("/me/profile", response_model=HakeemMeProfileResponse)
async def patch_my_hakeem_profile(
    payload: HakeemMeProfileUpdateRequest,
    current_user: User = Depends(require_hakeem),
    hakeem_service: HakeemService = Depends(get_hakeem_service),
    connections: ConnectionsService = Depends(get_connections_service),
) -> HakeemMeProfileResponse:
    updated = await hakeem_service.update_me_profile(current_user, payload)
    patients = await connections.count_accepted_for_user(current_user.id)
    updated.patients_count = patients
    return updated
