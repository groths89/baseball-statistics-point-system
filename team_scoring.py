from collections import defaultdict

def calculate_basic_team_points(boxscore, playbyplay, location):
    basic_batting_points = 0

    batting_totals = boxscore[f'{location}BattingTotals']
    basic_batting_points += int(batting_totals['r'])

    triples_from_plays = 0
    is_top_inning = (location == 'away')
    hits_points = int(batting_totals['h']) / 2
    homerun_points = 0
    walks = 0

    for play in playbyplay['liveData']['plays']['allPlays']:
        if play['about']['isTopInning'] == is_top_inning:
            event = play['result']['event']
            if event in ['Walk', 'Hit By Pitch']:
                walks += 1
            elif play['result']['type'] == 'atBat':
                if event == 'Triple':
                    triples_from_plays += 1
                elif event == 'Home Run':
                    runners_on_base = 0
                    for runner in play.get('runners', []):
                        if runner.get('movement', {}).get('originBase') is not None:
                            runners_on_base += 1
                
                    if runners_on_base == 0: # Solo HR
                        homerun_points += 1
                    elif 0 < runners_on_base < 3: # 2-run or 3-run HR
                        homerun_points += 2
                    elif runners_on_base == 3: # Grand Slam
                        homerun_points += 4

    basic_batting_points += walks
    if walks >= 5:
        basic_batting_points += 2
    basic_batting_points += hits_points
    basic_batting_points += triples_from_plays * 3
    basic_batting_points += homerun_points
    print(f"Basic Batting Points: {basic_batting_points}")
    return basic_batting_points

def calculate_team_totals(final_points_map):
    """Aggregates individual player scores into total team scores."""
    team_totals = defaultdict(float)

    for data in final_points_map.values():
        team_name = data.get('team')
        total_points = data.get('total_points', 0.0)

        if team_name:
            team_totals[team_name] += total_points

    return team_totals

def calculate_team_strikeout_for_pitchers_bonus(final_points_map, lineups, team_totals, TEAM_LOCATION):
    """Awards +1 point to the team total of the pitchers get 16 or more strikeouts"""
    BONUS_POINTS = 1.0
    MIN_STRIKEOUTS = 16
    team_strikeouts = 0

    if TEAM_LOCATION not in ['home', 'away']:
        return team_totals

    for player in lineups[TEAM_LOCATION]:
        mlb_id = player.get('mlb_id')
        player_data = final_points_map.get(mlb_id, {})
        
        for item in player_data.get('breakdown', []):
            if item.get('rule_category') == 'Pitching' and item.get('rule_name') == 'Strikeout(s)':
                team_strikeouts += item.get('value', 0)
                break 

    if team_strikeouts >= MIN_STRIKEOUTS:
        if 'Total Points' not in team_totals:
            team_totals['Total Points'] = 0.0

        team_totals['Total Points'] += BONUS_POINTS
        
        print(f"✅ TEAM STRIKEOUT BONUS: +{BONUS_POINTS} added to team total for recording {team_strikeouts} strikeouts.")
    else:
        print(f"❌ TEAM STRIKEOUT CHECK: {team_strikeouts} strikeouts recorded, falling short of the {MIN_STRIKEOUTS} minimum.")
    
    return team_totals