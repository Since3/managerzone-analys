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

from . import analysis, formation, league, matchlist, recommend
from .fetch import Client, FetchError
from .stats import StatsXmlError, parse_stats

STATIC = Path(__file__).with_name("static")
STATIC_FILES = {
    "/manifest.json": ("manifest.json", "application/manifest+json"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
}


def _option(o: recommend.Option) -> dict:
    return {"value": o.value, "matches": o.matches, "direct": o.direct, "wins": o.wins, "draws": o.draws,
            "losses": o.losses, "ppm": round(o.ppm, 2), "resid": round(o.resid, 2),
            "score": round(o.score, 2), "weight": o.weight}


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


def _strength_table(ratings, teams: dict[int, str], highlight: int) -> list[dict]:
    rows = sorted(ratings.strength.items(), key=lambda kv: -kv[1])
    return [{"team_id": t, "name": teams.get(t, str(t)), "strength": round(s, 2),
             "matches": ratings.matches.get(t, 0), "highlight": t == highlight} for t, s in rows]


def scouting_json(profile: analysis.TeamProfile, opponent_home: bool | None,
                  league_matches=None, ratings=None, teams: dict[int, str] | None = None) -> dict:
    rec = recommend.recommend(profile, opponent_home, league_matches, ratings)
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
        "strengths": _strength_table(ratings, teams or {}, profile.team_id) if ratings else None,
        "recommendation": None if rec is None else {
            "confidence": rec.confidence,
            "uses_league": rec.uses_league,
            "direct_matches": rec.direct_matches,
            "similar_matches": rec.similar_matches,
            "choices": [_choice(c) for c in rec.choices],
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

    def _start(self, target, *args) -> str:
        job_id = uuid.uuid4().hex[:8]
        job = {"status": "startar", "done": 0, "total": 0, "log": [], "result": None, "error": None}
        self.jobs[job_id] = job

        def run():
            try:
                target(job, *args)
            except Exception as e:  # visas i appen i stället för att jobbet tyst dör
                job["error"] = str(e)
                job["status"] = "fel"

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def start_scout(self, team: int, opponent_home: bool | None, my_team: int | None = None) -> str:
        return self._start(self._scout, team, opponent_home, my_team)

    def start_league(self, my_team: int) -> str:
        return self._start(self._league, my_team)

    def _index_path(self, my_team: int):
        return league.index_path(self.client.cache_dir, my_team)

    def league_info(self, my_team: int) -> dict:
        index = league.LeagueIndex.load(self._index_path(my_team))
        if not index:
            return {"exists": False}
        return {"exists": True, "teams": len(index.teams), "matches": len(index.mids), "series": index.series}

    def _league(self, job: dict, my_team: int) -> None:
        def progress(text, done, total):
            job["status"], job["done"], job["total"] = text, done, total

        with self.lock:
            index = league.collect(self.client, my_team, progress)
        index.save(self._index_path(my_team))
        job["log"] = [f"{k}: {v}" for k, v in list(index.failed.items())[:20]]
        job["result"] = self.league_info(my_team)
        job["status"] = "klar"

    def _scout(self, job: dict, team: int, opponent_home: bool | None, my_team: int | None) -> None:
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

        league_matches, ratings, teams = None, None, None
        index = league.LeagueIndex.load(self._index_path(my_team)) if my_team else None
        if index:
            league_matches = league.load_matches(self.client, index)
            ratings = league.ratings(league_matches)
            teams = index.teams
            # Ligadatabasen kan innehålla fler av motståndarens matcher än de senaste.
            known = {m.mid for m in matches}
            matches += [m for m in league_matches if m.mid not in known]
        profile = analysis.build_profile(matches, team)
        if not index:
            profile.matches = profile.matches[: self.antal]
        job["result"] = scouting_json(profile, opponent_home, league_matches, ratings, teams)
        job["status"] = "klar"


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
                elif url.path in STATIC_FILES:
                    name, ctype = STATIC_FILES[url.path]
                    self._send(200, (STATIC / name).read_bytes(), ctype)
                elif url.path == "/api/upcoming":
                    self._json({"matches": app.upcoming(int(q["team"]))})
                elif url.path == "/api/league":
                    self._json(app.league_info(int(q["team"])))
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
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                if url.path == "/api/scout":
                    home = body.get("opponent_home")
                    my_team = body.get("my_team")
                    job = app.start_scout(int(body["team"]), None if home is None else bool(home),
                                          int(my_team) if my_team else None)
                elif url.path == "/api/league":
                    job = app.start_league(int(body["my_team"]))
                else:
                    return self._send(404, b"Hittades inte", "text/plain; charset=utf-8")
                self._json({"job": job})
            except (KeyError, ValueError) as e:
                self._json({"error": f"Felaktig förfrågan: {e}"}, 400)

    return Handler


def lan_address() -> str | None:
    """Datorns adress i det lokala nätverket (ingen trafik skickas)."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def serve(client: Client, port: int = 8765, antal: int = 10, open_browser: bool = True,
          lan: bool = False) -> None:
    app = App(client, antal)
    server = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{port}/"
    print(f"Appen körs på {url}  (stäng med Ctrl+C)")
    if lan:
        ip = lan_address()
        print("\nMOBIL: anslut mobilen till samma wifi och öppna")
        print(f"   http://{ip or '<datorns-IP-adress>'}:{port}/")
        print("Frågar Windows om brandväggen: välj Tillåt för privata nätverk.")
        print("Använd inte det här läget på offentliga nätverk (kafé, hotell).\n")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAvslutar.")
    finally:
        server.server_close()
