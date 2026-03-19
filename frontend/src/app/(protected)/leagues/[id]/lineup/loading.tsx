export default function LineupLoading() {
  return (
    <div className="min-h-screen bg-[#050508] text-[#f1f5f9]">
      {/* Header skeleton */}
      <div className="border-b border-[rgba(255,255,255,0.06)] px-4 sm:px-6 py-4 flex items-center gap-3">
        <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
        <div className="h-4 w-20 bg-[#12121c] rounded animate-pulse" />
        <div className="ml-auto flex gap-3">
          <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
          <div className="h-4 w-12 bg-[#12121c] rounded animate-pulse" />
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Starters section */}
        <div>
          <div className="h-3 w-16 bg-[#1a1a28] rounded mb-3 animate-pulse" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] bg-[#0d0d14] border border-[rgba(255,255,255,0.06)] rounded-xl animate-pulse" />
            ))}
          </div>
        </div>

        {/* Coach section */}
        <div>
          <div className="h-3 w-20 bg-[#1a1a28] rounded mb-3 animate-pulse" />
          <div className="max-w-xs aspect-[3/4] bg-[#0d0d14] border border-[rgba(255,255,255,0.06)] rounded-xl animate-pulse" />
        </div>

        {/* Bench section */}
        <div>
          <div className="h-3 w-16 bg-[#1a1a28] rounded mb-3 animate-pulse" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] bg-[#0d0d14] border border-[rgba(255,255,255,0.06)] rounded-xl animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
