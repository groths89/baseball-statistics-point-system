def calculate_solo_homerun_points_for_player(lineups, player_points_map):
    POINTS_PER_HR = 1.0

    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']
                        
            if player.get('position') == 'P': continue

            if not mlb_id or not isinstance(stats, dict):
                continue

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

            if player.get('position') == 'P': continue

            if not mlb_id or not isinstance(stats, dict):
                continue

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

def calculate_total_triples_points_for_player(lineups, player_points_map):
    POINTS_PER_TRIPLE = 3.0
    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']

            if player.get('position') == 'P': continue

            if not mlb_id or not isinstance(stats, dict):
                continue

            try:
                triples_recorded = int(stats.get('triple', '0') or '0')
            except ValueError:
                triples_recorded = 0

            if triples_recorded > 0:
                points_awarded = float(triples_recorded * POINTS_PER_TRIPLE)
                player_points_map[mlb_id]['total_points'] += points_awarded
                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Basic Stats',
                    'rule_name': 'Triples',
                    'value': triples_recorded,
                    'points': points_awarded,
                })

    return player_points_map

def calculate_total_runs_points_for_player(lineups, player_points_map):
    POINTS_PER_RUN = 1.0
    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']

            if player.get('position') == 'P': continue

            if not mlb_id or not isinstance(stats, dict):
                continue

            try:
                runs_recorded = int(stats.get('r', '0') or '0')
            except ValueError:
                runs_recorded = 0

            if runs_recorded > 0:
                points_awarded = float(runs_recorded * POINTS_PER_RUN)
                player_points_map[mlb_id]['total_points'] += points_awarded
                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Basic Stats',
                    'rule_name': 'Runs',
                    'value': runs_recorded,
                    'points': points_awarded,
                })

    return player_points_map

def calculate_total_walks_points_for_player(lineups, player_points_map):
    POINTS_PER_WALK = 1.0
    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']

            if player.get('position') == 'P': continue

            if not mlb_id or not isinstance(stats, dict):
                continue


            try:
                walks_recorded = int(stats.get('bb', '0') or '0')
            except ValueError:
                walks_recorded = 0

            if walks_recorded > 0:
                points_awarded = float(walks_recorded * POINTS_PER_WALK)
                player_points_map[mlb_id]['total_points'] += points_awarded
                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Basic Stats',
                    'rule_name': 'Walks',
                    'value': walks_recorded,
                    'points': points_awarded,
                })

    return player_points_map

def calculate_strikeouts_points_for_pitcher(lineups, player_points_map):
    """Awards 0.5 points for each strikeout by a pitcher only"""
    POINTS_PER_STRIKEOUT = 0.0
    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            stats = player['game_stats']

            if player.get('position') != 'P': continue

            if not mlb_id or not isinstance(stats, dict): continue

            try:
                strikeouts_recorded = int(stats.get('k', '0') or '0')
            except ValueError:
                strikeouts_recorded = 0

            if strikeouts_recorded > 0:
                points_awarded = float(strikeouts_recorded * POINTS_PER_STRIKEOUT)
                player_points_map[mlb_id]['total_points'] += points_awarded

                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Pitching',
                    'rule_name': 'Strikeout(s)',
                    'value': strikeouts_recorded,
                    'points': points_awarded,
                })

    return player_points_map



def calculate_starter_ip_points_for_player(lineups, player_points_map, boxscore_data):
    POINTS_FOR_7_IP = 5.0
    MIN_IP_OUTS = 21

    starters = {}

    try:
        starters['home'] = boxscore_data.get('homePitchers', [{}][0]).get('personId')
        starters['away'] = boxscore_data.get('awayPitchers', [{}][0]).get('personId')
    except (IndexError, AttributeError):
        return player_points_map
    
    for player in (p for team_lineup in lineups.values() for p in team_lineup):
        mlb_id = player['mlb_id']
        stats = player['game_stats']

        if not mlb_id or not isinstance(stats, dict):
            continue

        is_starter = (mlb_id == starters.get('home') or mlb_id == starters.get('away'))

        if is_starter:
            try:
                ip_string = stats.get('ip')

                full_innings, partial_outs = map(int, ip_string.split('.'))
                total_outs = full_innings * 3 + partial_outs

            except (ValueError, AttributeError):
                total_outs = 0

            if total_outs >= MIN_IP_OUTS:
                points_awarded = POINTS_FOR_7_IP

                player_points_map[mlb_id]['total_points'] += points_awarded

                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Pitching',
                    'rule_name': 'Starter 7+ IP',
                    'value': ip_string,
                    'points': points_awarded,
                })
                
    return player_points_map

def calculate_starter_two_runs_or_less_points_for_player(lineups, player_points_map, boxscore_data):
    "Awards +5 to a pitcher if they are the starter AND give up less than 2 Earned Runs AND a minimum of 5.0 innings pitched"
    POINTS_FOR_STARTER_LOW_ER = 5.0
    MIN_IP_OUTS = 15
    MAX_EARNED_RUNS = 2.0

    starters = {}

    try:
        starters['home'] = boxscore_data.get('homePitchers', [{}])[0].get('personId')
        starters['away'] = boxscore_data.get('awayPitchers', [{}])[0].get('personId')
    except (IndexError, AttributeError):
        return player_points_map
    
    for player in (p for team_lineup in lineups.values() for p in team_lineup):
        mlb_id = player['mlb_id']
        stats = player['game_stats']

        if not mlb_id or not isinstance(stats, dict):
            continue

        is_starter = (mlb_id == starters.get('home') or mlb_id == starters.get('away'))

        if is_starter:
            try:
                earned_runs = float(stats.get('er', '3') or '3')
                ip_string = stats.get('ip', '0.0')

                full_innings, partial_outs = map(int, ip_string.split('.'))
                total_outs = (full_innings * 3) + partial_outs
                
            except (ValueError, AttributeError):
                total_outs = 0
                earned_runs = 0

            if total_outs >= MIN_IP_OUTS and earned_runs <= MAX_EARNED_RUNS:
                points_awarded = POINTS_FOR_STARTER_LOW_ER

                player_points_map[mlb_id]['total_points'] += points_awarded

                player_points_map[mlb_id]['breakdown'].append({
                    'rule_category': 'Pitching',
                    'rule_name': 'Starter Two Runs or Less (min 5 IP)',
                    'value': f'{ip_string} IP, {earned_runs} ER',
                    'points': points_awarded,
                })
                
    return player_points_map

def calculate_starter_pitches_complete_game_points_for_player(lineups, player_points_map, boxscore_data):
    POINTS_FOR_STARTER_COMPLETE_GAME = 10.0
    MIN_IP_OUTS = 27

    starters = {}

    try:
        starters['home'] = boxscore_data.get('homePitchers', [{}])[0].get('personId')
        starters['away'] = boxscore_data.get('awayPitchers', [{}])[0].get('personId')
    except (IndexError, AttributeError):
        return player_points_map
    
    for player in (p for team_lineup in lineups.values() for p in team_lineup):
        mlb_id = player['mlb_id']
        stats = player['game_stats']

        is_starter = (mlb_id == starters.get('home') or mlb_id == starters.get('away'))

        if not mlb_id or not isinstance(stats, dict):
            continue

    if is_starter:
        try:
            ip_string = stats.get('ip', '0.0')
            full_innings, partial_outs = map(int, ip_string.split('.'))

            total_outs = (full_innings * 3) + partial_outs

        except (ValueError, AttributeError):
            total_outs = 0

        if total_outs == MIN_IP_OUTS:
            points_awarded = POINTS_FOR_STARTER_COMPLETE_GAME
            player_points_map[mlb_id]['total_points'] += points_awarded

            player_points_map[mlb_id]['breakdown'].append({
                'rule_category': 'Pitching',
                'rule_name': 'Starter Complete Game',
                'value': f'{ip_string} IP',
                'points': points_awarded,
            })
            
    return player_points_map


    
