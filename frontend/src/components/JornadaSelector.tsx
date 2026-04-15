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

  // Build the full list: null = "Actual" (current), then each historical week
  const allOptions: (number | null)[] = [null, ...weeks];
  const currentIndex = allOptions.indexOf(selected);
  const isFirst = currentIndex <= 0;
  const isLast = currentIndex >= allOptions.length - 1;

  const goBack = () => {
    if (isFirst) return;
    onChange(allOptions[currentIndex - 1]);
  };

  const goForward = () => {
    if (isLast) return;
    onChange(allOptions[currentIndex + 1]);
  };

  const label = selected === null ? "Actual" : String(selected);

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        background: "#161616",
        border: "1px solid #2a2a2a",
        borderRadius: "8px",
        overflow: "hidden",
        height: "32px",
      }}
    >
      {/* Left chevron */}
      <button
        onClick={goBack}
        disabled={isFirst}
        style={{
          width: "28px",
          height: "32px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "transparent",
          border: "none",
          cursor: isFirst ? "default" : "pointer",
          padding: 0,
          opacity: isFirst ? 0.3 : 1,
          flexShrink: 0,
        }}
        aria-label="Jornada anterior"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M9 11L5 7L9 3" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Divider */}
      <div style={{ width: "1px", height: "18px", background: "#2a2a2a", flexShrink: 0 }} />

      {/* Label */}
      <span
        style={{
          fontFamily: "'Barlow Condensed', sans-serif",
          fontSize: "13px",
          fontWeight: 600,
          color: "#ffffff",
          letterSpacing: "0.04em",
          minWidth: "48px",
          textAlign: "center",
          padding: "0 8px",
          userSelect: "none",
          lineHeight: 1,
        }}
      >
        {label}
      </span>

      {/* Divider */}
      <div style={{ width: "1px", height: "18px", background: "#2a2a2a", flexShrink: 0 }} />

      {/* Right chevron */}
      <button
        onClick={goForward}
        disabled={isLast}
        style={{
          width: "28px",
          height: "32px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "transparent",
          border: "none",
          cursor: isLast ? "default" : "pointer",
          padding: 0,
          opacity: isLast ? 0.3 : 1,
          flexShrink: 0,
        }}
        aria-label="Jornada siguiente"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M5 3L9 7L5 11" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  );
}
