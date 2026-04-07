"use client";

import { useState } from "react";
import type { MatchDetailPlayed, MatchDetailUpcoming } from "@/types/match-detail";
import { MatchHeader } from "./MatchHeader";
import { GameTabBar } from "./GameTabBar";
import { SeriesView } from "./SeriesView";
import { GameView } from "./GameView";
import { UpcomingView } from "./UpcomingView";

export type MatchDetailProps =
  | { mode: "played"; data: MatchDetailPlayed; leagueId: string }
  | { mode: "upcoming"; data: MatchDetailUpcoming; leagueId: string };

export function MatchDetail(props: MatchDetailProps) {
  const [selectedTab, setSelectedTab] = useState<"series" | number>("series");

  if (props.mode === "upcoming") {
    const { data } = props;
    return (
      <div className="min-h-screen bg-[#0a0a0a]">
        <MatchHeader
          teamHome={data.team_home}
          teamAway={data.team_away}
          mode="upcoming"
          scheduledAt={data.scheduled_at}
        />
        <UpcomingView data={data} />
      </div>
    );
  }

  // played mode
  const { data } = props;
  const currentGame =
    typeof selectedTab === "number"
      ? data.games.find((g) => g.game_number === selectedTab) ?? null
      : null;

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
      <MatchHeader
        teamHome={data.team_home}
        teamAway={data.team_away}
        mode="played"
      />
      <GameTabBar
        games={data.games}
        selected={selectedTab}
        onChange={setSelectedTab}
      />
      {selectedTab === "series" ? (
        <SeriesView data={data} />
      ) : currentGame ? (
        <GameView
          game={currentGame}
          teamHome={data.team_home}
          teamAway={data.team_away}
        />
      ) : null}
    </div>
  );
}
