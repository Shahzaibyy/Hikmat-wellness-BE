"""Dev-only: seed 5 fully-verified hakeem accounts (bypasses admin review wait).

Usage:
  uv run python -m app.scripts.seed_verified_hakeems
  uv run python -m app.scripts.seed_verified_hakeems --reset
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.domains.hakeem.models import HakeemProfile, HakeemVerificationStatus
from app.domains.hakeem.schemas import HakeemSignupRequest
from app.domains.hakeem.service import HakeemService
from app.domains.users.models import User, UserRole
from app.domains.users.service import UserService

SEED_PASSWORD = "Test@1234"
# Placeholder private-shaped URLs (valid strings for apply(); not real uploads).
PLACEHOLDER_DOC = "private://hakeem-verification/seed/placeholder.pdf"


@dataclass(frozen=True)
class VerifiedHakeemSpec:
    email: str
    full_name: str
    specialization: str  # health_interest lookup key
    years: int
    fee: float
    city: str
    languages: list[str]
    avatar_n: int
    national_id: str
    license_number: str
    bio: str
    training_institute: str
    previous_practice: str
    reason: str


SPECS: list[VerifiedHakeemSpec] = [
    VerifiedHakeemSpec(
        email="hakeem.rehman@yopmail.com",
        full_name="Hakeem Abdul Rehman",
        specialization="Digestion",
        years=12,
        fee=800.0,
        city="Lahore",
        languages=["urdu", "english"],
        avatar_n=21,
        national_id="42101-7654321-1",
        license_number="PK-UNANI-1001",
        bio=(
            "Senior Unani physician focused on digestive disorders, "
            "humoral imbalance, and diet-based recovery protocols."
        ),
        training_institute="Tibbia College, University of Punjab",
        previous_practice="Shalamar Unani Clinic, Lahore",
        reason=(
            "I want to reach more patients digitally while keeping "
            "classical Unani consultation standards intact."
        ),
    ),
    VerifiedHakeemSpec(
        email="hakeem.yusuf@yopmail.com",
        full_name="Hakeem Muhammad Yusuf",
        specialization="Skin & Beauty",
        years=8,
        fee=650.0,
        city="Karachi",
        languages=["urdu"],
        avatar_n=22,
        national_id="42101-7654322-2",
        license_number="PK-UNANI-1002",
        bio=(
            "Specialist in Unani dermatology — blood purification, "
            "eczema, acne, and natural skin rejuvenation therapies."
        ),
        training_institute="Hamdard University, Karachi",
        previous_practice="Clifton Unani Skin Centre, Karachi",
        reason=(
            "Looking to offer verified skin consultations online "
            "for patients who cannot visit in person regularly."
        ),
    ),
    VerifiedHakeemSpec(
        email="hakeem.ayesha@yopmail.com",
        full_name="Hakeema Ayesha Siddiqui",
        specialization="Women's Health",
        years=10,
        fee=900.0,
        city="Islamabad",
        languages=["urdu", "english"],
        avatar_n=23,
        national_id="42101-7654323-3",
        license_number="PK-UNANI-1003",
        bio=(
            "Women's wellness through Unani medicine — hormonal "
            "balance, postpartum care, and lifestyle counselling."
        ),
        training_institute="Qarshi University, Lahore",
        previous_practice="Capital Unani Women's Clinic, Islamabad",
        reason=(
            "I hope Hikmat helps more women access trusted Unani "
            "care with privacy and verified practitioners."
        ),
    ),
    VerifiedHakeemSpec(
        email="hakeem.tariq@yopmail.com",
        full_name="Hakeem Tariq Mehmood",
        specialization="Joint & Bone Health",
        years=15,
        fee=750.0,
        city="Faisalabad",
        languages=["urdu"],
        avatar_n=24,
        national_id="42101-7654324-4",
        license_number="PK-UNANI-1004",
        bio=(
            "Fifteen years treating joint pain, arthritis, and "
            "mobility issues with herbal oils and regimental therapy."
        ),
        training_institute="Govt. Tibbia College, Faisalabad",
        previous_practice="Madina Town Unani Ortho Clinic",
        reason=(
            "Many rural patients need remote follow-ups for chronic "
            "joint conditions — Hikmat makes that practical."
        ),
    ),
    VerifiedHakeemSpec(
        email="hakeem.imran@yopmail.com",
        full_name="Hakeem Imran Qureshi",
        specialization="Stress & Sleep",
        years=5,
        fee=450.0,
        city="Multan",
        languages=["urdu", "english"],
        avatar_n=25,
        national_id="42101-7654325-5",
        license_number="PK-UNANI-1005",
        bio=(
            "Mizaj-based protocols for anxiety, insomnia, and "
            "stress-related digestive complaints in young adults."
        ),
        training_institute="Islamabad Tibbia College",
        previous_practice="Multan Sleep & Calm Unani Clinic",
        reason=(
            "I want to help busy professionals manage stress with "
            "authentic Unani guidance through a trusted platform."
        ),
    ),
]

SEED_EMAILS = {spec.email for spec in SPECS}


async def _reset_seed_hakeems(session: AsyncSession) -> int:
    """Delete only the 5 verified-hakeem seed emails managed by this script."""
    result = await session.execute(select(User).where(User.email.in_(SEED_EMAILS)))
    users = list(result.scalars().all())
    for user in users:
        await session.delete(user)
    await session.flush()
    return len(users)


async def _approve_profile(session: AsyncSession, user_id) -> HakeemProfile:
    hakeems = HakeemService(session)
    profile = await hakeems.repo.get_by_user_id(user_id)
    assert profile is not None
    profile.verification_status = HakeemVerificationStatus.APPROVED.value
    profile.is_verified_hakeem = True
    profile.reviewed_at = datetime.now(timezone.utc)
    profile.verification_notes = "[SEED] Auto-approved for local testing."
    return await hakeems.repo.save(profile)


async def _upsert_verified_hakeem(
    session: AsyncSession, spec: VerifiedHakeemSpec
) -> tuple[User, HakeemProfile, str]:
    users = UserService(session)
    hakeems = HakeemService(session)
    existing = await users.get_by_email(spec.email)

    if existing is None:
        tokens = await hakeems.apply(
            HakeemSignupRequest(
                email=spec.email,
                password=SEED_PASSWORD,
                full_name=spec.full_name,
                national_id_number=spec.national_id,
                national_id_document_url=PLACEHOLDER_DOC,
                license_number=spec.license_number,
                license_document_url=PLACEHOLDER_DOC,
                specializations=[spec.specialization],
                years_of_experience=spec.years,
                city=spec.city,
                languages_spoken=spec.languages,
                consultation_fee=spec.fee,
                bio=spec.bio,
                training_institute=spec.training_institute,
                previous_practice_location=spec.previous_practice,
                reason_for_joining=spec.reason,
                reference_contact="0300-1234567",
                agrees_to_terms=True,
            )
        )
        user = await users.get_by_id(tokens.user.id)
        action = "created"
    else:
        user = existing
        profile = await hakeems.repo.get_by_user_id(user.id)
        if profile is None:
            # Email exists without profile — recreate via delete is safer; raise clear error.
            raise RuntimeError(
                f"{spec.email} exists without a hakeem profile. "
                "Re-run with --reset to recreate cleanly."
            )
        # Refresh mutable profile + login password for idempotent re-runs.
        user.full_name = spec.full_name
        user.role = UserRole.HAKEEM.value
        user.city = spec.city
        user.hashed_password = hash_password(SEED_PASSWORD)
        user.is_active = True
        profile.specializations = [spec.specialization]
        profile.bio = spec.bio
        profile.city = spec.city
        profile.years_of_experience = spec.years
        profile.languages_spoken = spec.languages
        profile.consultation_fee = spec.fee
        profile.national_id_number = spec.national_id
        profile.license_number = spec.license_number
        profile.training_institute = spec.training_institute
        profile.previous_practice_location = spec.previous_practice
        profile.reason_for_joining = spec.reason
        await users.repo.save(user)
        await hakeems.repo.save(profile)
        action = "updated"

    user.avatar_url = f"https://i.pravatar.cc/300?img={spec.avatar_n}"
    await users.repo.save(user)
    profile = await _approve_profile(session, user.id)
    return user, profile, action


def _print_summary(rows: list[tuple[VerifiedHakeemSpec, User]]) -> None:
    print()
    print("=" * 100)
    print("VERIFIED HAKEEM SEED — password for all:", SEED_PASSWORD)
    print("=" * 100)
    print(
        f"{'NAME':<28} {'EMAIL':<30} {'CITY':<12} {'YEARS':>5} {'FEE':>6}  SPECIALIZATION"
    )
    print("-" * 100)
    for spec, user in rows:
        print(
            f"{spec.full_name:<28} {spec.email:<30} {spec.city:<12} "
            f"{spec.years:>5} {int(spec.fee):>6}  {spec.specialization}"
        )
        print(f"  user_id={user.id}")
    print("=" * 100)
    print(
        "All five are APPROVED (is_verified_hakeem=true). "
        "GET /api/v1/hakeems/{user_id}/profile should succeed without admin action."
    )
    print()


async def run(*, reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        try:
            if reset:
                deleted = await _reset_seed_hakeems(session)
                print(
                    f"--reset: deleted {deleted} verified-hakeem seed account(s) "
                    f"(emails: {', '.join(sorted(SEED_EMAILS))})"
                )

            rows: list[tuple[VerifiedHakeemSpec, User]] = []
            for spec in SPECS:
                user, _profile, action = await _upsert_verified_hakeem(session, spec)
                print(f"{action}: {spec.email} ({spec.full_name})")
                rows.append((spec, user))

            await session.commit()
            _print_summary(rows)
        except Exception:
            await session.rollback()
            raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Seed 5 fully-verified hakeem test accounts (Yopmail)."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete only this script's 5 hakeem seed emails, then re-seed.",
    )
    args = parser.parse_args(argv)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    engine.echo = False
    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()
