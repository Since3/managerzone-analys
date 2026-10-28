import unittest

from mzanalys import analysis, formation, recommend
from mzanalys.stats import parse_stats
from tests.helpers import F_352, F_41212, F_4213, make_stats_xml

THEM = (2768, "Täfte")
WINGS = ("wings", "normal", "normal")
SHORT = ("shortpass", "normal", "normal")


def _vs(mid, shape, setup, score_them, score_other, them_home=True):
    """Matchfil (XML) för Täfte (romb, kortpass) mot ett lag med given formation och upplägg."""
    if them_home:
        xml = make_stats_xml(mid, THEM, (mid, f"Lag{mid}"), (score_them, score_other),
                             home_shape=F_41212, away_shape=shape, home_setup=SHORT, away_setup=setup,
                             date=f"2026-10-{mid:02d} 20:00:00")
    else:
        xml = make_stats_xml(mid, (mid, f"Lag{mid}"), THEM, (score_other, score_them),
                             home_shape=shape, away_shape=F_41212, home_setup=setup, away_setup=SHORT,
                             date=f"2026-10-{mid:02d} 20:00:00")
    return xml


def tafte_like_xml():
    """Som det riktiga underlaget: fyrbackslag 4V 1F mot Täfte, trebackslag 0V 3F."""
    return [
        _vs(1, F_4213, WINGS, 2, 3, them_home=False),
        _vs(2, F_4213, SHORT, 0, 4),
        _vs(3, F_352, SHORT, 5, 1, them_home=False),
        _vs(4, F_4213, WINGS, 2, 3),
        _vs(5, F_4213, ("shortpass", "offensive", "aggressive"), 1, 2, them_home=False),
        _vs(6, F_352, ("shortpass", "offensive", "passive"), 6, 1),
        _vs(7, F_352, SHORT, 4, 0, them_home=False),
        _vs(8, F_4213, ("longball", "normal", "normal"), 3, 2),
    ]


def _tafte_like():
    return [parse_stats(x) for x in tafte_like_xml()]


class RecommendTest(unittest.TestCase):
    def setUp(self):
        self.profile = analysis.build_profile(_tafte_like(), 2768)
        self.rec = recommend.recommend(self.profile, opponent_home=True)

    def test_recommends_four_backs_and_4213(self):
        self.assertEqual(self.rec.backs.best.value, "4 backar")
        self.assertEqual((self.rec.backs.best.wins, self.rec.backs.best.losses), (4, 1))
        self.assertEqual(self.rec.formation.best.value, "4-2-1-3")
        self.assertEqual(self.rec.tactic.best.value, "wings")

    def test_single_match_does_not_win(self):
        # "aggressive" har bara en match (en vinst) och ska inte slå "normal" med sex matcher.
        self.assertEqual(self.rec.aggression.best.value, "normal")
        self.assertEqual(self.rec.playstyle.best.value, "normal")

    def test_shrinkage_and_baseline(self):
        self.assertAlmostEqual(self.rec.baseline, 12 / 8)
        best = self.rec.backs.best
        self.assertAlmostEqual(best.ppm, 12 / 5)
        self.assertAlmostEqual(best.score, (12 + 2 * 1.5) / 7)

    def test_reasons_avoid_and_shapes(self):
        self.assertTrue(any("4 backar" in r for r in self.rec.reasons))
        self.assertTrue(any("3 backar" in a for a in self.rec.avoid))
        self.assertEqual(len(self.rec.shape), 10)
        self.assertEqual(self.rec.opponent_formation, "4-1-2-1-2")
        self.assertEqual(len(self.rec.opponent_shape), 10)
        self.assertIn(self.rec.confidence, ("medel", "hög"))

    def test_editor_coordinates(self):
        self.assertEqual(formation.to_editor(371, 825), (103, 63))
        self.assertEqual(formation.to_editor(97, 307), (33, 223))


if __name__ == "__main__":
    unittest.main()
