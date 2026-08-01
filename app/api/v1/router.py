from fastapi import APIRouter

from app.api.v1.endpoints import auth, chat, community, connections, lookups, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(lookups.router)
api_router.include_router(community.router)
api_router.include_router(chat.router)
api_router.include_router(connections.router)
