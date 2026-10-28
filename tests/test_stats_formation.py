import re
import unittest

from mzanalys import formation
from mzanalys.stats import StatsXmlError, parse_stats
from mzanalys.stats import Player
from tests.helpers import F_442, F_4213, F_532, make_stats_xml

EVENTS = (
    '<Substitution time="61:02" clock="60:11" playerId="1150" substitutedId="1105" teamId="11" reason="preset" minute="55"/>'
    '<Tactic teamId="11" type="playstyle" new_setting="defensive" time="70:30"/>'
)


class ParseStatsTest(unittest.TestCase):
    def setUp(self):
        self.xml = make_stats_xml(1001, (11, "Hemmalaget"), (22, "Bortalaget"), (2, 1), events=EVENTS)
        self.m = parse_stats(self.xml)

    def test_teams_and_settings(self):
        home, away = self.m.teams
        self.assertEqual((home.id, home.home, home.tactic, home.playstyle, home.aggression),
                         (11, True, "wings", "offensive", "normal"))
        self.assertEqual((away.id, away.home, away.goals), (22, False, 1))
        self.assertEqual(home.manager, "mgr11")
        self.assertEqual(self.m.type, "series")

    def test_starters_and_bench(self):
        self.assertEqual(len(self.m.starters(11)), 11)
        self.assertEqual(len([p for p in self.m.players if p.team_id == 11]), 12)

    def test_events(self):
        (sub,) = self.m.substitutions
        self.assertEqual((sub.player_in, sub.player_out, sub.minute, sub.rule_minute, sub.reason),
                         (1150, 1105, 60, 55, "preset"))
        (ch,) = self.m.tactic_changes
        self.assertEqual((ch.team_id, ch.kind, ch.new_setting, ch.minute), (11, "playstyle", "defensive", 70))

    def test_embedded_in_html(self):
        m = parse_stats("<html><body><pre>" + self.xml.split("?>", 1)[1] + "</pre></body></html>")
        self.assertEqual(m.mid, 1001)

    def test_empty_file(self):
        with self.assertRaises(StatsXmlError):
            parse_stats("")
        with self.assertRaises(StatsXmlError):
            parse_stats("<html><body></body></html>")

    def test_goals_from_players_when_statistics_missing(self):
        xml = self.xml.replace('goals="2" possession', 'possession')
        xml = re.sub(r'(<Player id="1109"[^>]*?)/>',
                     r'\1><Goal time="10:00" team="11"/><Goal time="80:00" team="11"/></Player>', xml)
        self.assertEqual(parse_stats(xml).team(11).goals, 2)


class FormationTest(unittest.TestCase):
    def _derive(self, shape, keeper_at_top):
        xml = make_stats_xml(1, (11, "H"), (22, "B"), (0, 0), home_shape=shape, away_shape=shape)
        m = parse_stats(xml)
        team = 22 if keeper_at_top else 11
        return formation.derive(m.starters(team))

    def test_4213_both_orientations(self):
        for top in (False, True):
            f = self._derive(F_4213, top)
            self.assertEqual((f.lines, f.zones), ("4-2-1-3", "4-3-3"))

    def test_442_and_532(self):
        self.assertEqual(self._derive(F_442, False).lines, "4-4-2")
        self.assertEqual(self._derive(F_532, True).lines, "5-3-2")

    def test_known_conversion_points(self):
        # Tredjepartens kontrollpunkter: origin 371,175 = anfall, 97,693 = försvar (målvakt på y=1000).
        gk = Player(1, 1, "gk", 1, True, None, (375, 1000))
        fw = Player(2, 1, "fw", 9, False, None, (371, 175))
        df = Player(3, 1, "df", 3, False, None, (97, 693))
        (fw_pos, df_pos) = formation.normalize([gk, fw, df])
        self.assertGreaterEqual(fw_pos[1], formation.ATTACK_MIN_DEPTH)
        self.assertLessEqual(df_pos[1], formation.DEFENCE_MAX_DEPTH)

    def test_no_unique_keeper(self):
        self.assertIsNone(formation.derive([Player(1, 1, "x", 1, False, None, (1, 1))]))


if __name__ == "__main__":
    unittest.main()
