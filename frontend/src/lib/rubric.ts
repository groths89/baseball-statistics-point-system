export interface RubricRow {
  rule: string;
  points: string;
  group?: string;
}

export interface RubricSection {
  key: 'basic' | 'situational' | 'miracles' | 'deductions' | 'carry_over';
  title: string;
  rows: RubricRow[];
}

// Mirrors the "Custom Point System" section of the README
export const RUBRIC: RubricSection[] = [
  {
    key: 'basic',
    title: 'I. Basic Stats (Totals)',
    rows: [
      { group: 'Batting', rule: 'Solo home run', points: '+1' },
      { group: 'Batting', rule: 'Home run with runners on', points: '+2' },
      { group: 'Batting', rule: 'Grand slam', points: '+4' },
      { group: 'Batting', rule: 'Each run scored', points: '+1' },
      { group: 'Batting', rule: 'Each hit', points: '+0.5' },
      { group: 'Batting', rule: 'Each triple', points: '+3' },
      { group: 'Batting', rule: 'Each walk', points: '+1' },
      { group: 'Batting', rule: 'Team draws more than 5 walks', points: '+2' },
      { group: 'Pitching', rule: 'Team records 16+ strikeouts', points: '+1' },
      { group: 'Pitching', rule: 'Starter gives up 2 runs or less', points: '+5' },
      { group: 'Pitching', rule: 'Starter goes 7+ innings', points: '+5' },
      { group: 'Pitching', rule: 'Starter pitches a complete game', points: '+10' },
      { group: 'Pitching', rule: 'Bullpen gives up 0 runs', points: '+5' },
      { group: 'Pitching', rule: 'Closer completes a save', points: '+3' },
      { group: 'Pitching', rule: 'Closer saves without allowing a hit or walk', points: '+5' },
    ],
  },
  {
    key: 'situational',
    title: 'II. All the Small Things (Situational)',
    rows: [
      { group: 'Offense', rule: 'Two-out hit', points: '+1' },
      { group: 'Offense', rule: 'Two-out hit that scores run(s)', points: '+2 per run' },
      { group: 'Offense', rule: 'Hit scores a run to take the lead', points: '+1' },
      { group: 'Offense', rule: 'Walk with 2 outs and the bases empty', points: '+1' },
      { group: 'Offense', rule: 'Works the count to 10+ pitches', points: '+1, plus 1 per pitch after 10' },
      { group: 'Offense', rule: '10+ pitch at-bat that ends with the batter on base', points: '+2, plus 1 per pitch after 10' },
      { group: 'Offense', rule: 'Sac fly, ground ball or bunt moves a runner into scoring position', points: '+1' },
      { group: 'Offense', rule: 'Sac fly scores a run', points: '+2' },
      { group: 'Base running', rule: 'Runner goes 1st to 3rd on a single', points: '+1' },
      { group: 'Base running', rule: 'Runner advances on a throw to another base', points: '+1' },
      { group: 'Base running', rule: 'Runner advances on an errant throw or passed ball', points: '+1' },
      { group: 'Base running', rule: 'Stolen base', points: '+1' },
      { group: 'Team offense', rule: '5+ straight hits and/or walks', points: '+2' },
      { group: 'Team offense', rule: '4+ runs in a row without an out', points: '+2' },
      { group: 'Pitchers', rule: 'Picks off a runner', points: '+1' },
      { group: 'Pitchers', rule: 'Ends an inning without a run with runner(s) in scoring position', points: '+1' },
      { group: 'Pitchers', rule: 'Same, with 0 outs and runner(s) in scoring position', points: '+2' },
      { group: 'Fielders', rule: 'Catcher throws out a base stealer', points: '+1' },
      { group: 'Fielders', rule: 'Outfield assist', points: '+1' },
      { group: 'Fielders', rule: 'Outfield assist at home plate', points: '+2' },
      { group: 'Team defense', rule: 'Double play', points: '+2' },
      { group: 'Team defense', rule: 'Double play that ends an inning and prevents runs', points: '+3' },
    ],
  },
  {
    key: 'miracles',
    title: 'III. The Unusual & Miraculous',
    rows: [
      { group: 'Batters', rule: 'Hits for the cycle', points: '+10' },
      { group: 'Batters', rule: '3+ home runs in a game', points: '+5' },
      { group: 'Pitchers', rule: 'Strikes out 12+ in a game', points: '+5' },
      { group: 'Pitchers', rule: 'Perfect game or no-hitter', points: '+10' },
      { group: 'Team', rule: 'Triple play', points: '+10' },
      { group: 'Team', rule: 'Comes back from a 5+ run deficit in the last inning', points: '+20' },
      { group: 'Team', rule: 'Comes back from a 10+ run deficit in the last 2 innings', points: '+20' },
      { group: 'Team', rule: 'Walk-off win', points: '+5' },
    ],
  },
  {
    key: 'deductions',
    title: 'IV. Points Deducted',
    rows: [
      { group: 'Offense', rule: 'Player strikes out 4+ times', points: '-4' },
      { group: 'Offense', rule: 'Team strikes out 10+ times', points: '-1, then -1 per strikeout after 10' },
      { group: 'Offense', rule: 'Team goes scoreless for 6+ innings', points: '-1' },
      { group: 'Defense', rule: 'Error', points: '-1' },
      { group: 'Defense', rule: 'Passed ball', points: '-1' },
      { group: 'Defense', rule: 'Wild pitch', points: '-1' },
      { group: 'Defense', rule: 'Starter fails to complete 4 innings', points: '-1' },
      { group: 'Defense', rule: 'Reliever walks the first batter he faces', points: '-1' },
      { group: 'Defense', rule: 'Pitchers walk 5+ batters', points: '-1, then -1 per walk after 5' },
      { group: 'Defense', rule: 'Closer blows a save', points: '-2' },
    ],
  },
  {
    key: 'carry_over',
    title: 'V. Carry-Over Points',
    rows: [
      { rule: 'Walk-off win', points: '+2 into next game' },
      { rule: 'Comes back from a 5+ run deficit in the last inning', points: '+2 into next game' },
      { rule: 'Comes back from a 10+ run deficit in the last 2 innings', points: '+2 into next game' },
      { rule: 'Perfect game or no-hitter', points: '+2 into next game' },
    ],
  },
];
