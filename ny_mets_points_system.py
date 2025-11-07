import statsapi
import os
import traceback
import json

from team_scoring import (
    calculate_basic_team_points, 
    calculate_team_totals, 
    calculate_team_strikeout_for_pitchers_bonus,
    calculate_bullpen_zero_runs_bonus
)
from data_utils import get_lineups_from_boxscore, get_starters_from_boxscore, initialize_player_points_map
from player_scoring_rules import (
    calculate_solo_homerun_points_for_player, 
    calculate_total_hits_points_for_player, 
    calculate_total_triples_points_for_player, 
    calculate_total_runs_points_for_player, 
    calculate_total_walks_points_for_player, 
    calculate_starter_ip_points_for_player, 
    calculate_starter_two_runs_or_less_points_for_player, 
    calculate_starter_pitches_complete_game_points_for_player,
    calculate_strikeouts_points_for_pitcher,
    calculate_save_points_for_player,
    track_earned_runs_for_player
)





# Constants
TEAM_ID = 121
TEAM_LOCATION = None
TEAM_NAME = None
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
game_boxscore_data = statsapi.boxscore_data(last_game_id)
last_game = statsapi.get('game', {'gamePk': last_game_id})

if game_boxscore_data['teamInfo']['home']['id'] == TEAM_ID:
    TEAM_LOCATION = 'home'
    TEAM_NAME = game_boxscore_data['teamInfo']['home']['teamName']
elif game_boxscore_data['teamInfo']['away']['id'] == TEAM_ID:
    TEAM_LOCATION = 'away'
    TEAM_NAME = game_boxscore_data['teamInfo']['away']['teamName']
else:
    print(f"WARNING: Target Team ID {TEAM_ID} did not play in game {last_game_id}. Displaying all players.")
    TARGET_TEAM_LOCATION = 'all'

team_total_key = f"{TEAM_LOCATION.capitalize()} Total"

try:
    # 1. Data Fetching
    starters = get_starters_from_boxscore(game_boxscore_data)
    lineups = get_lineups_from_boxscore(last_game_id)
    final_points_map = initialize_player_points_map(lineups)

    # 2. Run all of the individual batting points
    final_points_map = calculate_solo_homerun_points_for_player(lineups, final_points_map)
    final_points_map = calculate_total_hits_points_for_player(lineups, final_points_map)
    final_points_map = calculate_total_triples_points_for_player(lineups, final_points_map)
    final_points_map = calculate_total_runs_points_for_player(lineups, final_points_map)
    final_points_map = calculate_total_walks_points_for_player(lineups, final_points_map)


    # 3. Run all of the individual pitching points
    final_points_map = calculate_starter_ip_points_for_player(lineups, final_points_map, game_boxscore_data)
    final_points_map = calculate_starter_two_runs_or_less_points_for_player(lineups, final_points_map, game_boxscore_data)
    final_points_map = calculate_starter_pitches_complete_game_points_for_player(lineups, final_points_map, game_boxscore_data)
    final_points_map = calculate_strikeouts_points_for_pitcher(lineups, final_points_map)
    final_points_map = track_earned_runs_for_player(lineups, final_points_map)
    final_points_map = calculate_save_points_for_player(final_points_map, game_boxscore_data)


    # 3. Calculating all of the team totals together
    team_totals = calculate_team_totals(final_points_map, lineups)
    team_totals = calculate_team_strikeout_for_pitchers_bonus(final_points_map, lineups, team_totals, TEAM_LOCATION, team_total_key)
    team_totals = calculate_bullpen_zero_runs_bonus(final_points_map, lineups, team_totals, starters, TEAM_LOCATION, team_total_key)

    print(team_totals)

    print(f"{TEAM_LOCATION.capitalize()} Team Totals: {team_totals[TEAM_LOCATION]}")

    with open(os.path.join(PROJECT_DIR, str(last_game_id) + ".txt"), "w+", encoding="utf-8") as textfile:
        line = f"The game is: {last_game_id}"
        line += f"\nThe home team is: {game_boxscore_data['teamInfo']['home']['teamName']}"
        line += f"\nThe away team is: {game_boxscore_data['teamInfo']['away']['teamName']}"
        line = line + "\n" + "The lineup is: " + str(lineups) + "\n"
        line += "\n\n### Individual Player Points (Applied Rules) ###" + "\n"
        
        separator = "-" * (WIDTH_TEAM + WIDTH_PLAYER + WIDTH_POINTS + WIDTH_DETAILS + 9)
        header_row = (
            "| "
            f"{'Team':<{WIDTH_TEAM}} | "
            f"{'Player'[:WIDTH_PLAYER]:<{WIDTH_PLAYER}} | "
            f"{'Position':<{WIDTH_PLAYER}} | "
            f"{'Total Points':>{WIDTH_POINTS}} | "
            f"{'Details (HR, Runs, Hits)':<{WIDTH_DETAILS}}"
        )
        line += header_row + "\n"
        line += separator + "\n"

        teams_to_loop = ['away', 'home'] if TEAM_LOCATION == 'all' else [TEAM_LOCATION]
    
        for team in teams_to_loop:
            for player in lineups.get(team, []):
                mlb_id = player.get('mlb_id')
                data = final_points_map.get(mlb_id, {'total_points': 0.0, 'breakdown': []})

                detail_str = " | ".join([
                    f"{item['rule_name']} ({item['value']}): {item['points']:.1f}pts" 
                    for item in data['breakdown']
                ])

                line += f"| {team.upper():<{WIDTH_TEAM}} | {player['name'][:WIDTH_PLAYER]:<{WIDTH_PLAYER}} | {player['position'][:WIDTH_PLAYER]:<{WIDTH_PLAYER}}| {data['total_points']:>{WIDTH_POINTS}} | {detail_str:<{WIDTH_DETAILS}}" + "\n"
                
                line += separator + "\n"
        line += "\n\n### Team Totals ###" + "\n"
        line += "\n"
        W_HT, W_HP = 30, 20
        W_TT, W_TP = 15, 20
        team_separator = "-" * (W_HT + W_HP + 9)

        line += f"| {'Team'[:W_HT]:<{W_HT}} | {'Total Points':<{W_HP}} |" + "\n"
        line += team_separator + "\n"
        for team_location in teams_to_loop:
            for team, total_points in team_totals.items():
                print(f"Team: {team}, Total Points: {total_points}")
                line += f"| {game_boxscore_data['teamInfo'][team_location]['teamName'][:W_TT]:<{W_TT}}{team.upper():<{W_TT}} | {total_points:>{W_TP}} |" + "\n"
                line += team_separator + "\n"
        line += "\n"


        line += "\n\n### RAW GAME DATA ###" + "\n"
        line += "\nBOXSCORE DATA: " + str(statsapi.boxscore_data(last_game_id)) + "\n"
        line += f"All Plays: {last_game['liveData']['plays']['allPlays']}" + "\n"
        line += "\n"

        textfile.write(line)
except Exception as e:
    print(f"Error fetching data from {last_game_id}: {e}")
    print("\n--- Full Traceback ---")
    print(traceback.format_exc()) 
    print("----------------------\n")