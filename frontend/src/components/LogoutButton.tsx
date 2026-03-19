"use client";

export function LogoutButton({ action }: { action: () => Promise<void> }) {
  return (
    <form action={action}>
      <button
        type="submit"
        className="text-sm rounded-lg px-3 py-1.5 transition-all"
        style={{
          border: "1px solid var(--border-medium)",
          color: "var(--text-secondary)",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-primary)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--color-primary)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border-medium)";
          (e.currentTarget as HTMLButtonElement).style.color = "var(--text-secondary)";
        }}
      >
        Salir
      </button>
    </form>
  );
}
