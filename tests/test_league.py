import tempfile
import unittest
from pathlib import Path

from mzanalys import league
from mzanalys.stats import parse_stats
from tests.helpers import F_41212, F_4213, make_stats_xml

ME, TAFTE, A, B = 13659, 2768, 50, 51
BASE = 1628449700


def _match(mid, home, away, score, series="div3.1", **kw):
    xml = make_stats_xml(mid, (home, f"Lag{home}"), (away, f"Lag{away}"), score, **kw)
    return xml.replace('series_name="div1.1"', f'series_name="{series}"')


class FakeLeagueClient:
    """Liten liga: fyra lag, en gammal säsong och en match i en annan serie."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.calls = 0
        pairs = [(ME, TAFTE), (A, B), (ME, A), (TAFTE, B), (ME, B), (TAFTE, A)]
        self.files = {}
        for i, (h, a) in enumerate(pairs):
            kw = {"home_shape": F_41212} if h == TAFTE else {"away_shape": F_41212} if a == TAFTE else {}
            self.files[BASE + i] = _match(BASE + i, h, a, (1 + i % 3, i % 2), **kw)
        self.files[1620000001] = _match(1620000001, ME, 99, (1, 0))  # förra säsongen
        self.files[BASE + 50] = _match(BASE + 50, B, 77, (2, 2), series="world")  # annan serie

    def cache_path(self, mid):
        return self.cache_dir / f"{mid}.xml"

    def team_matchlist_xml(self, team, limit=50, played=True):
        rows = []
        for mid, xml in self.files.items():
            m = parse_stats(xml)
            if any(t.id == team for t in m.teams):
                rows.append(f'<Match id="{mid}" type="league"/>')
        return "<ManagerZone_MatchList>" + "".join(rows) + "</ManagerZone_MatchList>"

    def match_stats(self, mid):
        path = self.cache_path(mid)
        if not path.exists():
            self.calls += 1
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.files[mid], encoding="utf-8")
        return path.read_text(encoding="utf-8")


class LeagueTest(unittest.TestCase):
    def test_collect_season_and_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeLeagueClient(Path(tmp) / "matches")
            index = league.collect(client, ME)
            self.assertEqual(index.series, "div3.1")
            self.assertEqual(set(index.teams), {ME, TAFTE, A, B})
            self.assertEqual(index.mids, [BASE + i for i in range(6)])  # utan gammal säsong och annan serie

            # Sparas och läses tillbaka; ingen ny hämtning andra gången.
            path = league.index_path(client.cache_dir, ME)
            index.save(path)
            again = league.LeagueIndex.load(path)
            self.assertEqual((again.mids, again.series), (index.mids, index.series))
            calls = client.calls
            league.collect(client, ME)
            self.assertEqual(client.calls, calls)
            self.assertEqual(len(league.load_matches(client, again)), 6)


if __name__ == "__main__":
    unittest.main()
