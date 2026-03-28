"use client";

import Link from "next/link";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);

    const supabase = createClient();
    const origin = window.location.origin;

    await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${origin}/auth/callback?next=/reset-password`,
    });

    // Always show success — don't leak whether user exists
    setSent(true);
    setLoading(false);
  }

  return (
    <div className="w-full max-w-md">
      {/* Logo mobile */}
      <div className="flex items-center gap-2 mb-8 lg:hidden">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: "#FCD400" }}
        >
          <span className="material-symbols-outlined text-base" style={{ color: "#111111" }}>
            military_tech
          </span>
        </div>
        <span
          className="font-black text-lg tracking-tight uppercase"
          style={{ color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          Summoner&apos;s Fantasy
        </span>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1
          className="font-black text-3xl uppercase tracking-tight mb-2"
          style={{ color: "#F0E8D0", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          Recuperar contraseña
        </h1>
        <p className="text-sm" style={{ color: "#555555" }}>
          Ingresá tu email y te enviamos un link para resetear tu contraseña.
        </p>
      </div>

      {/* Success state */}
      {sent ? (
        <div className="space-y-4">
          <div
            className="p-4 rounded-lg text-sm"
            style={{
              background: "rgba(34,197,94,0.1)",
              border: "1px solid rgba(34,197,94,0.3)",
              color: "#22C55E",
            }}
          >
            Si ese email existe en nuestro sistema, te enviamos un link de recuperación.
          </div>
          <Link
            href="/login"
            className="block text-sm font-semibold hover:underline"
            style={{ color: "#FCD400" }}
          >
            ← Volver al login
          </Link>
        </div>
      ) : (
        <>
          <form onSubmit={handleSubmit}>
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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-6 text-sm font-bold transition-all active:scale-95"
                style={{
                  background: loading ? "#b89e00" : "#FCD400",
                  color: "#111111",
                  borderRadius: "8px",
                  fontFamily: "'Space Grotesk', sans-serif",
                  opacity: loading ? 0.7 : 1,
                  cursor: loading ? "not-allowed" : "pointer",
                }}
                onMouseEnter={(e) => {
                  if (!loading) e.currentTarget.style.background = "#e6c000";
                }}
                onMouseLeave={(e) => {
                  if (!loading) e.currentTarget.style.background = "#FCD400";
                }}
              >
                {loading ? "Enviando..." : "Enviar link de recuperación"}
              </button>
            </div>
          </form>

          <p className="mt-6 text-sm" style={{ color: "#555555" }}>
            <Link href="/login" className="font-semibold hover:underline" style={{ color: "#FCD400" }}>
              ← Volver al login
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
