import statsapi
import os
import traceback

from player_scoring_rules import calculate_solo_homerun_points_for_player, calculate_total_hits_points_for_player
from team_scoring import calculate_basic_team_points
from data_utils import get_lineups_from_boxscore, initialize_player_points_map
from player_scoring_rules import calculate_solo_homerun_points_for_player, calculate_total_hits_points_for_player


# Constants
TEAM_ID = 121
PROJECT_DIR = os.path.join(os.getcwd(), "new_york_mets")
WIDTH_TEAM = 6
WIDTH_PLAYER = 25
WIDTH_POINTS = 15
WIDTH_DETAILS = 50

batting = []
pitching = []

if not os.path.exists(PROJECT_DIR):
    os.mkdir(PROJECT_DIR)

last_game_id = statsapi.last_game(TEAM_ID)
last_game = statsapi.get('game', {'gamePk': last_game_id})

try:
    lineups = get_lineups_from_boxscore(last_game_id)
    game_boxscore_data = statsapi.boxscore_data(last_game_id)
    game_play_by_play_data = statsapi.game_scoring_play_data(last_game_id)

    team_info = game_boxscore_data['teamInfo']
    mets_team_id = TEAM_ID
    mets_location = 'away' if team_info['away']['id'] == mets_team_id else 'home'

    basic_batting_points = 0

    batting_totals = game_boxscore_data[f'{mets_location}BattingTotals']
    basic_batting_points += int(batting_totals['r'])
    basic_batting_points += int(batting_totals['h']) / 2

    triples_from_plays = 0
    is_top_inning = mets_location == 'away'
    hits_points = 0
    homerun_points = 0
    walks = 0

    for play in last_game['liveData']['plays']['allPlays']:
        if play['about']['isTopInning'] == is_top_inning and play['result']['type'] == 'atBat':
            event = play['result']['event']
            if event == 'Walk':
                walks += 1
            elif event == 'Hit':
                hits_points += 0.5
            elif event == 'Triple':
                triples_from_plays += 1
            elif event == 'Home Run':
                runners_on_base = 0
                for runner in play.get('runners', []):
                    if runner.get('movement', {}).get('originBase') is not None:
                        runners_on_base += 1
                
                if runners_on_base == 0:
                    homerun_points += 1
                elif 0 < runners_on_base < 3:
                    homerun_points += 2
                elif runners_on_base == 3:
                    homerun_points += 4

    # Calculate the individual points to the basic batting points total
    basic_batting_points += walks
    if walks >= 5:
        basic_batting_points += 2
    basic_batting_points += triples_from_plays * 3
    basic_batting_points += homerun_points
    final_team_points = calculate_basic_team_points(game_boxscore_data, last_game, mets_location)
    print(f"Final Team Points: {final_team_points}")

    final_points_map = initialize_player_points_map(lineups)
    final_points_map = calculate_solo_homerun_points_for_player(lineups, final_points_map)
    final_points_map = calculate_total_hits_points_for_player(lineups, final_points_map)


    with open(os.path.join(PROJECT_DIR, str(statsapi.last_game(TEAM_ID) ) + ".txt"), "w+", encoding="utf-8") as textfile:
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
        line = line + "\n" + "Final Team Points: " + str(final_team_points) + "pts" + "\n"
        line += "\n\n### Individual Player Points (Applied Rules) ###" + "\n"
        
        separator = "-" * (WIDTH_TEAM + WIDTH_PLAYER + WIDTH_POINTS + WIDTH_DETAILS + 9)
        header_row = (
            "| "
            f"{'Team':<{WIDTH_TEAM}} | "
            f"{'Player'[:WIDTH_PLAYER]:<{WIDTH_PLAYER}} | "
            f"{'Total Points':>{WIDTH_POINTS}} | "
            f"{'Details (HR, Runs, Hits)':<{WIDTH_DETAILS}}"
        )
        line += header_row + "\n"
        line += separator + "\n"
    
        for team in ['away', 'home']:
            for player in lineups.get(team, []):
                mlb_id = player.get('mlb_id')
                data = final_points_map.get(mlb_id, {'total_points': 0.0, 'breakdown': []})

                detail_str = " | ".join([
                    f"{item['rule_name']} ({item['value']}): {item['points']:.1f}pts" 
                    for item in data['breakdown']
                ])

                line += f"| {team.upper():<{WIDTH_TEAM}} | {player['name'][:WIDTH_PLAYER]:<{WIDTH_PLAYER}} | {data['total_points']:>{WIDTH_POINTS}} | {detail_str:<{WIDTH_DETAILS}}" + "\n"
                
                line += separator + "\n"

        line += "\n\n### RAW GAME DATA ###" + "\n"
        line += "\nBOXSCORE DATA: " + str(statsapi.boxscore_data(last_game_id)) + "\n"
        line += f"All Plays: {last_game['liveData']['plays']['allPlays']}" + "\n"
        line += "\n" + str(game_play_by_play_data['plays']) + "\n"
        line += "\n"

        textfile.write(line)
except Exception as e:
    print(f"Error fetching data from {last_game_id}: {e}")
    print("\n--- Full Traceback ---")
    print(traceback.format_exc()) 
    print("----------------------\n")