export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex bg-[#faf9f6]">
      {/* Columna izquierda — branding (solo desktop) */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#6b21e8] flex-col justify-between p-12 relative overflow-hidden">
        {/* Orbes decorativos */}
        <div className="absolute -top-20 -right-20 w-96 h-96 bg-white/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-20 -left-20 w-80 h-80 bg-white/5 rounded-full blur-3xl" />

        {/* Logo/branding */}
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
              <span className="material-symbols-outlined text-white text-xl">military_tech</span>
            </div>
            <span className="font-display font-black text-white text-xl tracking-tight uppercase">LOLFantasy</span>
          </div>
        </div>

        {/* Tagline */}
        <div className="relative z-10">
          <h2 className="font-display font-black text-white text-4xl leading-tight uppercase tracking-tight mb-4">
            CREA TU<br />EQUIPO<br />IDEAL
          </h2>
          <p className="text-white/60 text-sm font-body leading-relaxed">
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
