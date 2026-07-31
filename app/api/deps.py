from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import safe_decode_token
from app.db.session import get_db_session
from app.domains.auth.exceptions import InvalidTokenError
from app.domains.users.models import User
from app.domains.users.service import UserService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidTokenError("Missing bearer token.")

    payload = safe_decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise InvalidTokenError()

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError() from exc

    return await UserService(session).get_by_id(user_id)
