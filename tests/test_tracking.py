import tempfile
import unittest
from pathlib import Path

from mzanalys import site, tracking
from tests.helpers import F_4213, F_41212
from tests.test_league import ME, TAFTE, FakeLeagueClient, _match

NEXT = 1628449999


class ScheduleClient(FakeLeagueClient):
    """Testligan plus en kommande match mot Täfte som kan 'spelas' mitt i testet."""

    played_next = False

    def team_matchlist_xml(self, team, limit=50, played=True):
        if played:
            return super().team_matchlist_xml(team, limit, played)
        if self.played_next:
            return "<ManagerZone_MatchList/>"
        return ('<ManagerZone_MatchList><Match id="%d" type="league" date="2026-11-01 18:00:00">'
                '<Team teamId="%d" teamName="Vi"/><Team teamId="%d" teamName="Täfte"/></Match>'
                '</ManagerZone_MatchList>' % (NEXT, ME, TAFTE))

    def play_next(self):
        self.played_next = True
        self.files[NEXT] = _match(NEXT, ME, TAFTE, (2, 1), home_shape=F_4213, away_shape=F_41212,
                                  home_setup=("wings", "normal", "normal"))


class TrackingTest(unittest.TestCase):
    def test_prediction_then_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = ScheduleClient(Path(tmp) / "data" / "matches")
            log = Path(tmp) / "data" / tracking.LOG_NAME

            snap = site.snapshot(client, ME, log_path=log)
            (entry,) = tracking.load(log)
            self.assertEqual((entry["mid"], entry["opponent_id"], entry["home"]), (NEXT, TAFTE, True))
            self.assertEqual(set(entry["prediction"]), set(tracking.DIMENSIONS))
            self.assertNotIn("outcome", entry)
            self.assertEqual((snap["tracking"]["evaluated"], snap["tracking"]["pending"]), (0, 1))
            prediction = dict(entry["prediction"])

            client.play_next()
            snap = site.snapshot(client, ME, log_path=log)
            (entry,) = tracking.load(log)
            out = entry["outcome"]
            self.assertEqual(entry["prediction"], prediction)  # ändras inte i efterhand
            self.assertEqual((out["goals_for"], out["goals_against"], out["result"]), (2, 1, "V"))
            self.assertEqual(out["played"], {"backs": "4 backar", "formation": "4-2-1-3", "tactic": "wings",
                                             "playstyle": "normal", "aggression": "normal"})
            self.assertEqual(out["followed"], [d for d in tracking.DIMENSIONS if prediction[d] == out["played"][d]])
            summary = snap["tracking"]
            self.assertEqual((summary["evaluated"], summary["pending"]), (1, 0))
            group = summary["followed"] if len(out["followed"]) >= tracking.FOLLOW_MIN else summary["not_followed"]
            self.assertEqual((group["matches"], group["wins"], group["ppm"]), (1, 1, 3.0))

            # Tredje körningen ändrar ingenting.
            site.snapshot(client, ME, log_path=log)
            self.assertEqual(tracking.load(log), [entry])

    def test_summary_groups(self):
        def e(mid, followed, result, gd, expected):
            return {"mid": mid, "prediction": {d: "x" for d in tracking.DIMENSIONS},
                    "outcome": {"followed": followed, "result": result, "gd": gd, "expected": expected}}
        entries = [e(1, list(tracking.DIMENSIONS), "V", 2, 0.5), e(2, ["backs"], "F", -1, 0.0),
                   e(3, list(tracking.DIMENSIONS[:4]), "O", 0, -0.5), {"mid": 4, "prediction": {}}]
        s = tracking.summary(entries)
        self.assertEqual((s["evaluated"], s["pending"]), (3, 1))
        self.assertEqual(s["followed"], {"matches": 2, "wins": 1, "draws": 1, "losses": 0, "ppm": 2.0, "resid": 1.0})
        self.assertEqual(s["not_followed"]["matches"], 1)
        self.assertEqual(s["per_dimension"]["aggression"]["not_followed"]["matches"], 2)
        self.assertEqual([x["mid"] for x in s["entries"]], [4, 3, 2, 1])

    def test_missing_or_broken_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(tracking.load(Path(tmp) / "saknas.json"), [])
            broken = Path(tmp) / "trasig.json"
            broken.write_text("{inte json", encoding="utf-8")
            self.assertEqual(tracking.load(broken), [])


if __name__ == "__main__":
    unittest.main()
