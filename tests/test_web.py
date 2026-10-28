import json
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from mzanalys import web
from tests.test_recommend import tafte_like_xml


class FakeClient:
    """Står i för ManagerZone: matchlistor och matchfiler från syntetiska data."""

    def __init__(self):
        self.files = {mid: xml for mid, xml in enumerate(tafte_like_xml(), start=1)}

    def team_matchlist_xml(self, team, limit=50, played=True):
        if not played:
            return ('<ManagerZone_MatchList><Match id="999" type="league" date="2026-10-30 20:00:00">'
                    '<Team teamId="2768" teamName="Täfte"/><Team teamId="13659" teamName="Vi"/></Match>'
                    '<Match id="998" type="friendly" date="2026-10-29 20:00:00">'
                    '<Team teamId="13659"/><Team teamId="5"/></Match></ManagerZone_MatchList>')
        return "<ManagerZone_MatchList>" + "".join(
            f'<Match id="{mid}" type="league" date="2026-10-{mid:02d}"/>' for mid in self.files) + "</ManagerZone_MatchList>"

    def match_stats(self, mid):
        return self.files[mid]


class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        client = FakeClient()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(web.App(client)))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.read().decode()

    def test_index(self):
        self.assertIn("MZ Scouting", self._get("/"))

    def test_upcoming(self):
        data = json.loads(self._get("/api/upcoming?team=13659"))
        self.assertEqual(data["matches"], [{"mid": 999, "date": "2026-10-30 20:00:00", "home": False,
                                            "opponent_id": 2768, "opponent": "Täfte"}])

    def test_scout_job(self):
        req = urllib.request.Request(self.base + "/api/scout", data=json.dumps({"team": 2768, "opponent_home": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        job = json.loads(urllib.request.urlopen(req).read())["job"]
        for _ in range(50):
            j = json.loads(self._get(f"/api/job?id={job}"))
            if j["status"] in ("klar", "fel"):
                break
            time.sleep(0.05)
        self.assertEqual(j["status"], "klar", j.get("error"))
        rec = j["result"]["recommendation"]
        self.assertEqual(rec["choices"][0]["best"]["value"], "4 backar")
        self.assertEqual(rec["choices"][1]["best"]["value"], "4-2-1-3")
        self.assertEqual(len(rec["shape"]), 10)
        self.assertEqual(j["result"]["matches_count"], 8)


if __name__ == "__main__":
    unittest.main()
