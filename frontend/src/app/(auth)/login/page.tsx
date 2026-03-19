"use client";

import Link from "next/link";
import { useFormState, useFormStatus } from "react-dom";
import { login } from "@/app/actions/auth";

const initialState = { error: null };

export default function LoginPage() {
  const [state, formAction] = useFormState(login, initialState);

  return (
    <div className="w-full max-w-md">
      {/* Header */}
      <div className="mb-8">
        {/* Logo mobile */}
        <div className="flex items-center gap-2 mb-8 lg:hidden">
          <div className="w-8 h-8 bg-[#6b21e8] rounded-lg flex items-center justify-center">
            <span className="material-symbols-outlined text-white text-base">military_tech</span>
          </div>
          <span className="font-display font-black text-[#1a1c1a] text-lg tracking-tight uppercase">LOLFantasy</span>
        </div>

        <h1 className="font-display font-black text-3xl text-[#1a1c1a] uppercase tracking-tight mb-2">
          Bienvenido
        </h1>
        <p className="text-[#7c7589] text-sm">
          ¿No tenés cuenta?{" "}
          <Link href="/signup" className="text-[#6b21e8] font-semibold hover:underline">
            Registrate
          </Link>
        </p>
      </div>

      {/* Error block */}
      {state?.error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-sm">
          {state.error}
        </div>
      )}

      {/* Form */}
      <form action={formAction}>
        <div className="space-y-4">
          {/* Email */}
          <div>
            <label
              className="block text-xs font-semibold text-[#4a4456] uppercase tracking-wider mb-1.5"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              name="email"
              required
              autoComplete="email"
              className="w-full px-4 py-3 bg-white border border-[rgba(26,28,26,0.15)] rounded-xl text-[#1a1c1a] placeholder-[#7c7589] text-sm focus:outline-none focus:border-[#6b21e8] focus:ring-2 focus:ring-[#6b21e8]/10 transition-all"
              placeholder="tu@email.com"
            />
          </div>

          {/* Contraseña */}
          <div>
            <label
              className="block text-xs font-semibold text-[#4a4456] uppercase tracking-wider mb-1.5"
              htmlFor="password"
            >
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              name="password"
              required
              autoComplete="current-password"
              className="w-full px-4 py-3 bg-white border border-[rgba(26,28,26,0.15)] rounded-xl text-[#1a1c1a] placeholder-[#7c7589] text-sm focus:outline-none focus:border-[#6b21e8] focus:ring-2 focus:ring-[#6b21e8]/10 transition-all"
              placeholder="Tu contraseña"
            />
          </div>

          {/* Submit */}
          <SubmitButton label="Entrar" pendingLabel="Entrando..." />
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
      className={`w-full bg-[#6b21e8] hover:bg-[#5100bd] text-white font-semibold py-3 px-6 rounded-xl transition-all active:scale-95 text-sm ${
        pending ? "opacity-60 cursor-not-allowed" : ""
      }`}
    >
      {pending ? pendingLabel : label}
    </button>
  );
}
