"use client";

export function JornadaSelector({
  weeks,
  selected,
  onChange,
}: {
  weeks: number[];
  selected: number | null;
  onChange: (w: number | null) => void;
}) {
  if (weeks.length === 0) return null;

  return (
    <div style={{
      display: "flex",
      overflowX: "auto",
      flexWrap: "nowrap",
      gap: 6,
      paddingBottom: 4,
      scrollbarWidth: "none",
      msOverflowStyle: "none",
      WebkitOverflowScrolling: "touch",
    } as React.CSSProperties}>
      {/* "Actual" chip */}
      <button
        onClick={() => onChange(null)}
        style={{
          background: selected === null ? "#FCD400" : "#1A1A1A",
          border: `1px solid ${selected === null ? "#FCD400" : "#2A2A2A"}`,
          borderRadius: 8,
          padding: "6px 14px",
          color: selected === null ? "#000" : "#777",
          fontSize: 12,
          fontWeight: selected === null ? 700 : 500,
          cursor: "pointer",
          fontFamily: "'Barlow Condensed', sans-serif",
          letterSpacing: "0.04em",
          flexShrink: 0,
          whiteSpace: "nowrap",
        }}
      >
        Actual
      </button>

      {weeks.map((w) => {
        const isActive = selected === w;
        return (
          <button
            key={w}
            onClick={() => onChange(w)}
            style={{
              background: isActive ? "#FCD400" : "#1A1A1A",
              border: `1px solid ${isActive ? "#FCD400" : "#2A2A2A"}`,
              borderRadius: 8,
              padding: "6px 14px",
              color: isActive ? "#000" : "#777",
              fontSize: 12,
              fontWeight: isActive ? 700 : 500,
              cursor: "pointer",
              fontFamily: "'Barlow Condensed', sans-serif",
              letterSpacing: "0.04em",
              flexShrink: 0,
              whiteSpace: "nowrap",
            }}
          >
            Jornada {w}
          </button>
        );
      })}
    </div>
  );
}
