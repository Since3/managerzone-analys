"""Kommandoradsgränssnitt: python -m mzanalys <kommando> …"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import analysis, formation, matchlist, report
from .fetch import Client, FetchError
from .stats import Match, StatsXmlError, parse_stats


def _read_mids(args) -> list[int]:
    mids: list[int] = []
    for value in args.matcher or []:
        mids += matchlist.mids_from_text(value)
    if getattr(args, "fil", None):
        mids += matchlist.mids_from_text(Path(args.fil).read_text(encoding="utf-8"))
    return list(dict.fromkeys(mids))


def _client(args) -> Client:
    return Client(cache_dir=args.cache, delay=args.paus)


def _load_cached(cache: Path) -> list[Match]:
    out = []
    for path in sorted(cache.glob("*.xml")):
        try:
            out.append(parse_stats(path.read_text(encoding="utf-8")))
        except StatsXmlError as e:
            print(f"Hoppar över {path.name}: {e}", file=sys.stderr)
    return out


def cmd_hamta(args) -> int:
    mids = _read_mids(args)
    if not mids:
        print("Ange match-ID:n, t.ex. `hamta 1625669278` eller `hamta --fil matcher.txt`.", file=sys.stderr)
        return 2
    client = _client(args)
    ok = 0
    for i, mid in enumerate(mids, 1):
        cached = client.cache_path(mid).exists()
        try:
            client.match_stats(mid)
            ok += 1
            print(f"[{i}/{len(mids)}] {mid}: {'fanns i cachen' if cached else 'hämtad'}")
        except (FetchError, StatsXmlError) as e:
            print(f"[{i}/{len(mids)}] {mid}: {e}", file=sys.stderr)
    print(f"{ok} av {len(mids)} matcher finns nu i {args.cache}.")
    return 0 if ok == len(mids) else 1


def cmd_lista(args) -> int:
    if args.html:
        mids = matchlist.league_mids_from_html(Path(args.html).read_text(encoding="utf-8"))
    else:
        client = _client(args)
        try:
            if args.session:
                mids = matchlist.league_mids_from_html(client.league_matchlist_html(args.lag))
            else:
                xml = client.team_matchlist_xml(args.lag, limit=200)
                if args.visa_typer:
                    for t, c in matchlist.match_types_in_xml(xml).items():
                        print(f"{t}: {c}")
                    return 0
                mids = matchlist.league_mids_from_xml(xml)
        except (FetchError, ValueError) as e:
            print(f"Kunde inte hämta matchlistan: {e}", file=sys.stderr)
            return 1
    mids = mids[: args.antal]
    if args.ut:
        Path(args.ut).write_text("\n".join(map(str, mids)) + "\n", encoding="utf-8")
    print("\n".join(map(str, mids)))
    return 0


def cmd_analysera(args) -> int:
    cache = Path(args.cache)
    mids = _read_mids(args)
    if mids:
        client = _client(args)
        matches = []
        for mid in mids:
            try:
                matches.append(parse_stats(client.match_stats(mid)))
            except (FetchError, StatsXmlError) as e:
                print(f"{mid}: {e}", file=sys.stderr)
    else:
        matches = _load_cached(cache)
    types = None if args.typer == "alla" else tuple(t.strip() for t in args.typer.split(","))
    profile = analysis.build_profile(matches, args.lag, types)
    profile.matches = profile.matches[: args.antal]
    text = report.render(profile)
    if args.ut:
        Path(args.ut).write_text(text, encoding="utf-8")
        print(f"Rapport sparad i {args.ut} ({len(profile.matches)} matcher).")
    else:
        print(text)
    return 0 if profile.matches else 1


def _opponent_mids(args, client: Client) -> list[int]:
    """Motståndarens ligamatcher: angivna ID:n, sajtens lista (session) eller XML-listan."""
    mids = _read_mids(args)
    if mids:
        return mids
    if args.session:
        return matchlist.league_mids_from_html(client.league_matchlist_html(args.lag))
    xml = client.team_matchlist_xml(args.lag, limit=200)
    return matchlist.league_mids_from_xml(xml)


def cmd_motstandare(args) -> int:
    client = _client(args)
    if args.match:
        if not args.mitt_lag:
            print("Ange ditt eget lag-ID med --mitt-lag, t.ex. --mitt-lag 13659.", file=sys.stderr)
            return 2
        try:
            teams = matchlist.teams_from_match_info(client.match_info(args.match))
        except Exception as e:
            print(f"Kunde inte läsa matchen {args.match}: {e}\n"
                  "Ange motståndarens lag-ID i stället (talet efter tid= i länken till deras lag).",
                  file=sys.stderr)
            return 1
        others = [(tid, name) for tid, name in teams if tid != args.mitt_lag]
        if len(teams) != 2 or len(others) != 1:
            print(f"Hittade inte ditt lag ({args.mitt_lag}) bland lagen i matchen: {teams}", file=sys.stderr)
            return 1
        args.lag, name = others[0]
        print(f"Nästa motståndare: {name} (lag-ID {args.lag})")
    if not args.lag:
        print("Ange motståndarens lag-ID, eller --match <match-ID> --mitt-lag <ditt lag-ID>.", file=sys.stderr)
        return 2
    try:
        mids = _opponent_mids(args, client)
    except Exception as e:  # matchlistan är obekräftad; ge en tydlig väg vidare
        print(f"Kunde inte hämta lagets matchlista automatiskt: {e}", file=sys.stderr)
        mids = []
    if not mids:
        print(
            "Inga ligamatcher hittades automatiskt. Ange match-ID:n själv, t.ex.\n"
            f"  py -m mzanalys motstandare {args.lag} <id1> <id2> <id3>\n"
            "Match-ID:n hittar du i lagets lista över spelade matcher (talet efter mid= i adressen).",
            file=sys.stderr,
        )
        return 1
    mids = mids[: args.antal]
    print(f"Hämtar {len(mids)} matcher (sparade matcher hämtas inte igen)…")
    matches = []
    for i, mid in enumerate(mids, 1):
        try:
            matches.append(parse_stats(client.match_stats(mid)))
            print(f"[{i}/{len(mids)}] {mid}: klar")
        except (FetchError, StatsXmlError) as e:
            print(f"[{i}/{len(mids)}] {e}", file=sys.stderr)
    profile = analysis.build_profile(matches, args.lag)
    profile.matches = profile.matches[: args.antal]
    text = report.render_scouting(profile)
    out = args.ut or f"scouting-{args.lag}.md"
    Path(out).write_text(text, encoding="utf-8")
    print(f"Scoutingrapport för {profile.name}: {out} ({len(profile.matches)} ligamatcher).")
    skipped = len(matches) - len(profile.matches)
    if skipped > 0:
        print(f"{skipped} matcher var inte ligamatcher för laget och togs inte med.")
    return 0 if profile.matches else 1


def cmd_liga(args) -> int:
    from . import league

    client = _client(args)

    def progress(text, done, total):
        if total:
            print(f"  {text}: {done}/{total}".ljust(70), end="\r", flush=True)

    try:
        index = league.collect(client, args.mitt_lag, progress)
    except (FetchError, ValueError) as e:
        print(f"\nKunde inte bygga ligadatabasen: {e}", file=sys.stderr)
        return 1
    index.save(league.index_path(args.cache, args.mitt_lag))
    print(f"\nLigadatabas: {len(index.mids)} matcher, {len(index.teams)} lag"
          + (f", serie {index.series}" if index.series else "") + ".")
    if index.failed:
        print(f"{len(index.failed)} hoppades över (t.ex. walkover).")
    ratings = league.ratings(league.load_matches(client, index))
    for i, (tid, s) in enumerate(sorted(ratings.strength.items(), key=lambda kv: -kv[1]), 1):
        print(f"  {i:2}. {index.teams.get(tid, tid):30} {s:+.2f}")
    return 0


def cmd_webb(args) -> int:
    from . import web

    web.serve(_client(args), port=args.port, antal=args.antal, open_browser=not args.ingen_webblasare,
              lan=args.mobil)
    return 0


def cmd_match(args) -> int:
    source = Path(args.match)
    if source.exists():
        text = source.read_text(encoding="utf-8")
    else:
        try:
            text = _client(args).match_stats(int(args.match))
        except (FetchError, StatsXmlError) as e:
            print(e, file=sys.stderr)
            return 1
    m = parse_stats(text)
    print(f"Match {m.mid}  {m.date or ''}  typ={m.type or '?'}")
    for t in m.teams:
        f = formation.derive(m.starters(t.id))
        print(
            f"  {'Hemma' if t.home else 'Borta'}: {t.name} ({t.id})  mål {t.goals}  "
            f"formation {f.lines if f else '?'} [{f.zones if f else '?'}]  "
            f"{t.tactic}/{t.playstyle}/{t.aggression}"
        )
        for c in m.tactic_changes:
            if c.team_id == t.id:
                print(f"     {c.minute}' {c.kind} → {c.new_setting}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mzanalys", description="Taktisk analys av ManagerZone-ligamatcher.")
    p.add_argument("--cache", default="data/matches", help="katalog för sparade matchfiler")
    p.add_argument("--paus", type=float, default=5.0, help="sekunder mellan anrop (minst 3)")
    sub = p.add_subparsers(dest="kommando", required=True)

    h = sub.add_parser("hamta", help="hämta och spara matchfiler")
    h.add_argument("matcher", nargs="*", help="match-ID:n")
    h.add_argument("--fil", help="textfil med match-ID:n")
    h.set_defaults(func=cmd_hamta)

    li = sub.add_parser("lista", help="ta fram ligamatchernas ID:n för ett lag")
    li.add_argument("lag", type=int, help="lag-ID")
    li.add_argument("--antal", type=int, default=20)
    li.add_argument("--html", help="sparad matchlista (HTML) i stället för att hämta")
    li.add_argument("--session", action="store_true", help="använd sajtens lista med din session (MZ_PHPSESSID)")
    li.add_argument("--visa-typer", action="store_true", help="visa vilka matchtyper XML-listan innehåller")
    li.add_argument("--ut", help="spara ID:n i en fil")
    li.set_defaults(func=cmd_lista)

    a = sub.add_parser("analysera", help="taktisk profil för ett lag")
    a.add_argument("lag", type=int, help="lag-ID")
    a.add_argument("matcher", nargs="*", help="match-ID:n (annars används alla i cachen)")
    a.add_argument("--fil", help="textfil med match-ID:n")
    a.add_argument("--antal", type=int, default=20)
    a.add_argument("--typer", default=analysis.LEAGUE,
                   help="matchtyper att ta med: 1 = liga (standard), 6 = cup, t.ex. 1,6 eller alla")
    a.add_argument("--ut", help="spara rapporten som Markdown")
    a.set_defaults(func=cmd_analysera)

    o = sub.add_parser("motstandare", help="scoutingrapport för nästa motståndare")
    o.add_argument("lag", type=int, nargs="?", help="motståndarens lag-ID")
    o.add_argument("matcher", nargs="*", help="deras match-ID:n (annars försöker verktyget hitta dem själv)")
    o.add_argument("--fil", help="textfil med match-ID:n")
    o.add_argument("--match", type=int, help="ID för din kommande match; motståndaren tas fram automatiskt")
    o.add_argument("--mitt-lag", type=int, help="ditt lag-ID (krävs med --match)")
    o.add_argument("--antal", type=int, default=10, help="antal senaste ligamatcher (standard 10)")
    o.add_argument("--session", action="store_true", help="använd sajtens lista med din session (MZ_PHPSESSID)")
    o.add_argument("--ut", help="filnamn för rapporten (standard scouting-<lag-ID>.md)")
    o.set_defaults(func=cmd_motstandare)

    lg = sub.add_parser("liga", help="bygg eller uppdatera ligadatabasen för din serie")
    lg.add_argument("--mitt-lag", type=int, required=True, help="ditt lag-ID")
    lg.set_defaults(func=cmd_liga)

    w = sub.add_parser("webb", help="starta webbappen i din webbläsare")
    w.add_argument("--port", type=int, default=8765)
    w.add_argument("--antal", type=int, default=10, help="antal senaste ligamatcher per motståndare")
    w.add_argument("--ingen-webblasare", action="store_true", help="öppna inte webbläsaren automatiskt")
    w.add_argument("--mobil", action="store_true", help="nåbar från mobilen i samma nätverk (wifi)")
    w.set_defaults(func=cmd_webb)

    m = sub.add_parser("match", help="visa en enskild match")
    m.add_argument("match", help="match-ID eller sökväg till en sparad matchfil")
    m.set_defaults(func=cmd_match)

    args = p.parse_args(argv)
    args.paus = max(args.paus, 3.0)
    return args.func(args)
