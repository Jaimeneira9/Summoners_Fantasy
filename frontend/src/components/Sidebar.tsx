"use client";

import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

interface SidebarProps {
  leagueId: string;
  leagueName?: string;
}

const itemClass = (active: boolean) =>
  `flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-all duration-150 text-sm font-semibold select-none ${
    active
      ? "nav-item-active shadow-lg"
      : "text-foreground hover:bg-white/5 hover:translate-x-1"
  }`;

export default function Sidebar({ leagueId, leagueName }: SidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const isMarketActive = pathname.includes("/market");
  const [marketOpen, setMarketOpen] = useState(isMarketActive);

  return (
    <aside className="hidden lg:flex flex-col h-full w-64 bg-background flex-shrink-0 border-r border-[#1e1e1e]">
      {/* Header del sidebar */}
      <div className="px-4 py-5 border-b border-[#1e1e1e]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 nav-item-active">
            <span className="material-symbols-outlined text-xl">military_tech</span>
          </div>
          <div className="min-w-0">
            <p className="font-display font-black text-sm text-foreground truncate uppercase tracking-tight">
              {leagueName || "Mi Liga"}
            </p>
            <p className="text-[10px] text-white/30 tracking-widest uppercase">LEC Fantasy</p>
          </div>
        </div>
      </div>

      {/* Navegación */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {/* Mis ligas */}
        <Link href="/dashboard" className={itemClass(pathname === "/dashboard")}>
          <span className="material-symbols-outlined text-xl">home</span>
          <span>Mis ligas</span>
        </Link>

        {/* Roster */}
        <Link
          href={`/leagues/${leagueId}/lineup`}
          className={itemClass(pathname.includes("/lineup"))}
        >
          <span className="material-symbols-outlined text-xl">groups</span>
          <span>Roster</span>
        </Link>

        {/* Mercado (acordeón) */}
        <button
          onClick={() => setMarketOpen(!marketOpen)}
          className={itemClass(isMarketActive) + " w-full"}
        >
          <span className="material-symbols-outlined text-xl">storefront</span>
          <span className="flex-1 text-left">Mercado</span>
          <span
            className={`material-symbols-outlined text-base transition-transform duration-200 ${
              marketOpen ? "rotate-180" : ""
            }`}
          >
            expand_more
          </span>
        </button>

        {marketOpen && (
          <div className="ml-4 mt-1 space-y-0.5">
            {[
              { label: "En vivo", tab: "live" },
              { label: "Pujas", tab: "bids" },
              { label: "Ofertas", tab: "offers" },
            ].map(({ label, tab }) => {
              const isActive =
                pathname.includes("/market") && searchParams.get("tab") === tab;
              return (
                <Link
                  key={tab}
                  href={`/leagues/${leagueId}/market?tab=${tab}`}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-150 select-none ${
                    isActive
                      ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)]"
                      : "text-white/70 hover:bg-white/5 hover:translate-x-1"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60" />
                  {label}
                </Link>
              );
            })}
          </div>
        )}

        {/* Clasificación */}
        <Link
          href={`/leagues/${leagueId}/standings`}
          className={itemClass(pathname.includes("/standings"))}
        >
          <span className="material-symbols-outlined text-xl">leaderboard</span>
          <span>Clasificación</span>
        </Link>

        {/* Actividad */}
        <Link
          href={`/leagues/${leagueId}/activity`}
          className={itemClass(pathname.includes("/activity"))}
        >
          <span className="material-symbols-outlined text-xl">history</span>
          <span>Actividad</span>
        </Link>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-[#1e1e1e]">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 px-3 py-2 text-xs text-white/30 hover:text-[var(--color-primary)] transition-colors"
        >
          <span className="material-symbols-outlined text-base">arrow_back</span>
          Volver a mis ligas
        </Link>
      </div>
    </aside>
  );
}
