"""Play-by-play based rules (situational, defensive, unusual and deduction events)."""
from data_utils import add_points, opposite, set_play_context

SITUATIONAL = 'Situational'
DEFENSE = 'Defense'
BASIC = 'Basic Stats'
UNUSUAL = 'Unusual'
DEDUCTION = 'Deduction'

HIT_EVENTS = {'single', 'double', 'triple', 'home_run'}
WALK_EVENTS = {'walk', 'intent_walk'}
REACH_EVENTS = HIT_EVENTS | WALK_EVENTS | {'hit_by_pitch', 'field_error', 'catcher_interf', 'fielders_choice'}
NON_PA_PREFIXES = (
    'pickoff', 'caught_stealing', 'stolen_base', 'wild_pitch', 'passed_ball', 'balk',
    'other_advance', 'defensive_indiff', 'other_out', 'runner_placed',
)
BASE_ORDER = {'1B': 1, '2B': 2, '3B': 3, 'score': 4}


def annotate_plays(all_plays):
    """
    Adds game state to every play: outs/bases/score before and after, who batted
    and pitched, how many pitches the plate appearance took and the runs scored.
    """
    annotated = []
    half_key = None
    outs = 0
    post_bases = set()
    away_score = home_score = 0

    for play in all_plays:
        about = play['about']
        runners = play.get('runners', [])
        matchup = play.get('matchup', {})
        key = (about['inning'], about['isTopInning'])

        first_in_half = key != half_key
        if first_in_half:
            half_key = key
            outs = 0
            # Extra-inning placed runners show up as runners with an origin base
            pre_bases = {r['movement']['originBase'] for r in runners if r['movement'].get('originBase')}
        else:
            pre_bases = set(post_bases)

        outs_on_play = sum(1 for r in runners if r['movement'].get('isOut'))
        scored_ids = {r['details']['runner']['id'] for r in runners if r['movement'].get('end') == 'score'}

        post_bases = set()
        for slot, base in (('postOnFirst', '1B'), ('postOnSecond', '2B'), ('postOnThird', '3B')):
            if matchup.get(slot):
                post_bases.add(base)

        result = play.get('result', {})
        side = 'away' if about['isTopInning'] else 'home'
        new_away = result.get('awayScore', away_score)
        new_home = result.get('homeScore', home_score)

        event_type = result.get('eventType') or ''
        annotated.append({
            'play': play,
            'index': about.get('atBatIndex'),
            'inning': about['inning'],
            'is_top': about['isTopInning'],
            'side': side,
            'half_key': key,
            'first_in_half': first_in_half,
            'outs_before': outs,
            'outs_after': min(3, outs + outs_on_play),
            'outs_on_play': outs_on_play,
            'pre_bases': pre_bases,
            'post_bases': post_bases,
            'score_before': {'away': away_score, 'home': home_score},
            'score_after': {'away': new_away, 'home': new_home},
            'runs_scored': len(scored_ids),
            'event_type': event_type,
            'raw_description': result.get('description') or '',
            'description': (result.get('description') or '').lower(),
            'batter_id': matchup.get('batter', {}).get('id'),
            'pitcher_id': matchup.get('pitcher', {}).get('id'),
            'pitches': sum(1 for e in play.get('playEvents', []) if e.get('isPitch')),
            'is_pa': bool(event_type) and not event_type.startswith(NON_PA_PREFIXES),
            'runners': runners,
        })

        outs = min(3, outs + outs_on_play)
        away_score, home_score = new_away, new_home

    return annotated


def play_snapshot(ctx):
    """The part of a play stored with each point event so the play log can be rebuilt."""
    return {
        'at_bat_index': ctx['index'],
        'inning': ctx['inning'],
        'is_top': ctx['is_top'],
        'outs': ctx['outs_before'],
        'away_score': ctx['score_after']['away'],
        'home_score': ctx['score_after']['home'],
        'description': ctx['raw_description'],
    }


def _has_risp(bases):
    return '2B' in bases or '3B' in bases


def calculate_homerun_points(plays, side, pm):
    """Solo HR: 1, HR with runners on: 2, grand slam: 4 (credited to the batter)."""
    for ctx in plays:
        if ctx['side'] != side or ctx['event_type'] != 'home_run':
            continue
        set_play_context(play_snapshot(ctx))
        runners_on = len({r['details']['runner']['id'] for r in ctx['runners'] if r['movement'].get('originBase')})
        if runners_on == 0:
            name, points = 'Solo Homerun', 1.0
        elif runners_on < 3:
            name, points = 'Homerun With Runners On', 2.0
        else:
            name, points = 'Grand Slam', 4.0
        add_points(pm, ctx['batter_id'], BASIC, name, f'{runners_on} on', points)
    set_play_context(None)


def calculate_offensive_situational_points(plays, side, pm, team_events):
    for ctx in plays:
        if ctx['side'] != side:
            continue
        set_play_context(play_snapshot(ctx))
        batter, event = ctx['batter_id'], ctx['event_type']
        is_hit = event in HIT_EVENTS

        if is_hit and ctx['outs_before'] == 2:
            add_points(pm, batter, SITUATIONAL, '2 Out Hit', 1, 1.0)
            if ctx['runs_scored']:
                add_points(pm, batter, SITUATIONAL, '2 Out Hit Scores Run(s)', ctx['runs_scored'], 2.0 * ctx['runs_scored'])

        if is_hit and ctx['runs_scored']:
            lead_before = ctx['score_before'][side] - ctx['score_before'][opposite(side)]
            lead_after = ctx['score_after'][side] - ctx['score_after'][opposite(side)]
            if lead_before <= 0 < lead_after:
                add_points(pm, batter, SITUATIONAL, 'Hit Scores Run To Take The Lead', 1, 1.0)

        if event in WALK_EVENTS and ctx['outs_before'] == 2 and not ctx['pre_bases']:
            add_points(pm, batter, SITUATIONAL, 'Walk With 2 Outs And Bases Empty', 1, 1.0)

        if ctx['is_pa'] and ctx['pitches'] >= 10:
            extra = ctx['pitches'] - 10
            if event in REACH_EVENTS:
                add_points(pm, batter, SITUATIONAL, 'Long At-Bat And Reaches Base', ctx['pitches'], 2.0 + extra)
            else:
                add_points(pm, batter, SITUATIONAL, 'Long At-Bat (10+ Pitches)', ctx['pitches'], 1.0 + extra)

        _score_sacrifices(ctx, pm)
        _score_baserunning(ctx, pm)

    set_play_context(None)
    _score_team_offense(plays, side, team_events)


def _score_sacrifices(ctx, pm):
    event, batter = ctx['event_type'], ctx['batter_id']
    if event == 'sac_fly' and ctx['runs_scored']:
        add_points(pm, batter, SITUATIONAL, 'Sac Fly Scores Run', ctx['runs_scored'], 2.0)

    is_productive_out = event in ('sac_fly', 'sac_bunt', 'sac_fly_double_play') or (
        event == 'field_out' and ('grounds out' in ctx['description'] or 'bunt' in ctx['description'])
    )
    if is_productive_out:
        advanced = any(
            r['details']['runner']['id'] != batter
            and r['movement'].get('start') == '1B'
            and r['movement'].get('end') in ('2B', '3B')
            and not r['movement'].get('isOut')
            for r in ctx['runners']
        )
        if advanced:
            add_points(pm, batter, SITUATIONAL, 'Advances Runner Into Scoring Position', 1, 1.0)


def _score_baserunning(ctx, pm):
    batter = ctx['batter_id']
    for r in ctx['runners']:
        move, details = r['movement'], r['details']
        runner = details['runner']['id']
        if move.get('isOut'):
            continue
        kind = details.get('eventType') or ''
        start, end = move.get('start'), move.get('end')
        advanced = BASE_ORDER.get(end, 0) > BASE_ORDER.get(start, 0)
        threw_wild = any(c.get('credit') == 'f_throwing_error' for c in r.get('credits', []))

        if kind.startswith('stolen_base'):
            add_points(pm, runner, SITUATIONAL, 'Stolen Base', 1, 1.0)
        elif kind == 'passed_ball' and advanced:
            add_points(pm, runner, SITUATIONAL, 'Advances On Passed Ball', 1, 1.0)
        elif kind == 'other_advance' and advanced and 'throw' in (details.get('event', '') + ctx['description']).lower():
            add_points(pm, runner, SITUATIONAL, 'Advances On Throw To Another Base', 1, 1.0)
        elif runner != batter and advanced and (kind.startswith('pickoff_error') or threw_wild):
            add_points(pm, runner, SITUATIONAL, 'Advances On Errant Throw', 1, 1.0)
        elif ctx['event_type'] == 'single' and runner != batter and start == '1B' and end == '3B':
            add_points(pm, runner, SITUATIONAL, 'First To Third On A Single', 1, 1.0)


def _score_team_offense(plays, side, team_events):
    own = [c for c in plays if c['side'] == side]

    streak, awarded = 0, False
    last_half = None
    for ctx in own:
        if ctx['half_key'] != last_half:
            last_half, streak, awarded = ctx['half_key'], 0, False
        if not ctx['is_pa']:
            continue
        if ctx['event_type'] in HIT_EVENTS | WALK_EVENTS:
            streak += 1
            if streak >= 5 and not awarded:
                awarded = True
                team_events.append((SITUATIONAL, '5+ Straight Hits/Walks', streak, 2.0, play_snapshot(ctx)))
        else:
            streak, awarded = 0, False

    runs_without_out, awarded = 0, False
    last_half = None
    for ctx in own:
        if ctx['half_key'] != last_half:
            last_half, runs_without_out, awarded = ctx['half_key'], 0, False
        if ctx['outs_on_play']:
            runs_without_out, awarded = 0, False
            continue
        runs_without_out += ctx['runs_scored']
        if runs_without_out >= 4 and not awarded:
            awarded = True
            team_events.append((SITUATIONAL, '4+ Runs In A Row Without An Out', runs_without_out, 2.0, play_snapshot(ctx)))


def calculate_defensive_situational_points(plays, side, pm, team_events):
    defense = [c for c in plays if c['side'] != side]
    seen_errors = set()
    seen_events = set()

    for ctx in defense:
        set_play_context(play_snapshot(ctx))
        for r in ctx['runners']:
            move, details = r['movement'], r['details']
            kind = details.get('eventType') or ''
            credits = r.get('credits', [])
            event_key = (ctx['index'], details.get('playIndex'), kind)

            if move.get('isOut') and kind.startswith('pickoff_') and 'error' not in kind and 'caught_stealing' not in kind:
                add_points(pm, ctx['pitcher_id'], DEFENSE, 'Pickoff', 1, 1.0)

            if move.get('isOut') and 'caught_stealing' in kind:
                for c in credits:
                    if c.get('credit') == 'f_assist' and c.get('position', {}).get('abbreviation') == 'C':
                        add_points(pm, c['player']['id'], DEFENSE, 'Catcher Throws Out Runner Stealing', 1, 1.0)

            if move.get('isOut'):
                for c in credits:
                    if c.get('credit') == 'f_assist' and c.get('position', {}).get('abbreviation') in ('LF', 'CF', 'RF'):
                        at_home = move.get('outBase') == 'HM'
                        add_points(pm, c['player']['id'], DEFENSE,
                                   'Outfield Assist At Home Plate' if at_home else 'Outfield Assist',
                                   1, 2.0 if at_home else 1.0)

            for c in credits:
                if 'error' in c.get('credit', ''):
                    error_key = (ctx['index'], details.get('playIndex'), c['player']['id'], c['credit'])
                    if error_key not in seen_errors:
                        seen_errors.add(error_key)
                        add_points(pm, c['player']['id'], DEDUCTION, 'Error', 1, -1.0)

            if kind == 'passed_ball' and event_key not in seen_events:
                seen_events.add(event_key)
                team_events.append((DEDUCTION, 'Passed Ball', 1, -1.0, play_snapshot(ctx)))
            if kind == 'wild_pitch' and event_key not in seen_events:
                seen_events.add(event_key)
                add_points(pm, ctx['pitcher_id'], DEDUCTION, 'Wild Pitch', 1, -1.0)

        if ctx['outs_on_play'] >= 3:
            team_events.append((UNUSUAL, 'Triple Play', 1, 10.0, play_snapshot(ctx)))
        elif ctx['outs_on_play'] == 2:
            ends_inning_stranding_risp = (
                ctx['outs_after'] == 3 and ctx['runs_scored'] == 0 and _has_risp(ctx['pre_bases'])
            )
            if ends_inning_stranding_risp:
                team_events.append((DEFENSE, 'Double Play To End Inning And Prevent Runs', 1, 3.0, play_snapshot(ctx)))
            else:
                team_events.append((DEFENSE, 'Double Play', 1, 2.0, play_snapshot(ctx)))

    set_play_context(None)
    _score_escaped_innings(defense, pm)


def _score_escaped_innings(defense, pm):
    """Pitcher finishes a scoreless inning after runner(s) reached scoring position."""
    halves = {}
    for ctx in defense:
        halves.setdefault(ctx['half_key'], []).append(ctx)

    for half in halves.values():
        last = half[-1]
        if last['outs_after'] < 3 or sum(c['runs_scored'] for c in half) > 0:
            continue

        placed_risp = half[0]['first_in_half'] and _has_risp(half[0]['pre_bases'])
        risp_seen = placed_risp or any(_has_risp(c['post_bases']) and c['outs_after'] < 3 for c in half)
        if not risp_seen:
            continue

        zero_out_risp = (placed_risp and half[0]['outs_before'] == 0) or any(
            _has_risp(c['post_bases']) and c['outs_after'] == 0 for c in half
        )
        set_play_context(play_snapshot(last))
        set_play_context(play_snapshot(last))
        if zero_out_risp:
            add_points(pm, last['pitcher_id'], DEFENSE, 'Escapes Inning With 0 Outs And Runner(s) In Scoring Position', 1, 2.0)
        else:
            add_points(pm, last['pitcher_id'], DEFENSE, 'Escapes Inning With Runner(s) In Scoring Position', 1, 1.0)
    set_play_context(None)
