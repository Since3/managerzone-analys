# managerzone-analys

Privat taktiskt analysverktyg för ManagerZone. Det analyserar **endast ligamatcher**.

Verktyget läser matchfilen för spelade matcher (`getMatchFiles.php?type=stats`) och tar fram en taktisk profil för ett lag:

- härledd formation (t.ex. `4-2-1-3`) ur startpositionerna,
- taktik, spelstil och aggressivitet vid avspark,
- taktikändringar och byten under matchen,
- resultat per formation, per upplägg och per motståndarens formation,
- det mest sannolika upplägget i nästa match, med stabilitet i procent.

Bakgrunden till vilka data som finns och vilka begränsningar som gäller står i [docs/teknisk-kartlaggning.md](docs/teknisk-kartlaggning.md).

> **Status:** Testat mot riktiga matchfiler från ManagerZone 2026-10-28 (en liga- och en cupmatch, utan inloggning). Analysen räknar som standard bara ligamatcher (`typ=1`). Lägg till `--typer 1,6` för att även ta med cupmatcher, eller `--typer alla` för alla typer.

> **Villkor:** ManagerZones användarvillkor begränsar programvara som kommunicerar med sajten (se rapporten, avsnitt 2.10). Använd bara ditt eget konto. Verktyget gör ett anrop i taget, med minst 3 sekunders paus (standard 5), och sparar varje match så att den bara hämtas en gång. Det anropar aldrig `/?p=match`.

## Krav

Python 3.10 eller senare. Inga andra beroenden.

## Webbappen

**Windows:** dubbelklicka på `starta-appen.bat` i mappen. **Övriga:** kör `python -m mzanalys webb`.

Appen öppnas i webbläsaren på `http://127.0.0.1:8765/` och körs bara på din egen dator. Låt det svarta fönstret vara öppet medan du använder appen; stänger du det avslutas appen.

1. Skriv ditt lag-ID och klicka **Visa kommande ligamatcher**.
2. Klicka på en match. Appen hämtar motståndarens senaste 10 ligamatcher (1–2 minuter första gången, sedan går det snabbt).
3. Du får:
   - ett **förslag** på antal backar, formation, taktik, spelstil och aggressivitet, med motivering och säkerhetsnivå,
   - en **planritning** av förslaget bredvid motståndarens väntade uppställning, och koordinater för taktikeditorn,
   - **tabeller** över hur lagen som mött dem har gått, per formation och upplägg,
   - deras väntade upplägg, troliga startelva, beteende under matchen och alla matcher.
   - **vilken kant de oftast anfaller på** (sett som i taktikeditorn, och vilken av dina kanter det motsvarar),
   - **varning för möjlig maskeringstaktik** om de byter taktik inom de första 10 minuterna i minst två matcher och minst 30 % av matcherna.

Hittar appen inga kommande matcher kan du ange motståndarens lag-ID direkt under **Analysera ett lag direkt**.

### Ligadatabas (rekommenderas)

Klicka **Bygg / uppdatera ligadatabas** i appen, eller kör `python -m mzanalys liga --mitt-lag <ditt lag-ID>`. Verktyget hämtar då alla ligamatcher i din serie den här säsongen:

1. Dina ligamatcher ger seriens lag. Säsongen avgränsas av att en series alla ligamatcher har match-ID nära varandra.
2. Varje lags ligamatcher i samma säsong hämtas. Matcher från andra serier (enligt matchfilens serienamn) sorteras bort.
3. Första gången tar det en stund (några sekunder per match). Därefter hämtas bara nya matcher. Kör gärna en uppdatering efter varje omgång.

Med ligadatabasen blir förslagen mer tillförlitliga på två sätt:
- **Större underlag:** även matcher där andra lag i serien mötte ett lag med **samma formation** som din motståndare räknas med. Matcher mot motståndaren själv väger dubbelt.
- **Hänsyn till lagens styrka:** varje lags styrka räknas fram ur seriens resultat. Måttet blir målskillnad **jämfört med det väntade**, så att en vinst för ett starkt lag väger mindre än en vinst för ett svagt.

**Hur förslaget räknas fram:** Matcherna grupperas efter vad laget som mötte motståndaren använde (antal backar, formation, taktik, spelstil, aggressivitet). Varje grupp får ett värde: medelvärdet av målskillnad och skillnad i skott på mål per match, båda jämförda med det väntade utifrån lagens styrka och hemmaplan (utan ligadatabas är det väntade 0). Skotten räknas om till mål med seriens omvandlingsgrad (mål per skott på mål). Skott är mindre beroende av tur än mål, så förslagen blir stabilare med få matcher. Små grupper dras mot noll (tre fiktiva matcher), och ett alternativ måste ha minst vikt 4 bakom sig för att föreslås: två matcher mot motståndaren, eller fyra mot lag med samma formation. Förslaget bygger på historiska resultat, inte på spelmotorn. Spelarkvalitet och motståndarnas styrka påverkar också utfallet.

**Säkerhet per val:** varje val (antal backar, formation, taktik, spelstil, aggressivitet) har en egen säkerhetsnivå. *Hög*: underlag minst 10 (match mot motståndaren = 2, mot lag med samma formation = 1) och värdet minst +0,4 per match efter krympning. *Medel*: minst 5 och +0,2. Annars *låg*.

**Ditt eget lags historik:** när ligadatabasen finns räknas även dina egna ligamatcher in. Varje alternativ får ett tillägg på halva ditt lags värde med samma val (målskillnad mot väntat, krympt mot noll); alternativ du aldrig använt räknas neutralt. Det kan avgöra mellan alternativ som ligger nära varandra mot motståndaren, men det som fungerat mot motståndaren väger tyngst. Tabellerna har en kolumn **Ditt lag**, och motiveringen säger när ditt lags resultat fällt avgörandet.

## Mobilsida som uppdateras automatiskt (GitHub)

Arbetsflödet `.github/workflows/scouting.yml` körs på GitHubs servrar, så din dator behöver inte vara igång:

- **När:** onsdag och söndag kväll efter ligaomgången, och morgonen därpå. Kan också startas för hand under **Actions → MZ Scouting → Run workflow**.
- **Vad:** bygger/uppdaterar ligadatabasen (sparade matcher återanvänds mellan körningarna) och skapar en mobilsida med rapport och förslag för **alla lag i serien**. Kommande motståndare visas överst om listan över kommande matcher går att läsa.
- **Var:** sidan publiceras med GitHub Pages. Lägg den på mobilens hemskärm för en app-ikon.

- **Uppföljning:** inför varje ligamatch sparas förslaget mot nästa motståndare. När matchen spelats läses det ut vad du faktiskt spelade och hur det gick. Sidan visar poäng per match och målskillnad mot väntat när du följde förslaget (minst 4 av 5 val) jämfört med när du inte gjorde det, även per val. Historiken sparas på grenen `historik` (`prognoser.json`).

Lokalt kan samma sida byggas med `python -m mzanalys publicera --mitt-lag <lag-ID> --ut site` och öppnas som fil (`site/index.html`).

## Scouting av nästa motståndare (kommandorad)

Det här är huvudfunktionen. Ange ID för din kommande ligamatch och ditt eget lag-ID (på Windows skriver du `py` i stället för `python`):

```bash
python -m mzanalys motstandare --match 1628449780 --mitt-lag 13659
```

Verktyget tar reda på motståndaren, hämtar deras senaste 10 ligamatcher och skriver `scouting-<lag-ID>.md` med fem delar:

1. **Väntat upplägg:** formation, taktik, spelstil och aggressivitet, totalt och uppdelat på hemma/borta.
2. **Trolig startelva:** vilka som brukar starta och på vilken position.
3. **Hur de reagerar under matchen:** ändringar när de leder, ligger lika eller ligger under.
4. **Vad har fungerat mot dem:** resultat för deras motståndare per formation och upplägg.
5. **Alla matcher** i en tabell.

Hittar verktyget inte motståndaren eller deras matcher automatiskt kan du ange dem själv:

```bash
python -m mzanalys motstandare <deras lag-ID> <match-ID 1> <match-ID 2> …
```

## Övriga kommandon

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

- `/xml/team_matchlist.php` och vilket värde den använder för ligamatcher är obekräftade. Kontrollera med `--visa-typer`.
- Det är okänt hur långt bakåt matchfilen går att generera. Hämta därför matcher löpande, så finns de i cachen.
- Formationen är en heuristik baserad på zongränser från tredjepartskällor. Två mittfältslinjer räknas som separata om djupskillnaden mellan dem är mer än 70 enheter.
