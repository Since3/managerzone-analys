import unittest

from mzanalys import analysis, recommend, tracking
from mzanalys.stats import parse_stats
from tests.helpers import make_stats_xml
from tests.test_recommend import _tafte_like

ME, OPP = 13659, 2768


def _match(mid, cards, score=(2, 0)):
    return parse_stats(make_stats_xml(mid, (ME, "Vi"), (OPP, "Täfte"), score, cards=cards))


class RedCardTest(unittest.TestCase):
    def test_parsing_and_early_flag(self):
        m = _match(1, (((4, "red"), (30, "yellow")), ((70, "second yellow"),)))
        self.assertEqual([(c.team_id, c.minute) for c in m.red_cards], [(ME, 4), (OPP, 70)])
        s = analysis.summarize(m, ME)
        self.assertEqual((s.red_for, s.red_against, s.early_red), ([4], [70], True))
        late = analysis.summarize(_match(2, ((), ((75, "red"),))), ME)
        self.assertFalse(late.early_red)
        self.assertFalse(analysis.summarize(_match(3, (((10, "yellow"),), ())), ME).early_red)

    def test_recommendation_weight_is_halved(self):
        profile = analysis.build_profile(_tafte_like(), OPP)
        base = recommend.recommend(profile).backs.best.weight
        # Samma matcher, men alla med ett tidigt rött kort: vikten halveras.
        for m in profile.matches:
            m.red_for = [5]
        rec = recommend.recommend(profile)
        self.assertAlmostEqual(rec.backs.best.weight, base * recommend.RED_CARD_WEIGHT)
        self.assertEqual(rec.backs.best.red_matches, rec.backs.best.matches)

    def test_tracking_backfills_and_excludes(self):
        # Ett utfall sparat innan röda kort följdes upp (som matchen mot Täfte).
        entry = {"mid": 9, "date": "2026-11-01 13:00", "created": "2026-10-28T16:00:00+00:00",
                 "prediction": {d: "x" for d in tracking.DIMENSIONS},
                 "outcome": {"played": {}, "followed": list(tracking.DIMENSIONS), "goals_for": 2,
                             "goals_against": 0, "result": "V", "gd": 2, "expected": 1.0}}
        entries = [entry]
        tracking.evaluate(entries, [_match(9, (((4, "red"),), ()))], ME)
        self.assertEqual(entry["outcome"]["red_cards"], {"for": [4], "against": [], "early": True})
        s = tracking.summary(entries)
        self.assertEqual((s["evaluated"], s["excluded_red"], s["pending"]), (0, 1, 0))
        self.assertEqual(s["followed"], {"matches": 0})


if __name__ == "__main__":
    unittest.main()
