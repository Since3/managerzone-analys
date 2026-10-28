"""Lokal webbapp: python -m mzanalys webb

Servern lyssnar bara på den egna datorn (127.0.0.1). Alla anrop mot ManagerZone går
genom samma klient som kommandoraden: ett i taget, med paus och cache.
"""

from __future__ import annotations

import json
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import analysis, formation, matchlist, recommend
from .fetch import Client, FetchError
from .stats import StatsXmlError, parse_stats

STATIC = Path(__file__).with_name("static")


def _option(o: recommend.Option) -> dict:
    return {"value": o.value, "matches": o.matches, "wins": o.wins, "draws": o.draws,
            "losses": o.losses, "ppm": round(o.ppm, 2), "score": round(o.score, 2)}


def _choice(c: recommend.Choice) -> dict:
    return {"label": c.label, "best": _option(c.best) if c.best else None,
            "options": [_option(o) for o in c.options]}


def _shape(points) -> list[dict] | None:
    if not points:
        return None
    out = []
    for w, d in points:
        ex, ey = formation.to_editor(w, d)
        out.append({"w": round(w), "d": round(d), "editor_x": ex, "editor_y": ey})
    return out


def scouting_json(profile: analysis.TeamProfile, opponent_home: bool | None) -> dict:
    rec = recommend.recommend(profile, opponent_home)
    n = len(profile.matches)
    likely = {
        side: {k: {"value": v, "share": round(s, 2), "matches": m} for k, (v, s, m) in profile.most_likely(h).items()}
        for side, h in (("total", None), ("home", True), ("away", False))
    }
    return {
        "team_id": profile.team_id,
        "name": profile.name,
        "matches_count": n,
        "record": profile.record,
        "goals": list(profile.goals),
        "likely": likely,
        "starters": [{"name": s.name, "role": s.role, "starts": k} for s, k in profile.regular_starters()[:16]],
        "changes_by_state": {k: dict(v) for k, v in profile.changes_by_state().items()},
        "matches_with_changes": sum(1 for m in profile.matches if m.changes),
        "avg_subs": round(sum(m.subs for m in profile.matches) / n, 1) if n else 0,
        "matches": [
            {
                "mid": m.mid, "date": (m.date or "")[:10], "home": m.home, "opponent": m.opponent,
                "goals_for": m.goals_for, "goals_against": m.goals_against, "result": m.result,
                "formation": m.formation, "setup": m.setup, "possession": m.possession,
                "changes": [str(c) for c in m.changes],
                "opponent_formation": m.opponent_formation, "opponent_setup": m.opponent_setup,
            }
            for m in profile.matches
        ],
        "recommendation": None if rec is None else {
            "baseline": round(rec.baseline, 2),
            "confidence": rec.confidence,
            "choices": [_choice(c) for c in (rec.backs, rec.formation, rec.tactic, rec.playstyle, rec.aggression)],
            "reasons": rec.reasons,
            "avoid": rec.avoid,
            "shape": _shape(rec.shape),
            "opponent_formation": rec.opponent_formation,
            "opponent_shape": _shape(rec.opponent_shape),
        },
    }


class App:
    def __init__(self, client: Client, antal: int = 10):
        self.client = client
        self.antal = antal
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()  # ett anrop mot ManagerZone i taget

    def upcoming(self, team: int) -> list[dict]:
        with self.lock:
            xml = self.client.team_matchlist_xml(team, limit=20, played=False)
        return matchlist.upcoming_from_xml(xml, team)

    def start_scout(self, team: int, opponent_home: bool | None) -> str:
        job_id = uuid.uuid4().hex[:8]
        job = {"status": "startar", "done": 0, "total": 0, "log": [], "result": None, "error": None}
        self.jobs[job_id] = job
        threading.Thread(target=self._scout, args=(job, team, opponent_home), daemon=True).start()
        return job_id

    def _scout(self, job: dict, team: int, opponent_home: bool | None) -> None:
        try:
            with self.lock:
                job["status"] = "hämtar matchlista"
                xml = self.client.team_matchlist_xml(team, limit=200)
                mids = matchlist.league_mids_from_xml(xml)[: self.antal]
                if not mids:
                    raise FetchError("Inga ligamatcher hittades för laget.")
                job["total"] = len(mids)
                matches = []
                for mid in mids:
                    job["status"] = f"hämtar match {job['done'] + 1} av {len(mids)}"
                    try:
                        matches.append(parse_stats(self.client.match_stats(mid)))
                    except (FetchError, StatsXmlError) as e:
                        job["log"].append(str(e))
                    job["done"] += 1
            profile = analysis.build_profile(matches, team)
            profile.matches = profile.matches[: self.antal]
            job["result"] = scouting_json(profile, opponent_home)
            job["status"] = "klar"
        except Exception as e:  # visas i appen i stället för att jobbet tyst dör
            job["error"] = str(e)
            job["status"] = "fel"


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # håll terminalen ren
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/upcoming":
                    self._json({"matches": app.upcoming(int(q["team"]))})
                elif url.path == "/api/job":
                    job = app.jobs.get(q.get("id", ""))
                    self._json(job if job else {"error": "okänt jobb"}, 200 if job else 404)
                else:
                    self._send(404, b"Hittades inte", "text/plain; charset=utf-8")
            except (KeyError, ValueError) as e:
                self._json({"error": f"Felaktig förfrågan: {e}"}, 400)
            except Exception as e:
                self._json({"error": str(e)}, 502)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/api/scout":
                return self._send(404, b"Hittades inte", "text/plain; charset=utf-8")
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                home = body.get("opponent_home")
                job = app.start_scout(int(body["team"]), None if home is None else bool(home))
                self._json({"job": job})
            except (KeyError, ValueError) as e:
                self._json({"error": f"Felaktig förfrågan: {e}"}, 400)

    return Handler


def serve(client: Client, port: int = 8765, antal: int = 10, open_browser: bool = True) -> None:
    app = App(client, antal)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{port}/"
    print(f"Appen körs på {url}  (stäng med Ctrl+C)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutar.")
    finally:
        server.server_close()
