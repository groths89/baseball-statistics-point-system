import statsapi
import os

batting = []
pitching = []

dest_dir = os.path.join(os.getcwd(), "new_york_mets")
if not os.path.exists(dest_dir):
    os.mkdir(dest_dir)

with open(os.path.join(dest_dir, str(statsapi.last_game(121) ) + ".txt"), "w+") as textfile:
    line = "The game is: " + str(statsapi.last_game(121))
    textfile.write(line)
    nextgame = statsapi.get('game', {'gamePk': statsapi.last_game(121)})
    textfile.write(str(nextgame))