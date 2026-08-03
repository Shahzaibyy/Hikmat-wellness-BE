from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.payments.exceptions import InsufficientBalanceError, PayoutAlreadyPendingError
from app.domains.payments.models import PayoutBatch, PayoutBatchStatus, TransactionStatus
from app.domains.payments.repository import PaymentsRepository
from app.domains.payments.schemas import (
    EarningsSummaryResponse,
    PayoutHistoryItem,
    RequestPayoutResponse,
)
from app.utils.pagination import CursorPage, build_page, decode_cursor

# Minimum pending balance (PKR) required to request a payout.
MIN_PAYOUT_THRESHOLD = Decimal("1000.00")

# Pending balance becomes withdrawable after this many days (matches UI copy).
WITHDRAWAL_HOLD_DAYS = 7


class PaymentsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = PaymentsRepository(session)

    async def get_earnings_summary(self, hakeem_user_id: UUID) -> EarningsSummaryResponse:
        now = datetime.now(timezone.utc)
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if this_month_start.month == 1:
            last_month_start = this_month_start.replace(year=this_month_start.year - 1, month=12)
        else:
            last_month_start = this_month_start.replace(month=this_month_start.month - 1)

        earn_statuses = [TransactionStatus.COMPLETED.value, TransactionStatus.HELD.value]
        pending_statuses = [TransactionStatus.PENDING.value, TransactionStatus.HELD.value]

        held_and_pending = await self.repo.sum_transactions(
            hakeem_user_id, statuses=pending_statuses
        )
        open_payouts = await self.repo.sum_pending_payouts(hakeem_user_id)
        pending_balance = held_and_pending - open_payouts
        if pending_balance < 0:
            pending_balance = Decimal("0.00")

        this_month = await self.repo.sum_transactions(
            hakeem_user_id,
            statuses=earn_statuses,
            start=this_month_start,
            end=None,
        )
        last_month = await self.repo.sum_transactions(
            hakeem_user_id,
            statuses=earn_statuses,
            start=last_month_start,
            end=this_month_start,
        )
        total_earned = await self.repo.sum_transactions(
            hakeem_user_id, statuses=[TransactionStatus.COMPLETED.value]
        )

        return EarningsSummaryResponse(
            pending_balance=pending_balance.quantize(Decimal("0.01")),
            currency="PKR",
            available_withdrawal_date=now + timedelta(days=WITHDRAWAL_HOLD_DAYS),
            this_month=this_month.quantize(Decimal("0.01")),
            last_month=last_month.quantize(Decimal("0.01")),
            total_earned=total_earned.quantize(Decimal("0.01")),
        )

    async def list_payout_history(
        self, hakeem_user_id: UUID, *, cursor: str | None, limit: int
    ) -> CursorPage[PayoutHistoryItem]:
        before_at: datetime | None = None
        before_id: UUID | None = None
        if cursor:
            data = decode_cursor(cursor)
            before_at = datetime.fromisoformat(data["t"])
            before_id = UUID(data["id"])

        rows = await self.repo.list_payouts(
            hakeem_user_id,
            limit=limit + 1,
            before_requested_at=before_at,
            before_id=before_id,
        )
        page = build_page(
            rows,
            limit=limit,
            cursor_builder=lambda r: {
                "t": r.requested_at.isoformat(),
                "id": str(r.id),
            },
        )
        items = [
            PayoutHistoryItem(
                id=r.id,
                amount=r.amount,
                currency=r.currency,
                status=r.status,
                reference=r.reference,
                requested_at=r.requested_at,
                paid_at=r.paid_at,
            )
            for r in page.items
        ]
        return CursorPage(items=items, next_cursor=page.next_cursor, has_more=page.has_more)


    async def request_payout(self, hakeem_user_id: UUID) -> RequestPayoutResponse:
        if await self.repo.get_open_payout(hakeem_user_id) is not None:
            raise PayoutAlreadyPendingError()

        summary = await self.get_earnings_summary(hakeem_user_id)
        if summary.pending_balance < MIN_PAYOUT_THRESHOLD:
            raise InsufficientBalanceError(
                f"Minimum payout is PKR {MIN_PAYOUT_THRESHOLD}. "
                f"Current pending balance: PKR {summary.pending_balance}."
            )

        now = datetime.now(timezone.utc)
        ref = f"PAY-{uuid4().hex[:8].upper()}"
        batch = PayoutBatch(
            hakeem_user_id=hakeem_user_id,
            amount=summary.pending_balance,
            currency="PKR",
            status=PayoutBatchStatus.PENDING_REVIEW.value,
            reference=ref,
            period_end=now,
            requested_at=now,
        )
        created = await self.repo.create_payout(batch)
        return RequestPayoutResponse(
            id=created.id,
            amount=created.amount,
            currency=created.currency,
            status=created.status,
            reference=created.reference,
            requested_at=created.requested_at,
        )
