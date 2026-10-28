import json
import re
import tempfile
import unittest
from pathlib import Path

from mzanalys import site
from tests.test_league import ME, TAFTE, FakeLeagueClient


class UpcomingClient(FakeLeagueClient):
    def team_matchlist_xml(self, team, limit=50, played=True):
        if played:
            return super().team_matchlist_xml(team, limit, played)
        return ('<ManagerZone_MatchList><Match id="1628449999" type="league" date="2026-11-01 18:00:00">'
                f'<Team teamId="{TAFTE}" teamName="Täfte"/><Team teamId="{ME}" teamName="Vi"/></Match>'
                '</ManagerZone_MatchList>')


class SiteTest(unittest.TestCase):
    def test_snapshot_and_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = UpcomingClient(Path(tmp) / "data" / "matches")
            snap = site.snapshot(client, ME)
            self.assertEqual(snap["series"], "div3.1")
            self.assertEqual(set(snap["reports"]), {str(TAFTE), "50", "51"})
            self.assertEqual([m["opponent_id"] for m in snap["upcoming"]], [TAFTE])
            self.assertEqual(set(snap["reports"][str(TAFTE)]), {"total", "as_home", "as_away"})
            self.assertNotIn(ME, [t["team_id"] for t in snap["teams"]])
            rec = snap["reports"][str(TAFTE)]["total"]["recommendation"]
            self.assertEqual(rec["own_matches"], 3)  # dina tre ligamatcher i testligan
            self.assertTrue(any(c["own"] for c in rec["choices"]))

            page = site.write_site(snap, Path(tmp) / "site")
            html = page.read_text(encoding="utf-8")
            data = re.search(r'<script id="snapshot" type="application/json">(.*?)</script>', html, re.S).group(1)
            self.assertEqual(json.loads(data)["my_team"], ME)
            for name in ("manifest.json", "icon-192.png", "icon-512.png", ".nojekyll"):
                self.assertTrue((page.parent / name).exists(), name)

    def test_script_end_tag_is_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = {"my_team": 1, "evil": "</script><b>x</b>"}
            html = site.write_site(snap, tmp).read_text(encoding="utf-8")
            self.assertNotIn("</script><b>", html)


if __name__ == "__main__":
    unittest.main()
