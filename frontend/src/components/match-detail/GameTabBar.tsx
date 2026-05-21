"use client";

/**
 * Barra de pestañas para navegar entre la vista general de la serie y cada game individual.
 *
 * Pestaña "General" → selected === "series"
 * Pestaña "G{n}" → selected === game_number (número entero)
 *
 * El tab activo se resalta con un borde inferior amarillo (#fcd400).
 * El scroll horizontal permite manejar series largas (BO5) en mobile.
 */
import type { GameDetailData } from "@/types/match-detail";

interface GameTabBarProps {
  games: GameDetailData[];
  selected: "series" | number;
  onChange: (tab: "series" | number) => void;
}

export function GameTabBar({ games, selected, onChange }: GameTabBarProps) {
  return (
    <div className="flex overflow-x-auto scrollbar-hide bg-[#111111] border-b border-[#1e1e1e]">
      {/* Serie tab */}
      <button
        onClick={() => onChange("series")}
        className={`shrink-0 px-5 py-3 text-sm font-semibold transition-colors border-b-2 ${
          selected === "series"
            ? "border-[#fcd400] text-[#fcd400]"
            : "border-transparent text-neutral-500 hover:text-neutral-300"
        }`}
      >
        General
      </button>

      {/* Game tabs */}
      {games.map((game) => (
        <button
          key={game.game_id}
          onClick={() => onChange(game.game_number)}
          className={`shrink-0 px-5 py-3 text-sm font-semibold transition-colors border-b-2 ${
            selected === game.game_number
              ? "border-[#fcd400] text-[#fcd400]"
              : "border-transparent text-neutral-500 hover:text-neutral-300"
          }`}
        >
          G{game.game_number}
        </button>
      ))}
    </div>
  );
}
