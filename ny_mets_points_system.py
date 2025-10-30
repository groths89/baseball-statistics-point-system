import statsapi
import os

TEAM_ID = 121
PROJECT_DIR = os.path.join(os.getcwd(), "new_york_mets")

batting = []
pitching = []

if not os.path.exists(PROJECT_DIR):
    os.mkdir(PROJECT_DIR)

last_game_id = statsapi.last_game(TEAM_ID)
last_game = statsapi.get('game', {'gamePk': last_game_id})

def extract_position_code(player_full_details):
    """
    Safely extracts the position code using the confirmed path 
    from the full player details structure.
    """
    # Check the nested path: 'position' -> 'abbreviation'
    position_entry = player_full_details.get('position')
    
    if isinstance(position_entry, dict):
        # We target 'abbreviation' (like 'C' for catcher)
        return position_entry.get('abbreviation', 'N/A')
        
    return 'N/A'

def get_lineups_from_boxscore(game_id):
    try:
        boxscore = statsapi.boxscore_data(game_id)
    except Exception as e:
        print(f"Error fetching boxscore data for game {game_id}: {e}")
        return {'home': [], 'away': []}

    all_lineups = {}
    player_map = boxscore.get('players', {})


    for team in ['away', 'home']:
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
            full_name = full_details.get('person', {}).get('fullName', 'Unknown Player')
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
            })

        all_lineups[team] = lineup
    
    return all_lineups


try:
    lineups = get_lineups_from_boxscore(last_game_id)
    game_boxscore_data = statsapi.boxscore_data(last_game_id)
    game_play_by_play_data = statsapi.game_scoring_play_data(last_game_id)

    team_info = game_boxscore_data['teamInfo']
    mets_team_id = TEAM_ID
    mets_location = 'away' if team_info['away']['id'] == mets_team_id else 'home'

    basic_batting_points = 0
    # Use the determined location to get the correct batting totals
    batting_totals = game_boxscore_data[f'{mets_location}BattingTotals']
    basic_batting_points += int(batting_totals['r'])
    basic_batting_points += int(batting_totals['h']) / 2

    # Add Triples to Basic Batting
    triples_from_plays = 0
    is_top_inning = mets_location == 'away'
    hits_points = 0
    homerun_points = 0
    walks = 0

    for play in last_game['liveData']['plays']['allPlays']:
        # Check if the play is a Mets at-bat
        if play['about']['isTopInning'] == is_top_inning and play['result']['type'] == 'atBat':
            event = play['result']['event']
            if event == 'Walk':
                walks += 1
            elif event == 'Hit':
                hits_points += 0.5
            elif event == 'Single':
                basic_batting_points += 1
            elif event == 'Double':
                basic_batting_points += 2
            elif event == 'Triple':
                triples_from_plays += 1
            elif event == 'Home Run':
                # Count runners on base before the home run
                runners_on_base = 0
                for runner in play.get('runners', []):
                    # The batter is also a "runner", but their originBase is None
                    if runner.get('movement', {}).get('originBase') is not None:
                        runners_on_base += 1
                
                if runners_on_base == 0: # Solo HR
                    homerun_points += 1
                elif 0 < runners_on_base < 3: # 2-run or 3-run HR
                    homerun_points += 2
                elif runners_on_base == 3: # Grand Slam
                    homerun_points += 4

    # Calculate the individual points to the basic batting points total
    basic_batting_points += walks
    if walks >= 5:
        basic_batting_points += 2
    basic_batting_points += triples_from_plays * 3
    basic_batting_points += homerun_points

    with open(os.path.join(PROJECT_DIR, str(statsapi.last_game(TEAM_ID) ) + ".txt"), "w+") as textfile:
        line = "The game is: " + str(statsapi.last_game(TEAM_ID))
        line = line + "\n" + "The home team is: " + str(game_boxscore_data['teamInfo']['home']['teamName']) + "\n"
        line = line + "The away team is: " + str(game_boxscore_data['teamInfo']['away']['teamName']) + "\n"
        line = line + "\n" + "The lineup is: " + str(lineups) + "\n"
        line = line + "\n" + "Basic Batting Points: " + str(basic_batting_points) + "pts" + "\n"
        line = line + f"Triples (Points): {triples_from_plays}" + "\n"
        line = line + f"Homerun (Points): {homerun_points}" + "\n"
        line = line + f"Walks (Points): {walks}" + "\n"
        line = line + f"Hits (Points): {hits_points}" + "\n"
        line = line + f"Runs: {batting_totals['r']}" + "\n"
        line = line + f"Hits: {batting_totals['h']}" + "\n"
        line = line + "\n"
        line = line + "\n" + str(statsapi.boxscore_data(last_game_id)) + "\n"
        line = line + f"All Plays: {last_game['liveData']['plays']['allPlays']}" + "\n"
        line = line + "\n" + str(game_play_by_play_data['plays']) + "\n"
        line = line + "\n"

        textfile.write(line)
except Exception as e:
    print(f"Error fetching data from {last_game_id}: {e}")