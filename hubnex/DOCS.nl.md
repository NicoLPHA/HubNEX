# HubNEX

*[Italiano](DOCS.md) · [English](DOCS.en.md) · Nederlands*

Het AI-hoofdkwartier voor thuis en werk: een assistent (standaard **Jarvis** genoemd) met een team
van Claude-agents, een 3D-dashboard in de zijbalk van Home Assistant, het dashboard van het huis,
een Telegram-groep, spraak en connectors voor de programma's die je op je werk gebruikt.

## Eerste start

1. Vul op het tabblad **Configuratie** minstens de **Anthropic API-sleutel** in
   (console.anthropic.com → API Keys), start de add-on en zet **Toon in zijbalk** aan.
2. Open **HubNEX** in de zijbalk: je ziet het hoofdkwartier met de assistent en zijn agents.
3. Schrijf in de chat onderaan. Voor het huis gebruikt hij al Home Assistant: je hoeft geen token
   aan te maken, de add-on loopt via de Supervisor.
4. Vertel in `agents.yaml` (hieronder) wie je bent en hoe je werkt: hoe meer hij weet, hoe nuttiger
   hij is.

**Taal**: de add-on spreekt de taal van Home Assistant (Italiaans, Nederlands, anders Engels); de
optie **Taal** kiest die met de hand. Bij de eerste start staat het voorbeeldbestand `agents.yaml` in
dezelfde taal.

Al het andere is optioneel en kun je op elk moment toevoegen, in deze voorgestelde volgorde:

| Wat | Waar | Hoofdstuk |
| --- | --- | --- |
| Je team, je bedrijf | `agents.yaml` | Het team |
| Plattegrond van het huis | Thuis → ⚙ Plattegrond | Weergave Thuis |
| Praten via Assist (app, speakers) | HubNEX-integratie + Spraakassistenten | Spraak |
| Spraak in het dashboard | optie *Stem van Home Assistant* of ElevenLabs | Spraak |
| Telegram-groep | de opties van de bots | De Telegram-groep |
| Zakelijke mailbox | IMAP/SMTP-opties | Zakelijke mailbox |
| De programma's van je werk | `connectors` in `agents.yaml` | Connectors |
| Tablet of telefoon buiten HA | HQ-token en poort | Gebruik buiten Home Assistant |

Elke optie op het tabblad **Configuratie** heeft naast het veld een uitleg.

## Het team: `agents.yaml`

Bij de eerste start wordt `agents.yaml` aangemaakt in de configuratiemap van de add-on,
`/addon_configs/<id>_hubnex/agents.yaml`. Open het met de add-on **File editor** of **Studio Code
Server**, of via Samba in de share `addon_configs`. **Start de add-on opnieuw op** na een wijziging.

- `boss`: de assistent die alles coördineert: naam, karakter, instructies, tools.
- `companies`: jouw "bedrijven" (werk, thuis, een vereniging…), met afdelingen en agents. Elke agent
  heeft een rol, instructies en de tools die hij mag gebruiken.
- `connectors`: de programma's van je werk (zie **Connectors**).
- Routines: taken die een agent op vaste tijden zelf uitvoert. Ze staan **uit** totdat je
  `enabled: true` schrijft.

Het Nederlandse voorbeeldteam is voor het **huis** (Jarvis Butler en Jarvis Wacht). Voor zakelijke
mail staat onderaan een kant-en-klaar blok **WERK** in commentaar (Jarvis Mail en Jarvis Boekhouder): haal
bij alle regels tussen `# >>> WERK` en `# <<< WERK` de eerste `# ` weg om het te gebruiken. Zonder de agent
met id `mail` zet HubNEX de mailbox uit en meldt dat in het logboek.

Laat agents weg die je niet nodig hebt: een agent is alleen nuttig als hij sensoren of gegevens heeft om
naar te kijken. Een beveiligingsagent zonder deur-, raam- of alarmsensoren heeft niets te doen.

Het voorbeeldbestand is regel voor regel van commentaar voorzien. Instructies mag je in elke taal
schrijven: de assistent antwoordt hoe dan ook in de taal van de add-on.

## Connectors: de programma's van je werk

HubNEX koppelt met de programma's die je op je werk gebruikt (boekhoudsoftware, agenda, CRM, Notion,
databases…) via **MCP** (Model Context Protocol), de open standaard om AI aan programma's te koppelen.
Veel programma's hebben al een "MCP-server", en wie er een ontwikkelt kan er een toevoegen.

In `agents.yaml`:

```yaml
connectors:
  - name: Boekhouding                   # naam die jij en de agents zien
    url: https://example.com/mcp        # adres van de MCP-server
    token: jouw-sleutel                 # als de server er een vraagt (Authorization: Bearer …)
    agents: [boss, technical]           # wie het mag gebruiken (weggelaten = iedereen; boss = de assistent)
```

HubNEX leest zelf welke tools het programma aanbiedt en geeft ze aan de genoemde agents.

- Tools die **lezen** worden vrij gebruikt.
- Tools die gegevens **wijzigen** worden niet meteen uitgevoerd: je ziet een samenvatting met
  **✅ Bevestig / ❌ Annuleer**, in de Telegram-groep en in het paneel "Ter goedkeuring" van het
  dashboard. Ze lopen pas na jouw akkoord, en maar één keer, ook als je twee keer drukt.
- Hoe het dat weet: de server geeft aan welke tools alleen-lezen zijn. Doet hij dat niet, dan zijn de
  alleen-lezen tools die waarvan de naam begint met `get`, `list`, `search`, `read`, `find`… en alle
  andere vragen om bevestiging. Je kunt dit corrigeren met `free: [naam]` (nooit vragen) en
  `always_confirm: [naam]` (altijd vragen), of met `confirm: always` voor de hele connector.
- `/stato` in de Telegram-groep laat weten of elke connector antwoordt en hoeveel tools hij
  aanbiedt; fouten verschijnen ook in de activiteit van het dashboard.

## Spraak

Je kunt op drie manieren met de assistent praten. Alles is optioneel.

**1. Assist van Home Assistant** (app, slimme speakers, wake word)

De add-on installeert zelf de **HubNEX**-integratie, waardoor de assistent een *gespreksagent* van
Assist wordt. Spraakherkenning en stem zijn van Home Assistant, met de engine van je voorkeur: Piper
(lokaal en gratis), Home Assistant Cloud, ElevenLabs, Google…

1. Start de add-on: er komt een melding. **Start Home Assistant opnieuw op**.
2. Instellingen → Apparaten & diensten: **HubNEX ontdekt** verschijnt → *Instellen* → *Verzenden*.
3. Instellingen → Spraakassistenten → je assistent → **Gespreksagent**: kies de assistent van HubNEX
   en laat **"Opdrachten bij voorkeur lokaal afhandelen"** aan staan: eenvoudige opdrachten ("doe de
   keukenlamp aan") voert Home Assistant uit, direct en zonder tegoed te gebruiken; al het andere gaat
   naar de assistent.

Als de integratie niet wordt ontdekt: Apparaten & diensten → Toevoegen → "HubNEX", met het adres van
de add-on (`http://<hostnaam van de add-on>:8765`, de hostnaam staat op de pagina van de add-on) en
het **HQ-token**. Meestal is het genoeg om de HubNEX-add-on opnieuw op te starten.

Gesproken antwoorden zijn kort (hooguit twee zinnen), in de taal die Assist spreekt. Elk verzoek,
van Assist of van het dashboard, neemt de snelst mogelijke weg:

1. **Home Assistant zelf** ("doe de keukenlamp aan"): direct, zonder AI. Assist doet dit al; het
   dashboard probeert het eerst. Stel de entiteiten beschikbaar voor Assist en geef ze een alias met
   de naam die je zegt. Sloten, het alarm en deuren gaan nooit deze weg.
2. **De snelle route** voor de andere verzoeken over het huis: het **Model voor snelle opdrachten**
   (standaard Haiku) met de lijst van entiteiten en hun toestanden al bij de hand. In de chat staat
   onder het antwoord SNEL ANTWOORD (of HOME ASSISTANT bij punt 1).
3. **Jarvis** met zijn model en al zijn instructies voor al het andere: ingewikkelde vragen, werk,
   agents, sloten en het alarm (met bevestiging).

**2. Dashboard** (microfoon en speaker in de onderste balk)

- Wat je zegt wordt herkend door de browser (gratis). Browsers staan dat alleen toe op `https://`: het
  werkt vanuit de Home Assistant-app en via Nabu Casa, niet vanaf `http://homeassistant.local`.
- De assistent antwoordt met de stem die in de configuratie is gekozen:
  - **Stem van Home Assistant**: schrijf een van de tekst-naar-spraak-engines van Home Assistant, bijv.
    `tts.piper` (lokaal, gratis) of `tts.home_assistant_cloud`. Die heeft voorrang. Bij **Stem van de
    engine van Home Assistant** kun je de stem op naam kiezen (bijv. `Colette` of `Fenna` bij Home
    Assistant Cloud): bestaat de naam niet, dan noemt de foutmelding de beschikbare stemmen. De taal is
    die van Home Assistant;
  - of **ElevenLabs**: API-sleutel (elevenlabs.io → Profile → API Keys), stem-ID (Voices → de stem →
    ID) en model (`eleven_flash_v2_5`, het goedkoopste).
- Start de stem niet, dan staat de reden onder het antwoord.
- Voordat de tekst wordt voorgelezen, wordt hij geschikt gemaakt voor luisteren: geen symbolen,
  emoji of links, eenheden en afkortingen in woorden (Ω → "ohm", kWh → "kilowattuur"), datums
  uitgeschreven, een pauze bij elk punt van een lijst. De geschreven tekst blijft zoals hij is.
- **Gesproken antwoorden**: `completa` (de stem leest het hele antwoord) of `riassunto` (samenvatting):
  bij lange antwoorden zegt de stem alleen de kern in een of twee zinnen en blijft de geschreven tekst
  compleet. Korte antwoorden worden helemaal voorgelezen. Het geldt voor het dashboard met de speaker
  aan en voor Telegram-spraakberichten; Assist antwoordt al in twee zinnen.

**3. Telegram**: stuur een spraakbericht, het wordt met ElevenLabs uitgeschreven en de assistent
antwoordt ook met spraak (`telegram_voice_replies`). Voor het uitschrijven is ElevenLabs nodig.

**Over ElevenLabs (gratis abonnement):** stemmen uit de openbare bibliotheek zijn niet via de API te
gebruiken; het account kan worden geblokkeerd wegens "ongebruikelijke activiteit", ook als er nog
tekens over zijn. In die gevallen zegt de foutmelding dat.

## De Telegram-groep

Een groep met **één bot voor de assistent** en eventueel **één voor de mailagent**. Agents zonder
eigen bot spreken via de assistent, met hun naam ervoor.

1. Maak de bots met @BotFather (`/newbot`) en zet de groepsprivacy uit (*Bot Settings → Group Privacy →
   Turn off*), voeg ze daarna toe aan een groep.
2. Zet de tokens in de configuratie, start en stuur `/id` in de groep: dat geeft het ID van de groep
   (een negatief getal, `allowed_chat_id`) en het jouwe (`allowed_user_id`). De bots negeren iedereen
   anders.

Gebruik:

- Een gewoon bericht → de assistent antwoordt, door het zelf te doen of te delegeren. De agent aan wie
  hij delegeert antwoordt rechtstreeks in de groep.
- Antwoord op een bericht van de mailagent, of schrijf `@naam_van_de_mailbot` → die antwoordt.
- Antwoord op een **concept** met wat er moet veranderen ("formeler") → de nieuwe versie komt.
- Opdrachten: `/id`, `/stato` (status), `/posta` (controleer nu de mail), `/regole` (je regels).

Een bot kan maar door één programma worden beluisterd: twee installaties met dezelfde tokens
botsen.

## Bijlagen: foto's en documenten

Je kunt de assistent en de agents **foto's, pdf's en tekstbestanden** (txt, csv, md, json) sturen:
handig bijvoorbeeld vanaf een bouwplaats.

- **Telegram**: stuur een foto, een album of een bestand, met het verzoek in het onderschrift ("kijk
  naar deze scheur: moet ik me zorgen maken?"). Of antwoord op een eerder gestuurde foto met de vraag.
  Net als bij berichten gaat het naar de assistent; voor een agent met een eigen bot antwoord je op een
  bericht van hem of schrijf je `@botnaam` in het onderschrift. Zonder tekst kijkt de assistent en
  vraagt hij wat je nodig hebt.
- **Dashboard**: de paperclip naast het chatveld (op een telefoon ook de camera); je kunt ook een
  schermafbeelding plakken of bestanden op de chat slepen. Grote foto's worden vóór het verzenden
  verkleind, om minder data te gebruiken.
- **API**: `POST /api/attachments?name=foto.jpg` met het bestand als body → `{"id": …}`; daarna
  `"attachments": ["id"]` in `/api/chat` of `/api/agents/{id}/task`.

De assistent ziet de bijlagen en geeft ze, als hij een klus delegeert, samen met de taak door aan de
agent. Het gesprek bewaart alleen een notitie met hun code (`#1a2b3c4d`): foto's worden niet bij elk
bericht opnieuw betaald, en iedereen in het team kan ze zo nodig opnieuw bekijken ("op de foto van
daarnet…").

Grenzen: 20 MB per bestand (dezelfde grens als Telegram-bots), pdf's tot 100 pagina's, 10 bijlagen per
bericht. Foto's worden gedraaid zoals ze zijn genomen en geschaald tot 1568 pixels aan de lange kant
(wat Claude toch al leest). Word- en Excel-bestanden worden niet direct gelezen: sla ze op als pdf (of
csv voor een spreadsheet). Elke foto kost ongeveer evenveel als 1.500 woorden tekst; een pdf ongeveer
1.500–3.000 per pagina. Bijlagen worden 30 dagen bewaard in `/data/allegati` en daarna verwijderd.

## Zakelijke mailbox

Stel de IMAP/SMTP van je provider in (servers, SSL-poorten 993/465, gebruiker, wachtwoord).

- Elke `check_interval_minutes` controleert hij de mailbox, sorteert de nieuwe e-mails (hoge,
  gemiddelde, lage prioriteit: `alta`, `media`, `bassa`) en meldt ze je vanaf `notify_min_priority`.
  E-mails worden niet als gelezen gemarkeerd.
- **Afzenders die niet gemeld worden** (`mail_ignore`): gescheiden door komma's, een adres
  (`aanbiedingen@winkel.nl`), een domein (`@nieuwsbrief.nl`) of een woord uit het adres (`noreply`).
  Hun e-mails blijven in de mailbox en Jarvis Mail leest ze als je erom vraagt, maar er komt geen
  Telegram-bericht en ze worden niet eens gesorteerd (geen Claude-tegoed).
- **Er gaat niets uit zonder jou**: elk antwoord is een concept met Verstuur, Bewaar in Concepten,
  Wijzig, Verwerp, op Telegram en in het dashboard.
- **Handtekening**: je kunt de HTML-handtekening uit je mailprogramma plakken.
- Zet in de instructies van de mailagent je **belangrijke klanten**: hun e-mails krijgen hoge
  prioriteit.

## Weergave Thuis

De knop **⌂ Thuis** opent het dashboard van Home Assistant. Bovenaan de **HUD**: wie er thuis is,
alarm, gemiddeld klimaat, lampen aan, energie en camera's; daaronder de scènes. Elke entiteit heeft
zijn **kaart**: lampen (tik op de kaart, helderheidsbalk; als de lamp ze heeft, opent het bolletje bij
de status kleurtemperatuur en kleuren), klimaat met een draaiknop, rolluiken met het getekende raam,
kleppen, media met hoes, voortgang, willekeurig/herhalen, volume en bron, **robotstofzuigers** met
hun kaart (waar de robot zich beweegt), status, batterij en opdrachten, stopcontacten met hun
verbruik, deuren en ramen (rood als ze open zijn, "hoe lang al"), sensoren met de grafiek van de
laatste 24 uur, personen, camera's. **Sloten** met een code in Home Assistant vragen er op een
toetsenbord om, de andere om een bevestiging in de kaart; het **alarm** schakel je uit met het
toetsenbord. De **kamers zijn de gebieden van Home Assistant**: de entiteiten van een gebied (of van
zijn apparaat) verschijnen vanzelf in de kamer.

Rond de plattegrond, in één oogopslag:

- **Weer** in de HUD: toestand, temperatuur, min/max en regen; met een tik opent de verwachting voor de
  komende dagen, met luchtvochtigheid en wind. Het gebruikt de entiteit `weather.*` van Home Assistant.
- **Vandaag en de komende dagen**: jouw deadlines en die van de agents in de komende 7 dagen, met een
  vinkje om ze af te sluiten. Alleen jij ziet dit: Home Assistant-gebruikers met alleen toegang tot het
  huis niet.
- **Op de plattegrond**, onder de naam van de kamer: een persoon waar aanwezigheid of beweging is, een
  noot waar iets speelt, de robot waar hij schoonmaakt, een wasmachine waar de wasmachine of
  vaatwasser draait.
- **Huishoudelijke apparaten**: wasmachine, vaatwasser, droger, oven en waterkoker op een stopcontact
  dat het vermogen meet (herkend aan de naam): "in bedrijf" en, 3 uur lang, "klaar … geleden".
- **Recente gebeurtenissen**: de laatste wijzigingen in de afgelopen 24 uur van deuren, ramen, sloten,
  alarm en personen.

**Voorraden (pellets en dergelijke).** Een *Getal*-helper of *Teller* van Home Assistant met "pellet",
"zakken" of "voorraad" in de naam wordt een kaart **Voorraad**; voor andere kies je "Voorraad" als type bij
het wijzigen van de kamer. Hij toont hoeveel er over zijn, hoeveel er per dag opgaan en de laatste
levering (uit de laatste 30 dagen geschiedenis), de **resterende dagen**; **−1 geladen** als je er een
gebruikt, **+levering** als de pellets binnenkomen. Kies bij **Instellingen** hoeveel er in een levering
zitten en onder hoeveel je gewaarschuwd wilt worden: dan wordt de kaart rood en komt de melding
**Voorraden om bij te bestellen** (een regel bij de meldingen van het huis).

**Vrije kaart.** Met **Kamer wijzigen → + Vrije kaart** bouw je een kaart uit blokken op een raster van
4 kolommen (2 op een telefoon). Blokken: **grote waarde**, **ringmeter**, **schakelaar**, **knop**
(scène, script, knop), **schuif** (helderheid of een getal), **grafiek** van de laatste 24 uur, **balk**,
**tijdvak** (een begin- en eindtijd), **keuzelijst**, **status** (hoe het is en sinds wanneer) en
**tekst**. Kies bij elk blok de entiteit (de zoekfunctie biedt alleen de geschikte aan), een label, de
grootte (1×1 tot 4×2) en, bij ring en balk, minimum en maximum; **Voor/Na** verplaatsen het. De kaart
heeft een naam, een kleur en een stijl (**Strak**, de standaard: de blokken direct op de kaart;
**Vakken**: elk in een eigen vak); in het midden van de editor zie je het voorbeeld met de echte
waarden. **Wijzig** opent hem opnieuw.

Meer blokken: **media** (hoes, titel, bediening en volume), **camera** (live; een tik opent hem groot)
en **Vraag aan Jarvis** (een kant-en-klare vraag: een tik stuurt hem naar de chat). Bij elk blok kun je
ook instellen:

- **Kleur volgens de waarde**: maximaal 4 regels, bijv. "boven 23 → rood", "onder 19 → blauw",
  "gelijk aan open → oranje";
- **Toon alleen als**: het blok verschijnt alleen zolang een entiteit een bepaalde waarde heeft (bijv.
  de tv "gelijk aan playing"); in de editor blijft het zichtbaar, gedimd;
- **Bij aantikken**: aan/uit zetten, een scène of script starten, Jarvis vragen, een andere kamer openen.

De waarden zijn die van Home Assistant: `on`, `off`, `open`, `playing`… of een getal. Om snel te
beginnen zijn er **sjablonen** (Kachel, Hal, Wasruimte, Kamerklimaat, Energie, Muziek), die de geschikte
entiteiten van de kamer overnemen; blokken kun je ook **slepen**.

De **lijn bovenaan** elke kaart (vrij of samengesteld) licht vanzelf op: amber zolang iets aan staat of
een sensor iets detecteert, rood bij een alarm (deur of raam open, water, rook, gas). Bij een kaart met
een hoofdschakelaar, zoals de kachel, beslist die schakelaar; de kleurregels die je met de hand instelt
komen daar bovenop.

**Beschrijf het aan Jarvis**: schrijf bovenaan de editor wat je wilt ("de kachel met temperatuur,
aan/uit, tijden en pellets; rood boven 23 graden") en tik op **Maak**: Jarvis stelt de kaart samen met de
echte entiteiten van het huis (verzonnen entiteiten worden weggelaten) en opent hem in de editor, om te
controleren en op te slaan. Het is één Claude-verzoek, een paar cent. Dit gebruikt het model van Jarvis;
bij een ander model dan Claude moet dat gestructureerde uitvoer ondersteunen.

**Kaart exporteren / importeren**: **Exporteer** kopieert de kaart als tekst, om te delen; **Kamer
wijzigen → Kaart importeren** plakt hem in een ander huis, en blokken waarvan de entiteiten er niet zijn
blijven leeg om te kiezen. Bij voorwaarden en regels met "gelijk aan" en "ongelijk aan" kies je de
waarde uit een lijst (on/off, open/closed, playing…).

**Entiteiten toevoegen.** Met **Kamer wijzigen → Entiteit toevoegen** kun je elke entiteit van Home
Assistant in een kamer zetten, ook een zonder gebied of van een soort die HubNEX niet tekent (hij toont
de status). Helpers ontstaan zonder gebied: stel dat in bij Home Assistant of voeg ze hier toe.

- **Plattegrond**: **⚙ Plattegrond** opent de editor.
  1. **Plattegrond uploaden**: een foto of pdf van de plattegrond (witte randen worden automatisch
     weggesneden). Hij blijft alleen in de map van de add-on.
  2. **Kamers voorstellen**: Claude bekijkt de plattegrond en stelt de kamers voor, al gekoppeld aan
     de gebieden van Home Assistant als de naam overeenkomt (één verzoek, een paar cent).
  3. Corrigeer met de hand: sleep een kamer om hem te verplaatsen, de rechteronderhoek om hem te
     schalen, sleep over lege ruimte (of **+ Kamer**) om een nieuwe te tekenen. Kies in het paneel het
     gebied, of "alleen tekening" voor een ruimte zonder entiteiten; **omtrek** voor balkons en
     terrassen. Vink de gebieden **Buitenshuis** aan (tuin, parkeerplaats…).
  4. **Plattegrond opslaan**. Met **+ Verdieping** voeg je meer verdiepingen toe.

  Als je liever wilt, kun je met **Tekst** de indeling in YAML schrijven (posities `x, y, w, h` in
  procenten van de tekening); optioneel `energy: { power: sensor.…, today: sensor.… }`. Alles komt in
  `casa.yaml` in de map van de add-on; zonder plattegrond verschijnen de gebieden als tegels.
  ```yaml
  floors:
    - name: Begane grond
      aspect: 1.2          # breedte / hoogte van de tekening
      rooms:
        - { area: Woonkamer, x: 0, y: 0, w: 50, h: 60 }
        - { area: Keuken, x: 50, y: 0, w: 50, h: 60 }
        - { area: Slaapkamer, x: 0, y: 60, w: 100, h: 40 }
  outside: [Tuin]
  ```
- **Namen**: als je een entiteit in Home Assistant **aliassen** hebt gegeven (entiteitsinstellingen →
  Aliassen), toont HubNEX de eerste; anders de naam van Home Assistant. Bij het zoeken naar entiteiten
  om toe te voegen tellen alle namen mee.
- **Energie**: tik op "Energie" in de HUD: er opent een venster. Drie weergaven, één of meer: **de
  reactor** (de periode verdeeld per tarief rond het vermogen nu, in % van de meter), **de dag** (het
  vermogen van vandaag, over de tarieven als die er zijn) en **de energierekening** (kosten, schatting
  voor het einde van de periode in het huidige tempo, vergelijking met de vorige periode). Kies met
  **Instellen** de weergaven en je sensoren: de tariefperiode (**één tarief**, je eigen sensor met
  de status F1/F2/F3, of de Italiaanse ARERA-kalender die HubNEX berekent), de kWh van de periode
  (bijv. de "utility meters" van Home Assistant: het begin van de periode en de vergelijking komen
  daar vandaan), prijzen of kosten, het vermogen en de grootte van de meter, overige waarden
  (spanning, arbeidsfactor…). Geen enkele berekening gebruikt AI. Voor Nederland is **één tarief**
  de logische keuze, eventueel met een eigen sensor voor dal- en normaaltarief.
- **Personen**: de personen van Home Assistant (Instellingen → Personen, met de telefoon-app of een
  tracker) staan bovenaan de weergave Thuis: *thuis*, *weg* of de naam van de zone waarin ze zijn.
- **Tijden en instellingen**: de helpers van Home Assistant kun je gebruiken in de weergave Thuis. Een
  tijd (`input_datetime`, `time`) wijzig je door op de tijd te tikken of met −15 / +15; getallen met de
  schuif, lijsten door de optie te kiezen, teksten door te schrijven. Home Assistant slaat de waarde
  op en je automatiseringen gebruiken hem zoals eerder.
- **Eigen kaarten**: geef in *Kamer wijzigen* → **+ Nieuwe kaart** een naam, voeg entiteiten toe (ook
  uit andere kamers), orden ze, kies de **groep** (Klimaat, Lampen…; standaard die van de eerste
  entiteit) en klein of breed. Voorbeeld: een kaart "Kachel" met zijn aan- en uit-tijden toont ook het
  tarief over de dag en "aan tot 22:00"; staat de schakelaar die de tijden inschakelt in de kaart
  (bijv. "automatisch", gekozen in de editor), dan zegt de kaart bij uit "tijden niet actief".
  Numerieke sensoren tonen de grafiek van de laatste 24 uur: schakel die in de editor uit met de
  schakelaar "grafiek", bij losse kaarten met "Verberg grafiek" tijdens het bewerken. Tijdens het
  bewerken verplaatst elke kaart zich binnen zijn groep (slepen ⋮⋮ of met ‹ ›), kan hij alleen in
  HubNEX worden hernoemd, breed of klein gemaakt, verwijderd; *Automatische volgorde* herstelt de
  oorspronkelijke volgorde. Alles blijft in HubNEX: er verandert niets in Home Assistant.
- **Kamer**: tik erop voor de snelle kaart, **Kamer openen** voor al zijn entiteiten gegroepeerd per
  type. Bij meerdere temperatuursensoren kies je welke gebruikt wordt ("temperatuur van").
- **Kamer wijzigen**: voeg **elke entiteit** van Home Assistant toe (ook die Home Assistant verbergt,
  zoals spelers die Music Assistant verbergt), waarbij het gebied ook in Home Assistant wordt
  verplaatst (aanbevolen) of alleen in het dashboard; **Verwijder** verbergt hem alleen van het
  dashboard; **Toon als** verandert het type (Licht, Stopcontact / schakelaar, Poort / deur met een
  impuls, Sirene, Alleen status). Voor een relais dat een lamp voedt is "Toon als → Licht" in de
  instellingen van de entiteit in Home Assistant nog beter: Assist en de assistent behandelen het dan
  ook als lamp.
- **Media**: aan en uit, ▶ / ❚❚ en volume.
- **Camera's**: de miniaturen in de kamers zijn **live** (maximaal 3 tegelijk, de andere verversen elke
  5 seconden); tikken op een miniatuur opent hem groot, meteen live, en binnen Home Assistant schakelt
  hij over op zijn video van hoge kwaliteit. In een **samengestelde kaart** met een camera en zijn
  sensoren (een voertuig, een persoon, beweging) staan de sensoren over het beeld en lichten ze rood op
  als ze afgaan. De knop **Camera's** bovenaan toont ze allemaal.
- **Alarm**: een knop bovenaan met zijn status; Thuis / Weg / Nacht en Uitschakelen met een
  toetsenbord voor de code.
- De opdrachten van de weergave Thuis gaan rechtstreeks naar Home Assistant en **gebruiken geen
  Claude-tegoed**.

## Meldingen van het huis

HubNEX bewaakt het huis zelf en waarschuwt je als er iets niet klopt. **Het gebruikt Claude niet**: het
zijn vaste regels op de toestanden van Home Assistant, dus de waarschuwingen komen direct en kosten
niets. Stel ze in via ⚙ Voorkeuren → **Meldingen van het huis**.

| Regel | Wanneer hij waarschuwt |
|---|---|
| Lekkages, rook, gas | Een water-, rook-, gas- of koolmonoxidesensor gaat af: direct, ook tijdens de stille uren |
| Ramen open | Een raam blijft open terwijl de verwarming of de airco aan staat, of terwijl het regent |
| Niemand thuis | Iedereen is weg en een deur, de poort of een slot staat open. Knop **Sluiten** |
| Hoog verbruik | Het vermogen van het huis (de sensor die bij Energie is gekozen) blijft boven de drempel |
| Lampen aan in de nacht | Lampen staan nog aan in de nachtelijke uren (standaard 23:30–06:00). Knop **Zet uit** |
| Lege batterijen | Sensoren met een batterij onder 15% |
| Apparaten niet bereikbaar | Apparaten die al meer dan een uur niet hebben gereageerd |

**Waar ze aankomen**, per regel:

- de Home Assistant-**app** op je telefoon: een pushmelding met de knoppen. HubNEX vindt de telefoons
  met de app zelf; je kunt er een paar uitsluiten. Dringende waarschuwingen komen met hoge prioriteit.
- **Telegram**, in de groep van Jarvis, met dezelfde knoppen.
- **Home Assistant**: de meldingen onder het belletje.
- **Speakers** (Sonos, Google…): de melding wordt hardop voorgelezen via de tekst-naar-spraak van Home
  Assistant. Dit staat **standaard uit**. Zet het aan bij ⚙ Voorkeuren → **Meldingen van het huis** →
  **Gesproken meldingen**, kies de speakers (alle `media_player`-entiteiten van Home Assistant worden
  getoond), eventueel de spraakengine en een volume. Daarna kies je per regel of hij ook spreekt
  (knop **Speaker** naast App, Telegram en Home Assistant): standaard alleen
  **Lekkages, rook, gas**. De schakelaar bovenaan zet alle gesproken meldingen in één keer aan of uit,
  en **Stuur een test** laat ze horen. Het volume wordt vóór het bericht ingesteld en daarna **niet**
  teruggezet; laat het op 0 om het volume van de speaker ongemoeid te laten. De stille uren gelden ook
  voor de speakers, behalve bij lekkages, rook en gas. Zonder spraakengine (optie **Stem van Home
  Assistant** of een TTS-integratie zoals Piper of Home Assistant Cloud) is er niets om voor te lezen.

Hoe ze zich gedragen:

- elke regel wacht tot het probleem een paar minuten duurt (jij kiest hoeveel), zodat een raam dat
  even open stond je niet lastigvalt;
- hij waarschuwt **één keer** per probleem; komt er intussen een ander bij (een tweede raam), dan
  werkt hij de waarschuwing bij;
- als het probleem is opgelost, **verdwijnt** de melding op de telefoon en onder het belletje **vanzelf**
  en verdwijnen op Telegram de knoppen;
- in de **stille uren** wachten waarschuwingen tot het einde van het blok (behalve lekkages, rook en
  gas);
- **hij onderneemt alleen actie als je op een knop in de melding drukt**. Zonder jouw tik verandert er
  niets.

Bij elke regel somt «Bewaakt N van N» de entiteiten op waar hij naar kijkt: vink die uit om ze te
negeren (bijvoorbeeld een bodemvochtsensor die als waterlek wordt gezien). **Stuur een test** stuurt
een melding op elk gebruikt kanaal.

## Neurale kaart

De knop **✺ Kaart** toont de "geest" van het team in 3D: de assistent in het midden, bedrijven,
afdelingen en agents, en eromheen alles wat het team weet (herinneringen, taken, deadlines, concepten),
gekoppeld aan wie het heeft gemaakt en aan de trefwoorden die ze delen. Zoek een naam om alles
erover te markeren.

## Geen initiatief zonder jouw opdracht

- Routines staan uit totdat je `enabled: true` schrijft. Zelfs als ze aan staan, **kunnen ze niets in
  huis veranderen**, en hetzelfde geldt voor gebeurtenissen van automatiseringen: ze kijken en
  schrijven je wat ze voorstellen.
- Agents doen alleen de taak die ze hebben gekregen; de rest stellen ze voor.
- Wijzigingen in gekoppelde programma's en e-mails gaan pas uit na jouw bevestiging.
- **Jouw regels**: als je de assistent iets zegt dat altijd moet gelden ("doe nooit…", "vanaf nu…"),
  slaat hij het op als regel voor het **hele** team. `/regole` toont ze.

## Gebruik buiten Home Assistant

**Met Nabu Casa** (aanbevolen): open HubNEX in de zijbalk, kopieer het adres en voeg het toe aan het
beginscherm van de telefoon.

**Alleen lokaal netwerk**: stel een **HQ-token** in, schrijf `8765` bij de poort (Configuratie →
Netwerk), start opnieuw op en open `http://IP-VAN-HOME-ASSISTANT:8765`. Je kunt het als app
installeren via het menu van de browser.

**Open HubNEX zodra Home Assistant start**: binnen Home Assistant, bovenaan **⚙** → de schakelaar. Het
geldt alleen voor jouw account; de andere gebruikers houden hun dashboard.

**Taal**: het dashboard is in het Italiaans, Nederlands of Engels, volgens de Home Assistant-taal van
wie het opent (andere talen = Engels). Bovenaan kiest **⚙ → Taal** hem met de hand, alleen voor die
browser. Jarvis, de agents, Telegram en de berichten van de add-on volgen de optie **Taal** van de
configuratie (auto = die van Home Assistant).

**Alleen Thuis, voor wie alleen een lamp wil aandoen**: bovenaan **⚙** → zet **Tabbladen HQ en Kaart**
uit (HubNEX opent direct op de weergave Thuis) en/of **AI-assistent** (chat, spraak en goedkeuringen
verdwijnen: geen Claude-tegoed). Binnen Home Assistant wordt de keuze bewaard bij het account van wie
is ingelogd en geldt hij op al zijn apparaten; daarbuiten blijft hij in de browser. Het is een gemak,
geen slot: iedereen kan ze via hetzelfde menu weer aanzetten.

**Gebruikers zonder beheerdersrechten**: HubNEX staat in de zijbalk van **alle** gebruikers van Home
Assistant. Wie geen beheerder is, krijgt alleen de weergave **Thuis**: lampen, klimaat, rolluiken,
scènes, camera's en alarm (met de code), zoals in Home Assistant. Zij zien de assistent, mail, agents,
activiteit of kosten niet en kunnen de plattegrond of de kamers niet wijzigen. De add-on controleert dat
bij elk verzoek, niet alleen in de interface. Om ze alles te geven: optie **Gebruikers zonder
beheerdersrechten → completo** (volledig).

## Gebeurtenissen van automatiseringen

Automatiseringen kunnen een gebeurtenis aan de assistent doorgeven, die je schrijft wat hij voorstelt.
Met een **HQ-token**, in `configuration.yaml`:

```yaml
rest_command:
  hubnex_event:
    url: "http://<hostnaam van de add-on>:8765/api/ha/event"
    method: POST
    headers:
      Authorization: "Bearer JOUW_HQ_TOKEN"
    content_type: "application/json"
    payload: '{"message": "{{ message }}"}'
```

## Beveiliging

- Vanuit de zijbalk kom alleen jij binnen, via de login van Home Assistant.
- Poort 8765 is standaard dicht; als je hem opent, is het **HQ-token** nodig.
- De diensten bij **Geblokkeerde HA-diensten** (sloten, het alarm uitschakelen) roept de assistent
  nooit zelf aan; vanuit het dashboard kun je dat wel doen, met een bevestiging of de code.
- De sleutels staan alleen in de configuratie van de add-on en in `agents.yaml`, op je Home Assistant.

**Goed om te weten (beperkingen):**

- **De blokkade werkt op de exacte naam van de dienst** (`lock.unlock`, `lock.open`,
  `alarm_control_panel.alarm_disarm`). Een script, scène of automatisering in Home Assistant die iets
  ontgrendelt, valt er dus niet onder. De assistent mag scripts wel starten (`script.turn_on`).
  Voeg gevoelige diensten toe aan **Geblokkeerde HA-diensten**, bijvoorbeeld `cover.open_cover` als je
  een garagedeur of poort als `cover` hebt, en geef in de assistent geen scripts door die sloten
  bedienen. Opdrachten over deuren, sloten en het alarm worden bovendien
  herkend aan trefwoorden (Italiaans, Nederlands en Engels) en gaan niet via de snelle route maar via
  Jarvis, die om bevestiging vraagt. Dat is een vangnet op woorden, geen garantie: een omschrijving
  zonder die woorden kan erdoorheen glippen.
- **Wat de assistent leest, zijn gegevens, geen opdrachten** (e-mails, websites, bijlagen), en dat
  staat ook in zijn instructies. Een slimme afzender kan zo'n instructie toch proberen te verstoppen.
  Daarom hebben de standaardagents de taken verdeeld: de mailagent heeft geen toegang tot Home
  Assistant, en e-mails gaan alleen uit na jouw goedkeuring. Geef een agent die mail of het web leest
  niet ook `ha_call_service`.
- **Privacy:** je berichten, bijlagen en de toestand van de apparaten die de assistent nodig heeft
  gaan naar de Anthropic API; spraakberichten naar ElevenLabs, en alle Telegram-berichten via
  Telegram. Een volledig lokale opstelling is dit dus niet.
- De add-on mag de hele configuratiemap van Home Assistant beschrijven (alleen om de Assist-integratie
  in `custom_components/hubnex` te installeren). Zet **Assist-integratie** uit als je dat liever zelf
  doet.
- De back-up bevat `agents.yaml` en dus ook eventuele MCP-tokens: bewaar hem als een wachtwoord.

## Andere AI-aanbieders: OpenAI en lokale modellen

Claude blijft de aanbevolen keuze, maar Jarvis en elke agent kunnen ook **OpenAI** of een **lokaal
model** (Ollama, LM Studio) gebruiken, gratis en zonder cloud. Je kiest het model op naam, met het
voorvoegsel van de aanbieder:

| Schrijf | Aanbieder | In te vullen opties |
|---|---|---|
| `claude-sonnet-5-5` | Anthropic (zoals eerder) | Anthropic API-sleutel |
| `openai:gpt-5-mini` | OpenAI | OpenAI API-sleutel |
| `ollama:qwen3:14b` | Ollama, op je computer of server | Ollama-adres, bijv. `http://192.168.1.20:11434` |
| `compat:modelnaam` | Elke OpenAI-compatibele dienst: LM Studio, OpenRouter, Gemini, Mistral, DeepSeek, Groq | Adres (tot `/v1`) en, indien nodig, sleutel |

Schrijf het bij **Model van Jarvis**, **Model van Jarvis Mail** en **Model voor snelle opdrachten**, of
voor één agent in `agents.yaml` met `model: ollama:qwen3:14b`. Je kunt ze combineren: bijvoorbeeld
Jarvis op Claude en de mail op een gratis lokaal model. Gebruik je alleen andere aanbieders, dan mag de
Anthropic-sleutel leeg blijven.

Adressen voor `compat`, bijvoorbeeld:

- LM Studio: `http://PC-IP:1234/v1`
- OpenRouter: `https://openrouter.ai/api/v1` (modellen zoals `compat:openai/gpt-5-mini`)
- Gemini: `https://generativelanguage.googleapis.com/v1beta/openai` (modellen zoals `compat:gemini-2.5-flash`)

**Wat verandert ten opzichte van Claude**

- **Zoeken op het web** bestaat alleen met Claude. **Een pagina lezen** vanaf een link (`web_fetch`)
  doet HubNEX zelf en werkt met alle modellen, alleen voor openbare adressen.
- **Foto's** komen aan bij de modellen die ze kunnen zien; **pdf's** komen aan als tekst.
- De **gedachten** van Jarvis in de 3D-weergave verschijnen alleen met Claude.
- **Uitgaven**: Ollama-modellen kosten niets. Voor `openai`- en `compat`-modellen vul je de
  catalogusprijs in bij **Invoer-/uitvoerprijs van andere modellen** ($ per miljoen tokens), anders
  worden ze niet meegeteld. Het **Anthropic-tegoed** telt alleen de aanroepen van Claude af.
- **Kwaliteit**: Jarvis gebruikt veel tools (huis, geheugen, team). Kleine lokale modellen gebruiken ze
  slechter: voor echt gebruik heb je modellen van minstens 14 miljard parameters nodig die tools
  ondersteunen (qwen3, llama3.1, mistral-small). Geef kleinere modellen alleen eenvoudige agents, zoals
  de mail.
- **Privacy en veiligheid**: de prompts, de toestand van je huis en bijlagen gaan naar de gekozen
  aanbieder (bij Ollama op je eigen netwerk blijft het lokaal). Zwakkere modellen laten zich
  gemakkelijker door tekst in mail of webpagina's sturen: geef een agent met een klein model dan nooit
  `ha_call_service`.

## Anthropic-tegoed

De tegel **Claude-tegoed** is een **schatting**: schrijf in `anthropic_credit_usd` het saldo dat je ziet
op console.anthropic.com → Billing en HubNEX trekt de kosten van elk verzoek ervan af. Onder de $1
krijg je een waarschuwing. Met `0` zie je alleen hoeveel je hebt uitgegeven.

### Uitgavengeschiedenis

Klik in HQ op de tegel **Uitgaven/tegoed Claude** (op de telefoon: ⚙ Voorkeuren → **Uitgaven Claude**)
om de geschiedenis te openen:

- **vandaag**, **deze maand** en de **schatting voor het einde van de maand**, gebaseerd op het
  tempo van de afgelopen dagen;
- één balk per dag over de laatste 7, 30 of 90 dagen (wijs aan voor het bedrag en de aanroepen);
- de uitgaven **per agent** (Jarvis, Jarvis Mail, de agents van het team, het plattegrondvoorstel) en
  **per model** (Sonnet, Haiku…), met aanroepen en tokens.

Met `monthly_budget_usd` stel je een maandbudget in: bij 80% en 100% krijg je een waarschuwing in de
Telegram-groep en in de meldingen van Home Assistant, en toont het venster de budgetbalk. Het is
alleen een waarschuwing: HubNEX stopt niet. De geschiedenis begint zodra je deze versie installeert en
zit in de back-up.

De bedragen zijn de schatting van HubNEX tegen catalogusprijzen voor elke aanroep: de exacte rekening
staat op console.anthropic.com.

Om weinig uit te geven: de mailagent gebruikt het goedkope model; bij Assist voert Home Assistant
eenvoudige opdrachten uit; routines en zoekopdrachten op het web kosten tegoed, gebruik ze als het
nodig is. Stel in `agents.yaml`, voor Jarvis en voor elke agent, in:

- `effort: medium` in plaats van `high`: hij redeneert nog steeds, maar korter;
- `max_searches: 3`: hooguit 3 zoekopdrachten op het web per verzoek in plaats van 5. Elke zoekopdracht
  brengt resultaatpagina's binnen, die bij elke stap opnieuw worden gelezen;
- sluit het gesprek (×) als je in de chat van onderwerp verandert: nieuwe vragen slepen dan de laatste
  uitwisselingen niet mee.

## Gegevens en back-up

Geheugen, deadlines, concepten, regels en geschiedenis staan in `/data/hubnex.db`; `agents.yaml` en
`casa.yaml` in de configuratiemap van de add-on. Ze zitten allemaal in de back-ups van Home Assistant.

### HubNEX-back-up en verhuizen naar een andere installatie

**⚙ Voorkeuren → Back-up → Download** geeft je één `.zip`-bestand met alles wat HubNEX weet:
geheugen en neurale kaart, deadlines, chat, instellingen van de weergave Thuis (kaarten, namen,
volgorde, energie), de plattegrond met zijn afbeeldingen en `agents.yaml`. De opties van de add-on
(Anthropic-sleutel, Telegram, mail) zitten er **niet** in; `agents.yaml` wel, met eventuele tokens van
MCP-connectors: bewaar het bestand als een wachtwoord. Alleen voor beheerders.

**Herstel → Uploaden…** op een andere installatie zet alles op zijn plaats en start HubNEX opnieuw op.
De bestanden die het vervangt, blijven ernaast staan met het achtervoegsel `.prima-del-ripristino`.

Verhuizen van een lokale kopie (`/addons/local`) naar de add-on uit de repository:

1. In de lokale kopie: **Voorkeuren → Back-up → Download**.
2. Op de pagina van de lokale add-on: **Configuratie → ⋮ → Bewerken in YAML**, kopieer alles (je
   opties en sleutels) en **stop** de lokale add-on.
3. Installeer HubNEX uit de repository, open **Configuratie → ⋮ → Bewerken in YAML**, plak, sla op
   en start.
4. Open HubNEX: **Voorkeuren → Herstel → Uploaden…** en kies de back-up. HubNEX start opnieuw op met
   je gegevens.
5. Assist: verwijder in **Apparaten & diensten** de oude HubNEX-integratie en **start daarna de
   HubNEX-add-on opnieuw op**: "HubNEX ontdekt" verschijnt, druk op *Instellen* (geen token invullen).
6. Als alles werkt, verwijder je de lokale add-on.
