"""Socket.IO chat handlers — thin like routes; business logic lives in ChatService."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.exceptions import AppError
from app.core.security import safe_decode_token
from app.db.session import AsyncSessionLocal
from app.domains.chat.schemas import (
    DeleteScopeEnum,
    MessageEditRequest,
    MessageSendRequest,
)
from app.domains.chat.service import ChatService
from app.domains.users.service import UserService
from app.sockets.socket_manager import conversation_room, sio, user_room

logger = logging.getLogger(__name__)


async def _session_user_id(sid: str) -> UUID | None:
    session = await sio.get_session(sid)
    raw = session.get("user_id") if session else None
    if raw is None:
        return None
    return UUID(str(raw))


def _error_payload(exc: Exception) -> dict:
    if isinstance(exc, AppError):
        return {
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        }
    logger.exception("Unhandled socket error")
    return {
        "error_code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred.",
        "details": None,
    }


@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    token = auth.get("token") or auth.get("access_token")
    if not token:
        logger.info("Rejecting socket connect %s: missing token", sid)
        await sio.emit(
            "connect:error",
            {"error_code": "INVALID_TOKEN", "message": "Missing auth token."},
            to=sid,
        )
        return False

    payload = safe_decode_token(token)
    if payload is None or payload.get("type") != "access":
        await sio.emit(
            "connect:error",
            {"error_code": "INVALID_TOKEN", "message": "Invalid or expired token."},
            to=sid,
        )
        return False

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        await sio.emit(
            "connect:error",
            {"error_code": "INVALID_TOKEN", "message": "Invalid token subject."},
            to=sid,
        )
        return False

    async with AsyncSessionLocal() as session:
        try:
            user = await UserService(session).get_by_id(user_id)
            chat = ChatService(session)
            conversation_ids = await chat.list_user_conversation_ids(user.id)
            await session.commit()
        except Exception:
            await session.rollback()
            await sio.emit(
                "connect:error",
                {"error_code": "INVALID_TOKEN", "message": "User not found."},
                to=sid,
            )
            return False

    await sio.save_session(
        sid,
        {"user_id": str(user.id), "conversation_ids": [str(c) for c in conversation_ids]},
    )
    await sio.enter_room(sid, user_room(user.id))
    for cid in conversation_ids:
        await sio.enter_room(sid, conversation_room(cid))
        await sio.emit(
            "presence:online",
            {"user_id": str(user.id), "conversation_id": str(cid)},
            room=conversation_room(cid),
            skip_sid=sid,
        )

    logger.info("Socket connected user=%s sid=%s rooms=%s", user.id, sid, len(conversation_ids))
    return True


@sio.event
async def disconnect(sid):
    session = await sio.get_session(sid)
    if not session:
        return
    user_id = session.get("user_id")
    conversation_ids = session.get("conversation_ids") or []
    if user_id:
        for cid in conversation_ids:
            await sio.emit(
                "presence:offline",
                {"user_id": user_id, "conversation_id": cid},
                room=conversation_room(cid),
                skip_sid=sid,
            )
    logger.info("Socket disconnected sid=%s user=%s", sid, user_id)


@sio.on("conversation:join")
async def conversation_join(sid, data):
    """Client can join a newly created conversation room after connect."""
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        conversation_id = UUID(str(data["conversation_id"]))
    except (KeyError, ValueError, TypeError):
        await sio.emit(
            "message:error",
            {"error_code": "INVALID_PAYLOAD", "message": "conversation_id required."},
            to=sid,
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            chat = ChatService(session)
            await chat.ensure_participant(conversation_id, user_id)
            await session.commit()
        except AppError as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return
        except Exception as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return

    await sio.enter_room(sid, conversation_room(conversation_id))
    sess = await sio.get_session(sid)
    ids = set(sess.get("conversation_ids") or [])
    ids.add(str(conversation_id))
    sess["conversation_ids"] = list(ids)
    await sio.save_session(sid, sess)


@sio.on("message:send")
async def message_send(sid, data):
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        conversation_id = UUID(str(data["conversation_id"]))
        body_text = str(data["body_text"])
        reply_raw = data.get("reply_to_message_id")
        reply_to = UUID(str(reply_raw)) if reply_raw else None
    except (KeyError, ValueError, TypeError):
        await sio.emit(
            "message:error",
            {
                "error_code": "INVALID_PAYLOAD",
                "message": "conversation_id and body_text are required.",
            },
            to=sid,
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await UserService(session).get_by_id(user_id)
            chat = ChatService(session)
            # Wire block checker if connections domain is importable.
            try:
                from app.domains.connections.service import ConnectionsService

                chat.set_block_checker(ConnectionsService(session).is_blocked_either_way)
            except ImportError:
                pass
            message = await chat.send_message(
                user,
                conversation_id,
                MessageSendRequest(body_text=body_text, reply_to_message_id=reply_to),
            )
            await session.commit()
        except AppError as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return
        except Exception as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return

    await sio.emit(
        "message:new",
        message.model_dump(mode="json"),
        room=conversation_room(conversation_id),
    )


@sio.on("message:edit")
async def message_edit(sid, data):
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        message_id = UUID(str(data["message_id"]))
        body_text = str(data["body_text"])
    except (KeyError, ValueError, TypeError):
        await sio.emit(
            "message:error",
            {"error_code": "INVALID_PAYLOAD", "message": "message_id and body_text required."},
            to=sid,
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await UserService(session).get_by_id(user_id)
            chat = ChatService(session)
            message = await chat.edit_message(
                user, message_id, MessageEditRequest(body_text=body_text)
            )
            await session.commit()
        except AppError as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return
        except Exception as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return

    await sio.emit(
        "message:edited",
        message.model_dump(mode="json"),
        room=conversation_room(message.conversation_id),
    )


@sio.on("message:delete")
async def message_delete(sid, data):
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        message_id = UUID(str(data["message_id"]))
        scope = DeleteScopeEnum(str(data.get("scope", "for_me")))
    except (KeyError, ValueError, TypeError):
        await sio.emit(
            "message:error",
            {
                "error_code": "INVALID_PAYLOAD",
                "message": "message_id and scope (for_me|for_everyone) required.",
            },
            to=sid,
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await UserService(session).get_by_id(user_id)
            chat = ChatService(session)
            # Need conversation_id before delete-for-me returns None.
            existing = await chat.repo.get_message(message_id)
            if existing is None:
                from app.domains.chat.exceptions import MessageNotFoundError

                raise MessageNotFoundError()
            conversation_id = existing.conversation_id
            result = await chat.delete_message(user, message_id, scope)
            await session.commit()
        except AppError as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return
        except Exception as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return

    if scope == DeleteScopeEnum.for_everyone and result is not None:
        await sio.emit(
            "message:deleted",
            {
                "message": result.model_dump(mode="json"),
                "scope": scope.value,
            },
            room=conversation_room(conversation_id),
        )
    else:
        await sio.emit(
            "message:deleted",
            {
                "message_id": str(message_id),
                "conversation_id": str(conversation_id),
                "scope": scope.value,
            },
            to=sid,
        )


@sio.on("message:react")
async def message_react(sid, data):
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        message_id = UUID(str(data["message_id"]))
        emoji = str(data["emoji"])
    except (KeyError, ValueError, TypeError):
        await sio.emit(
            "message:error",
            {"error_code": "INVALID_PAYLOAD", "message": "message_id and emoji required."},
            to=sid,
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await UserService(session).get_by_id(user_id)
            chat = ChatService(session)
            message, _ = await chat.react(user, message_id, emoji)
            await session.commit()
        except AppError as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return
        except Exception as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return

    await sio.emit(
        "message:reaction_updated",
        {
            "message_id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "user_id": str(user_id),
            "emoji": emoji,
            "reactions": [r.model_dump(mode="json") for r in message.reactions],
        },
        room=conversation_room(message.conversation_id),
    )


@sio.on("message:unreact")
async def message_unreact(sid, data):
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        message_id = UUID(str(data["message_id"]))
    except (KeyError, ValueError, TypeError):
        await sio.emit(
            "message:error",
            {"error_code": "INVALID_PAYLOAD", "message": "message_id required."},
            to=sid,
        )
        return

    async with AsyncSessionLocal() as session:
        try:
            user = await UserService(session).get_by_id(user_id)
            chat = ChatService(session)
            message = await chat.unreact(user, message_id)
            await session.commit()
        except AppError as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return
        except Exception as exc:
            await session.rollback()
            await sio.emit("message:error", _error_payload(exc), to=sid)
            return

    await sio.emit(
        "message:reaction_updated",
        {
            "message_id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "user_id": str(user_id),
            "emoji": None,
            "reactions": [r.model_dump(mode="json") for r in message.reactions],
        },
        room=conversation_room(message.conversation_id),
    )


@sio.on("typing:start")
async def typing_start(sid, data):
    await _emit_typing(sid, data, is_typing=True)


@sio.on("typing:stop")
async def typing_stop(sid, data):
    await _emit_typing(sid, data, is_typing=False)


async def _emit_typing(sid, data, *, is_typing: bool):
    user_id = await _session_user_id(sid)
    if user_id is None:
        return
    try:
        conversation_id = UUID(str(data["conversation_id"]))
    except (KeyError, ValueError, TypeError):
        return
    await sio.emit(
        "typing:update",
        {
            "conversation_id": str(conversation_id),
            "user_id": str(user_id),
            "is_typing": is_typing,
        },
        room=conversation_room(conversation_id),
        skip_sid=sid,
    )
