# ⚾ Baseball Statistics Point System: New York Mets Analysis

## Project Overview

This project is a custom analytical tool designed to score the quality of play for the New York Mets beyond standard Wins and Losses. It utilizes the MLB Stats API, and the Python package `MLB-StatsAPI` to process Box Score and Play-by-Play data, applying a complex, situational point system to measure team momentum, clutch performance, and defensive excellence. The final goal is to create a Full-Stack application that visualizes these custom scores and potentially correlates them with advanced metrics like WAR.

## 🛠️ Technical Stack (MVP)

| Area             | Technology                | Purpose    |
| ---------------- | ------------------------- | ---------- |
| Data Acquisition | Python (statsapi) Library | Fetch game schedules, box scores, and play-by-play data.|
| Backend/Logic    | Python        | Core scoring engine and data parsing logic. |
| Data Persistence | SQLite (`new_york_mets/points.db`) | Stores each game's totals and every point event. |
| API              |  |  |
| Frontend/Visual  |  |  |

## 🚀 Getting Started

This project gets a schedule for the given team, in one instance it is the New York Mets. It processes the data and calculates points adding and subtracting a certain number of points for each event a player and team does. If a player does well in the game they can bring value to a team's success.

1. Fetch Schedule: Use `statsapi.schedule(team=121)` to get all completed game IDs.

2. Fetch Data: For each game ID, retrieve two data sets: `statsapi.boxscore_data()` and `statsapi.last_game(teamId)` (for totals) and `statsapi.get('game_play_by_play')` (for situational details).

3. Calculate Scores: Apply the scoring logic defined below.

4. Persist: Store the game ID and the final point breakdown into the database.

### Running it

```
pip install -r requirements.txt
python ny_mets_points_system.py                    # latest completed game
python ny_mets_points_system.py --game 776450      # one game
python ny_mets_points_system.py --season 2025      # every completed regular season game, in order (carry over points flow game to game)
python ny_mets_points_system.py --start 2025-09-01 --end 2025-09-14
python ny_mets_points_system.py --summary          # stored results and average points per game
```

A report for each game is written to `new_york_mets/<gameId>.txt` and the results are saved to SQLite (`--no-save` to skip). Use `--team` to score another team.

Code layout: `data_utils.py` (box score parsing), `player_scoring_rules.py` (box score rules), `situational_rules.py` (play-by-play rules), `team_scoring.py` (team rules and carry over), `game_scoring.py` (applies everything to a game), `storage.py` (SQLite), `report.py` (text report).

### Moments (off-field events)

```
python moments.py add --date 2025-06-12 --headline "..." --type media --url https://... --note "..." --team 121
python moments.py list
python moments.py delete 1
```

The eight most covered games of each season are also pinned automatically (blue), so only off-field events that aren't in the headlines need a manual moment. Each moment shows as a pin on the Season Trends chart at the first game on or after its date, with that game's result and points. Omit `--team` for a moment that applies to every team.

### Media (headlines around each game)

```
python media.py --season 2024                  # MLB recap/highlights + Google News for each scored game without media yet
python media.py --game 745811 --team 121
python media.py --start 2024-06-10 --end 2024-06-20 --source google --refresh
```

Needs no API keys. Only titles, links, publisher and time are saved (`media_items` table), never article text. The Google News story count (and number of outlets) is stored per game as its buzz and compared with points on the Insights page. Doubleheaders share a count because the search is by date. They show up under "Around the game" on each game page and as a headline under each game on the Insights page.

### API

```
uvicorn api:app --reload        # docs at http://localhost:8000/docs
```

Read-only JSON over the SQLite database. Set `POINTS_DB` to use another database file and `CORS_ORIGINS` (comma separated) for your frontend's origin; the default is Astro's dev server, `http://localhost:4321`.

| Endpoint | Purpose |
| -------- | ------- |
| `GET /teams?season=` | Teams with games, wins, total and average points |
| `GET /games?team_id=&season=&start=&end=&sort=date\|points&limit=&offset=` | Game list |
| `GET /games/{game_id}?team_id=` | One team's game: totals, category totals, player totals, every point event |
| `GET /games/{game_id}/breakdown?team_id=` | Everything the Game Breakdown screen needs: five-category ledger, batter/pitcher tables with percentile grades, play log |
| `GET /search?q=&team_id=&limit=` | Quick search: players by name, games by opponent/team/date |
| `GET /players?team_id=&season=&min_games=&sort=total\|per_game&limit=&offset=` | Player leaderboard |
| `GET /insights/outliers?team_id=&season=&limit=` | Insights: hidden gems (losses with high points), smoke and mirrors (wins with low points), and win rate by points quartile |
| `GET /games/{game_id}/media?team_id=` | Recap, highlight videos and news headlines collected for a game |
| `GET /insights/buzz?team_id=&season=&limit=` | Media coverage per game vs. points: correlations, most covered games, and high-scoring games that got little coverage |
| `GET /teams/{team_id}/buzz-pins?season=&limit=` | The most covered games of a season (one per date), pinned automatically on Season Trends |
| `GET /moments?team_id=&season=` | Off-field moments (media, culture, trades) pinned on the Season Trends timeline |
| `GET /teams/{team_id}/trend?season=&window=` | Points per game with a rolling average |

All endpoints work for any team stored in the database, so adding more teams only requires scoring them with `--team`.

### Frontend (Astro)

The `frontend/` folder is an Astro app (dark and light themes) that renders the Game Breakdown screen from the API. It needs Node >= 22.23.4.

```bash
uvicorn api:app --reload            # terminal 1, http://localhost:8000
cd frontend && cp .env.example .env # set PUBLIC_API_URL if the API is elsewhere
npm install && npm run dev          # terminal 2, http://localhost:4321
```

Pages are server-rendered, so a production build needs a deployment adapter (for Cloudflare, `@astrojs/cloudflare`), which is not set up yet. The opponent's points and the margin only appear once both teams in a game have been scored.

### Interpretation notes and known gaps

- "Starter gives up 2 runs or less" uses runs (not earned runs) and requires at least 5 IP.
- "Team walks" applies at more than 5 walks. Strikeout deductions: 10 Ks = -1, each extra K = -1 more. Walk deduction: 5 walks = -1, each extra = -1 more.
- Long at-bats: 10+ pitches = 1 + 1 per pitch past 10; if the batter reaches base it is 2 + 1 per pitch past 10 instead.
- Double play that ends the inning is worth 3 (instead of 2) when a runner was in scoring position and no run scored on the play.
- Comeback/walk-off rules check the final inning (and last 2 innings) of the game; a comeback is worth 20 once.
- Not detectable from the API data and therefore not scored: diving plays, robbing a home run, and an outfielder backing up an errant throw to throw out a runner.

### Usages
- Used `statsapi.last_game(teamID)` and `statsapi.get('game', {'gamePk': last_game_id})` to get the latest game of the team being analyzed.

- Used `statsapi.boxscore_data(gamenumber)` to get both the batting totals and the pitching totals of the box score.

- Used `homePitchingTotals` and `awayPitchingTotals` for basic pitching stats.

- Used `homeBattingTotals` and `awayBattingTotals` for basic batting stats.

## 💯 Custom Point System

The scoring system is divided into five main categories: Basic Stats (Totals), Situational Play, Unusual and Miraculous, Deductions, and Carry Over. Then we would make a correlation to how well the player did by looking at advanced stats and comparing the numbers.

Why would we use this to find the value a player provides to a team to a successful season, this point system would add value to a team’s value together. Baseball is a team sport, every player needs to work together to produce quality baseball. You could measure a player’s performance by seeing how many points they can get like a grade rubric. You can also calculate the difference between a player’s WAR and how many points a player gets a team per game. These points are more about quantifying the advanced stats of a player then really getting the most points. Over an entire 162 game season you can look at statistical trends of the point system.

### I. BASIC STATS (TOTALS)

| Stat       | Points Given |
| ---------- | ------------ |
| Batting    | Total: 14+   |
| Home-runs	 |              |
| Solo	     | 1 point      |
| Runners On | 2 points     |
| Grand slam | 4 points     |
| Runs/Hits	 |              | 
| Total Runs | 1 point for each run scored |
| Total Hits | .5 a point for each hit |
| Triple 	   | 3 points for each triple |
| Walks	     | 1 point for each walk recorded |
| Total Walks |	If more than 5 walks get 2 points |
| Pitching	 | Total: 34    |
| Overall	   |              |
| Total Strikeouts for team |	If team gets 16 strikeouts or more add 1 point |
| Starters	 |              |
| Gives up 2 runs or less |	5 points |
| Goes 7+ innings |	5 points |
| Pitches complete game |	10 points |
| Relievers	|               |
| Bullpen gives up 0 runs |	5 points |
| Closer completes save	| 3 points |
| Closer completes save without giving up hit or walk |	5 points |


### II. ALL THE SMALL THINGS/SITUATIONAL BASEBALL

| Stat       | Points Given |
| ---------- | ------------ |
| Offensive  | Total: 17+   |
| Batters	   |              |
| 2 Out Hit	 | 1 point      |
| 2 out hit scores run(s) | 2 points for each run scored |
| Hit scores run to take the lead |	1 point |
| Batter walks with 2 outs and no one on base |	1 point |
| Batter works count to 10+ pitches	| 1 point for each pitch after 10 add 1 point |
| Batter works count to 10+ pitches and gets on base | 2 points + 1 point for each pitch after 10 |
| Sac fly/ground ball/bunt advances runner into scoring position | 1 point |
| Sac fly scores run |	2 point |
| Base running 	    |         |
| Runner advances from 1st to 3rd on a single	| 1 point |
| Runner advances on throw to another base | 1 point |
| Runner advances on errant throw or passed ball | 1 point |
| Stolen base |	1 point |
| Team Overall |  |	
| Team records 5 or more straight hits and/or walks |	2 points |
| Team scores 4+ runs in a row without an out	| 2 points |
| Defensive |	Total: 11+ |
| Pitchers	|  |
| Pitcher picks off runner on base | 1 point |
|Pitcher gets out of inning without runs scored when there’s runner(s) in scoring position | 1 point |
| Pitcher gets out of inning without runs scored, when there’s 0 outs and runner(s) in scoring position | 2 points |
| Infielder |  |	
| Catcher throws out runner trying to steal base |	1 point |
| Outfielder |  |
| Outfield assist |	1 point |
| Outfield assist at home plate | 2 points |
| Outfielder backs up errant throw and throws runner out |	1 point |
| Team Overall |  |	
| Team records double play | 2 points |
| Team records double play to end inning and prevent runs from scoring | 3 points |


### III. THE UNUSUAL & MIRACULOUS

| Stat       | Points Given |
| ---------- | ------------ |
| Batters	   |              |
| Player hits for cycle	| 10 points |
| Player hits 3+ home runs in game |	5 points |
| Pitchers	 |              |
| Pitcher strikes out 12+ in game |	5 points |
| Pitcher(s) pitch perfect game or no hitter | 10 points |
| Fielders   |              |	
| Infielder/outfielder makes diving play for out | 3 points |
| Outfielder robs a home run | 5 points |
| Team Overall |  |	
| Team turns triple play | 10 points |
| Team comes back from 5+ run deficit in last inning |	20 points |
| Team comes back from 10+ deficit in last 2 innings | 20 points |
| Team has walk off win	| 5 points |


### IV. POINTS DEDUCTED

| Stat       | Points Given |
| ---------- | ------------ |
| Offensive  | Total:       |
| Batters    |	            |
| Player strikes out 4+ times in game |	-4 points |
| Team Overall |  |	
| Team is struck out 10+ times in a game | -1 points plus subtract 1 point for each strikeout after the 10 |
| Team doesn’t score a run(s) for 6+ innings |	-1 point |
| Defensive |               |	
| Errors |	-1 point        |
| Passed balls |	-1 point  |
| Wild pitch	 | -1 point   |
| Starting pitcher doesn’t complete 4+ innings | -1 point |
| Relief pitcher walks first batter he faces	| -1 point |
| Pitcher(s) walk 5+ batters in a game |	-1 point and subtract 1 point for each walk after 5 walks |
| Closer blows save opportunity |	-2 points |


### V. CARRY OVER POINTS

| Stat       | Points Given |
| ---------- | ------------ |
| A walk off win |	2 points into next game |
| Team comes back from 5+ run deficit in last inning |	2 points into next game |
| Team comes back from 10+ run deficit in last 2 innings | 2 points into next game |
| Pitcher pitches perfect game/no hitter | 2 points into next game |


## Notes for development

- Initialize a dictionary with keys, and values:
  - Batting : []
  - Pitching : []
- Batting stats:
  - Solo Homerun add 1 point to homeruns:
  - Runners on more than 0 and less than 3 add 2 points to homeruns:
  - Grand Slam have runners on equal to 3 add 4 points to homeruns:
  - Look at Boxscore stats and add the Total Runs to totalruns:
  - Look at Boxscore stats and add Total Hits divided by 2 to totalhits:
  - Add 3 points if see any triples
  - Add 1 point for each walk in total walks stat cat
  - walks greater than 5 add 2 points to totalwalks:
- Pitching stats:
  - Add 1 point to a cat called total_strikeouts if sees greater than or equal to 16 in whole list of strikeouts.
  - Add 5 points to cat called starting_pitcher if the starting pitcher run total is less than or equal to 2
  - Add 5 points to cat called starting_pitcher if the IP is greater than or equal to 7
  - Add 10 points to cat called starting_pitcher if the IP is equal to 9
  - Add 5 points to cat called relief_pitchers if the sum of all other pitchers runs is equal to 0
  - Add 3 points to cat called relief_pitchers if last inning is 9 and team is winning team
  - Add 5 points if last pitcher on home team is in 9th inning and the amount of hits is equal to 0 and the amount of walks is equal to 0
