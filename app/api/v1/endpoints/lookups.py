from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.domains.lookups.schemas import LookupsResponse
from app.domains.lookups.service import LookupService

router = APIRouter(prefix="/lookups", tags=["lookups"])


def get_lookup_service(session: AsyncSession = Depends(get_db_session)) -> LookupService:
    return LookupService(session)


@router.get("", response_model=LookupsResponse)
async def get_lookups(
    service: LookupService = Depends(get_lookup_service),
) -> LookupsResponse:
    return await service.get_all()
