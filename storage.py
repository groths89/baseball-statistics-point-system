"""SQLite persistence for game results and their point breakdowns."""
import json
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    game_date TEXT,
    team_name TEXT,
    opponent TEXT,
    home_away TEXT,
    won INTEGER,
    runs_for INTEGER,
    runs_against INTEGER,
    player_points REAL,
    team_points REAL,
    carry_in REAL,
    carry_out REAL,
    total_points REAL,
    PRIMARY KEY (game_id, team_id)
);
CREATE TABLE IF NOT EXISTS point_events (
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    scope TEXT NOT NULL,
    mlb_id INTEGER,
    player_name TEXT,
    category TEXT,
    rule TEXT,
    value TEXT,
    points REAL
);
CREATE TABLE IF NOT EXISTS play_context (
    game_id INTEGER NOT NULL,
    at_bat_index INTEGER NOT NULL,
    balls INTEGER,
    strikes INTEGER,
    leverage_index REAL,
    wpa REAL,
    launch_speed REAL,
    launch_angle REAL,
    distance REAL,
    pitch_speed REAL,
    pitch_type TEXT,
    inning INTEGER,
    is_top INTEGER,
    batter TEXT,
    PRIMARY KEY (game_id, at_bat_index)
);
CREATE INDEX IF NOT EXISTS idx_point_events_game ON point_events (game_id, team_id);
CREATE TABLE IF NOT EXISTS game_players (
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    mlb_id INTEGER NOT NULL,
    name TEXT,
    position TEXT,
    batting_order INTEGER,
    pa INTEGER,
    bat_json TEXT,
    pit_json TEXT,
    PRIMARY KEY (game_id, team_id, mlb_id)
);
CREATE TABLE IF NOT EXISTS moments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    moment_date TEXT NOT NULL,
    team_id INTEGER,
    game_id INTEGER,
    type TEXT NOT NULL DEFAULT 'media',
    headline TEXT NOT NULL,
    source_url TEXT,
    note TEXT
);
CREATE TABLE IF NOT EXISTS game_buzz (
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    news_count INTEGER NOT NULL,
    publishers INTEGER NOT NULL,
    fetched_at TEXT,
    PRIMARY KEY (game_id, team_id)
);
CREATE TABLE IF NOT EXISTS media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    publisher TEXT,
    published_at TEXT,
    fetched_at TEXT,
    UNIQUE (game_id, team_id, url)
);
"""

# Columns added after the first version; applied to existing databases on connect
MIGRATIONS = {
    'games': [
        ('team_abbr', 'TEXT'), ('opponent_id', 'INTEGER'), ('opponent_abbr', 'TEXT'),
        ('team_record', 'TEXT'), ('opponent_record', 'TEXT'), ('venue', 'TEXT'),
        ('attendance', 'INTEGER'), ('temp', 'INTEGER'), ('conditions', 'TEXT'), ('innings', 'INTEGER'),
        ('team_h', 'INTEGER'), ('team_e', 'INTEGER'), ('team_lob', 'INTEGER'),
        ('opp_h', 'INTEGER'), ('opp_e', 'INTEGER'), ('opp_lob', 'INTEGER'),
    ],
    'point_events': [
        ('at_bat_index', 'INTEGER'), ('inning', 'INTEGER'), ('is_top', 'INTEGER'), ('outs', 'INTEGER'),
        ('away_score', 'INTEGER'), ('home_score', 'INTEGER'), ('description', 'TEXT'),
    ],
}


def connect(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    for table, columns in MIGRATIONS.items():
        existing = {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}
        for name, sql_type in columns:
            if name not in existing:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}')
    conn.commit()
    return conn


def save_play_context(conn, game_id, rows):
    with conn:
        conn.execute('DELETE FROM play_context WHERE game_id = ?', (game_id,))
        conn.executemany(
            'INSERT INTO play_context VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            [(game_id, r['at_bat_index'], r['balls'], r['strikes'], r['leverage_index'], r['wpa'],
              r['launch_speed'], r['launch_angle'], r['distance'], r['pitch_speed'], r['pitch_type'], r['inning'], r['is_top'], r['batter']) for r in rows],
        )


def _event_row(game_id, team_id, scope, mlb_id, name, item):
    play = item.get('play') or {}
    return (
        game_id, team_id, scope, mlb_id, name, item['rule_category'], item['rule_name'], str(item['value']),
        item['points'], play.get('at_bat_index'), play.get('inning'),
        None if play.get('is_top') is None else int(play['is_top']), play.get('outs'),
        play.get('away_score'), play.get('home_score'), play.get('description'),
    )


def save_game(conn, result):
    game_id, team_id = result['game_id'], result['team_id']
    with conn:
        for table in ('games', 'point_events', 'game_players'):
            conn.execute(f'DELETE FROM {table} WHERE game_id = ? AND team_id = ?', (game_id, team_id))
        conn.execute(
            'INSERT INTO games (game_id, team_id, game_date, team_name, opponent, home_away, won, runs_for, '
            'runs_against, player_points, team_points, carry_in, carry_out, total_points, team_abbr, opponent_id, '
            'opponent_abbr, team_record, opponent_record, venue, attendance, temp, conditions, innings, team_h, team_e, team_lob, opp_h, opp_e, opp_lob) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (game_id, team_id, result['game_date'], result['team_name'], result['opponent'], result['side'],
             int(result['won']), result['runs_for'], result['runs_against'], result['player_points'],
             result['team_points'], result['carry_in'], result['carry_out'], result['total'],
             result['team_abbr'], result['opponent_id'], result['opponent_abbr'], result['team_record'],
             result['opponent_record'], result['venue'], result['attendance'], result['temp'],
             result['conditions'], result['innings'],
             *(result.get(k) for k in ('team_h', 'team_e', 'team_lob', 'opp_h', 'opp_e', 'opp_lob'))),
        )
        rows = [
            _event_row(game_id, team_id, 'player', mlb_id, data['name'], item)
            for mlb_id, data in result['players'].items()
            for item in data['breakdown']
        ]
        rows += [_event_row(game_id, team_id, 'team', None, None, item) for item in result['team_breakdown']]
        conn.executemany('INSERT INTO point_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        conn.executemany(
            'INSERT INTO game_players VALUES (?,?,?,?,?,?,?,?,?)',
            [(game_id, team_id, p['mlb_id'], p['name'], p['position'], p['batting_order'], p['pa'],
              json.dumps(p['bat']), json.dumps(p['pit'])) for p in result['player_stats']],
        )


def get_carry_in(conn, team_id, game_date, game_id):
    """Carry over points produced by the team's most recent stored game before this one."""
    row = conn.execute(
        'SELECT carry_out FROM games WHERE team_id = ? AND (game_date < ? OR (game_date = ? AND game_id < ?)) '
        'ORDER BY game_date DESC, game_id DESC LIMIT 1',
        (team_id, game_date, game_date, game_id),
    ).fetchone()
    return row[0] if row else 0.0


def get_season_summary(conn, team_id):
    return conn.execute(
        'SELECT game_date, game_id, opponent, won, runs_for, runs_against, total_points '
        'FROM games WHERE team_id = ? ORDER BY game_date, game_id',
        (team_id,),
    ).fetchall()


def add_moment(conn, moment_date, headline, team_id=None, game_id=None, type='media', source_url=None, note=None):
    with conn:
        cur = conn.execute(
            'INSERT INTO moments (moment_date, team_id, game_id, type, headline, source_url, note) VALUES (?,?,?,?,?,?,?)',
            (moment_date, team_id, game_id, type, headline, source_url, note),
        )
    return cur.lastrowid
