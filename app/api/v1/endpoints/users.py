from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.domains.users.models import User
from app.domains.users.schemas import OnboardingUpdateRequest, UserResponse
from app.domains.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(session: AsyncSession = Depends(get_db_session)) -> UserService:
    return UserService(session)


@router.patch("/me/onboarding", response_model=UserResponse)
async def update_onboarding(
    payload: OnboardingUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    user = await service.update_onboarding(current_user.id, payload)
    return UserResponse.model_validate(user)
