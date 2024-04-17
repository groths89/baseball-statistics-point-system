# Where to Start

- From the function `statsapi.last_game(teamID)` then use this in the function right below

- From the function `statsapi.boxscore(gamenumber)`

- `homePitchers`

- `homeBattingNotes`

- `homePitchingTotals`

- `homeBattingTotals`

- `teamStats`

- `{'title': 'FIELDING', 'fieldList': [{'label': 'DP', 'value': '2 (Baty-McNeil-Alonso; Lindor-McNeil-Alonso).'}]}], 'note': []}`

## For points start with Basic Stats

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
