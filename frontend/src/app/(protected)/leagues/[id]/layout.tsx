"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";

gsap.registerPlugin(useGSAP);

export default function LeagueLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  const contentRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      gsap.from(contentRef.current, {
        autoAlpha: 0,
        y: 16,
        duration: 0.4,
        ease: "power2.out",
      });
    },
    { scope: contentRef }
  );

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar leagueId={params.id} />
      <main className="flex-1 overflow-y-auto">
        <div ref={contentRef}>
          {children}
        </div>
        <BottomNav leagueId={params.id} />
      </main>
    </div>
  );
}
