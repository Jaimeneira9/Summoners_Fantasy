"use client";

import { useRef, useEffect, useState } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import Sidebar from "@/components/Sidebar";
import BottomNav from "@/components/BottomNav";
import { api } from "@/lib/api";

gsap.registerPlugin(useGSAP);

const STARTER_SLOT_KEYS = ["starter_1", "starter_2", "starter_3", "starter_4", "starter_5"];

export default function LeagueLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [hasIncompleteRoster, setHasIncompleteRoster] = useState(false);

  useEffect(() => {
    api.roster.get(params.id).then((roster) => {
      const filledCount = roster.players.filter((p) => STARTER_SLOT_KEYS.includes(p.slot)).length;
      setHasIncompleteRoster(filledCount < 5);
    }).catch(() => {
      // silently ignore — no indicator shown if fetch fails
    });
  }, [params.id]);

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
    <div className="flex h-[100dvh] bg-background overflow-hidden">
      <Sidebar leagueId={params.id} hasIncompleteRoster={hasIncompleteRoster} />
      <main className="flex-1 overflow-y-auto">
        <div ref={contentRef}>
          {children}
        </div>
        <BottomNav leagueId={params.id} hasIncompleteRoster={hasIncompleteRoster} />
      </main>
    </div>
  );
}
