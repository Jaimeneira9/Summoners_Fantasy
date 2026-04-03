"""
Helper cacheado para resolver team_id a partir de un nombre/alias.

El cache dura 600 segundos (10 min) y se comparte entre todos los requests
que corren en el mismo proceso — evita queries repetidas a la tabla teams.
"""
import time

from supabase import Client

_cache: dict = {"data": None, "timestamp": 0.0}
_TTL = 600.0  # segundos


def resolve_team_id(supabase: Client, team_name: str) -> str | None:
    """Devuelve el team id (como str) que coincida con team_name, o None.

    La búsqueda es case-insensitive y compara contra el campo `name` y cada
    elemento del array `aliases`.  El resultado viene de un cache en memoria
    con TTL de 10 minutos para evitar golpear la DB en cada request.
    """
    now = time.monotonic()
    if _cache["data"] is None or (now - _cache["timestamp"]) > _TTL:
        resp = supabase.table("teams").select("id, name, aliases").execute()
        _cache["data"] = resp.data or []
        _cache["timestamp"] = now

    needle = team_name.strip().lower()
    for t in _cache["data"]:
        aliases: list[str] = t.get("aliases") or []
        all_names = [t["name"]] + aliases
        for candidate in all_names:
            if candidate.strip().lower() == needle:
                return str(t["id"])
    return None
