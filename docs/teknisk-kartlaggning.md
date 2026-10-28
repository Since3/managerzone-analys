# Teknisk kartläggning: datakällor för ett taktiskt analysverktyg för ManagerZone

Datum: 2026-10-27. Analysverktyget är ännu inte byggt. Det här dokumentet beskriver bara vilka data som finns och hur de kan hämtas.

---

## Uppdatering 2026-10-28: första eget test (nivå A)

Testet kördes av användaren från en vanlig dator med verktyget `mzanalys`, utan inloggning, mot ligamatch 1628449768 (Gårdagens talanger – Sunderland FC):

- `getMatchFiles.php?type=stats` var först tom. `check-match` svarade `queued` två gånger och sedan `ok`, varefter filen kunde hämtas. **Verifierat: matchfilen för en ligamatch går att hämta utan inloggning efter förberedelse via `check-match`.**
- Ur filen lästes datum (2026-10-25 18:00), lag-ID och lagnamn, hemma/borta, resultat 3–0 (**bekräftat av användaren**) samt `tactic`, `playstyle` och `aggression` för **båda** lagen. **Verifierat: motståndarens taktiska inställningar finns i matchfilen.**
- Startpositionerna gav formationerna 4-3-1-2 och 5-3-1-1. De är ännu inte bekräftade.
- `check-match` kan även svara `walkover` (cupmatch 1637344955, vunnen på walkover). Då finns ingen matchfil.
- **Nytt:** `SoccerStatistics@type` är numeriskt: **`1` = ligamatch** (1628449768) och **`6` = cupmatch** (1637077861). Vänskapsmatcher och andra typer är ännu inte kartlagda.
- `/xml/match_info.php` svarar med **fel** för en match som ännu inte spelats (1628449780). Den kan alltså inte användas för att hitta nästa motståndare.
- **`/xml/team_matchlist.php` fungerar fortfarande utan inloggning** (lag 2768). Matchtyperna i listan är ord: `league` (8), `friendly` (22) och `private_cup_group` (18) av 48 matcher. Ligamatcher är alltså `league` i listan men `1` i matchfilen.
- Taktikändringar under matchen är verifierade: i cupmatch 1637077861 visade filen att hemmalaget i 66:e minuten bytte till `playstyle=defensive` och `tactic=shortpass`.

---

## 0. Sammanfattning

- **Officiellt API:** Det finns inget dokumenterat, öppet API. Det äldre utvecklarprogrammet ("MZ Tools", certifierade appar) är enligt ManagerZone-personal sedan 2015 stängt för nya appar. Kvar finns ett äldre, odokumenterat **XML-gränssnitt** under `/xml/` (länkat som "XML" i sidfoten), samt de interna anrop som webbplatsen själv använder (`/ajax.php`, `/matchviewer/`).
- **Den viktigaste källan för taktisk analys** är matchfilen `/matchviewer/getMatchFiles.php?type=stats`. Enligt tredjepartskod och tredjepartstester innehåller den för **båda lagen** taktik (`tactic`), spelstil (`playstyle`), aggressivitet (`aggression`), startelvans startpositioner (formationen kan räknas fram), byten, taktikändringar under matchen, mål, kort och statistik. För ligamatcher ska filen enligt uppgift gå att hämta **utan inloggning**.
- **Matchlistor** (de senaste N matcherna med matchtyp) hämtas via `POST /ajax.php?p=matches&sub=list`, vilket **kräver inloggning**. Ett äldre XML-alternativ utan inloggning (`/xml/team_matchlist.php`) finns i kod från 2013, men det är inte bekräftat att det fortfarande fungerar.
- **Spelardata:** namn, ålder och värde är synliga för alla lag. Lön och färdigheter syns i princip bara för det egna laget, eller för andra lags spelare vars färdigheter är offentliga.
- **Juridik/villkor:** ManagerZones användarvillkor förbjuder enligt ett ordagrant citat hos en tredje part att skapa "any software interfacing with the Software". `robots.txt` spärrar `/?p=match` och blockerar AI-crawlers helt. Det här är den största risken och den behöver klaras ut med ManagerZone innan något automatiseras.
- **Bedömning:** Tekniskt genomförbart (se avsnitt 8), med reservationer för villkoren och för att inget kunde verifieras med egna tester i den här sessionen.

---

## 1. Metod och viktig begränsning

### 1.1 Egna tester: inga kunde genomföras

Nätverkspolicyn i molnmiljön där undersökningen kördes blockerade följande värdar (proxyn svarade `403 CONNECT tunnel failed`, eller DNS-uppslag misslyckades):

| Värd | Resultat |
|---|---|
| `www.managerzone.com` (inkl. `/robots.txt`, `/xml/*`, `/ajax.php`) | blockerad |
| `mzlive.eu` | blockerad |
| `greasyfork.org`, `update.greasyfork.org`, `sleazyfork.org` | blockerade |
| `web.archive.org` | blockerad |
| `github.com` / `raw.githubusercontent.com` (publika repon) | **nåbar** |

**Därför finns i den här rapporten inga uppgifter som är verifierade genom egna tester.** Inga riktiga svar från ManagerZone kunde hämtas. Datastrukturerna i avsnitt 4 är rekonstruerade ur tredjepartskod och tredjepartsdokumentation och är märkta som sådana. Inga försök gjordes att ta sig runt blockeringen, till exempel via proxytjänster.

För att verifiera behöver `www.managerzone.com` och `greasyfork.org` (helst även `update.greasyfork.org` och `mzlive.eu`) läggas till under *Allowed domains* i miljöns nätverksinställningar (https://code.claude.com/docs/en/cloud-environments#network-access). Alternativt kan du själv köra ett fåtal anrop i din webbläsare.

### 1.2 Evidensnivåer som används i rapporten

| Nivå | Betydelse |
|---|---|
| **A: Eget test** | Testat i den här undersökningen. *Inga uppgifter når denna nivå.* |
| **B: Tredjepartstest** | En tredje part har dokumenterat ett faktiskt anrop mot managerzone.com med datum och utfall. |
| **C: Tredjepartskod** | Anropet finns i aktiv, öppen källkod men utfallet är inte dokumenterat. |
| **D: Äldre kod/forum** | Finns bara i gammal kod (≥ 10 år) eller i forum- och sökresultat. Kan ha ändrats. |

### 1.3 Källor som analyserades

| Källa | Typ | Aktualitet | Används för |
|---|---|---|---|
| [mz-ir/mazyar](https://github.com/mz-ir/mazyar) (även på Greasy Fork #476290) | Användarskript, MIT | aktivt 2026 | `manager_data.php`, `match_info.php`, `ajax.php` (spelare, scoutrapport, transfer), HTML-sidor |
| [gastonandriolo/managerzone-tactical-analysis](https://github.com/gastonandriolo/managerzone-tactical-analysis) v1.5.0 | Användarskript | 2026 | `getMatchFiles.php` (stats/data), taktikattribut, byten, taktikändringar |
| [frechdachs85a/MZ-Manager](https://github.com/frechdachs85a/MZ-Manager) (`mz-coach/docs/mz-seiten.md`, `mz-wissen.md`, parsers + tester) | App + daterade observationer | 21–26 okt 2026 | Tredjepartstester (nivå B): inloggningskrav, `check-match`, matchlista, robots.txt, användarvillkor |
| [jreyes33/mzcompare](https://github.com/jreyes33/mzcompare) | Python-app (server-side, utan inloggning) | 2013 | `team_matchlist.php`, `team_playerlist.php`, `team_league.php`, `manager_data.php?team_id=` |
| Greasy Fork-listningar (via sökmotor, inte direkt) | Metadata | 2025–2026 | Beskrivning av *MZ Player Weekly Matches Tracker* och *MZ Axis* |
| ManagerZone-forum och community-FAQ (via sökmotor) | Forum | 2012–2018 | Status för officiellt API / MZ Tools |

---

## 2. Svar på frågorna 1–10

### 2.1 Officiellt API eller dokumenterade dataformat?

- **Inget öppet, dokumenterat API.** Enligt ett svar från ManagerZone-personal (2015) är utvecklar-API:et stängt för nya appar: *"Unless you already have an mz app approved by us you cannot make API calls against it."* (nivå D, forum via sökning). Det fanns tidigare ett certifieringsprogram ("MZ Tools", APPLY/RULES) och en SOAP-tjänst (`/xml/mtcp.wsdl`), men ingen aktuell dokumentation hittades.
- **XML-gränssnittet under `/xml/`** är länkat från sidfoten ("XML Content", tänkt för att visa MZ-data på egna hemsidor). Det är halvofficiellt men odokumenterat. Kända endpoints: `manager_data.php`, `match_info.php` (används av Mazyar 2026, nivå C), samt `team_matchlist.php`, `team_playerlist.php`, `team_league.php` (endast 2013, nivå D).
- **Taktik-XML (`<SoccerTactics>`)** är ett användarsynligt format i taktikeditorn (kopiera/klistra in). Det är inget datahämtnings-API, men det är relevant som utdataformat.

### 2.2 Vilka anrop använder de öppna användarskripten?

| Skript | Anrop (ur källkod) | Nivå |
|---|---|---|
| **Mazyar** | `GET /xml/manager_data.php?username=<u>` → `Team[sport=…]@teamId, @teamName` | C |
| | `GET /xml/match_info.php?sport_id=1&match_id=<mid>` → `Team[field=home/away]@id, @goals`; felrot `ManagerZone_Error` | C |
| | `GET /?p=players&sub=alt&tid=<tid>` (kadersammanfattning, HTML) → ålder, värde | C |
| | `GET /?p=players&tid=<tid>` och `/?p=players&pid=<pid>` (HTML) → namn, ålder, färdigheter, maxade färdigheter | C |
| | `GET /ajax.php?p=players&sub=scout_report&pid=<pid>&sport=soccer` (HTML) | C |
| | `GET /ajax.php?p=transfer&sub=transfer-search&…` → JSON `{totalHits, players(HTML)}` | C (inloggningskrav B) |
| | `GET /ajax.php?p=nationalTeams&sub=players&ntid=<id>&sport=…` | C |
| **ManagerZone – Tactical Analysis** | `GET /matchviewer/getMatchFiles.php?type=stats&mid=<mid>&sport=soccer` (`credentials: same-origin`) | C |
| | `GET /matchviewer/getMatchFiles.php?type=data&mid=<mid>&sport=soccer` (fallback för händelser) | C |
| | `GET /?p=tactics&sport=soccer`, `/?p=training&sport=soccer` (egna data) | C |
| **MZ-Manager (mz-coach)** | `GET /ajax.php?p=matchViewer&sub=check-match&type=2d&mid=<mid>&sport=soccer` → JSON | B |
| | `POST /ajax.php?p=matches&sub=list&sport=soccer` (formulär) | B (kräver inloggning) |
| **mzcompare (2013)** | `/xml/team_matchlist.php?sport_id=1&team_id=<tid>&match_status=1\|2&limit=<n>` | D |
| | `/xml/team_playerlist.php?sport_id=1&team_id=<tid>` | D |
| | `/xml/team_league.php?sport_id=1&league_id=<sid>` | D |
| | `/xml/manager_data.php?sport_id=1&team_id=<tid>` och `&username=<u>` | D |

**De två skript du särskilt bad om:**

- **MZ – Player Weekly Matches Tracker** (Greasy Fork #469470, douglasdotv, MIT, v5.4–5.5, 2025): Räknar hur många vänskaps- och ligamatcher (senior/U23/U21/U18) varje spelare i **det egna laget** spelat under innevarande vecka. Knappen ligger på utmaningssidan. **Källkoden kunde inte läsas** eftersom greasyfork.org är blockerad och det inte finns någon GitHub-spegel. *Slutsats utifrån beskrivningen (ej verifierad):* skriptet bör använda den inloggade matchlistan (`ajax.php?p=matches&sub=list`, filtrerad på vecka och typ) och per match uppgifter om deltagande, troligen via matchrapporten eller `getMatchFiles` (`Player`-element). Det visar framför allt att *matchtyp och spelardeltagande per match går att hämta automatiskt*.
- **MZ Axis** (Greasy Fork #489696, "J R C L", MIT, v0.4.1, 2026-03-13, baserat på "Murder"-skriptet): Förbättrar taktikeditorn. Funktionerna är kopiera/klistra in formationer (koordinater eller XML), **visa motståndarens formation med extra spelardata utifrån ett match-ID** och spara taktiker. Enligt listningen krävs att 2D-visaren initierats minst en gång för att statistiken ska genereras, och skriptet ber om behörighet att hämta "statistikfilen från MZ-servern". **Källkoden kunde inte läsas** (blockerad). *Slutsats (ej verifierad men stämmer helt med nivå B/C-källorna):* skriptet använder `check-match`/2D-initiering + `getMatchFiles.php?type=stats`. Den behörighetsfråga som beskrivs är typisk för `GM_xmlhttpRequest` med `@connect`.

### 2.3 Laginformation utifrån manager-ID eller lag-ID

| Väg | Indata | Ger | Inloggning | Nivå |
|---|---|---|---|---|
| `/xml/manager_data.php?sport_id=1&username=<u>` | användarnamn | användardata + lag per sport (`teamId`, `teamName`, m.m.) | nej (antaget) | C (2026) |
| `/xml/manager_data.php?sport_id=1&team_id=<tid>` | lag-ID | användardata (`userId`, `username`) + lagdata | nej | D (2013) |
| `/?p=team&tid=<tid>` (HTML) | lag-ID | lagsida | okänt | C (länk används) |
| `/?p=players&sub=alt&tid=<tid>` (HTML) | lag-ID | kadersammanfattning (namn, värde, ålder, …) | **ja** (B: utan inloggning omdirigeras man till en utloggningssida) | B/C |
| `/xml/team_playerlist.php?sport_id=1&team_id=<tid>` | lag-ID | spelarlista (`id, name, age, value, salary, junior, countryShortname`), lagets valuta | nej (2013) | D |

**Manager-ID (user ID):** Ingen källa visar en endpoint som tar `user_id` direkt. Ett forum från 2000-talet nämner `manager_data.php?user_id=`, men det är obekräftat (D). Säkrast är användarnamn eller lag-ID. Profilsidan `/?p=profile&uid=<uid>` finns (C).

### 2.4 Senaste 20 matcherna för ett lag

1. **Primär väg (B, kräver inloggning):** `POST /ajax.php?p=matches&sub=list&sport=soccer` med formulärfälten
   `type=played, hidescore=false, tid1=<TID>, tid2=<eget TID|tomt>, offset=, selectType=<all|series|cup|friendly|scout_match|world_series|…>, limit=<default|max>`.
   - `limit=default` ger de **senaste 25** matcherna, så de 20 senaste kan tas därifrån. `limit=max` ger fler.
   - Svaret är HTML (eventuellt inbäddat i JSON) med `dl#fixtures-results-list`, där varje match är en `dd.odd/.even` med datum, tid, matchtyp, tävling, hemma/borta (`tid`), resultat och match-ID (`dl#action-panel-<mid>`).
   - Utan inloggning blir svaret: `"An error occurred: You need to be logged in"` (B, 25.10.2026).
   - Observera: standardlistan blandar alla typer. Ett lag med många cupmatcher kan bara ha 2 ligamatcher bland de 25 senaste (B). Använd därför `selectType=series` när just ligamatcher behövs.
2. **Alternativ utan inloggning (D, obekräftat 2026):** `/xml/team_matchlist.php?sport_id=1&team_id=<TID>&match_status=1&limit=20` (`match_status=1` = spelade, `2` = kommande). Svaret är en lista med `Match`-element, vart och ett med två `Team`-barn (hemma, borta). **Detta bör testas först**, eftersom det i så fall löser matchlistan helt utan inloggning.
3. HTML-sidan `/?p=match&sub=played&tid=<TID>` ger samma lista, men `/?p=match` är **spärrad i robots.txt** (B).

### 2.5 Serie, cup eller träningsmatch

| Var | Hur | Nivå |
|---|---|---|
| Matchlistan (ajax) | Texten i `.match-reference-text-wrapper span`: "League match"/"Ligaspiel", "Official cup", "Friendly", "Scout match" (språkberoende). Ungdomsmatcher har dessutom klassen `uxx`. Tävlingslänk (`?p=league…`, `?p=cup…`, `?p=private_cup…`, `?p=friendlyseries…`) | B |
| Matchlistan (filter) | Serverfilter `selectType` = `series`, `cup`, `friendly`, `scout_match`, `world_series`, åldersklasser | B |
| Stats-XML | Rotattribut `SoccerStatistics@type` (värdena är inte dokumenterade) | B (attribut finns) |
| `match_info.php` / `team_matchlist.php` | `Match@type` (troligen även typnamn/typ-ID) | D |
| Heuristik | Intervall för match-ID per säsong (t.ex. liga > 1 620 000 000 säsong 100). Bräckligt, rekommenderas inte. | B (skör) |

Mest robust är att använda `selectType` som filter och läsa länken till tävlingen (`p=league|cup|private_cup|friendlyseries`), som inte beror på språk.

### 2.6 Innehåller matchrapporter startelva, formation, spelstil och aggressivitet?

**Ja, i stats-XML:en. Inte i `match_info.php`.**

| Uppgift | Finns | Var | Nivå |
|---|---|---|---|
| Startelva | ja | `Player` med icke-tomt `origin` (bänkspelare har tomt `origin`), `teamId`, `shirtno`, `goalkeeper="1"` | B (testat på verklig fil, 32 spelare, 11 startande per lag) |
| Formation | **härledbar** | `origin="x,y"` för de 11 startande. Omräkning till editorns koordinater är dokumenterad och bekräftad på ±1 punkt. Formationsnamnet (t.ex. 4-4-2) finns inte explicit och måste klustras fram. | B |
| Taktik (passningsspel) | ja | `Team@tactic` = `wings` / `shortpass` / `longball` | B |
| Spelstil | ja | `Team@playstyle` = `offensive` / `normal` / `defensive` | B |
| Aggressivitet | ja | `Team@aggression` = `aggressive` / `normal` / `passive` | B |
| Ändringar under matchen | delvis | `Events/Tactic@type, @new_setting, @time` (bara regler som utlöstes; villkoret syns inte) | B/C |
| Byten | ja | `Events/Substitution@playerId, @substitutedId, @minute, @reason (preset/injury)` | B |
| Mål, kort | ja | `Player/Goal@time, @assister`, `Player/Card@type` | B |
| Lagstatistik | ja | `Team/Statistics` och `HalfStatistics` (mål, bollinnehav, skott på/utanför mål, …) | B |
| Spelarstatistik | ja | `Player/Statistics` | B |
| Detaljerad spelarstatistik (33 fält) | ja | HTML `/?p=match&sub=result&mid=` → "Complete match statistics" (**spärrad i robots.txt**) | B |

**Praktiska villkor för stats-XML (B):**
- Filen kan vara tom (0 byte) tills 2D-visaren har "förberett" matchen. Anropa först `GET /ajax.php?p=matchViewer&sub=check-match&type=2d&mid=<mid>&sport=soccer` och upprepa var 5–6:e sekund tills svaret blir `{"response":"ok"}`. Svaret `"queued"` med `"Error preparing match!"` är ett mellanläge och inget fel.
- Utan `&sport=soccer` blir svaret ofta tomt.
- Direkt efter en match kan filen fortfarande räknas fram.
- **Ligamatcher: fungerar utan inloggning (B, 7 matcher testade 25.10.2026).** **Scoutmatcher: `{"response":"blocked"}` utan inloggning.**
- `type=data` är hela 2D-scenfilen (cirka 2,7 MB) och behövs inte för taktikanalys.

### 2.7 Spelaruppgifter: namn, ålder, position, värde, lön, färdigheter

| Fält | Eget lag | Andra lag | Källa | Nivå |
|---|---|---|---|---|
| Namn | ja | ja | `?p=players`, `?p=players&sub=alt`, stats-XML `Player@name` | B |
| Ålder | ja | ja | `?p=players&sub=alt` (kolumn), spelarprofil | B (eget) / C (andra) |
| Position | se not | se not | ManagerZone har ingen fast position per spelare. Matchposition = `Player@position`/`origin` i stats-XML. Editorns positionsetikett (`.pitch-position`) gäller bara det egna laget. | B |
| Värde | ja | ja | `?p=players&sub=alt`, profil, `team_playerlist.php` (D) | B / C |
| Lön | ja | **i regel nej** | `?p=players&sub=alt` (eget). Okänt om `team_playerlist.php@salary` fortfarande lämnas ut för andra lag (D 2013). | B / D |
| Färdigheter (11 st + form, erfarenhet) | ja, inkl. "maxed" | **bara när de är offentliga** (enligt B gällde det cirka 104 spelare i 10 topplag) | `table.player_skills`, `#playerAltViewTable` | B |
| Scoutrapport (stjärnor/potential) | ja | nej | `ajax.php?p=players&sub=scout_report` | C |
| Skador/avstängningar | ja | nej | `?p=players&sub=unavailable` | B |
| Träningsläger | ja | nej | `?p=training_camp`, `dd.tc` i `?p=tactics` | B |

Alla HTML-vägar under `/?p=players` kräver inloggning, även för andra lag (B: utan inloggning omdirigeras man till en utloggningssida).

### 2.8 Motståndarens taktiska inställningar, eller bara formationen?

**Mer än formationen syns, men bara för matcher som redan spelats.** Ur stats-XML:en för en spelad match kan man för motståndaren läsa:

- startformation (positioner), taktik, spelstil och aggressivitet vid avspark,
- taktikändringar och byten som faktiskt utlöstes, med tidpunkt.

**Det som inte kan hämtas:**
- motståndarens sparade taktiker i editorn och inställningar inför en kommande match,
- villkoren i taktikregler (bara utlösta händelser syns, inte "om vi leder med 1 efter 60'"),
- regler som aldrig utlöstes, alternativa formationer 1 och 2 om de aldrig användes,
- straff- och frisparksskyttar, lagkapten (de finns i taktik-XML men inte i stats-XML),
- färdigheter för spelare som inte är offentliga.

Att se icke-offentliga laguppgifter utan ägarens tillstånd är dessutom uttryckligen förbjudet enligt spelreglerna (se 2.10). Data om motståndare bör därför begränsas till det som ManagerZone själv visar publikt, alltså spelade matcher.

### 2.9 Vad kräver autentisering?

| Endpoint / sida | Inloggning | Grund |
|---|---|---|
| `/xml/manager_data.php` | nej (antaget) | C/D (mzcompare körde server-side utan cookies) |
| `/xml/match_info.php` | nej (antaget) | C/D |
| `/xml/team_matchlist.php`, `team_playerlist.php`, `team_league.php` | okänt (nej 2013) | D |
| `/matchviewer/getMatchFiles.php?type=stats` | **nej** för liga | B |
| `/ajax.php?p=matchViewer&sub=check-match` | **nej** för liga, **blockerad** för scoutmatch | B |
| `POST /ajax.php?p=matches&sub=list` (matchlista/spelschema) | **ja** | B |
| `/?p=players…` (alla varianter, alla lag) | **ja** | B |
| `/ajax.php?p=players&sub=scout_report` | ja (eget lag) | C |
| `/ajax.php?p=transfer&sub=transfer-search` | **ja** | B |
| `/?p=tactics`, `/?p=training`, `/?p=training_camp` | ja (eget lag) | B |
| `/?p=match&sub=result&mid=` | okänt (spärrad i robots.txt) | B |

Sessionen bärs av cookien `PHPSESSID` (B). Inloggningssidan laddar reCAPTCHA och spärrar IP-adressen tillfälligt efter för många misslyckade försök (B). Automatisk inloggning är därför både bräcklig och riskabel. Ett verktyg ska aldrig spara eller automatiskt försöka igen med lösenord.

### 2.10 Användarvillkor och åtkomstbegränsningar

Följande citat kommer från tredjepartsdokumentation (MZ-Manager, `docs/mz-seiten.md`, läst 24.10.2026). Jag kunde inte läsa originalsidorna själv.

- **Terms of Use** (`/?p=start&sub=terms_of_use`, "Revised May 2018"):
  > "You may not modify, adapt, translate, reverse engineer, decompile, or disassemble the Software or create any derivative work thereof or any **software interfacing with the Software**." ("Software" omfattar uttryckligen "all HTML code contained in this Web site".)
  > "Failure to abide by these terms and conditions may result in disqualification, account closure, forfeiture of funds and/or legal action against you."
- **General Rules** (`/?p=start&sub=game_rules`):
  > "you must not log into any account other than your own"
  > "It is also forbidden to view any non-public team details without the owner's or crew's permission"
  Enligt källan finns ingen uttrycklig regel om botar, skript eller anropsfrekvens.
- **robots.txt:** `User-agent: *` → `Disallow: /?p=match` (matchrapportsidor), `/css/`, `/js/`, `/img/`. `ClaudeBot`, `GPTBot`, `OAI-SearchBot` m.fl. får `Disallow: /`. `/?p=players`, `/ajax.php`, `/xml/` och `/matchviewer/` står inte med.
- **Utvecklar-API:** stängt för nya appar sedan 2015 (forum, D).
- **Praxis i communityn:** Det finns många öppna användarskript (Greasy Fork, MIT) som anropar exakt dessa endpoints och som verkar tolereras. Det är ingen juridisk garanti.

**Konsekvenser för verktyget:**
1. Klausulen om "software interfacing with the Software" omfattar formellt även ett privat analysverktyg. **Rekommendation: be ManagerZone-supporten om skriftligt godkännande** för privat, lågfrekvent användning innan något automatiseras.
2. Hämta bara publika data och data om det egna laget, med det egna kontot. Logga aldrig in på någon annans konto.
3. Skrapa inte `/?p=match`, eftersom den är spärrad i robots.txt. Använd stats-XML i stället.
4. Begränsa anropstakten: sekventiellt, några sekunders paus (tredje part använde 3–6 s), cache per `mid` (en spelad match ändras inte) och ingen parallellisering.
5. Ett verktyg som körs av en AI-agent omfattas sannolikt av blockeringen av `ClaudeBot` i robots.txt. Datainsamlingen bör därför köras som ditt eget skript eller användarskript, inte av en crawler.

---

## 3. Endpoint-katalog

| # | Endpoint | Metod | Parametrar | Svarsformat | Inloggning | Nivå |
|---|---|---|---|---|---|---|
| E1 | `/xml/manager_data.php` | GET | `sport_id=1`, `username=` eller `team_id=` | XML | nej? | C/D |
| E2 | `/xml/match_info.php` | GET | `sport_id=1\|2`, `match_id=` | XML (`ManagerZone_Error` vid fel) | nej? | C/D |
| E3 | `/xml/team_matchlist.php` | GET | `sport_id=1`, `team_id=`, `match_status=1\|2`, `limit=` | XML | okänt | D |
| E4 | `/xml/team_playerlist.php` | GET | `sport_id=1`, `team_id=` | XML | okänt | D |
| E5 | `/xml/team_league.php` | GET | `sport_id=1`, `league_id=` | XML (tabell) | okänt | D |
| E6 | `/ajax.php?p=matches&sub=list&sport=soccer` | POST | `type, hidescore, tid1, tid2, offset, selectType, limit` | HTML (eventuellt i JSON) | **ja** | B |
| E7 | `/ajax.php?p=matchViewer&sub=check-match` | GET | `type=2d, mid, sport=soccer` | JSON `{response, content}` | nej (liga) | B |
| E8 | `/matchviewer/getMatchFiles.php` | GET | `type=stats\|data, mid, sport=soccer` | XML (stats) / binär (data) | nej (liga) | B |
| E9 | `/?p=players&sub=alt&tid=` | GET | `tid` | HTML `#playerAltViewTable` | **ja** | B |
| E10 | `/?p=players&tid=` / `&pid=` | GET | `tid`/`pid` | HTML `div#thePlayers_<n>` | **ja** | B |
| E11 | `/ajax.php?p=players&sub=scout_report` | GET | `pid, sport` | HTML | ja | C |
| E12 | `/ajax.php?p=transfer&sub=transfer-search` | GET | sökformulärets fält, `o` (offset) | JSON `{totalHits, players}` | **ja** | B/C |
| E13 | `/?p=tactics` | GET | – | HTML (eget lag) | ja | B |
| E14 | `/?p=match&sub=result&mid=` | GET | `mid` | HTML | okänt | B (**robots: disallow**) |

---

## 4. Datastrukturer per endpoint

> **Obs:** Inget av exemplen nedan är ett riktigt svar som hämtats i den här undersökningen. De är **strukturskisser** som bara innehåller element- och attributnamn som förekommer i den angivna tredjepartskällan. Värden står som `…`, utom där källan själv återger ett verkligt värde (det markeras då).

### E1 `manager_data.php` (C: Mazyar 2026; D: mzcompare 2013)

```xml
<!-- rot: okänt namn; användardata = första barnet, lagdata = dess barn (mzcompare) -->
<…>
  <UserData userId="…" username="…" …>          <!-- elementnamn ej bekräftat -->
    <Team sport="soccer" teamId="…" teamName="…" … />   <!-- Mazyar: Team[sport=…]@teamId/@teamName -->
  </UserData>
</…>
```
Bekräftade attribut (C): `Team@sport`, `Team@teamId`, `Team@teamName`. Från D: `userId`, `username`, `countryShortname`, `seriesId`, `seriesName`.

### E2 `match_info.php` (C: Mazyar 2026; D: mzcompare 2013)

```xml
<…>                                   <!-- vid fel: <ManagerZone_Error …> -->
  <Match id="…" date="…" type="…" …>  <!-- matchattribut (D) -->
    <Team field="home" id="…" goals="…" … />
    <Team field="away" id="…" goals="…" … />
  </Match>
</…>
```
Bekräftat (C): `Team[field=home|away]@id`, `@goals`. Används för resultat, **inte** för taktik.

### E3 `team_matchlist.php` (D: mzcompare 2013)

```xml
<…>
  <Match id="…" date="…" type="…" …>   <!-- ett per match, i ordning -->
    <Team … />                         <!-- hemma (första barn) -->
    <Team … />                         <!-- borta (sista barn) -->
  </Match>
  …
</…>
```

### E4 `team_playerlist.php` (D: mzcompare 2013)

```xml
<…>
  <TeamPlayers teamId="…" teamName="…" teamCurrency="…" countryShortname="…">  <!-- elementnamn ej bekräftat -->
    <Player id="…" name="…" age="…" value="…" salary="…" junior="…" countryShortname="…" … />
  </TeamPlayers>
</…>
```

### E6 matchlista (B: MZ-Manager, verklig sida 25.10.2026)

```html
<dl id="fixtures-results-list" class="fixtures">
  <dd class="group">24-10-2026</dd>
  <dd class="odd [uxx]">
    <span class="match-time">HH:MM</span>
    <div class="match-reference-text-wrapper"><span>League match</span> <a href="?p=league…">div1.1</a></div>
    <dd class="home-team-column"><a href="?p=team&tid=…"><span class="full-name">…</span></a></dd>
    <a class="score-shown" href="…mid=…">2 - 4</a>                 <!-- verkligt exempelvärde i källan -->
    <dd class="away-team-column">…</dd>
    <dl id="action-panel-<mid>">…</dl>
  </dd>
</dl>
<input id="tid1" value="…">
```
Utan inloggning blir svaret texten `An error occurred: You need to be logged in` (B).

### E7 `check-match` (B: verkliga svar 25.10.2026, citerade av tredje part)

```json
{"response":"queued","content":"Error preparing match!"}
{"response":"ok","content":"<script …"}
{"response":"blocked","content":"You are not allowed to view …"}
```

### E8 `getMatchFiles.php?type=stats` (B: verklig fil, match 1625669278, 24–27 KB; C: två skript)

```xml
<?xml version="1.0" encoding="utf-8"?>
<SoccerStatistics matchId="…" type="…" date="2026-10-21 14:45:00" enddate="…" version="…" seed="…" final="1">
  <Team id="…" name="FFK Kosova" shortname="…" visiting="0"
        tactic="wings" playstyle="normal" aggression="passive">   <!-- verkliga värden ur testfil -->
    <MetaData manager="…" series_name="…"/>
    <HalfStatistics …/>
    <Statistics goals="…" possession="…" shotsOnGoal="…" shotsWide="…" …/>
  </Team>
  <Team id="…" name="FC Toho" visiting="1" tactic="shortpass" playstyle="normal" aggression="normal">…</Team>

  <!-- Player-element ligger INTE under Team; de bär teamId -->
  <Player id="…" teamId="…" name="…" shirtno="…" goalkeeper="1" position="…" origin="375,1000">
    <Goal frame="…" time="…" clock="…" team="…" assister="…"/>
    <Card time="…" clock="…" frame="…" type="yellow|second yellow|red"/>
    <Miss …/> <Save …/> <Statistics …/>
  </Player>
  <Player … origin=""/>                         <!-- tomt origin = bänk -->

  <Events>
    <Substitution time="…" clock="…" frame="…" playerId="…" teamId="…" substitutedId="…" reason="preset|injury" minute="…"/>
    <Tactic teamId="…" type="tactic|playstyle|aggression" new_setting="…" time="…" minute="…"/>
    <Replay …/> <Post …/>
  </Events>
</SoccerStatistics>
```
Omräkning `origin` → editorns koordinater (B, bekräftad ±1): om målvaktens `origin-y = 1000` gäller `d = 1000 − y` och x behålls; om `origin-y = 0` gäller `d = y` och `x' = 750 − x`. Därefter `editor_x = 0.2555·x + 8.4` och `editor_y = max(63, 318 − 0.31·d)`.

### E9 kadersammanfattning (B: verklig sida 24.10.2026)

`table#playerAltViewTable`, kolumner: nr, namn (`?p=players&pid=<PID>`), värde, lön, ålder, född (säsong), Speed, Stamina, Play intelligence, Passing, Shooting, Heading, Keeping, Ball control, Tackling, Aerial passing, Set plays, Experience, Form. Maxad färdighet = `td.maxed`. Belopp anges som `1 084 289 EUR`.

---

## 5. Fälttabell

Kolumnen "Automatiskt hämtbar" följer din skala. Eftersom inget kunde testas här används **inte** "verifierad". "Möjlig" har kompletterats med evidensnivå (B/C/D) enligt 1.2.

| Fältnamn | Datakälla | Endpoint / sidtyp | Kräver inloggning | Automatiskt hämtbar | Begränsningar |
|---|---|---|---|---|---|
| Användar-ID, användarnamn | XML | E1 `manager_data.php` | nej (antaget) | möjlig (C/D) | Ingen sökning på user-ID är bekräftad |
| Lag-ID, lagnamn per sport | XML | E1 | nej (antaget) | möjlig (C) | – |
| Land, serie-ID/-namn för lag | XML | E1 | nej (antaget) | möjlig (D) | Attributnamn från 2013 |
| Ligatabell | XML | E5 `team_league.php` | okänt | möjlig (D) | Obekräftat 2026 |
| Match-ID-lista (senaste N) | AJAX | E6 matchlista | **ja** | möjlig (B) | `limit=default` = 25; kräver session |
| Match-ID-lista (alternativ) | XML | E3 `team_matchlist.php` | okänt | möjlig (D) | Kan vara nedlagd |
| Matchdatum/-tid | AJAX / XML | E6 / E8 `@date` | ja / nej | möjlig (B) | Serverns tid ≈ Europe/Berlin |
| Matchtyp (liga/cup/vänskap/scout) | AJAX | E6 (text + tävlingslänk, `selectType`) | **ja** | möjlig (B) | Texten är språkberoende; använd länktyp/filter |
| Matchtyp (rå) | XML | E8 `SoccerStatistics@type`, E2/E3 `Match@type` | nej | möjlig (B/D) | Värdena är inte dokumenterade |
| Resultat | XML | E2 `Team@goals`, E8 `Statistics@goals` | nej | möjlig (C/B) | – |
| Hemma/borta | XML | E2 `@field`, E8 `@visiting` | nej | möjlig (C/B) | – |
| Motståndarens lag-ID/-namn | XML | E8 `Team@id/@name` | nej | möjlig (B) | – |
| Motståndarens manager | XML | E8 `MetaData@manager` | nej | möjlig (B) | – |
| Startelva | XML | E8 `Player` med `origin` | nej (liga) | möjlig (B) | Kräver `check-match`; scout = blockerad utan inloggning |
| Formation (positioner) | XML | E8 `Player@origin` | nej (liga) | möjlig (B) | Inget formationsnamn; måste härledas |
| Taktik (wings/shortpass/longball) | XML | E8 `Team@tactic` | nej (liga) | möjlig (B) | Läge vid avspark |
| Spelstil | XML | E8 `Team@playstyle` | nej (liga) | möjlig (B) | Läge vid avspark |
| Aggressivitet | XML | E8 `Team@aggression` | nej (liga) | möjlig (B) | Läge vid avspark |
| Taktikändringar i matchen | XML | E8 `Events/Tactic` | nej (liga) | möjlig (B/C) | Bara utlösta regler, utan villkor |
| Byten | XML | E8 `Events/Substitution` | nej (liga) | möjlig (B) | `reason` preset/injury |
| Mål, assist, kort | XML | E8 `Player/Goal`, `Player/Card` | nej (liga) | möjlig (B) | – |
| Lagstatistik (bollinnehav, skott …) | XML | E8 `Team/Statistics`, `HalfStatistics` | nej (liga) | möjlig (B) | Fullständig attributlista ej dokumenterad |
| Spelarstatistik per match | XML | E8 `Player/Statistics` | nej (liga) | möjlig (B) | – |
| Detaljerad spelarstatistik (33 fält) | HTML | E14 matchrapport | okänt | **ej tillgänglig** (bör inte användas) | Spärrad i robots.txt |
| Komplett 2D-scen (rörelser) | binär | E8 `type=data` | nej? | möjlig (C) | ~2,7 MB, odokumenterat format |
| Spelarnamn | XML / HTML | E8 `Player@name`, E9/E10 | nej / ja | möjlig (B) | – |
| Tröjnummer | XML | E8 `@shirtno` | nej | möjlig (B) | – |
| Ålder | HTML / XML | E9/E10, E4 | ja / okänt | möjlig (B/D) | – |
| Position i match | XML | E8 `@position`, `@origin` | nej | möjlig (B) | Ingen fast position i MZ |
| Marknadsvärde | HTML / XML | E9/E10, E4 | ja / okänt | möjlig (B/D) | Valutan beror på lagets land |
| Lön | HTML | E9 (eget lag) | ja | möjlig (B) eget lag; **ej tillgänglig** andra lag (sannolikt) | E4 `@salary` 2013, obekräftat |
| Färdigheter (11) + form + erfarenhet | HTML | E9/E10 | ja | möjlig (B) eget lag; andra lag endast offentliga | Icke-offentliga: förbjudet att se utan tillstånd |
| Maxade färdigheter | HTML | E9/E10 `.maxed` | ja | möjlig (B) eget lag | – |
| Scoutrapport (potential) | AJAX | E11 | ja | möjlig (C) eget lag | – |
| Skador/avstängningar | HTML | `?p=players&sub=unavailable` | ja | möjlig (B) eget lag | Strukturen för fallet med skador är inte sedd |
| Träningsläger / ej uppställningsbar | HTML | `?p=training_camp`, E13 `dd.tc` | ja | möjlig (B) eget lag | – |
| Egna sparade taktiker | HTML / XML | E13 + `<SoccerTactics>` i editorn | ja | möjlig (B/C) eget lag | – |
| Motståndarens sparade taktiker/regler | – | – | – | **ej tillgänglig** | Syns inte för andra |
| Motståndarens uppställning inför kommande match | – | – | – | **ej tillgänglig** | Bara historik |
| Veckans matcher per spelare | AJAX + XML | E6 + E8 (`Player` per match) | ja (lista) | möjlig (C, härledd från Weekly Tracker-beskrivning) | Skriptets källkod är inte läst |
| Transfermarknad | AJAX | E12 | ja | möjlig (B/C) | Inte relevant för taktik |
| MZ "manager value"-formel | mzlive.eu | – | – | ej undersökt (blockerad) | Vikter finns citerade i tredjepartskälla |

---

## 6. mzlive.eu

Värden var blockerad och kunde inte undersökas. Utifrån sökresultat och tredjepartskällor är det en communitysajt ("MZ Live Project") med bland annat en **taktikkonverterare** (`/tactics-converter/`) och ett "MZ Manager"-värde per spelare (viktad summa av färdigheter). Inget offentligt API från mzlive.eu hittades. Sajten är en sekundärkälla som själv bygger på MZ-data och är inte relevant som datakälla för ett eget verktyg.

---

## 7. Öppna frågor som bör verifieras först (när nätverket tillåter)

Ordnade efter nytta. Kör sekventiellt, ett anrop i taget, med några sekunders paus:

1. `GET /robots.txt` och `/?p=start&sub=terms_of_use`: bekräfta citaten ovan.
2. `GET /xml/team_matchlist.php?sport_id=1&team_id=<TID>&match_status=1&limit=20` utan inloggning. **Om det fungerar behövs ingen inloggning för matchlistan.**
3. `GET /xml/match_info.php?sport_id=1&match_id=<MID>` och `/xml/manager_data.php?sport_id=1&team_id=<TID>`: dokumentera rotelement och attribut.
4. `GET /ajax.php?p=matchViewer&sub=check-match&type=2d&mid=<MID>&sport=soccer`, därefter `GET /matchviewer/getMatchFiles.php?type=stats&mid=<MID>&sport=soccer` för en ligamatch, en cupmatch och en vänskapsmatch. Kontrollera värdena i `SoccerStatistics@type` och om cup- och vänskapsmatcher också är öppna utan inloggning.
5. `GET /xml/team_playerlist.php?sport_id=1&team_id=<annat TID>`: lämnas `salary` och färdigheter ut?
6. Läs källkoden till *MZ Axis* och *Weekly Matches Tracker* på Greasy Fork (`/code`) och bekräfta antagandena i 2.2.

---

## 8. Bedömning: är ett automatiskt taktiskt analysverktyg tekniskt genomförbart?

**Ja, tekniskt sett mycket troligt. Den viktigaste osäkerheten gäller villkoren, inte tekniken.**

**Talar för:**
- Kärnan i en taktisk analys finns i en enda strukturerad XML per spelad match: formation, taktik, spelstil, aggressivitet, byten, taktikändringar och statistik för **båda** lagen. Två oberoende tredjepartsprojekt läser filen i drift i oktober 2026, ett av dem med enhetstester mot en verklig fil.
- Ligamatcher ska enligt tredjepartstest kunna hämtas **utan inloggning**.
- Matchlistor med typfilter finns (med inloggning), och ett möjligt XML-alternativ utan inloggning.
- Datamängden är liten (cirka 25 KB per match, 20 matcher per lag), så det räcker med väldigt få anrop och allt kan cachas permanent per match-ID.

**Begränsningar som påverkar verktygets design:**
- Analysen blir **historisk och utfallsbaserad**. Motståndarens sparade taktik, regelvillkor och planer inför en kommande match går inte att se.
- Formationer måste **härledas** ur koordinater (klustring till 4-4-2, 4-2-1-3 osv.).
- Matchfilen måste ibland "förberedas" via `check-match` (köhantering och omförsök) och kan saknas direkt efter en match.
- Matchlistor kräver troligen inloggad session (cookien `PHPSESSID`, reCAPTCHA vid inloggning). En robust lösning är att verktyget använder **din egen webbläsarsession**, till exempel som användarskript eller med manuellt inklistrad cookie, i stället för automatisk inloggning.
- Färdigheter och lön för motståndarnas spelare är i regel inte tillgängliga och får inte hämtas utan tillstånd.
- Matchtyp i klartext är språkberoende och bör tolkas via filter eller tävlingslänk.
- Allt bygger på odokumenterade, interna endpoints som kan ändras utan förvarning.

**Villkor och risk:**
- ToU-klausulen om "software interfacing with the Software" gör att även ett privat verktyg formellt kan bryta mot villkoren, med kontostängning som möjlig påföljd. Många öppna användarskript gör i praktiken samma sak, men det är ingen garanti.
- **Rekommendation:** (1) Be ManagerZone-supporten om godkännande. (2) Om du går vidare: bara eget konto, låg takt, cache, ingen skrapning av `/?p=match`, inga icke-offentliga data om andra lag, ingen automatisk inloggning. (3) Verifiera först punkterna i avsnitt 7 innan någon kod skrivs.

**Föreslagen minimiarkitektur för senare (ej påbörjad):** matchlista (E6 eller E3) → för varje match-ID: `check-match` → stats-XML (E8) → lokal cache → härledning av formation och taktikprofil per motståndare över de senaste 20 matcherna.
