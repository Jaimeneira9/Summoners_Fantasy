import Link from "next/link";

export default function ConfirmEmailPage() {
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

      {/* Icon */}
      <div className="mb-8 flex justify-center lg:justify-start">
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center"
          style={{ background: "rgba(252,212,0,0.1)", border: "1px solid rgba(252,212,0,0.2)" }}
        >
          <span className="material-symbols-outlined text-4xl" style={{ color: "#FCD400" }}>
            mark_email_unread
          </span>
        </div>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1
          className="font-black text-3xl uppercase tracking-tight mb-3"
          style={{ color: "#F0E8D0", fontFamily: "'Space Grotesk', sans-serif" }}
        >
          Revisá tu email
        </h1>
        <p className="text-sm leading-relaxed mb-4" style={{ color: "#888888" }}>
          Te enviamos un link de confirmación. Hacé click en el link para activar tu cuenta.
        </p>
        <p className="text-xs" style={{ color: "#555555" }}>
          ¿No llegó? Revisá la carpeta de spam.
        </p>
      </div>

      {/* Back to login */}
      <Link
        href="/login"
        className="text-sm font-semibold hover:underline"
        style={{ color: "#FCD400" }}
      >
        ← Volver al login
      </Link>
    </div>
  );
}
