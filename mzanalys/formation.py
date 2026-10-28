"""Härledning av formation ur startpositionerna (`Player@origin`) i matchfilen.

Planen i matchfilen är 750 × 1000 enheter. Målvakten står på y = 1000 eller y = 0, och
det avgör lagets spelriktning. Omräkning och zongränser kommer från tredjepartskällor
(docs/teknisk-kartlaggning.md, avsnitt 4, E8) och är en heuristik:

  djup d = avstånd från egen mållinje (0 = eget mål)
  editor_y = 318 − 0.31·d   (taktikeditorns koordinat)
  försvar  : editor_y ≥ 215  ⇔  d ≤ 332
  anfall   : editor_y ≤ 110  ⇔  d ≥ 671
  mittfält : däremellan
"""

from __future__ import annotations

from dataclasses import dataclass

from .stats import Player

PITCH_WIDTH = 750.0
PITCH_LENGTH = 1000.0

DEFENCE_MAX_DEPTH = (318 - 215) / 0.31  # ≈ 332
ATTACK_MIN_DEPTH = (318 - 110) / 0.31  # ≈ 671

# Minsta djupskillnad mellan två mittfältslinjer för att räkna dem som separata linjer.
MIDFIELD_LINE_GAP = 70.0


@dataclass
class Formation:
    zones: str  # försvar-mittfält-anfall, t.ex. "4-3-3"
    lines: str  # med mittfältet uppdelat i linjer, t.ex. "4-2-1-3"
    positions: list[tuple[float, float]]  # (bredd, djup) per utespelare, normaliserat

    def __str__(self) -> str:
        return self.lines


def _attacks_upwards(starters: list[Player]) -> bool | None:
    """True om laget har eget mål vid y = 1000 (målvakten där)."""
    keepers = [p for p in starters if p.goalkeeper and p.origin]
    if len(keepers) != 1:
        return None
    y = keepers[0].origin[1]
    if y >= PITCH_LENGTH / 2:
        return True
    return False


def normalize(starters: list[Player]) -> list[tuple[float, float]] | None:
    """Utespelarnas positioner som (bredd, djup) med eget mål vid djup 0.

    Bredden speglas så att lagets vänsterkant alltid är 0 sett i spelriktningen.
    Returnerar None om målvakten inte går att identifiera entydigt.
    """
    up = _attacks_upwards(starters)
    if up is None:
        return None
    out = []
    for p in starters:
        if p.goalkeeper or not p.origin:
            continue
        x, y = p.origin
        if up:
            out.append((x, PITCH_LENGTH - y))
        else:
            out.append((PITCH_WIDTH - x, y))
    return out


def _split_lines(depths: list[float], gap: float) -> list[int]:
    """Dela sorterade djup i linjer där avståndet mellan grannar överstiger gap."""
    if not depths:
        return []
    depths = sorted(depths)
    sizes = [1]
    for prev, cur in zip(depths, depths[1:]):
        if cur - prev > gap:
            sizes.append(1)
        else:
            sizes[-1] += 1
    return sizes


def derive(starters: list[Player]) -> Formation | None:
    positions = normalize(starters)
    if positions is None or len(positions) != 10:
        return None
    defence = [d for _, d in positions if d <= DEFENCE_MAX_DEPTH]
    attack = [d for _, d in positions if d >= ATTACK_MIN_DEPTH]
    midfield = [d for _, d in positions if DEFENCE_MAX_DEPTH < d < ATTACK_MIN_DEPTH]

    zones = "-".join(str(n) for n in (len(defence), len(midfield), len(attack)))
    parts = [len(defence)] + _split_lines(midfield, MIDFIELD_LINE_GAP) + [len(attack)]
    lines = "-".join(str(n) for n in parts if n)
    return Formation(zones=zones, lines=lines, positions=positions)
