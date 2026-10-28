"""Utläsning av match-ID:n för ligamatcher ur olika källor.

- XML från /xml/team_matchlist.php (struktur från kod från 2013, obekräftad i dag),
- HTML från sajtens matchlista (ajax.php?p=matches&sub=list eller sparad sida),
- en vanlig textfil eller kommandorad med match-ID:n.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

# Tävlingslänkar i matchlistan. Ligamatcher länkar till ?p=league…; cup, privat cup och
# vänskapsserier har egna värden och tas därför bort.
_LEAGUE_LINK = re.compile(r"[?&]p=league\b")
_ROW_SPLIT = re.compile(r'(?=<dd class="(?:odd|even)[" ])')
_MID = re.compile(r'action-panel-(\d+)|[?&]mid=(\d+)')


def mids_from_text(text: str) -> list[int]:
    """Alla heltal med minst 6 siffror, i ordning och utan dubbletter."""
    seen: list[int] = []
    for m in re.findall(r"\d{6,}", text):
        mid = int(m)
        if mid not in seen:
            seen.append(mid)
    return seen


def _html_from_response(text: str) -> str:
    """HTML direkt, eller första strängen i ett JSON-svar som innehåller matchlistan."""
    if "fixtures-results-list" in text and not text.lstrip().startswith(("{", "[")):
        return text
    try:
        data = json.loads(text)
    except ValueError:
        return text

    def find(v):
        if isinstance(v, str):
            return v if "fixtures-results-list" in v else None
        if isinstance(v, dict):
            v = list(v.values())
        if isinstance(v, list):
            for x in v:
                r = find(x)
                if r:
                    return r
        return None

    return find(data) or text


def league_mids_from_html(html: str) -> list[int]:
    """Match-ID:n för ligamatcher ur matchlistans HTML (dl#fixtures-results-list).

    Svaret från ajax.php kan vara HTML direkt eller HTML inbäddad i JSON.
    En rad räknas som ligamatch om tävlingslänken pekar på ?p=league. Ungdomsligor
    (rader med klassen uxx) tas bort.
    """
    html = _html_from_response(html)
    start = html.find("fixtures-results-list")
    if start < 0:
        raise ValueError("Ingen matchlista (fixtures-results-list) hittades i svaret.")
    rows = _ROW_SPLIT.split(html[start:])[1:]
    out: list[int] = []
    for row in rows:
        head = row[: row.find(">") + 1]
        if "uxx" in head:
            continue
        if not _LEAGUE_LINK.search(row):
            continue
        m = _MID.search(row)
        if m:
            mid = int(m.group(1) or m.group(2))
            if mid not in out:
                out.append(mid)
    return out


def league_mids_from_xml(xml: str, league_types: tuple[str, ...] = ("series",)) -> list[int]:
    """Match-ID:n ur team_matchlist.php, filtrerade på Match@type.

    Värdet för ligamatcher antas vara "series" (samma ord som sajtens filter selectType).
    Det är obekräftat; kör `mzanalys lista --visa-typer` för att se vilka värden som finns.
    """
    root = ET.fromstring(xml)
    out = []
    for m in root.iter("Match"):
        if m.get("type") in league_types:
            mid = m.get("id") or m.get("mid")
            if mid and mid.isdigit():
                out.append(int(mid))
    return out


def match_types_in_xml(xml: str) -> dict[str, int]:
    root = ET.fromstring(xml)
    counts: dict[str, int] = {}
    for m in root.iter("Match"):
        t = m.get("type") or "(saknas)"
        counts[t] = counts.get(t, 0) + 1
    return counts
