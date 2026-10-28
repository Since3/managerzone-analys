"""Taktisk profil för ett lag över ett antal spelade matcher."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from . import formation
from .stats import Match


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
    changes: list[str]  # taktikändringar under matchen, t.ex. "62' playstyle→offensive"
    subs: int
    sub_minutes: list[int]

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
    def setup(self) -> str:
        return _setup(self.tactic, self.playstyle, self.aggression)


def _setup(tactic, playstyle, aggression) -> str:
    return "/".join(x or "?" for x in (tactic, playstyle, aggression))


@dataclass
class TeamProfile:
    team_id: int
    name: str
    matches: list[MatchSummary] = field(default_factory=list)

    def _count(self, attr: str) -> Counter:
        return Counter(getattr(m, attr) for m in self.matches if getattr(m, attr))

    @property
    def record(self) -> dict[str, int]:
        c = Counter(m.result for m in self.matches)
        return {k: c.get(k, 0) for k in ("V", "O", "F")}

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

    def results_by(self, key) -> dict[str, dict[str, int]]:
        """Resultat (V/O/F) grupperat på en egenskap, t.ex. formation eller upplägg."""
        out: dict[str, Counter] = {}
        for m in self.matches:
            k = key(m) or "?"
            out.setdefault(k, Counter())[m.result] += 1
        return {k: {r: c.get(r, 0) for r in ("V", "O", "F")} for k, c in out.items()}

    def change_patterns(self) -> Counter:
        """Taktikändringar under matchen utan minut, t.ex. 'playstyle→offensive'."""
        return Counter(c.split(" ", 1)[1] for m in self.matches for c in m.changes)

    def average_sub_minute(self) -> float | None:
        minutes = [x for m in self.matches for x in m.sub_minutes]
        return sum(minutes) / len(minutes) if minutes else None

    def most_likely(self) -> dict[str, tuple[str, float]]:
        """Vanligaste värdet och andelen matcher det förekom i (stabilitet)."""
        n = len(self.matches) or 1
        out = {}
        for label, counter in (
            ("formation", self.formations()),
            ("taktik", self.tactics()),
            ("spelstil", self.playstyles()),
            ("aggressivitet", self.aggressions()),
        ):
            if counter:
                value, count = counter.most_common(1)[0]
                out[label] = (value, count / n)
        return out


def summarize(match: Match, team_id: int) -> MatchSummary:
    team = match.team(team_id)
    opp = match.opponent(team_id)
    own_f = formation.derive(match.starters(team_id))
    opp_f = formation.derive(match.starters(opp.id))
    changes = [
        f"{c.minute if c.minute is not None else '?'}' {c.kind}→{c.new_setting}"
        for c in match.tactic_changes
        if c.team_id == team_id
    ]
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
    )


def build_profile(matches: list[Match], team_id: int) -> TeamProfile:
    """Profil för laget över matcherna där det deltog, nyaste först."""
    own = [m for m in matches if any(t.id == team_id for t in m.teams)]
    own.sort(key=lambda m: (m.date or "", m.mid), reverse=True)
    name = own[0].team(team_id).name if own else str(team_id)
    profile = TeamProfile(team_id=team_id, name=name)
    profile.matches = [summarize(m, team_id) for m in own]
    return profile
