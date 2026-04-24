"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

// ---------------------------------------------------------------------------
// League SVG logos
// ---------------------------------------------------------------------------

function LogoLEC() {
  return (
    <svg width="22" height="22" viewBox="0 0 34 34" fill="none">
      <path d="M7 26 L7 12 L11 16 L17 8 L23 16 L27 12 L27 26 Z" stroke="#8B5CF6" strokeWidth="2" strokeLinejoin="round" fill="none"/>
      <rect x="10" y="22" width="14" height="3" rx="1" fill="#8B5CF6"/>
    </svg>
  );
}

function LogoLCK() {
  return (
    <svg width="22" height="22" viewBox="0 0 34 34" fill="none">
      <path d="M10 9 L10 25" stroke="#EF4444" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M10 17 L24 9" stroke="#EF4444" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M10 17 L24 25" stroke="#EF4444" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M17 13 L24 25" stroke="#EF4444" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}

function LogoLPL() {
  return (
    <svg width="22" height="22" viewBox="0 0 34 34" fill="none">
      <path d="M17 8 C13 12 11 15 13 18 C11 17 10 20 12 22 C14 24 18 24 20 22 C24 18 23 13 17 8Z" stroke="#3B82F6" strokeWidth="1.8" fill="none" strokeLinejoin="round"/>
      <path d="M17 14 C16 17 17 20 19 21" stroke="#60A5FA" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function LogoLCS() {
  return (
    <svg width="22" height="22" viewBox="0 0 34 34" fill="none">
      <path d="M12 9 H22 V19 C22 23 12 23 12 19 Z" stroke="#60A5FA" strokeWidth="2" strokeLinejoin="round" fill="none"/>
      <path d="M12 13 H9 C9 13 9 18 12 18" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round"/>
      <path d="M22 13 H25 C25 13 25 18 22 18" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round"/>
      <path d="M15 23 L15 26 M19 23 L19 26" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round"/>
      <path d="M13 26 H21" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

function LogoMSI() {
  return (
    <svg width="22" height="22" viewBox="0 0 34 34" fill="none">
      <circle cx="17" cy="17" r="9" stroke="#C89B3C" strokeWidth="2"/>
      <path d="M8 17 Q12 12 17 17 Q22 22 26 17" stroke="#C89B3C" strokeWidth="1.5" fill="none"/>
      <path d="M17 8 Q14 12 14 17 Q14 22 17 26" stroke="#C89B3C" strokeWidth="1.5" fill="none"/>
      <path d="M17 8 Q20 12 20 17 Q20 22 17 26" stroke="#C89B3C" strokeWidth="1.5" fill="none"/>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// League data
// ---------------------------------------------------------------------------

type CompetitionOption = {
  id: string;
  name: string;
  region: string;
  active: boolean;
  logo: React.ReactNode;
  iconBg: string;
};

const COMPETITIONS: CompetitionOption[] = [
  { id: "lec", name: "LEC", region: "Europe", active: true,  logo: <LogoLEC />, iconBg: "#1A1228" },
  { id: "lck", name: "LCK", region: "Korea",  active: false, logo: <LogoLCK />, iconBg: "#1A1228" },
  { id: "lpl", name: "LPL", region: "China",  active: false, logo: <LogoLPL />, iconBg: "#1A1228" },
  { id: "lcs", name: "LCS", region: "NA",     active: false, logo: <LogoLCS />, iconBg: "#1A1228" },
  { id: "msi", name: "MSI", region: "Global", active: false, logo: <LogoMSI />, iconBg: "#1A1228" },
];

// ---------------------------------------------------------------------------
// Lock icon (SVG inline)
// ---------------------------------------------------------------------------

function LockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
      <rect x="5" y="11" width="14" height="10" rx="2" stroke="#C89B3C" strokeWidth="2"/>
      <path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="#C89B3C" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Types & props
// ---------------------------------------------------------------------------

type ModalMode = "create" | "join";

interface LeagueModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMode?: ModalMode;
}

// ---------------------------------------------------------------------------
// LeagueModal
// ---------------------------------------------------------------------------

export function LeagueModal({ isOpen, onClose, initialMode = "create" }: LeagueModalProps) {
  const router = useRouter();
  const [mode, setMode] = useState<ModalMode>(initialMode);

  // Form state — create
  const [ligaNombre, setLigaNombre] = useState("");
  const [maxManagers, setMaxManagers] = useState<number | null>(8);
  const [gameMode, setGameMode] = useState<"draft_market" | "budget_pick">("draft_market");

  // Form state — join
  const [inviteCode, setInviteCode] = useState("");

  // Shared async state
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Trap focus and handle Escape
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Lock body scroll while open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [isOpen]);

  // Reset state when modal opens (and sync mode with initialMode)
  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setLigaNombre("");
      setGameMode("draft_market");
      setMaxManagers(8);
      setInviteCode("");
      setError(null);
      setBusy(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  const done = () => { onClose(); router.refresh(); };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.leagues.create(ligaNombre.trim(), maxManagers, gameMode);
      done();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al crear la liga");
    } finally {
      setBusy(false);
    }
  };

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.leagues.join(inviteCode.trim());
      done();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al unirse");
    } finally {
      setBusy(false);
    }
  };

  // Shared input styles
  const inputBase: React.CSSProperties = {
    width: "100%",
    background: "#1C1D2A",
    border: "1px solid #2A2B3D",
    borderRadius: "10px",
    color: "#E8E9EE",
    padding: "10px 14px",
    fontSize: "14px",
    outline: "none",
    transition: "border-color 0.15s, box-shadow 0.15s",
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: "11px",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#6B6C7E",
    marginBottom: "6px",
  };

  return (
    // Overlay
    <div
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.70)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Panel */}
      <div
        style={{
          background: "#14151E",
          width: "calc(100% - 32px)",
          maxWidth: "700px",
          maxHeight: "90vh",
          borderRadius: "16px",
          display: "flex",
          flexDirection: "column",
          overflowY: "auto",
          position: "relative",
        }}
        className="animate-modal-in"
      >
        {/* ---- Header ---- */}
        <div
          style={{
            padding: "20px 24px 16px",
            borderBottom: "1px solid #2A2B3D",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          {/* Tab switcher */}
          <div
            style={{
              display: "flex",
              gap: "4px",
              background: "#1C1D2A",
              borderRadius: "10px",
              padding: "4px",
            }}
          >
            {(["create", "join"] as ModalMode[]).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(null); }}
                style={{
                  padding: "6px 16px",
                  borderRadius: "7px",
                  fontSize: "13px",
                  fontWeight: 600,
                  border: "none",
                  cursor: "pointer",
                  transition: "background 0.15s, color 0.15s",
                  background: mode === m ? "#C89B3C" : "transparent",
                  color: mode === m ? "#111111" : "#6B6C7E",
                }}
              >
                {m === "create" ? "Crear liga" : "Unirse"}
              </button>
            ))}
          </div>

          {/* Close button */}
          <button
            onClick={onClose}
            aria-label="Cerrar"
            style={{
              background: "#1C1D2A",
              border: "1px solid #2A2B3D",
              borderRadius: "8px",
              color: "#6B6C7E",
              width: "32px",
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* ---- Body: two-column on desktop ---- */}
        <div
          style={{ display: "flex", flex: 1, overflow: "hidden", minHeight: 0 }}
          className="flex-col md:flex-row"
        >
          {/* Left panel: league selector (desktop: sidebar, mobile: horizontal chips) */}
          {/* Mobile chips */}
          <div
            style={{
              padding: "16px 24px",
              borderBottom: "1px solid #2A2B3D",
              flexShrink: 0,
              overflowX: "auto",
            }}
            className="md:hidden"
          >
            <p style={{ ...labelStyle, marginBottom: "10px" }}>Competición</p>
            <div style={{ display: "flex", gap: "10px" }}>
              {COMPETITIONS.map((c) => (
                <div
                  key={c.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "6px",
                    opacity: c.active ? 1 : 0.4,
                    flexShrink: 0,
                  }}
                >
                  <div
                    style={{
                      width: "60px",
                      height: "60px",
                      borderRadius: "14px",
                      background: c.active ? "rgba(200,155,60,0.10)" : c.iconBg,
                      border: c.active ? "1.5px solid rgba(200,155,60,0.35)" : "1.5px solid #2A2B3D",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {c.logo}
                  </div>
                  <span style={{ fontSize: "11px", fontWeight: 600, color: c.active ? "#E8E9EE" : "#6B6C7E" }}>
                    {c.name}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Desktop sidebar */}
          <div
            style={{
              width: "220px",
              flexShrink: 0,
              borderRight: "1px solid #2A2B3D",
              padding: "20px 0",
              overflowY: "auto",
            }}
            className="hidden md:block"
          >
            <p style={{ ...labelStyle, padding: "0 20px", marginBottom: "10px" }}>Competición</p>
            {COMPETITIONS.map((c) => (
              <div
                key={c.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 20px",
                  opacity: c.active ? 1 : 0.4,
                  background: c.active ? "rgba(200,155,60,0.06)" : "transparent",
                  borderLeft: c.active ? "2px solid #C89B3C" : "2px solid transparent",
                  cursor: c.active ? "default" : "not-allowed",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "9px",
                    background: c.active ? "rgba(200,155,60,0.10)" : c.iconBg,
                    border: c.active ? "1px solid rgba(200,155,60,0.35)" : "1px solid #2A2B3D",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {c.logo}
                </div>
                <div style={{ minWidth: 0 }}>
                  <p style={{ fontSize: "13px", fontWeight: 700, color: c.active ? "#E8E9EE" : "#6B6C7E", margin: 0 }}>
                    {c.name}
                  </p>
                  <p style={{ fontSize: "11px", color: "#6B6C7E", margin: 0 }}>{c.region}</p>
                </div>
                {!c.active && (
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: "9px",
                      fontWeight: 700,
                      letterSpacing: "0.06em",
                      background: "#2A2B3D",
                      color: "#6B6C7E",
                      borderRadius: "4px",
                      padding: "2px 5px",
                      flexShrink: 0,
                    }}
                  >
                    SOON
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Right panel: form */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
            {mode === "create" ? (
              <form onSubmit={handleCreate} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div>
                  <p
                    style={{
                      fontSize: "18px",
                      fontWeight: 700,
                      color: "#E8E9EE",
                      margin: "0 0 4px",
                    }}
                  >
                    Nueva liga
                  </p>
                  <p style={{ fontSize: "13px", color: "#6B6C7E", margin: 0 }}>
                    Configurá tu liga de LEC y compartí el código con tus amigos.
                  </p>
                </div>

                {/* Game mode cards */}
                <div>
                  <label style={labelStyle}>Modo de juego</label>
                  <div style={{ display: "flex", gap: "10px" }}>
                    {(
                      [
                        {
                          value: "draft_market" as const,
                          label: "Mercado",
                          desc: "Jugadores exclusivos, precios dinámicos",
                          icon: (
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                              <path d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-1.5 6h13" stroke="#C89B3C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                              <circle cx="9" cy="21" r="1" fill="#C89B3C"/>
                              <circle cx="20" cy="21" r="1" fill="#C89B3C"/>
                            </svg>
                          ),
                        },
                        {
                          value: "budget_pick" as const,
                          label: "Presupuesto",
                          desc: "Ficha cualquier jugador con tu presupuesto",
                          icon: (
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                              <circle cx="12" cy="12" r="9" stroke="#C89B3C" strokeWidth="1.8"/>
                              <path d="M12 7v1m0 8v1M9.5 9.5C9.5 8.4 10.6 7.5 12 7.5s2.5.9 2.5 2c0 2.5-5 2.5-5 5 0 1.1 1.1 2 2.5 2s2.5-.9 2.5-2" stroke="#C89B3C" strokeWidth="1.8" strokeLinecap="round"/>
                            </svg>
                          ),
                        },
                      ] as const
                    ).map((opt) => {
                      const selected = gameMode === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => {
                            setGameMode(opt.value);
                            setMaxManagers(opt.value === "draft_market" ? 8 : null);
                          }}
                          style={{
                            flex: 1,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "flex-start",
                            gap: "8px",
                            padding: "14px",
                            background: selected ? "rgba(200,155,60,0.08)" : "#1C1D2A",
                            border: `1.5px solid ${selected ? "#C89B3C" : "#2A2B3D"}`,
                            borderRadius: "10px",
                            cursor: "pointer",
                            textAlign: "left",
                            transition: "border-color 0.15s, background 0.15s",
                          }}
                        >
                          <div
                            style={{
                              width: "36px",
                              height: "36px",
                              borderRadius: "9px",
                              background: selected ? "rgba(200,155,60,0.14)" : "#14151E",
                              border: `1px solid ${selected ? "rgba(200,155,60,0.35)" : "#2A2B3D"}`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            {opt.icon}
                          </div>
                          <p style={{ fontSize: "13px", fontWeight: 700, color: selected ? "#E8E9EE" : "#9899A8", margin: 0 }}>
                            {opt.label}
                          </p>
                          <p style={{ fontSize: "11px", color: "#6B6C7E", margin: 0, lineHeight: 1.4 }}>
                            {opt.desc}
                          </p>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Liga name */}
                <div>
                  <label style={labelStyle}>Nombre de la liga</label>
                  <input
                    value={ligaNombre}
                    onChange={(e) => setLigaNombre(e.target.value)}
                    required
                    minLength={3}
                    maxLength={60}
                    placeholder="Mi liga de LEC..."
                    style={inputBase}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "#C89B3C";
                      e.currentTarget.style.boxShadow = "0 0 0 3px rgba(200,155,60,0.12)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "#2A2B3D";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  />
                </div>

                {/* Max managers — opciones dinámicas según game_mode */}
                <div>
                  <label style={labelStyle}>Máximo de managers</label>
                  <select
                    value={maxManagers === null ? "null" : String(maxManagers)}
                    onChange={(e) => {
                      const v = e.target.value;
                      setMaxManagers(v === "null" ? null : Number(v));
                    }}
                    style={{
                      ...inputBase,
                      cursor: "pointer",
                      appearance: "none",
                      WebkitAppearance: "none",
                      backgroundImage: `url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L6 7L11 1' stroke='%236B6C7E' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                      backgroundRepeat: "no-repeat",
                      backgroundPosition: "right 14px center",
                      paddingRight: "36px",
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "#C89B3C";
                      e.currentTarget.style.boxShadow = "0 0 0 3px rgba(200,155,60,0.12)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "#2A2B3D";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  >
                    <option value={4}>4 managers</option>
                    <option value={6}>6 managers</option>
                    <option value={8}>8 managers</option>
                    {gameMode === "budget_pick" && (
                      <>
                        <option value={10}>10 managers</option>
                        <option value={12}>12 managers</option>
                        <option value="null">Sin límite</option>
                      </>
                    )}
                  </select>
                </div>

                {error && (
                  <p style={{ fontSize: "13px", color: "#EF4444", margin: 0 }}>{error}</p>
                )}

                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", paddingTop: "4px" }}>
                  <button
                    type="button"
                    onClick={onClose}
                    style={{
                      padding: "10px 18px",
                      fontSize: "13px",
                      fontWeight: 500,
                      color: "#6B6C7E",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      borderRadius: "8px",
                    }}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={busy || ligaNombre.trim().length < 3}
                    style={{
                      padding: "10px 24px",
                      fontSize: "13px",
                      fontWeight: 700,
                      color: "#111111",
                      background: "#C89B3C",
                      border: "none",
                      borderRadius: "10px",
                      cursor: busy || ligaNombre.trim().length < 3 ? "not-allowed" : "pointer",
                      opacity: busy || ligaNombre.trim().length < 3 ? 0.4 : 1,
                      transition: "opacity 0.15s, filter 0.15s",
                    }}
                    onMouseEnter={(e) => {
                      if (!busy && ligaNombre.trim().length >= 3)
                        e.currentTarget.style.filter = "brightness(0.9)";
                    }}
                    onMouseLeave={(e) => { e.currentTarget.style.filter = "none"; }}
                  >
                    {busy ? "Creando…" : "Crear liga"}
                  </button>
                </div>
              </form>
            ) : (
              /* ---- JOIN form ---- */
              <form onSubmit={handleJoin} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <div>
                  <p
                    style={{
                      fontSize: "18px",
                      fontWeight: 700,
                      color: "#E8E9EE",
                      margin: "0 0 4px",
                    }}
                  >
                    Unirse a una liga
                  </p>
                  <p style={{ fontSize: "13px", color: "#6B6C7E", margin: 0 }}>
                    Ingresá el código que te pasó el creador de la liga.
                  </p>
                </div>

                {/* Invite code */}
                <div>
                  <label style={labelStyle}>Código de invitación</label>
                  <div style={{ position: "relative" }}>
                    <span
                      style={{
                        position: "absolute",
                        left: "12px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      <LockIcon />
                    </span>
                    <input
                      value={inviteCode}
                      onChange={(e) => setInviteCode(e.target.value)}
                      required
                      placeholder="ej. a3f9c1b2"
                      style={{
                        ...inputBase,
                        borderColor: "#C89B3C",
                        letterSpacing: "0.08em",
                        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                        paddingLeft: "38px",
                        boxShadow: "0 0 0 0px rgba(200,155,60,0.12)",
                      }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = "#C89B3C";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(200,155,60,0.12)";
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = "#C89B3C";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>
                  <p style={{ fontSize: "12px", color: "#6B6C7E", marginTop: "6px", margin: "6px 0 0" }}>
                    Pedile el código al creador de la liga
                  </p>
                </div>

                {error && (
                  <p style={{ fontSize: "13px", color: "#EF4444", margin: 0 }}>{error}</p>
                )}

                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end", paddingTop: "4px" }}>
                  <button
                    type="button"
                    onClick={onClose}
                    style={{
                      padding: "10px 18px",
                      fontSize: "13px",
                      fontWeight: 500,
                      color: "#6B6C7E",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      borderRadius: "8px",
                    }}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={busy || inviteCode.trim().length === 0}
                    style={{
                      padding: "10px 24px",
                      fontSize: "13px",
                      fontWeight: 700,
                      color: "#111111",
                      background: "#C89B3C",
                      border: "none",
                      borderRadius: "10px",
                      cursor: busy || inviteCode.trim().length === 0 ? "not-allowed" : "pointer",
                      opacity: busy || inviteCode.trim().length === 0 ? 0.4 : 1,
                      transition: "opacity 0.15s, filter 0.15s",
                    }}
                    onMouseEnter={(e) => {
                      if (!busy && inviteCode.trim().length > 0)
                        e.currentTarget.style.filter = "brightness(0.9)";
                    }}
                    onMouseLeave={(e) => { e.currentTarget.style.filter = "none"; }}
                  >
                    {busy ? "Uniéndose…" : "Unirse"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
