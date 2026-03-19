export default function ActivityLoading() {
  return (
    <div className="min-h-screen bg-[#050508] text-[#f1f5f9]">
      {/* Header skeleton */}
      <div className="border-b border-[rgba(255,255,255,0.06)] px-4 sm:px-6 py-4 flex items-center gap-3">
        <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
        <div className="h-4 w-20 bg-[#12121c] rounded animate-pulse" />
        <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
        <div className="ml-auto flex gap-3">
          <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
          <div className="h-4 w-16 bg-[#12121c] rounded animate-pulse" />
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="h-6 w-40 bg-[#1a1a28] rounded mb-6 animate-pulse" />
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-16 bg-[#0d0d14] border border-[rgba(255,255,255,0.06)] rounded-xl animate-pulse"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
