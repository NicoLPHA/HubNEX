# HubNEX

Il quartier generale AI per casa e lavoro: un assistente (di serie si chiama **Jarvis**) con il
suo team di agenti Claude, una dashboard 3D nella barra laterale di Home Assistant, la plancia
della casa, il gruppo Telegram, la voce e i connettori per i programmi del tuo lavoro.

## Primo avvio

1. Nella scheda **Configurazione** inserisci almeno la **chiave API Anthropic**
   (console.anthropic.com → API Keys), avvia l'add-on e attiva **Mostra nella barra laterale**.
2. Apri **HubNEX** dalla barra laterale: vedi il quartier generale con l'assistente e gli agenti.
3. Scrivigli nella chat in basso. Per la casa usa già Home Assistant: non serve creare token,
   l'add-on accede tramite il Supervisor.
4. Racconta chi sei e come lavori in `agents.yaml` (sotto): più sa, più è utile.

Tutto il resto è facoltativo e si aggiunge quando vuoi, in quest'ordine consigliato:

| Cosa | Dove | Sezione |
| --- | --- | --- |
| Il tuo team, la tua azienda | `agents.yaml` | Il team |
| Piantina della casa | Casa → ⚙ Piantina | Vista Casa |
| Parlare con Assist (app, speaker) | integrazione HubNEX + Assistenti vocali | Voce |
| Voce nella dashboard | opzione *Voce da Home Assistant* o ElevenLabs | Voce |
| Gruppo Telegram | opzioni dei bot | Il gruppo Telegram |
| Posta di lavoro | opzioni IMAP/SMTP | Posta di lavoro |
| I programmi del lavoro | `connectors` in `agents.yaml` | Connettori |
| Tablet o telefono fuori da HA | Token HQ e porta | Usarla fuori da Home Assistant |

Ogni opzione della scheda **Configurazione** ha la sua spiegazione accanto al campo.

## Il team: `agents.yaml`

Al primo avvio viene creato `agents.yaml` nella cartella di configurazione dell'add-on,
`/addon_configs/<id>_hubnex/agents.yaml`. Lo apri con l'add-on **File editor** o **Studio Code
Server**, oppure via Samba nella condivisione `addon_configs`. Dopo una modifica **riavvia
l'add-on**.

- `boss`: l'assistente che coordina tutto: nome, carattere, istruzioni, strumenti.
- `companies`: le tue "aziende" (il lavoro, la casa, un'associazione…), con reparti e agenti.
  Ogni agente ha un ruolo, istruzioni e gli strumenti che può usare.
- `connectors`: i programmi del tuo lavoro (vedi **Connettori**).
- Routine: compiti che un agente fa da solo a orari fissi. Sono **spente** finché non scrivi
  `enabled: true`.

Il file d'esempio è commentato riga per riga.

## Connettori: i programmi del tuo lavoro

HubNEX si collega ai programmi che usi al lavoro (gestionale, calendario, CRM, Notion,
database…) tramite **MCP** (Model Context Protocol), lo standard aperto per collegare le AI ai
programmi. Molti software hanno già un "server MCP", e chi sviluppa un gestionale può
aggiungerne uno.

In `agents.yaml`:

```yaml
connectors:
  - name: Gestionale                    # nome mostrato a te e agli agenti
    url: https://esempio.it/mcp         # indirizzo del server MCP
    token: la-tua-chiave                # se il server la chiede (Authorization: Bearer …)
    agents: [boss, tecnico]             # chi lo può usare (omesso = tutti; boss = l'assistente)
```

HubNEX legge da solo quali strumenti offre il programma e li dà agli agenti indicati.

- Gli strumenti che **leggono** li usano liberamente.
- Quelli che **modificano** i dati non partono subito: ti vengono mostrati con un riepilogo e
  **✅ Conferma / ❌ Annulla**, nel gruppo Telegram e nel pannello "Da approvare" della
  dashboard. Partono solo dopo il tuo ok, una volta sola anche se premi due volte.
- Come lo capisce: il server dichiara quali strumenti sono di sola lettura. Se non lo dichiara,
  sono di sola lettura quelli che iniziano con `get`, `list`, `search`, `read`, `find`… e tutti
  gli altri chiedono conferma. Puoi correggere con `free: [nome]` (mai conferma) e
  `always_confirm: [nome]` (sempre), oppure `confirm: always` per l'intero connettore.
- `/stato` nel gruppo Telegram dice se ogni connettore risponde e quanti strumenti offre; gli
  errori compaiono anche nell'attività della dashboard.

## Voce

Puoi parlare con l'assistente in tre modi. Tutti sono facoltativi.

**1. Assist di Home Assistant** (app, smart speaker, parola di attivazione)

L'add-on installa da solo l'integrazione **HubNEX**, che rende l'assistente un *agente di
conversazione* di Assist. Il riconoscimento e la voce li fa Home Assistant, con il motore che
preferisci: Piper (locale e gratuito), Home Assistant Cloud, ElevenLabs, Google…

1. Avvia l'add-on: arriva una notifica. **Riavvia Home Assistant**.
2. Impostazioni → Dispositivi e servizi: compare **HubNEX rilevato** → *Configura* → *Invia*.
3. Impostazioni → Assistenti vocali → il tuo assistente → **Agente di conversazione**: scegli
   l'assistente di HubNEX e lascia attivo **"Preferisci gestire i comandi localmente"**: i
   comandi semplici ("accendi la luce della cucina") li esegue Home Assistant, subito e senza
   consumare credito; tutto il resto va all'assistente.

Le risposte a voce sono brevi (al massimo due frasi). Ogni richiesta, da Assist o dalla
dashboard, segue la strada più veloce possibile:

1. **Home Assistant da solo** ("accendi la luce della cucina"): istantaneo, senza AI. Assist lo
   fa già; la dashboard lo prova per prima. Esponi le entità ad Assist e dai loro un alias con
   il nome che pronunci. Serrature, allarme e porte non passano mai di qui.
2. **La via rapida** per le altre richieste sulla casa: il **Modello per i comandi rapidi** (di
   serie Haiku) con l'elenco delle entità e del loro stato già in mano. Nella chat, sotto la
   risposta, compare la scritta RISPOSTA RAPIDA (o HOME ASSISTANT per il punto 1).
3. **Jarvis** con il suo modello e tutte le istruzioni per tutto il resto: domande complesse,
   lavoro, agenti, serrature e allarme (con la conferma). Se l'integrazione non viene rilevata:
Dispositivi e servizi → Aggiungi → "HubNEX", con l'indirizzo dell'add-on (`http://<hostname
dell'add-on>:8765`, l'hostname è nella pagina dell'add-on) e il **Token HQ**.

**2. Dashboard** (microfono e altoparlante nella barra in basso)

- Quello che dici lo riconosce il browser (gratis). I browser lo permettono solo su `https://`:
  funziona dall'app di Home Assistant e da Nabu Casa, non da `http://homeassistant.local`.
- L'assistente risponde con la voce scelta nella configurazione:
  - **Voce da Home Assistant**: scrivi un motore di sintesi vocale di Home Assistant, per
    esempio `tts.piper` (locale, gratuito) o `tts.home_assistant_cloud`. Ha la precedenza.
    In **Voce del motore di Home Assistant** puoi scegliere la voce per nome (per esempio
    `Rinaldo` o `Diego` con Home Assistant Cloud): se il nome non esiste, il messaggio d'errore
    elenca quelle disponibili. La lingua è quella di Home Assistant;
  - oppure **ElevenLabs**: chiave API (elevenlabs.io → Profilo → API Keys), ID della voce
    (Voices → la voce → ID) e modello (`eleven_flash_v2_5`, il più economico, parla italiano).
- Se la voce non parte, sotto la risposta compare il motivo.
- Prima di leggere, il testo viene preparato per l'ascolto: niente simboli, emoji o link,
  unità e sigle in parole (Ω → "ohm", kW → "chilowatt", MT/BT → "media e bassa tensione"),
  date per esteso, una pausa per ogni punto di un elenco. Lo scritto resta com'è.
- **Risposte a voce**: `completa` (la voce legge tutta la risposta) oppure `riassunto`: per le
  risposte lunghe la voce dice solo il succo in una o due frasi e il testo scritto resta
  completo. Le risposte brevi vengono lette per intero. Vale per la dashboard con
  l'altoparlante acceso e per i vocali di Telegram; Assist risponde già in due frasi.

**3. Telegram**: mandi un vocale, viene trascritto con ElevenLabs e l'assistente risponde anche
a voce (`telegram_voice_replies`). La trascrizione dei vocali richiede ElevenLabs.

**Note su ElevenLabs (piano gratuito):** le voci prese dalla libreria pubblica non si possono
usare tramite API; l'account può essere bloccato per "attività insolita" anche con caratteri
disponibili. In questi casi il messaggio d'errore lo dice.

## Il gruppo Telegram

Un gruppo con **un bot per l'assistente** e, facoltativo, **uno per l'agente della posta**. Gli
agenti senza un bot proprio parlano tramite l'assistente, con il loro nome davanti.

1. Crea i bot con @BotFather (`/newbot`) e disattiva la privacy di gruppo (*Bot Settings →
   Group Privacy → Turn off*), poi aggiungili a un gruppo.
2. Metti i token nella configurazione, avvia e scrivi `/id` nel gruppo: ti dice l'ID del gruppo
   (numero negativo, `allowed_chat_id`) e il tuo (`allowed_user_id`). I bot ignorano tutti gli
   altri.

Uso:

- Messaggio normale → risponde l'assistente, che fa da sé o delega. L'agente a cui delega
  risponde direttamente nel gruppo.
- Rispondi a un messaggio dell'agente della posta, o scrivi `@nome_bot_mail` → risponde lui.
- Rispondi a una **bozza** con cosa cambiare ("più formale") → arriva la nuova versione.
- Comandi: `/id`, `/stato`, `/posta` (controlla subito la posta), `/regole`.

Un bot può essere ascoltato da un solo programma: due installazioni con gli stessi token vanno
in conflitto.

## Posta di lavoro

Imposta IMAP/SMTP del tuo provider (server, porte SSL 993/465, utente, password).

- Ogni `check_interval_minutes` controlla la casella, classifica le nuove email (alta, media,
  bassa) e ti avvisa da `notify_min_priority` in su. Le email non vengono segnate come lette.
- **Niente parte senza di te**: ogni risposta è una bozza con Invia, Salva in Bozze, Modifica,
  Scarta, su Telegram e nella dashboard.
- **Firma**: puoi incollare quella in HTML del tuo programma di posta.
- Nelle istruzioni dell'agente della posta elenca i tuoi **clienti importanti**: le loro email
  hanno priorità alta.

## Vista Casa

Il pulsante **⌂ Casa** apre la plancia di Home Assistant. In alto il **cruscotto**: chi è in
casa, allarme, clima medio, luci accese, energia e telecamere; sotto le scene. Ogni entità ha la
sua **card**: luci (tocca la card, barra della luminosità), clima con quadrante, tapparelle con la
finestra disegnata, valvole, media con copertina e comandi, prese con il consumo, porte e finestre
(rosse quando aperte, "da quanto"), sensori con il grafico delle ultime 24 ore, persone,
telecamere. Le **serrature** con un codice in Home Assistant chiedono il codice sul tastierino,
le altre una conferma nella card; l'**allarme** si disinserisce con il tastierino. Le **stanze sono le aree di Home
Assistant**: le entità di un'area (o del suo dispositivo) compaiono da sole nella stanza.

- **Piantina**: **⚙ Piantina** apre l'editor.
  1. **Carica planimetria**: una foto o un PDF della pianta (i margini bianchi vengono
     tolti da soli). Resta solo nella cartella dell'add-on.
  2. **Proponi le stanze**: Claude guarda la pianta e propone le stanze, già collegate alle
     aree di Home Assistant quando il nome corrisponde (una richiesta, pochi centesimi).
  3. Sistema a mano: trascina una stanza per spostarla, l'angolo in basso a destra per
     ridimensionarla, trascina sul vuoto (o **+ Stanza**) per disegnarne una nuova. Nel
     pannello scegli l'area, oppure "solo disegno" per un ambiente senza entità; **contorno**
     per balconi e terrazzi. Spunta le aree **Fuori casa** (giardino, parcheggio…).
  4. **Salva piantina**. Con **+ Piano** aggiungi altri piani.

  Chi preferisce può usare **Testo** e scrivere la disposizione in YAML (posizioni `x, y, w, h`
  in percentuale del disegno); facoltativo `energy: { power: sensor.…, today: sensor.… }`.
  Tutto finisce in `casa.yaml` nella cartella dell'add-on; senza piantina le aree compaiono
  come riquadri.
  ```yaml
  floors:
    - name: Piano terra
      aspect: 1.2          # larghezza / altezza del disegno
      rooms:
        - { area: Soggiorno, x: 0, y: 0, w: 50, h: 60 }
        - { area: Cucina, x: 50, y: 0, w: 50, h: 60 }
        - { area: Camera da letto, x: 0, y: 60, w: 100, h: 40 }
  outside: [Giardino]
  ```
- **Nomi**: se a un'entità hai dato degli **alias** in Home Assistant (impostazioni
  dell'entità → Alias), HubNEX mostra il primo; altrimenti il nome di Home Assistant. Nella
  ricerca per aggiungere entità valgono tutti i nomi.
- **Energia**: tocca "Energia" nel cruscotto: si apre un popup (F1 arancione, F2 blu, F3 verde). Tre viste a scelta, anche insieme: **il reattore**
  (il periodo diviso per fascia attorno alla potenza adesso, in % del contatore), **la
  giornata** (la potenza di oggi sulle fasce, con i kWh per fascia) e **la bolletta** (spesa,
  stima a fine periodo al ritmo attuale, fasce a confronto col periodo precedente e un
  consiglio quando una fascia cresce). Con **Configura** scegli le viste e i tuoi sensori: la
  fascia (calendario ARERA calcolato da HubNEX con i festivi, un tuo sensore, o tariffa unica),
  i kWh per fascia (es. i contatori "utility meter" di Home Assistant: da loro arrivano inizio
  del periodo e confronto), prezzi o spesa, la potenza e la taglia del contatore, altri valori
  (tensione, fattore di potenza…). Nessun calcolo usa l'AI.
- **Persone**: le persone di Home Assistant (Impostazioni → Persone, con l'app sul telefono o un
  dispositivo di tracciamento) compaiono in alto nella Casa: *a casa*, *fuori* o il nome della
  zona in cui si trovano.
- **Orari e impostazioni**: gli helper di Home Assistant si usano dalla Casa. Un orario
  (`input_datetime`, `time`) si cambia toccando l'ora o con −15 / +15; i numeri con il cursore,
  le liste scegliendo l'opzione, i testi scrivendo. Il valore lo salva Home Assistant e le
  automazioni lo usano come prima.
- **Card su misura**: in *Modifica stanza* → **+ Nuova card** dai un nome, aggiungi le entità
  (anche di altre stanze), le metti in ordine, scegli il **gruppo** (Clima, Luci…; di base
  quello della prima entità) e piccola o larga. Esempio: una card
  "Stufa" con l'ora di accensione e di spegnimento mostra anche la fascia sulla giornata e
  "attiva fino alle 22:00"; se nella card c'è l'interruttore che attiva gli orari (es.
  "automatica", si sceglie nell'editor), da spento la card dice "orari non attivi". I sensori numerici mostrano il grafico delle
  ultime 24 ore: nell'editor lo spegni con l'interruttore "grafico", sulle card singole con
  "Togli grafico" in modifica. Sempre in modifica ogni card si sposta dentro il suo gruppo
  (trascinando ⋮⋮ o con ‹ ›), si rinomina solo in HubNEX, diventa larga o piccola, si toglie;
  *Ordine automatico* rimette l'ordine di partenza. Tutto resta in HubNEX: in Home Assistant non cambia nulla.
- **Stanza**: toccala per la scheda rapida, **Apri stanza** per tutte le entità divise per
  tipo. Con più sensori di temperatura scegli quale usare ("temperatura da").
- **Modifica stanza**: aggiungi **qualsiasi entità** di Home Assistant (anche quelle che Home
  Assistant nasconde, come i lettori nascosti da Music Assistant), spostando l'area anche in Home
  Assistant (consigliato) o solo nella plancia; **Togli** la nasconde solo dalla plancia; **Mostra come** cambia il
  tipo (Luce, Presa / interruttore, Cancello / porta a impulso, Sirena, Solo stato). Per un relè
  che accende una luce è ancora meglio "Mostra come → Luce" nelle impostazioni dell'entità in
  Home Assistant: così anche Assist e l'assistente la trattano da luce.
- **Media**: accendi e spegni, ▶ / ❚❚ e volume.
- **Telecamere**: miniature nelle stanze e il pulsante **Telecamere** in alto; toccandone una
  si apre il video dal vivo (lo stesso flusso che usa Home Assistant).
- **Allarme**: pulsante in alto con lo stato; In casa / Fuori / Notte e Disinserisci con
  tastierino per il codice.
- I comandi della vista Casa vanno diretti a Home Assistant e **non usano credito Claude**.

## Mappa neurale

Il pulsante **✺ Mappa** mostra la "mente" del team in 3D: l'assistente al centro, aziende,
reparti e agenti, e intorno tutto ciò che il team sa (memorie, compiti, scadenze, bozze),
collegato a chi l'ha prodotto e alle parole chiave in comune. Cerca un nome per evidenziare
tutto quello che lo riguarda.

## Niente iniziative senza il tuo ordine

- Le routine sono spente finché non scrivi `enabled: true`. Anche accese, **non possono
  cambiare nulla in casa**, e lo stesso vale per gli eventi delle automazioni: guardano e ti
  scrivono cosa propongono.
- Gli agenti fanno solo il compito ricevuto; il resto lo propongono.
- Le modifiche ai programmi collegati e le email partono solo dopo la tua conferma.
- **Le tue regole**: quando dici all'assistente qualcosa che deve valere sempre ("non fare
  mai…", "d'ora in poi…"), la salva come regola per **tutto** il team. `/regole` le elenca.

## Usarla fuori da Home Assistant

**Con Nabu Casa** (consigliato): apri HubNEX dalla barra laterale, copia l'indirizzo e
aggiungilo alla schermata Home del telefono.

**Solo in rete locale**: imposta un **Token HQ**, scrivi `8765` nella porta (Configurazione →
Rete), riavvia e apri `http://IP-DI-HOME-ASSISTANT:8765`. Puoi installarla come app dal menu del
browser.

**Aprire HubNEX all'avvio di Home Assistant**: dentro Home Assistant, in alto **⚙** →
interruttore. Vale solo per il tuo account; gli altri utenti restano sulla loro plancia.

**Solo la Casa, per chi vuole solo accendere una luce**: in alto **⚙** → spegni **Schede HQ e
Mappa** (HubNEX apre direttamente la Casa) e/o **Assistente AI** (spariscono chat, voce e
approvazioni: nessun credito Claude). Dentro Home Assistant la scelta è salvata con l'account
di chi è collegato e vale su tutti i suoi dispositivi; fuori resta nel browser. È una comodità,
non un blocco: chiunque può riaccenderle dallo stesso menu.

**Utenti non amministratori**: HubNEX compare nella barra laterale di **tutti** gli utenti di
Home Assistant. Chi non è amministratore ha solo la **Casa**: luci, clima, tapparelle, scene,
telecamere e allarme (con codice), come in Home Assistant. Non vede l'assistente, la posta, gli
agenti, l'attività e i costi, e non può modificare piantina e stanze. Il controllo lo fa l'add-on
a ogni richiesta, non solo l'interfaccia. Per dare tutto anche a loro: opzione
**Utenti non amministratori → completo**.

## Eventi dalle automazioni

Le automazioni possono passare un evento all'assistente, che ti scrive cosa propone. Con un
**Token HQ**, in `configuration.yaml`:

```yaml
rest_command:
  hubnex_event:
    url: "http://<hostname dell'add-on>:8765/api/ha/event"
    method: POST
    headers:
      Authorization: "Bearer IL_TUO_TOKEN_HQ"
    content_type: "application/json"
    payload: '{"message": "{{ message }}"}'
```

## Sicurezza

- Dalla barra laterale accedi solo tu, perché passi dal login di Home Assistant.
- La porta 8765 è chiusa di default; se la apri serve il **Token HQ**.
- I servizi in **Servizi HA bloccati** (serrature, disinserimento allarme) l'assistente non li
  chiama mai da solo; dalla plancia puoi farlo tu, con conferma o codice.
- Le chiavi stanno solo nella configurazione dell'add-on e in `agents.yaml`, sul tuo Home
  Assistant.

## Credito Anthropic

Il riquadro **Credito Claude** è una **stima**: in `anthropic_credit_usd` scrivi il saldo che
vedi su console.anthropic.com → Billing e HubNEX scala il costo di ogni richiesta. Sotto 1 $
ricevi un avviso. Con `0` vedi solo quanto hai speso.

Per spendere poco: l'agente della posta usa il modello economico; con Assist i comandi semplici
li fa Home Assistant; le routine e le ricerche web consumano, usale quando servono.

## Dati e backup

Memoria, scadenze, bozze, regole e cronologia sono in `/data/hubnex.db`; `agents.yaml` e
`casa.yaml` nella cartella di configurazione dell'add-on. Finiscono tutti nei backup di Home
Assistant.

### Backup di HubNEX e trasferimento su un'altra installazione

Da **⚙ Preferenze → Backup → Scarica** ottieni un unico file `.zip` con tutto ciò che HubNEX
sa: memoria e mappa neurale, scadenze, chat, impostazioni della Casa (card, nomi, ordine,
energia), piantina con le sue immagini e `agents.yaml`. Le opzioni dell'add-on (chiave Anthropic,
Telegram, posta) **non** sono incluse; `agents.yaml` sì, con gli eventuali token dei connettori
MCP: custodisci il file come una password. Solo per gli amministratori.

**Ripristina → Carica…** su un'altra installazione mette tutto al suo posto e riavvia HubNEX.
I file che sostituisce restano accanto con il suffisso `.prima-del-ripristino`.

Per passare da una copia locale (`/addons/local`) all'add-on del repository:

1. Nella copia locale: **Preferenze → Backup → Scarica**.
2. Nella pagina dell'add-on locale: **Configurazione → ⋮ → Modifica in YAML**, copia tutto
   (sono le tue opzioni e chiavi) e **arresta** l'add-on locale.
3. Installa HubNEX dal repository, apri **Configurazione → ⋮ → Modifica in YAML**, incolla,
   salva e avvia.
4. Apri HubNEX: **Preferenze → Ripristina → Carica…** e scegli il backup. HubNEX si riavvia
   con i tuoi dati.
5. Assist: in **Dispositivi e servizi** elimina la vecchia integrazione HubNEX e configura
   quella "rilevata" del nuovo add-on.
6. Quando tutto funziona, disinstalla l'add-on locale.
