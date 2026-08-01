from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.sockets.socket_manager import sio

# Register socket event handlers (side-effect import).
import app.sockets.chat_handler  # noqa: E402, F401

fastapi_app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(fastapi_app)
fastapi_app.include_router(api_router)


@fastapi_app.get("/")
async def root():
    return {"status": "ok", "app": settings.APP_NAME}


@fastapi_app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Socket.IO wraps FastAPI so both REST and websockets share one ASGI entrypoint.
# uvicorn app.main:app
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
