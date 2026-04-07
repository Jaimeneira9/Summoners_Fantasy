"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ActionPopupProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;

  playerName: string;
  playerRole: string;
  playerTeam: string;
  playerImage?: string | null;

  /** "input" muestra campo numérico editable; "confirm" muestra mensaje fijo */
  mode: "input" | "confirm";

  /** Monto mínimo para mode="input" */
  minAmount?: number;

  /** Monto máximo permitido para mode="input" (ej: presupuesto disponible) */
  maxAmount?: number;

  /** Puja existente del usuario para este listing — pre-llena el input y ajusta el label */
  existingBid?: number;

  /** Texto del botón de confirmación */
  confirmLabel?: string;

  /** Texto de preview dinámico bajo el input (mode="input") */
  previewText?: (amount: number) => string;

  /** Mensaje fijo de confirmación (mode="confirm") */
  confirmMessage?: string;

  onConfirm: (amount?: number) => Promise<void>;

  isLoading?: boolean;
  error?: string | null;
}

// ---------------------------------------------------------------------------
// ActionPopup
// ---------------------------------------------------------------------------

export function ActionPopup({
  isOpen,
  onClose,
  title,
  playerName,
  playerRole,
  playerTeam,
  playerImage,
  mode,
  minAmount = 0,
  maxAmount,
  existingBid,
  confirmLabel = "Confirmar",
  previewText,
  confirmMessage,
  onConfirm,
  isLoading = false,
  error = null,
}: ActionPopupProps) {
  const [mounted, setMounted] = useState(false);
  const [amount, setAmount] = useState(
    existingBid != null ? existingBid.toFixed(2)
    : minAmount > 0     ? minAmount.toFixed(2)
    : ""
  );

  useEffect(() => { setMounted(true); }, []);

  // Sync amount cuando cambia el listing seleccionado
  useEffect(() => {
    if (existingBid != null) setAmount(existingBid.toFixed(2));
    else if (minAmount > 0)  setAmount(minAmount.toFixed(2));
  }, [minAmount, existingBid]);

  // Cerrar con Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!mounted || !isOpen) return null;

  const parsedAmount = parseFloat(amount);
  const isValidAmount =
    !isNaN(parsedAmount) &&
    parsedAmount >= minAmount &&
    parsedAmount > 0 &&
    (maxAmount === undefined || parsedAmount <= maxAmount);

  const handleConfirm = async () => {
    if (mode === "input") {
      await onConfirm(parsedAmount);
    } else {
      await onConfirm();
    }
  };

  const modal = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-sm flex flex-col"
        style={{
          background: "#161b27",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "16px",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        >
          <p
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: "13px",
              fontWeight: 700,
              color: "#F0E8D0",
            }}
          >
            {title}
          </p>
          <button
            onClick={onClose}
            className="transition-colors"
            style={{ color: "#555", fontSize: "18px", lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        {/* Player info */}
        <div
          className="flex items-center gap-3 px-5 py-4"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        >
          {playerImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={playerImage}
              alt={playerName}
              style={{
                width: 48,
                height: 48,
                borderRadius: "8px",
                objectFit: "cover",
                objectPosition: "center top",
                flexShrink: 0,
              }}
            />
          ) : (
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "8px",
                background: "#1e2535",
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "18px",
                fontWeight: 700,
                color: "rgba(255,255,255,0.2)",
                fontFamily: "'Barlow Condensed', sans-serif",
              }}
            >
              {playerName[0]?.toUpperCase()}
            </div>
          )}

          <div className="flex flex-col gap-0.5 min-w-0">
            <p
              style={{
                fontFamily: "'Barlow Condensed', sans-serif",
                fontSize: "20px",
                fontWeight: 700,
                color: "#FFFFFF",
                letterSpacing: "-0.01em",
                lineHeight: 1,
              }}
            >
              {playerName}
            </p>
            <p
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "11px",
                color: "#8892aa",
              }}
            >
              {playerRole.toUpperCase()} · {playerTeam}
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-4 flex flex-col gap-3">
          {mode === "input" && (
            <>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.5"
                  min={minAmount}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="flex-1 outline-none appearance-none [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  style={{
                    background: "#1e2535",
                    border: "1px solid rgba(252,212,0,0.2)",
                    borderRadius: "8px",
                    color: "#F0E8D0",
                    padding: "8px 12px",
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "14px",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "#FCD400"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(252,212,0,0.2)"; }}
                />
                <span
                  style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "12px",
                    color: "#555",
                    flexShrink: 0,
                  }}
                >
                  M
                </span>
              </div>

              {previewText && isValidAmount && (
                <p
                  style={{
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontSize: "12px",
                    color: "#8892aa",
                  }}
                >
                  {previewText(parsedAmount)}
                </p>
              )}
            </>
          )}

          {mode === "confirm" && confirmMessage && (
            <p
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "13px",
                color: "#8892aa",
              }}
            >
              {confirmMessage}
            </p>
          )}

          {error && (
            <p
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: "12px",
                color: "#f87171",
              }}
            >
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={onClose}
              className="flex-1 py-2 text-sm transition-colors"
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                color: "#555",
                background: "transparent",
                border: "1px solid #2a2a2a",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            >
              Cancelar
            </button>
            <button
              onClick={handleConfirm}
              disabled={isLoading || (mode === "input" && !isValidAmount)}
              className="flex-[2] py-2 text-sm font-bold rounded-lg transition-all active:scale-95 disabled:opacity-40"
              style={{
                fontFamily: "'Space Grotesk', sans-serif",
                background: "linear-gradient(135deg, #FCD400, #FCB900)",
                color: "#111111",
                borderRadius: "8px",
                border: "none",
                cursor: isLoading || (mode === "input" && !isValidAmount) ? "not-allowed" : "pointer",
              }}
            >
              {isLoading ? "…" : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
