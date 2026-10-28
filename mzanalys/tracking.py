"""Uppföljning av förslagen: vad appen föreslog inför varje ligamatch och hur det gick.

Loggen är en lista med en post per kommande ligamatch (nyckel: match-ID):
- prediction: förslaget (senast beräknade före matchen) per dimension,
- outcome: när matchen spelats, vad du faktiskt spelade, resultatet och målskillnaden
  jämfört med det väntade utifrån lagens styrka.

En match räknas som att du följde förslaget om minst FOLLOW_MIN av de fem valen stämde.
Förslag sparas och uppdateras bara före avspark (matchtiden anges i svensk tid). Poster som
råkat sparas efter avspark tas bort, eftersom de inte är riktiga förhandsförslag.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import analysis
from .recommend import _values

LOG_NAME = "prognoser.json"
DIMENSIONS = ("backs", "formation", "tactic", "playstyle", "aggression")
FOLLOW_MIN = 4
POINTS = {"V": 3, "O": 1, "F": 0}


def _mz_zone():
    """ManagerZones tider är svensk tid. Utan tidszonsdata (t.ex. Windows) används UTC+1."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Europe/Stockholm")
    except Exception:
        return timezone(timedelta(hours=1))


def kickoff(date: str | None) -> datetime | None:
    """Avsparkstid ur matchlistans datum, t.ex. '2026-10-28 15:15'."""
    if not date:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(date, fmt).replace(tzinfo=_mz_zone())
        except ValueError:
            continue
    return None


def _before_kickoff(entry_or_match: dict, when: str) -> bool:
    ko = kickoff(entry_or_match.get("date"))
    return ko is None or datetime.fromisoformat(when) < ko


def load(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def save(path: str | Path, entries: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")


def drop_late(entries: list[dict]) -> None:
    """Ta bort poster som sparats efter avspark; de är inga riktiga förhandsförslag."""
    entries[:] = [e for e in entries if _before_kickoff(e, e["created"])]


def record_predictions(entries: list[dict], upcoming: list[dict], reports: dict, now: str) -> None:
    """Spara eller uppdatera förslaget för varje kommande match, bara före avspark."""
    drop_late(entries)
    by_mid = {e["mid"]: e for e in entries}
    for m in upcoming:
        if not _before_kickoff(m, now):
            continue  # matchen har börjat; förslaget får inte ändras eller skapas nu
        report = reports.get(str(m["opponent_id"]), {})
        variant = report.get("as_away" if m["home"] else "as_home") or report.get("total")
        rec = (variant or {}).get("recommendation")
        if not rec:
            continue
        entry = by_mid.get(m["mid"])
        if entry and entry.get("outcome"):
            continue  # redan spelad och utvärderad; förslaget får inte ändras i efterhand
        if not entry:
            entry = {"mid": m["mid"], "created": now}
            entries.append(entry)
            by_mid[m["mid"]] = entry
        entry.update({
            "date": m.get("date"), "opponent_id": m["opponent_id"], "opponent": m["opponent"],
            "home": m["home"], "updated": now, "confidence": rec.get("confidence"),
            "prediction": {dim: (c["best"] or {}).get("value") for dim, c in zip(DIMENSIONS, rec["choices"])},
            "confidences": {dim: c.get("confidence") for dim, c in zip(DIMENSIONS, rec["choices"])},
        })
    entries.sort(key=lambda e: (e.get("date") or "", e["mid"]))


def evaluate(entries: list[dict], matches, my_team: int, ratings=None) -> None:
    """Fyll i utfallet för spelade matcher som har ett förslag men inget utfall än."""
    drop_late(entries)
    by_mid = {m.mid: m for m in matches}
    for e in entries:
        if e.get("outcome") or e["mid"] not in by_mid:
            continue
        match = by_mid[e["mid"]]
        if not any(t.id == my_team for t in match.teams):
            continue
        s = analysis.summarize(match, my_team)
        if s.goals_for is None or s.goals_against is None:
            continue
        played = _values(s)
        followed = [d for d in DIMENSIONS if e["prediction"].get(d) and e["prediction"][d] == played.get(d)]
        expected = ratings.expected_gd(my_team, s.opponent_id, home=s.home) if ratings else 0.0
        e["outcome"] = {
            "played": played, "followed": followed,
            "goals_for": s.goals_for, "goals_against": s.goals_against, "result": s.result,
            "gd": s.goals_for - s.goals_against, "expected": round(expected, 2),
        }


def _group(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"matches": 0}
    results = [r["outcome"]["result"] for r in rows]
    return {
        "matches": n,
        "wins": results.count("V"), "draws": results.count("O"), "losses": results.count("F"),
        "ppm": round(sum(POINTS.get(x, 0) for x in results) / n, 2),
        "resid": round(sum(r["outcome"]["gd"] - r["outcome"]["expected"] for r in rows) / n, 2),
    }


def summary(entries: list[dict]) -> dict:
    done = [e for e in entries if e.get("outcome")]
    followed = [e for e in done if len(e["outcome"]["followed"]) >= FOLLOW_MIN]
    other = [e for e in done if len(e["outcome"]["followed"]) < FOLLOW_MIN]
    per_dimension = {
        d: {"followed": _group([e for e in done if d in e["outcome"]["followed"]]),
            "not_followed": _group([e for e in done if e["prediction"].get(d) and d not in e["outcome"]["followed"]])}
        for d in DIMENSIONS
    }
    return {
        "follow_min": FOLLOW_MIN,
        "evaluated": len(done),
        "pending": len(entries) - len(done),
        "followed": _group(followed),
        "not_followed": _group(other),
        "per_dimension": per_dimension,
        "entries": list(reversed(entries)),  # nyaste först
    }
