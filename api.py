"""
Read-only JSON API over the points database.

Run:  uvicorn api:app --reload      (docs at /docs)
Env:  POINTS_DB      path to the SQLite file (default new_york_mets/points.db)
      CORS_ORIGINS   comma separated allowed origins (default http://localhost:4321, Astro's dev server)
"""
import bisect
import json
import os
import sqlite3
from typing import Iterator, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import storage

DB_PATH = os.environ.get(
    'POINTS_DB',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'new_york_mets', 'points.db'),
)
CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', 'http://localhost:4321').split(',') if o.strip()]

app = FastAPI(title='Baseball Point System API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=['GET'], allow_headers=['*'])

# Make sure the schema exists so an empty database returns empty lists instead of errors
storage.connect(DB_PATH).close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class Team(BaseModel):
    team_id: int
    team_name: str
    games: int
    wins: int
    total_points: float
    avg_points: float


class Game(BaseModel):
    game_id: int
    team_id: int
    game_date: Optional[str]
    team_name: Optional[str]
    opponent: Optional[str]
    team_abbr: Optional[str] = None
    opponent_abbr: Optional[str] = None
    home_away: Optional[str]
    won: bool
    runs_for: int
    runs_against: int
    player_points: float
    team_points: float
    carry_in: float
    carry_out: float
    total_points: float


class PointEvent(BaseModel):
    scope: str
    mlb_id: Optional[int]
    player_name: Optional[str]
    category: Optional[str]
    rule: Optional[str]
    value: Optional[str]
    points: float


class CategoryTotal(BaseModel):
    category: str
    points: float


class GameDetail(BaseModel):
    game: Game
    categories: list[CategoryTotal]
    players: list['PlayerGameTotal']
    events: list[PointEvent]


class PlayerGameTotal(BaseModel):
    mlb_id: int
    player_name: str
    points: float


class PlayerSeason(BaseModel):
    mlb_id: int
    player_name: str
    team_id: int
    games: int
    total_points: float
    points_per_game: float


class TrendPoint(BaseModel):
    game_id: int
    game_date: Optional[str]
    opponent: Optional[str]
    won: bool
    total_points: float
    rolling_avg: float


GameDetail.model_rebuild()


def _game_filters(team_id, season, start, end):
    clauses, params = [], []
    if team_id is not None:
        clauses.append('team_id = ?')
        params.append(team_id)
    if season is not None:
        clauses.append("substr(game_date, 1, 4) = ?")
        params.append(str(season))
    if start:
        clauses.append('game_date >= ?')
        params.append(start)
    if end:
        clauses.append('game_date <= ?')
        params.append(end)
    return (' WHERE ' + ' AND '.join(clauses)) if clauses else '', params


def _to_game(row: sqlite3.Row) -> Game:
    data = dict(row)
    data['won'] = bool(data['won'])
    return Game(**data)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/seasons', response_model=list[int])
def list_seasons(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        'SELECT DISTINCT CAST(substr(game_date, 1, 4) AS INTEGER) AS season FROM games ORDER BY season DESC'
    ).fetchall()
    return [r['season'] for r in rows]


@app.get('/teams', response_model=list[Team])
def list_teams(season: Optional[int] = None, db: sqlite3.Connection = Depends(get_db)):
    where, params = _game_filters(None, season, None, None)
    rows = db.execute(
        f'SELECT team_id, MAX(team_name) AS team_name, COUNT(*) AS games, SUM(won) AS wins, '
        f'SUM(total_points) AS total_points, AVG(total_points) AS avg_points '
        f'FROM games{where} GROUP BY team_id ORDER BY avg_points DESC',
        params,
    ).fetchall()
    return [Team(**dict(r)) for r in rows]


@app.get('/games', response_model=list[Game])
def list_games(
    team_id: Optional[int] = None,
    season: Optional[int] = None,
    start: Optional[str] = Query(None, description='YYYY-MM-DD'),
    end: Optional[str] = Query(None, description='YYYY-MM-DD'),
    sort: str = Query('date', pattern='^(date|points)$'),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    where, params = _game_filters(team_id, season, start, end)
    order = 'game_date DESC, game_id DESC' if sort == 'date' else 'total_points DESC'
    rows = db.execute(
        f'SELECT * FROM games{where} ORDER BY {order} LIMIT ? OFFSET ?',
        params + [limit, offset],
    ).fetchall()
    return [_to_game(r) for r in rows]


@app.get('/games/{game_id}', response_model=GameDetail)
def get_game(game_id: int, team_id: int, db: sqlite3.Connection = Depends(get_db)):
    """A game is scored once per team, so team_id selects which side's breakdown to return."""
    game = db.execute('SELECT * FROM games WHERE game_id = ? AND team_id = ?', (game_id, team_id)).fetchone()
    if game is None:
        raise HTTPException(status_code=404, detail='Game not found for that team')

    events = db.execute(
        'SELECT scope, mlb_id, player_name, category, rule, value, points FROM point_events '
        'WHERE game_id = ? AND team_id = ? ORDER BY points DESC',
        (game_id, team_id),
    ).fetchall()
    categories = db.execute(
        'SELECT category, SUM(points) AS points FROM point_events WHERE game_id = ? AND team_id = ? '
        'GROUP BY category ORDER BY points DESC',
        (game_id, team_id),
    ).fetchall()
    players = db.execute(
        "SELECT mlb_id, player_name, SUM(points) AS points FROM point_events "
        "WHERE game_id = ? AND team_id = ? AND scope = 'player' GROUP BY mlb_id, player_name "
        "ORDER BY points DESC",
        (game_id, team_id),
    ).fetchall()

    return GameDetail(
        game=_to_game(game),
        categories=[CategoryTotal(**dict(r)) for r in categories],
        players=[PlayerGameTotal(**dict(r)) for r in players],
        events=[PointEvent(**dict(r)) for r in events],
    )


class OutlierGame(Game):
    headline: Optional[str] = None
    headline_url: Optional[str] = None
    run_diff: int
    points_percentile: int
    verdict: str


class QuartileRow(BaseModel):
    label: str
    games: int
    wins: int
    win_pct: float


class Outliers(BaseModel):
    games: int
    wins: int
    correlation_run_diff: Optional[float]
    correlation_win: Optional[float]
    quartiles: list[QuartileRow]
    hidden_gems: list[OutlierGame]
    smoke_and_mirrors: list[OutlierGame]


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


class BuzzGame(Game):
    news_count: int
    outlets: int
    buzz_percentile: int
    points_percentile: int
    headline: Optional[str] = None
    headline_url: Optional[str] = None


class Buzz(BaseModel):
    games: int
    covered_games: int
    correlation_points: Optional[float]
    correlation_abs_run_diff: Optional[float]
    avg_news_wins: Optional[float]
    avg_news_losses: Optional[float]
    most_covered: list[BuzzGame]
    quiet_standouts: list[BuzzGame]


class BuzzPin(BaseModel):
    game_id: int
    team_id: int
    game_date: str
    news_count: int
    outlets: int
    headline: Optional[str]
    headline_url: Optional[str]


@app.get('/teams/{team_id}/buzz-pins', response_model=list[BuzzPin])
def buzz_pins(
    team_id: int,
    season: Optional[int] = None,
    limit: int = Query(8, ge=1, le=30),
    db: sqlite3.Connection = Depends(get_db),
):
    """The most covered games of a season (one per date), for automatic pins on the timeline."""
    where, params = _game_filters(team_id, season, None, None)
    rows = db.execute(
        f'SELECT g.game_id, g.team_id, g.game_date, b.news_count, b.publishers AS outlets '
        f'FROM (SELECT * FROM games{where}) g JOIN game_buzz b ON b.game_id = g.game_id AND b.team_id = g.team_id '
        'ORDER BY b.news_count DESC, g.game_date',
        params,
    ).fetchall()
    pins, seen = [], set()
    for r in rows:
        if r['game_date'] in seen:
            continue
        seen.add(r['game_date'])
        media = db.execute(
            "SELECT title, url FROM media_items WHERE game_id = ? AND team_id = ? "
            "ORDER BY CASE kind WHEN 'news' THEN 0 WHEN 'recap' THEN 1 ELSE 2 END, published_at DESC LIMIT 1",
            (r['game_id'], r['team_id']),
        ).fetchone()
        pins.append(BuzzPin(**dict(r), headline=media['title'] if media else None,
                            headline_url=media['url'] if media else None))
        if len(pins) >= limit:
            break
    return sorted(pins, key=lambda p: p.game_date)


@app.get('/insights/buzz', response_model=Buzz)
def buzz(
    team_id: int,
    season: Optional[int] = None,
    limit: int = Query(8, ge=1, le=25),
    db: sqlite3.Connection = Depends(get_db),
):
    """Compares how much media coverage each game got (see media.py) with how many points it scored."""
    where, params = _game_filters(team_id, season, None, None)
    rows = db.execute(
        f'SELECT g.*, b.news_count, b.publishers AS outlets FROM (SELECT * FROM games{where}) g '
        'JOIN game_buzz b ON b.game_id = g.game_id AND b.team_id = g.team_id',
        params,
    ).fetchall()
    total_games = db.execute(f'SELECT COUNT(*) FROM games{where}', params).fetchone()[0]
    if not rows:
        raise HTTPException(404, 'No media collected for these games yet')

    news_sorted = sorted(r['news_count'] for r in rows)
    points_sorted = sorted(r['total_points'] for r in rows)
    n = len(rows)

    def pct(values: list, value: float) -> int:
        return round(100 * bisect.bisect_left(values, value) / max(n - 1, 1))

    def headline(game_id: int):
        return db.execute(
            "SELECT title, url FROM media_items WHERE game_id = ? AND team_id = ? "
            "ORDER BY CASE kind WHEN 'recap' THEN 0 WHEN 'news' THEN 1 ELSE 2 END, published_at DESC LIMIT 1",
            (game_id, team_id),
        ).fetchone()

    def build(r: sqlite3.Row) -> BuzzGame:
        data = dict(r)
        news, outlets = data.pop('news_count'), data.pop('outlets')
        game = Game(**{**data, 'won': bool(data['won'])})
        h = headline(game.game_id)
        return BuzzGame(
            **game.model_dump(), news_count=news, outlets=outlets,
            buzz_percentile=pct(news_sorted, news), points_percentile=pct(points_sorted, game.total_points),
            headline=h['title'] if h else None, headline_url=h['url'] if h else None,
        )

    news = [float(r['news_count']) for r in rows]
    won = [r for r in rows if r['won']]
    lost = [r for r in rows if not r['won']]
    by_news = sorted(rows, key=lambda r: (-r['news_count'], -r['total_points']))
    # high points, little coverage: the best games nobody wrote about
    quiet = sorted(
        (r for r in rows if r['news_count'] <= news_sorted[n // 4]),
        key=lambda r: -r['total_points'],
    )
    return Buzz(
        games=total_games,
        covered_games=n,
        correlation_points=_round_or_none(_pearson(news, [r['total_points'] for r in rows])),
        correlation_abs_run_diff=_round_or_none(
            _pearson(news, [float(abs(r['runs_for'] - r['runs_against'])) for r in rows])),
        avg_news_wins=round(sum(r['news_count'] for r in won) / len(won), 1) if won else None,
        avg_news_losses=round(sum(r['news_count'] for r in lost) / len(lost), 1) if lost else None,
        most_covered=[build(r) for r in by_news[:limit]],
        quiet_standouts=[build(r) for r in quiet[:limit]],
    )


@app.get('/insights/outliers', response_model=Outliers)
def outliers(
    team_id: int,
    season: Optional[int] = None,
    limit: int = Query(5, ge=1, le=25),
    db: sqlite3.Connection = Depends(get_db),
):
    """Games where the points disagree with the final score: losses that scored
    high (hidden gems) and wins that scored low (smoke and mirrors)."""
    where, params = _game_filters(team_id, season, None, None)
    rows = db.execute(f'SELECT * FROM games{where}', params).fetchall()
    games = [_to_game(r) for r in rows]
    if not games:
        raise HTTPException(404, 'No games found')

    totals = sorted(g.total_points for g in games)
    n = len(totals)

    def percentile(points: float) -> int:
        return round(100 * bisect.bisect_left(totals, points) / max(n - 1, 1))

    diffs = [float(g.runs_for - g.runs_against) for g in games]
    points = [g.total_points for g in games]
    wins_flag = [1.0 if g.won else 0.0 for g in games]

    ranked = sorted(games, key=lambda g: g.total_points)
    quartiles = []
    for i, label in enumerate(['Bottom 25%', '25-50%', '50-75%', 'Top 25%']):
        chunk = ranked[i * n // 4:(i + 1) * n // 4]
        wins = sum(1 for g in chunk if g.won)
        quartiles.append(QuartileRow(
            label=label, games=len(chunk), wins=wins,
            win_pct=round(100 * wins / len(chunk), 1) if chunk else 0.0,
        ))

    def build(g: Game, verdict: str) -> OutlierGame:
        media = db.execute(
            "SELECT title, url FROM media_items WHERE game_id = ? AND team_id = ? "
            "ORDER BY CASE kind WHEN 'recap' THEN 0 WHEN 'news' THEN 1 ELSE 2 END, published_at DESC LIMIT 1",
            (g.game_id, g.team_id),
        ).fetchone()
        return OutlierGame(
            **g.model_dump(), headline=media['title'] if media else None,
            headline_url=media['url'] if media else None, run_diff=g.runs_for - g.runs_against,
            points_percentile=percentile(g.total_points), verdict=verdict,
        )

    losses = sorted((g for g in games if not g.won), key=lambda g: -g.total_points)
    wins = sorted((g for g in games if g.won), key=lambda g: g.total_points)
    return Outliers(
        games=n,
        wins=sum(1 for g in games if g.won),
        correlation_run_diff=_round_or_none(_pearson(points, diffs)),
        correlation_win=_round_or_none(_pearson(points, wins_flag)),
        quartiles=quartiles,
        hidden_gems=[build(g, 'Played well, lost anyway') for g in losses[:limit]],
        smoke_and_mirrors=[build(g, 'Won, but did not play well') for g in wins[:limit]],
    )


def _round_or_none(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 3)


class Moment(BaseModel):
    id: int
    moment_date: str
    team_id: Optional[int]
    game_id: Optional[int]
    type: str
    headline: str
    source_url: Optional[str]
    note: Optional[str]


@app.get('/moments', response_model=list[Moment])
def list_moments(
    team_id: Optional[int] = None,
    season: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """Off-field moments (media, culture, transactions) for the timeline. Moments with no team apply to every team."""
    clauses, params = [], []
    if team_id is not None:
        clauses.append('(team_id IS NULL OR team_id = ?)')
        params.append(team_id)
    if season is not None:
        clauses.append('substr(moment_date, 1, 4) = ?')
        params.append(str(season))
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    rows = db.execute(f'SELECT * FROM moments{where} ORDER BY moment_date, id', params).fetchall()
    return [Moment(**dict(r)) for r in rows]


class MediaItem(BaseModel):
    id: int
    game_id: int
    team_id: int
    source: str
    kind: str
    title: str
    url: str
    publisher: Optional[str]
    published_at: Optional[str]


@app.get('/games/{game_id}/media', response_model=list[MediaItem])
def game_media(game_id: int, team_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Recap, highlights and news headlines collected for one game (see media.py)."""
    rows = db.execute(
        "SELECT id, game_id, team_id, source, kind, title, url, publisher, published_at FROM media_items "
        "WHERE game_id = ? AND team_id = ? "
        "ORDER BY CASE kind WHEN 'recap' THEN 0 WHEN 'news' THEN 1 ELSE 2 END, published_at DESC, id",
        (game_id, team_id),
    ).fetchall()
    return [MediaItem(**dict(r)) for r in rows]


@app.get('/search')
def search(
    q: str = Query(..., min_length=2, max_length=60),
    team_id: Optional[int] = None,
    limit: int = Query(6, ge=1, le=20),
    db: sqlite3.Connection = Depends(get_db),
):
    """Quick search over players (by name) and games (by opponent, team or date)."""
    like = f'%{q.strip()}%'
    team_clause, team_params = ('', [])
    if team_id is not None:
        team_clause, team_params = ' AND team_id = ?', [team_id]

    players = db.execute(
        'SELECT p.mlb_id, p.name, p.team_id, COUNT(*) AS games, '
        'MAX(g.game_date) AS last_date, '
        '(SELECT p2.game_id FROM game_players p2 JOIN games g3 ON g3.game_id = p2.game_id AND g3.team_id = p2.team_id '
        'WHERE p2.mlb_id = p.mlb_id AND p2.team_id = p.team_id ORDER BY g3.game_date DESC LIMIT 1) AS last_game_id '
        'FROM game_players p JOIN games g ON g.game_id = p.game_id AND g.team_id = p.team_id '
        f'WHERE p.name LIKE ?{team_clause.replace("team_id", "p.team_id")} '
        'GROUP BY p.mlb_id, p.team_id ORDER BY games DESC LIMIT ?',
        [like] + team_params + [limit],
    ).fetchall()
    games = db.execute(
        'SELECT game_id, team_id, game_date, team_name, opponent, home_away, runs_for, runs_against, total_points '
        f'FROM games WHERE (opponent LIKE ? OR team_name LIKE ? OR game_date LIKE ?){team_clause} '
        'ORDER BY game_date DESC LIMIT ?',
        [like, like, like] + team_params + [limit],
    ).fetchall()
    return {'players': [dict(r) for r in players], 'games': [dict(r) for r in games]}


@app.get('/players', response_model=list[PlayerSeason])
def list_players(
    team_id: Optional[int] = None,
    season: Optional[int] = None,
    min_games: int = Query(1, ge=1),
    sort: str = Query('total', pattern='^(total|per_game)$'),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    clauses, params = ["e.scope = 'player'"], []
    if team_id is not None:
        clauses.append('e.team_id = ?')
        params.append(team_id)
    if season is not None:
        clauses.append('substr(g.game_date, 1, 4) = ?')
        params.append(str(season))
    order = 'total_points DESC' if sort == 'total' else 'points_per_game DESC'
    rows = db.execute(
        'SELECT e.mlb_id, MAX(e.player_name) AS player_name, e.team_id, '
        'COUNT(DISTINCT e.game_id) AS games, SUM(e.points) AS total_points, '
        'SUM(e.points) * 1.0 / COUNT(DISTINCT e.game_id) AS points_per_game '
        'FROM point_events e JOIN games g ON g.game_id = e.game_id AND g.team_id = e.team_id '
        f"WHERE {' AND '.join(clauses)} GROUP BY e.mlb_id, e.team_id "
        f'HAVING games >= ? ORDER BY {order} LIMIT ? OFFSET ?',
        params + [min_games, limit, offset],
    ).fetchall()
    return [PlayerSeason(**dict(r)) for r in rows]


@app.get('/teams/{team_id}/trend', response_model=list[TrendPoint])
def team_trend(
    team_id: int,
    season: Optional[int] = None,
    window: int = Query(10, ge=1, le=162, description='rolling average size in games'),
    db: sqlite3.Connection = Depends(get_db),
):
    where, params = _game_filters(team_id, season, None, None)
    rows = db.execute(
        f'SELECT game_id, game_date, opponent, won, total_points FROM games{where} ORDER BY game_date, game_id',
        params,
    ).fetchall()

    points, trend = [], []
    for r in rows:
        points.append(r['total_points'])
        recent = points[-window:]
        trend.append(TrendPoint(
            game_id=r['game_id'], game_date=r['game_date'], opponent=r['opponent'],
            won=bool(r['won']), total_points=r['total_points'], rolling_avg=sum(recent) / len(recent),
        ))
    return trend


@app.get('/teams/{team_id}/season-trends')
def team_season_trends(
    team_id: int,
    season: Optional[int] = None,
    split: str = Query('all', pattern='^(all|high-leverage|carry-only|home-only)$'),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return filtered game points, monthly scoring components and carry-over sequels."""
    where, params = _game_filters(team_id, season, None, None)
    game_rows = db.execute(
        f'SELECT * FROM games{where} ORDER BY game_date, game_id',
        params,
    ).fetchall()
    games = [dict(row) for row in game_rows]

    if split == 'home-only':
        games = [game for game in games if game['home_away'] == 'home']
    elif split == 'carry-only':
        games = [game for game in games if (game['carry_in'] or 0) != 0 or (game['carry_out'] or 0) != 0]
    elif split == 'high-leverage':
        leverage_rows = db.execute(
            'SELECT e.game_id, SUM(e.points) AS total_points, '
            "SUM(CASE WHEN e.scope = 'player' THEN e.points ELSE 0 END) AS player_points, "
            "SUM(CASE WHEN e.scope = 'team' THEN e.points ELSE 0 END) AS team_points "
            'FROM point_events e JOIN play_context p ON p.game_id = e.game_id AND p.at_bat_index = e.at_bat_index '
            'JOIN games g ON g.game_id = e.game_id AND g.team_id = e.team_id '
            f'WHERE e.team_id = ? AND p.leverage_index > 1.8{(" AND substr(g.game_date, 1, 4) = ?" if season is not None else "")} '
            'GROUP BY e.game_id',
            [team_id] + ([str(season)] if season is not None else []),
        ).fetchall()
        leverage_by_game = {row['game_id']: dict(row) for row in leverage_rows}
        games = [
            {
                **game,
                'total_points': leverage_by_game[game['game_id']]['total_points'] or 0,
                'player_points': leverage_by_game[game['game_id']]['player_points'] or 0,
                'team_points': leverage_by_game[game['game_id']]['team_points'] or 0,
            }
            for game in games
            if game['game_id'] in leverage_by_game
        ]

    selected_ids = [game['game_id'] for game in games]
    months = {}
    for row in games:
        month_key = row['game_date'][:7] if row['game_date'] else 'Unknown'
        month = months.setdefault(month_key, {
            'month': month_key,
            'games': 0,
            'wins': 0,
            'base_points': 0.0,
            'situational_points': 0.0,
            'miracle_carry_points': 0.0,
            'penalty_points': 0.0,
            'total_points': 0.0,
        })
        month['games'] += 1
        month['wins'] += int(bool(row['won']))
        month['total_points'] += row['total_points'] or 0.0

    if selected_ids:
        id_clause = ','.join('?' for _ in selected_ids)
        event_join = (
            'JOIN play_context p ON p.game_id = e.game_id AND p.at_bat_index = e.at_bat_index '
            if split == 'high-leverage' else ''
        )
        leverage_filter = ' AND p.leverage_index > 1.8' if split == 'high-leverage' else ''
        event_rows = db.execute(
            'SELECT substr(g.game_date, 1, 7) AS month, e.category, SUM(e.points) AS points '
            f'FROM point_events e {event_join}JOIN games g ON g.game_id = e.game_id AND g.team_id = e.team_id '
            f'WHERE e.team_id = ? AND e.game_id IN ({id_clause}){leverage_filter} '
            'GROUP BY month, e.category',
            [team_id] + selected_ids,
        ).fetchall()
        for row in event_rows:
            month = months.get(row['month'])
            if month is None:
                continue
            category = row['category']
            if category in ('Basic Stats', 'Pitching'):
                month['base_points'] += row['points'] or 0.0
            elif category in ('Situational', 'Defense'):
                month['situational_points'] += row['points'] or 0.0
            elif category in ('Unusual', 'Carry Over'):
                month['miracle_carry_points'] += row['points'] or 0.0
            elif category == 'Deduction':
                month['penalty_points'] += row['points'] or 0.0

    carry_ledger = []
    for row in games:
        if (row['carry_out'] or 0) == 0:
            continue
        next_game = db.execute(
            'SELECT game_id, game_date, won, runs_for, runs_against, total_points '
            'FROM games WHERE team_id = ? AND (game_date > ? OR (game_date = ? AND game_id > ?)) '
            'ORDER BY game_date, game_id LIMIT 1',
            (team_id, row['game_date'], row['game_date'], row['game_id']),
        ).fetchone()
        trigger = db.execute(
            "SELECT GROUP_CONCAT(DISTINCT rule) AS rules FROM point_events "
            "WHERE team_id = ? AND game_id = ? AND category = 'Carry Over'",
            (team_id, row['game_id']),
        ).fetchone()
        carry_ledger.append({
            'game_id': row['game_id'],
            'game_date': row['game_date'],
            'opponent': row['opponent'],
            'home_away': row['home_away'],
            'runs_for': row['runs_for'],
            'runs_against': row['runs_against'],
            'carry_points': row['carry_out'],
            'trigger': trigger['rules'] if trigger and trigger['rules'] else 'Rule V carry-over trigger',
            'next_game': dict(next_game) if next_game else None,
        })

    return {
        'games': games,
        'months': [months[key] for key in sorted(months)],
        'carry_ledger': carry_ledger,
    }


# ---------------------------------------------------------------------------
# Game breakdown (everything the Game Breakdown screen needs in one request)
# ---------------------------------------------------------------------------

CATEGORY_GROUPS = [
    ('basic', 'I. Basic Stats', 'I', {'Basic Stats', 'Pitching'}),
    ('situational', 'II. Situational', 'II', {'Situational', 'Defense'}),
    ('miracles', 'III. Miracles', 'III', {'Unusual'}),
    ('deductions', 'IV. Deductions', 'IV', {'Deduction'}),
    ('carry_over', 'V. Carry-Over', 'V', {'Carry Over'}),
]
GROUP_BY_CATEGORY = {cat: g for g in CATEGORY_GROUPS for cat in g[3]}


class Opponent(BaseModel):
    team_id: Optional[int]
    name: str
    abbr: Optional[str]
    record: Optional[str]
    runs: int
    hits: Optional[int] = None
    errors: Optional[int] = None
    lob: Optional[int] = None


class BreakdownTeam(Opponent):
    side: str


class BreakdownGame(BaseModel):
    game_id: int
    game_date: Optional[str]
    won: bool
    innings: Optional[int]
    venue: Optional[str]
    attendance: Optional[int]
    temp: Optional[int]
    conditions: Optional[str]
    team: BreakdownTeam
    opponent: Opponent
    prev_game_id: Optional[int]
    next_game_id: Optional[int]


class BreakdownPoints(BaseModel):
    total: float
    player_points: float
    team_points: float
    carry_in: float
    carry_out: float
    opponent_total: Optional[float]
    margin: Optional[float]
    season_avg: float = 0.0
    season_rank: int = 1
    season_games: int = 1
    carry_reason: Optional[str] = None
    avg_li: Optional[float] = None
    peak_li: Optional[float] = None
    peak_li_inning: Optional[str] = None
    peak_li_player: Optional[str] = None


class CategoryCard(BaseModel):
    key: str
    label: str
    points: float
    events: int
    stat: str = ''
    top_rule: Optional[str]
    top_rule_points: Optional[float]


class BatterRow(BaseModel):
    mlb_id: int
    name: str
    position: str
    pa: int
    basic: float
    situational: float
    deductions: float
    net: float
    grade: int
    has_miracle: bool = False


class PitcherRow(BaseModel):
    mlb_id: int
    name: str
    decision: str
    ip: Optional[str]
    er: int
    so: int
    pitches: int
    bb: int = 0
    situational: float = 0.0
    highlight: Optional[str] = None
    net: float
    grade: int


class PlayLogRow(BaseModel):
    at_bat_index: int
    inning: int
    half: str
    outs: int
    score: str
    description: str
    highlights: list[str]
    category: str
    category_keys: list[str]
    impact: float
    count: Optional[str] = None
    li: Optional[float] = None
    detail: Optional[str] = None


def _context_fields(c):
    if c is None:
        return {}
    parts = []
    if c['launch_speed']:
        parts.append(f"{c['launch_speed']:.1f} mph EV")
    if c['launch_angle'] is not None and c['launch_speed']:
        parts.append(f"{c['launch_angle']:.0f}° LA")
    if c['distance']:
        parts.append(f"{c['distance']:.0f} ft")
    if c['pitch_speed'] and c['pitch_type']:
        parts.append(f"{c['pitch_speed']:.1f} mph {c['pitch_type']}")
    return {
        'count': f"{c['balls']}-{c['strikes']}" if c['balls'] is not None else None,
        'li': c['leverage_index'], 'detail': ' • '.join(parts) or None,
    }


class Breakdown(BaseModel):
    game: BreakdownGame
    points: BreakdownPoints
    categories: list[CategoryCard]
    batters: list[BatterRow]
    pitchers: list[PitcherRow]
    play_log: list[PlayLogRow]
    batter_summary: str
    pitcher_summary: str
    scored_events: int


def _ordinal(n: int) -> str:
    suffix = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def _grades(db: sqlite3.Connection, pitchers: bool) -> list[float]:
    """Sorted per-game point totals for every batter (or pitcher) in the database, used for percentile grades."""
    role = 'gp.pit_json != \'null\'' if pitchers else 'gp.batting_order IS NOT NULL'
    rows = db.execute(
        'SELECT COALESCE(SUM(e.points), 0) AS net FROM game_players gp '
        'LEFT JOIN point_events e ON e.game_id = gp.game_id AND e.team_id = gp.team_id '
        "AND e.mlb_id = gp.mlb_id AND e.scope = 'player' "
        f'WHERE {role} GROUP BY gp.game_id, gp.team_id, gp.mlb_id'
    ).fetchall()
    return sorted(r['net'] for r in rows)


def _percentile(sorted_values: list[float], value: float) -> int:
    if not sorted_values:
        return 50
    below = bisect.bisect_left(sorted_values, value)
    equal = bisect.bisect_right(sorted_values, value) - below
    return max(1, min(99, round(100 * (below + equal / 2) / len(sorted_values))))


@app.get('/games/{game_id}/breakdown', response_model=Breakdown)
def game_breakdown(game_id: int, team_id: int, db: sqlite3.Connection = Depends(get_db)):
    g = db.execute('SELECT * FROM games WHERE game_id = ? AND team_id = ?', (game_id, team_id)).fetchone()
    if g is None:
        raise HTTPException(status_code=404, detail='Game not found for that team')

    events = db.execute(
        'SELECT * FROM point_events WHERE game_id = ? AND team_id = ? ORDER BY rowid', (game_id, team_id)
    ).fetchall()
    players = db.execute(
        'SELECT * FROM game_players WHERE game_id = ? AND team_id = ? ORDER BY rowid', (game_id, team_id)
    ).fetchall()

    opp = db.execute(
        'SELECT total_points FROM games WHERE game_id = ? AND team_id = ?', (game_id, g['opponent_id'])
    ).fetchone()
    opponent_total = opp['total_points'] if opp else None

    season = (g['game_date'] or '')[:4]
    season_totals = [r['total_points'] for r in db.execute(
        'SELECT total_points FROM games WHERE team_id = ? AND substr(game_date, 1, 4) = ?', (team_id, season)
    ).fetchall()]
    season_avg = sum(season_totals) / len(season_totals) if season_totals else g['total_points']
    season_rank = 1 + sum(1 for t in season_totals if t > g['total_points'])
    carry_row = db.execute(
        "SELECT rule FROM point_events WHERE game_id = ? AND team_id = ? AND category = 'Carry Over' ORDER BY points DESC LIMIT 1",
        (game_id, team_id),
    ).fetchone()

    nav = {}
    for key, op, order in (('prev', '<', 'DESC'), ('next', '>', 'ASC')):
        row = db.execute(
            f'SELECT game_id FROM games WHERE team_id = ? AND (game_date {op} ? OR (game_date = ? AND game_id {op} ?)) '
            f'ORDER BY game_date {order}, game_id {order} LIMIT 1',
            (team_id, g['game_date'], g['game_date'], game_id),
        ).fetchone()
        nav[key] = row['game_id'] if row else None

    # Category cards
    bat_stats = [json.loads(p['bat_json']) for p in players if p['batting_order'] is not None and p['bat_json']]
    pit_stats = [json.loads(p['pit_json']) for p in players if p['pit_json'] and p['pit_json'] != 'null']
    sum_of = lambda rows, k: sum((r.get(k) or 0) for r in rows)
    card_stat = {
        'basic': f"{sum_of(bat_stats, 'r')} R / {sum_of(bat_stats, 'h')} H",
        'deductions': f"{sum_of(bat_stats, 'k')} K / {sum_of(pit_stats, 'bb')} BB / {g['team_e'] or 0} E",
    }
    cards = []
    for key, label, _, members in CATEGORY_GROUPS:
        group = [e for e in events if e['category'] in members]
        scoring = [e for e in group if e['points'] != 0]
        top = max(scoring, key=lambda e: abs(e['points']), default=None)
        rule_counts: dict[str, int] = {}
        for e in scoring:
            rule_counts[e['rule']] = rule_counts.get(e['rule'], 0) + 1
        common = max(rule_counts.items(), key=lambda kv: kv[1], default=None)
        stat = card_stat.get(key) or (
            f'{common[0]} ×{common[1]}' if common and key == 'situational'
            else f'{len(scoring)} {"event" if len(scoring) == 1 else "events"}' if scoring else 'None'
        )
        cards.append(CategoryCard(
            key=key, label=label, points=sum(e['points'] for e in group), events=len(scoring), stat=stat,
            top_rule=top['rule'] if top else None, top_rule_points=top['points'] if top else None,
        ))

    # Per-player point buckets
    per_player: dict[int, dict[str, float]] = {}
    miracle_ids: set[int] = set()
    top_event: dict[int, tuple[str, float]] = {}
    for e in events:
        if e['scope'] != 'player' or e['mlb_id'] is None:
            continue
        bucket = per_player.setdefault(e['mlb_id'], {'basic': 0.0, 'situational': 0.0, 'deductions': 0.0})
        group_key = GROUP_BY_CATEGORY.get(e['category'], CATEGORY_GROUPS[0])[0]
        bucket['deductions' if group_key == 'deductions' else 'situational' if group_key in ('situational', 'miracles') else 'basic'] += e['points']
        if group_key == 'miracles':
            miracle_ids.add(e['mlb_id'])
        if group_key != 'basic' and (e['mlb_id'] not in top_event or abs(e['points']) > abs(top_event[e['mlb_id']][1])):
            top_event[e['mlb_id']] = (e['rule'], e['points'])

    batter_dist, pitcher_dist = _grades(db, False), _grades(db, True)
    batters, pitchers = [], []
    for p in players:
        b = per_player.get(p['mlb_id'], {'basic': 0.0, 'situational': 0.0, 'deductions': 0.0})
        net = b['basic'] + b['situational'] + b['deductions']
        if p['batting_order'] is not None:
            batters.append(BatterRow(
                mlb_id=p['mlb_id'], name=p['name'], position=p['position'] or '', pa=p['pa'] or 0,
                basic=b['basic'], situational=b['situational'], deductions=b['deductions'], net=net,
                grade=_percentile(batter_dist, net), has_miracle=p['mlb_id'] in miracle_ids,
            ))
        pit = json.loads(p['pit_json']) if p['pit_json'] else None
        if pit:
            pitchers.append(PitcherRow(
                mlb_id=p['mlb_id'], name=p['name'], decision=pit.get('decision', ''), ip=pit.get('ip'),
                er=pit.get('er', 0), so=pit.get('k', 0), pitches=pit.get('pitches', 0), bb=pit.get('bb', 0),
                situational=b['situational'] + b['deductions'],
                highlight=top_event[p['mlb_id']][0] if p['mlb_id'] in top_event else None, net=net,
                grade=_percentile(pitcher_dist, net),
            ))
    batters.sort(key=lambda r: r.net, reverse=True)

    # Play log: one row per play that produced points
    plays: dict[int, list[sqlite3.Row]] = {}
    for e in events:
        if e['at_bat_index'] is not None and e['points'] != 0:
            plays.setdefault(e['at_bat_index'], []).append(e)

    home_abbr = g['team_abbr'] if g['home_away'] == 'home' else g['opponent_abbr']
    away_abbr = g['opponent_abbr'] if g['home_away'] == 'home' else g['team_abbr']
    ctx = {r['at_bat_index']: r for r in db.execute(
        'SELECT * FROM play_context WHERE game_id = ?', (game_id,)).fetchall()}
    li_rows = [r for r in ctx.values() if r['leverage_index'] is not None]
    peak_ctx = max(li_rows, key=lambda r: r['leverage_index'], default=None)
    peak_inning = f"{'Top' if peak_ctx['is_top'] else 'Bot'} {peak_ctx['inning']}" if peak_ctx else None
    peak_player = peak_ctx['batter'] if peak_ctx else None
    play_log = []
    for index in sorted(plays):
        group = plays[index]
        first = group[0]
        keys = []
        for e in group:
            k = GROUP_BY_CATEGORY.get(e['category'], CATEGORY_GROUPS[0])
            if k[0] not in keys:
                keys.append(k[0])
        keys.sort(key=lambda k: [c[0] for c in CATEGORY_GROUPS].index(k))
        by_key = {c[0]: c for c in CATEGORY_GROUPS}
        label = (by_key[keys[0]][1].split('. ', 1)[1] if len(keys) == 1
                 else ' + '.join(by_key[k][2] for k in keys) + ' Blend')
        play_log.append(PlayLogRow(
            at_bat_index=index, inning=first['inning'], half='Top' if first['is_top'] else 'Bot', outs=first['outs'],
            score=f"{away_abbr} {first['away_score']} - {home_abbr} {first['home_score']}",
            description=first['description'] or '',
            highlights=[f"{e['rule']} ({e['points']:+.1f})" for e in group],
            category=label, category_keys=keys, impact=sum(e['points'] for e in group),
            **_context_fields(ctx.get(index)),
        ))

    bat_rows = [p for p in players if p['batting_order'] is not None]
    bat_json = [json.loads(p['bat_json']) for p in bat_rows if p['bat_json']]
    hits, runs = sum(b['h'] for b in bat_json), sum(b['r'] for b in bat_json)
    pit_json = [json.loads(p['pit_json']) for p in players if p['pit_json'] and p['pit_json'] != 'null']
    outs = sum(int(x['ip'].split('.')[0]) * 3 + int(x['ip'].split('.')[1]) for x in pit_json if x.get('ip'))
    ip_total = f'{outs // 3}.{outs % 3}'
    batter_total = sum(b.net for b in batters)
    pitcher_total = sum(p.net for p in pitchers)

    return Breakdown(
        game=BreakdownGame(
            game_id=game_id, game_date=g['game_date'], won=bool(g['won']), innings=g['innings'], venue=g['venue'],
            attendance=g['attendance'], temp=g['temp'], conditions=g['conditions'],
            team=BreakdownTeam(team_id=team_id, name=g['team_name'], abbr=g['team_abbr'], record=g['team_record'],
                               runs=g['runs_for'], hits=g['team_h'], errors=g['team_e'], lob=g['team_lob'], side=g['home_away']),
            opponent=Opponent(team_id=g['opponent_id'], name=g['opponent'], abbr=g['opponent_abbr'],
                              record=g['opponent_record'], runs=g['runs_against'],
                              hits=g['opp_h'], errors=g['opp_e'], lob=g['opp_lob']),
            prev_game_id=nav['prev'], next_game_id=nav['next'],
        ),
        points=BreakdownPoints(
            total=g['total_points'], player_points=g['player_points'], team_points=g['team_points'],
            carry_in=g['carry_in'], carry_out=g['carry_out'], opponent_total=opponent_total,
            margin=None if opponent_total is None else g['total_points'] - opponent_total,
            season_avg=season_avg, season_rank=season_rank, season_games=len(season_totals) or 1,
            carry_reason=carry_row['rule'] if carry_row else None,
            avg_li=sum(r['leverage_index'] for r in li_rows) / len(li_rows) if li_rows else None,
            peak_li=peak_ctx['leverage_index'] if peak_ctx else None,
            peak_li_inning=peak_inning, peak_li_player=peak_player,
        ),
        categories=cards, batters=batters, pitchers=pitchers, play_log=play_log,
        batter_summary=f'{hits} H · {runs} R · Net {batter_total:+.1f} bat pts',
        pitcher_summary=f'{ip_total} IP · {sum(x["k"] for x in pit_json)} SO · Net {pitcher_total:+.1f} pitch pts',
        scored_events=len(plays),
    )
