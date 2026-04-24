"use client";

import { useState } from "react";
import { LeagueModal } from "@/components/LeagueModal";

type ModalMode = "create" | "join";

export function LeagueActions() {
  const [isOpen, setIsOpen] = useState(false);
  const [initialMode, setInitialMode] = useState<ModalMode>("create");

  const open = (mode: ModalMode) => {
    setInitialMode(mode);
    setIsOpen(true);
  };

  return (
    <>
      <div className="flex gap-2">
        <button
          onClick={() => open("create")}
          className="px-4 py-2 text-sm font-bold rounded-lg transition-all active:scale-95 hover:brightness-90"
          style={{ background: "var(--color-primary)", color: "#111111" }}
        >
          Crear liga
        </button>
        <button
          onClick={() => open("join")}
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

      <LeagueModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        initialMode={initialMode}
      />
    </>
  );
}
