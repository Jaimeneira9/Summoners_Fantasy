import { createClient } from "@/lib/supabase/server";
import { serverApi } from "@/lib/api-server";
import { logout } from "@/app/actions/auth";
import { LeagueActions } from "@/components/LeagueActions";
import { LeagueRow } from "@/components/LeagueRow";
import type { League } from "@/lib/api";
import { LogoutButton } from "@/components/LogoutButton";

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  let leagues: League[] = [];
  try {
    leagues = await serverApi.leagues.list();
  } catch {
    // backend not available — show empty state
  }

  const displayName = user?.user_metadata?.full_name ?? user?.email?.split("@")[0] ?? "Manager";

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>

      {/* ------------------------------------------------------------------ */}
      {/* Topbar                                                               */}
      {/* ------------------------------------------------------------------ */}
      <header
        className="px-6 py-3.5 flex items-center justify-between sticky top-0 z-10"
        style={{
          background: "rgba(10,10,10,0.92)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: "var(--color-primary)" }}
          >
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
            </svg>
          </div>
          <span
            className="font-black tracking-tight text-base"
            style={{ color: "var(--color-primary)", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            LOL Fantasy
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm hidden sm:block" style={{ color: "var(--text-secondary)" }}>{user?.email}</span>
          <LogoutButton action={logout} />
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Hero header band                                                     */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="relative overflow-hidden"
        style={{
          background: "var(--bg-surface)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        <div className="max-w-3xl mx-auto px-6 py-8 relative">
          <p
            className="text-xs font-bold uppercase tracking-[0.18em] mb-2"
            style={{ color: "var(--text-muted)" }}
          >
            LEC Fantasy Season 2026
          </p>
          <h1
            className="text-4xl sm:text-5xl font-black leading-none mb-1"
            style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text-primary)" }}
          >
            {displayName}
          </h1>
          <p className="text-sm mt-2" style={{ color: "var(--text-secondary)" }}>
            {leagues.length === 0
              ? "Crea o únete a una liga para empezar."
              : `${leagues.length} liga${leagues.length !== 1 ? "s" : ""} activa${leagues.length !== 1 ? "s" : ""} · temporada en curso`}
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Main content                                                         */}
      {/* ------------------------------------------------------------------ */}
      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">

        {/* Section header + CTA actions */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2
            className="text-base font-black uppercase tracking-wider"
            style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text-primary)" }}
          >
            Mis ligas
          </h2>
          <LeagueActions />
        </div>

        {/* League list or empty state */}
        {leagues.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-3">
            {leagues.map((league) => (
              <LeagueRow key={league.id} league={league} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="rounded-2xl p-12 text-center"
      style={{
        background: "var(--bg-surface)",
        border: "1px dashed var(--border-medium)",
      }}
    >
      {/* Icon */}
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5"
        style={{
          background: "var(--color-primary-bg)",
          border: "1px solid rgba(252,212,0,0.2)",
        }}
      >
        <svg
          className="w-7 h-7 opacity-70"
          style={{ color: "var(--color-primary)" }}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
      </div>

      <p className="font-bold text-base mb-1" style={{ color: "var(--text-primary)" }}>
        No estás en ninguna liga todavía
      </p>
      <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
        Crea la tuya o únete con un código de invitación.
      </p>

      {/* CTA cards */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center max-w-sm mx-auto">
        <div
          className="flex-1 rounded-xl p-5 text-left cursor-default"
          style={{
            background: "var(--color-primary-bg)",
            border: "1px solid rgba(252,212,0,0.2)",
          }}
        >
          <p className="font-black mb-1" style={{ color: "var(--color-primary)" }}>Crear liga</p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Sé el comisionado, invita a tus amigos.</p>
        </div>
        <div
          className="flex-1 rounded-xl p-5 text-left cursor-default"
          style={{
            background: "var(--bg-panel)",
            border: "1px solid var(--border-medium)",
          }}
        >
          <p className="font-black mb-1" style={{ color: "var(--text-secondary)" }}>Unirse</p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Introduce el código de invitación.</p>
        </div>
      </div>
    </div>
  );
}
