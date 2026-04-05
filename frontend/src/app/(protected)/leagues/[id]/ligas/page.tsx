"use client";

import { useEffect, useState } from "react";
import { api, type League } from "@/lib/api";
import { LeagueRow } from "@/components/LeagueRow";
import { LeagueActions } from "@/components/LeagueActions";

export default function LigasPage() {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.leagues
      .list()
      .then(setLeagues)
      .catch(() => setLeagues([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div
      className="min-h-[100dvh]"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-8">
        {/* Page header */}
        <div className="flex items-center justify-between gap-4 flex-wrap mb-6">
          <h1
            className="text-base font-black uppercase tracking-wider"
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              color: "var(--text-primary)",
            }}
          >
            Mis ligas
          </h1>
          <LeagueActions />
        </div>

        {/* Content */}
        {loading ? (
          <LigasSkeleton />
        ) : leagues.length === 0 ? (
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

function LigasSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="h-24 rounded-xl animate-pulse"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        />
      ))}
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
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"
          />
        </svg>
      </div>

      <p className="font-bold text-base mb-1" style={{ color: "var(--text-primary)" }}>
        No estás en ninguna liga todavía
      </p>
      <p className="text-sm mb-8" style={{ color: "var(--text-secondary)" }}>
        Crea la tuya o únete con un código de invitación.
      </p>

      <div className="flex flex-col sm:flex-row gap-3 justify-center max-w-sm mx-auto">
        <div
          className="flex-1 rounded-xl p-5 text-left cursor-default"
          style={{
            background: "var(--color-primary-bg)",
            border: "1px solid rgba(252,212,0,0.2)",
          }}
        >
          <p className="font-black mb-1" style={{ color: "var(--color-primary)" }}>
            Crear liga
          </p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Sé el comisionado, invita a tus amigos.
          </p>
        </div>
        <div
          className="flex-1 rounded-xl p-5 text-left cursor-default"
          style={{
            background: "var(--bg-panel)",
            border: "1px solid var(--border-medium)",
          }}
        >
          <p className="font-black mb-1" style={{ color: "var(--text-secondary)" }}>
            Unirse
          </p>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Introduce el código de invitación.
          </p>
        </div>
      </div>
    </div>
  );
}
