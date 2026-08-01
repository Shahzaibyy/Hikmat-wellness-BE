from app.core.exceptions import AppError


class PostNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="POST_NOT_FOUND",
            message="Post not found.",
            status_code=404,
        )


class InvalidPostCategoryError(AppError):
    def __init__(self, value: str) -> None:
        super().__init__(
            error_code="INVALID_POST_CATEGORY",
            message="Invalid post category.",
            status_code=422,
            details={"field": "category", "value": value},
        )


class InvalidCursorError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="INVALID_CURSOR",
            message="Invalid pagination cursor.",
            status_code=400,
        )


class CannotFollowSelfError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="CANNOT_FOLLOW_SELF",
            message="You cannot follow yourself.",
            status_code=400,
        )


class AlreadyFollowingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="ALREADY_FOLLOWING",
            message="You are already following this user.",
            status_code=409,
        )


class NotFollowingError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="NOT_FOLLOWING",
            message="You are not following this user.",
            status_code=404,
        )
