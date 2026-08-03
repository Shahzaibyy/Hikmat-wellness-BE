from app.core.exceptions import AppError


class InsufficientBalanceError(AppError):
    def __init__(self, message: str = "Pending balance is below the minimum payout threshold.") -> None:
        super().__init__(
            error_code="INSUFFICIENT_PAYOUT_BALANCE",
            message=message,
            status_code=400,
        )


class PayoutAlreadyPendingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="PAYOUT_ALREADY_PENDING",
            message="You already have a payout request awaiting admin review.",
            status_code=409,
        )
