"""
Lógica de reset entre splits de LEC.

Al reset:
1. Snapshot de puntos del split en member_split_scores
2. Borrar roster_players no protegidos
3. Quitar is_protected de los que se conservan
4. Redistribuir presupuesto: último +8M, penúltimo +6M, ... primero +0M
5. Marcar competition como inactiva
"""
import logging
from datetime import date

from supabase import Client

logger = logging.getLogger(__name__)

BUDGET_BONUS_STEP = 2.0  # M por posición desde el final


def run_split_reset_if_due(supabase: Client, force: bool = False) -> None:
    """
    Comprueba si hoy es reset_date de alguna competition activa.
    Si force=True, ejecuta aunque no sea la fecha.
    """
    today = date.today().isoformat()

    resp = (
        supabase.table("competitions")
        .select("id, name, reset_date")
        .eq("is_active", True)
        .execute()
    )
    competitions = resp.data or []

    for competition in competitions:
        if force or (competition.get("reset_date") and competition["reset_date"] <= today):
            logger.info("Running split reset for competition: %s", competition["name"])
            _execute_reset(supabase, competition["id"])
            return  # Un reset por ejecución


def _execute_reset(supabase: Client, competition_id: str) -> None:
    # ── 1. Snapshot de puntos ──────────────────────────────────────────────
    _record_split_scores(supabase, competition_id)

    # ── 2. Por cada liga activa: limpiar rosters y redistribuir presupuesto
    leagues_resp = (
        supabase.table("fantasy_leagues")
        .select("id, budget")
        .eq("is_active", True)
        .execute()
    )
    for league in (leagues_resp.data or []):
        _reset_league(supabase, league["id"], float(league["budget"]), competition_id)

    # ── 3. Marcar competition como inactiva ────────────────────────────────
    supabase.table("competitions").update({"is_active": False}).eq("id", competition_id).execute()
    logger.info("Competition %s marked inactive", competition_id)


def _record_split_scores(supabase: Client, competition_id: str) -> None:
    """Guarda los puntos ganados en este split para cada miembro."""
    members_resp = supabase.table("league_members").select("id, total_points").execute()
    for member in (members_resp.data or []):
        prev_resp = (
            supabase.table("member_split_scores")
            .select("points")
            .eq("member_id", member["id"])
            .execute()
        )
        prev_total = sum(float(p["points"]) for p in (prev_resp.data or []))
        this_split = max(0.0, float(member["total_points"] or 0) - prev_total)

        supabase.table("member_split_scores").insert({
            "member_id": member["id"],
            "competition_id": competition_id,
            "points": this_split,
        }).execute()


def _reset_league(supabase: Client, league_id: str, base_budget: float, competition_id: str) -> None:
    # Miembros ordenados por puntos desc (rank 1 = mejor)
    members_resp = (
        supabase.table("league_members")
        .select("id, total_points")
        .eq("league_id", league_id)
        .order("total_points", desc=True)
        .execute()
    )
    members = members_resp.data or []
    n = len(members)

    for rank_0, member in enumerate(members):
        # rank_0: 0 = mejor, n-1 = peor
        # Bonus: mejor recibe 0, peor recibe (n-1)*2
        bonus = rank_0 * BUDGET_BONUS_STEP
        new_budget = base_budget + bonus

        # Borrar roster: primero obtener roster del miembro
        roster_resp = (
            supabase.table("rosters")
            .select("id")
            .eq("member_id", member["id"])
            .execute()
        )
        if roster_resp.data:
            roster_id = roster_resp.data[0]["id"]

            # Registrar qué jugadores estaban protegidos (para restricción next split)
            protected_resp = (
                supabase.table("roster_players")
                .select("player_id")
                .eq("roster_id", roster_id)
                .eq("is_protected", True)
                .execute()
            )
            for p in (protected_resp.data or []):
                try:
                    supabase.table("split_protect_history").insert({
                        "member_id": member["id"],
                        "player_id": p["player_id"],
                        "competition_id": competition_id,
                    }).execute()
                except Exception as exc:
                    logger.warning("Could not record protect history: %s", exc)

            # Borrar los no protegidos
            supabase.table("roster_players").delete().eq(
                "roster_id", roster_id
            ).eq("is_protected", False).execute()

            # Quitar flag de protección a los que se quedan
            supabase.table("roster_players").update(
                {"is_protected": False}
            ).eq("roster_id", roster_id).execute()

        # Actualizar presupuesto
        supabase.table("league_members").update(
            {"remaining_budget": new_budget}
        ).eq("id", member["id"]).execute()

    logger.info(
        "League %s reset: %d members, base_budget=%.1fM, max_bonus=%.1fM",
        league_id, n, base_budget, (n - 1) * BUDGET_BONUS_STEP,
    )
