"""Förslag på upplägg mot en motståndare, utifrån hur andra lag har gått mot dem.

Metod: för varje egenskap (antal backar, formation, taktik, spelstil, aggressivitet)
grupperas motståndarens matcher efter vad laget som mötte dem använde. Varje grupp får
poäng per match sett från det mötande lagets sida. Små grupper dras mot genomsnittet
(empirisk Bayes-krympning med PRIOR_WEIGHT fiktiva matcher), så att en enstaka vinst
inte väger lika tungt som ett mönster över flera matcher.

Förslaget bygger på historiska resultat, inte på spelmotorn. Spelarnas kvalitet
påverkar utfallet minst lika mycket.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import formation
from .analysis import MatchSummary, TeamProfile

PRIOR_WEIGHT = 2.0
MIN_MATCHES = 2  # ett alternativ föreslås bara om det har minst så många matcher bakom sig

POINTS = {"V": 3, "O": 1, "F": 0}


@dataclass
class Option:
    value: str
    matches: int
    wins: int
    draws: int
    losses: int
    ppm: float  # faktiska poäng per match för laget som mötte dem
    score: float  # krympt poäng per match


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
    baseline: float  # poäng per match för motståndarnas motståndare i snitt
    backs: Choice
    formation: Choice
    tactic: Choice
    playstyle: Choice
    aggression: Choice
    confidence: str  # låg | medel | hög
    reasons: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    shape: list[tuple[float, float]] | None = None  # föreslagen formation, genomsnittliga positioner
    opponent_formation: str | None = None
    opponent_shape: list[tuple[float, float]] | None = None


def _options(matches: list[MatchSummary], key, baseline: float) -> list[Option]:
    groups: dict[str, list[str]] = {}
    for m in matches:
        value = key(m)
        if value:
            groups.setdefault(value, []).append(m.opponent_result)
    out = []
    for value, results in groups.items():
        n = len(results)
        pts = sum(POINTS.get(r, 0) for r in results)
        out.append(
            Option(
                value=value,
                matches=n,
                wins=results.count("V"),
                draws=results.count("O"),
                losses=results.count("F"),
                ppm=pts / n,
                score=(pts + PRIOR_WEIGHT * baseline) / (n + PRIOR_WEIGHT),
            )
        )
    out.sort(key=lambda o: (-o.score, -o.matches))
    return out


def _best(options: list[Option]) -> Option | None:
    """Högst justerad poäng bland alternativ med tillräckligt underlag, annars bland alla."""
    solid = [o for o in options if o.matches >= MIN_MATCHES]
    pool = solid or options
    return pool[0] if pool else None


def _choice(label: str, matches, key, baseline) -> Choice:
    options = _options(matches, key, baseline)
    return Choice(label, _best(options), options)


def _record(o: Option) -> str:
    return f"{o.wins}V {o.draws}O {o.losses}F"


def _confidence(choice: Choice, baseline: float, total: int) -> str:
    best = choice.best
    if not best or total < 4:
        return "låg"
    lift = best.score - baseline
    if best.matches >= 4 and lift >= 0.5:
        return "hög"
    if best.matches >= 2 and lift >= 0.25:
        return "medel"
    return "låg"


def recommend(profile: TeamProfile, opponent_home: bool | None = None) -> Recommendation | None:
    """Förslag mot laget i profilen.

    opponent_home: True om motståndaren spelar hemma i den kommande matchen. Används för
    att visa deras väntade formation (hemma- respektive bortaupplägg).
    """
    ms = profile.matches
    if not ms:
        return None
    baseline = sum(POINTS.get(m.opponent_result, 0) for m in ms) / len(ms)

    backs = _choice("Antal backar", ms, lambda m: m.opponent_backs, baseline)
    # Formation väljs inom det bästa antalet backar, så att förslaget hänger ihop.
    within = [m for m in ms if backs.best and m.opponent_backs == backs.best.value] or ms
    form = _choice("Formation", within, lambda m: m.opponent_formation, baseline)
    form.options = _options(ms, lambda m: m.opponent_formation, baseline)
    if form.best:
        form.best = next(o for o in form.options if o.value == form.best.value)
    tactic = _choice("Taktik", ms, lambda m: m.opponent_tactic, baseline)
    playstyle = _choice("Spelstil", ms, lambda m: m.opponent_playstyle, baseline)
    aggression = _choice("Aggressivitet", ms, lambda m: m.opponent_aggression, baseline)

    rec = Recommendation(
        baseline=baseline,
        backs=backs,
        formation=form,
        tactic=tactic,
        playstyle=playstyle,
        aggression=aggression,
        confidence=_confidence(backs, baseline, len(ms)),
    )

    for choice in (backs, form, tactic, playstyle, aggression):
        best, other = choice.best, choice.runner_up()
        if not best:
            continue
        line = (f"{choice.label}: lag med **{best.value}** har gått {_record(best)} mot dem "
                f"({best.ppm:.1f} p/match)")
        if other:
            line += f", jämfört med {other.value}: {_record(other)} ({other.ppm:.1f} p/match)"
            if other.matches < MIN_MATCHES:
                line += " – för få matcher för att väga tungt"
        rec.reasons.append(line + ".")
        worst = choice.options[-1] if len(choice.options) > 1 else None
        if worst and worst.matches >= 2 and worst.ppm < baseline:
            rec.avoid.append(f"{choice.label}: {worst.value} ({_record(worst)} mot dem)")

    if form.best:
        shapes = [m.opponent_shape for m in ms if m.opponent_formation == form.best.value]
        rec.shape = formation.average_shape(shapes)

    side = [m for m in ms if opponent_home is None or m.home == opponent_home] or ms
    likely = profile.most_likely(home=opponent_home) or profile.most_likely()
    if "formation" in likely:
        rec.opponent_formation = likely["formation"][0]
        rec.opponent_shape = formation.average_shape(
            [m.shape for m in side if m.formation == rec.opponent_formation]
        )
    return rec
