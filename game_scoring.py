"""Scores a single game for one team by applying every rule in the README."""
import player_scoring_rules as player_rules
import situational_rules as pbp_rules
import team_scoring
from data_utils import (
    fetch_game,
    get_lineups_from_boxscore,
    get_starters_from_boxscore,
    initialize_player_points_map,
    opposite,
    to_int,
)


class TeamNotInGameError(ValueError):
    pass


def find_side(boxscore, team_id):
    for side in ('home', 'away'):
        if boxscore['teamInfo'][side]['id'] == team_id:
            return side
    raise TeamNotInGameError(f'Team {team_id} did not play in this game')


def score_game(game_id, team_id, carry_in=0.0, boxscore=None, live_feed=None):
    """Returns the full point breakdown for `team_id` in `game_id`."""
    if boxscore is None or live_feed is None:
        boxscore, live_feed = fetch_game(game_id)

    side = find_side(boxscore, team_id)
    other = opposite(side)

    lineups = get_lineups_from_boxscore(game_id, boxscore)
    players = lineups[side]
    starter_id = get_starters_from_boxscore(boxscore)[side]
    pm = initialize_player_points_map(lineups, sides=(side,))
    team_events = []

    plays = pbp_rules.annotate_plays(live_feed['liveData']['plays']['allPlays'])
    linescore_innings = live_feed['liveData']['linescore'].get('innings', [])

    # I. Basic stats
    player_rules.calculate_total_hits_points_for_player(players, pm)
    player_rules.calculate_total_triples_points_for_player(players, pm)
    player_rules.calculate_total_runs_points_for_player(players, pm)
    player_rules.calculate_total_walks_points_for_player(players, pm)
    pbp_rules.calculate_homerun_points(plays, side, pm)
    player_rules.calculate_starter_points(players, pm, starter_id)
    player_rules.calculate_save_points_for_player(players, pm)
    player_rules.calculate_strikeout_tracking_for_pitcher(players, pm)
    player_rules.track_earned_runs_for_player(players, pm)
    team_scoring.calculate_team_walks_bonus(boxscore, side, team_events)
    team_scoring.calculate_team_strikeout_for_pitchers_bonus(boxscore, side, team_events)
    team_scoring.calculate_bullpen_zero_runs_bonus(players, starter_id, team_events)

    # II. Situational baseball
    pbp_rules.calculate_offensive_situational_points(plays, side, pm, team_events)
    pbp_rules.calculate_defensive_situational_points(plays, side, pm, team_events)

    # III. Unusual and miraculous
    player_rules.calculate_unusual_batting_points(players, pm)
    carry_out = team_scoring.calculate_unusual_team_events(plays, boxscore, side, players, team_events)

    # IV. Deductions
    player_rules.calculate_batter_strikeout_deduction(players, pm)
    player_rules.calculate_relief_first_batter_walk_deduction(plays, side, starter_id, pm)
    team_scoring.calculate_team_deductions(boxscore, side, linescore_innings, team_events)

    # V. Carry over is applied through carry_in and reported through carry_out
    summary = team_scoring.summarize_team(pm, team_events, carry_in, carry_out)

    game_data = live_feed['gameData']
    final_plays = live_feed['liveData']['linescore']['teams']
    runs_for = final_plays[side].get('runs', 0)
    runs_against = final_plays[other].get('runs', 0)

    plate_appearances = {}
    for ctx in plays:
        if ctx['side'] == side and ctx['is_pa']:
            plate_appearances[ctx['batter_id']] = plate_appearances.get(ctx['batter_id'], 0) + 1

    def record(s):
        r = game_data['teams'][s].get('record', {})
        return f"{r.get('wins', 0)}-{r.get('losses', 0)}"

    weather = game_data.get('weather', {})
    team_info, opp_info = boxscore['teamInfo'][side], boxscore['teamInfo'][other]
    attendance = next((i['value'] for i in live_feed['liveData']['boxscore'].get('info', []) if i.get('label') == 'Att'), '')

    ls_teams = live_feed['liveData']['linescore'].get('teams', {})
    mine, theirs = ls_teams.get(side, {}), ls_teams.get(other, {})

    return {
        'team_h': mine.get('hits'), 'team_e': mine.get('errors'), 'team_lob': mine.get('leftOnBase'),
        'opp_h': theirs.get('hits'), 'opp_e': theirs.get('errors'), 'opp_lob': theirs.get('leftOnBase'),
        'game_id': game_id,
        'game_date': game_data['datetime'].get('officialDate'),
        'team_id': team_id,
        'team_name': team_info['teamName'],
        'team_abbr': team_info.get('abbreviation'),
        'opponent': opp_info['teamName'],
        'opponent_id': opp_info['id'],
        'opponent_abbr': opp_info.get('abbreviation'),
        'side': side,
        'runs_for': runs_for,
        'runs_against': runs_against,
        'won': runs_for > runs_against,
        'team_record': record(side),
        'opponent_record': record(other),
        'venue': game_data.get('venue', {}).get('name'),
        'attendance': to_int(attendance.strip('.').replace(',', '')) or None,
        'temp': to_int(weather.get('temp')) or None,
        'conditions': weather.get('condition'),
        'innings': live_feed['liveData']['linescore'].get('currentInning'),
        'players': pm,
        'lineup': players,
        'player_stats': [_player_stats(p, plate_appearances) for p in players],
        **summary,
    }


def _player_stats(player, plate_appearances):
    """Box score line for a player; stored so the ledgers can show more than point totals."""
    batting, pitching = player.get('batting'), player.get('pitching')
    note = ((pitching or {}).get('note') or '').strip('() ')
    decision = note.split(',')[0].strip() if note else ''
    return {
        'mlb_id': player['mlb_id'],
        'name': player['name'],
        'position': player['position'],
        'batting_order': player['batting_spot'] if batting else None,
        'pa': plate_appearances.get(player['mlb_id'], 0) if batting else None,
        'bat': {k: to_int(batting.get(k)) for k in ('ab', 'r', 'h', 'hr', 'rbi', 'bb', 'k')} if batting else None,
        'pit': {
            'ip': pitching.get('ip'),
            'h': to_int(pitching.get('h')), 'r': to_int(pitching.get('r')), 'er': to_int(pitching.get('er')),
            'bb': to_int(pitching.get('bb')), 'k': to_int(pitching.get('k')), 'pitches': to_int(pitching.get('p')),
            'decision': decision if decision in ('W', 'L', 'S', 'H', 'BS') else '',
        } if pitching else None,
    }
