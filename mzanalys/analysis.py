"""Taktisk profil för ett lag över ett antal spelade matcher."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from . import formation
from .stats import Match

# Matchtyper i SoccerStatistics@type, verifierade mot riktiga matcher 2026-10-28.
LEAGUE = "1"
CUP = "6"

RESULTS = ("V", "O", "F")
EARLY_MINUTE = 10  # ändringar hit räknas som tidiga
MASKING_SHARE = 0.3  # minst så stor andel av matcherna (och minst två) ger varning


@dataclass
class Change:
    minute: int | None
    kind: str  # tactic | playstyle | aggression
    new_setting: str
    state: str | None  # "leder", "lika", "under" vid ändringen, None om okänt
    score: tuple[int, int] | None

    def __str__(self) -> str:
        m = f"{self.minute}'" if self.minute is not None else "?'"
        s = f" (vid {self.score[0]}–{self.score[1]})" if self.score else ""
        return f"{m} {self.kind}→{self.new_setting}{s}"


@dataclass
class Starter:
    id: int
    name: str
    role: str  # t.ex. "försvar vänster"


@dataclass
class MatchSummary:
    mid: int
    date: str | None
    home: bool
    opponent: str
    opponent_id: int
    goals_for: int | None
    goals_against: int | None
    formation: str | None  # linjer, t.ex. 4-2-1-3
    formation_zones: str | None  # försvar-mittfält-anfall
    tactic: str | None
    playstyle: str | None
    aggression: str | None
    opponent_formation: str | None
    opponent_setup: str
    possession: str | None
    changes: list[Change]
    subs: int
    sub_minutes: list[int]
    starters: list[Starter] = field(default_factory=list)
    attack_side: str | None = None  # vänster | höger | centralt (som i taktikeditorn)
    shots_for: int | None = None  # skott på mål
    shots_against: int | None = None
    shape: formation.Formation | None = None
    opponent_shape: formation.Formation | None = None
    opponent_tactic: str | None = None
    opponent_playstyle: str | None = None
    opponent_aggression: str | None = None

    @property
    def opponent_backs(self) -> str | None:
        """Antal backar hos laget som mötte dem, t.ex. '4 backar'."""
        if not self.opponent_shape:
            return None
        return f"{self.opponent_shape.zones.split('-')[0]} backar"

    @property
    def result(self) -> str:
        if self.goals_for is None or self.goals_against is None:
            return "?"
        if self.goals_for > self.goals_against:
            return "V"
        if self.goals_for < self.goals_against:
            return "F"
        return "O"

    @property
    def opponent_result(self) -> str:
        return {"V": "F", "F": "V"}.get(self.result, self.result)

    @property
    def setup(self) -> str:
        return _setup(self.tactic, self.playstyle, self.aggression)


def _setup(tactic, playstyle, aggression) -> str:
    return "/".join(x or "?" for x in (tactic, playstyle, aggression))


def _state(score: tuple[int, int] | None) -> str | None:
    if score is None:
        return None
    if score[0] > score[1]:
        return "leder"
    if score[0] < score[1]:
        return "under"
    return "lika"


def _shots(team) -> int | None:
    value = team.statistics.get("shotsOnGoal")
    try:
        return int(float(value)) if value not in (None, "") else None
    except ValueError:
        return None


def _role(width: float, depth: float) -> str:
    if depth <= formation.DEFENCE_MAX_DEPTH:
        line = "försvar"
    elif depth >= formation.ATTACK_MIN_DEPTH:
        line = "anfall"
    else:
        line = "mittfält"
    third = formation.PITCH_WIDTH / 3
    side = "vänster" if width < third else "höger" if width > 2 * third else "central"
    return f"{line} {side}"


def _tally(results) -> dict[str, int]:
    c = Counter(results)
    return {r: c.get(r, 0) for r in RESULTS}


@dataclass
class TeamProfile:
    team_id: int
    name: str
    matches: list[MatchSummary] = field(default_factory=list)

    def _count(self, attr: str, matches=None) -> Counter:
        ms = self.matches if matches is None else matches
        return Counter(getattr(m, attr) for m in ms if getattr(m, attr))

    @property
    def record(self) -> dict[str, int]:
        return _tally(m.result for m in self.matches)

    @property
    def goals(self) -> tuple[int, int]:
        gf = sum(m.goals_for or 0 for m in self.matches)
        ga = sum(m.goals_against or 0 for m in self.matches)
        return gf, ga

    def formations(self) -> Counter:
        return self._count("formation")

    def formation_zones(self) -> Counter:
        return self._count("formation_zones")

    def tactics(self) -> Counter:
        return self._count("tactic")

    def playstyles(self) -> Counter:
        return self._count("playstyle")

    def aggressions(self) -> Counter:
        return self._count("aggression")

    def setups(self) -> Counter:
        return Counter(m.setup for m in self.matches)

    def results_by(self, key, opponent_view: bool = False) -> dict[str, dict[str, int]]:
        """Resultat (V/O/F) grupperat på en egenskap.

        opponent_view=True räknar resultatet från motståndarens sida, alltså hur det
        gick för lagen som mötte det analyserade laget.
        """
        groups: dict[str, list[str]] = {}
        for m in self.matches:
            groups.setdefault(key(m) or "?", []).append(m.opponent_result if opponent_view else m.result)
        return {k: _tally(v) for k, v in groups.items()}

    def change_patterns(self) -> Counter:
        """Taktikändringar utan minut, t.ex. 'playstyle→offensive'."""
        return Counter(f"{c.kind}→{c.new_setting}" for m in self.matches for c in m.changes)

    def changes_by_state(self) -> dict[str, Counter]:
        """Ändringar grupperade på ställningen när de gjordes: leder, lika, under."""
        out: dict[str, Counter] = {}
        for m in self.matches:
            for c in m.changes:
                out.setdefault(c.state or "okänd", Counter())[f"{c.kind}→{c.new_setting}"] += 1
        return out

    def attack_sides(self) -> Counter:
        return Counter(m.attack_side for m in self.matches if m.attack_side)

    def early_changes(self, minute: int = EARLY_MINUTE) -> dict:
        """Taktikändringar tidigt i matchen (möjlig maskeringstaktik)."""
        hits = [m for m in self.matches
                if any(c.minute is not None and c.minute <= minute for c in m.changes)]
        changes = Counter(f"{c.kind}→{c.new_setting}" for m in hits for c in m.changes
                          if c.minute is not None and c.minute <= minute)
        n = len(self.matches)
        return {"minute": minute, "matches": len(hits), "total": n, "changes": changes,
                "masking": n > 0 and len(hits) >= 2 and len(hits) / n >= MASKING_SHARE}

    def change_minutes(self) -> list[int]:
        return sorted(c.minute for m in self.matches for c in m.changes if c.minute is not None)

    def average_sub_minute(self) -> float | None:
        minutes = [x for m in self.matches for x in m.sub_minutes]
        return sum(minutes) / len(minutes) if minutes else None

    def most_likely(self, home: bool | None = None) -> dict[str, tuple[str, float, int]]:
        """Vanligaste värdet, andelen matcher det förekom i och antal matcher.

        home=True/False begränsar till hemma- respektive bortamatcher.
        """
        ms = [m for m in self.matches if home is None or m.home == home]
        n = len(ms)
        out = {}
        for label, attr in (
            ("formation", "formation"),
            ("taktik", "tactic"),
            ("spelstil", "playstyle"),
            ("aggressivitet", "aggression"),
        ):
            counter = self._count(attr, ms)
            if counter:
                value, count = counter.most_common(1)[0]
                out[label] = (value, count / n, n)
        return out

    def regular_starters(self) -> list[tuple[Starter, int]]:
        """Spelare sorterade på antal starter, med deras vanligaste roll."""
        starts: Counter = Counter()
        roles: dict[int, Counter] = {}
        names: dict[int, str] = {}
        for m in self.matches:
            for s in m.starters:
                starts[s.id] += 1
                names[s.id] = s.name
                roles.setdefault(s.id, Counter())[s.role] += 1
        return [
            (Starter(pid, names[pid], roles[pid].most_common(1)[0][0]), n)
            for pid, n in starts.most_common()
        ]


def summarize(match: Match, team_id: int) -> MatchSummary:
    team = match.team(team_id)
    opp = match.opponent(team_id)
    starters = match.starters(team_id)
    own_f = formation.derive(starters)
    opp_f = formation.derive(match.starters(opp.id))

    changes = []
    for c in match.tactic_changes:
        if c.team_id != team_id:
            continue
        score = match.score_at(team_id, c.minute)
        changes.append(Change(c.minute, c.kind, c.new_setting, _state(score), score))

    starter_rows = []
    if own_f:
        outfield = [p for p in starters if not p.goalkeeper]
        for p, (w, d) in zip(outfield, own_f.positions):
            starter_rows.append(Starter(p.id, p.name, _role(w, d)))
    starter_rows += [Starter(p.id, p.name, "målvakt") for p in starters if p.goalkeeper]

    subs = [s for s in match.substitutions if s.team_id == team_id]
    return MatchSummary(
        mid=match.mid,
        date=match.date,
        home=team.home,
        opponent=opp.name,
        opponent_id=opp.id,
        goals_for=team.goals,
        goals_against=opp.goals,
        formation=own_f.lines if own_f else None,
        formation_zones=own_f.zones if own_f else None,
        tactic=team.tactic,
        playstyle=team.playstyle,
        aggression=team.aggression,
        opponent_formation=opp_f.lines if opp_f else None,
        opponent_setup=_setup(opp.tactic, opp.playstyle, opp.aggression),
        possession=team.statistics.get("possession"),
        changes=changes,
        subs=len(subs),
        sub_minutes=[s.minute for s in subs if s.minute is not None],
        starters=starter_rows,
        attack_side=formation.attack_side(own_f),
        shots_for=_shots(team),
        shots_against=_shots(opp),
        shape=own_f,
        opponent_shape=opp_f,
        opponent_tactic=opp.tactic,
        opponent_playstyle=opp.playstyle,
        opponent_aggression=opp.aggression,
    )


def build_profile(
    matches: list[Match], team_id: int, types: tuple[str, ...] | None = (LEAGUE,)
) -> TeamProfile:
    """Profil för laget över matcherna där det deltog, nyaste först.

    Som standard bara ligamatcher. types=None tar med alla matchtyper.
    """
    own = [
        m
        for m in matches
        if any(t.id == team_id for t in m.teams) and (types is None or m.type in types)
    ]
    own.sort(key=lambda m: (m.date or "", m.mid), reverse=True)
    name = own[0].team(team_id).name if own else str(team_id)
    profile = TeamProfile(team_id=team_id, name=name)
    profile.matches = [summarize(m, team_id) for m in own]
    return profile
