# Changelog

## 1.8.4
- Energia torna a essere un popup, come gli altri della barra in alto: si chiude con ×, con
  un clic sullo sfondo o con Esc. Impostazioni invariate.
- I popup della Casa stanno in un livello a parte: gli aggiornamenti dal vivo della casa non
  li ridisegnano più, e un popup si aggiorna solo quando cambia ciò che mostra, senza perdere
  lo scorrimento.
- Nuovi colori delle fasce, ben distinti: F1 arancione, F2 blu, F3 verde. Anche "fascia
  adesso" prende il colore della fascia in corso.

## 1.8.3
- Nuova opzione "Risposte a voce": completa (come prima) o riassunto. Con riassunto, quando la
  risposta è lunga Jarvis aggiunge una o due frasi da dire a voce e la voce legge solo quelle;
  il testo scritto resta completo. Dashboard (altoparlante acceso) e vocali di Telegram.

## 1.8.2
- La voce legge un testo preparato per l'ascolto: niente simboli, emoji e link; unità e sigle
  in parole (Ω, kW, kWh, °, MT/BT…), date per esteso, pause al posto dei trattini degli
  elenchi. Vale per la dashboard, i vocali di Telegram e Assist.
- Nuova opzione "Voce del motore di Home Assistant": la voce per nome (es. Rinaldo con Home
  Assistant Cloud). La lingua è sempre quella di Home Assistant, anche senza voce scelta.
- ElevenLabs: crediti esauriti, chiave sbagliata e piano gratuito bloccato hanno ora messaggi
  distinti (prima tutti "chiave API non valida").

## 1.8.1
- Energia è una pagina come quelle delle stanze (← Casa per tornare), non più un popup: lo
  scorrimento non torna in alto con gli aggiornamenti dal vivo. Anche gli editor mantengono
  la posizione.
- "Fuori casa" e le altre aree non toccano più la piantina.
- Temperature delle stanze allineate qualunque sia il numero di decimali.

## 1.8.0
- Pannello Energia (tocca "Energia" nel cruscotto della Casa) con tre viste a scelta:
  - il reattore: il periodo diviso per fascia F1/F2/F3 attorno alla potenza adesso;
  - la giornata: la potenza di oggi sullo sfondo delle fasce, kWh di oggi per fascia;
  - la bolletta: spesa, stima a fine periodo, fasce col confronto sul periodo precedente e un
    consiglio quando una fascia cresce.
- Configurabile da HubNEX: viste, fascia (calendario ARERA con festivi, un proprio sensore,
  tariffa unica), kWh per fascia, prezzi o spesa, potenza e contatore, altri valori.
- Le finestre (editor, codice, energia) si aprono sotto la barra in alto e nascondono la chat.

## 1.7.5
- Grafico a scelta: nell'editor della card su misura ogni sensore numerico ha l'interruttore
  "grafico"; sulle card singole, in "Modifica stanza", "Togli grafico" / "Mostra grafico".

## 1.7.4
- Card su misura: i sensori numerici (luce, temperatura, consumo…) hanno il grafico delle
  ultime 24 ore, come nelle card singole.
- La linea sopra ogni entità di una card su misura si accende d'ambra quando quell'entità è
  attiva (movimento rilevato, interruttore acceso…) e di rosso per un allarme (finestra
  aperta, acqua, fumo).

## 1.7.3
- Card con orari: l'interruttore che li attiva (es. "automatica") conta. Acceso: "attiva fino
  alle…" / "si attiva alle…"; spento: "automatica spenta · orari non attivi" e fascia grigia.
- Nell'editor della card: "Gli orari valgono quando è acceso" (automatico dal nome, un
  interruttore a scelta, o nessuno).

## 1.7.2
- Card su misura: gli interruttori stanno in una colonna, uno sotto l'altro con il loro nome,
  invece di finire in fondo alle altre entità.
- Un input_boolean (es. "automatica") non conta più come "stufa accesa/spenta": lo stato viene
  solo da un interruttore, una luce o un termostato vero.
- Le card della stessa riga hanno la stessa altezza, anche tra gruppi affiancati.

## 1.7.1
- I gruppi della stanza (Luci, Clima, Prese…) restano sempre, anche dopo aver creato una card o
  cambiato l'ordine; non c'è più "Le mie card".
- Ogni card su misura va in un gruppo: si sceglie nell'editor ("Gruppo"), di base quello della
  prima entità.
- Spostare una card (trascinando o con ‹ ›) la muove dentro il suo gruppo.

## 1.7.0
- Orari, numeri, liste e testi di Home Assistant (input_datetime, time, date, input_number,
  number, input_select, select, input_text, text) si comandano dalla Casa: ora grande con
  −15 / +15, cursore, scelta dell'opzione, campo di testo.
- Card su misura: in "Modifica stanza" → "+ Nuova card" si compone una card con più entità
  (es. la stufa con accensione e spegnimento, fascia della giornata e "attiva fino alle…").
- Disposizione della stanza: card da spostare (trascinando o con ‹ ›), rinominare solo in
  HubNEX, rendere larghe o piccole, togliere; "Ordine automatico" per tornare ai gruppi.

## 1.6.0
- Vista Casa più sobria, in stile Jarvis: carattere Saira, numeri sottili, stati in minuscolo,
  card piatte e più piccole senza etichetta del tipo; una sottile linea ambra in alto quando
  una cosa è accesa, rossa quando c'è un problema.
- Cruscotto come una riga sottile; scene, interruttori e cursori più discreti; modalità del
  clima e dell'allarme come parole sottolineate; "Spegni tutte" e "Sblocca" come link.

## 1.5.1
- Le card tornano al carattere di prima (niente testo monospaziato negli stati).
- "Spegni tutte" non sposta più in basso le card delle luci rispetto alle sezioni accanto.

## 1.5.0
- Vista Casa ridisegnata in stile HUD: cruscotto in alto (persone, allarme, clima, luci,
  energia, telecamere) e scene esagonali.
- Una card per ogni tipo di entità: luci, clima con quadrante, tapparelle, valvole, media con
  copertina, avanzamento, comandi e volume, prese con il consumo del dispositivo, serrature,
  allarme, porte/finestre con "da quanto", sensori con il grafico delle ultime 24 ore, persone,
  sirene, telecamere.
- Scheda rapida della stanza con anelli di temperatura e umidità, luci come tasti, "da tenere
  d'occhio" e telecamera; sul telefono sale dal basso (trascina giù per chiudere, su per aprire).
- Serrature: con codice in Home Assistant il tastierino, altrimenti conferma nella card.
- Consumo della stanza nella pagina della stanza.

## 1.4.2
- Valvole (irrigazione, acqua): sezione propria con Apri / Chiudi (e Ferma, se la valvola lo
  permette). Prima erano trattate come tapparelle e i comandi non arrivavano.

## 1.4.1
- Scadenze: la spunta "fatto" è centrata nel suo riquadro e allineata al testo.

## 1.4.0
- Modifica stanza: si può aggiungere qualsiasi entità di Home Assistant, anche quelle nascoste
  (es. lettori di Music Assistant) o di diagnostica; le solite prima, con l'entity_id accanto.
- Persone: nella Casa compare chi è a casa, chi è fuori e in quale zona.
- Media: riproduci/pausa e volume, con titolo e artista.

## 1.3.1
- Nomi delle entità: se in Home Assistant hai dato degli alias a un'entità, la vista Casa
  mostra il primo; la ricerca per aggiungere entità trova anche gli alias.
- Documentazione: percorso consigliato per configurare tutto, nel primo avvio.

## 1.3.0
- HubNEX è visibile a tutti gli utenti di Home Assistant, non solo agli amministratori.
- Chi non è amministratore ha solo la Casa (comandi dei dispositivi, telecamere, allarme):
  assistente, posta, agenti, attività, costi e modifiche alla piantina restano agli
  amministratori. Il controllo è fatto dall'add-on su ogni richiesta. Nuova opzione
  "Utenti non amministratori" (casa / completo).

## 1.2.0
- Preferenze per utente: si possono spegnere le schede HQ e Mappa (HubNEX si apre sulla Casa)
  e l'assistente AI (niente chat, voce e approvazioni). Dentro Home Assistant valgono per
  l'account e lo seguono su tutti i dispositivi.

## 1.1.0
- Editor della piantina: carica una foto o un PDF della planimetria, sposta, ridimensiona e
  disegna le stanze con il dito o il mouse, collega ognuna a un'area di Home Assistant.
- "Proponi le stanze": Claude legge la planimetria e propone la disposizione da rifinire.
- La planimetria compare in trasparenza sotto la piantina olografica.
- Il YAML resta disponibile dal pulsante "Testo".

## 1.0.0
Prima versione pubblica.
- Assistente con team di agenti Claude configurabile in `agents.yaml` (aziende, reparti,
  agenti, istruzioni, routine spente di default, regole permanenti).
- Dashboard 3D: quartier generale, mappa neurale, nucleo animato durante la conversazione.
- Vista Casa: piantina olografica delle aree di Home Assistant, scheda rapida e pagina stanza,
  modifica delle entità (anche spostando l'area in Home Assistant), "Mostra come", telecamere
  dal vivo, allarme con tastierino.
- Connettori MCP per i programmi del lavoro, con conferma per ogni modifica.
- Posta IMAP/SMTP con smistamento e bozze da approvare.
- Gruppo Telegram con un bot per l'assistente e uno per la posta, vocali compresi.
- Voce: integrazione Assist (agente di conversazione), ElevenLabs o sintesi vocale di Home
  Assistant nella dashboard.
- Stima del credito Anthropic, eventi dalle automazioni, apertura all'avvio per singolo utente.
