"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

type Mode = "idle" | "create" | "join";

export function LeagueActions() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("idle");

  const close = () => setMode("idle");
  const done = () => { close(); router.refresh(); };

  return (
    <div>
      {mode === "idle" && (
        <div className="flex gap-2">
          <button
            onClick={() => setMode("create")}
            className="px-4 py-2 text-sm font-bold rounded-lg transition-all active:scale-95 hover:brightness-90"
            style={{ background: "var(--color-primary)", color: "#111111" }}
          >
            Crear liga
          </button>
          <button
            onClick={() => setMode("join")}
            className="px-4 py-2 text-sm rounded-lg border transition-all"
            style={{
              borderColor: "var(--color-primary)",
              color: "var(--color-primary)",
              background: "transparent",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "var(--color-primary-bg)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            }}
          >
            Unirse con código
          </button>
        </div>
      )}

      {mode === "create" && <CreateForm onDone={done} onCancel={close} />}
      {mode === "join"   && <JoinForm   onDone={done} onCancel={close} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create league form
// ---------------------------------------------------------------------------
function CreateForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [maxMembers, setMaxMembers] = useState(8);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.leagues.create(name.trim(), maxMembers);
      onDone();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al crear la liga");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl p-5 space-y-4 animate-fade-in"
      style={{
        background: "var(--bg-panel)",
        border: "1px solid var(--border-medium)",
        borderRadius: "12px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      <h2 className="font-bold" style={{ color: "var(--text-primary)" }}>Nueva liga</h2>

      <div className="space-y-1">
        <label className="text-xs uppercase tracking-wider font-medium" style={{ color: "var(--text-secondary)" }}>
          Nombre
        </label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          minLength={3}
          maxLength={60}
          placeholder="Mi liga de la LEC"
          className="w-full rounded-lg px-3 py-2 text-sm placeholder-[#7c7589] outline-none transition-colors"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-medium)",
            color: "var(--text-primary)",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--color-primary)";
            e.currentTarget.style.boxShadow = "0 0 0 3px var(--color-primary-bg)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--border-medium)";
            e.currentTarget.style.boxShadow = "none";
          }}
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs uppercase tracking-wider font-medium" style={{ color: "var(--text-secondary)" }}>
          Jugadores máx. <span className="normal-case font-normal" style={{ color: "var(--text-muted)" }}>(2–9)</span>
        </label>
        <input
          type="number"
          value={maxMembers}
          onChange={(e) => setMaxMembers(Number(e.target.value))}
          min={2}
          max={9}
          className="w-32 rounded-lg px-3 py-2 text-sm outline-none transition-colors"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-medium)",
            color: "var(--text-primary)",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--color-primary)";
            e.currentTarget.style.boxShadow = "0 0 0 3px var(--color-primary-bg)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--border-medium)";
            e.currentTarget.style.boxShadow = "none";
          }}
        />
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm transition-colors underline-offset-2 hover:underline"
          style={{ color: "var(--text-muted)" }}
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={busy || name.trim().length < 3}
          className="px-4 py-2 text-sm font-bold rounded-lg transition-all disabled:opacity-40 active:scale-95 hover:brightness-90"
          style={{ background: "var(--color-primary)", color: "#111111" }}
        >
          {busy ? "Creando…" : "Crear liga"}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Join with code form
// ---------------------------------------------------------------------------
function JoinForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.leagues.join(code.trim());
      onDone();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al unirse");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl p-5 space-y-4 animate-fade-in"
      style={{
        background: "var(--bg-panel)",
        border: "1px solid var(--border-medium)",
        borderRadius: "12px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      <h2 className="font-bold" style={{ color: "var(--text-primary)" }}>Unirse a una liga</h2>

      <div className="space-y-1">
        <label className="text-xs uppercase tracking-wider font-medium" style={{ color: "var(--text-secondary)" }}>
          Código de invitación
        </label>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
          placeholder="ej. a3f9c1b2"
          className="w-full rounded-lg px-3 py-2 text-sm placeholder-[#7c7589] font-mono outline-none transition-colors"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border-medium)",
            color: "var(--text-primary)",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "var(--color-primary)";
            e.currentTarget.style.boxShadow = "0 0 0 3px var(--color-primary-bg)";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "var(--border-medium)";
            e.currentTarget.style.boxShadow = "none";
          }}
        />
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm transition-colors underline-offset-2 hover:underline"
          style={{ color: "var(--text-muted)" }}
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={busy || code.trim().length === 0}
          className="px-4 py-2 text-sm font-bold rounded-lg transition-all disabled:opacity-40 active:scale-95 hover:brightness-90"
          style={{ background: "var(--color-primary)", color: "#111111" }}
        >
          {busy ? "Uniéndose…" : "Unirse"}
        </button>
      </div>
    </form>
  );
}
