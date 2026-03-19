export default function DashboardLoading() {
  return (
    <div className="min-h-screen bg-[#050508]">
      {/* Header skeleton */}
      <div className="border-b border-[rgba(255,255,255,0.06)] px-6 py-4 flex items-center justify-between">
        <div className="h-5 w-28 bg-[#12121c] rounded animate-pulse" />
        <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
      </div>

      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Hero skeleton */}
        <div className="mb-10 space-y-2">
          <div className="h-3 w-32 bg-[#12121c] rounded animate-pulse" />
          <div className="h-9 w-48 bg-[#1a1a28] rounded animate-pulse" />
          <div className="h-3 w-64 bg-[#12121c] rounded animate-pulse" />
        </div>

        <div className="flex items-center justify-between mb-6">
          <div className="h-5 w-24 bg-[#1a1a28] rounded animate-pulse" />
          <div className="h-8 w-28 bg-[#1a1a28] rounded animate-pulse" />
        </div>

        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl p-5 h-28 animate-pulse"
              style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
