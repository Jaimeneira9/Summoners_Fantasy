from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


class ActivityEvent(BaseModel):
    id: UUID
    type: str
    player_name: str
    player_role: str
    player_image_url: str | None
    player_team: str
    buyer_name: str | None
    seller_name: str | None
    price: float
    executed_at: str


def _check_membership(supabase: Client, league_id: str, user_id: str) -> None:
    resp = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")


@router.get("/{league_id}", response_model=list[ActivityEvent])
async def get_activity(
    league_id: UUID,
    limit: int = 50,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[ActivityEvent]:
    _check_membership(supabase, str(league_id), user["id"])

    tx_resp = (
        supabase.table("transactions")
        .select(
            "id, type, buyer_id, seller_id, player_id, price, executed_at,"
            " players(name, role, image_url, team)"
        )
        .eq("league_id", str(league_id))
        .order("executed_at", desc=True)
        .limit(limit)
        .execute()
    )
    transactions = tx_resp.data or []
    if not transactions:
        return []

    # Recoger IDs únicos de members para resolver nombres
    member_ids: set[str] = set()
    for tx in transactions:
        if tx.get("buyer_id"):
            member_ids.add(tx["buyer_id"])
        if tx.get("seller_id"):
            member_ids.add(tx["seller_id"])

    names: dict[str, str] = {}
    if member_ids:
        members_resp = (
            supabase.table("league_members")
            .select("id, user_id, display_name")
            .in_("id", list(member_ids))
            .execute()
        )
        members_data = members_resp.data or []

        # Resolve usernames from profiles (same source as leaderboard)
        user_ids = [m["user_id"] for m in members_data if m.get("user_id")]
        profiles_map: dict[str, str] = {}
        if user_ids:
            profiles_resp = (
                supabase.table("profiles")
                .select("id, username")
                .in_("id", user_ids)
                .execute()
            )
            profiles_map = {
                p["id"]: p["username"]
                for p in (profiles_resp.data or [])
                if p.get("username")
            }

        for m in members_data:
            profile_username = profiles_map.get(m.get("user_id", ""))
            names[m["id"]] = m.get("display_name") or profile_username or "Manager"

    result = []
    for tx in transactions:
        player = tx.get("players") or {}
        result.append(ActivityEvent(
            id=tx["id"],
            type=tx["type"],
            player_name=player.get("name", "Desconocido"),
            player_role=player.get("role", ""),
            player_image_url=player.get("image_url"),
            player_team=player.get("team", ""),
            buyer_name=names.get(tx["buyer_id"]) if tx.get("buyer_id") else None,
            seller_name=names.get(tx["seller_id"]) if tx.get("seller_id") else None,
            price=float(tx["price"]),
            executed_at=tx["executed_at"],
        ))
    return result
