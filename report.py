"""Text report for a scored game."""
WIDTH_PLAYER = 25
WIDTH_POS = 8
WIDTH_POINTS = 8


def _fmt(points):
    return f'{points:+.1f}'


def build_report(result):
    lines = [
        f"Game {result['game_id']} ({result['game_date']}): {result['team_name']} "
        f"{'vs' if result['side'] == 'home' else '@'} {result['opponent']}  "
        f"{result['runs_for']}-{result['runs_against']} {'W' if result['won'] else 'L'}",
        '',
        '### Individual Player Points (Applied Rules) ###',
        f"| {'Player':<{WIDTH_PLAYER}} | {'Pos':<{WIDTH_POS}} | {'Points':>{WIDTH_POINTS}} | Details",
        '-' * 110,
    ]
    for player in result['lineup']:
        data = result['players'].get(player['mlb_id'], {'total_points': 0.0, 'breakdown': []})
        scoring = [i for i in data['breakdown'] if i['points'] != 0]
        detail = ' | '.join(f"{i['rule_name']} ({i['value']}): {_fmt(i['points'])}" for i in scoring)
        lines.append(
            f"| {player['name'][:WIDTH_PLAYER]:<{WIDTH_PLAYER}} | {player['position'][:WIDTH_POS]:<{WIDTH_POS}} "
            f"| {data['total_points']:>{WIDTH_POINTS}.1f} | {detail}"
        )

    lines += ['', '### Team Events ###']
    if result['team_breakdown']:
        for item in result['team_breakdown']:
            lines.append(f"  {item['rule_category']:<12} {item['rule_name']} ({item['value']}): {_fmt(item['points'])}")
    else:
        lines.append('  (none)')

    lines += [
        '',
        '### Team Totals ###',
        f"  Player points: {result['player_points']:.1f}",
        f"  Team points:   {result['team_points']:.1f}  (includes {result['carry_in']:.1f} carried over)",
        f"  TOTAL:         {result['total']:.1f}",
        f"  Carry over into next game: {result['carry_out']:.1f}",
        '',
    ]
    return '\n'.join(lines)
