const BASE = (import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export const DEFAULT_TEAM_ID = Number(import.meta.env.PUBLIC_DEFAULT_TEAM_ID ?? 121);

export interface TeamSide {
  team_id: number | null;
  name: string;
  abbr: string | null;
  record: string | null;
  hits?: number | null;
  errors?: number | null;
  lob?: number | null;
  runs: number;
}

export interface Breakdown {
  game: {
    game_id: number;
    game_date: string | null;
    won: boolean;
    innings: number | null;
    venue: string | null;
    attendance: number | null;
    temp: number | null;
    conditions: string | null;
    team: TeamSide & { side: 'home' | 'away' };
    opponent: TeamSide;
    prev_game_id: number | null;
    next_game_id: number | null;
  };
  points: {
    total: number;
    player_points: number;
    team_points: number;
    carry_in: number;
    carry_out: number;
    opponent_total: number | null;
    margin: number | null;
    season_avg: number;
    season_rank: number;
    season_games: number;
    carry_reason: string | null;
    avg_li: number | null;
    peak_li: number | null;
    peak_li_inning: string | null;
    peak_li_player: string | null;
  };
  categories: {
    key: 'basic' | 'situational' | 'miracles' | 'deductions' | 'carry_over';
    label: string;
    points: number;
    events: number;
    stat: string;
    top_rule: string | null;
    top_rule_points: number | null;
  }[];
  batters: {
    mlb_id: number;
    name: string;
    position: string;
    pa: number;
    basic: number;
    situational: number;
    deductions: number;
    net: number;
    grade: number;
    has_miracle: boolean;
  }[];
  pitchers: {
    mlb_id: number;
    name: string;
    decision: string;
    ip: string | null;
    er: number;
    so: number;
    pitches: number;
    bb: number;
    situational: number;
    highlight: string | null;
    net: number;
    grade: number;
  }[];
  play_log: {
    at_bat_index: number;
    inning: number;
    half: 'Top' | 'Bot';
    outs: number;
    score: string;
    description: string;
    highlights: string[];
    category: string;
    category_keys: string[];
    impact: number;
    count: string | null;
    li: number | null;
    detail: string | null;
  }[];
  batter_summary: string;
  pitcher_summary: string;
  scored_events: number;
}

export interface GameListItem {
  game_id: number;
  team_id: number;
  game_date: string | null;
  team_name: string | null;
  team_abbr: string | null;
  opponent: string | null;
  opponent_abbr: string | null;
  home_away: 'home' | 'away' | null;
  won: boolean;
  runs_for: number;
  runs_against: number;
  player_points: number;
  team_points: number;
  carry_in: number;
  carry_out: number;
  total_points: number;
}

export interface TeamListItem {
  team_id: number;
  team_name: string;
  games: number;
  wins: number;
  total_points: number;
  avg_points: number;
}

export interface SeasonTrendMonth {
  month: string;
  games: number;
  wins: number;
  base_points: number;
  situational_points: number;
  miracle_carry_points: number;
  penalty_points: number;
  total_points: number;
}

export interface SeasonCarryLedgerItem {
  game_id: number;
  game_date: string | null;
  opponent: string | null;
  home_away: 'home' | 'away' | null;
  runs_for: number;
  runs_against: number;
  carry_points: number;
  trigger: string;
  next_game: {
    game_id: number;
    game_date: string | null;
    won: boolean;
    runs_for: number;
    runs_against: number;
    total_points: number;
  } | null;
}

export interface SeasonTrends {
  games: GameListItem[];
  months: SeasonTrendMonth[];
  carry_ledger: SeasonCarryLedgerItem[];
}

async function get<T>(path: string): Promise<T | null> {
  const res = await fetch(`${BASE}${path}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const getBreakdown = (gameId: number, teamId: number) =>
  get<Breakdown>(`/games/${gameId}/breakdown?team_id=${teamId}`);

export const getGames = (teamId: number, season?: number, limit = 200) =>
  get<GameListItem[]>(`/games?team_id=${teamId}&limit=${limit}${season ? `&season=${season}` : ''}`);

export const getSeasons = () => get<number[]>('/seasons');

export const getTeams = (season?: number) =>
  get<TeamListItem[]>(`/teams${season ? `?season=${season}` : ''}`);

export const getSeasonTrends = (teamId: number, season?: number, split = 'all') =>
  get<SeasonTrends>(
    `/teams/${teamId}/season-trends?split=${encodeURIComponent(split)}${season ? `&season=${season}` : ''}`,
  );

export interface OutlierGame extends GameListItem {
  headline: string | null;
  headline_url: string | null;
  run_diff: number;
  points_percentile: number;
  verdict: string;
}

export interface Outliers {
  games: number;
  wins: number;
  correlation_run_diff: number | null;
  correlation_win: number | null;
  quartiles: { label: string; games: number; wins: number; win_pct: number }[];
  hidden_gems: OutlierGame[];
  smoke_and_mirrors: OutlierGame[];
}

export const getOutliers = (teamId: number, season?: number, limit = 5) =>
  get<Outliers>(`/insights/outliers?team_id=${teamId}&limit=${limit}${season ? `&season=${season}` : ''}`);

export interface Moment {
  id: number;
  moment_date: string;
  team_id: number | null;
  game_id: number | null;
  type: string;
  headline: string;
  source_url: string | null;
  note: string | null;
}

export const getMoments = (teamId: number, season?: number) =>
  get<Moment[]>(`/moments?team_id=${teamId}${season ? `&season=${season}` : ''}`);

export interface BuzzGame extends GameListItem {
  news_count: number;
  outlets: number;
  buzz_percentile: number;
  points_percentile: number;
  headline: string | null;
  headline_url: string | null;
}

export interface Buzz {
  games: number;
  covered_games: number;
  correlation_points: number | null;
  correlation_abs_run_diff: number | null;
  avg_news_wins: number | null;
  avg_news_losses: number | null;
  most_covered: BuzzGame[];
  quiet_standouts: BuzzGame[];
}

export const getBuzz = (teamId: number, season?: number, limit = 8) =>
  get<Buzz>(`/insights/buzz?team_id=${teamId}&limit=${limit}${season ? `&season=${season}` : ''}`);

export interface BuzzPin {
  game_id: number;
  team_id: number;
  game_date: string;
  news_count: number;
  outlets: number;
  headline: string | null;
  headline_url: string | null;
}

export const getBuzzPins = (teamId: number, season?: number, limit = 8) =>
  get<BuzzPin[]>(`/teams/${teamId}/buzz-pins?limit=${limit}${season ? `&season=${season}` : ''}`);

export interface MediaItem {
  id: number;
  game_id: number;
  team_id: number;
  source: string;
  kind: 'recap' | 'highlight' | 'news';
  title: string;
  url: string;
  publisher: string | null;
  published_at: string | null;
}

export const getGameMedia = (gameId: number, teamId: number) =>
  get<MediaItem[]>(`/games/${gameId}/media?team_id=${teamId}`);

export const fmtPts = (n: number, digits = 1) => `${n > 0 ? '+' : ''}${n.toFixed(digits)}`;

export const tone = (n: number) => (n > 0 ? 'pos' : n < 0 ? 'neg' : 'zero');

export const gradeClass = (g: number) =>
  g >= 90 ? 'g-elite' : g >= 70 ? 'g-above' : g >= 40 ? 'g-avg' : g >= 20 ? 'g-below' : 'g-poor';

export const fmtDate = (iso: string | null) =>
  iso
    ? new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : '';

export const ordinal = (n: number) => {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`;
};
