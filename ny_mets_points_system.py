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

try:
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
    for play in last_game['liveData']['plays']['allPlays']:
        if play['about']['isTopInning'] == is_top_inning and play['result']['event'] == 'Triple':
            triples_from_plays += 1

    basic_batting_points += triples_from_plays * 3

    homerun_points = 0
    walks = 0
    for play in last_game['liveData']['plays']['allPlays']:
        # Check if the play is a Mets at-bat
        if play['about']['isTopInning'] == is_top_inning and play['result']['type'] == 'atBat':
            event = play['result']['event']
            if event == 'Walk':
                walks += 1
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

    if walks >= 5:
        basic_batting_points += walks
        basic_batting_points += 2
    else:
        basic_batting_points += walks

    basic_batting_points += homerun_points

    with open(os.path.join(PROJECT_DIR, str(statsapi.last_game(TEAM_ID) ) + ".txt"), "w+") as textfile:
        line = "The game is: " + str(statsapi.last_game(TEAM_ID))
        line = line + "\n" + "The team is: " + str(game_boxscore_data['teamInfo']) + "\n"
        line = line + "\n" + "Basic Batting Points: " + str(basic_batting_points) + "pts" + "\n"
        line = line + f"Triples (from plays): {triples_from_plays}" + "\n"
        line = line + f"Homerun Points: {homerun_points}" + "\n"
        line = line + f"Walks: {walks}" + "\n"
        line = line + f"All Plays: {last_game['liveData']['plays']['allPlays']}" + "\n"
        line = line + "\n" + str(game_play_by_play_data['plays']) + "\n"
        line = line + "\n"

        textfile.write(line)
        nextgame = statsapi.get('game', {'gamePk': statsapi.last_game(TEAM_ID)})
        textfile.write(str(nextgame))
except Exception as e:
    print(f"Error fetching data from {last_game_id}: {e}")