from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    safe_decode_token,
    verify_password,
)
from app.domains.auth.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
)
from app.domains.auth.schemas import LoginRequest, SignupRequest, TokenResponse
from app.domains.users.schemas import UserResponse
from app.domains.users.service import UserService


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserService(session)

    async def signup(self, payload: SignupRequest) -> TokenResponse:
        existing = await self.users.get_by_email(payload.email)
        if existing is not None:
            raise UserAlreadyExistsError()

        user = await self.users.create_user(
            email=str(payload.email),
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name,
        )
        return await self._issue_tokens(user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_email(str(payload.email))
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise InvalidCredentialsError()
        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = safe_decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise InvalidTokenError()

        try:
            user_id = UUID(payload["sub"])
        except (KeyError, ValueError) as exc:
            raise InvalidTokenError() from exc

        user = await self.users.get_by_id(user_id)
        if not user.is_active:
            raise InvalidTokenError("User is inactive.")
        return await self._issue_tokens(user)

    async def _issue_tokens(self, user) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(subject=user.id),
            refresh_token=create_refresh_token(subject=user.id),
            user=await self.users.to_response(user),
        )
