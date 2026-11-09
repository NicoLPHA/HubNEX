// Settings screen (⚙ Voorkeuren → Lingua, voce e agende): language, voice engine, voice and calendars chosen
// from lists that Home Assistant itself provides, instead of typed in the add-on's options. A choice applies at
// once, wins over the add-on's option and survives a restart; "Come nell'add-on" takes it back.
import { t } from "./i18n.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ADDON = "__addon__"; // the dropdown's "as in the add-on" entry: no choice made here

export class SettingsView {
  constructor(api) {
    this.api = api;
    this.data = null;
    this.el = null;
    this.note = "";
    this.voices = {}; // engine -> [{id, name}] or { error }
    addEventListener("keydown", (e) => { if (e.key === "Escape" && this.el) { e.stopImmediatePropagation(); this.close(); } }, true);
  }

  async open() {
    if (!this.el) {
      this.el = document.createElement("div");
      this.el.className = "casa-modal alerts-modal settings-modal";
      this.el.setAttribute("role", "dialog");
      this.el.setAttribute("aria-label", t("Lingua, voce e agende"));
      this.el.addEventListener("click", (e) => this.onClick(e));
      this.el.addEventListener("change", (e) => this.onChange(e));
      document.body.appendChild(this.el);
      document.body.classList.add("casa-modal-open");
    }
    this.render();
    try {
      this.data = await (await this.api("/api/settings")).json();
      await this.loadVoices();
    } catch (e) {
      this.note = `⚠ ${e.message || e}`;
    }
    this.render();
  }

  close() {
    this.el?.remove();
    this.el = null;
    if (!document.querySelector(".casa-modal")) document.body.classList.remove("casa-modal-open");
  }

  async loadVoices() {
    const engine = this.data?.values.voice_tts_entity;
    if (!engine || engine in this.voices) return;
    try {
      this.voices[engine] = (await (await this.api(`/api/settings/voices?engine=${encodeURIComponent(engine)}`)).json()).voices;
    } catch (e) {
      this.voices[engine] = { error: e.message || String(e) };
    }
  }

  async save(patch) {
    try {
      this.data = await (await this.api("/api/settings", { method: "PUT", body: JSON.stringify(patch) })).json();
      this.note = t("Salvato");
      await this.loadVoices();
    } catch (e) {
      this.note = `⚠ ${e.message || e}`;
    }
    this.render();
  }

  onClick(e) {
    if (e.target === this.el || e.target.closest("[data-st-close]")) return this.close();
    if (e.target.closest("[data-st-cal-reset]")) return this.save({ calendar_entities: null });
  }

  onChange(e) {
    const el = e.target, d = this.data;
    if (!d) return;
    if (el.dataset.st) {
      const key = el.dataset.st, value = el.value === ADDON ? null : el.value;
      const patch = { [key]: value };
      if (key === "voice_tts_entity") patch.voice_tts_voice = value === null ? null : ""; // a voice belongs to its engine
      this.save(patch);
    } else if (el.dataset.stCal) {
      const now = new Set(d.values.calendar_entities);
      el.checked ? now.add(el.dataset.stCal) : now.delete(el.dataset.stCal);
      this.save({ calendar_entities: [...now] });
    }
  }

  render() {
    if (!this.el) return;
    const d = this.data;
    const body = d ? this.fieldsHTML(d) : `<p class="al-note">${t("Carico…")}</p>`;
    this.el.innerHTML = `<section class="panel casa-panel alerts settings">
      <h3>${t("Lingua, voce e agende")}<span class="costs-head"><button class="casa-x" data-st-close aria-label="${t("Chiudi")}">×</button></span></h3>
      <p class="al-intro">${t("Scegli da elenchi ciò che altrimenti si digita nelle opzioni dell'add-on. La scelta vale subito e prevale sull'add-on; «Come nell'add-on» la annulla. Chiavi e token restano nelle opzioni dell'add-on.")}</p>
      <p class="al-note" aria-live="polite">${esc(this.note)}</p>
      ${body}
    </section>`;
  }

  /** A dropdown whose first entry is "as in the add-on". */
  select(d, key, label, small, entries, addonLabel, disabled = false) {
    const over = d.overrides.includes(key);
    const current = over ? d.values[key] : ADDON;
    const opts = [[ADDON, t("Come nell'add-on ({v})", { v: addonLabel })], ...entries]
      .map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(current) ? "selected" : ""}>${esc(l)}</option>`).join("");
    return `<div class="al-row"><span>${label}${small ? `<small>${small}</small>` : ""}${over ? `<small class="st-set">${t("Impostato qui nella plancia")}</small>` : ""}</span>
      <select data-st="${key}" aria-label="${esc(label)}" ${disabled ? "disabled" : ""}>${opts}</select></div>`;
  }

  fieldsHTML(d) {
    const none = t("nessuna");
    const langName = { auto: t("Automatica (quella di Home Assistant)"), nl: "Nederlands", en: "English", it: "Italiano" };
    const language = this.select(d, "language", t("Lingua dell'assistente"), t("Assistente, agenti, Telegram e messaggi dell'add-on"),
      d.options.languages.map((l) => [l, langName[l] || l]), langName[d.addon.language] || d.addon.language);

    const engines = d.options.tts.map((x) => [x.e, `${x.n} (${x.e})`]);
    const engine = this.select(d, "voice_tts_entity", t("Voce da Home Assistant"), t("Il motore vocale per la plancia e per le notifiche a voce"),
      [["", t("Nessuno (ElevenLabs o niente)")], ...engines], d.addon.voice_tts_entity || none);

    const effective = d.values.voice_tts_entity;
    const list = this.voices[effective];
    let voice;
    if (!effective) {
      voice = `<div class="al-row"><span>${t("Nome della voce")}</span><span class="al-muted">${t("Scegli prima un motore vocale")}</span></div>`;
    } else {
      const names = Array.isArray(list) ? list.map((v) => [v.name, v.name]) : [];
      const cur = d.values.voice_tts_voice;
      if (cur && !names.some(([v]) => v === cur)) names.unshift([cur, cur]);
      voice = this.select(d, "voice_tts_voice", t("Nome della voce"), t("Le voci che il motore offre nella lingua di Home Assistant"),
        [["", t("Voce predefinita del motore")], ...names], d.addon.voice_tts_voice || t("Voce predefinita del motore"));
      if (list && list.error) voice += `<div class="al-row"><span></span><span class="al-muted">${t("Elenco delle voci non disponibile: {e}", { e: esc(list.error) })}</span></div>`;
    }

    const over = d.overrides.includes("calendar_entities");
    const chosen = new Set(d.values.calendar_entities);
    const cals = d.options.calendars.length
      ? d.options.calendars.map((c) => `<label class="al-check"><input type="checkbox" data-st-cal="${esc(c.e)}" ${chosen.has(c.e) ? "checked" : ""}>${esc(c.n)}<small>${esc(c.e)}</small></label>`).join("")
      : `<span class="al-muted">${t("Nessuna agenda trovata in Home Assistant.")}</span>`;
    const reset = over ? `<button type="button" class="hc-link" data-st-cal-reset>${t("Torna all'add-on")}</button>` : "";
    const calendars = `<div class="al-row"><span>${t("Agende consentite")}<small>${t("Gli agenti con lo strumento calendar_events leggono solo queste. Niente selezionato = tutte le agende.")}</small>${over ? `<small class="st-set">${t("Impostato qui nella plancia")}</small>` : ""}</span>
      <div class="al-phones">${cals}${reset}</div></div>`;

    return `<div class="al-where">${language}${engine}${voice}${calendars}</div>`;
  }
}
