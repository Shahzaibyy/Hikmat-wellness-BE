from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EarningsSummaryResponse(BaseModel):
    pending_balance: Decimal
    currency: str = "PKR"
    available_withdrawal_date: datetime | None = None
    this_month: Decimal
    last_month: Decimal
    total_earned: Decimal


class PayoutHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: str
    status: str
    reference: str
    requested_at: datetime
    paid_at: datetime | None = None


class RequestPayoutResponse(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    status: str
    reference: str
    requested_at: datetime
    message: str = "Payout request submitted for admin review."
