"""Rapport i Markdown för en lagprofil."""

from __future__ import annotations

from collections import Counter

from .analysis import TeamProfile


def _pct(x: float) -> str:
    return f"{round(x * 100)} %"


def _counter_line(counter: Counter, total: int) -> str:
    if not counter:
        return "–"
    return ", ".join(f"{k} {v}/{total}" for k, v in counter.most_common())


def _results_table(title: str, rows: dict[str, dict[str, int]]) -> list[str]:
    out = [f"### {title}", "", "| | Matcher | V | O | F | Poäng/match |", "|---|---|---|---|---|---|"]
    for k, r in sorted(rows.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(r.values())
        ppm = (3 * r["V"] + r["O"]) / n if n else 0
        out.append(f"| {k} | {n} | {r['V']} | {r['O']} | {r['F']} | {ppm:.2f} |")
    return out + [""]


def render(profile: TeamProfile) -> str:
    n = len(profile.matches)
    rec = profile.record
    gf, ga = profile.goals
    lines = [
        f"# Taktisk profil: {profile.name} (lag-ID {profile.team_id})",
        "",
        f"Underlag: {n} ligamatcher. Resultat: {rec['V']}V {rec['O']}O {rec['F']}F, mål {gf}–{ga}.",
        "",
    ]
    if not n:
        return "\n".join(lines + ["Inga matcher att analysera."])

    lines += ["## Mest sannolika upplägg", ""]
    likely = profile.most_likely()
    for label, (value, share) in likely.items():
        lines.append(f"- **{label.capitalize()}:** {value} ({_pct(share)} av matcherna)")
    lines += [
        "",
        "Andelen anger hur stabilt laget är. Under cirka 60 % växlar laget upplägg och prognosen är osäker.",
        "",
        "## Fördelning",
        "",
        f"- Formation (linjer): {_counter_line(profile.formations(), n)}",
        f"- Formation (zoner F-M-A): {_counter_line(profile.formation_zones(), n)}",
        f"- Taktik: {_counter_line(profile.tactics(), n)}",
        f"- Spelstil: {_counter_line(profile.playstyles(), n)}",
        f"- Aggressivitet: {_counter_line(profile.aggressions(), n)}",
        "",
        "## Under matchen",
        "",
    ]
    changes = profile.change_patterns()
    with_changes = sum(1 for m in profile.matches if m.changes)
    lines.append(f"- Taktikändringar i {with_changes} av {n} matcher: {_counter_line(changes, n)}")
    avg_subs = sum(m.subs for m in profile.matches) / n
    avg_min = profile.average_sub_minute()
    lines.append(
        f"- Byten per match: {avg_subs:.1f}"
        + (f", genomsnittlig minut {avg_min:.0f}" if avg_min is not None else "")
    )
    lines += [
        "",
        "Endast utlösta regler syns i matchfilen. Villkoren bakom dem (t.ex. ställning) syns inte.",
        "",
        "## Resultat per upplägg",
        "",
    ]
    lines += _results_table("Per formation", profile.results_by(lambda m: m.formation))
    lines += _results_table("Per taktik/spelstil/aggressivitet", profile.results_by(lambda m: m.setup))
    lines += _results_table("Per motståndarens formation", profile.results_by(lambda m: m.opponent_formation))

    lines += [
        "## Matcher",
        "",
        "| Datum | H/B | Motståndare | Res. | Formation | Upplägg | Bollinnehav | Ändringar | Motst. formation | Motst. upplägg |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in profile.matches:
        score = f"{m.goals_for}–{m.goals_against} {m.result}" if m.goals_for is not None else "?"
        lines.append(
            "| {date} | {ha} | {opp} | {score} | {f} | {setup} | {pos} | {ch} | {of} | {os} |".format(
                date=(m.date or "?")[:10],
                ha="H" if m.home else "B",
                opp=m.opponent.replace("|", "/"),
                score=score,
                f=m.formation or "?",
                setup=m.setup,
                pos=f"{m.possession} %" if m.possession else "–",
                ch="; ".join(m.changes) or "–",
                of=m.opponent_formation or "?",
                os=m.opponent_setup,
            )
        )
    lines += [
        "",
        "---",
        "Formationen är härledd ur startpositionerna med en heuristik och kan avvika från lagets egen benämning.",
    ]
    return "\n".join(lines) + "\n"
