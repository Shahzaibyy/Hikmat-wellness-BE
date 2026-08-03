"""Dev-only seed utility — never imported by app.main or deploy hooks.

Usage:
  uv run python -m app.scripts.seed_test_data
  uv run python -m app.scripts.seed_test_data --reset
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.domains.chat.models import Conversation, ConversationParticipant
from app.domains.chat.schemas import MessageSendRequest
from app.domains.chat.service import ChatService
from app.domains.community.models import Post
from app.domains.community.schemas import (
    CommentCreateRequest,
    PostCreateRequest,
    PostTypeEnum,
)
from app.domains.community.service import CommunityService
from app.domains.connections.schemas import BlockCreateRequest, ConnectionRequestCreate
from app.domains.connections.service import ConnectionsService
from app.domains.users.models import (
    ActivityLevel,
    DietPreference,
    Gender,
    MizajType,
    PreferredLanguage,
    User,
)
from app.domains.users.schemas import OnboardingUpdateRequest
from app.domains.users.service import UserService

SEED_PASSWORD = "Test@1234"
YOMAIL_DOMAIN = "@yopmail.com"

# health_interest keys from lookup_options (seeded in first Alembic migration).
# post_category keys from community migration.
POST_CAT = {
    "digestion": "digestion",
    "skin": "skin_health",
    "mindfulness": "mindfulness",
    "herbal": "herbal_tea",
    "ancestral": "ancestral_wisdom",
}


@dataclass(frozen=True)
class HakeemSpec:
    n: int
    full_name: str
    specialization: str  # health_interest key
    bio: str
    city: str
    gender: str


@dataclass(frozen=True)
class UserSpec:
    n: int
    full_name: str
    mizaj_type: str
    health_interests: list[str]
    diet: str
    activity: str
    city: str
    gender: str


HAKEEMS: list[HakeemSpec] = [
    HakeemSpec(1, "Hakeem Zafar Ali", "Digestion", "20 years treating gut disorders with Unani herbs.", "Lahore", Gender.MALE.value),
    HakeemSpec(2, "Hakeema Sara Khan", "Skin & Beauty", "Classical Unani skincare and blood purification.", "Karachi", Gender.FEMALE.value),
    HakeemSpec(3, "Hakeem Imran Qureshi", "Stress & Sleep", "Mizaj-based sleep and anxiety protocols.", "Islamabad", Gender.MALE.value),
    HakeemSpec(4, "Hakeema Nadia Riaz", "Women's Health", "Women's wellness through humoral balance.", "Multan", Gender.FEMALE.value),
    HakeemSpec(5, "Hakeem Bilal Ahmed", "Joint & Bone Health", "Joints, bones, and mobility with herbal oils.", "Faisalabad", Gender.MALE.value),
    HakeemSpec(6, "Hakeema Farah Siddiqui", "Immunity", "Seasonal immunity and diet for all mizaj types.", "Peshawar", Gender.FEMALE.value),
]

USERS: list[UserSpec] = [
    UserSpec(1, "Ayesha Malik", MizajType.DAMVI.value, ["Digestion", "Immunity"], DietPreference.VEGETARIAN.value, ActivityLevel.MODERATE.value, "Lahore", Gender.FEMALE.value),
    UserSpec(2, "Omar Sheikh", MizajType.SAFRAVI.value, ["Skin & Beauty", "Stress & Sleep"], DietPreference.NON_VEGETARIAN.value, ActivityLevel.ACTIVE.value, "Karachi", Gender.MALE.value),
    UserSpec(3, "Fatima Noor", MizajType.BALGHAMI.value, ["Weight Management", "Joint & Bone Health"], DietPreference.VEGAN.value, ActivityLevel.LOW.value, "Islamabad", Gender.FEMALE.value),
    UserSpec(4, "Hassan Raza", MizajType.SAUDAVI.value, ["Stress & Sleep", "Heart Health"], DietPreference.EGGETARIAN.value, ActivityLevel.MODERATE.value, "Rawalpindi", Gender.MALE.value),
    UserSpec(5, "Sana Iqbal", MizajType.DAMVI.value, ["Hair Care", "Skin & Beauty"], DietPreference.VEGETARIAN.value, ActivityLevel.ACTIVE.value, "Lahore", Gender.FEMALE.value),
    UserSpec(6, "Usmar Farooq", MizajType.SAFRAVI.value, ["Digestion", "Blood Sugar Balance"], DietPreference.NON_VEGETARIAN.value, ActivityLevel.MODERATE.value, "Hyderabad", Gender.MALE.value),
]


def _hakeem_email(n: int) -> str:
    return f"hakeem.test{n}{YOMAIL_DOMAIN}"


def _user_email(n: int) -> str:
    return f"user.test{n}{YOMAIL_DOMAIN}"


def _avatar(n: int) -> str:
    return f"https://i.pravatar.cc/300?img={n}"


def _hakeem_notes(spec: HakeemSpec) -> str:
    """Encode seed hakeem metadata until a real hakeem domain exists."""
    return (
        "[SEED_HAKEEM]\n"
        f"specialization={spec.specialization}\n"
        f"is_verified_hakeem=true\n"
        f"bio={spec.bio}"
    )


async def _reset_yopmail_users(session: AsyncSession) -> int:
    """Hard-delete every @yopmail.com user (seed scope only) and orphan conversations."""
    result = await session.execute(
        select(User).where(User.email.ilike(f"%{YOMAIL_DOMAIN}"))
    )
    users = list(result.scalars().all())
    count = len(users)
    for user in users:
        await session.delete(user)
    await session.flush()

    # Conversations left with zero participants after CASCADE participant deletes.
    has_participant = exists(
        select(ConversationParticipant.conversation_id).where(
            ConversationParticipant.conversation_id == Conversation.id
        )
    )
    await session.execute(delete(Conversation).where(~has_participant))
    await session.flush()
    return count


async def _get_or_create_user(
    users: UserService,
    *,
    email: str,
    full_name: str,
) -> tuple[User, bool]:
    existing = await users.get_by_email(email)
    if existing is not None:
        return existing, False
    created = await users.create_user(
        email=email,
        hashed_password=hash_password(SEED_PASSWORD),
        full_name=full_name,
    )
    return created, True


async def _seed_hakeem(session: AsyncSession, spec: HakeemSpec) -> tuple[User, bool]:
    users = UserService(session)
    email = _hakeem_email(spec.n)
    user, created = await _get_or_create_user(
        users, email=email, full_name=spec.full_name
    )
    # Upsert profile fields so re-runs refresh seed metadata without duplicating.
    user.full_name = spec.full_name
    user.gender = spec.gender
    user.city = spec.city
    user.avatar_url = _avatar(spec.n)
    user.health_interests = [spec.specialization]
    user.notes = _hakeem_notes(spec)
    user.onboarding_completed = True
    user.is_active = True
    user.preferred_language = PreferredLanguage.URDU.value
    user.hashed_password = hash_password(SEED_PASSWORD)
    await users.repo.save(user)
    return user, created


async def _seed_regular_user(session: AsyncSession, spec: UserSpec) -> tuple[User, bool]:
    users = UserService(session)
    email = _user_email(spec.n)
    user, created = await _get_or_create_user(
        users, email=email, full_name=spec.full_name
    )
    await users.update_onboarding(
        user.id,
        OnboardingUpdateRequest(
            full_name=spec.full_name,
            gender=spec.gender,
            city=spec.city,
            avatar_url=_avatar(10 + spec.n),
            diet_preference=spec.diet,
            activity_level=spec.activity,
            mizaj_type=spec.mizaj_type,
            preferred_language=PreferredLanguage.ENGLISH.value,
            health_interests=spec.health_interests,
            notes="[SEED_USER] Completed onboarding for For You feed testing.",
            complete=True,
        ),
    )
    # Ensure password stays the known test password on re-seed.
    refreshed = await users.get_by_id(user.id)
    refreshed.hashed_password = hash_password(SEED_PASSWORD)
    refreshed.is_active = True
    await users.repo.save(refreshed)
    return refreshed, created


async def _ensure_pending(
    session: AsyncSession, requester: User, recipient: User
) -> str:
    connections = ConnectionsService(session)
    existing = await connections.repo.find_between(requester.id, recipient.id)
    if existing is not None:
        return f"exists ({existing.status})"
    await connections.request_connection(
        requester, ConnectionRequestCreate(recipient_id=recipient.id)
    )
    return "created pending"


async def _ensure_accepted_with_chat(
    session: AsyncSession, requester: User, recipient: User
) -> str:
    connections = ConnectionsService(session)
    chat = ChatService(session)
    chat.set_block_checker(connections.is_blocked_either_way)

    existing = await connections.repo.find_between(requester.id, recipient.id)
    if existing is None:
        conn = await connections.request_connection(
            requester, ConnectionRequestCreate(recipient_id=recipient.id)
        )
        accepted = await connections.accept(recipient, conn.id)
        conversation_id = accepted.conversation_id
    elif existing.status != "accepted":
        if existing.status == "pending" and existing.recipient_id == recipient.id:
            accepted = await connections.accept(recipient, existing.id)
            conversation_id = accepted.conversation_id
        else:
            # Force accepted path via get_or_create conversation + status update.
            existing.status = "accepted"
            await connections.repo.save(existing)
            conv = await chat.get_or_create_direct_conversation(
                requester.id, recipient.id
            )
            conversation_id = conv.id
    else:
        conv = await chat.get_or_create_direct_conversation(requester.id, recipient.id)
        conversation_id = conv.id

    assert conversation_id is not None

    # Sample messages only if conversation is empty (idempotent).
    page = await chat.list_messages(
        requester, conversation_id, limit=5, cursor=None
    )
    if page.items:
        return f"accepted + conversation {conversation_id} (messages already present)"

    m1 = await chat.send_message(
        requester,
        conversation_id,
        MessageSendRequest(body_text="Assalam o Alaikum! I need help with digestion."),
    )
    m2 = await chat.send_message(
        recipient,
        conversation_id,
        MessageSendRequest(
            body_text="Wa alaikum assalam. Tell me about your daily meals and sleep.",
            reply_to_message_id=m1.id,
        ),
    )
    await chat.send_message(
        requester,
        conversation_id,
        MessageSendRequest(
            body_text="I skip breakfast and drink a lot of chai. Any Unani tips?",
            reply_to_message_id=m2.id,
        ),
    )
    await chat.react(recipient, m1.id, "🙏")
    return f"accepted + conversation {conversation_id} + 3 messages (1 reply, 1 reaction)"


async def _ensure_block(session: AsyncSession, blocker: User, blocked: User) -> str:
    connections = ConnectionsService(session)
    if await connections.repo.is_blocked_either_way(blocker.id, blocked.id):
        return "block already exists"
    await connections.block(blocker, BlockCreateRequest(user_id=blocked.id))
    return "created block"


async def _ensure_community(
    session: AsyncSession,
    hakeems: dict[int, User],
    regulars: dict[int, User],
) -> list[str]:
    community = CommunityService(session)
    notes: list[str] = []

    # Follow so Following tab has content for user.test4.
    try:
        await community.follow_user(regulars[4], hakeems[1].id)
        notes.append(f"follow: {_user_email(4)} → {_hakeem_email(1)}")
    except Exception as exc:
        from app.domains.community.exceptions import AlreadyFollowingError

        if isinstance(exc, AlreadyFollowingError):
            notes.append(f"follow: {_user_email(4)} → {_hakeem_email(1)} (already)")
        else:
            raise

    authors_posts: list[tuple[User, PostCreateRequest]] = [
        (
            hakeems[1],
            PostCreateRequest(
                post_type=PostTypeEnum.tip,
                category=POST_CAT["digestion"],
                body_text="Tip: Sip warm saunf (fennel) water after heavy meals to ease bloating.",
                image_url=None,
            ),
        ),
        (
            hakeems[2],
            PostCreateRequest(
                post_type=PostTypeEnum.tip,
                category=POST_CAT["skin"],
                body_text="Tip: Apply cooled rose water before bed for calm, clear skin — Safravi types especially.",
                image_url="https://picsum.photos/seed/hikmat-skin/600/400",
            ),
        ),
        (
            hakeems[3],
            PostCreateRequest(
                post_type=PostTypeEnum.question,
                category=POST_CAT["mindfulness"],
                body_text="Question: What evening routine helps your Balghami patients sleep deeper?",
                image_url=None,
            ),
        ),
        (
            regulars[5],
            PostCreateRequest(
                post_type=PostTypeEnum.question,
                category=POST_CAT["herbal"],
                body_text="Question: Has anyone tried tulsi + ginger tea for seasonal immunity?",
                image_url=None,
            ),
        ),
        (
            hakeems[6],
            PostCreateRequest(
                post_type=PostTypeEnum.tip,
                category=POST_CAT["ancestral"],
                body_text="Tip: Align meals with seasons — lighter foods in summer heat, warming broths in winter.",
                image_url=None,
            ),
        ),
    ]

    # Idempotency for posts: if this author already has posts, reuse them.
    created_posts = []
    for author, payload in authors_posts:
        existing = await session.execute(
            select(Post.id).where(Post.author_id == author.id).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            notes.append(f"posts: skip {author.email} (already has posts)")
            row = await session.execute(
                select(Post).where(Post.author_id == author.id).limit(1)
            )
            post = row.scalar_one()
            created_posts.append((author, post))
            continue
        post_resp = await community.create_post(author, payload)
        row = await session.execute(select(Post).where(Post.id == post_resp.id))
        created_posts.append((author, row.scalar_one()))
        notes.append(f"post: {author.email} → {payload.post_type}/{payload.category}")
    if len(created_posts) >= 3 and created_posts[0][1].comment_count == 0:
        p0 = created_posts[0][1]
        p1 = created_posts[1][1]
        p2 = created_posts[2][1]
        await community.like_post(p0.id, regulars[1])
        await community.like_post(p0.id, regulars[2])
        await community.like_post(p1.id, regulars[4])
        await community.like_post(p2.id, regulars[6])
        await community.add_comment(
            p0.id,
            regulars[1],
            CommentCreateRequest(body_text="Tried this — bloating eased in two days!"),
        )
        await community.add_comment(
            p1.id,
            regulars[5],
            CommentCreateRequest(body_text="Does this work for oily skin too?"),
        )
        notes.append("likes/comments: seeded on first three posts")
    else:
        notes.append("likes/comments: skipped (already present or insufficient posts)")

    return notes


def _print_summary(
    *,
    hakeems: dict[int, User],
    regulars: dict[int, User],
    pending_note: str,
    accepted_note: str,
    block_note: str,
    community_notes: list[str],
) -> None:
    print()
    print("=" * 88)
    print("SEED SUMMARY — password for all accounts:", SEED_PASSWORD)
    print("=" * 88)
    print(f"{'EMAIL':<32} {'ROLE':<8} {'NAME':<24} {'NOTES'}")
    print("-" * 88)
    for n, u in sorted(hakeems.items()):
        spec = next(h for h in HAKEEMS if h.n == n)
        print(
            f"{_hakeem_email(n):<32} {'hakeem':<8} {u.full_name:<24} "
            f"spec={spec.specialization}"
        )
    for n, u in sorted(regulars.items()):
        spec = next(s for s in USERS if s.n == n)
        print(
            f"{_user_email(n):<32} {'user':<8} {u.full_name:<24} "
            f"mizaj={spec.mizaj_type} interests={','.join(spec.health_interests)}"
        )
    print("-" * 88)
    print("RELATIONSHIPS")
    print(f"  PENDING : {_user_email(1)} → {_hakeem_email(1)}  [{pending_note}]")
    print(f"  ACCEPTED: {_user_email(2)} ↔ {_hakeem_email(2)}  [{accepted_note}]")
    print(f"            → start chat testing by logging in as either of these two")
    print(f"  BLOCKED : {_user_email(3)} blocks {_hakeem_email(3)}  [{block_note}]")
    print(f"  CLEAN   : remaining pairs have no connection (fresh connect flow)")
    print("-" * 88)
    print("COMMUNITY")
    for line in community_notes:
        print(f"  - {line}")
    print("=" * 88)
    print(
        "NOTE: is_verified_hakeem is not a User column yet (hakeem domain stub). "
        "Seeded in notes as is_verified_hakeem=true; community API still returns false "
        "until hakeem profiles ship."
    )
    print()


async def run(*, reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        try:
            if reset:
                deleted = await _reset_yopmail_users(session)
                print(f"--reset: deleted {deleted} @{YOMAIL_DOMAIN.lstrip('@')} account(s)")

            hakeems: dict[int, User] = {}
            regulars: dict[int, User] = {}

            for spec in HAKEEMS:
                user, created = await _seed_hakeem(session, spec)
                hakeems[spec.n] = user
                print(f"{'created' if created else 'updated'} hakeem {_hakeem_email(spec.n)}")

            for spec in USERS:
                user, created = await _seed_regular_user(session, spec)
                regulars[spec.n] = user
                print(f"{'created' if created else 'updated'} user   {_user_email(spec.n)}")

            pending_note = await _ensure_pending(session, regulars[1], hakeems[1])
            accepted_note = await _ensure_accepted_with_chat(
                session, regulars[2], hakeems[2]
            )
            block_note = await _ensure_block(session, regulars[3], hakeems[3])
            community_notes = await _ensure_community(session, hakeems, regulars)

            await session.commit()
            _print_summary(
                hakeems=hakeems,
                regulars=regulars,
                pending_note=pending_note,
                accepted_note=accepted_note,
                block_note=block_note,
                community_notes=community_notes,
            )
        except Exception:
            await session.rollback()
            raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Seed Hikmat test accounts (Yopmail) for local E2E testing."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=f"Delete all *{YOMAIL_DOMAIN} users (and cascaded data) before seeding.",
    )
    args = parser.parse_args(argv)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    # Engine echo bypasses the logger — mute for readable seed output.
    from app.db.session import engine

    engine.echo = False
    asyncio.run(run(reset=args.reset))


if __name__ == "__main__":
    main()
