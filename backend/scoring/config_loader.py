"""
Carga de pesos de scoring desde la DB (scoring_config).

Fallback automático a las constantes hardcodeadas de engine.py si la tabla
no existe, no tiene fila para ese (competition_id, role), o falla la query.

El cache en memoria es request-scoped (no se limpia entre requests del mismo
proceso) — suficiente para el pipeline de ingestión batch. Llamar
clear_weights_cache() en tests o si se actualizan los pesos en caliente.
"""
from __future__ import annotations

import logging

from supabase import Client

from scoring.engine import MULTIKILL_BONUS, ROLE_WEIGHTS

logger = logging.getLogger(__name__)

_WEIGHTS_CACHE: dict = {}


def get_scoring_weights(supabase: Client, competition_id: str, role: str) -> dict:
    """
    Devuelve los pesos de scoring para (competition_id, role).

    Orden de precedencia:
      1. Cache en memoria
      2. scoring_config en DB
      3. ROLE_WEIGHTS[role] hardcodeado en engine.py
    """
    key = (competition_id, role)
    if key in _WEIGHTS_CACHE:
        return _WEIGHTS_CACHE[key]

    try:
        resp = (
            supabase.table("scoring_config")
            .select("weights")
            .eq("competition_id", competition_id)
            .eq("role", role)
            .limit(1)
            .execute()
        )
        if resp.data:
            weights = resp.data[0]["weights"]
            _WEIGHTS_CACHE[key] = weights
            return weights
    except Exception as e:
        logger.warning(
            "scoring_config lookup failed for %s/%s: %s", competition_id, role, e
        )

    fallback = ROLE_WEIGHTS.get(role, {})
    _WEIGHTS_CACHE[key] = fallback
    return fallback


def get_multikill_bonuses(supabase: Client, competition_id: str) -> dict:
    """
    Devuelve los bonuses de multikill para competition_id.

    Toma la primera fila de scoring_config donde multikill_bonuses IS NOT NULL.
    Si no existe ninguna, devuelve MULTIKILL_BONUS hardcodeado en engine.py.
    """
    key = f"multikill:{competition_id}"
    if key in _WEIGHTS_CACHE:
        return _WEIGHTS_CACHE[key]

    try:
        resp = (
            supabase.table("scoring_config")
            .select("multikill_bonuses")
            .eq("competition_id", competition_id)
            .not_.is_("multikill_bonuses", "null")
            .limit(1)
            .execute()
        )
        if resp.data:
            bonuses = resp.data[0]["multikill_bonuses"]
            _WEIGHTS_CACHE[key] = bonuses
            return bonuses
    except Exception as e:
        logger.warning(
            "multikill_bonuses lookup failed for %s: %s", competition_id, e
        )

    _WEIGHTS_CACHE[key] = MULTIKILL_BONUS
    return MULTIKILL_BONUS


def clear_weights_cache() -> None:
    """Limpia el cache en memoria. Útil en tests y si se actualizan pesos en caliente."""
    _WEIGHTS_CACHE.clear()
