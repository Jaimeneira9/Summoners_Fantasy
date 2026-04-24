"use client";

import { createPortal } from "react-dom";
import { useState, useEffect, useCallback } from "react";
import { Split } from "@/lib/api";

export interface FilterDrawerFilters {
  splitId: string | null;
  role: string;
  team: string;
  priceMin: number;
  priceMax: number | undefined;
}

interface FilterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (filters: FilterDrawerFilters) => void;
  committed: FilterDrawerFilters;
  splits: Split[];
  teams: string[];          // without "all" — drawer adds "Todos los equipos"
  roleLabels: Record<string, string>;
  isMobile: boolean;
}

export default function FilterDrawer({
  isOpen,
  onClose,
  onApply,
  committed,
  splits,
  teams,
  roleLabels,
  isMobile,
}: FilterDrawerProps) {
  const [draft, setDraft] = useState<FilterDrawerFilters>(committed);
  const [isClosing, setIsClosing] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [hoveredSplit, setHoveredSplit] = useState<string | null>(null);

  useEffect(() => { setMounted(true); }, []);
  useEffect(() => { if (isOpen) setDraft({ ...committed }); }, [isOpen, committed]);

  const priceValid = draft.priceMax === undefined || draft.priceMin <= draft.priceMax;

  const handleClose = useCallback(() => {
    setIsClosing(true);
    setTimeout(() => { setIsClosing(false); onClose(); }, 220);
  }, [onClose]);

  // Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, handleClose]);

  if (!mounted || (!isOpen && !isClosing)) return null;

  return createPortal(
    <div style={{ position: "fixed", inset: 0, zIndex: 9999, display: "flex" }}>
      {/* Overlay */}
      <div
        className={isClosing ? "opacity-0 transition-opacity duration-200" : "animate-fade-in"}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)" }}
        onClick={handleClose}
      />
      {/* Panel */}
      <div
        className={`absolute right-0 top-0 bottom-0 flex flex-col ${isClosing ? "animate-slide-out-right" : "animate-slide-in-right"}`}
        style={{
          width: isMobile ? "100vw" : "320px",
          background: "#1A1A1A",
          borderLeft: "1px solid #2A2A2A",
          zIndex: 10000,
          overflowY: "auto",
        }}
      >
        {/* Header */}
        <div style={{ padding: "16px", borderBottom: "1px solid #2A2A2A", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 14, fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.08em" }}>FILTROS</span>
          <button
            onClick={handleClose}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#FFF")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#888")}
            className="active:scale-95 transition-all duration-150"
            style={{ background: "none", border: "none", color: "#888", cursor: "pointer", fontSize: 18, lineHeight: 1 }}
          >✕</button>
        </div>

        {/* Section: COMPETICIÓN */}
        {splits.length > 0 && (
          <div style={{ padding: "16px", borderBottom: "1px solid #2A2A2A" }}>
            <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, fontWeight: 600, color: "#888", letterSpacing: "0.08em", marginBottom: 10 }}>COMPETICIÓN</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {splits.map((s) => {
                const active = draft.splitId === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => setDraft(d => ({ ...d, splitId: s.id }))}
                    onMouseEnter={() => { if (!active) setHoveredSplit(s.id); }}
                    onMouseLeave={() => setHoveredSplit(null)}
                    style={{ background: active ? "#FCD400" : hoveredSplit === s.id ? "rgba(255,255,255,0.08)" : "#0A0A0A", border: `1px solid ${active ? "#FCD400" : "#2A2A2A"}`, borderRadius: 6, padding: "5px 12px", color: active ? "#000" : "#888", fontSize: 11, fontWeight: active ? 700 : 500, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif", letterSpacing: "0.04em", transition: "background 150ms" }}
                  >{s.name}</button>
                );
              })}
            </div>
          </div>
        )}

        {/* Section: ROL */}
        <div style={{ padding: "16px", borderBottom: "1px solid #2A2A2A" }}>
          <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, fontWeight: 600, color: "#888", letterSpacing: "0.08em", marginBottom: 10 }}>ROL</div>
          <select
            value={draft.role}
            onChange={(e) => setDraft(d => ({ ...d, role: e.target.value }))}
            className="outline-none w-full"
            style={{ background: "#0A0A0A", color: "#CCCCCC", border: "1px solid #2A2A2A", borderRadius: 6, padding: "6px 10px", fontSize: 13, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif" }}
          >
            <option value="all">Todos los roles</option>
            {["top", "jungle", "mid", "adc", "support"].map((r) => (
              <option key={r} value={r}>{roleLabels[r] ?? r.toUpperCase()}</option>
            ))}
          </select>
        </div>

        {/* Section: EQUIPO */}
        <div style={{ padding: "16px", borderBottom: "1px solid #2A2A2A" }}>
          <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, fontWeight: 600, color: "#888", letterSpacing: "0.08em", marginBottom: 10 }}>EQUIPO</div>
          <select
            value={draft.team}
            onChange={(e) => setDraft(d => ({ ...d, team: e.target.value }))}
            className="outline-none w-full"
            style={{ background: "#0A0A0A", color: "#CCCCCC", border: "1px solid #2A2A2A", borderRadius: 6, padding: "6px 10px", fontSize: 13, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif" }}
          >
            <option value="all">Todos los equipos</option>
            {teams.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        {/* Section: PRECIO */}
        <div style={{ padding: "16px", borderBottom: "1px solid #2A2A2A" }}>
          <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, fontWeight: 600, color: "#888", letterSpacing: "0.08em", marginBottom: 10 }}>PRECIO (M)</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 10, color: "#666", marginBottom: 4 }}>MÍN</div>
              <input
                type="number"
                min={0}
                max={50}
                step={0.5}
                value={draft.priceMin}
                onChange={(e) => setDraft(d => ({ ...d, priceMin: parseFloat(e.target.value) || 0 }))}
                className="outline-none w-full"
                style={{ background: "#0A0A0A", color: "#CCCCCC", border: `1px solid ${!priceValid ? "#f87171" : "#2A2A2A"}`, borderRadius: 6, padding: "6px 10px", fontSize: 13, fontFamily: "'Space Grotesk',sans-serif" }}
              />
            </div>
            <span style={{ color: "#444", marginTop: 16 }}>—</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 10, color: "#666", marginBottom: 4 }}>MÁX</div>
              <input
                type="number"
                min={0}
                max={50}
                step={0.5}
                value={draft.priceMax ?? ""}
                onChange={(e) => setDraft(d => ({ ...d, priceMax: e.target.value === "" ? undefined : parseFloat(e.target.value) || 0 }))}
                className="outline-none w-full"
                style={{ background: "#0A0A0A", color: "#CCCCCC", border: `1px solid ${!priceValid ? "#f87171" : "#2A2A2A"}`, borderRadius: 6, padding: "6px 10px", fontSize: 13, fontFamily: "'Space Grotesk',sans-serif" }}
              />
            </div>
          </div>
          {!priceValid && (
            <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontSize: 11, color: "#f87171", marginTop: 6 }}>El mínimo no puede ser mayor al máximo</div>
          )}
        </div>

        {/* Footer */}
        <div style={{ marginTop: "auto", padding: "16px", borderTop: "1px solid #2A2A2A", display: "flex", gap: 8 }}>
          <button
            onClick={() => setDraft({ splitId: splits[0]?.id ?? null, role: "all", team: "all", priceMin: 0, priceMax: undefined })}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#FFF")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#888")}
            className="active:scale-95 transition-all duration-150"
            style={{ flex: 1, background: "#0A0A0A", border: "1px solid #2A2A2A", borderRadius: 6, padding: "8px 0", color: "#888", fontSize: 12, cursor: "pointer", fontFamily: "'Space Grotesk',sans-serif", fontWeight: 600, letterSpacing: "0.04em" }}
          >RESETEAR</button>
          <button
            onClick={() => { if (priceValid) onApply(draft); }}
            disabled={!priceValid}
            className="hover:brightness-90 active:scale-95 transition-all duration-150"
            style={{ flex: 2, background: priceValid ? "#FCD400" : "#2A2A2A", border: "none", borderRadius: 6, padding: "8px 0", color: priceValid ? "#000" : "#555", fontSize: 12, cursor: priceValid ? "pointer" : "not-allowed", fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, letterSpacing: "0.06em" }}
          >APLICAR</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
