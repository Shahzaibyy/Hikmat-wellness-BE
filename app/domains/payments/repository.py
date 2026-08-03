from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.payments.models import PayoutBatch, PayoutBatchStatus, Transaction, TransactionStatus


class PaymentsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def sum_transactions(
        self,
        hakeem_user_id: UUID,
        *,
        statuses: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Decimal:
        stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.hakeem_user_id == hakeem_user_id,
            Transaction.status.in_(statuses),
        )
        if start is not None:
            stmt = stmt.where(Transaction.created_at >= start)
        if end is not None:
            stmt = stmt.where(Transaction.created_at < end)
        result = await self.session.execute(stmt)
        value = result.scalar_one()
        return Decimal(str(value))

    async def sum_pending_payouts(self, hakeem_user_id: UUID) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(PayoutBatch.amount), 0)).where(
                PayoutBatch.hakeem_user_id == hakeem_user_id,
                PayoutBatch.status.in_(
                    [
                        PayoutBatchStatus.PENDING_REVIEW.value,
                        PayoutBatchStatus.APPROVED.value,
                    ]
                ),
            )
        )
        return Decimal(str(result.scalar_one()))

    async def get_open_payout(self, hakeem_user_id: UUID) -> PayoutBatch | None:
        result = await self.session.execute(
            select(PayoutBatch)
            .where(
                PayoutBatch.hakeem_user_id == hakeem_user_id,
                PayoutBatch.status == PayoutBatchStatus.PENDING_REVIEW.value,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_payout(self, batch: PayoutBatch) -> PayoutBatch:
        self.session.add(batch)
        await self.session.flush()
        await self.session.refresh(batch)
        return batch

    async def list_payouts(
        self,
        hakeem_user_id: UUID,
        *,
        limit: int,
        before_requested_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> list[PayoutBatch]:
        stmt = (
            select(PayoutBatch)
            .where(PayoutBatch.hakeem_user_id == hakeem_user_id)
            .order_by(PayoutBatch.requested_at.desc(), PayoutBatch.id.desc())
            .limit(limit)
        )
        if before_requested_at is not None and before_id is not None:
            stmt = stmt.where(
                (PayoutBatch.requested_at < before_requested_at)
                | (
                    (PayoutBatch.requested_at == before_requested_at)
                    & (PayoutBatch.id < before_id)
                )
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_transaction(self, txn: Transaction) -> Transaction:
        self.session.add(txn)
        await self.session.flush()
        await self.session.refresh(txn)
        return txn
