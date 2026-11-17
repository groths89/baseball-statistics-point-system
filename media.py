"""Pull media around each scored game (headlines, recaps, highlight videos) into the media_items table.

Sources (no API keys needed; only titles and links are stored, never article text):
  mlb     official MLB recap and highlight videos for the game
  google  Google News RSS headlines for the two teams in the days around the game; the total
          number of stories and distinct outlets is saved as the game's buzz (game_buzz table)

  python media.py --season 2024                 # every scored game that has no media yet
  python media.py --game 745811 --team 121
  python media.py --start 2024-06-10 --end 2024-06-20 --source google
  python media.py --season 2024 --refresh       # re-fetch games that already have items
"""
import argparse
import os
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import statsapi

import storage

DB_PATH = os.environ.get(
    'POINTS_DB',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'new_york_mets', 'points.db'),
)
USER_AGENT = 'Mozilla/5.0 (compatible; baseball-statistics-point-system)'
SOURCES = ('mlb', 'google')


def fetch_mlb(game):
    content = statsapi.get('game_content', {'gamePk': game['game_id']})
    items = []
    recap = (content.get('editorial') or {}).get('recap', {}).get('mlb') or {}
    if recap.get('slug'):
        items.append({
            'kind': 'recap',
            'title': recap.get('seoTitle') or recap.get('headline'),
            'url': f"https://www.mlb.com/news/{recap['slug']}",
            'publisher': 'MLB.com',
            'published_at': recap.get('date'),
        })
    for clip in ((content.get('highlights') or {}).get('highlights') or {}).get('items', [])[:6]:
        if clip.get('slug'):
            items.append({
                'kind': 'highlight',
                'title': clip.get('headline') or clip.get('title'),
                'url': f"https://www.mlb.com/video/{clip['slug']}",
                'publisher': 'MLB.com',
                'published_at': clip.get('date'),
            })
    return items


def fetch_google(game, limit=6):
    """Returns the top headlines; sets game['buzz'] to the total coverage found in the window."""
    day = date.fromisoformat(game['game_date'])
    query = f'"{game["team_name"]}" "{game["opponent"]}" after:{day} before:{day + timedelta(days=2)}'
    url = f'https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en'
    with urlopen(Request(url, headers={'User-Agent': USER_AGENT}), timeout=20) as resp:
        root = ET.fromstring(resp.read())
    items, publishers, total = [], set(), 0
    for item in root.iter('item'):
        title, link = item.findtext('title'), item.findtext('link')
        if not title or not link:
            continue
        total += 1
        source = item.find('source')
        publisher = source.text if source is not None else None
        publishers.add(publisher)
        if len(items) >= limit:
            continue
        if publisher and title.endswith(f' - {publisher}'):
            title = title[: -len(publisher) - 3]
        published = item.findtext('pubDate')
        items.append({
            'kind': 'news',
            'title': title,
            'url': link,
            'publisher': publisher,
            'published_at': parsedate_to_datetime(published).astimezone(timezone.utc).isoformat() if published else None,
        })
    game['buzz'] = (total, len(publishers))
    return items


FETCHERS = {'mlb': fetch_mlb, 'google': fetch_google}


def save_items(conn, game, source, items):
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        if game.get('buzz') and source == 'google':
            conn.execute(
                'INSERT OR REPLACE INTO game_buzz (game_id, team_id, news_count, publishers, fetched_at) VALUES (?,?,?,?,?)',
                (game['game_id'], game['team_id'], *game['buzz'], now),
            )
        conn.executemany(
            'INSERT OR IGNORE INTO media_items (game_id, team_id, source, kind, title, url, publisher, published_at, fetched_at) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            [(game['game_id'], game['team_id'], source, i['kind'], i['title'], i['url'], i['publisher'],
              i['published_at'], now) for i in items],
        )


def select_games(conn, args):
    clauses, params = [], []
    for column, value in (('team_id', args.team), ('game_id', args.game)):
        if value is not None:
            clauses.append(f'{column} = ?')
            params.append(value)
    if args.season:
        clauses.append('substr(game_date, 1, 4) = ?')
        params.append(str(args.season))
    if args.start:
        clauses.append('game_date >= ?')
        params.append(args.start)
    if args.end:
        clauses.append('game_date <= ?')
        params.append(args.end)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    conn.row_factory = sqlite3.Row
    return conn.execute(
        f'SELECT game_id, team_id, game_date, team_name, opponent FROM games{where} ORDER BY game_date, game_id', params
    ).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--team', type=int)
    parser.add_argument('--game', type=int)
    parser.add_argument('--season', type=int)
    parser.add_argument('--start', help='YYYY-MM-DD')
    parser.add_argument('--end', help='YYYY-MM-DD')
    parser.add_argument('--source', choices=SOURCES + ('all',), default='all')
    parser.add_argument('--refresh', action='store_true', help='re-fetch games that already have media from the source')
    parser.add_argument('--sleep', type=float, default=1.0, help='seconds between requests')
    args = parser.parse_args()
    if not any((args.team, args.game, args.season, args.start, args.end)):
        parser.error('choose games with --team, --game, --season, --start or --end')

    conn = storage.connect(DB_PATH)
    games = select_games(conn, args)
    sources = SOURCES if args.source == 'all' else (args.source,)
    added = 0
    for n, game in enumerate(games, 1):
        game = dict(game)
        for source in sources:
            table = 'game_buzz' if source == 'google' else 'media_items'
            sql = f'SELECT 1 FROM {table} WHERE game_id = ? AND team_id = ?'
            if source != 'google':
                sql += ' AND source = ?'
            if not args.refresh and conn.execute(
                sql + ' LIMIT 1', (game['game_id'], game['team_id'], *((source,) if source != 'google' else ())),
            ).fetchone():
                continue
            try:
                items = FETCHERS[source](game)
            except Exception as exc:
                print(f'  {game["game_date"]} {game["game_id"]} {source}: {exc}')
                continue
            before = conn.total_changes
            save_items(conn, game, source, items)
            added += conn.total_changes - before
            time.sleep(args.sleep)
        if n % 10 == 0 or n == len(games):
            print(f'{n}/{len(games)} games, {added} items added')


if __name__ == '__main__':
    main()
