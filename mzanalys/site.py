"""Färdig mobilsida (ögonblicksbild) för publicering, t.ex. med GitHub Pages.

Bygger/uppdaterar ligadatabasen, räknar fram rapport och förslag för varje lag i serien
och skriver en fristående sida där all data ligger inbakad. Sidan behöver ingen server.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, league, matchlist, tracking
from .fetch import Client, FetchError
from .web import STATIC, STATIC_FILES, scouting_json


def snapshot(client: Client, my_team: int, progress=lambda text, done, total: None,
             log_path: str | Path | None = None) -> dict:
    """Ögonblicksbild för mobilsidan. log_path: fil för uppföljning av förslagen (valfri)."""
    index = league.collect(client, my_team, progress)
    index.save(league.index_path(client.cache_dir, my_team))
    matches = league.load_matches(client, index)
    ratings = league.ratings(matches)

    try:
        upcoming = matchlist.upcoming_from_xml(client.team_matchlist_xml(my_team, limit=20, played=False), my_team)
    except (FetchError, ValueError):
        upcoming = []  # kommande matcher är inte verifierade; sidan visar då bara alla lag

    own = analysis.build_profile(matches, my_team)
    reports: dict[str, dict] = {}
    for tid in index.teams:
        profile = own if tid == my_team else analysis.build_profile(matches, tid)
        if not profile.matches:
            continue
        # Ditt eget lag: hur andra har spelat mot dig (ingen egen historik att väga in).
        report = {"total": scouting_json(profile, None, matches, ratings, index.teams,
                                         None if tid == my_team else own)}
        if any(m["opponent_id"] == tid for m in upcoming):
            report["as_home"] = scouting_json(profile, True, matches, ratings, index.teams, own)
            report["as_away"] = scouting_json(profile, False, matches, ratings, index.teams, own)
        reports[str(tid)] = report

    teams = sorted(
        ({"team_id": t, "name": index.teams.get(t, str(t)), "strength": round(s, 2), "is_me": t == my_team}
         for t, s in ratings.strength.items()),
        key=lambda x: -x["strength"],
    )
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    track = None
    if log_path:
        entries = tracking.load(log_path)
        tracking.evaluate(entries, matches, my_team, ratings)
        tracking.record_predictions(entries, upcoming, reports, now)
        tracking.save(log_path, entries)
        track = tracking.summary(entries)

    return {
        "generated": now,
        "tracking": track,
        "my_team": my_team,
        "my_team_name": index.teams.get(my_team),
        "series": index.series,
        "league_matches": len(matches),
        "teams": teams,
        "upcoming": [m for m in upcoming if str(m["opponent_id"]) in reports],
        "reports": reports,
    }


def write_site(snap: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    placeholder = '<script id="snapshot" type="application/json">null</script>'
    if placeholder not in html:
        raise RuntimeError("Platsen för data saknas i index.html.")
    data = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")  # får inte avsluta script-taggen
    (out / "index.html").write_text(
        html.replace(placeholder, f'<script id="snapshot" type="application/json">{data}</script>'),
        encoding="utf-8",
    )
    for name, _ in STATIC_FILES.values():
        shutil.copyfile(STATIC / name, out / name)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return out / "index.html"
