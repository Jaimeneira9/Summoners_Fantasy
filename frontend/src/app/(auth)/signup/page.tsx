"use client";

import Link from "next/link";
import { useFormState, useFormStatus } from "react-dom";
import { signup } from "@/app/actions/auth";

const initialState = { error: null };

export default function SignupPage() {
  const [state, formAction] = useFormState(signup, initialState);

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="mb-8">
        {/* Logo mobile */}
        <div className="flex items-center gap-2 mb-8 lg:hidden">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "#FCD400" }}
          >
            <span className="material-symbols-outlined text-base" style={{ color: "#111111" }}>military_tech</span>
          </div>
          <span
            className="font-black text-lg tracking-tight uppercase"
            style={{ color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            Summoner&apos;s Fantasy
          </span>
        </div>

        <h1
          className="font-black text-3xl uppercase tracking-tight mb-2"
          style={{ color: "#F0E8D0", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          Crear cuenta
        </h1>
        <p className="text-sm" style={{ color: "#555555" }}>
          ¿Ya tienes cuenta?{" "}
          <Link href="/login" className="font-semibold hover:underline" style={{ color: "#FCD400" }}>
            Inicia sesión
          </Link>
        </p>
      </div>

      {/* Error block */}
      {state?.error && (
        <div
          className="mb-4 p-3 rounded-lg text-sm"
          style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#EF4444" }}
        >
          {state.error}
        </div>
      )}

      {/* Form */}
      <form action={formAction}>
        <div className="space-y-4">
          {/* Email */}
          <div>
            <label
              className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
              htmlFor="email"
              style={{ color: "#888888", fontFamily: "'Space Grotesk', sans-serif" }}
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              name="email"
              required
              autoComplete="email"
              className="w-full px-4 py-3 text-sm transition-all focus:outline-none"
              style={{
                background: "#1A1A1A",
                border: "1px solid #2A2A2A",
                borderRadius: "8px",
                color: "#F0E8D0",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "#FCD400")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#2A2A2A")}
              placeholder="tu@email.com"
            />
          </div>

          {/* Contraseña */}
          <div>
            <label
              className="block text-xs font-semibold uppercase tracking-wider mb-1.5"
              htmlFor="password"
              style={{ color: "#888888", fontFamily: "'Space Grotesk', sans-serif" }}
            >
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              name="password"
              required
              autoComplete="new-password"
              minLength={6}
              className="w-full px-4 py-3 text-sm transition-all focus:outline-none"
              style={{
                background: "#1A1A1A",
                border: "1px solid #2A2A2A",
                borderRadius: "8px",
                color: "#F0E8D0",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "#FCD400")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "#2A2A2A")}
              placeholder="Mínimo 6 caracteres"
            />
          </div>

          {/* Submit */}
          <SubmitButton label="Crear cuenta" pendingLabel="Creando cuenta..." />
        </div>
      </form>
    </div>
  );
}

function SubmitButton({ label, pendingLabel }: { label: string; pendingLabel: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full py-3 px-6 text-sm font-bold transition-all active:scale-95"
      style={{
        background: pending ? "#b89e00" : "#FCD400",
        color: "#111111",
        borderRadius: "8px",
        fontFamily: "'Space Grotesk', sans-serif",
        opacity: pending ? 0.7 : 1,
        cursor: pending ? "not-allowed" : "pointer",
      }}
      onMouseEnter={(e) => { if (!pending) e.currentTarget.style.background = "#e6c000"; }}
      onMouseLeave={(e) => { if (!pending) e.currentTarget.style.background = "#FCD400"; }}
    >
      {pending ? pendingLabel : label}
    </button>
  );
}
