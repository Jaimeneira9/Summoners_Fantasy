"use client";

import { usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";

interface BottomNavProps {
  leagueId: string;
}

export default function BottomNav({ leagueId }: BottomNavProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tab = searchParams.get("tab");

  const isScout = pathname.includes("/market") && tab === "scout";
  const isMarket = pathname.includes("/market") && tab !== "scout";

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
    {
      label: "Mercado",
      icon: "storefront",
      href: `/leagues/${leagueId}/market`,
      isActive: isMarket,
    },
    {
      label: "Explorar",
      icon: "manage_search",
      href: `/leagues/${leagueId}/market?tab=scout`,
      isActive: isScout,
    },
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

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around px-1 pb-8 pt-3 bg-background/90 backdrop-blur-xl shadow-[0_-10px_30px_rgba(0,0,0,0.05)]">
      {NAV_ITEMS.map(({ label, icon, href, isActive }) => (
        <Link
          key={label}
          href={href}
          className={`flex flex-col items-center gap-0.5 transition-all ${
            isActive
              ? "nav-item-active rounded-2xl py-2 px-3 scale-110"
              : "opacity-50 hover:opacity-100 active:scale-90 transition-all"
          }`}
        >
          <span className="material-symbols-outlined text-[18px]">{icon}</span>
          <span className="text-[9px] font-semibold">{label}</span>
        </Link>
      ))}
    </nav>
  );
}
