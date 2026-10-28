import unittest

from mzanalys import analysis, formation, recommend
from mzanalys.stats import parse_stats
from tests.helpers import F_352, F_41212, F_4213, F_532, make_stats_xml

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

    def test_goal_difference_and_shrinkage(self):
        # Utan ligadatabas är det väntade 0: fyrbackslagen gjorde +1, +4, +1, +1, −1 mot Täfte.
        best = self.rec.backs.best
        self.assertAlmostEqual(best.ppm, 12 / 5)
        self.assertAlmostEqual(best.resid, 6 / 5)
        self.assertAlmostEqual(best.score, 2 * 6 / (2 * 5 + recommend.PRIOR_WEIGHT))
        self.assertEqual((best.direct, self.rec.direct_matches, self.rec.similar_matches), (5, 8, 0))

    def test_reasons_avoid_and_shapes(self):
        self.assertTrue(any("4 backar" in r for r in self.rec.reasons))
        self.assertTrue(any("3 backar" in a for a in self.rec.avoid))
        self.assertEqual(len(self.rec.shape), 10)
        self.assertEqual(self.rec.opponent_formation, "4-1-2-1-2")
        self.assertEqual(len(self.rec.opponent_shape), 10)
        self.assertIn(self.rec.confidence, ("medel", "hög"))

    def test_similar_opponents_from_league(self):
        # Två ligamatcher mellan andra lag: ett rombenlag (som Täfte) förlorar mot ett fembackslag.
        league = [
            parse_stats(make_stats_xml(101, (50, "Romb"), (60, "Fembackar"), (0, 3), home_shape=F_41212,
                                       away_shape=F_532, home_setup=SHORT, away_setup=WINGS)),
            parse_stats(make_stats_xml(102, (61, "Fembackar2"), (51, "Romb2"), (2, 0), home_shape=F_532,
                                       away_shape=F_41212, home_setup=WINGS, away_setup=SHORT)),
            # Matcher utan rombformation räknas inte.
            parse_stats(make_stats_xml(103, (70, "X"), (71, "Y"), (5, 0))),
        ]
        rec = recommend.recommend(self.profile, opponent_home=True, league_matches=league)
        self.assertEqual(rec.similar_matches, 2)
        five = next(o for o in rec.backs.options if o.value == "5 backar")
        self.assertEqual((five.matches, five.direct, five.wins, five.resid), (2, 0, 2, 2.5))

    def _own(self, setup, score, n=6):
        me = (13659, "Vi")
        return analysis.build_profile([
            parse_stats(make_stats_xml(200 + i, me, (300 + i, f"M{i}"), score, home_shape=F_4213, home_setup=setup))
            for i in range(n)], 13659)

    def test_own_history_can_tip_a_close_choice(self):
        # Mot Täfte: normal spelstil −0.5/match (6 matcher), offensiv −2.0/match (2 matcher).
        # Ditt lag har vunnit stort med offensiv spelstil: +3/match i 6 matcher.
        own = self._own(("shortpass", "offensive", "normal"), (4, 1))
        rec = recommend.recommend(self.profile, opponent_home=True, own=own)
        self.assertEqual(rec.own_matches, 6)
        self.assertEqual(rec.playstyle.best.value, "offensive")
        self.assertEqual(rec.playstyle.own["offensive"].matches, 6)
        self.assertTrue(any("Valt framför normal" in r for r in rec.reasons))
        # Antal backar ändras inte: fyra backar är klart bäst mot Täfte och ditt lag spelar också fyra.
        self.assertEqual(rec.backs.best.value, "4 backar")

    def test_own_history_does_not_override_clear_pattern(self):
        # Ditt lag har gått bra med långbollar, men mot Täfte har kantspel varit klart bäst.
        own = self._own(("longball", "normal", "normal"), (2, 1), n=3)
        rec = recommend.recommend(self.profile, opponent_home=True, own=own)
        self.assertEqual(rec.tactic.best.value, "wings")

    def test_without_own_history_unchanged(self):
        rec = recommend.recommend(self.profile, opponent_home=True)
        self.assertEqual((rec.own_matches, rec.playstyle.best.value), (0, "normal"))

    def test_ratings_hand_calculated(self):
        from mzanalys import league as lg
        # A–B 2–0 och B–A 1–1. Hemmafördel = (2 + 0) / 2 = 1.
        # Rensat för hemmafördel: A +1 och +1, B −1 och −1. Styrka = summa / (2 + 3).
        ms = [parse_stats(make_stats_xml(1, (1, "A"), (2, "B"), (2, 0))),
              parse_stats(make_stats_xml(2, (2, "B"), (1, "A"), (1, 1)))]
        r = lg.ratings(ms)
        self.assertAlmostEqual(r.home_advantage, 1.0)
        self.assertAlmostEqual(r.strength[1], 0.4)
        self.assertAlmostEqual(r.strength[2], -0.4)
        self.assertAlmostEqual(r.expected_gd(1, 2, home=True), 1.8)
        self.assertAlmostEqual(r.expected_gd(2, 1, home=False), -1.8)

    def test_season_block(self):
        from mzanalys import league as lg
        mids = [1620000001, 1620000050, 1628449726, 1628449780, 1628449739]
        self.assertEqual(lg.season_block(mids), [1628449726, 1628449739, 1628449780])

    def test_editor_coordinates(self):
        self.assertEqual(formation.to_editor(371, 825), (103, 63))
        self.assertEqual(formation.to_editor(97, 307), (33, 223))


if __name__ == "__main__":
    unittest.main()
