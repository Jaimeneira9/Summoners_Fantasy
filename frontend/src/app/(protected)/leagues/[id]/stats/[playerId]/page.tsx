"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, type PlayerSplitHistory, type Split, type UpcomingMatch, type ClauseInfo, type GameDetailStat } from "@/lib/api";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP);

import type { PlayerHistoryResponse, WeekStat } from "./_components/types";
import { LoadingSkeleton } from "./_components/LoadingSkeleton";
import { UpcomingSchedule } from "./_components/UpcomingSchedule";
import { SellPanel } from "./_components/SellPanel";
import { ClausePanel } from "./_components/ClausePanel";
import { OfferPanel } from "./_components/OfferPanel";
import { PlayerHero } from "./_components/PlayerHero";
import { WeekSelector } from "./_components/WeekSelector";
import { StatCards } from "./_components/StatCards";
import { BarChart } from "./_components/BarChart";
import { MatchHistoryList } from "./_components/MatchHistoryList";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PLAYER_PHOTO_BASE =
  "https://kjtifrtuknxtuuiyflza.supabase.co/storage/v1/object/public/FotosJugadoresLec/";


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPlayerPhotoUrl(name: string): string {
  return `${PLAYER_PHOTO_BASE}${name.toLowerCase().replace(/ /g, "-")}.webp`;
}

function calcKDA(kills: number, deaths: number, assists: number): string {
  if (deaths === 0) return "PERFECT";
  return ((kills + assists) / deaths).toFixed(2);
}

function barWidth(value: number, max: number): number {
  return Math.min(Math.max((value / max) * 100, 0), 100);
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PlayerStatsPage() {
  const { id: leagueId, playerId } = useParams<{ id: string; playerId: string }>();
  const searchParams = useSearchParams();
  const fromScout = searchParams.get("from") === "scout";

  const chartRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<PlayerHistoryResponse | null>(null);
  const [, setSplitHistory] = useState<PlayerSplitHistory[]>([]);
  const [splits, setSplits] = useState<Split[]>([]);
  const [selectedSplitId, setSelectedSplitId] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [schedule, setSchedule] = useState<UpcomingMatch[] | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(true);
  const [clauseInfo, setClauseInfo] = useState<ClauseInfo | null>(null);
  const [forSale, setForSale] = useState<boolean>(false);
  const [expandedSeriesId, setExpandedSeriesId] = useState<string | null>(null);
  const [gamesCache, setGamesCache] = useState<Map<string, GameDetailStat[]>>(new Map());
  const [gamesLoading, setGamesLoading] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      api.scoring.playerHistory(playerId),
      api.splits.playerHistory(playerId),
      api.splits.list(),
    ])
      .then(([history, splitHistory, splitList]) => {
        if (cancelled) return;
        const h = history as PlayerHistoryResponse;
        setHistoryData(h);
        setSplitHistory(splitHistory as PlayerSplitHistory[]);
        const availableSplits = splitList as Split[];
        setSplits(availableSplits);

        // Por defecto mostrar el split activo, con fallback al primero de la lista
        const activeSplit = availableSplits.find(s => s.is_active) ?? availableSplits[0] ?? null;
        const defaultSplitId = activeSplit?.id ?? null;
        setSelectedSplitId(defaultSplitId);

        // Default to last week del split seleccionado por defecto
        const defaultStats = defaultSplitId
          ? h.stats.filter(s => s.competition_id === defaultSplitId)
          : h.stats;
        if (defaultStats.length > 0) {
          setSelectedWeek(defaultStats.length);
        } else if (h.stats.length > 0) {
          setSelectedWeek(h.stats.length);
        }
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [playerId]);

  // Independent schedule fetch — does not block hero render
  useEffect(() => {
    setScheduleLoading(true);
    api.players.schedule(playerId)
      .then((data) => setSchedule(data.upcoming))
      .catch(() => setSchedule([]))
      .finally(() => setScheduleLoading(false));
  }, [playerId]);

  // Independent clause fetch — silent failure if endpoint not yet available
  useEffect(() => {
    if (!leagueId) return;
    api.clause.info(leagueId, playerId).then((info) => {
      setClauseInfo(info);
      setForSale(info.for_sale ?? false);
    }).catch(() => {});
  }, [leagueId, playerId]);

  // ---------------------------------------------------------------------------
  // Derived values
  // ---------------------------------------------------------------------------

  const player = historyData?.player ?? null;
  // matchStats filtrados por split seleccionado, con 1-based week index
  const matchStats: WeekStat[] = (historyData?.stats ?? [])
    .filter(s => !selectedSplitId || s.competition_id === selectedSplitId)
    .sort((a, b) => new Date(a.matches?.scheduled_at ?? 0).getTime() - new Date(b.matches?.scheduled_at ?? 0).getTime())
    .map((s, i) => ({ ...s, week: i + 1 }));
  const totalPoints = matchStats.reduce((sum, s) => sum + (s.fantasy_points ?? 0), 0);

  const lastMatchPts = matchStats.length > 0 ? matchStats[matchStats.length - 1].fantasy_points : 0;

  const photoUrl = player ? (player.image_url ?? getPlayerPhotoUrl(player.name)) : "";

  // Selected stat for zona 3
  const selectedStat = matchStats.find((s) => s.week === selectedWeek) ?? null;

  // Computed per-game stats for zona 3
  const statCards = selectedStat
    ? [
        {
          label: "KDA",
          value: calcKDA(selectedStat.kills, selectedStat.deaths, selectedStat.assists),
          barPct: selectedStat.deaths === 0 ? null : (() => {
            const kda = (selectedStat.kills + selectedStat.assists) / selectedStat.deaths;
            return kda >= 5 ? 80 : barWidth(kda, 10);
          })(),
          deathColor: selectedStat.deaths === 0 ? "#FCD400" : undefined,
        },
        {
          label: "Kills",
          value: String(selectedStat.kills),
          barPct: barWidth(selectedStat.kills, 10),
          breakdownKey: "kills",
        },
        {
          label: "Deaths",
          value: String(selectedStat.deaths),
          barPct: Math.max(0, 100 - (selectedStat.deaths / 10) * 100),
          deathColor: selectedStat.deaths <= 2 ? "#4CAF50" : selectedStat.deaths >= 5 ? "#EF5350" : "#FFF",
          breakdownKey: "deaths",
        },
        {
          label: "Assists",
          value: String(selectedStat.assists),
          barPct: barWidth(selectedStat.assists, 15),
          breakdownKey: "assists",
        },
        {
          label: "CS/min",
          value: selectedStat.cs_per_min != null ? selectedStat.cs_per_min.toFixed(1) : "—",
          barPct: selectedStat.cs_per_min != null ? barWidth(selectedStat.cs_per_min, 10) : null,
          breakdownKey: "cs_per_min",
        },
        {
          label: "Daño/min",
          value: selectedStat.dpm != null ? String(Math.round(selectedStat.dpm)) : "—",
          barPct: selectedStat.dpm != null ? barWidth(selectedStat.dpm, 1200) : null,
          breakdownKey: "dpm",
        },
        {
          label: "XP @15",
          value: selectedStat.xp_diff_at_15 != null
            ? (selectedStat.xp_diff_at_15 >= 0 ? `+${Math.round(selectedStat.xp_diff_at_15)}` : String(Math.round(selectedStat.xp_diff_at_15)))
            : "—",
          barPct: selectedStat.xp_diff_at_15 != null
            ? Math.min(Math.max(50 + (selectedStat.xp_diff_at_15 / 2000) * 50, 0), 100)
            : null,
          deathColor: selectedStat.xp_diff_at_15 != null
            ? (selectedStat.xp_diff_at_15 > 0 ? "#4ade80" : selectedStat.xp_diff_at_15 < 0 ? "#f87171" : "#888888")
            : undefined,
          breakdownKey: "xp_diff_15",
        },
        {
          label: "Gold @15",
          value: selectedStat.gold_diff_at_15 != null
            ? (selectedStat.gold_diff_at_15 >= 0 ? `+${Math.round(selectedStat.gold_diff_at_15)}` : String(Math.round(selectedStat.gold_diff_at_15)))
            : "—",
          barPct: selectedStat.gold_diff_at_15 != null
            ? Math.min(Math.max(50 + (selectedStat.gold_diff_at_15 / 2000) * 50, 0), 100)
            : null,
          deathColor: selectedStat.gold_diff_at_15 != null
            ? (selectedStat.gold_diff_at_15 > 0 ? "#4ade80" : selectedStat.gold_diff_at_15 < 0 ? "#f87171" : "#888888")
            : undefined,
          breakdownKey: "gold_diff_15",
        },
      ]
    : null;

  // Bar chart max
  const maxPts = Math.max(...matchStats.map((s) => s.fantasy_points), 1);

  // ---------------------------------------------------------------------------
  // GSAP: animación del gráfico de barras
  // ---------------------------------------------------------------------------

  useGSAP(() => {
    if (matchStats.length === 0) return;
    gsap.from(".bar-item", {
      scaleY: 0,
      transformOrigin: "bottom center",
      duration: 0.6,
      ease: "power3.out",
      stagger: 0.04,
    });
    gsap.from(".bar-label", {
      autoAlpha: 0,
      y: 8,
      duration: 0.4,
      delay: 0.3,
      stagger: 0.04,
    });
  }, { scope: chartRef, dependencies: [selectedSplitId, matchStats.length] });

  // ---------------------------------------------------------------------------
  // Loading / error states
  // ---------------------------------------------------------------------------

  if (loading) return <LoadingSkeleton />;

  if (error || !player) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0A0A0A" }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ color: "rgba(255,255,255,0.3)", fontSize: 14, marginBottom: 12 }}>
            {error ?? "Jugador no encontrado"}
          </p>
          <Link
            href={`/leagues/${leagueId}/lineup`}
            style={{ color: "#FCD400", fontSize: 12, textDecoration: "underline" }}
          >
            Volver al lineup
          </Link>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div style={{ minHeight: "100dvh", background: "#0A0A0A", color: "#fff", overflowX: "hidden" }}>
      <main style={{ maxWidth: 900, margin: "0 auto", padding: "16px 16px 96px" }}>

        {/* Breadcrumb */}
        <nav style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#444", marginBottom: 20 }}>
          <Link
            href={fromScout ? `/leagues/${leagueId}/market?tab=scout` : `/leagues/${leagueId}/lineup`}
            style={{ color: "#555", textDecoration: "none" }}
          >
            {fromScout ? "Explorar" : "Mi Equipo"}
          </Link>
          <span>›</span>
          <span style={{ color: "#888" }}>Stats de Jugador</span>
        </nav>

        {/* ================================================================ */}
        {/* ZONA 1: Player Hero                                              */}
        {/* ================================================================ */}
        <PlayerHero
          player={player}
          totalPoints={totalPoints}
          lastMatchPts={lastMatchPts}
          photoUrl={photoUrl}
          imgError={imgError}
          onImgError={() => setImgError(true)}
        />

        {/* ================================================================ */}
        {/* UPCOMING SCHEDULE: between hero and week selector               */}
        {/* ================================================================ */}
        <UpcomingSchedule
          matches={schedule}
          loading={scheduleLoading}
          role={player.role}
          leagueId={leagueId}
        />

        {/* ================================================================ */}
        {/* SELL PANEL: shown only when owned_by_me                         */}
        {/* ================================================================ */}
        {clauseInfo?.owned_by_me === true && clauseInfo.roster_player_id && (
          <SellPanel
            leagueId={leagueId}
            rosterPlayerId={clauseInfo.roster_player_id}
            forSale={forSale}
            onToggle={setForSale}
          />
        )}

        {/* ================================================================ */}
        {/* CLAUSE PANEL: below hero zone                                    */}
        {/* ================================================================ */}
        {clauseInfo && (
          <ClausePanel
            info={clauseInfo}
            leagueId={leagueId}
            player={player}
            onActivated={() => {
              // Refetch clause info after upgrade
              api.clause.info(leagueId, playerId).then((info) => {
                setClauseInfo(info);
                setForSale(info.for_sale ?? false);
              }).catch(() => {});
            }}
          />
        )}

        {/* ================================================================ */}
        {/* OFFER PANEL: shown when player is owned by someone else + for_sale */}
        {/* ================================================================ */}
        {clauseInfo &&
          clauseInfo.is_owned &&
          !clauseInfo.owned_by_me &&
          forSale === true &&
          clauseInfo.roster_player_id && (
            <OfferPanel
              leagueId={leagueId}
              rosterPlayerId={clauseInfo.roster_player_id}
            />
          )}

        {/* ================================================================ */}
        {/* ZONA 2: Selector de jornada                                      */}
        {/* ================================================================ */}
        {matchStats.length > 0 && (
          <WeekSelector
            matchStats={matchStats}
            selectedWeek={selectedWeek}
            onSelectWeek={setSelectedWeek}
            player={player}
          />
        )}

        {/* ================================================================ */}
        {/* ZONA 3: Stat cards de la jornada seleccionada                    */}
        {/* ================================================================ */}
        {statCards && selectedStat && (
          <StatCards
            statCards={statCards}
            selectedStat={selectedStat}
          />
        )}

        {/* ================================================================ */}
        {/* ZONA 4: Dos columnas                                             */}
        {/* ================================================================ */}
        <div className="flex flex-col sm:flex-row gap-5">

          {/* Col izquierda: Selector de splits + Bar chart */}
          <BarChart
            ref={chartRef}
            matchStats={matchStats}
            selectedWeek={selectedWeek}
            selectedSplitId={selectedSplitId}
            splits={splits}
            maxPts={maxPts}
            historyDataStats={historyData?.stats ?? []}
            onSelectWeek={setSelectedWeek}
            onSelectSplit={(splitId, newWeek) => {
              setSelectedSplitId(splitId);
              setSelectedWeek(newWeek);
            }}
          />

          {/* Col derecha: Historial de jornadas */}
          <MatchHistoryList
            matchStats={matchStats}
            selectedWeek={selectedWeek}
            expandedSeriesId={expandedSeriesId}
            gamesCache={gamesCache}
            gamesLoading={gamesLoading}
            player={player}
            playerId={playerId}
            onSelectWeek={setSelectedWeek}
            onGamesLoaded={(seriesId, games) => {
              setGamesCache((prev) => {
                const next = new Map(prev);
                next.set(seriesId, games);
                return next;
              });
            }}
            onGamesLoadingChange={setGamesLoading}
            onExpandedSeriesIdChange={setExpandedSeriesId}
          />

        </div>

      </main>
    </div>
  );
}
