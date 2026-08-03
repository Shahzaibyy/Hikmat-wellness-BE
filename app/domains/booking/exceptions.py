from app.core.exceptions import AppError


class BookingNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="BOOKING_NOT_FOUND",
            message="Booking not found.",
            status_code=404,
        )


class BookingConflictError(AppError):
    def __init__(self, message: str = "Booking conflicts with an existing appointment.") -> None:
        super().__init__(
            error_code="BOOKING_CONFLICT",
            message=message,
            status_code=409,
        )
