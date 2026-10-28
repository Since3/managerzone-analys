"""Syntetiska matchfiler för tester.

OBS: Inte riktiga svar från ManagerZone. Strukturen följer den dokumenterade
<SoccerStatistics>-filen (docs/teknisk-kartlaggning.md, avsnitt 4, E8).
"""

from __future__ import annotations

# Formationer som lista av (bredd, djup) för utespelare, djup = avstånd från eget mål.
F_4213 = [(100, 250), (280, 240), (470, 240), (650, 250),
          (300, 420), (450, 420), (375, 560),
          (120, 760), (375, 780), (630, 760)]
F_442 = [(100, 250), (280, 240), (470, 240), (650, 250),
         (100, 470), (300, 490), (450, 490), (650, 470),
         (300, 720), (450, 720)]
F_532 = [(80, 280), (220, 230), (375, 220), (530, 230), (670, 280),
         (250, 480), (375, 500), (500, 480),
         (300, 720), (450, 720)]


def _players(team_id: int, shape, keeper_at_top: bool, base_id: int) -> str:
    out = []
    gk_y = 1000 if keeper_at_top else 0
    out.append(f'<Player id="{base_id}" teamId="{team_id}" name="Keeper {team_id}" shirtno="1" '
               f'goalkeeper="1" position="goalie" origin="375,{gk_y}"/>')
    for i, (w, d) in enumerate(shape, start=1):
        x, y = (w, 1000 - d) if keeper_at_top else (750 - w, d)
        out.append(f'<Player id="{base_id + i}" teamId="{team_id}" name="P{team_id}-{i}" '
                   f'shirtno="{i + 1}" position="normal" origin="{x:g},{y:g}"/>')
    out.append(f'<Player id="{base_id + 50}" teamId="{team_id}" name="Bench {team_id}" shirtno="20" origin=""/>')
    return "\n  ".join(out)


def make_stats_xml(
    mid: int,
    home: tuple[int, str],
    away: tuple[int, str],
    score: tuple[int, int],
    home_shape=F_4213,
    away_shape=F_442,
    home_setup=("wings", "offensive", "normal"),
    away_setup=("shortpass", "normal", "normal"),
    date: str = "2026-10-21 14:45:00",
    events: str = "",
) -> str:
    (hid, hname), (aid, aname) = home, away
    return f"""<?xml version="1.0" encoding="utf-8"?>
<SoccerStatistics matchId="{mid}" type="series" date="{date}" final="1">
  <Team id="{hid}" name="{hname}" shortname="H" visiting="0" tactic="{home_setup[0]}" playstyle="{home_setup[1]}" aggression="{home_setup[2]}">
    <MetaData manager="mgr{hid}" series_name="div1.1"/>
    <HalfStatistics goals="0"/>
    <Statistics goals="{score[0]}" possession="55" shotsOnGoal="6" shotsWide="4"/>
  </Team>
  <Team id="{aid}" name="{aname}" shortname="A" visiting="1" tactic="{away_setup[0]}" playstyle="{away_setup[1]}" aggression="{away_setup[2]}">
    <MetaData manager="mgr{aid}" series_name="div1.1"/>
    <Statistics goals="{score[1]}" possession="45" shotsOnGoal="3" shotsWide="5"/>
  </Team>
  {_players(hid, home_shape, keeper_at_top=False, base_id=hid * 100)}
  {_players(aid, away_shape, keeper_at_top=True, base_id=aid * 100)}
  <Events>
    {events}
  </Events>
</SoccerStatistics>
"""
