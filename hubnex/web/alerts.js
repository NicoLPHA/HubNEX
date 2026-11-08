// Smart notifications popup (⚙ Preferenze → Notifiche della casa): which rules, where they
// arrive, quiet hours, what each rule looks at. Every change is saved at once.
import { t } from "./i18n.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const RULES = [
  ["safety", () => t("Perdite, fumo, gas"), () => t("Sensori di acqua, fumo, gas e monossido: avviso immediato, anche nelle ore di silenzio.")],
  ["windows", () => t("Finestre aperte"), () => t("Con il riscaldamento o il condizionatore acceso, o quando piove.")],
  ["away", () => t("Casa vuota"), () => t("Porte, cancello o serrature aperti quando tutti sono fuori casa. Con il pulsante Chiudi.")],
  ["power", () => t("Consumo alto"), () => t("La potenza della casa resta sopra la soglia. Usa il sensore di potenza dell'Energia.")],
  ["night", () => t("Luci accese di notte"), () => t("Luci ancora accese nella fascia notturna. Con il pulsante Spegni.")],
  ["battery", () => t("Batterie scariche"), () => t("Sensori e dispositivi con la batteria sotto la soglia.")],
  ["offline", () => t("Dispositivi non raggiungibili"), () => t("Dispositivi che non rispondono a Home Assistant da un po'.")],
  ["stock", () => t("Scorte da riordinare"), () => t("Pellet e altre scorte sotto la soglia impostata nella loro card.")],
];

export class AlertsView {
  constructor(api) {
    this.api = api;
    this.data = null;
    this.el = null;
    this.note = "";
    this.openList = new Set();
    addEventListener("keydown", (e) => { if (e.key === "Escape" && this.el) { e.stopImmediatePropagation(); this.close(); } }, true);
  }

  async open() {
    if (!this.el) {
      this.el = document.createElement("div");
      this.el.className = "casa-modal alerts-modal";
      this.el.setAttribute("role", "dialog");
      this.el.setAttribute("aria-label", t("Notifiche della casa"));
      this.el.addEventListener("click", (e) => this.onClick(e));
      this.el.addEventListener("change", (e) => this.onChange(e));
      document.body.appendChild(this.el);
      document.body.classList.add("casa-modal-open");
    }
    this.render();
    try {
      this.data = await (await this.api("/api/alerts")).json();
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

  async save() {
    try {
      this.data = await (await this.api("/api/alerts", { method: "PUT", body: JSON.stringify(this.data.cfg) })).json();
      this.note = t("Salvato");
    } catch (e) {
      this.note = `⚠ ${e.message || e}`;
    }
    this.render();
  }

  async onClick(e) {
    if (e.target === this.el || e.target.closest("[data-al-close]")) return this.close();
    const cfg = this.data?.cfg;
    if (!cfg) return;
    const sw = e.target.closest("[data-al-on]");
    if (sw) { cfg.rules[sw.dataset.alOn].on = !cfg.rules[sw.dataset.alOn].on; return this.save(); }
    const ch = e.target.closest("[data-al-ch]");
    if (ch) { const [rule, c] = ch.dataset.alCh.split(":"); cfg.rules[rule][c] = !cfg.rules[rule][c]; return this.save(); }
    const list = e.target.closest("[data-al-list]");
    if (list) { const r = list.dataset.alList; this.openList.has(r) ? this.openList.delete(r) : this.openList.add(r); return this.render(); }
    if (e.target.closest("[data-al-test]")) {
      this.note = t("Invio…");
      this.render();
      try {
        const { sent } = await (await this.api("/api/alerts/test", { method: "POST" })).json();
        this.note = sent.length ? t("Prova inviata a: {list}", { list: sent.join(", ") }) : t("Nessun canale attivo a cui inviarla");
      } catch (err) {
        this.note = `⚠ ${err.message || err}`;
      }
      this.render();
    }
  }

  onChange(e) {
    const cfg = this.data?.cfg;
    if (!cfg) return;
    const el = e.target;
    if (el.dataset.alNum) {
      const [rule, key] = el.dataset.alNum.split(":");
      cfg.rules[rule][key] = el.type === "time" ? el.value : Number(el.value);
    } else if (el.dataset.alQuiet) {
      cfg.quiet[el.dataset.alQuiet] = el.value;
    } else if (el.dataset.alPhone) {
      const all = this.data.phones.map((p) => p.service);
      const now = new Set(cfg.phones ?? all);
      el.checked ? now.add(el.dataset.alPhone) : now.delete(el.dataset.alPhone);
      cfg.phones = all.every((s) => now.has(s)) ? null : [...now];
    } else if (el.dataset.alEnt) {
      const ex = new Set(cfg.exclude);
      el.checked ? ex.delete(el.dataset.alEnt) : ex.add(el.dataset.alEnt);
      cfg.exclude = [...ex];
    } else return;
    this.save();
  }

  render() {
    if (!this.el) return;
    const d = this.data;
    let body = `<p class="al-note">${t("Carico…")}</p>`;
    if (d) body = this.activeHTML(d) + this.whereHTML(d) + RULES.map((r) => this.ruleHTML(d, ...r)).join("");
    this.el.innerHTML = `<section class="panel casa-panel alerts">
      <h3>${t("Notifiche della casa")}<span class="costs-head">
        <button type="button" class="hc-link" data-al-test>${t("Invia una prova")}</button>
        <button class="casa-x" data-al-close aria-label="${t("Chiudi")}">×</button></span></h3>
      <p class="al-intro">${t("HubNEX controlla la casa da solo, senza usare Claude. Ti avvisa una volta e toglie l'avviso quando il problema è risolto. Agisce solo se premi un pulsante della notifica.")}</p>
      <p class="al-note" aria-live="polite">${esc(this.note)}</p>
      ${body}
    </section>`;
  }

  activeHTML(d) {
    if (!d.active.length) return "";
    return `<div class="al-active"><h4>${t("Adesso")}</h4>${d.active.map((a) => `
      <div class="al-act ${a.urgent ? "urgent" : ""}"><b>${esc(a.title)}</b><span>${esc(a.text)}</span>${a.sent ? "" : `<small>${t("in attesa")}</small>`}</div>`).join("")}</div>`;
  }

  whereHTML(d) {
    const cfg = d.cfg;
    const phones = d.phones.length
      ? d.phones.map((p) => `<label class="al-check"><input type="checkbox" data-al-phone="${esc(p.service)}" ${cfg.phones === null || cfg.phones.includes(p.service) ? "checked" : ""}>${esc(p.name)}</label>`).join("")
      : `<span class="al-muted">${t("Nessun telefono con l'app di Home Assistant: installala e accedi, poi riapri questa finestra.")}</span>`;
    return `<div class="al-where">
      <div class="al-row"><span>${t("Telefoni (app Home Assistant)")}</span><div class="al-phones">${phones}</div></div>
      <div class="al-row"><span>${t("Telegram")}</span><span class="al-muted">${d.telegram ? t("Gruppo collegato") : t("Non configurato: le regole con Telegram usano solo gli altri canali")}</span></div>
      <div class="al-row"><span>${t("Ore di silenzio")}<small>${t("Tranne perdite, fumo e gas. Vuoto = sempre attive")}</small></span>
        <span class="al-times"><input type="time" data-al-quiet="from" value="${esc(cfg.quiet.from)}" aria-label="${t("Dalle")}"> – <input type="time" data-al-quiet="to" value="${esc(cfg.quiet.to)}" aria-label="${t("Alle")}"></span></div>
    </div>`;
  }

  ruleHTML(d, id, title, desc) {
    const r = d.cfg.rules[id];
    const watched = d.watched[id] || [];
    const on = watched.filter((w) => !d.cfg.exclude.includes(w.e)).length;
    const chip = (c, label, disabled) => `<button type="button" class="al-chip ${r[c] ? "on" : ""}" data-al-ch="${id}:${c}" aria-pressed="${!!r[c]}" ${disabled ? "disabled" : ""}>${label}</button>`;
    const num = (key, min, max, step = 1) => `<input type="number" class="al-num" data-al-num="${id}:${key}" value="${r[key]}" min="${min}" max="${max}" step="${step}" aria-label="${key}">`;
    const params = [];
    if (id === "power") params.push(t("Sopra {v} W", { v: num("watts", 100, 100000, 100) }));
    if (id === "night") params.push(t("Dalle {a} alle {b}", { a: `<input type="time" data-al-num="night:at" value="${r.at}">`, b: `<input type="time" data-al-num="night:until" value="${r.until}">` }));
    if (id === "battery") params.push(t("Sotto il {v}%", { v: num("percent", 1, 99) }));
    if ("minutes" in r) params.push(t("Dopo {v} minuti", { v: num("minutes", 0, 1440) }));
    const list = this.openList.has(id)
      ? `<div class="al-ents">${watched.map((w) => `<label class="al-check"><input type="checkbox" data-al-ent="${esc(w.e)}" ${d.cfg.exclude.includes(w.e) ? "" : "checked"}>${esc(w.n)}<small>${esc(w.e)}</small></label>`).join("") || `<span class="al-muted">${t("Nessuna entità adatta in Home Assistant")}</span>`}</div>`
      : "";
    return `<div class="al-rule ${r.on ? "" : "off"}">
      <div class="al-head">
        <button type="button" class="casa-switch ${r.on ? "on" : ""}" data-al-on="${id}" role="switch" aria-checked="${r.on}" aria-label="${esc(title())}"></button>
        <div><b>${title()}</b><small>${desc()}</small></div>
      </div>
      <div class="al-body">
        <div class="al-chips">${chip("app", t("App"))}${chip("telegram", "Telegram", !d.telegram)}${chip("ha", t("Home Assistant"))}</div>
        ${params.length ? `<div class="al-params">${params.join("")}</div>` : ""}
        <button type="button" class="hc-link" data-al-list="${id}" aria-expanded="${this.openList.has(id)}">${id === "power" && !watched.length ? t("Nessun sensore di potenza: sceglilo in Energia → Configura") : t("Controlla {n} di {tot}", { n: on, tot: watched.length })}</button>
        ${list}
      </div>
    </div>`;
  }
}
