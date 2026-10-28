"""Tolkning av matchfilen `getMatchFiles.php?type=stats` (<SoccerStatistics>).

Strukturen bygger på tredjepartskällor (se docs/teknisk-kartlaggning.md, avsnitt 4, E8)
och är ännu inte verifierad mot ett eget hämtat svar. Tolkningen är därför tolerant:
saknade attribut ger None i stället för fel.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


class StatsXmlError(ValueError):
    """Filen är tom, inte XML eller saknar det som behövs."""


@dataclass
class Player:
    id: int
    team_id: int
    name: str
    shirt_no: int | None
    goalkeeper: bool
    position: str | None
    origin: tuple[float, float] | None  # None = bänk
    goals: int = 0
    cards: list[str] = field(default_factory=list)

    @property
    def starter(self) -> bool:
        return self.origin is not None


@dataclass
class Substitution:
    team_id: int
    player_in: int | None
    player_out: int | None
    minute: int | None  # matchklockans minut
    rule_minute: int | None  # inställd regelminut (attributet minute)
    reason: str | None  # "preset" = regel, "injury" = skada


@dataclass
class TacticChange:
    team_id: int
    kind: str  # tactic | playstyle | aggression
    new_setting: str
    minute: int | None


@dataclass
class Goal:
    team_id: int  # laget som fick målet tillgodoräknat
    minute: int | None


@dataclass
class Team:
    id: int
    name: str
    home: bool
    tactic: str | None
    playstyle: str | None
    aggression: str | None
    manager: str | None
    goals: int | None
    statistics: dict[str, str]
    series: str | None = None  # MetaData@series_name, t.ex. 'div1.1'


@dataclass
class Match:
    mid: int
    type: str | None
    date: str | None
    final: bool
    teams: list[Team]  # [hemma, borta]
    players: list[Player]
    substitutions: list[Substitution]
    tactic_changes: list[TacticChange]
    goals: list[Goal] = field(default_factory=list)

    def score_at(self, team_id: int, minute: int | None) -> tuple[int, int] | None:
        """Ställningen (egna, motståndarens) före given minut, sett från team_id."""
        if minute is None or any(g.minute is None for g in self.goals):
            return None
        if any(t.goals is not None for t in self.teams) and len(self.goals) != sum(t.goals or 0 for t in self.teams):
            return None  # målhändelserna är ofullständiga
        own = sum(1 for g in self.goals if g.team_id == team_id and g.minute < minute)
        other = sum(1 for g in self.goals if g.team_id != team_id and g.minute < minute)
        return own, other

    def team(self, team_id: int) -> Team:
        for t in self.teams:
            if t.id == team_id:
                return t
        raise KeyError(team_id)

    def opponent(self, team_id: int) -> Team:
        for t in self.teams:
            if t.id != team_id:
                return t
        raise KeyError(team_id)

    def starters(self, team_id: int) -> list[Player]:
        return [p for p in self.players if p.team_id == team_id and p.starter]


def _int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _clock_minute(clock: str | None) -> int | None:
    """'60:11' -> 60. Matchklockan anges som mm:ss."""
    if not clock:
        return None
    m = re.match(r"\s*(\d+)", clock)
    return int(m.group(1)) if m else None


def _origin(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


def extract_xml(text: str) -> str:
    """Plocka ut <SoccerStatistics>…</SoccerStatistics>, även om den ligger inbäddad i HTML."""
    if not text or not text.strip():
        raise StatsXmlError("Tom matchfil (matchen är troligen inte förberedd ännu).")
    m = re.search(r"<SoccerStatistics\b.*</SoccerStatistics>", text, re.S)
    if not m:
        raise StatsXmlError("<SoccerStatistics> saknas.")
    return m.group(0)


def parse_stats(text: str) -> Match:
    try:
        root = ET.fromstring(extract_xml(text))
    except ET.ParseError as e:
        raise StatsXmlError(f"Ogiltig XML: {e}") from e

    mid = _int(root.get("matchId"))
    if mid is None:
        raise StatsXmlError("matchId saknas.")

    team_els = root.findall("Team")
    if len(team_els) != 2:
        raise StatsXmlError(f"{len(team_els)} lag i stället för 2.")

    teams = []
    for t in team_els:
        stat = t.find("Statistics")
        meta = t.find("MetaData")
        statistics = dict(stat.attrib) if stat is not None else {}
        teams.append(
            Team(
                id=_int(t.get("id")) or 0,
                name=t.get("name", ""),
                home=t.get("visiting") == "0",
                tactic=t.get("tactic"),
                playstyle=t.get("playstyle"),
                aggression=t.get("aggression"),
                manager=meta.get("manager") if meta is not None else None,
                series=meta.get("series_name") if meta is not None else None,
                goals=_int(statistics.get("goals")),
                statistics=statistics,
            )
        )
    # Hemmalaget först. Saknas visiting antas dokumentets ordning.
    if not teams[0].home and teams[1].home:
        teams.reverse()

    players = []
    for p in root.iter("Player"):
        players.append(
            Player(
                id=_int(p.get("id")) or 0,
                team_id=_int(p.get("teamId")) or 0,
                name=p.get("name", ""),
                shirt_no=_int(p.get("shirtno")),
                goalkeeper=p.get("goalkeeper") == "1",
                position=p.get("position"),
                origin=_origin(p.get("origin")),
                goals=len(p.findall("Goal")),
                cards=[c.get("type", "") for c in p.findall("Card")],
            )
        )

    # Målhändelser. Goal@team anger laget som får målet (självmål), annars spelarens lag.
    goal_events = [
        Goal(
            team_id=_int(g.get("team")) or _int(p.get("teamId")) or 0,
            minute=_clock_minute(g.get("clock") or g.get("time")),
        )
        for p in root.iter("Player")
        for g in p.findall("Goal")
    ]
    goal_events.sort(key=lambda g: (g.minute is None, g.minute or 0))
    for t in teams:
        if t.goals is None:
            t.goals = sum(1 for g in goal_events if g.team_id == t.id)

    subs = [
        Substitution(
            team_id=_int(s.get("teamId")) or 0,
            player_in=_int(s.get("playerId")),
            player_out=_int(s.get("substitutedId")),
            minute=_clock_minute(s.get("clock")) if s.get("clock") else _int(s.get("minute")),
            rule_minute=_int(s.get("minute")),
            reason=s.get("reason"),
        )
        for s in root.iter("Substitution")
    ]

    changes = [
        TacticChange(
            team_id=_int(c.get("teamId")) or 0,
            kind=c.get("type", ""),
            new_setting=c.get("new_setting", ""),
            minute=_clock_minute(c.get("clock") or c.get("time")) or _int(c.get("minute")),
        )
        for c in root.iter("Tactic")
    ]

    return Match(
        mid=mid,
        type=root.get("type"),
        date=root.get("date"),
        final=root.get("final") == "1",
        teams=teams,
        players=players,
        substitutions=subs,
        tactic_changes=changes,
        goals=goal_events,
    )
