from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


class CompetitionOut(BaseModel):
    id: UUID
    name: str
    logo_url: str | None


@router.get("/", response_model=list[CompetitionOut])
async def list_competitions(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[CompetitionOut]:
    """Devuelve todas las competiciones activas."""
    resp = (
        supabase.table("competitions")
        .select("id, name, logo_url")
        .eq("is_active", True)
        .order("name", desc=False)
        .execute()
    )
    return resp.data or []
