"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api, type AvailablePlayer, type PickResult } from "@/lib/api";
import { ROLE_LABEL } from "@/components/RoleIcon";
import { getRoleColor } from "@/lib/roles";
import { getTeamBadgeUrl } from "@/components/PlayerCard";

export interface PickPanelProps {
  leagueId: string;
  slot: string;
  role: string;
  currentPlayer: { id: string; name: string; price_paid: number } | null;
  remainingBudget: number;
  onPick: (result: PickResult) => void;
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Skeleton row — shown while loading
// ---------------------------------------------------------------------------
function SkeletonRow() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "10px 16px",
        borderBottom: "1px solid #1a1a1a",
      }}
    >
      <div style={{ width: 56, height: 56, borderRadius: "10px", background: "#1e1e1e", flexShrink: 0 }} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "6px" }}>
        <div style={{ height: 14, width: "55%", borderRadius: 4, background: "#1e1e1e" }} />
        <div style={{ height: 11, width: "35%", borderRadius: 4, background: "#1a1a1a" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "6px" }}>
        <div style={{ height: 20, width: 32, borderRadius: 4, background: "#1e1e1e" }} />
        <div style={{ height: 12, width: 28, borderRadius: 4, background: "#1a1a1a" }} />
      </div>
      <div style={{ width: 58, height: 30, borderRadius: 6, background: "#1e1e1e", flexShrink: 0 }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Player row — Scout-style layout
// ---------------------------------------------------------------------------
function PlayerRow({
  player,
  currentPlayer,
  remainingBudget,
  picking,
  onPick,
}: {
  player: AvailablePlayer;
  currentPlayer: { id: string; name: string; price_paid: number } | null;
  remainingBudget: number;
  picking: string | null;
  onPick: (player: AvailablePlayer) => void;
}) {
  const roleHex = getRoleColor(player.role);
  const netCost = player.current_price - (currentPlayer?.price_paid ?? 0);
  const affordable = netCost <= remainingBudget;
  const budgetAfter = remainingBudget - netCost;
  const isPicking = picking === player.id;

  const imageUrl =
    player.image_url ||
    `https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/${player.name
      .toLowerCase()
      .replace(/ /g, "-")}.webp`;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "10px 16px",
        borderBottom: "1px solid #1a1a1a",
        background: isPicking ? "#141414" : "transparent",
        opacity: affordable ? 1 : 0.38,
        transition: "background 0.1s",
      }}
    >
      {/* Foto jugador — 56×56 estilo ScoutRow */}
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: "10px",
          overflow: "hidden",
          flexShrink: 0,
          background: roleHex + "22",
          border: `1px solid ${roleHex}44`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt={player.name}
          style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center top" }}
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      </div>

      {/* Info — nombre, equipo, badges */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Fila 1: nombre + rol badge + "en equipo" */}
        <div style={{ display: "flex", alignItems: "center", gap: "5px", marginBottom: "4px" }}>
          <span
            style={{
              fontFamily: "'Barlow Condensed', sans-serif",
              fontSize: "16px",
              fontWeight: 700,
              color: "#F0E8D0",
              lineHeight: 1.2,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {player.name}
          </span>
          <span
            style={{
              background: roleHex + "22",
              color: roleHex,
              border: `1px solid ${roleHex}44`,
              borderRadius: "4px",
              padding: "1px 5px",
              fontSize: "9px",
              fontWeight: 700,
              fontFamily: "'Space Grotesk', sans-serif",
              letterSpacing: "0.05em",
              flexShrink: 0,
            }}
          >
            {ROLE_LABEL[player.role] ?? player.role.toUpperCase()}
          </span>
          {player.in_my_roster && (
            <span
              style={{
                fontSize: "9px",
                color: "#3b82f6",
                background: "rgba(59,130,246,0.12)",
                border: "1px solid rgba(59,130,246,0.3)",
                padding: "1px 5px",
                borderRadius: "4px",
                fontWeight: 600,
                fontFamily: "'Space Grotesk', sans-serif",
                flexShrink: 0,
              }}
            >
              en equipo
            </span>
          )}
        </div>

        {/* Fila 2: escudo + nombre equipo + precio + saldo resultante */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          {/* Escudo del equipo */}
          <div style={{ width: 14, height: 14, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getTeamBadgeUrl(player.team)}
              alt={player.team}
              style={{ width: 14, height: 14, objectFit: "contain" }}
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
          </div>
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "12px",
              color: "#555555",
              flexShrink: 0,
            }}
          >
            {player.team}
          </span>
          <span style={{ color: "#2a2a2a", fontSize: "11px", flexShrink: 0 }}>·</span>
          <span
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "13px",
              fontWeight: 700,
              color: "#FCD400",
              flexShrink: 0,
            }}
          >
            {player.current_price.toFixed(1)}M
          </span>
          {affordable && currentPlayer && (
            <>
              <span style={{ color: "#2a2a2a", fontSize: "11px", flexShrink: 0 }}>→</span>
              <span
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "11px",
                  color: budgetAfter >= 0 ? "#22c55e" : "#ef4444",
                  flexShrink: 0,
                }}
              >
                {budgetAfter.toFixed(1)}M
              </span>
            </>
          )}
        </div>
      </div>

      {/* PTS stat */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "1px",
          flexShrink: 0,
          minWidth: 36,
        }}
      >
        <span
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: "9px",
            fontWeight: 700,
            color: "#555555",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          PTS
        </span>
        <span
          style={{
            fontFamily: "'Barlow Condensed', sans-serif",
            fontSize: "18px",
            fontWeight: 700,
            color: "#FCD400",
            lineHeight: 1,
          }}
        >
          {player.split_points > 0 ? Math.round(player.split_points) : "—"}
        </span>
      </div>

      {/* Botón fichar */}
      <button
        onClick={() => onPick(player)}
        disabled={!affordable || !!picking}
        title={!affordable ? "Presupuesto insuficiente" : undefined}
        style={{
          padding: "7px 14px",
          borderRadius: "8px",
          fontSize: "12px",
          fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 600,
          cursor: affordable && !picking ? "pointer" : "not-allowed",
          border: "none",
          background: affordable ? (isPicking ? "#1d4ed8" : "#2563eb") : "#1a1a1a",
          color: affordable ? "#FFFFFF" : "#444444",
          transition: "background 0.15s",
          flexShrink: 0,
          minWidth: 62,
          textAlign: "center",
        }}
      >
        {isPicking ? "..." : "Fichar"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PickPanel
// ---------------------------------------------------------------------------
export function PickPanel({
  leagueId,
  slot,
  role,
  currentPlayer,
  remainingBudget,
  onPick,
  onClose,
}: PickPanelProps) {
  const [players, setPlayers] = useState<AvailablePlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [picking, setPicking] = useState<string | null>(null);
  const [pickError, setPickError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    const roleFilter = role !== "bench" ? role : undefined;
    setLoading(true);
    setPickError(null);
    api.roster
      .availablePlayers(leagueId, roleFilter)
      .then((data) => setPlayers(data))
      .catch((e: Error) => setPickError(e.message))
      .finally(() => setLoading(false));
  }, [leagueId, role]);

  const handlePick = async (player: AvailablePlayer) => {
    const netCost = player.current_price - (currentPlayer?.price_paid ?? 0);
    if (netCost > remainingBudget || picking) return;
    setPicking(player.id);
    setPickError(null);
    try {
      const result = await api.roster.pick(leagueId, player.id, slot);
      onPick(result);
    } catch (e) {
      setPickError(e instanceof Error ? e.message : "Error al fichar jugador");
      setPicking(null);
    }
  };

  const slotLabel = ROLE_LABEL[role] ?? slot;

  const SKELETON_COUNT = 8;

  const panel = (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        background: "rgba(0,0,0,0.75)",
        paddingBottom: "68px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#111111",
          border: "1px solid #222222",
          borderRadius: "18px 18px 0 0",
          width: "100%",
          maxWidth: "560px",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 16px 14px",
            borderBottom: "1px solid #1e1e1e",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <div>
            <p
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: "20px",
                fontWeight: 700,
                color: "#FFFFFF",
                margin: 0,
                lineHeight: 1.2,
              }}
            >
              Elegir {slotLabel}
            </p>
            <p
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "11px",
                color: "#444444",
                margin: "3px 0 0",
              }}
            >
              Ordenados por puntos · {slotLabel}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background: "#1e1e1e",
              border: "1px solid #2a2a2a",
              color: "#777777",
              fontSize: 14,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            ✕
          </button>
        </div>

        {/* Budget bar */}
        <div
          style={{
            padding: "10px 16px",
            borderBottom: "1px solid #1a1a1a",
            background: "#0d0d0d",
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "12px", color: "#555555" }}>
            Presupuesto:
          </span>
          <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "14px", fontWeight: 700, color: "#FCD400" }}>
            ${remainingBudget.toFixed(1)}M
          </span>
          {currentPlayer && (
            <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "11px", color: "#555555" }}>
              · Liberás ${currentPlayer.price_paid.toFixed(1)}M de {currentPlayer.name}
            </span>
          )}
          {pickError && (
            <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "11px", color: "#ef4444", width: "100%", marginTop: 2 }}>
              {pickError}
            </span>
          )}
        </div>

        {/* Player list */}
        <div style={{ overflowY: "auto", flex: 1 }}>
          {loading ? (
            // Skeleton rows — same height as real rows so the panel appears at full size
            Array.from({ length: SKELETON_COUNT }).map((_, i) => <SkeletonRow key={i} />)
          ) : players.length === 0 ? (
            <div
              style={{
                padding: "40px 32px",
                textAlign: "center",
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "13px",
                color: "#555555",
              }}
            >
              No hay jugadores disponibles para este rol
            </div>
          ) : (
            players.map((player) => (
              <PlayerRow
                key={player.id}
                player={player}
                currentPlayer={currentPlayer}
                remainingBudget={remainingBudget}
                picking={picking}
                onPick={handlePick}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );

  if (!mounted) return null;
  return createPortal(panel, document.body);
}
