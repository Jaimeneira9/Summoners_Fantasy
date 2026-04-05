"use client";

export function LoadingSkeleton() {
  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0A" }}>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px 96px" }}>
        <div style={{ height: 14, width: 120, borderRadius: 6, background: "#1A1A1A", marginBottom: 24 }} />
        <div style={{ height: 140, borderRadius: 12, background: "#111", marginBottom: 12 }} />
        <div style={{ height: 40, borderRadius: 8, background: "#111", marginBottom: 12 }} />
        <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} style={{ flex: 1, height: 90, borderRadius: 10, background: "#111" }} />
          ))}
        </div>
        <div style={{ display: "flex", gap: 20 }}>
          <div style={{ flex: 1.4, height: 260, borderRadius: 12, background: "#111" }} />
          <div style={{ flex: 1, height: 260, borderRadius: 12, background: "#111" }} />
        </div>
      </div>
    </div>
  );
}
