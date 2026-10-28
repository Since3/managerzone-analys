"""Hämtning av matchfiler och matchlistor från ManagerZone, med lokal cache.

Riktlinjer (se docs/teknisk-kartlaggning.md, avsnitt 2.10):
- ett anrop i taget, minst `delay` sekunder mellan anropen,
- varje spelad match hämtas bara en gång och sparas sedan i cachen,
- ingen inloggning; en matchlista som kräver session använder bara din egen
  PHPSESSID från miljövariabeln MZ_PHPSESSID och sparas aldrig,
- inga anrop mot /?p=match (spärrad i robots.txt).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__
from .stats import StatsXmlError, extract_xml

BASE_URL = "https://www.managerzone.com"
USER_AGENT = f"mzanalys/{__version__} (privat analysverktyg, lag anropstakt)"


class FetchError(RuntimeError):
    pass


class Client:
    def __init__(
        self,
        cache_dir: str | Path = "data/matches",
        delay: float = 5.0,
        base_url: str = BASE_URL,
        session_id: str | None = None,
        opener=None,
        sleep=time.sleep,
        log=print,
    ):
        self.cache_dir = Path(cache_dir)
        self.delay = delay
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id if session_id is not None else os.environ.get("MZ_PHPSESSID")
        self._open = opener or urllib.request.urlopen
        self._sleep = sleep
        self._log = log
        self._last_request = 0.0

    # --- HTTP ---------------------------------------------------------------

    def _request(self, path: str, data: dict | None = None, with_session: bool = False) -> str:
        wait = self._last_request + self.delay - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        headers = {"User-Agent": USER_AGENT}
        if with_session:
            if not self.session_id:
                raise FetchError("Anropet kräver inloggning: sätt MZ_PHPSESSID till din egen session.")
            headers["Cookie"] = f"PHPSESSID={self.session_id}"
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(self.base_url + path, data=body, headers=headers)
        try:
            with self._open(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise FetchError(f"{path}: {e}") from e
        finally:
            self._last_request = time.monotonic()

    # --- Matchfil (stats-XML) ------------------------------------------------

    def cache_path(self, mid: int) -> Path:
        return self.cache_dir / f"{mid}.xml"

    def match_stats(self, mid: int, max_checks: int = 5) -> str:
        """Matchfilen för en spelad match. Cachad efter första lyckade hämtning."""
        path = self.cache_path(mid)
        if path.exists():
            return path.read_text(encoding="utf-8")

        stats_path = f"/matchviewer/getMatchFiles.php?type=stats&mid={mid}&sport=soccer"
        check_path = f"/ajax.php?p=matchViewer&sub=check-match&type=2d&mid={mid}&sport=soccer"

        text = self._request(stats_path)
        if not _is_stats(text):
            # Filen genereras vid behov: be 2D-visaren förbereda matchen och vänta på "ok".
            for attempt in range(1, max_checks + 1):
                status = self._check_match(check_path)
                if status == "ok":
                    break
                if status == "blocked":
                    raise FetchError(f"Match {mid}: åtkomst nekad (kräver inloggning eller är inte offentlig).")
                self._log(f"  match {mid}: {status}, försök {attempt}/{max_checks}")
            text = self._request(stats_path)
            if not _is_stats(text):
                raise FetchError(f"Match {mid}: matchfilen är fortfarande tom. Försök igen senare.")

        xml = extract_xml(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml, encoding="utf-8")
        return xml

    def _check_match(self, path: str) -> str:
        raw = self._request(path)
        try:
            return str(json.loads(raw).get("response", "okänt"))
        except (ValueError, AttributeError):
            return "okänt"

    # --- Matchlistor ---------------------------------------------------------

    def team_matchlist_xml(self, team_id: int, limit: int = 50) -> str:
        """Gamla XML-gränssnittet. Obekräftat om det fortfarande fungerar."""
        return self._request(
            f"/xml/team_matchlist.php?sport_id=1&team_id={team_id}&match_status=1&limit={limit}"
        )

    def league_matchlist_html(self, team_id: int) -> str:
        """Lagets spelade ligamatcher via sajtens egen lista. Kräver din egen session."""
        return self._request(
            "/ajax.php?p=matches&sub=list&sport=soccer",
            data={
                "type": "played",
                "hidescore": "false",
                "tid1": str(team_id),
                "offset": "",
                "selectType": "series",
                "limit": "default",
            },
            with_session=True,
        )


def _is_stats(text: str) -> bool:
    try:
        extract_xml(text)
        return True
    except StatsXmlError:
        return False
