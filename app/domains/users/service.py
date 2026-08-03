from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lookups.service import LookupService, MIZAJ_META
from app.domains.users.exceptions import InvalidOnboardingValueError, UserNotFoundError
from app.domains.users.models import (
    ActivityLevel,
    DietPreference,
    Gender,
    HakeemGenderPreference,
    MizajType,
    PreferredLanguage,
    User,
    UserRole,
)
from app.domains.users.repository import UserRepository
from app.domains.users.schemas import OnboardingUpdateRequest, UserResponse


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UserRepository(session)
        self.lookups = LookupService(session)

    async def to_response(self, user: User) -> UserResponse:
        """Build UserResponse; for hakeems include live verification fields."""
        data = UserResponse.model_validate(user)
        if user.role != UserRole.HAKEEM.value:
            return data
        from app.domains.hakeem.repository import HakeemRepository

        profile = await HakeemRepository(self.repo.session).get_by_user_id(user.id)
        if profile is None:
            return data.model_copy(
                update={"is_verified_hakeem": False, "verification_status": "pending"}
            )
        return data.model_copy(
            update={
                "is_verified_hakeem": profile.is_verified_hakeem,
                "verification_status": profile.verification_status,
            }
        )

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self.repo.get_by_email(email)

    async def create_user(
        self,
        *,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
        role: str | None = None,
        city: str | None = None,
    ) -> User:
        return await self.repo.create(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            city=city,
        )

    async def update_onboarding(self, user_id: UUID, payload: OnboardingUpdateRequest) -> User:
        user = await self.get_by_id(user_id)
        await self._validate_onboarding(payload)

        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if payload.gender is not None:
            user.gender = payload.gender
        if payload.date_of_birth is not None:
            user.date_of_birth = payload.date_of_birth
        if payload.city is not None:
            user.city = payload.city
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url
        if payload.diet_preference is not None:
            user.diet_preference = payload.diet_preference
        if payload.activity_level is not None:
            user.activity_level = payload.activity_level
        if payload.mizaj_type is not None:
            user.mizaj_type = payload.mizaj_type
            # Keep legacy display field in sync for older UI consumers.
            user.mizaj_hint = MIZAJ_META[payload.mizaj_type]["label"]
        elif payload.mizaj_hint is not None:
            user.mizaj_hint = payload.mizaj_hint
        if payload.mizaj_assessment_answers is not None:
            user.mizaj_assessment_answers = payload.mizaj_assessment_answers
        if payload.preferred_language is not None:
            user.preferred_language = payload.preferred_language
        if payload.preferred_hakeem_gender is not None:
            user.preferred_hakeem_gender = payload.preferred_hakeem_gender
        if payload.health_interests is not None:
            user.health_interests = payload.health_interests
        if payload.health_flags is not None:
            user.health_flags = payload.health_flags
        if payload.notes is not None:
            user.notes = payload.notes
        if payload.complete:
            user.onboarding_completed = True

        return await self.repo.save(user)

    async def _validate_onboarding(self, payload: OnboardingUpdateRequest) -> None:
        if payload.gender is not None and payload.gender not in {g.value for g in Gender}:
            raise InvalidOnboardingValueError("gender", payload.gender)
        if payload.diet_preference is not None and payload.diet_preference not in {
            d.value for d in DietPreference
        }:
            raise InvalidOnboardingValueError("diet_preference", payload.diet_preference)
        if payload.activity_level is not None and payload.activity_level not in {
            a.value for a in ActivityLevel
        }:
            raise InvalidOnboardingValueError("activity_level", payload.activity_level)
        if payload.mizaj_type is not None and payload.mizaj_type not in {
            m.value for m in MizajType
        }:
            raise InvalidOnboardingValueError("mizaj_type", payload.mizaj_type)
        if payload.preferred_language is not None and payload.preferred_language not in {
            lang.value for lang in PreferredLanguage
        }:
            raise InvalidOnboardingValueError("preferred_language", payload.preferred_language)
        if payload.preferred_hakeem_gender is not None and payload.preferred_hakeem_gender not in {
            pref.value for pref in HakeemGenderPreference
        }:
            raise InvalidOnboardingValueError(
                "preferred_hakeem_gender", payload.preferred_hakeem_gender
            )

        if payload.health_interests is not None:
            allowed = await self.lookups.get_keys("health_interest")
            for item in payload.health_interests:
                if item not in allowed:
                    raise InvalidOnboardingValueError("health_interests", item)

        if payload.health_flags is not None:
            allowed = await self.lookups.get_keys("health_flag")
            for item in payload.health_flags:
                if item not in allowed:
                    raise InvalidOnboardingValueError("health_flags", item)
