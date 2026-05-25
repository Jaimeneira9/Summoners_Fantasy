"use client";

/**
 * Página de listado de ligas del usuario.
 *
 * Muestra todas las ligas a las que pertenece el usuario autenticado.
 * Permite crear una nueva liga o unirse con código de invitación
 * a través del componente LeagueModal.
 *
 * Flujo:
 *   mount → api.leagues.list() → setLeagues
 *   Al cerrar el modal (creación/join exitoso) → reload automático via load()
 */

import { useEffect, useState } from "react";
import { api, type League } from "@/lib/api";
import { LeagueRow } from "@/components/LeagueRow";
import { LeagueModal } from "@/components/LeagueModal";

/** Modos disponibles del modal de liga. */
type ModalMode = "create" | "join";

/**
 * Página de "Mis ligas".
 * Lista las ligas del usuario, con acceso rápido para crear o unirse a una.
 * Si no hay ligas, muestra un EmptyState clickeable que abre el modal de creación.
 */
export default function LigasPage() {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>("create");

  /** Carga (o recarga) la lista de ligas del usuario. Se llama al montar y al cerrar el modal. */
  const load = () => {
    setLoading(true);
    api.leagues
      .list()
      .then(setLeagues)
      .catch(() => setLeagues([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  /** Abre el modal en el modo indicado ("create" por defecto). */
  const openModal = (mode: ModalMode = "create") => {
    setModalMode(mode);
    setModalOpen(true);
  };

  return (
    <div
      className="min-h-[100dvh]"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-8 pb-24 sm:py-8">
        {/* Page header */}
        <div className="flex items-center justify-between gap-4 flex-wrap mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Mis ligas</h1>
            {!loading && (
              <p className="text-sm text-gray-400 mt-0.5">
                {leagues.length === 0
                  ? "No estás en ninguna liga todavía"
                  : `${leagues.length} liga${leagues.length !== 1 ? "s" : ""} activa${leagues.length !== 1 ? "s" : ""}`}
              </p>
            )}
          </div>
          {/* Nueva liga button */}
          <button
            onClick={() => openModal("create")}
            className="px-4 py-2 text-sm font-bold rounded-lg bg-yellow-400 text-black hover:bg-yellow-300 transition-colors active:scale-95"
          >
            Nueva liga
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <LigasSkeleton />
        ) : leagues.length === 0 ? (
          <EmptyState onOpen={() => openModal("create")} />
        ) : (
          <div className="space-y-3">
            {leagues.map((league) => (
              <LeagueRow key={league.id} league={league} />
            ))}
          </div>
        )}
      </main>

      <LeagueModal
        isOpen={modalOpen}
        onClose={() => { setModalOpen(false); load(); }}
        initialMode={modalMode}
      />
    </div>
  );
}

/** Skeleton de carga: tres filas pulsantes mientras se obtienen las ligas. */
function LigasSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="h-24 rounded-xl animate-pulse"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        />
      ))}
    </div>
  );
}

/**
 * Estado vacío cuando el usuario no tiene ligas.
 * Es un botón completo (toda el área es clickeable) que abre el modal de creación.
 */
function EmptyState({ onOpen }: { onOpen?: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full rounded-xl border border-dashed border-white/20 hover:border-white/40 transition-colors duration-200 p-12 flex flex-col items-center gap-3 cursor-pointer group"
      style={{ background: "#0f0f1a" }}
    >
      <div className="w-12 h-12 rounded-full border-2 border-dashed border-white/20 group-hover:border-white/40 transition-colors flex items-center justify-center">
        <svg
          className="w-6 h-6 text-gray-500 group-hover:text-gray-300 transition-colors"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
      </div>
      <span className="text-sm text-gray-400 group-hover:text-gray-200 transition-colors font-medium">
        Crear o unirse a una liga
      </span>
    </button>
  );
}
