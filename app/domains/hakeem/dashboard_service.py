from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.booking.service import BookingService
from app.domains.connections.service import ConnectionsService
from app.domains.hakeem.dashboard_schemas import (
    DashboardConnectionRequest,
    DashboardConsultationItem,
    DashboardQuickStats,
    HakeemDashboardResponse,
)
from app.domains.hakeem.service import HakeemService
from app.domains.users.service import UserService


class HakeemDashboardService:
    """Composes booking + connections + hakeem profile for the Today screen.

    Does not touch other domains' repositories — only their services.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.bookings = BookingService(session)
        self.connections = ConnectionsService(session)
        self.hakeem = HakeemService(session)
        self.users = UserService(session)

    async def get_today_overview(self, hakeem_user_id: UUID) -> HakeemDashboardResponse:
        user = await self.users.get_by_id(hakeem_user_id)

        schedule = await self.bookings.list_today_for_hakeem(hakeem_user_id)
        pending = await self.connections.list_pending_incoming(hakeem_user_id)
        week_count = await self.bookings.count_this_week(hakeem_user_id)
        response_rate = await self.connections.compute_response_rate(hakeem_user_id)
        rating = await self.hakeem.get_average_rating(hakeem_user_id)

        return HakeemDashboardResponse(
            greeting_name=user.full_name,
            consultations_today_count=len(schedule),
            quick_stats=DashboardQuickStats(
                consultations_this_week=week_count,
                average_rating=rating,
                response_rate=response_rate,
            ),
            todays_schedule=[
                DashboardConsultationItem(
                    id=b.id,
                    patient_id=b.patient.id,
                    patient_name=b.patient.full_name,
                    patient_avatar_url=b.patient.avatar_url,
                    scheduled_at=b.scheduled_at.isoformat(),
                    appointment_type=b.appointment_type,
                    can_join=b.can_join,
                    status=b.status,
                )
                for b in schedule
            ],
            pending_connection_requests=[
                DashboardConnectionRequest(
                    id=c.id,
                    requester_id=c.requester.id,
                    requester_name=c.requester.full_name,
                    requester_avatar_url=c.requester.avatar_url,
                    note=None,
                    created_at=c.created_at.isoformat(),
                )
                for c in pending
            ],
        )
