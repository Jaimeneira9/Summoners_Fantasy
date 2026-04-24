"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface BottomNavProps {
  leagueId: string;
  hasIncompleteRoster?: boolean;
  gameMode?: string | null;
}

const MAS_ITEMS = (leagueId: string) => [
  { icon: "leaderboard", label: "Clasificación", href: `/leagues/${leagueId}/standings` },
  { icon: "bolt", label: "Actividad", href: `/leagues/${leagueId}/activity` },
];

export default function BottomNav({ leagueId, hasIncompleteRoster, gameMode }: BottomNavProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [masOpen, setMasOpen] = useState(false);
  const [hoveredMas, setHoveredMas] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const isMasActive =
    masOpen ||
    pathname.includes("/standings") ||
    pathname.includes("/activity");

  const NAV_ITEMS = [
    {
      label: "Ligas",
      icon: "home",
      href: `/leagues/${leagueId}/ligas`,
      isActive: pathname.includes("/ligas"),
    },
    {
      label: "Roster",
      icon: "groups",
      href: `/leagues/${leagueId}/lineup`,
      isActive: pathname.includes("/lineup"),
    },
    ...(gameMode !== "budget_pick"
      ? [
          {
            label: "Mercado",
            icon: "storefront",
            href: `/leagues/${leagueId}/market`,
            isActive: pathname.includes("/market"),
          },
        ]
      : [
          {
            label: "Explorar",
            icon: "search",
            href: `/leagues/${leagueId}/market?tab=scout`,
            isActive: pathname.includes("/market"),
          },
        ]),
    {
      label: "Equipos",
      icon: "shield",
      href: `/leagues/${leagueId}/teams`,
      isActive: pathname.includes("/teams"),
    },
    {
      label: "Calendario",
      icon: "calendar_month",
      href: `/leagues/${leagueId}/calendar`,
      isActive: pathname.includes("/calendar"),
    },
  ];

  // Close panel when navigating away
  useEffect(() => {
    setMasOpen(false);
  }, [pathname]);

  const portal = mounted && masOpen ? createPortal(
    <>
      <style>{`
        @keyframes mas-popup {
          from { opacity: 0; transform: scale(0.92) translateY(6px); }
          to   { opacity: 1; transform: scale(1)    translateY(0); }
        }
      `}</style>
      <div className="fixed inset-0 z-[9998]" onClick={() => setMasOpen(false)} />
      <div
        ref={panelRef}
        className="fixed z-[9999]"
        style={{
          bottom: "calc(72px + env(safe-area-inset-bottom, 0px))",
          right: 12,
          background: "#1E1E1E",
          border: "1px solid #2A2A2A",
          borderRadius: 16,
          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
          minWidth: 190,
          padding: 6,
          animation: "mas-popup 180ms ease-out both",
          transformOrigin: "bottom right",
        }}
      >
        {MAS_ITEMS(leagueId).map(({ icon, label, href }) => {
          const isActive = pathname.includes(href.split(`/leagues/${leagueId}`)[1]);
          return (
            <button
              key={label}
              className="active:scale-95"
              onClick={() => { setMasOpen(false); router.push(href); }}
              onMouseEnter={() => setHoveredMas(label)}
              onMouseLeave={() => setHoveredMas(null)}
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                gap: 12,
                width: "100%",
                padding: "12px 14px",
                borderRadius: 10,
                color: isActive ? "#FCD400" : hoveredMas === label ? "#FFFFFF" : "#AAAAAA",
                background: isActive ? "rgba(252,212,0,0.08)" : hoveredMas === label ? "rgba(255,255,255,0.06)" : "transparent",
                border: "none",
                cursor: "pointer",
                transition: "all 150ms",
              }}
            >
              <span className="material-symbols-outlined text-[20px]">{icon}</span>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{label}</span>
            </button>
          );
        })}
      </div>
    </>,
    document.body
  ) : null;

  return (
    <>
      {portal}
      <nav className="lg:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around px-1 pb-8 pt-3 bg-background/90 backdrop-blur-xl shadow-[0_-10px_30px_rgba(0,0,0,0.05)]">
        {NAV_ITEMS.map(({ label, icon, href, isActive }) => {
          const showDot = label === "Roster" && hasIncompleteRoster;
          return (
            <Link
              key={label}
              href={href}
              className={`flex flex-col items-center gap-0.5 transition-all ${
                isActive
                  ? "nav-item-active rounded-2xl py-2 px-3 scale-110"
                  : "opacity-50 hover:opacity-100 active:scale-90 transition-all"
              }`}
            >
              <span className="relative inline-flex">
                <span className="material-symbols-outlined text-[18px]">{icon}</span>
                {showDot && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500" />
                )}
              </span>
              <span className="text-[9px] font-semibold">{label}</span>
            </Link>
          );
        })}

        {/* Más button */}
        <button
          onClick={() => setMasOpen((prev) => !prev)}
          className={`flex flex-col items-center gap-0.5 transition-all ${
            isMasActive
              ? "nav-item-active rounded-2xl py-2 px-3 scale-110"
              : "opacity-50 hover:opacity-100 active:scale-90 transition-all"
          }`}
        >
          <span className="material-symbols-outlined text-[18px]">more_horiz</span>
          <span className="text-[9px] font-semibold">Más</span>
        </button>
      </nav>
    </>
  );
}
