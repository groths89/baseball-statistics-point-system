"""Team level rules and aggregation (sections I, III, IV and V of the README)."""
from data_utils import opposite, parse_ip_to_outs, to_int
from situational_rules import REACH_EVENTS

BASIC = 'Basic Stats'
PITCHING = 'Pitching'
UNUSUAL = 'Unusual'
DEDUCTION = 'Deduction'
CARRY = 'Carry Over'


def calculate_team_walks_bonus(boxscore, side, team_events):
    walks = to_int(boxscore[f'{side}BattingTotals'].get('bb'))
    if walks > 5:
        team_events.append((BASIC, 'Team Walks (more than 5)', walks, 2.0))


def calculate_team_strikeout_for_pitchers_bonus(boxscore, side, team_events):
    strikeouts = to_int(boxscore[f'{side}PitchingTotals'].get('k'))
    if strikeouts >= 16:
        team_events.append((PITCHING, 'Team Pitchers 16+ Strikeouts', strikeouts, 1.0))


def calculate_bullpen_zero_runs_bonus(players, starter_id, team_events):
    relievers = [p for p in players if p.get('pitching') and p['mlb_id'] != starter_id]
    if relievers and sum(to_int(p['pitching'].get('r'), 1) for p in relievers) == 0:
        team_events.append((PITCHING, 'Bullpen Gives Up 0 Runs', len(relievers), 5.0))


def calculate_team_deductions(boxscore, side, linescore_innings, team_events):
    batting_k = to_int(boxscore[f'{side}BattingTotals'].get('k'))
    if batting_k >= 10:
        team_events.append((DEDUCTION, 'Team Struck Out 10+ Times', batting_k, -(batting_k - 9.0)))

    walks_issued = to_int(boxscore[f'{side}PitchingTotals'].get('bb'))
    if walks_issued >= 5:
        team_events.append((DEDUCTION, 'Pitchers Walk 5+ Batters', walks_issued, -(walks_issued - 4.0)))

    longest_drought = current = 0
    for inning in linescore_innings:
        runs = inning.get(side, {}).get('runs')
        if runs == 0:
            current += 1
            longest_drought = max(longest_drought, current)
        else:
            current = 0
    if longest_drought >= 6:
        team_events.append((DEDUCTION, 'No Runs For 6+ Innings', longest_drought, -1.0))


def calculate_unusual_team_events(plays, boxscore, side, players, team_events):
    """No-hitter/perfect game, comeback wins and walk-offs. Returns the carry over points for the next game."""
    carry_out = 0.0
    other = opposite(side)

    pitching_totals = boxscore[f'{side}PitchingTotals']
    outs = sum(parse_ip_to_outs(p['pitching'].get('ip')) for p in players if p.get('pitching'))
    if outs >= 27 and to_int(pitching_totals.get('h')) == 0:
        opponent_reached = any(c['side'] == other and c['event_type'] in REACH_EVENTS for c in plays)
        name = 'Pitchers Throw No-Hitter' if opponent_reached else 'Pitchers Throw Perfect Game'
        team_events.append((UNUSUAL, name, 1, 10.0))
        carry_out += 2.0

    if not plays:
        return carry_out

    final = plays[-1]
    won = final['score_after'][side] > final['score_after'][other]
    if not won:
        return carry_out

    last_inning = final['inning']

    def max_deficit(first_inning):
        deficits = [0]
        for c in plays:
            if c['inning'] >= first_inning:
                deficits.append(c['score_before'][other] - c['score_before'][side])
        return max(deficits)

    if max_deficit(last_inning) >= 5:
        team_events.append((UNUSUAL, 'Comeback From 5+ Run Deficit In Last Inning', max_deficit(last_inning), 20.0))
        carry_out += 2.0
    elif max_deficit(last_inning - 1) >= 10:
        team_events.append((UNUSUAL, 'Comeback From 10+ Run Deficit In Last 2 Innings', max_deficit(last_inning - 1), 20.0))
        carry_out += 2.0

    if side == 'home' and not final['is_top'] and final['score_before'][side] <= final['score_before'][other]:
        team_events.append((UNUSUAL, 'Walk-Off Win', 1, 5.0))
        carry_out += 2.0

    return carry_out


def summarize_team(player_points_map, team_events, carry_in, carry_out):
    """Combines player points, team level events and carry over points into the team's game total."""
    player_points = sum(d['total_points'] for d in player_points_map.values())
    breakdown = [
        {'rule_category': e[0], 'rule_name': e[1], 'value': e[2], 'points': e[3], 'play': e[4] if len(e) > 4 else None}
        for e in team_events
    ]
    if carry_in:
        breakdown.append({'rule_category': CARRY, 'rule_name': 'Carry Over From Previous Game', 'value': carry_in, 'points': carry_in, 'play': None})

    team_points = sum(item['points'] for item in breakdown)
    return {
        'player_points': player_points,
        'team_points': team_points,
        'team_breakdown': breakdown,
        'carry_in': carry_in,
        'carry_out': carry_out,
        'total': player_points + team_points,
    }
