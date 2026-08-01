from app.core.exceptions import AppError


class ConnectionNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="CONNECTION_NOT_FOUND",
            message="Connection request not found.",
            status_code=404,
        )


class ConnectionForbiddenError(AppError):
    def __init__(self, message: str = "Not allowed for this connection.") -> None:
        super().__init__(
            error_code="CONNECTION_FORBIDDEN",
            message=message,
            status_code=403,
        )


class ConnectionConflictError(AppError):
    def __init__(self, message: str = "A connection already exists.") -> None:
        super().__init__(
            error_code="CONNECTION_CONFLICT",
            message=message,
            status_code=409,
        )


class ConnectionBlockedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="CONNECTION_BLOCKED",
            message="Cannot connect — a block exists between these users.",
            status_code=403,
        )


class InvalidConnectionStateError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="INVALID_CONNECTION_STATE",
            message=message,
            status_code=400,
        )


class CannotConnectSelfError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="CANNOT_CONNECT_SELF",
            message="You cannot send a connection request to yourself.",
            status_code=400,
        )
