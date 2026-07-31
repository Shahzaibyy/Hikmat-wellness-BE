from app.core.exceptions import AppError


class UserAlreadyExistsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="USER_ALREADY_EXISTS",
            message="An account with this email already exists.",
            status_code=409,
        )


class InvalidCredentialsError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
            status_code=401,
        )


class InvalidTokenError(AppError):
    def __init__(self, message: str = "Invalid or expired token.") -> None:
        super().__init__(
            error_code="INVALID_TOKEN",
            message=message,
            status_code=401,
        )
