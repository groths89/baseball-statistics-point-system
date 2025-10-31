def calculate_solo_homerun_points_for_player(lineups, player_points_map):
    POINTS_PER_HR = 1.0

    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']

            try:
                hrs = int(stats.get('homeRuns', '0') or '0')
            except ValueError:
                hrs = 0

            if hrs > 0:
                points_awarded = hrs * POINTS_PER_HR
                player_points_map[mlb_id]['total_points'] += points_awarded
                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Basic Stats',
                    'rule_name': 'Solo Homerun',
                    'value': hrs,
                    'points': points_awarded,
                })

    return player_points_map

def calculate_total_hits_points_for_player(lineups, player_points_map):
    POINTS_PER_HIT = 0.5

    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']

            try:
                hits_recorded = int(stats.get('h', '0') or '0')
            except ValueError:
                hits_recorded = 0

            if hits_recorded > 0:
                points_awarded = float(hits_recorded * POINTS_PER_HIT)
                player_points_map[mlb_id]['total_points'] += points_awarded
                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Basic Stats',
                    'rule_name': 'Hits',
                    'value': hits_recorded,
                    'points': points_awarded,
                })

    return player_points_map