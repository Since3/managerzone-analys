import unittest

from mzanalys import analysis, formation
from mzanalys.stats import parse_stats
from tests.helpers import F_41212, F_4213, make_stats_xml

# 4-3-3 med vänsterkantsanfall: vänsterytter och en extra anfallare till vänster (som i taktikeditorn).
F_LEFT = [(100, 250), (280, 240), (470, 240), (650, 250),
          (300, 480), (450, 480), (120, 600),
          (100, 760), (300, 780), (450, 760)]


def _profile(shapes, events=None):
    ms = []
    for i, shape in enumerate(shapes):
        ms.append(parse_stats(make_stats_xml(i + 1, (1, "Laget"), (100 + i, f"M{i}"), (1, 0),
                                             home_shape=shape, events=(events or [""] * len(shapes))[i],
                                             date=f"2026-10-{i + 1:02d} 20:00:00")))
    return analysis.build_profile(ms, 1)


class AttackSideTest(unittest.TestCase):
    def test_sides(self):
        def side(shape, keeper_at_top):
            m = parse_stats(make_stats_xml(1, (1, "H"), (2, "B"), (0, 0), home_shape=shape, away_shape=shape))
            return formation.attack_side(formation.derive(m.starters(2 if keeper_at_top else 1)))
        mirrored = [(750 - w, d) for w, d in F_LEFT]
        for top in (False, True):
            self.assertEqual(side(F_LEFT, top), "vänster")
            self.assertEqual(side(mirrored, top), "höger")
            self.assertEqual(side(F_4213, top), "centralt")   # symmetrisk
            self.assertEqual(side(F_41212, top), "centralt")  # romb, inga yttrar

    def test_profile_counts(self):
        p = _profile([F_LEFT, F_LEFT, F_4213])
        self.assertEqual(p.attack_sides(), {"vänster": 2, "centralt": 1})


class EarlyChangeTest(unittest.TestCase):
    def test_masking_warning(self):
        early = '<Tactic teamId="1" type="tactic" new_setting="wings" time="5:30"/>'
        late = '<Tactic teamId="1" type="playstyle" new_setting="offensive" time="70:00"/>'
        p = _profile([F_4213] * 4, events=[early, early, late, ""])
        e = p.early_changes()
        self.assertEqual((e["matches"], e["total"], e["masking"]), (2, 4, True))
        self.assertEqual(e["changes"], {"tactic→wings": 2})

    def test_single_early_change_is_no_warning(self):
        early = '<Tactic teamId="1" type="tactic" new_setting="wings" time="3:00"/>'
        e = _profile([F_4213] * 3, events=[early, "", ""]).early_changes()
        self.assertEqual((e["matches"], e["masking"]), (1, False))

    def test_opponent_changes_are_ignored(self):
        other = '<Tactic teamId="100" type="tactic" new_setting="wings" time="3:00"/>'
        self.assertEqual(_profile([F_4213], events=[other]).early_changes()["matches"], 0)


if __name__ == "__main__":
    unittest.main()
