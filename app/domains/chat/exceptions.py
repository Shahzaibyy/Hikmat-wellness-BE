from app.core.exceptions import AppError


class ConversationNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="CONVERSATION_NOT_FOUND",
            message="Conversation not found.",
            status_code=404,
        )


class NotConversationParticipantError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="NOT_CONVERSATION_PARTICIPANT",
            message="You are not a participant in this conversation.",
            status_code=403,
        )


class MessageNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="MESSAGE_NOT_FOUND",
            message="Message not found.",
            status_code=404,
        )


class MessageForbiddenError(AppError):
    def __init__(self, message: str = "You cannot modify this message.") -> None:
        super().__init__(
            error_code="MESSAGE_FORBIDDEN",
            message=message,
            status_code=403,
        )


class InvalidMessagePayloadError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            error_code="INVALID_MESSAGE_PAYLOAD",
            message=message,
            status_code=422,
        )


class MessagingBlockedError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="MESSAGING_BLOCKED",
            message="Messaging is blocked between these users.",
            status_code=403,
        )


class InvalidCursorError(AppError):
    def __init__(self) -> None:
        super().__init__(
            error_code="INVALID_CURSOR",
            message="Invalid pagination cursor.",
            status_code=400,
        )


class ConversationExistsError(AppError):
    def __init__(self, conversation_id: str) -> None:
        super().__init__(
            error_code="CONVERSATION_EXISTS",
            message="A conversation between these users already exists.",
            status_code=409,
            details={"conversation_id": conversation_id},
        )
