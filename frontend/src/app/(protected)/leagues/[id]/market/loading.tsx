export default function MarketLoading() {
  return (
    <div className="min-h-screen bg-[#050508] text-[#f1f5f9]">
      {/* Header skeleton */}
      <div className="border-b border-[rgba(255,255,255,0.06)] px-4 sm:px-6 py-4 flex items-center gap-3">
        <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
        <div className="h-4 w-24 bg-[#12121c] rounded animate-pulse" />
        <div className="ml-auto flex gap-3">
          <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
          <div className="h-4 w-12 bg-[#12121c] rounded animate-pulse" />
        </div>
      </div>
      {/* Tabs skeleton */}
      <div className="border-b border-[rgba(255,255,255,0.06)] px-4 sm:px-6 flex gap-4 py-1">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-8 w-20 bg-[#12121c] rounded animate-pulse my-1" />
        ))}
      </div>
      {/* Cards grid skeleton */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="rounded-xl overflow-hidden border border-[rgba(255,255,255,0.06)] animate-pulse">
              <div className="w-full aspect-[3/4] bg-[#12121c]" />
              <div className="p-3 space-y-2 bg-[#0d0d14]">
                <div className="h-3.5 bg-[#1a1a28] rounded w-3/4" />
                <div className="h-3 bg-[#1a1a28] rounded w-1/2" />
                <div className="h-7 bg-[#1a1a28] rounded mt-2" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
