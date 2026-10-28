import io
import json
import tempfile
import unittest
from pathlib import Path

from mzanalys import analysis, matchlist, report
from mzanalys.fetch import Client, FetchError
from mzanalys.stats import parse_stats
from tests.helpers import F_442, F_532, F_4213, make_stats_xml

US = (11, "Vårt lag")


def _season():
    """Fyra ligamatcher för lag 11, två hemma och två borta."""
    return [
        parse_stats(make_stats_xml(1, US, (22, "A"), (2, 0), date="2026-10-01 20:00:00")),
        parse_stats(make_stats_xml(2, (33, "B"), US, (1, 1), home_shape=F_532, away_shape=F_4213,
                                   away_setup=("wings", "offensive", "normal"), date="2026-10-05 20:00:00")),
        parse_stats(make_stats_xml(3, US, (44, "C"), (0, 2), home_shape=F_442,
                                   home_setup=("shortpass", "normal", "aggressive"), date="2026-10-08 20:00:00",
                                   goal_minutes=((), (30, 80)),
                                   events='<Tactic teamId="11" type="playstyle" new_setting="offensive" time="62:00"/>')),
        parse_stats(make_stats_xml(4, US, (22, "A"), (3, 1), date="2026-10-12 20:00:00")),
    ]


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.p = analysis.build_profile(_season(), 11)

    def test_order_and_results(self):
        self.assertEqual([m.mid for m in self.p.matches], [4, 3, 2, 1])
        self.assertEqual(self.p.record, {"V": 2, "O": 1, "F": 1})
        self.assertEqual(self.p.goals, (6, 4))
        self.assertEqual([m.home for m in self.p.matches], [True, True, False, True])

    def test_only_league_matches_by_default(self):
        cup = parse_stats(make_stats_xml(9, US, (55, "Cup"), (0, 5), match_type="6"))
        self.assertEqual(len(analysis.build_profile(_season() + [cup], 11).matches), 4)
        self.assertEqual(len(analysis.build_profile(_season() + [cup], 11, types=None).matches), 5)

    def test_most_likely(self):
        likely = self.p.most_likely()
        self.assertEqual(likely["formation"], ("4-2-1-3", 0.75, 4))
        self.assertEqual(likely["taktik"], ("wings", 0.75, 4))
        self.assertEqual(self.p.most_likely(home=False)["formation"], ("4-2-1-3", 1.0, 1))

    def test_opponents_and_changes(self):
        away_game = self.p.matches[2]
        self.assertEqual((away_game.opponent, away_game.opponent_formation), ("B", "5-3-2"))
        self.assertEqual([str(c) for c in self.p.matches[1].changes], ["62' playstyle→offensive (vid 0–1)"])
        self.assertEqual(self.p.changes_by_state(), {"under": {"playstyle→offensive": 1}})
        self.assertEqual(self.p.results_by(lambda m: m.formation)["4-4-2"], {"V": 0, "O": 0, "F": 1})

    def test_opponent_view_results(self):
        # Sett från motståndarna: 4-4-2 mot oss gav 1 vinst (match 3) och 2 förluster.
        self.assertEqual(self.p.results_by(lambda m: m.opponent_formation, True)["4-4-2"],
                         {"V": 1, "O": 0, "F": 2})

    def test_regular_starters(self):
        starters = self.p.regular_starters()
        self.assertEqual(len(starters), 11)
        roles = {s.name: s.role for s, _ in starters}
        self.assertEqual(roles["Keeper 11"], "målvakt")
        self.assertEqual(roles["P11-1"], "försvar vänster")
        self.assertEqual(roles["P11-9"], "anfall central")

    def test_report_renders(self):
        text = report.render(self.p)
        self.assertIn("formation **4-2-1-3** (75 %)", text)
        self.assertIn("| 2026-10-08 | H | C | 0–2 F | 4-4-2 |", text)

    def test_scouting_report(self):
        text = report.render_scouting(self.p)
        for heading in ("## 1. Väntat upplägg", "## 2. Trolig startelva", "## 3. Hur de reagerar",
                        "## 4. Vad har fungerat mot dem?", "Litet underlag"):
            self.assertIn(heading, text)
        self.assertIn("När de ligger under: playstyle→offensive (1)", text)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ClientTest(unittest.TestCase):
    def _client(self, responses, tmp):
        calls = []

        def opener(req, timeout):
            calls.append(req.full_url)
            return FakeResponse(responses.pop(0).encode())

        c = Client(cache_dir=tmp, delay=0, session_id="", opener=opener, sleep=lambda s: None, log=lambda *a: None)
        return c, calls

    def test_check_match_then_cache(self):
        xml = make_stats_xml(77, US, (22, "A"), (1, 0))
        with tempfile.TemporaryDirectory() as tmp:
            c, calls = self._client(["", json.dumps({"response": "queued"}), json.dumps({"response": "ok"}), xml], tmp)
            self.assertEqual(parse_stats(c.match_stats(77)).mid, 77)
            self.assertEqual(len(calls), 4)
            self.assertIn("check-match", calls[1])
            # Andra gången: från cachen, inga nya anrop.
            c.match_stats(77)
            self.assertEqual(len(calls), 4)
            self.assertTrue((Path(tmp) / "77.xml").exists())

    def test_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, _ = self._client(["", json.dumps({"response": "blocked"})], tmp)
            with self.assertRaises(FetchError):
                c.match_stats(5)

    def test_walkover_stops_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, calls = self._client(["", json.dumps({"response": "walkover"})], tmp)
            with self.assertRaisesRegex(FetchError, "walkover"):
                c.match_stats(1637344955)
            self.assertEqual(len(calls), 2)

    def test_session_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, calls = self._client([], tmp)
            with self.assertRaises(FetchError):
                c.league_matchlist_html(11)
            self.assertEqual(calls, [])


class MatchlistTest(unittest.TestCase):
    HTML = """<dl id="fixtures-results-list" class="fixtures">
<dd class="group">24-10-2026</dd>
<dd class="odd"><div class="match-reference-text-wrapper"><span>League match</span> <a href="/?p=league&type=senior&sid=1">div1.1</a></div>
<a class="score-shown" href="/?p=match&sub=result&mid=111">2 - 1</a><dl id="action-panel-111"></dl></dd>
<dd class="even"><div class="match-reference-text-wrapper"><span>Official cup</span> <a href="/?p=cup&sub=schedule&cid=5">Cup</a></div>
<dl id="action-panel-222"></dl></dd>
<dd class="odd uxx"><div class="match-reference-text-wrapper"><span>League match</span> <a href="/?p=league&type=u18&sid=2">U18</a></div>
<dl id="action-panel-333"></dl></dd>
<dd class="even"><div class="match-reference-text-wrapper"><span>Friendly</span> <a href="/?p=friendlyseries&fsid=9">FS</a></div>
<dl id="action-panel-444"></dl></dd>
</dl>"""

    def test_league_only(self):
        self.assertEqual(matchlist.league_mids_from_html(self.HTML), [111])

    def test_json_wrapped(self):
        self.assertEqual(matchlist.league_mids_from_html(json.dumps({"list": self.HTML})), [111])

    def test_xml_list(self):
        xml = ('<ManagerZone_MatchList><Match id="5" type="series"><Team/><Team/></Match>'
               '<Match id="6" type="cup"><Team/><Team/></Match></ManagerZone_MatchList>')
        self.assertEqual(matchlist.league_mids_from_xml(xml), [5])
        self.assertEqual(matchlist.match_types_in_xml(xml), {"series": 1, "cup": 1})

    def test_teams_from_match_info(self):
        xml = ('<ManagerZone_MatchInfo><Match id="1628449780">'
               '<Team field="away" id="13659" name="Vi"/><Team field="home" id="555" name="De"/>'
               '</Match></ManagerZone_MatchInfo>')
        self.assertEqual(matchlist.teams_from_match_info(xml), [(555, "De"), (13659, "Vi")])
        with self.assertRaises(ValueError):
            matchlist.teams_from_match_info("<ManagerZone_Error message='x'/>")

    def test_mids_from_text(self):
        self.assertEqual(matchlist.mids_from_text("1625669278, 1625669278\nmid=1637650666"),
                         [1625669278, 1637650666])


if __name__ == "__main__":
    unittest.main()
