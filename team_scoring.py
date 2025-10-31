def calculate_basic_team_points(boxscore, playbyplay, location):
    basic_batting_points = 0

    batting_totals = boxscore[f'{location}BattingTotals']
    basic_batting_points += int(batting_totals['r'])
    basic_batting_points += int(batting_totals['h']) / 2

    triples_from_plays = 0
    is_top_inning = location
    hits_points = 0
    homerun_points = 0
    walks = 0

    for play in playbyplay['liveData']['plays']['allPlays']:
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

