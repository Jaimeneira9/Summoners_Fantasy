"use client";

import type { PlayerMatchStat } from "@/lib/api";

export type PlayerHistoryResponse = {
  player: {
    id: string;
    name: string;
    team: string;
    role: string;
    image_url: string | null;
    current_price: number;
  };
  stats: PlayerMatchStat[];
  total_points: number;
};

export type WeekStat = PlayerMatchStat & { week: number };
