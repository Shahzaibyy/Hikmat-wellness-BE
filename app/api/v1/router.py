from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    chat,
    community,
    connections,
    hakeem,
    hakeem_practitioner,
    lookups,
    uploads,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(lookups.router)
api_router.include_router(community.router)
api_router.include_router(chat.router)
api_router.include_router(connections.router)
api_router.include_router(hakeem.router)
api_router.include_router(hakeem_practitioner.router)
api_router.include_router(admin.router)
api_router.include_router(uploads.router)
