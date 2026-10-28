"""Ligadatabas: alla ligamatcher i din serie den här säsongen, plus lagstyrka.

Insamling (bara verifierade anrop, ett i taget med paus och cache):
1. Din matchlista (team_matchlist.php) ger dina ligamatchers ID:n. Alla ligamatcher i en
   serie och säsong har ID:n nära varandra (schemat skapas samtidigt), så säsongen avgränsas
   som det sammanhängande blocket kring ditt senaste match-ID.
2. Dina spelade matcher i blocket hämtas; motståndarna i dem är seriens lag.
3. Varje lags matchlista ger deras ligamatcher i samma block. Alla hämtas och sparas.

Lagstyrka: målskillnad per match, krympt mot 0, plus ligans hemmafördel. Ett lags
resultat i en match jämförs med det väntade utifrån styrkorna (residual).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import matchlist
from .fetch import Client, FetchError
from .stats import Match, StatsXmlError, parse_stats

SEASON_GAP = 10_000  # största ID-avstånd mellan två ligamatcher i samma säsong
STRENGTH_PRIOR = 3.0  # fiktiva 0-matcher vid beräkning av lagstyrka


def season_block(mids: list[int], gap: int = SEASON_GAP) -> list[int]:
    """Det sammanhängande blocket av match-ID:n som innehåller det högsta ID:t."""
    if not mids:
        return []
    ordered = sorted(set(mids), reverse=True)
    block = [ordered[0]]
    for mid in ordered[1:]:
        if block[-1] - mid > gap:
            break
        block.append(mid)
    return sorted(block)


@dataclass
class LeagueIndex:
    my_team: int
    series: str | None = None
    teams: dict[int, str] = field(default_factory=dict)
    mids: list[int] = field(default_factory=list)
    block: tuple[int, int] = (0, 0)
    failed: dict[int, str] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "my_team": self.my_team, "series": self.series,
            "teams": {str(k): v for k, v in self.teams.items()},
            "mids": self.mids, "block": list(self.block),
            "failed": {str(k): v for k, v in self.failed.items()},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LeagueIndex | None":
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            my_team=d["my_team"], series=d.get("series"),
            teams={int(k): v for k, v in d.get("teams", {}).items()},
            mids=list(d.get("mids", [])), block=tuple(d.get("block", (0, 0))),
            failed={int(k): v for k, v in d.get("failed", {}).items()},
        )


def index_path(cache_dir: str | Path, my_team: int) -> Path:
    return Path(cache_dir).parent / f"liga-{my_team}.json"


def collect(client: Client, my_team: int, progress=lambda text, done, total: None) -> LeagueIndex:
    """Bygg eller uppdatera ligadatabasen för my_team. Redan sparade matcher hämtas inte igen."""
    progress("hämtar din matchlista", 0, 0)
    my_mids = matchlist.league_mids_from_xml(client.team_matchlist_xml(my_team, limit=200))
    block = season_block(my_mids)
    if not block:
        raise FetchError("Inga ligamatcher hittades för ditt lag.")
    lo, hi = block[0] - SEASON_GAP, block[-1] + SEASON_GAP
    index = LeagueIndex(my_team=my_team, block=(block[0], block[-1]))

    def fetch(mid: int) -> Match | None:
        try:
            return parse_stats(client.match_stats(mid))
        except (FetchError, StatsXmlError) as e:
            index.failed[mid] = str(e)
            return None

    # Dina matcher ger seriens lag och serienamn.
    series_count: dict[str, int] = {}
    for i, mid in enumerate(block, 1):
        progress("hämtar dina ligamatcher", i, len(block))
        m = fetch(mid)
        if not m or not any(t.id == my_team for t in m.teams):
            continue
        index.mids.append(mid)
        for t in m.teams:
            index.teams[t.id] = t.name
            if t.id == my_team and t.series:
                series_count[t.series] = series_count.get(t.series, 0) + 1
    if series_count:
        index.series = max(series_count, key=series_count.get)

    # Övriga lags ligamatcher i samma säsongsblock.
    others = [tid for tid in index.teams if tid != my_team]
    wanted: list[int] = []
    for i, tid in enumerate(others, 1):
        progress(f"hämtar matchlista för {index.teams[tid]}", i, len(others))
        try:
            mids = matchlist.league_mids_from_xml(client.team_matchlist_xml(tid, limit=200))
        except (FetchError, ValueError) as e:
            index.failed[tid] = f"matchlista: {e}"
            continue
        wanted += [mid for mid in mids if lo <= mid <= hi and mid not in index.mids and mid not in wanted]

    for i, mid in enumerate(wanted, 1):
        progress("hämtar ligans matcher", i, len(wanted))
        m = fetch(mid)
        if m and in_series(m, index.series):
            index.mids.append(mid)
    index.mids.sort()
    return index


def in_series(m: Match, series: str | None) -> bool:
    """Sant om matchen är en ligamatch i serien (eller om serien är okänd)."""
    if m.type != "1":
        return False
    names = {t.series for t in m.teams if t.series}
    return series is None or not names or series in names


def load_matches(client: Client, index: LeagueIndex) -> list[Match]:
    """Ligadatabasens matcher ur cachen (inga nya anrop för sparade matcher)."""
    out = []
    for mid in index.mids:
        path = client.cache_path(mid)
        if path.exists():
            try:
                out.append(parse_stats(path.read_text(encoding="utf-8")))
            except StatsXmlError:
                pass
    return out


@dataclass
class Ratings:
    strength: dict[int, float]  # väntad målskillnad per match mot ett genomsnittslag
    matches: dict[int, int]
    home_advantage: float  # väntad målskillnad för hemmalaget mellan två lika lag

    def expected_gd(self, team: int, opponent: int, home: bool) -> float:
        h = self.home_advantage
        return self.strength.get(team, 0.0) - self.strength.get(opponent, 0.0) + (h if home else -h)


def ratings(matches: list[Match]) -> Ratings:
    played = [m for m in matches if all(t.goals is not None for t in m.teams)]
    home_gd = [m.teams[0].goals - m.teams[1].goals for m in played]
    h = sum(home_gd) / len(home_gd) if home_gd else 0.0
    gd: dict[int, float] = {}
    n: dict[int, int] = {}
    for m in played:
        home, away = m.teams
        diff = home.goals - away.goals - h  # rensa bort hemmafördelen
        for team, sign in ((home.id, 1), (away.id, -1)):
            gd[team] = gd.get(team, 0.0) + sign * diff
            n[team] = n.get(team, 0) + 1
    # Modell: målskillnad när A möter B på neutral plan = styrka A − styrka B. Mot ett
    # genomsnittligt schema blir styrkan lagets hemmajusterade målskillnad per match.
    strength = {t: gd[t] / (n[t] + STRENGTH_PRIOR) for t in gd}
    return Ratings(strength=strength, matches=n, home_advantage=h)
