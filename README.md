# managerzone-analys

Privat taktiskt analysverktyg för ManagerZone. Det analyserar **endast ligamatcher**.

Verktyget läser matchfilen för spelade matcher (`getMatchFiles.php?type=stats`) och tar fram en taktisk profil för ett lag:

- härledd formation (t.ex. `4-2-1-3`) ur startpositionerna,
- taktik, spelstil och aggressivitet vid avspark,
- taktikändringar och byten under matchen,
- resultat per formation, per upplägg och per motståndarens formation,
- det mest sannolika upplägget i nästa match, med stabilitet i procent.

Bakgrunden till vilka data som finns och vilka begränsningar som gäller står i [docs/teknisk-kartlaggning.md](docs/teknisk-kartlaggning.md).

> **Status:** Verktyget är testat mot syntetiska matchfiler som följer den dokumenterade strukturen, men **inte mot riktiga svar från ManagerZone**. Kör det första gången mot en enda match och kontrollera resultatet.

> **Villkor:** ManagerZones användarvillkor begränsar programvara som kommunicerar med sajten (se rapporten, avsnitt 2.10). Använd bara ditt eget konto. Verktyget gör ett anrop i taget, med minst 3 sekunders paus (standard 5), och sparar varje match så att den bara hämtas en gång. Det anropar aldrig `/?p=match`.

## Krav

Python 3.10 eller senare. Inga andra beroenden.

## Användning

Kör från repots rotkatalog.

```bash
# 1. Ta fram de senaste 20 ligamatcherna för ett lag (lag-ID = tid i lagets adress)
python -m mzanalys lista 847159 --ut matcher.txt
#    Vilka matchtyper finns i XML-listan? (används för att bekräfta filtret "series")
python -m mzanalys lista 847159 --visa-typer
#    Alternativ: sajtens egen lista med din inloggade session
MZ_PHPSESSID=<din cookie> python -m mzanalys lista 847159 --session --ut matcher.txt
#    Alternativ: en matchlista du sparat från webbläsaren
python -m mzanalys lista 847159 --html sparad-lista.html --ut matcher.txt

# 2. Hämta matchfilerna (sparas i data/matches/<mid>.xml)
python -m mzanalys hamta --fil matcher.txt
python -m mzanalys hamta 1625669278 1625669279

# 3. Analysera ett lag (använder alla sparade matcher där laget deltog)
python -m mzanalys analysera 847159 --ut rapport.md
python -m mzanalys analysera 847159 --fil matcher.txt --antal 10

# Visa en enskild match: båda lagens formation och upplägg
python -m mzanalys match 1625669278
```

Du kan också klistra in match-ID:n i `matcher.txt` för hand, ett per rad. Det fungerar alltid, även när ingen av listvägarna gör det.

## Struktur

| Fil | Innehåll |
|---|---|
| `mzanalys/stats.py` | Tolkning av matchfilen `<SoccerStatistics>` |
| `mzanalys/formation.py` | Formation ur startpositioner (heuristik) |
| `mzanalys/matchlist.py` | Match-ID:n för ligamatcher ur XML, HTML eller text |
| `mzanalys/fetch.py` | Hämtning med paus, `check-match`-förberedelse och cache |
| `mzanalys/analysis.py` | Lagprofil över flera matcher |
| `mzanalys/report.py` | Rapport i Markdown |
| `mzanalys/cli.py` | Kommandoraden |

## Tester

```bash
python -m unittest discover -s tests -t .
```

## Kända osäkerheter

- `/xml/team_matchlist.php` och dess värde för ligamatcher (`type="series"`) är obekräftade. Kontrollera med `--visa-typer`.
- Det är okänt hur långt bakåt matchfilen går att generera. Hämta därför matcher löpande, så finns de i cachen.
- Formationen är en heuristik baserad på zongränser från tredjepartskällor. Två mittfältslinjer räknas som separata om djupskillnaden mellan dem är mer än 70 enheter.
