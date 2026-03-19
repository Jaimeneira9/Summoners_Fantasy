import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";

export default async function LeagueLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <div className="flex h-screen bg-[#faf9f6] overflow-hidden">
      <Sidebar leagueId={params.id} />
      <main className="flex-1 overflow-y-auto">
        {children}
        <BottomNav leagueId={params.id} />
      </main>
    </div>
  );
}
