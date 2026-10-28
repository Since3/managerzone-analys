"""Förslag på upplägg mot en motståndare.

Underlag (evidens) är matcher där ett lag mötte antingen
- motståndaren själv (direkt, vikt DIRECT_WEIGHT), eller
- ett annat lag i ligan som spelade motståndarens väntade formation (liknande, vikt 1).

Måttet är målskillnaden för laget som mötte dem, minus den väntade målskillnaden utifrån
lagens styrka och hemmafördel (se league.ratings). Utan ligadatabas är det väntade 0.
Grupper med lite underlag dras mot 0 (PRIOR_WEIGHT fiktiva matcher), och ett alternativ
måste ha minst MIN_WEIGHT i vikt för att föreslås.

Förslaget bygger på historiska resultat, inte på spelmotorn. Spelarnas kvalitet påverkar
också utfallet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import analysis, formation
from .analysis import MatchSummary, TeamProfile

DIRECT_WEIGHT = 2.0
PRIOR_WEIGHT = 3.0
MIN_WEIGHT = 4.0  # t.ex. två direkta matcher eller fyra liknande

DIMENSIONS = (
    ("backs", "Antal backar"),
    ("formation", "Formation"),
    ("tactic", "Taktik"),
    ("playstyle", "Spelstil"),
    ("aggression", "Aggressivitet"),
)


@dataclass
class Evidence:
    values: dict[str, str | None]  # det mötande lagets val per dimension
    result: str  # V/O/F för det mötande laget
    gd: int
    expected: float
    weight: float
    direct: bool


@dataclass
class Option:
    value: str
    matches: int
    direct: int
    wins: int
    draws: int
    losses: int
    ppm: float  # faktiska poäng per match
    resid: float  # målskillnad jämfört med väntat, viktat medel
    score: float  # krympt resid
    weight: float


@dataclass
class Choice:
    label: str
    best: Option | None
    options: list[Option]

    def runner_up(self) -> Option | None:
        others = [o for o in self.options if self.best and o.value != self.best.value]
        return others[0] if others else None


@dataclass
class Recommendation:
    backs: Choice
    formation: Choice
    tactic: Choice
    playstyle: Choice
    aggression: Choice
    confidence: str  # låg | medel | hög
    direct_matches: int
    similar_matches: int
    uses_league: bool
    reasons: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    shape: list[tuple[float, float]] | None = None
    opponent_formation: str | None = None
    opponent_shape: list[tuple[float, float]] | None = None

    @property
    def choices(self) -> list[Choice]:
        return [self.backs, self.formation, self.tactic, self.playstyle, self.aggression]


POINTS = {"V": 3, "O": 1, "F": 0}


def _backs(shape: formation.Formation | None) -> str | None:
    return f"{shape.zones.split('-')[0]} backar" if shape else None


def _values(s: MatchSummary) -> dict[str, str | None]:
    """Det analyserade lagets val i en sammanfattning."""
    return {"backs": _backs(s.shape), "formation": s.formation, "tactic": s.tactic,
            "playstyle": s.playstyle, "aggression": s.aggression}


def direct_evidence(profile: TeamProfile, ratings=None) -> tuple[list[Evidence], list]:
    """Matcher mot motståndaren, sett från lagen som mötte dem."""
    rows, shapes = [], []
    for m in profile.matches:
        if m.goals_for is None or m.goals_against is None:
            continue
        exp = ratings.expected_gd(m.opponent_id, profile.team_id, home=not m.home) if ratings else 0.0
        rows.append(Evidence(
            values={"backs": m.opponent_backs, "formation": m.opponent_formation, "tactic": m.opponent_tactic,
                    "playstyle": m.opponent_playstyle, "aggression": m.opponent_aggression},
            result=m.opponent_result, gd=m.goals_against - m.goals_for, expected=exp,
            weight=DIRECT_WEIGHT, direct=True,
        ))
        shapes.append((m.opponent_formation, m.opponent_shape))
    return rows, shapes


def similar_evidence(league_matches, opponent_id: int, opponent_formation: str | None,
                     ratings=None) -> tuple[list[Evidence], list]:
    """Ligamatcher där ett annat lag spelade samma formation som motståndaren väntas spela."""
    rows, shapes = [], []
    if not opponent_formation:
        return rows, shapes
    for match in league_matches:
        if any(t.id == opponent_id for t in match.teams):
            continue
        for faced in match.teams:
            faced_f = formation.derive(match.starters(faced.id))
            if not faced_f or faced_f.lines != opponent_formation:
                continue
            challenger = match.opponent(faced.id)
            s = analysis.summarize(match, challenger.id)
            if s.goals_for is None or s.goals_against is None:
                continue
            exp = ratings.expected_gd(challenger.id, faced.id, home=s.home) if ratings else 0.0
            rows.append(Evidence(values=_values(s), result=s.result, gd=s.goals_for - s.goals_against,
                                 expected=exp, weight=1.0, direct=False))
            shapes.append((s.formation, s.shape))
    return rows, shapes


def _options(rows: list[Evidence], dim: str) -> list[Option]:
    groups: dict[str, list[Evidence]] = {}
    for r in rows:
        v = r.values.get(dim)
        if v:
            groups.setdefault(v, []).append(r)
    out = []
    for value, rs in groups.items():
        w = sum(r.weight for r in rs)
        weighted = sum(r.weight * (r.gd - r.expected) for r in rs)
        out.append(Option(
            value=value, matches=len(rs), direct=sum(1 for r in rs if r.direct),
            wins=sum(1 for r in rs if r.result == "V"), draws=sum(1 for r in rs if r.result == "O"),
            losses=sum(1 for r in rs if r.result == "F"),
            ppm=sum(POINTS.get(r.result, 0) for r in rs) / len(rs),
            resid=weighted / w, score=weighted / (w + PRIOR_WEIGHT), weight=w,
        ))
    out.sort(key=lambda o: (-o.score, -o.weight))
    return out


def _choice(label: str, rows: list[Evidence], dim: str) -> Choice:
    options = _options(rows, dim)
    solid = [o for o in options if o.weight >= MIN_WEIGHT]
    pool = solid or options
    return Choice(label, pool[0] if pool else None, options)


def _signed(x: float) -> str:
    return f"{x:+.1f}".replace("-", "−")


def _n(count: int) -> str:
    return f"{count} {'match' if count == 1 else 'matcher'}"


def _describe(o: Option, name: str) -> str:
    if o.direct == o.matches:
        where = f"{_n(o.matches)} mot {name}"
    elif o.direct:
        where = f"{_n(o.matches)}, varav {o.direct} mot {name}"
    else:
        where = f"{_n(o.matches)} mot lag med samma formation"
    return f"{_signed(o.resid)} mål/match mot väntat ({where}; {o.wins}V {o.draws}O {o.losses}F)"


def _confidence(best: Option | None) -> str:
    if not best:
        return "låg"
    if best.weight >= 10 and best.score >= 0.4:
        return "hög"
    if best.weight >= 5 and best.score >= 0.2:
        return "medel"
    return "låg"


def recommend(profile: TeamProfile, opponent_home: bool | None = None,
              league_matches=None, ratings=None) -> Recommendation | None:
    """Förslag mot laget i profilen.

    opponent_home: True om motståndaren spelar hemma i den kommande matchen.
    league_matches/ratings: ligadatabasen (league.load_matches / league.ratings), valfri.
    """
    if not profile.matches:
        return None
    likely = profile.most_likely(home=opponent_home) or profile.most_likely()
    opp_formation = likely.get("formation", (None,))[0]

    rows, shapes = direct_evidence(profile, ratings)
    sim_rows, sim_shapes = similar_evidence(league_matches or [], profile.team_id, opp_formation, ratings)
    rows += sim_rows
    shapes += sim_shapes

    backs = _choice("Antal backar", rows, "backs")
    within = [r for r in rows if backs.best and r.values["backs"] == backs.best.value] or rows
    form = _choice("Formation", within, "formation")
    form.options = _options(rows, "formation")
    if form.best:
        form.best = next(o for o in form.options if o.value == form.best.value)

    rec = Recommendation(
        backs=backs, formation=form,
        tactic=_choice("Taktik", rows, "tactic"),
        playstyle=_choice("Spelstil", rows, "playstyle"),
        aggression=_choice("Aggressivitet", rows, "aggression"),
        confidence=_confidence(backs.best),
        direct_matches=sum(1 for r in rows if r.direct),
        similar_matches=len(sim_rows),
        uses_league=ratings is not None,
    )

    for choice in rec.choices:
        best, other = choice.best, choice.runner_up()
        if not best:
            continue
        line = f"{choice.label}: lag med **{best.value}** har gjort {_describe(best, profile.name)}"
        if other:
            line += f". Jämfört med {other.value}: {_describe(other, profile.name)}"
            if other.weight < MIN_WEIGHT:
                line += " – för lite underlag för att väga tungt"
        rec.reasons.append(line + ".")
        worst = choice.options[-1] if len(choice.options) > 1 else None
        if worst and worst.weight >= MIN_WEIGHT and worst.score < -0.25:
            rec.avoid.append(f"{choice.label}: {worst.value} ({_signed(worst.resid)} mål/match mot väntat, "
                             f"{worst.wins}V {worst.draws}O {worst.losses}F)")

    if form.best:
        rec.shape = formation.average_shape([s for f, s in shapes if f == form.best.value])

    side = [m for m in profile.matches if opponent_home is None or m.home == opponent_home] or profile.matches
    rec.opponent_formation = opp_formation
    if opp_formation:
        rec.opponent_shape = formation.average_shape([m.shape for m in side if m.formation == opp_formation])
    return rec
