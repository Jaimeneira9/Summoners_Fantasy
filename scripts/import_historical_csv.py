"""
Importa estadísticas históricas agregadas de un split desde un CSV de LEC Versus.

Formato CSV esperado (cabecera):
  Player,Team,Pos,GP,W%,CTR%,K,D,A,KDA,KP,...,CSPM,...,DPM,DMG%,...,WPM,...

Uso:
  python3 scripts/import_historical_csv.py --file data/versus_winter_2026.csv \
      --split "LEC Versus Winter 2026" [--competition "LEC"] [--dry-run]

Equipos ignorados (no LEC principal):
  Los Ratones, Karmine Corp Blue
"""
import argparse
import csv
import os
import sys

from dotenv import load_dotenv

# Load .env from backend directory
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client

# Equipos que se excluyen del import
SKIP_TEAMS = {"Los Ratones", "Karmine Corp Blue"}

# Mapa de posición CSV → rol en DB
POS_TO_ROLE = {
    "Top":     "top",
    "Jungle":  "jungle",
    "Middle":  "mid",
    "ADC":     "adc",
    "Support": "support",
}


def _pct(value: str) -> float:
    """Convierte "55%" → 0.55"""
    return float(value.strip().rstrip("%")) / 100.0


def _safe_float(value: str) -> float | None:
    try:
        result = float(value)
        if result != result or result == float("inf") or result == float("-inf"):  # NaN or Infinity
            return None
        return result
    except (ValueError, TypeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Import LEC historical CSV")
    parser.add_argument("--file",        required=True,  help="Ruta al CSV")
    parser.add_argument("--split",       required=True,  help='Nombre del split, e.g. "LEC Versus Winter 2026"')
    parser.add_argument("--competition", default="LEC",  help="Competición (default: LEC)")
    parser.add_argument("--dry-run",     action="store_true", help="Simula sin escribir en DB")
    args = parser.parse_args()

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    # ── 1. Obtener o crear el split ───────────────────────────────────────
    split_resp = sb.table("splits").select("id").eq("name", args.split).execute()
    if split_resp.data:
        split_id = split_resp.data[0]["id"]
        print(f"Split existente: {args.split} ({split_id})")
    else:
        if args.dry_run:
            print(f"[DRY RUN] Crearía split: {args.split}")
            split_id = "dry-run-id"
        else:
            new_split = sb.table("splits").insert({
                "name": args.split,
                "competition": args.competition,
            }).execute()
            split_id = new_split.data[0]["id"]
            print(f"Split creado: {args.split} ({split_id})")

    # ── 2. Cargar todos los jugadores de la DB (nombre → id) ─────────────
    players_resp = sb.table("players").select("id, name").execute()
    # Normalizar: lower sin espacios para matching flexible
    db_players: dict[str, str] = {}   # normalized_name → id
    db_names:   dict[str, str] = {}   # normalized_name → original name
    for p in (players_resp.data or []):
        key = p["name"].lower().replace(" ", "")
        db_players[key] = p["id"]
        db_names[key] = p["name"]

    # ── 3. Parsear CSV ────────────────────────────────────────────────────
    inserted = 0
    skipped_team = 0
    not_found: list[str] = []

    with open(args.file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            team = row["Team"].strip()
            if team in SKIP_TEAMS:
                skipped_team += 1
                continue

            player_name = row["Player"].strip()
            key = player_name.lower().replace(" ", "")
            player_id = db_players.get(key)

            if not player_id:
                not_found.append(f"{player_name} ({team})")
                continue

            gp = int(row["GP"])
            wins = round(gp * _pct(row["W%"])) if row.get("W%") else 0

            record = {
                "player_id":          player_id,
                "split_id":           split_id,
                "games_played":       gp,
                "wins":               wins,
                "kills":              int(row["K"]),
                "deaths":             int(row["D"]),
                "assists":            int(row["A"]),
                "kda":                _safe_float(row.get("KDA", "")),
                "cspm":               _safe_float(row.get("CSPM", "")),
                "dpm":                _safe_float(row.get("DPM", "")),
                "damage_pct":         _pct(row["DMG%"]) if row.get("DMG%") else None,
                "kill_participation": _pct(row["KP"])   if row.get("KP")   else None,
                "wards_per_min":      _safe_float(row.get("WPM", "")),
            }

            if args.dry_run:
                print(f"[DRY RUN] {player_name} ({team}): {gp}GP, {record['kills']}/{record['deaths']}/{record['assists']}")
            else:
                # Upsert: si ya existe el par (player_id, split_id) actualiza
                existing = (
                    sb.table("player_historical_stats")
                    .select("id")
                    .eq("player_id", player_id)
                    .eq("split_id", split_id)
                    .execute()
                )
                if existing.data:
                    sb.table("player_historical_stats").update(record).eq("id", existing.data[0]["id"]).execute()
                else:
                    sb.table("player_historical_stats").insert(record).execute()
                print(f"  ✓ {player_name} ({team})")
            inserted += 1

    # ── 4. Resumen ────────────────────────────────────────────────────────
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Resumen:")
    print(f"  Importados : {inserted}")
    print(f"  Omitidos (equipo no LEC): {skipped_team}")
    if not_found:
        print(f"  No encontrados en DB ({len(not_found)}):")
        for name in not_found:
            print(f"    - {name}")


if __name__ == "__main__":
    main()
