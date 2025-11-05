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
        pitching_entries = boxscore.get(f'{team}Pitchers', [])
        
        valid_batters = [
            p for p in batting_entries 
            if p.get('battingOrder') is not None and p.get('battingOrder').strip() != ''
        ]

        valid_batters.sort(key=lambda p: p['battingOrder'])
        
        combined_players = {}

        for player in valid_batters:
            combined_players[player['personId']] = {
                'stats': player,
                'is_pitcher': False,
                'sort_key': int(player['battingOrder']) // 100 
            }

        for player in pitching_entries:
            player_id = player['personId']

            if not player_id or not isinstance(player_id, int) or player_id == 0:
                continue
            
            if player_id not in combined_players:
                # Assign a high sort key (99) to place pitchers at the end of the list
                combined_players[player_id] = {
                    'stats': player,
                    'is_pitcher': True,
                    'sort_key': 99 
                }
        
        final_list = []
        for player_id, data in combined_players.items():
            player_map_key = f'ID{player_id}'
            full_details = player_map.get(player_map_key, {})
            stats = data['stats']
            
            full_name = full_details.get('person', {}).get('fullName', stats.get('namefield', 'Unknown'))
            position_code = extract_position_code(full_details)

            final_list.append({
                'batting_spot': data['sort_key'],
                'name': full_name,
                'position': position_code,
                'mlb_id': player_id,
                'game_stats': stats,
            })

        final_list.sort(key=lambda player: player['batting_spot'])
        lineup = [player for player in final_list]
        all_lineups[team] = lineup
    
    return all_lineups