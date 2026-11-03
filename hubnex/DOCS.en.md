# HubNEX

*[Italiano](DOCS.md) · English*

The AI headquarters for home and work: an assistant (called **Jarvis** out of the box) with its
team of Claude agents, a 3D dashboard in Home Assistant's sidebar, the house's dashboard, a
Telegram group, voice and connectors for the programs you use at work.

## First start

1. In the **Configuration** tab enter at least the **Anthropic API key**
   (console.anthropic.com → API Keys), start the add-on and turn on **Show in sidebar**.
2. Open **HubNEX** from the sidebar: you see the headquarters with the assistant and its agents.
3. Write to it in the chat at the bottom. It already uses Home Assistant for the house: no token
   to create, the add-on goes through the Supervisor.
4. Tell it who you are and how you work in `agents.yaml` (below): the more it knows, the more
   useful it is.

**Language**: the add-on speaks Home Assistant's language (Italian, otherwise English); the
**Language** option chooses it by hand. On the first start the example `agents.yaml` is in
the same language.

Everything else is optional and can be added whenever you like, in this suggested order:

| What | Where | Section |
| --- | --- | --- |
| Your team, your business | `agents.yaml` | The team |
| Floor plan of the house | Home → ⚙ Floor plan | Home view |
| Talking through Assist (app, speakers) | HubNEX integration + Voice assistants | Voice |
| Voice in the dashboard | *Voice from Home Assistant* option or ElevenLabs | Voice |
| Telegram group | the bots' options | The Telegram group |
| Work mailbox | IMAP/SMTP options | Work mailbox |
| The programs of your work | `connectors` in `agents.yaml` | Connectors |
| Tablet or phone outside HA | HQ token and port | Using it outside Home Assistant |

Every option of the **Configuration** tab has its explanation next to the field.

## The team: `agents.yaml`

On the first start `agents.yaml` is created in the add-on's configuration folder,
`/addon_configs/<id>_hubnex/agents.yaml`. Open it with the **File editor** or **Studio Code
Server** add-on, or through Samba in the `addon_configs` share. After a change **restart the
add-on**.

- `boss`: the assistant who coordinates everything: name, character, instructions, tools.
- `companies`: your "companies" (work, home, a club…), with departments and agents. Every agent
  has a role, instructions and the tools it may use.
- `connectors`: the programs of your work (see **Connectors**).
- Routines: tasks an agent does by itself at fixed times. They are **off** until you write
  `enabled: true`.

The example file is commented line by line. Instructions can be written in any language: the
assistant answers in the add-on's language anyway.

## Connectors: the programs of your work

HubNEX connects to the programs you use at work (management software, calendar, CRM, Notion,
databases…) through **MCP** (Model Context Protocol), the open standard to connect AI to
programs. Many programs already have an "MCP server", and whoever develops one can add it.

In `agents.yaml`:

```yaml
connectors:
  - name: Management                    # name shown to you and to the agents
    url: https://example.com/mcp        # address of the MCP server
    token: your-key                     # if the server asks for one (Authorization: Bearer …)
    agents: [boss, technical]           # who may use it (omitted = everybody; boss = the assistant)
```

HubNEX reads by itself which tools the program offers and gives them to the agents listed.

- Tools that **read** are used freely.
- Tools that **change** data don't run at once: you see a summary with **✅ Confirm / ❌
  Cancel**, in the Telegram group and in the "To approve" panel of the dashboard. They run only
  after your ok, and only once even if you press twice.
- How it knows: the server declares which tools are read-only. If it doesn't, the read-only ones
  are those starting with `get`, `list`, `search`, `read`, `find`… and all the others ask for
  confirmation. You can correct this with `free: [name]` (never ask) and
  `always_confirm: [name]` (always ask), or `confirm: always` for the whole connector.
- `/stato` in the Telegram group says whether each connector answers and how many tools it
  offers; errors also appear in the dashboard's activity.

## Voice

You can talk to the assistant in three ways. All are optional.

**1. Home Assistant's Assist** (app, smart speakers, wake word)

The add-on installs the **HubNEX** integration by itself, which makes the assistant an Assist
*conversation agent*. Speech recognition and the voice are Home Assistant's, with the engine you
prefer: Piper (local and free), Home Assistant Cloud, ElevenLabs, Google…

1. Start the add-on: a notification arrives. **Restart Home Assistant**.
2. Settings → Devices & services: **HubNEX discovered** appears → *Configure* → *Submit*.
3. Settings → Voice assistants → your assistant → **Conversation agent**: choose HubNEX's
   assistant and keep **"Prefer handling commands locally"** on: simple commands ("turn on
   the kitchen light") are run by Home Assistant, at once and without using credit; everything
   else goes to the assistant.

If the integration is not discovered: Devices & services → Add → "HubNEX", with the add-on's
address (`http://<add-on hostname>:8765`, the hostname is on the add-on page) and the
**HQ token**. Usually it's enough to restart the HubNEX add-on.

Spoken answers are short (two sentences at most), in the language Assist is speaking. Every
request, from Assist or the dashboard, takes the fastest possible road:

1. **Home Assistant by itself** ("turn on the kitchen light"): instant, no AI. Assist does it
   already; the dashboard tries it first. Expose the entities to Assist and give them an alias
   with the name you say. Locks, the alarm and doors never go this way.
2. **The quick route** for the other requests about the house: the **Quick command model**
   (Haiku out of the box) with the list of entities and their states already in hand. In the
   chat, under the answer, it says QUICK ANSWER (or HOME ASSISTANT for point 1).
3. **Jarvis** with its model and all its instructions for everything else: complex questions,
   work, agents, locks and the alarm (with confirmation).

**2. Dashboard** (microphone and speaker in the bottom bar)

- What you say is recognised by the browser (free). Browsers allow it only on `https://`: it
  works from the Home Assistant app and through Nabu Casa, not from `http://homeassistant.local`.
- The assistant answers with the voice chosen in the configuration:
  - **Voice from Home Assistant**: write one of Home Assistant's text-to-speech engines, e.g.
    `tts.piper` (local, free) or `tts.home_assistant_cloud`. It takes precedence. In **Home
    Assistant engine voice** you can choose the voice by name (e.g. `Ryan` or `Jenny` with Home
    Assistant Cloud): if the name doesn't exist, the error message lists the available ones. The
    language is Home Assistant's;
  - or **ElevenLabs**: API key (elevenlabs.io → Profile → API Keys), voice ID (Voices → the
    voice → ID) and model (`eleven_flash_v2_5`, the cheapest).
- If the voice doesn't start, the reason appears under the answer.
- Before it is read, the text is prepared for listening: no symbols, emoji or links, units and
  abbreviations in words (Ω → "ohms", kWh → "kilowatt hours"), dates spelled out, a pause for
  every item of a list. The written text stays as it is.
- **Spoken answers**: `completa` (the voice reads the whole answer) or `riassunto` (summary):
  for long answers the voice says only the gist in one or two sentences and the written text
  stays complete. Short answers are read whole. It applies to the dashboard with the speaker on
  and to Telegram voice notes; Assist already answers in two sentences.

**3. Telegram**: send a voice note, it is transcribed with ElevenLabs and the assistant also
answers by voice (`telegram_voice_replies`). Transcription needs ElevenLabs.

**About ElevenLabs (free plan):** voices from the public library can't be used through the API;
the account can be blocked for "unusual activity" even with characters left. In these cases the
error message says so.

## The Telegram group

A group with **one bot for the assistant** and, optionally, **one for the mail agent**. Agents
without a bot of their own speak through the assistant, with their name in front.

1. Create the bots with @BotFather (`/newbot`) and turn group privacy off (*Bot Settings →
   Group Privacy → Turn off*), then add them to a group.
2. Put the tokens in the configuration, start and send `/id` in the group: it tells you the
   group's ID (a negative number, `allowed_chat_id`) and yours (`allowed_user_id`). The bots
   ignore everybody else.

Use:

- A normal message → the assistant answers, doing it itself or delegating. The agent it
  delegates to answers directly in the group.
- Reply to a message of the mail agent, or write `@mail_bot_name` → it answers.
- Reply to a **draft** with what to change ("more formal") → the new version arrives.
- Commands: `/id`, `/stato` (status), `/posta` (check the mail now), `/regole` (your rules).

A bot can be listened to by one program only: two installations with the same tokens conflict.

## Work mailbox

Set your provider's IMAP/SMTP (servers, SSL ports 993/465, user, password).

- Every `check_interval_minutes` it checks the mailbox, sorts the new emails (high, medium, low
  priority: `alta`, `media`, `bassa`) and tells you from `notify_min_priority` up. Emails are
  not marked as read.
- **Senders not to announce** (`mail_ignore`): comma separated, an address
  (`offers@shop.com`), a domain (`@newsletter.com`) or a word of the address (`noreply`).
  Their emails stay in the mailbox and Jarvis Mail reads them if you ask, but no Telegram
  message arrives and they aren't even sorted (no Claude credit).
- **Nothing goes out without you**: every reply is a draft with Send, Save to Drafts, Edit,
  Discard, on Telegram and in the dashboard.
- **Signature**: you can paste the HTML one from your mail program.
- In the mail agent's instructions list your **important customers**: their emails get high
  priority.

## Home view

The **⌂ Home** button opens Home Assistant's dashboard. At the top the **HUD**: who is home,
alarm, average climate, lights on, energy and cameras; below, the scenes. Every entity has its
**card**: lights (tap the card, brightness bar), climate with a dial, blinds with the window drawn,
valves, media with cover art and controls, plugs with their consumption, doors and windows (red
when open, "for how long"), sensors with the chart of the last 24 hours, people, cameras.
**Locks** with a code in Home Assistant ask for it on a keypad, the others for a confirmation in
the card; the **alarm** is disarmed with the keypad. The **rooms are Home Assistant's areas**:
the entities of an area (or of its device) appear in the room by themselves.

- **Floor plan**: **⚙ Floor plan** opens the editor.
  1. **Upload floor plan**: a photo or a PDF of the plan (white margins are trimmed by
     themselves). It stays only in the add-on's folder.
  2. **Suggest rooms**: Claude looks at the plan and suggests the rooms, already linked to Home
     Assistant's areas when the name matches (one request, a few cents).
  3. Fix by hand: drag a room to move it, the bottom-right corner to resize it, drag on empty
     space (or **+ Room**) to draw a new one. In the panel choose the area, or "drawing only"
     for a space without entities; **outline** for balconies and terraces. Tick the
     **Outdoors** areas (garden, parking…).
  4. **Save floor plan**. **+ Floor** adds more floors.

  If you prefer, **Text** lets you write the layout in YAML (positions `x, y, w, h` in percent of
  the drawing); optional `energy: { power: sensor.…, today: sensor.… }`. Everything ends up in
  `casa.yaml` in the add-on's folder; without a floor plan the areas appear as tiles.
  ```yaml
  floors:
    - name: Ground floor
      aspect: 1.2          # width / height of the drawing
      rooms:
        - { area: Living room, x: 0, y: 0, w: 50, h: 60 }
        - { area: Kitchen, x: 50, y: 0, w: 50, h: 60 }
        - { area: Bedroom, x: 0, y: 60, w: 100, h: 40 }
  outside: [Garden]
  ```
- **Names**: if you gave an entity **aliases** in Home Assistant (entity settings → Aliases),
  HubNEX shows the first one; otherwise Home Assistant's name. When searching for entities to
  add, all names count.
- **Energy**: tap "Energy" in the HUD: a popup opens. Three views, one or more: **the reactor**
  (the period split by band around the power now, in % of the meter), **the day** (today's power,
  over the bands when there are any) and **the bill** (cost, estimate at the end of the period at
  the current pace, comparison with the previous period). With **Configure** choose the views
  and your sensors: the time band (a **single rate**, your own sensor with state F1/F2/F3, or the
  Italian ARERA calendar computed by HubNEX), the kWh of the period (e.g. Home Assistant's
  "utility meters": the start of the period and the comparison come from them), prices or cost,
  the power and the size of the meter, other readings (voltage, power factor…). No calculation
  uses AI.
- **People**: Home Assistant's people (Settings → People, with the phone app or a tracker)
  appear at the top of the Home view: *home*, *away* or the name of the zone they are in.
- **Times and settings**: Home Assistant's helpers can be used from the Home view. A time
  (`input_datetime`, `time`) changes by tapping the time or with −15 / +15; numbers with the
  slider, lists by choosing the option, texts by writing. Home Assistant saves the value and
  your automations use it as before.
- **Custom cards**: in *Edit room* → **+ New card** give it a name, add entities (from other
  rooms too), order them, choose the **group** (Climate, Lights…; by default the first entity's)
  and small or wide. Example: a "Stove" card with its on and off times also shows the band over
  the day and "on until 22:00"; if the switch that enables the times is in the card (e.g.
  "automatic", chosen in the editor), when it is off the card says "times not active". Numeric
  sensors show the chart of the last 24 hours: in the editor turn it off with the "chart" switch,
  on single cards with "Hide chart" while editing. Still while editing every card moves within
  its group (dragging ⋮⋮ or with ‹ ›), can be renamed in HubNEX only, made wide or small,
  removed; *Automatic order* restores the original order. Everything stays in HubNEX: nothing
  changes in Home Assistant.
- **Room**: tap it for its quick card, **Open room** for all its entities grouped by type. With
  several temperature sensors choose which one to use ("temperature from").
- **Edit room**: add **any entity** of Home Assistant (including those Home Assistant hides, like
  players hidden by Music Assistant), moving the area in Home Assistant too (recommended) or only
  in the dashboard; **Remove** hides it from the dashboard only; **Show as** changes its type
  (Light, Plug / switch, Gate / door with a pulse, Siren, State only). For a relay that powers a
  light, "Show as → Light" in the entity's settings in Home Assistant is even better: Assist and
  the assistant then treat it as a light too.
- **Media**: on and off, ▶ / ❚❚ and volume.
- **Cameras**: thumbnails in the rooms and the **Cameras** button at the top; tapping one opens
  the live video (the same stream Home Assistant uses).
- **Alarm**: a button at the top with its state; Home / Away / Night and Disarm with a keypad
  for the code.
- The Home view's commands go straight to Home Assistant and **use no Claude credit**.

## House notifications

HubNEX watches the house by itself and warns you when something is wrong. **It doesn't use
Claude**: these are fixed rules on Home Assistant's states, so the warnings are immediate and
free. Set them up in ⚙ Preferences → **House notifications**.

| Rule | When it warns |
|---|---|
| Leaks, smoke, gas | A water, smoke, gas or carbon monoxide sensor goes off: at once, even in the quiet hours |
| Windows open | A window stays open while the heating or the air conditioning is on, or while it rains |
| Nobody home | Everybody is out and a door, the gate or a lock is open. **Close** button |
| High consumption | The house's power (the sensor chosen in Energy) stays above the threshold |
| Lights on at night | Lights still on during the night hours (23:30–06:00 by default). **Turn off** button |
| Low batteries | Sensors with the battery below 15% |
| Devices not responding | Devices that haven't answered for more than an hour |

**Where they arrive**, rule by rule:

- the Home Assistant **app** on your phone: a push notification with the buttons. HubNEX finds
  the phones with the app by itself; you can leave some out. Urgent warnings come with high
  priority.
- **Telegram**, in Jarvis' group, with the same buttons.
- **Home Assistant**: the notifications under the bell.

How they behave:

- every rule waits for the problem to last a few minutes (you choose how many), so a window
  opened for a moment doesn't bother you;
- it warns **once** per problem; if another one joins in the meantime (a second window) it
  updates the warning;
- when the problem is solved, the notification on the phone and under the bell **goes away by
  itself**, and on Telegram the buttons disappear;
- in the **quiet hours** warnings wait for the end of the slot (except leaks, smoke and gas);
- **it acts only if you press a button** on the notification. Without your tap nothing changes.

In every rule, «Watches N of N» lists the entities it looks at: untick those to ignore (for
example a soil moisture sensor seen as a water leak). **Send a test** sends a notification on
every channel in use.

## Neural map

The **✺ Map** button shows the team's "mind" in 3D: the assistant in the middle, companies,
departments and agents, and around them everything the team knows (memories, tasks, deadlines,
drafts), linked to whoever produced it and to the keywords they share. Search for a name to
highlight everything about it.

## No initiative without your order

- Routines are off until you write `enabled: true`. Even when on, **they can't change anything
  in the house**, and the same goes for events from automations: they look and write to you what
  they suggest.
- Agents do only the task they were given; the rest they suggest.
- Changes to connected programs and emails go out only after your confirmation.
- **Your rules**: when you tell the assistant something that must always apply ("never…",
  "from now on…"), it saves it as a rule for the **whole** team. `/regole` lists them.

## Using it outside Home Assistant

**With Nabu Casa** (recommended): open HubNEX from the sidebar, copy the address and add it to
the phone's home screen.

**Local network only**: set an **HQ token**, write `8765` in the port (Configuration →
Network), restart and open `http://HOME-ASSISTANT-IP:8765`. You can install it as an app from
the browser's menu.

**Open HubNEX when Home Assistant starts**: inside Home Assistant, at the top **⚙** → the
switch. It applies to your account only; the other users keep their dashboard.

**Language**: the dashboard is in Italian or English, following the Home Assistant language of
whoever opens it (not Italian = English). At the top **⚙ → Language** chooses it by hand, for
that browser only. Jarvis, the agents, Telegram and the add-on's messages follow the
**Language** option of the configuration (auto = Home Assistant's).

**Home only, for whoever just wants to turn on a light**: at the top **⚙** → turn off **HQ and
Map tabs** (HubNEX opens straight on the Home view) and/or **AI assistant** (chat, voice and
approvals disappear: no Claude credit). Inside Home Assistant the choice is saved with the
account of whoever is signed in and applies on all their devices; outside, it stays in the
browser. It's a convenience, not a lock: anybody can turn them back on from the same menu.

**Non-admin users**: HubNEX appears in the sidebar of **all** Home Assistant users. Who isn't an
administrator gets the **Home** view only: lights, climate, blinds, scenes, cameras and alarm
(with the code), as in Home Assistant. They don't see the assistant, mail, agents, activity or
costs, and can't change the floor plan or the rooms. The add-on checks it on every request, not
only the interface. To give them everything: option **Non-admin users → completo** (full).

## Events from automations

Automations can hand an event to the assistant, which writes to you what it suggests. With an
**HQ token**, in `configuration.yaml`:

```yaml
rest_command:
  hubnex_event:
    url: "http://<add-on hostname>:8765/api/ha/event"
    method: POST
    headers:
      Authorization: "Bearer YOUR_HQ_TOKEN"
    content_type: "application/json"
    payload: '{"message": "{{ message }}"}'
```

## Security

- From the sidebar only you get in, through Home Assistant's login.
- Port 8765 is closed by default; if you open it, the **HQ token** is needed.
- The services in **Blocked HA services** (locks, disarming the alarm) are never called by the
  assistant on its own; from the dashboard you can do it, with a confirmation or the code.
- The keys stay only in the add-on's configuration and in `agents.yaml`, on your Home Assistant.

## Anthropic credit

The **Claude credit** tile is an **estimate**: in `anthropic_credit_usd` write the balance you
see at console.anthropic.com → Billing and HubNEX subtracts the cost of every request. Below
$1 you get a warning. With `0` you only see how much you spent.

### Spend history

Click the **Claude spend/credit** tile in HQ (on the phone: ⚙ Preferences → **Claude spend**)
to open the history:

- **today**, **this month** and the **end-of-month estimate**, based on the pace of the days
  gone by;
- one bar per day over the last 7, 30 or 90 days (hover for the amount and the calls);
- the spend **by agent** (Jarvis, Jarvis Mail, the team's agents, the floor plan proposal) and
  **by model** (Sonnet, Haiku…), with calls and tokens.

With `monthly_budget_usd` you set a monthly budget: at 80% and 100% you get a warning in the
Telegram group and in Home Assistant's notifications, and the popup shows the budget bar. It is
only a warning: HubNEX doesn't stop. The history starts when you install this version and is
included in the backup.

The figures are HubNEX's estimate at list price for every call: the exact bill is on
console.anthropic.com.

To spend little: the mail agent uses the cheap model; with Assist simple commands are done by
Home Assistant; routines and web searches cost credit, use them when needed.

## Data and backup

Memory, deadlines, drafts, rules and history are in `/data/hubnex.db`; `agents.yaml` and
`casa.yaml` in the add-on's configuration folder. All of them go into Home Assistant's backups.

### HubNEX backup and moving to another installation

**⚙ Preferences → Backup → Download** gives you one `.zip` file with everything HubNEX knows:
memory and neural map, deadlines, chat, Home view settings (cards, names, order, energy), the
floor plan with its images and `agents.yaml`. The add-on's options (Anthropic key, Telegram,
mail) are **not** included; `agents.yaml` is, with any MCP connector tokens: keep the file like a
password. Administrators only.

**Restore → Upload…** on another installation puts everything in place and restarts HubNEX.
The files it replaces stay next to them with the `.prima-del-ripristino` suffix.

To move from a local copy (`/addons/local`) to the repository's add-on:

1. In the local copy: **Preferences → Backup → Download**.
2. On the local add-on's page: **Configuration → ⋮ → Edit in YAML**, copy everything (your
   options and keys) and **stop** the local add-on.
3. Install HubNEX from the repository, open **Configuration → ⋮ → Edit in YAML**, paste, save
   and start.
4. Open HubNEX: **Preferences → Restore → Upload…** and choose the backup. HubNEX restarts with
   your data.
5. Assist: in **Devices & services** delete the old HubNEX integration, then **restart the
   HubNEX add-on**: "HubNEX discovered" appears, press *Configure* (no token to enter).
6. When everything works, uninstall the local add-on.
