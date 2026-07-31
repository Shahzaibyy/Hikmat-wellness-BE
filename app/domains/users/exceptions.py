from app.core.exceptions import AppError


class UserNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="USER_NOT_FOUND",
            message="User not found.",
            status_code=404,
        )


class InvalidOnboardingValueError(AppError):
    def __init__(self, field: str, value: str) -> None:
        super().__init__(
            error_code="INVALID_ONBOARDING_VALUE",
            message=f"Invalid value for {field}.",
            status_code=422,
            details={"field": field, "value": value},
        )
