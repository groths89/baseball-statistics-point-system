"""
Custom baseball point system for the New York Mets (or any team via --team).

Examples:
    python ny_mets_points_system.py                       # score the latest completed game
    python ny_mets_points_system.py --game 776450         # score one game
    python ny_mets_points_system.py --season 2025         # score every completed regular season game
    python ny_mets_points_system.py --summary             # print stored season results
"""
import argparse
import os
import traceback

import statsapi

import storage
from data_utils import fetch_game, fetch_play_context
from game_scoring import TeamNotInGameError, score_game
from report import build_report

TEAM_ID = 121
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'new_york_mets')
DB_PATH = os.path.join(PROJECT_DIR, 'points.db')
FINAL_STATES = ('Final', 'Game Over', 'Completed')


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--team', type=int, default=TEAM_ID, help='MLB team id (default: 121, New York Mets)')
    parser.add_argument('--game', type=int, help='score a specific game id')
    parser.add_argument('--season', type=int, help='score every completed regular season game of a season')
    parser.add_argument('--start', help='start date YYYY-MM-DD (use with --end)')
    parser.add_argument('--end', help='end date YYYY-MM-DD (use with --start)')
    parser.add_argument('--summary', action='store_true', help='print the stored results and exit')
    parser.add_argument('--no-save', action='store_true', help='do not write to the database')
    parser.add_argument('--quiet', action='store_true', help='only print one line per game')
    return parser.parse_args()


def completed_game_ids(team_id, start, end):
    games = statsapi.schedule(team=team_id, start_date=start, end_date=end)
    final = [g for g in games if g['game_type'] == 'R' and g['status'].startswith(FINAL_STATES)]
    final.sort(key=lambda g: (g['game_date'], g['game_datetime'], g['game_id']))
    return [g['game_id'] for g in final]


def pick_game_ids(args):
    if args.game:
        return [args.game]
    if args.season:
        return completed_game_ids(args.team, f'{args.season}-02-01', f'{args.season}-11-30')
    if args.start and args.end:
        return completed_game_ids(args.team, args.start, args.end)
    return [statsapi.last_game(args.team)]


def print_summary(conn, team_id):
    rows = storage.get_season_summary(conn, team_id)
    if not rows:
        print('No stored games yet.')
        return
    print(f"{'Date':<11} {'Game':<8} {'Opponent':<22} {'W/L':<4} {'Score':<7} {'Points':>7}")
    for date, game_id, opponent, won, runs_for, runs_against, total in rows:
        print(f"{date:<11} {game_id:<8} {opponent[:22]:<22} {'W' if won else 'L':<4} "
              f"{runs_for}-{runs_against:<5} {total:>7.1f}")
    wins = sum(r[3] for r in rows)
    average = sum(r[6] for r in rows) / len(rows)
    print(f'\n{len(rows)} games, {wins}-{len(rows) - wins}, average points per game: {average:.1f}')


def main():
    args = parse_args()
    os.makedirs(PROJECT_DIR, exist_ok=True)
    conn = storage.connect(DB_PATH)

    if args.summary:
        print_summary(conn, args.team)
        return

    game_ids = pick_game_ids(args)
    carry = None

    for game_id in game_ids:
        try:
            boxscore, live_feed = fetch_game(game_id)
            if carry is None:
                game_date = live_feed['gameData']['datetime'].get('officialDate')
                carry = storage.get_carry_in(conn, args.team, game_date, game_id)
            result = score_game(game_id, args.team, carry_in=carry, boxscore=boxscore, live_feed=live_feed)
        except TeamNotInGameError as e:
            print(f'Skipping {game_id}: {e}')
            continue
        except Exception as e:
            print(f'Error scoring game {game_id}: {e}')
            print(traceback.format_exc())
            continue

        carry = result['carry_out']
        report = build_report(result)
        with open(os.path.join(PROJECT_DIR, f'{game_id}.txt'), 'w', encoding='utf-8') as f:
            f.write(report)
        if not args.no_save:
            storage.save_game(conn, result)
            try:
                storage.save_play_context(conn, game_id, fetch_play_context(game_id))
            except Exception as e:
                print(f'Play context unavailable for {game_id}: {e}')

        if args.quiet or len(game_ids) > 1:
            print(f"{result['game_date']} {game_id} {result['opponent'][:20]:<20} "
                  f"{'W' if result['won'] else 'L'} {result['total']:.1f} pts")
        else:
            print(report)


if __name__ == '__main__':
    main()
