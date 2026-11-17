"""Box score based player rules (sections I, III and IV of the README)."""
from data_utils import add_points, parse_ip_to_outs, set_play_context, to_int
from situational_rules import play_snapshot

BASIC = 'Basic Stats'
PITCHING = 'Pitching'
UNUSUAL = 'Unusual'
DEDUCTION = 'Deduction'


def _batters(players):
    return [p for p in players if p.get('batting')]


def calculate_total_hits_points_for_player(players, pm):
    POINTS_PER_HIT = 0.5
    for p in _batters(players):
        hits = to_int(p['batting'].get('h'))
        if hits > 0:
            add_points(pm, p['mlb_id'], BASIC, 'Hits', hits, hits * POINTS_PER_HIT)


def calculate_total_triples_points_for_player(players, pm):
    POINTS_PER_TRIPLE = 3.0
    for p in _batters(players):
        triples = to_int(p['batting'].get('triples'))
        if triples > 0:
            add_points(pm, p['mlb_id'], BASIC, 'Triples', triples, triples * POINTS_PER_TRIPLE)


def calculate_total_runs_points_for_player(players, pm):
    POINTS_PER_RUN = 1.0
    for p in _batters(players):
        runs = to_int(p['batting'].get('r'))
        if runs > 0:
            add_points(pm, p['mlb_id'], BASIC, 'Runs', runs, runs * POINTS_PER_RUN)


def calculate_total_walks_points_for_player(players, pm):
    POINTS_PER_WALK = 1.0
    for p in _batters(players):
        walks = to_int(p['batting'].get('bb'))
        if walks > 0:
            add_points(pm, p['mlb_id'], BASIC, 'Walks', walks, walks * POINTS_PER_WALK)


def calculate_starter_points(players, pm, starter_id):
    """Starter rules: <=2 runs (min 5 IP), 7+ IP, complete game, and the <4 IP deduction."""
    POINTS_LOW_RUNS = 5.0
    POINTS_SEVEN_IP = 5.0
    POINTS_COMPLETE_GAME = 10.0
    MIN_OUTS_LOW_RUNS = 15
    SEVEN_IP_OUTS = 21
    COMPLETE_GAME_OUTS = 27
    SHORT_START_OUTS = 12

    starter = next((p for p in players if p['mlb_id'] == starter_id and p.get('pitching')), None)
    if starter is None:
        return

    stats = starter['pitching']
    outs = parse_ip_to_outs(stats.get('ip'))
    runs = to_int(stats.get('r'), default=99)
    ip = stats.get('ip')
    only_pitcher = sum(1 for p in players if p.get('pitching')) == 1

    if outs >= MIN_OUTS_LOW_RUNS and runs <= 2:
        add_points(pm, starter_id, PITCHING, 'Starter 2 Runs or Less (min 5 IP)', f'{ip} IP, {runs} R', POINTS_LOW_RUNS)
    if outs >= SEVEN_IP_OUTS:
        add_points(pm, starter_id, PITCHING, 'Starter 7+ IP', f'{ip} IP', POINTS_SEVEN_IP)
    if outs >= COMPLETE_GAME_OUTS or (only_pitcher and outs >= 24):
        add_points(pm, starter_id, PITCHING, 'Starter Complete Game', f'{ip} IP', POINTS_COMPLETE_GAME)
    if outs < SHORT_START_OUTS:
        add_points(pm, starter_id, DEDUCTION, 'Starter Under 4 IP', f'{ip} IP', -1.0)


def calculate_save_points_for_player(players, pm):
    """Save: +3, save without a hit or walk: +5, blown save: -2. Parsed from the pitcher note, e.g. '(S, 5)'."""
    SAVE_POINTS = 3.0
    CLEAN_SAVE_POINTS = 5.0
    BLOWN_SAVE_POINTS = -2.0

    for p in players:
        stats = p.get('pitching')
        if not stats:
            continue
        note = (stats.get('note') or '').strip('() ')
        tags = [t.strip() for t in note.split(',')]

        if 'BS' in tags:
            add_points(pm, p['mlb_id'], DEDUCTION, 'Blown Save', note, BLOWN_SAVE_POINTS)
        if 'S' in tags:
            hits, walks = to_int(stats.get('h'), 1), to_int(stats.get('bb'), 1)
            if hits == 0 and walks == 0:
                add_points(pm, p['mlb_id'], PITCHING, 'Save without a hit or walk', '0 H, 0 BB', CLEAN_SAVE_POINTS)
            else:
                add_points(pm, p['mlb_id'], PITCHING, 'Save', f'{hits} H, {walks} BB', SAVE_POINTS)


def calculate_strikeout_tracking_for_pitcher(players, pm):
    """Strikeouts score at the team level (16+); record them per pitcher for reporting and the 12+ rule."""
    POINTS_TWELVE_K = 5.0
    for p in players:
        stats = p.get('pitching')
        if not stats:
            continue
        strikeouts = to_int(stats.get('k'))
        if strikeouts > 0:
            add_points(pm, p['mlb_id'], PITCHING, 'Strikeout(s)', strikeouts, 0.0)
        if strikeouts >= 12:
            add_points(pm, p['mlb_id'], UNUSUAL, 'Pitcher 12+ Strikeouts', strikeouts, POINTS_TWELVE_K)


def track_earned_runs_for_player(players, pm):
    for p in players:
        if p.get('pitching'):
            add_points(pm, p['mlb_id'], PITCHING, 'Earned Runs', to_int(p['pitching'].get('er')), 0.0)


def calculate_unusual_batting_points(players, pm):
    """Cycle: +10, 3+ home runs: +5."""
    for p in _batters(players):
        b = p['batting']
        hits, doubles, triples, hrs = (to_int(b.get(k)) for k in ('h', 'doubles', 'triples', 'hr'))
        singles = hits - doubles - triples - hrs

        if singles > 0 and doubles > 0 and triples > 0 and hrs > 0:
            add_points(pm, p['mlb_id'], UNUSUAL, 'Hit for the Cycle', 1, 10.0)
        if hrs >= 3:
            add_points(pm, p['mlb_id'], UNUSUAL, '3+ Home Runs', hrs, 5.0)


def calculate_batter_strikeout_deduction(players, pm):
    for p in _batters(players):
        strikeouts = to_int(p['batting'].get('k'))
        if strikeouts >= 4:
            add_points(pm, p['mlb_id'], DEDUCTION, 'Struck Out 4+ Times', strikeouts, -4.0)


def calculate_relief_first_batter_walk_deduction(plays, side, starter_id, pm):
    """Relief pitcher walks the first batter he faces: -1 (play-by-play)."""
    seen = set()
    for ctx in plays:
        if ctx['side'] == side or not ctx['is_pa']:
            continue
        pitcher = ctx['pitcher_id']
        if pitcher in seen:
            continue
        seen.add(pitcher)
        if pitcher != starter_id and ctx['event_type'] in ('walk', 'intent_walk'):
            set_play_context(play_snapshot(ctx))
            add_points(pm, pitcher, DEDUCTION, 'Reliever Walks First Batter', 1, -1.0)
            set_play_context(None)
