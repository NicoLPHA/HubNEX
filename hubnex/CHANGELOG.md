# Changelog

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
