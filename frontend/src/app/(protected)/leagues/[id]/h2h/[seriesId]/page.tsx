"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { MatchDetail } from "@/components/match-detail";
import type { MatchDetailEnvelope } from "@/types/match-detail";

export default function H2HPage() {
  const params = useParams();
  const leagueId = params.id as string;
  const seriesId = params.seriesId as string;

  const [envelope, setEnvelope] = useState<MatchDetailEnvelope | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.series
      .matchDetail(seriesId, leagueId)
      .then(setEnvelope)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [seriesId, leagueId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#fcd400] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !envelope) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <p className="text-neutral-500 text-sm">
          {error ?? "No se pudo cargar el partido"}
        </p>
      </div>
    );
  }

  if (envelope.mode === "played") {
    return <MatchDetail mode="played" data={envelope.played!} leagueId={leagueId} />;
  }

  return <MatchDetail mode="upcoming" data={envelope.upcoming!} leagueId={leagueId} />;
}
