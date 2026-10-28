"""Rapporter i Markdown: lagprofil och scoutingrapport inför nästa motståndare."""

from __future__ import annotations

from collections import Counter

from .analysis import TeamProfile

SMALL_SAMPLE = 5  # färre matcher än så: säg det tydligt


def _pct(x: float) -> str:
    return f"{round(x * 100)} %"


def _counter_line(counter: Counter, total: int) -> str:
    if not counter:
        return "–"
    return ", ".join(f"{k} {v}/{total}" for k, v in counter.most_common())


def _ppm(r: dict[str, int]) -> float:
    n = sum(r.values())
    return (3 * r["V"] + r["O"]) / n if n else 0.0


def _results_table(title: str, rows: dict[str, dict[str, int]], note: str = "") -> list[str]:
    out = [f"### {title}", ""]
    if note:
        out += [note, ""]
    out += ["| | Matcher | V | O | F | Poäng/match |", "|---|---|---|---|---|---|"]
    for k, r in sorted(rows.items(), key=lambda kv: (-_ppm(kv[1]), -sum(kv[1].values()))):
        out.append(f"| {k} | {sum(r.values())} | {r['V']} | {r['O']} | {r['F']} | {_ppm(r):.2f} |")
    return out + [""]


def _likely_lines(profile: TeamProfile) -> list[str]:
    out = []
    for label, home in (("Totalt", None), ("Hemma", True), ("Borta", False)):
        likely = profile.most_likely(home)
        if not likely:
            continue
        n = next(iter(likely.values()))[2]
        parts = [f"{k} **{v}** ({_pct(share)})" for k, (v, share, _) in likely.items()]
        out.append(f"- **{label}** ({n} matcher): " + ", ".join(parts))
    return out


def _in_match_lines(profile: TeamProfile) -> list[str]:
    n = len(profile.matches)
    with_changes = sum(1 for m in profile.matches if m.changes)
    out = [f"- Gjorde taktikändringar i {with_changes} av {n} matcher."]
    labels = {"leder": "När de leder", "lika": "Vid lika ställning", "under": "När de ligger under",
              "okänd": "Okänd ställning"}
    for state in ("under", "lika", "leder", "okänd"):
        c = profile.changes_by_state().get(state)
        if c:
            out.append(f"- {labels[state]}: " + ", ".join(f"{k} ({v})" for k, v in c.most_common()))
    minutes = profile.change_minutes()
    if minutes:
        out.append(f"- Ändringarna skedde mellan minut {minutes[0]} och {minutes[-1]}, median {minutes[len(minutes) // 2]}.")
    avg_subs = sum(m.subs for m in profile.matches) / n
    avg_min = profile.average_sub_minute()
    out.append(
        f"- Byten per match: {avg_subs:.1f}"
        + (f", genomsnittlig minut {avg_min:.0f}" if avg_min is not None else "")
    )
    return out


def _starters_table(profile: TeamProfile, limit: int = 16) -> list[str]:
    n = len(profile.matches)
    out = ["| Spelare | Starter | Vanligaste roll |", "|---|---|---|"]
    for s, starts in profile.regular_starters()[:limit]:
        out.append(f"| {s.name} | {starts}/{n} | {s.role} |")
    return out


def _match_table(profile: TeamProfile) -> list[str]:
    out = [
        "| Datum | H/B | Motståndare | Res. | Formation | Upplägg | Bollinnehav | Ändringar | Motst. formation | Motst. upplägg |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in profile.matches:
        score = f"{m.goals_for}–{m.goals_against} {m.result}" if m.goals_for is not None else "?"
        out.append(
            "| {date} | {ha} | {opp} | {score} | {f} | {setup} | {pos} | {ch} | {of} | {os} |".format(
                date=(m.date or "?")[:10],
                ha="H" if m.home else "B",
                opp=m.opponent.replace("|", "/"),
                score=score,
                f=m.formation or "?",
                setup=m.setup,
                pos=f"{m.possession} %" if m.possession else "–",
                ch="; ".join(str(c) for c in m.changes) or "–",
                of=m.opponent_formation or "?",
                os=m.opponent_setup,
            )
        )
    return out


def _header(profile: TeamProfile, title: str) -> list[str]:
    n = len(profile.matches)
    rec = profile.record
    gf, ga = profile.goals
    out = [
        f"# {title}: {profile.name} (lag-ID {profile.team_id})",
        "",
        f"Underlag: {n} ligamatcher. Deras resultat: {rec['V']}V {rec['O']}O {rec['F']}F, mål {gf}–{ga}.",
        "",
    ]
    if 0 < n < SMALL_SAMPLE:
        out += [f"> **Litet underlag ({n} matcher).** Se mönstren som indikationer, inte som säkra slutsatser.", ""]
    return out


FOOTER = [
    "",
    "---",
    "Formationen är härledd ur startpositionerna med en heuristik och kan avvika från lagets egen benämning. "
    "Matchfilen visar bara regler som faktiskt utlöstes, inte villkoren bakom dem eller regler som aldrig användes.",
]


def render_scouting(profile: TeamProfile) -> str:
    """Scoutingrapport inför en match mot laget i profilen."""
    lines = _header(profile, "Scoutingrapport")
    if not profile.matches:
        return "\n".join(lines + ["Inga ligamatcher att analysera."]) + "\n"

    lines += ["## 1. Väntat upplägg", ""]
    lines += _likely_lines(profile)
    lines += [
        "",
        "Procenten anger hur ofta värdet förekom. Under cirka 60 % växlar laget och prognosen är osäker. "
        "Spelar du hemma möter du deras bortaupplägg, och tvärtom.",
        "",
        f"- Formationer: {_counter_line(profile.formations(), len(profile.matches))}",
        f"- Taktik: {_counter_line(profile.tactics(), len(profile.matches))}",
        f"- Spelstil: {_counter_line(profile.playstyles(), len(profile.matches))}",
        f"- Aggressivitet: {_counter_line(profile.aggressions(), len(profile.matches))}",
        "",
        "## 2. Trolig startelva",
        "",
    ]
    lines += _starters_table(profile)
    lines += ["", "## 3. Hur de reagerar under matchen", ""]
    lines += _in_match_lines(profile)

    lines += [
        "",
        "## 4. Vad har fungerat mot dem?",
        "",
        "Resultaten räknas här från **deras motståndares** sida: V betyder att laget som mötte dem vann.",
        "",
    ]
    lines += _results_table("Motståndarnas formation", profile.results_by(lambda m: m.opponent_formation, True))
    lines += _results_table("Motståndarnas taktik/spelstil/aggressivitet",
                            profile.results_by(lambda m: m.opponent_setup, True))
    lines += _results_table(
        "Deras egen formation",
        profile.results_by(lambda m: m.formation),
        "Här räknas resultatet från deras sida: med vilken formation har de lyckats bäst?",
    )
    lines += [
        "Ta hänsyn till motståndarnas styrka: en vinst för ett topplag säger mindre än en vinst för ett bottenlag.",
        "",
        "## 5. Alla matcher",
        "",
    ]
    lines += _match_table(profile)
    return "\n".join(lines + FOOTER) + "\n"


def render(profile: TeamProfile) -> str:
    """Allmän lagprofil (används för det egna laget)."""
    lines = _header(profile, "Taktisk profil")
    if not profile.matches:
        return "\n".join(lines + ["Inga matcher att analysera."]) + "\n"
    lines += ["## Upplägg", ""]
    lines += _likely_lines(profile)
    lines += ["", "## Under matchen", ""]
    lines += _in_match_lines(profile)
    lines += [""]
    lines += _results_table("Per formation", profile.results_by(lambda m: m.formation))
    lines += _results_table("Per taktik/spelstil/aggressivitet", profile.results_by(lambda m: m.setup))
    lines += _results_table("Per motståndarens formation", profile.results_by(lambda m: m.opponent_formation))
    lines += ["## Startspelare", ""]
    lines += _starters_table(profile)
    lines += ["", "## Matcher", ""]
    lines += _match_table(profile)
    return "\n".join(lines + FOOTER) + "\n"
