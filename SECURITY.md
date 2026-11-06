# Sicurezza

HubNEX custodisce chiavi API, accesso alla posta e il controllo della casa, serrature e
allarme compresi. Una falla va trattata in privato.

## Come segnalare un problema

**Non aprire una segnalazione pubblica.** Usa la segnalazione privata di GitHub:
[Security → Report a vulnerability](https://github.com/NicoLPHA/HubNEX/security/advisories/new).

Scrivi la versione di HubNEX, cosa si può fare sfruttando il problema e come riprodurlo.
Riceverai una risposta entro una settimana; la correzione esce in una nuova versione e la
segnalazione viene resa pubblica solo dopo, con il tuo nome se lo desideri.

## Versioni supportate

Solo l'ultima versione pubblicata riceve correzioni di sicurezza: aggiorna l'add-on.

## Cosa conta come problema di sicurezza

- accesso alla dashboard o all'API senza autorizzazione, o un utente non amministratore che
  arriva oltre la Casa;
- un'azione su serrature, allarme, posta o connettori eseguita senza la conferma prevista;
- chiavi, token o dati personali esposti (log, backup, risposte dell'API);
- un modo per far eseguire ad agenti o automazioni azioni non richieste dal proprietario.

## Cosa fa già HubNEX

- Le chiavi stanno solo nelle opzioni dell'add-on e in `agents.yaml`, nel tuo Home Assistant.
  Il backup di HubNEX non contiene le opzioni dell'add-on; contiene `agents.yaml`, quindi gli
  eventuali token dei connettori: va custodito come una password.
- Dalla barra laterale vale l'accesso di Home Assistant; da fuori serve il token HQ.
- Serrature, allarme e servizi bloccati chiedono sempre conferma; le scritture sui programmi
  di lavoro (MCP) e le email partono solo dopo il tuo ✅.
