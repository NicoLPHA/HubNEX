# Contribuire a HubNEX

Grazie dell'interesse! Segnalazioni, idee e correzioni sono benvenute. Per i problemi di
sicurezza leggi prima [SECURITY.md](SECURITY.md).

## Com'è fatto

```
hubnex/                 l'add-on
  hubnex/               il server (Python, FastAPI): assistente, agenti, Casa, energia, voce
  web/                  la dashboard (JavaScript senza build: moduli ES, three.js)
  integration/hubnex/   l'integrazione Assist che l'add-on installa in Home Assistant
  config/agents.yaml    il team d'esempio
  dev/demo.py           HubNEX con una casa e un Claude finti
  tests/                test del server (pytest) e della dashboard (tests/ui, nel browser)
docs/                   la presentazione (GitHub Pages)
```

## Provare la dashboard senza Home Assistant

```bash
cd hubnex
pip install -r requirements-dev.txt
python dev/demo.py 8765
```

Apri <http://127.0.0.1:8765>: una casa d'esempio con stanze, luci, clima, energia, telecamere e
un Claude finto che risponde sempre la stessa frase. Nessuna chiave API, nulla esce dal computer.
I comandi "accendi …" e "spegni …" nella chat li esegue la casa finta.

## I test

```bash
cd hubnex
python -m pytest -q                         # server
npm install --prefix tests/ui               # una volta: Playwright
npx --prefix tests/ui playwright install chromium
node --test tests/ui/*.test.cjs             # dashboard nel browser, contro dev/demo.py
```

Gli stessi controlli girano su GitHub a ogni modifica (scheda **Actions**): una modifica entra
solo con tutto verde.

## Lo stile

- **Python**: semplice e leggibile, funzioni brevi, docstring che spiegano il *perché*. I test
  accompagnano ogni comportamento nuovo.
- **Dashboard**: niente framework né build; i testi per l'utente sono in italiano (la versione
  inglese è in arrivo), sobri, senza emoji nell'interfaccia.
- **Niente iniziative**: HubNEX non agisce senza un ordine del proprietario. Serrature, allarme,
  posta e scritture sui programmi di lavoro chiedono sempre conferma. Una modifica che aggira
  questa regola non viene accettata.
- **Nessun dato personale** nel repository: esempi, test e schermate usano la casa d'esempio.

## Proporre una modifica

1. Apri prima una segnalazione o un'idea, così ne parliamo.
2. Fai un fork, un ramo con un nome chiaro, la modifica con i suoi test.
3. Aggiorna `hubnex/CHANGELOG.md` e, se cambia il comportamento, `hubnex/DOCS.md`.
4. Apri la pull request: descrivi cosa cambia per chi usa HubNEX.

La versione in `hubnex/config.yaml` la aggiorna chi pubblica: ogni nuova versione costruisce le
immagini dell'add-on.
