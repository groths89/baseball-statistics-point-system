import statsapi

def initialize_player_points_map(lineups):
    points_map = {}
    for team in ['away', 'home']:
        for player in lineups.get(team, []):
            mlb_id = player['mlb_id']
            points_map[mlb_id] = {
                'name': player['name'],
                'team': team,
                'total_points': 0.0,
                'breakdown': []
            }
    return points_map

def extract_position_code(player_full_details):
    """
    Safely extracts the position code using the confirmed path 
    from the full player details structure.
    """
    position_entry = player_full_details.get('position')
    
    if isinstance(position_entry, dict):
        return position_entry.get('abbreviation', 'N/A')
        
    return 'N/A'

def get_lineups_from_boxscore(game_id):
    try:
        boxscore = statsapi.boxscore_data(game_id)
    except Exception as e:
        print(f"Error fetching boxscore data for game {game_id}: {e}")
        return {'home': [], 'away': []}

    all_lineups = {}
    player_map = boxscore.get('playerInfo', {})


    for team in ['away', 'home']:
        player_map = boxscore.get(team, {}).get('players', {})

        batting_entries = boxscore.get(f'{team}Batters', [])
        
        valid_batters = [
            p for p in batting_entries 
            if p.get('battingOrder') is not None and p.get('battingOrder').strip() != ''
        ]

        valid_batters.sort(key=lambda p: p['battingOrder'])
        
        lineup = []
        for player in valid_batters:
            player_id = player['personId']
            player_map_key = f'ID{player_id}'

            full_details = player_map.get(player_map_key, {})
            
            full_name = full_details.get('person', {}).get('fullName', player.get('namefield', 'Unknown'))
            position_code = extract_position_code(full_details)
            lineup.append({
                'batting_spot': (
                    int(player['battingOrder']) // 100 
                    if player.get('battingOrder') and player['battingOrder'].isdigit() 
                    else 0
                ),
                'name': full_name,
                'mlb_id': player_id,
                'position': position_code,
                'game_stats': player,            
            })

        all_lineups[team] = lineup
    
    return all_lineups