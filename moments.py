"""Manage off-field moments (media, culture, trades, injuries) shown as pins on the season timeline.

  python moments.py add --date 2025-06-12 --headline "..." --type media --url https://... --note "..." [--team 121] [--game 123]
  python moments.py list [--team 121]
  python moments.py delete ID
"""
import argparse
import os

import storage

DB_PATH = os.environ.get(
    'POINTS_DB',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'new_york_mets', 'points.db'),
)
TYPES = ('media', 'culture', 'transaction', 'injury', 'other')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    add = sub.add_parser('add')
    add.add_argument('--date', required=True, help='YYYY-MM-DD')
    add.add_argument('--headline', required=True)
    add.add_argument('--type', choices=TYPES, default='media')
    add.add_argument('--url')
    add.add_argument('--note')
    add.add_argument('--team', type=int, help='omit for a moment that applies to every team')
    add.add_argument('--game', type=int)
    lst = sub.add_parser('list')
    lst.add_argument('--team', type=int)
    delete = sub.add_parser('delete')
    delete.add_argument('id', type=int)
    args = parser.parse_args()

    conn = storage.connect(DB_PATH)
    if args.cmd == 'add':
        print('Added moment', storage.add_moment(
            conn, args.date, args.headline, args.team, args.game, args.type, args.url, args.note))
    elif args.cmd == 'delete':
        with conn:
            conn.execute('DELETE FROM moments WHERE id = ?', (args.id,))
    else:
        sql = 'SELECT id, moment_date, type, headline, source_url FROM moments'
        params = []
        if args.team is not None:
            sql += ' WHERE team_id IS NULL OR team_id = ?'
            params.append(args.team)
        for row in conn.execute(sql + ' ORDER BY moment_date', params):
            print(*row, sep=' | ')


if __name__ == '__main__':
    main()
