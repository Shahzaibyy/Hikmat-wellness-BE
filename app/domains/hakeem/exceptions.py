from app.core.exceptions import AppError


class HakeemAlreadyAppliedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="HAKEEM_ALREADY_APPLIED",
            message="A hakeem application already exists for this account or email.",
            status_code=409,
        )


class HakeemNotVerifiedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="HAKEEM_NOT_VERIFIED",
            message="Hakeem profile is not available.",
            status_code=404,
        )


class HakeemNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="HAKEEM_NOT_FOUND",
            message="Hakeem application not found.",
            status_code=404,
        )


class InvalidHakeemApplicationError(AppError):
    def __init__(self, message: str, *, field: str | None = None, value: str | None = None) -> None:
        details: dict | None = None
        if field is not None:
            details = {"field": field, "value": value}
        super().__init__(
            error_code="INVALID_HAKEEM_APPLICATION",
            message=message,
            status_code=422,
            details=details,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(
            error_code="FORBIDDEN",
            message=message,
            status_code=403,
        )


class AvailabilityConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="AVAILABILITY_CONFLICT",
            message=message,
            status_code=409,
        )
