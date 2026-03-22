"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

interface BottomNavProps {
  leagueId: string;
}

const NAV_ITEMS = [
  { label: "Ligas", icon: "home", href: "/dashboard", match: "/dashboard" },
  { label: "Roster", icon: "groups", href: "lineup", match: "/lineup" },
  { label: "Mercado", icon: "storefront", href: "market", match: "/market" },
  { label: "Actividad", icon: "history", href: "activity", match: "/activity" },
] as const;

export default function BottomNav({ leagueId }: BottomNavProps) {
  const pathname = usePathname();

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around px-4 pb-8 pt-3 bg-background/90 backdrop-blur-xl shadow-[0_-10px_30px_rgba(0,0,0,0.05)]">
      {NAV_ITEMS.map(({ label, icon, href, match }) => {
        const resolvedHref =
          href === "/dashboard" ? href : `/leagues/${leagueId}/${href}`;
        const isActive = pathname.includes(match);

        return (
          <Link
            key={label}
            href={resolvedHref}
            className={`flex flex-col items-center gap-0.5 transition-all ${
              isActive
                ? "nav-item-active rounded-2xl py-2 px-5 scale-110"
                : "opacity-50 hover:opacity-100 active:scale-90 transition-all"
            }`}
          >
            <span className="material-symbols-outlined text-xl">{icon}</span>
            <span className="text-[10px] font-semibold">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
