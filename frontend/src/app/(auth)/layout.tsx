export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex" style={{ background: "#0A0A0A" }}>
      {/* Columna izquierda — branding (solo desktop) */}
      <div
        className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: "#111111", borderRight: "1px solid #1E1E1E" }}
      >
        {/* Orbes decorativos */}
        <div className="absolute -top-20 -right-20 w-96 h-96 rounded-full blur-3xl" style={{ background: "rgba(252,212,0,0.04)" }} />
        <div className="absolute -bottom-20 -left-20 w-80 h-80 rounded-full blur-3xl" style={{ background: "rgba(252,212,0,0.04)" }} />

        {/* Logo/branding */}
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "#FCD400" }}
            >
              <span className="material-symbols-outlined text-xl" style={{ color: "#111111" }}>military_tech</span>
            </div>
            <span
              className="font-black text-xl tracking-tight uppercase"
              style={{ color: "#FCD400", fontFamily: "'Space Grotesk', sans-serif" }}
            >
              Summoner&apos;s Fantasy
            </span>
          </div>
        </div>

        {/* Tagline */}
        <div className="relative z-10">
          <h2
            className="font-black text-4xl leading-tight uppercase tracking-tight mb-4"
            style={{ color: "#F0E8D0", fontFamily: "'Space Grotesk', sans-serif" }}
          >
            CREA TU<br />EQUIPO<br />IDEAL
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "#555555" }}>
            Gestiona tu plantilla, compite en el mercado y sube en la clasificación de la LEC.
          </p>
        </div>
      </div>

      {/* Columna derecha — form */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        {children}
      </div>
    </div>
  );
}
