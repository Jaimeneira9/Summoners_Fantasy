"use client";

import Link from "next/link";
import type { UpcomingMatch } from "@/lib/api";

export function UpcomingSchedule({
  matches,
  loading,
  role,
  leagueId,
}: {
  matches: UpcomingMatch[] | null;
  loading: boolean;
  role: string;
  leagueId: string;
}) {
  if (role === "coach") return null;

  const cardStyle = {
    background: "#111111",
    border: "1px solid #1E1E1E",
    borderRadius: 12,
    padding: "16px 20px",
    marginBottom: 12,
  };

  if (loading) {
    return (
      <div style={cardStyle}>
        <p style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          marginBottom: 12,
        }}>
          Próximas partidas
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[0, 1].map((i) => (
            <div
              key={i}
              className="animate-pulse"
              style={{ height: 40, borderRadius: 8, background: "#1A1A1A" }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (matches !== null && matches.length === 0) {
    return (
      <div style={cardStyle}>
        <p style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 13,
          fontWeight: 600,
          color: "#fff",
          marginBottom: 8,
        }}>
          Próximas partidas
        </p>
        <p style={{ fontSize: 13, color: "#555" }}>Sin partidas programadas</p>
      </div>
    );
  }

  if (!matches) return null;

  return (
    <div style={cardStyle}>
      <p style={{
        fontFamily: "'Space Grotesk', sans-serif",
        fontSize: 13,
        fontWeight: 600,
        color: "#fff",
        marginBottom: 12,
      }}>
        Próximas partidas
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {matches.slice(0, 3).map((match, i) => {
          const dateObj = new Date(match.date);
          const formatted = dateObj.toLocaleDateString("es-ES", {
            weekday: "short",
            day: "numeric",
            month: "short",
          });
          const opponentSlug = match.opponent.toLowerCase().replace(/ /g, "-");
          const inner = (
            <>
              {/* Team logo */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosEquiposLec/${opponentSlug}.webp`}
                alt={match.opponent}
                style={{ width: 22, height: 22, objectFit: "contain", flexShrink: 0 }}
                onError={(e) => { e.currentTarget.style.display = "none"; }}
              />
              {/* Opponent name */}
              <span style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: 13,
                fontWeight: 600,
                color: "#F5F5F5",
                flex: 1,
              }}>
                {match.opponent}
              </span>
              {/* Home/away badge */}
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                color: match.home_or_away === "home" ? "#4CAF50" : "#888",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                flexShrink: 0,
              }}>
                {match.home_or_away === "home" ? "LOCAL" : "VISITANTE"}
              </span>
              {/* Date */}
              <span style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: 12,
                color: "#555",
                flexShrink: 0,
                minWidth: 72,
                textAlign: "right",
                textTransform: "capitalize",
              }}>
                {formatted}
              </span>
            </>
          );
          const sharedStyle: React.CSSProperties = {
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 10px",
            borderRadius: 8,
            background: "#0F0F0F",
            border: "1px solid #1A1A1A",
            textDecoration: "none",
          };
          return match.series_id ? (
            <Link
              key={i}
              href={`/leagues/${leagueId}/h2h/${match.series_id}`}
              style={{ ...sharedStyle, cursor: "pointer" }}
            >
              {inner}
            </Link>
          ) : (
            <div key={i} style={sharedStyle}>
              {inner}
            </div>
          );
        })}
      </div>
    </div>
  );
}
