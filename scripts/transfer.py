#!/usr/bin/env python3
"""
CLI de gestión de jugadores para LOLFantasy.

Uso:
  python scripts/transfer.py transfer --player "Jackies" --team "Team Heretics"
  python scripts/transfer.py transfer --player "Jackies" --team "Team Heretics" --role support
  python scripts/transfer.py create --player "Yike" --team "Team Heretics" --role support --price 5.0
  python scripts/transfer.py release --player "Jackies"

Agregar --dry-run a cualquier comando para simular sin ejecutar.
"""

import argparse
import os
import sys
from pathlib import Path

# Cargar .env desde backend/.env (el script se ejecuta desde la raíz del proyecto)
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / "backend" / ".env")

from supabase import Client, create_client  # noqa: E402

# ── ANSI colors ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}{msg}{RESET}")


def err(msg: str) -> None:
    print(f"{RED}{msg}{RESET}", file=sys.stderr)


# ── Supabase client ──────────────────────────────────────────────────────────

def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        err("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en backend/.env")
        sys.exit(1)
    return create_client(url, key)


# ── Helpers ──────────────────────────────────────────────────────────────────

def find_player(sb: Client, name: str) -> dict:
    """Busca jugador por nombre (case-insensitive). Termina el proceso si no existe."""
    resp = sb.table("players").select("*").ilike("name", name).execute()
    if not resp.data:
        err(f"Jugador '{name}' no encontrado.")
        sys.exit(1)
    if len(resp.data) > 1:
        warn(f"Se encontraron {len(resp.data)} jugadores con ese nombre. Usando el primero: {resp.data[0]['name']}")
    return resp.data[0]


def find_team(sb: Client, name: str) -> dict:
    """Busca equipo por nombre (case-insensitive). Termina el proceso si no existe."""
    resp = sb.table("teams").select("*").ilike("name", name).execute()
    if not resp.data:
        err(f"Equipo '{name}' no encontrado.")
        sys.exit(1)
    if len(resp.data) > 1:
        warn(f"Se encontraron {len(resp.data)} equipos con ese nombre. Usando el primero: {resp.data[0]['name']}")
    return resp.data[0]


def confirm(prompt: str) -> bool:
    """Pide confirmación al usuario. Devuelve True si responde 's'."""
    answer = input(f"{YELLOW}{prompt} [s/N]: {RESET}").strip().lower()
    return answer == "s"


# ── Comando: transfer ────────────────────────────────────────────────────────

def cmd_transfer(args: argparse.Namespace, sb: Client) -> None:
    player = find_player(sb, args.player)
    new_role = args.role or player.get("role")

    print()
    print(f"  Jugador   : {player['name']} (id: {player['id']})")
    print(f"  Equipo    : {player.get('team')} → {args.team}")
    if args.role:
        print(f"  Nuevo rol : {player.get('role')} → {new_role}")
    print()

    if args.dry_run:
        warn("[DRY-RUN] No se realizaron cambios.")
        return

    if not confirm("¿Confirmar transferencia?"):
        warn("Operación cancelada.")
        return

    update_data: dict = {"team": args.team}
    if args.role:
        update_data["role"] = new_role

    sb.table("players").update(update_data).eq("id", player["id"]).execute()
    ok(f"✓ {player['name']} transferido a {args.team}.")


# ── Comando: create ──────────────────────────────────────────────────────────

def cmd_create(args: argparse.Namespace, sb: Client) -> None:
    # Verificar que NO existe ya
    exists = sb.table("players").select("id").ilike("name", args.player).execute()
    if exists.data:
        err(f"El jugador '{args.player}' ya existe (id: {exists.data[0]['id']}). Usá 'transfer' si querés moverlo.")
        sys.exit(1)

    team = find_team(sb, args.team)

    print()
    print(f"  Jugador   : {args.player}")
    print(f"  Equipo    : {team['name']} (id: {team['id']})")
    print(f"  Rol       : {args.role}")
    print(f"  Precio    : {args.price}M")
    print()

    if args.dry_run:
        warn("[DRY-RUN] No se realizaron cambios.")
        return

    if not confirm("¿Confirmar creación del jugador?"):
        warn("Operación cancelada.")
        return

    new_player = {
        "name":          args.player,
        "team":          team["name"],
        "role":          args.role,
        "league":        "LEC",
        "current_price": args.price,
        "image_url":     None,
        "is_active":     True,
    }

    resp = sb.table("players").insert(new_player).execute()
    created = resp.data[0] if resp.data else {}
    ok(f"✓ Jugador '{args.player}' creado con id: {created.get('id', '???')}.")


# ── Comando: release ─────────────────────────────────────────────────────────

def cmd_release(args: argparse.Namespace, sb: Client) -> None:
    player = find_player(sb, args.player)
    player_id = player["id"]

    # Obtener todos los roster_players con ese player_id,
    # haciendo JOIN a rosters → league_members para obtener price_paid y member_id.
    # La cadena de JOINs en Supabase Python se expresa con select anidado.
    roster_resp = (
        sb.table("roster_players")
        .select("id, price_paid, roster_id, rosters(member_id, league_members(id, remaining_budget, user_id, fantasy_leagues(name)))")
        .eq("player_id", player_id)
        .execute()
    )
    affected = roster_resp.data or []

    print()
    print(f"  Jugador   : {player['name']} (id: {player_id})")
    print(f"  Precio    : {player.get('current_price', '?')}M")
    print()

    if affected:
        print("  Managers afectados:")
        for entry in affected:
            price_paid  = entry.get("price_paid", 0)
            roster_data = entry.get("rosters") or {}
            member_data = roster_data.get("league_members") or {}
            league_data = member_data.get("fantasy_leagues") or {}
            league_name = league_data.get("name", "Liga desconocida")
            user_id     = member_data.get("user_id", "?")
            print(f"    - {user_id} ({league_name}): reembolso {price_paid}M")
    else:
        print("  Sin managers afectados (jugador no está en ningún roster).")

    print()

    if args.dry_run:
        warn("[DRY-RUN] No se realizaron cambios.")
        return

    if not confirm(f"¿Confirmar RELEASE definitivo de '{player['name']}'? Esta acción no se puede deshacer"):
        warn("Operación cancelada.")
        return

    # a) Devolver presupuesto a cada manager afectado
    for entry in affected:
        price_paid  = entry.get("price_paid", 0) or 0
        roster_data = entry.get("rosters") or {}
        member_data = roster_data.get("league_members") or {}
        member_id   = member_data.get("id")
        current_budget = member_data.get("remaining_budget", 0) or 0

        if member_id and price_paid:
            new_budget = current_budget + price_paid
            sb.table("league_members").update({"remaining_budget": new_budget}).eq("id", member_id).execute()

    # b) Limpiar NO ACTION FKs en orden antes de borrar el jugador
    sb.table("market_candidates").delete().eq("player_id", player_id).execute()
    sb.table("sell_offers").delete().eq("player_id", player_id).execute()
    sb.table("trade_offers").delete().eq("offered_player_id", player_id).execute()
    sb.table("trade_offers").delete().eq("requested_player_id", player_id).execute()

    # transactions: intentar SET player_id = NULL; si falla (NOT NULL constraint), borrar
    try:
        sb.table("transactions").update({"player_id": None}).eq("player_id", player_id).execute()
    except Exception:
        sb.table("transactions").delete().eq("player_id", player_id).execute()

    # c) Borrar jugador — el CASCADE se encarga de roster_players, market_listings,
    #    player_game_stats, player_series_stats, etc.
    sb.table("players").delete().eq("id", player_id).execute()

    ok(f"✓ Jugador '{player['name']}' eliminado. {len(affected)} manager(s) reembolsado(s).")


# ── Entry point ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI de gestión de jugadores para LOLFantasy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # transfer
    p_transfer = sub.add_parser("transfer", help="Transferir un jugador a otro equipo")
    p_transfer.add_argument("--player", required=True, help="Nombre del jugador")
    p_transfer.add_argument("--team",   required=True, help="Nombre del nuevo equipo")
    p_transfer.add_argument("--role",   choices=["top", "jungle", "mid", "adc", "support", "coach"],
                            help="Nuevo rol (opcional)")
    p_transfer.add_argument("--dry-run", action="store_true", dest="dry_run",
                            help="Simular sin ejecutar cambios")

    # create
    p_create = sub.add_parser("create", help="Crear un jugador nuevo")
    p_create.add_argument("--player", required=True, help="Nombre del jugador")
    p_create.add_argument("--team",   required=True, help="Nombre del equipo")
    p_create.add_argument("--role",   required=True,
                          choices=["top", "jungle", "mid", "adc", "support", "coach"],
                          help="Rol del jugador")
    p_create.add_argument("--price",  required=True, type=float, help="Precio inicial (en millones)")
    p_create.add_argument("--dry-run", action="store_true", dest="dry_run",
                          help="Simular sin ejecutar cambios")

    # release
    p_release = sub.add_parser("release", help="Liberar un jugador (baja con reembolso)")
    p_release.add_argument("--player", required=True, help="Nombre del jugador")
    p_release.add_argument("--dry-run", action="store_true", dest="dry_run",
                           help="Simular sin ejecutar cambios")

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    sb     = get_client()

    if args.command == "transfer":
        cmd_transfer(args, sb)
    elif args.command == "create":
        cmd_create(args, sb)
    elif args.command == "release":
        cmd_release(args, sb)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
