import statsapi

SIDES = ('away', 'home')


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_ip_to_outs(ip_string):
    """Converts an innings pitched string such as '6.2' into outs recorded (20)."""
    try:
        full_innings, partial_outs = str(ip_string).split('.')
        return int(full_innings) * 3 + int(partial_outs)
    except (ValueError, AttributeError):
        return 0


def opposite(side):
    return 'home' if side == 'away' else 'away'


_current_play = None


def set_play_context(snapshot):
    """Tags every point event recorded until it is cleared (None) with the play that caused it."""
    global _current_play
    _current_play = snapshot


def add_points(points_map, mlb_id, category, rule_name, value, points):
    """Records a scoring event for a player and updates the player's running total."""
    entry = points_map.setdefault(mlb_id, {
        'name': f'Player {mlb_id}',
        'team': None,
        'total_points': 0.0,
        'breakdown': [],
    })
    entry['total_points'] += points
    entry['breakdown'].append({
        'rule_category': category,
        'rule_name': rule_name,
        'value': value,
        'points': points,
        'play': _current_play,
    })


def initialize_player_points_map(lineups, sides=SIDES):
    points_map = {}
    for team in sides:
        for player in lineups.get(team, []):
            points_map[player['mlb_id']] = {
                'name': player['name'],
                'team': team,
                'total_points': 0.0,
                'breakdown': [],
            }
    return points_map


def extract_position_code(player_full_details):
    position_entry = player_full_details.get('position')
    if isinstance(position_entry, dict):
        return position_entry.get('abbreviation', 'N/A')
    return 'N/A'


def get_lineups_from_boxscore(game_id, boxscore=None):
    """
    Builds a lineup per side. Each player has separate 'batting' and 'pitching'
    stat dicts (None when the player did not bat / pitch), so a player who both
    bats and pitches is never double counted or misclassified.
    """
    if boxscore is None:
        boxscore = statsapi.boxscore_data(game_id)

    all_lineups = {}

    for team in SIDES:
        player_map = boxscore.get(team, {}).get('players', {})

        batters = {
            p['personId']: p for p in boxscore.get(f'{team}Batters', [])
            if p.get('personId') and (p.get('battingOrder') or '').strip() != ''
        }
        pitchers = {
            p['personId']: p for p in boxscore.get(f'{team}Pitchers', [])
            if isinstance(p.get('personId'), int) and p['personId'] != 0
        }

        final_list = []
        for player_id in list(batters) + [pid for pid in pitchers if pid not in batters]:
            batting = batters.get(player_id)
            pitching = pitchers.get(player_id)
            full_details = player_map.get(f'ID{player_id}', {})
            source = batting or pitching

            position = extract_position_code(full_details)
            if batting is None:
                position = 'P'

            final_list.append({
                'batting_spot': to_int(batting['battingOrder']) // 100 if batting else 99,
                'name': full_details.get('person', {}).get('fullName', source.get('name', 'Unknown')),
                'position': position,
                'mlb_id': player_id,
                'batting': batting,
                'pitching': pitching,
            })

        final_list.sort(key=lambda player: player['batting_spot'])
        all_lineups[team] = final_list

    return all_lineups


def get_starters_from_boxscore(boxscore_data):
    """Returns the starting pitcher id per side (the first real row after the header row)."""
    starters = {}
    for side in SIDES:
        pitchers = boxscore_data.get(f'{side}Pitchers', [])
        real = [p for p in pitchers if isinstance(p.get('personId'), int) and p['personId'] != 0]
        starters[side] = real[0]['personId'] if real else None
    return starters


def fetch_game(game_id):
    """Fetches everything needed to score a game: box score data and the live feed (play-by-play)."""
    boxscore = statsapi.boxscore_data(game_id)
    live_feed = statsapi.get('game', {'gamePk': game_id})
    return boxscore, live_feed


def fetch_play_context(game_id):
    """Per-play count, leverage index, win probability added and batted-ball data (one row per at-bat)."""
    rows = []
    for play in statsapi.get('game_winProbability', {'gamePk': game_id}):
        events = play.get('playEvents', [])
        hit = next((e['hitData'] for e in reversed(events) if e.get('hitData')), {})
        pitch = next((e for e in reversed(events) if e.get('isPitch')), {})
        count = play.get('count', {})
        wpa = play.get('homeTeamWinProbabilityAdded')
        rows.append({
            'at_bat_index': play['about']['atBatIndex'],
            'balls': count.get('balls'), 'strikes': count.get('strikes'),
            'leverage_index': play.get('leverageIndex'),
            'wpa': None if wpa is None else wpa if not play['about'].get('isTopInning') else -wpa,
            'launch_speed': hit.get('launchSpeed'), 'launch_angle': hit.get('launchAngle'),
            'distance': hit.get('totalDistance'),
            'pitch_speed': pitch.get('pitchData', {}).get('startSpeed'),
            'pitch_type': pitch.get('details', {}).get('type', {}).get('description'),
            'inning': play['about'].get('inning'), 'is_top': int(bool(play['about'].get('isTopInning'))),
            'batter': play.get('matchup', {}).get('batter', {}).get('fullName'),
        })
    return rows
