from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domains.auth.exceptions import UserAlreadyExistsError
from app.domains.auth.service import AuthService
from app.domains.auth.schemas import TokenResponse
from app.domains.hakeem.exceptions import (
    HakeemAlreadyAppliedError,
    HakeemNotFoundError,
    HakeemNotVerifiedError,
    InvalidHakeemApplicationError,
)
from app.domains.hakeem.models import HakeemProfile, HakeemVerificationStatus
from app.domains.hakeem.repository import HakeemRepository
from app.domains.hakeem.schemas import (
    MIN_YEARS_OF_EXPERIENCE,
    HakeemAdminReviewResponse,
    HakeemPublicProfileResponse,
    HakeemReviewDecisionRequest,
    HakeemSignupRequest,
)
from app.domains.hakeem.dashboard_schemas import (
    HakeemMeProfileResponse,
    HakeemMeProfileUpdateRequest,
)
from app.domains.lookups.service import LookupService
from app.domains.users.models import PreferredLanguage, User, UserRole
from app.domains.users.service import UserService
from app.utils.object_storage import get_object_storage
from app.utils.pagination import CursorPage, build_page, decode_cursor


class HakeemService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = HakeemRepository(session)
        self.users = UserService(session)
        self.lookups = LookupService(session)
        self.auth = AuthService(session)
        self._storage = None

    @property
    def storage(self):
        # Lazy: dashboard/profile must not require a writable upload dir.
        if self._storage is None:
            self._storage = get_object_storage()
        return self._storage

    async def apply(self, payload: HakeemSignupRequest) -> TokenResponse:
        await self._validate_application(payload)

        existing = await self.users.get_by_email(str(payload.email))
        if existing is not None:
            if await self.repo.get_by_user_id(existing.id) is not None:
                raise HakeemAlreadyAppliedError()
            raise UserAlreadyExistsError()

        # Single request session = one transaction (committed by get_db_session).
        user = await self.users.create_user(
            email=str(payload.email),
            hashed_password=hash_password(payload.password),
            full_name=payload.full_name.strip(),
            role=UserRole.HAKEEM.value,
            city=payload.city.strip(),
        )
        profile = HakeemProfile(
            user_id=user.id,
            specializations=payload.specializations,
            bio=payload.bio.strip(),
            city=payload.city.strip(),
            years_of_experience=payload.years_of_experience,
            languages_spoken=payload.languages_spoken,
            consultation_fee=payload.consultation_fee,
            rating_count=0,
            national_id_number=payload.national_id_number.strip(),
            national_id_document_url=payload.national_id_document_url,
            license_number=payload.license_number,
            license_document_url=payload.license_document_url,
            training_institute=payload.training_institute.strip(),
            previous_practice_location=payload.previous_practice_location,
            reason_for_joining=payload.reason_for_joining.strip(),
            reference_contact=payload.reference_contact,
            verification_status=HakeemVerificationStatus.PENDING.value,
            is_verified_hakeem=False,
        )
        await self.repo.create(profile)
        return await self.auth._issue_tokens(user)

    async def get_public_profile(self, hakeem_user_id: UUID) -> HakeemPublicProfileResponse:
        profile = await self.repo.get_by_user_id(hakeem_user_id)
        if profile is None or not profile.is_verified_hakeem:
            raise HakeemNotVerifiedError()
        user = await self.users.get_by_id(hakeem_user_id)
        return HakeemPublicProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            specializations=profile.specializations,
            bio=profile.bio,
            city=profile.city,
            years_of_experience=profile.years_of_experience,
            languages_spoken=profile.languages_spoken,
            consultation_fee=float(profile.consultation_fee)
            if profile.consultation_fee is not None
            else None,
            rating_avg=float(profile.rating_avg) if profile.rating_avg is not None else None,
            rating_count=profile.rating_count,
            is_verified_hakeem=profile.is_verified_hakeem,
        )

    async def get_average_rating(self, hakeem_user_id: UUID) -> float | None:
        profile = await self.repo.get_by_user_id(hakeem_user_id)
        if profile is None or profile.rating_avg is None:
            return None
        return float(profile.rating_avg)

    async def verified_user_ids(self, user_ids: list[UUID]) -> set[UUID]:
        return await self.repo.list_verified_user_ids(user_ids)

    async def get_me_profile(
        self, hakeem_user: User, *, patients_count: int = 0
    ) -> HakeemMeProfileResponse:
        profile = await self.repo.get_by_user_id(hakeem_user.id)
        if profile is None:
            raise HakeemNotFoundError()
        return HakeemMeProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=hakeem_user.full_name,
            avatar_url=hakeem_user.avatar_url,
            email=hakeem_user.email,
            specializations=profile.specializations,
            bio=profile.bio,
            city=profile.city,
            years_of_experience=profile.years_of_experience,
            languages_spoken=profile.languages_spoken,
            consultation_fee=float(profile.consultation_fee)
            if profile.consultation_fee is not None
            else None,
            rating_avg=float(profile.rating_avg) if profile.rating_avg is not None else None,
            rating_count=profile.rating_count,
            is_verified_hakeem=profile.is_verified_hakeem,
            verification_status=profile.verification_status,
            patients_count=patients_count,
        )

    async def update_me_profile(
        self, hakeem_user: User, payload: HakeemMeProfileUpdateRequest
    ) -> HakeemMeProfileResponse:
        """Edit public profile fields. Does NOT reset verification status.

        Decision: bio / specializations / fee / languages / city edits do not
        require re-verification. Identity docs and experience years remain locked.
        """
        profile = await self.repo.get_by_user_id(hakeem_user.id)
        if profile is None:
            raise HakeemNotFoundError()

        data = payload.model_dump(exclude_unset=True)
        if "specializations" in data:
            allowed_specs = await self.lookups.get_keys("health_interest")
            for item in data["specializations"]:
                if item not in allowed_specs:
                    raise InvalidHakeemApplicationError(
                        "Invalid specialization.",
                        field="specializations",
                        value=item,
                    )
            profile.specializations = data["specializations"]
        if "languages_spoken" in data:
            allowed_langs = {lang.value for lang in PreferredLanguage}
            for item in data["languages_spoken"]:
                if item not in allowed_langs:
                    raise InvalidHakeemApplicationError(
                        "Invalid language. Use lookup keys: urdu, english, punjabi.",
                        field="languages_spoken",
                        value=item,
                    )
            profile.languages_spoken = data["languages_spoken"]
        if "bio" in data:
            profile.bio = data["bio"]
        if "consultation_fee" in data:
            profile.consultation_fee = data["consultation_fee"]
        if "city" in data:
            profile.city = data["city"]
            hakeem_user.city = data["city"]
            await self.users.repo.save(hakeem_user)

        await self.repo.save(profile)
        return await self.get_me_profile(hakeem_user)

    async def list_applications(
        self,
        *,
        status: str,
        cursor: str | None,
        limit: int,
    ) -> CursorPage[HakeemAdminReviewResponse]:
        cursor_data = None
        if cursor:
            try:
                cursor_data = decode_cursor(cursor)
            except ValueError as exc:
                raise InvalidHakeemApplicationError("Invalid pagination cursor.") from exc

        cursor_created_at = None
        cursor_id = None
        if cursor_data:
            try:
                cursor_created_at = datetime.fromisoformat(str(cursor_data["t"]))
                cursor_id = UUID(str(cursor_data["id"]))
            except (KeyError, ValueError) as exc:
                raise InvalidHakeemApplicationError("Invalid pagination cursor.") from exc

        rows = await self.repo.list_by_status(
            status,
            limit=limit + 1,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
        page = build_page(
            rows,
            limit=limit,
            cursor_builder=lambda p: {
                "t": p.created_at.isoformat(),
                "id": str(p.id),
            },
        )
        items = [await self._to_admin_response(p, sign_docs=False) for p in page.items]
        return CursorPage(items=items, next_cursor=page.next_cursor, has_more=page.has_more)

    async def get_application_for_admin(self, profile_id: UUID) -> HakeemAdminReviewResponse:
        profile = await self.repo.get_by_id(profile_id)
        if profile is None:
            raise HakeemNotFoundError()
        return await self._to_admin_response(profile, sign_docs=True)

    async def approve(self, profile_id: UUID, admin: User) -> HakeemAdminReviewResponse:
        profile = await self._get_for_review(profile_id)
        profile.verification_status = HakeemVerificationStatus.APPROVED.value
        profile.is_verified_hakeem = True
        profile.reviewed_by_admin_id = admin.id
        profile.reviewed_at = datetime.now(timezone.utc)
        profile.verification_notes = None
        saved = await self.repo.save(profile)
        # TODO(notifications): NotificationService.notify_hakeem_approved(saved.user_id)
        return await self._to_admin_response(saved, sign_docs=True)

    async def reject(
        self, profile_id: UUID, admin: User, payload: HakeemReviewDecisionRequest
    ) -> HakeemAdminReviewResponse:
        profile = await self._get_for_review(profile_id)
        profile.verification_status = HakeemVerificationStatus.REJECTED.value
        profile.is_verified_hakeem = False
        profile.reviewed_by_admin_id = admin.id
        profile.reviewed_at = datetime.now(timezone.utc)
        profile.verification_notes = payload.notes
        saved = await self.repo.save(profile)
        # TODO(notifications): NotificationService.notify_hakeem_rejected(saved.user_id, payload.notes)
        return await self._to_admin_response(saved, sign_docs=True)

    async def request_more_info(
        self, profile_id: UUID, admin: User, payload: HakeemReviewDecisionRequest
    ) -> HakeemAdminReviewResponse:
        profile = await self._get_for_review(profile_id)
        if not payload.notes:
            raise InvalidHakeemApplicationError(
                "Notes are required when requesting more information.",
                field="notes",
            )
        profile.verification_status = HakeemVerificationStatus.NEEDS_MORE_INFO.value
        profile.is_verified_hakeem = False
        profile.reviewed_by_admin_id = admin.id
        profile.reviewed_at = datetime.now(timezone.utc)
        profile.verification_notes = payload.notes
        saved = await self.repo.save(profile)
        # TODO(notifications): NotificationService.notify_hakeem_needs_info(saved.user_id, payload.notes)
        return await self._to_admin_response(saved, sign_docs=True)

    async def _get_for_review(self, profile_id: UUID) -> HakeemProfile:
        profile = await self.repo.get_by_id(profile_id)
        if profile is None:
            raise HakeemNotFoundError()
        return profile

    async def _validate_application(self, payload: HakeemSignupRequest) -> None:
        if payload.years_of_experience < MIN_YEARS_OF_EXPERIENCE:
            raise InvalidHakeemApplicationError(
                f"Applicants must have at least {MIN_YEARS_OF_EXPERIENCE} years of "
                "professional experience. Fresh graduates and applicants with less than "
                f"{MIN_YEARS_OF_EXPERIENCE} years cannot apply yet.",
                field="years_of_experience",
                value=str(payload.years_of_experience),
            )

        allowed_specs = await self.lookups.get_keys("health_interest")
        for item in payload.specializations:
            if item not in allowed_specs:
                raise InvalidHakeemApplicationError(
                    "Invalid specialization.",
                    field="specializations",
                    value=item,
                )

        allowed_langs = {lang.value for lang in PreferredLanguage}
        for item in payload.languages_spoken:
            if item not in allowed_langs:
                raise InvalidHakeemApplicationError(
                    "Invalid language. Use lookup keys: urdu, english, punjabi.",
                    field="languages_spoken",
                    value=item,
                )

        # Reject duplicate application if a hakeem profile somehow exists for email's user
        # (email uniqueness already covered above for new users).

    async def _to_admin_response(
        self, profile: HakeemProfile, *, sign_docs: bool
    ) -> HakeemAdminReviewResponse:
        user = await self.users.get_by_id(profile.user_id)
        nid_url = profile.national_id_document_url
        lic_url = profile.license_document_url
        if sign_docs:
            nid_url = self.storage.generate_signed_url(nid_url, expires_in=900)
            lic_url = self.storage.generate_signed_url(lic_url, expires_in=900)
        return HakeemAdminReviewResponse(
            id=profile.id,
            user_id=profile.user_id,
            email=user.email,
            full_name=user.full_name,
            specializations=profile.specializations,
            bio=profile.bio,
            city=profile.city,
            years_of_experience=profile.years_of_experience,
            languages_spoken=profile.languages_spoken,
            consultation_fee=float(profile.consultation_fee)
            if profile.consultation_fee is not None
            else None,
            national_id_number=profile.national_id_number,
            national_id_document_url=nid_url,
            license_number=profile.license_number,
            license_document_url=lic_url,
            training_institute=profile.training_institute,
            previous_practice_location=profile.previous_practice_location,
            reason_for_joining=profile.reason_for_joining,
            reference_contact=profile.reference_contact,
            screening_answers_extra=profile.screening_answers_extra,
            verification_status=profile.verification_status,
            verification_notes=profile.verification_notes,
            is_verified_hakeem=profile.is_verified_hakeem,
            created_at=profile.created_at,
            reviewed_at=profile.reviewed_at,
        )
