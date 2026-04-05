"use client";

import { RoleIcon, ROLE_COLORS, ROLE_LABEL } from "@/components/RoleIcon";
import { getRoleColor } from "@/lib/roles";

export function PlayerHero({
  player,
  totalPoints,
  lastMatchPts,
  photoUrl,
  imgError,
  onImgError,
}: {
  player: {
    id: string;
    name: string;
    team: string;
    role: string;
    image_url: string | null;
    current_price: number;
  };
  totalPoints: number;
  lastMatchPts: number;
  photoUrl: string;
  imgError: boolean;
  onImgError: () => void;
}) {
  const roleHex = getRoleColor(player.role);
  const roleColor = ROLE_COLORS[player.role] ?? ROLE_COLORS.coach;

  return (
    <div className="player-hero" style={{
      background: "#111111",
      borderRadius: 12,
      padding: "16px",
      border: "1px solid #222",
      display: "flex",
      alignItems: "center",
      gap: 16,
      marginBottom: 12,
    }}>
      {/* Photo + role badge */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <div style={{
          width: 80,
          height: 80,
          borderRadius: 10,
          border: `2px solid ${roleHex}`,
          overflow: "hidden",
          background: `${roleHex}22`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}>
          {!imgError ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photoUrl}
              alt={player.name}
              style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
              onError={onImgError}
            />
          ) : (
            <RoleIcon role={player.role} className={`w-10 h-10 ${roleColor.text} opacity-60`} />
          )}
        </div>
        {/* Role badge */}
        <div style={{
          background: roleHex,
          color: "#000",
          fontSize: 9,
          fontWeight: 900,
          padding: "2px 8px",
          borderRadius: 4,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}>
          {ROLE_LABEL[player.role] ?? player.role.toUpperCase()}
        </div>
      </div>

      {/* Player info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 28,
          fontWeight: 700,
          color: "#fff",
          lineHeight: 1.1,
          margin: 0,
          textTransform: "uppercase",
        }}>
          {player.name}
        </h1>
        <p style={{ fontSize: 13, color: "#555", margin: "2px 0 0", fontFamily: "'Space Grotesk', sans-serif" }}>
          {player.team}
        </p>
        <p style={{ fontSize: 12, color: "#444", margin: "2px 0 0" }}>
          LEC · {player.current_price.toFixed(1)}M
        </p>
      </div>

      {/* Total points */}
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: 40,
          fontWeight: 700,
          color: "#FCD400",
          lineHeight: 1,
        }}>
          {Math.round(totalPoints)}
        </div>
        <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
          pts total
        </div>
        {lastMatchPts > 0 && (
          <div style={{ fontSize: 12, color: "#4CAF50", marginTop: 4, fontWeight: 600 }}>
            +{Math.round(lastMatchPts)} esta semana
          </div>
        )}
      </div>
    </div>
  );
}
