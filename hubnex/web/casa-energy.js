// The house's energy panel, opened from "Energia" in the dashboard. Three views the owner picks
// from (the reactor, the day, the bill), over the sensors they choose: kWh per time band
// (F1/F2/F3), prices or cost, power now, any other reading. Mixed into CasaView.

import { esc, num } from "./casa-cards.js";

const BANDS = ["F1", "F2", "F3"];
const BAND_COLOR = { F1: "#4fa3ff", F2: "#f2c14e", F3: "#8b7cf6" };
const VIEWS = [["reactor", "Il reattore"], ["day", "La giornata"], ["bill", "La bolletta"]];
const BAND_HINT = {
  F1: "Sono le ore diurne dei giorni feriali (8-19): gli elettrodomestici a orario si possono spostare la sera o nel weekend.",
  F2: "Sono le sere e il sabato: se lavatrice o lavastoviglie partono dopo le 23, passano in F3.",
};

// ARERA bands (also computed by the add-on): F1 working days 8-19, F2 7-8 / 19-23 and Saturday 7-23, F3 the rest.
function easter(y) {
  const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31), day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(y, month - 1, day);
}
function holiday(d) {
  const md = `${d.getMonth() + 1}-${d.getDate()}`;
  if (["1-1", "1-6", "4-25", "5-1", "6-2", "8-15", "11-1", "12-8", "12-25", "12-26"].includes(md)) return true;
  const em = easter(d.getFullYear());
  em.setDate(em.getDate() + 1);
  return em.toDateString() === d.toDateString();
}
function areraBand(d, hour) {
  if (d.getDay() === 0 || holiday(d)) return "F3";
  if (d.getDay() === 6) return hour >= 7 && hour < 23 ? "F2" : "F3";
  if (hour >= 8 && hour < 19) return "F1";
  return hour === 7 || (hour >= 19 && hour < 23) ? "F2" : "F3";
}

export const Energy = {
  // ---------------------------------------------------------------- data
  ecfg() { return this.data?.energy_panel || {}; },

  eNum(eid) { const s = eid && this.st(eid); const v = s ? parseFloat(s.s) : NaN; return isNaN(v) ? null : v; },

  // The billing period: from the meters (last_reset, meter_period), else the calendar.
  ePeriod() {
    const cfg = this.ecfg();
    const ref = [...Object.values(cfg.bands || {}), cfg.total, cfg.cost].map((e) => e && this.st(e)).find((s) => s?.a?.last_reset);
    const now = new Date();
    let start, months = cfg.cycle === "monthly" ? 1 : 2;
    if (ref) {
      start = new Date(ref.a.last_reset);
      months = { monthly: 1, bimonthly: 2, quarterly: 3, yearly: 12 }[ref.a.meter_period] || months;
    } else {
      start = new Date(now.getFullYear(), months === 2 ? now.getMonth() - (now.getMonth() % 2) : now.getMonth(), 1);
    }
    const end = new Date(start);
    end.setMonth(end.getMonth() + months);
    const frac = Math.min(1, Math.max(0, (now - start) / (end - start)));
    const day = Math.max(1, Math.ceil((now - start) / 864e5)), days = Math.round((end - start) / 864e5);
    return { start, end, frac, day, days, name: months === 2 ? "bimestre" : months === 1 ? "mese" : "periodo" };
  },

  eData() {
    const cfg = this.ecfg(), period = this.ePeriod();
    const trend = (cur, last) => (cur != null && last > 0 && period.frac > 0.03 ? cur / (last * period.frac) - 1 : null);
    const bands = cfg.band_mode === "single" ? [] : BANDS.filter((b) => cfg.bands?.[b] && this.st(cfg.bands[b])).map((b) => {
      const s = this.st(cfg.bands[b]), kwh = this.eNum(cfg.bands[b]);
      return { name: b, kwh, last: parseFloat(s.a.last_period), price: this.eNum(cfg.prices?.[b]) };
    });
    bands.forEach((b) => { b.trend = trend(b.kwh, b.last); });
    const total = bands.length ? bands.reduce((s, b) => s + (b.kwh || 0), 0) : this.eNum(cfg.total);
    const lastTotal = bands.length ? bands.reduce((s, b) => s + (b.last || 0), 0) : parseFloat(this.st(cfg.total)?.a?.last_period);
    let cost = this.eNum(cfg.cost);
    if (cost == null && bands.length && bands.every((b) => b.price != null)) cost = bands.reduce((s, b) => s + (b.kwh || 0) * b.price, 0);
    const watts = (() => {
      const s = cfg.power && this.st(cfg.power), v = this.eNum(cfg.power);
      return v == null ? null : v * (/kw/i.test(s.a.unit_of_measurement || "") ? 1000 : 1);
    })();
    let now = this.energyLive?.band?.name || null, until = this.energyLive?.band?.until || null;
    if (cfg.band_mode === "sensor") { now = (String(this.st(cfg.band_sensor)?.s || "").toUpperCase().match(/F[123]/) || [null])[0]; until = null; }
    if (cfg.band_mode === "single") now = null;
    return { cfg, period, bands, total, totalTrend: trend(total, lastTotal), cost, projection: cost != null && period.frac > 0.03 ? cost / period.frac : null, watts, now, until };
  },

  async loadEnergy() {
    try {
      this.energyLive = await (await this.api("/api/casa/energy")).json();
    } catch { this.energyLive ||= {}; }
    if (this.energyOpen) this.render();
  },

  // ---------------------------------------------------------------- the panel
  energyHTML() {
    const d = this.eData();
    const configured = d.watts != null || d.bands.length || d.total != null;
    const views = (d.cfg.views || []).filter(() => configured);
    const body = this.energyEdit ? this.energyCfgHTML()
      : views.length ? views.map((v) => ({ reactor: () => this.reactorHTML(d), day: () => this.dayHTML(d), bill: () => this.billHTML(d) })[v]?.() || "").join("")
      : `<p class="casa-muted">${configured ? "Nessuna vista scelta." : "Il pannello non è ancora configurato: scegli i sensori di consumo, fasce e potenza."} <button class="hc-link" data-act="energy-cfg">Configura</button></p>`;
    return `<div class="casa-modal" role="dialog" aria-label="Energia"><section class="panel casa-panel hc-dialog hc-energy">
      <h3>${this.energyEdit ? "Configura il pannello Energia" : "Energia"}<span class="hc-energy-actions">${this.energyEdit ? "" : `<button class="hc-link" data-act="energy-cfg">Configura</button>`}<button class="casa-x" data-act="energy-close" aria-label="Chiudi">×</button></span></h3>
      ${body}
    </section></div>`;
  },

  trendHTML(t) {
    if (t == null) return "";
    const pct = `${t > 0 ? "+" : "−"}${num(Math.abs(t) * 100)}%`;
    return `<span class="${t > 0 ? "e-up" : "e-down"}">${pct}</span>`;
  },

  readoutsHTML(d, cls = "e-ro") {
    return (d.cfg.readouts || []).filter((e) => this.st(e)).map((e) => {
      const s = this.st(e);
      return `<div class="${cls}"><span class="hc-state">${esc(s.n.toLowerCase())}</span><span class="hc-num">${esc(this.value(e))}</span></div>`;
    }).join("");
  },

  // A · the reactor: the period split by band around the power now.
  reactorHTML(d) {
    const C = 2 * Math.PI * 160, total = d.bands.reduce((s, b) => s + (b.kwh || 0), 0);
    let offset = 0;
    const segs = d.bands.length && total > 0
      ? d.bands.map((b) => {
          const len = Math.max(0, ((b.kwh || 0) / total) * C - 4);
          const seg = `<circle cx="200" cy="200" r="160" stroke="${BAND_COLOR[b.name]}" stroke-dasharray="${len.toFixed(1)} ${C.toFixed(1)}" stroke-dashoffset="${(-offset).toFixed(1)}"/>${b.name === d.now ? `<circle class="e-pulse" cx="200" cy="200" r="160" stroke="${BAND_COLOR[b.name]}" stroke-dasharray="${len.toFixed(1)} ${C.toFixed(1)}" stroke-dashoffset="${(-offset).toFixed(1)}"/>` : ""}`;
          offset += ((b.kwh || 0) / total) * C;
          return seg;
        }).join("")
      : `<circle cx="200" cy="200" r="160" stroke="var(--accent)" stroke-dasharray="${C.toFixed(1)} ${C.toFixed(1)}" opacity=".5"/>`;
    const contract = (d.cfg.contract_kw || 3) * 1000, ci = 2 * Math.PI * 122;
    const p = d.watts != null ? Math.min(1, d.watts / contract) : 0;
    let ticks = "";
    for (let i = 0; i < 72; i++) {
      const a = (i / 72) * 2 * Math.PI, r1 = 178, r2 = i % 6 ? 174 : 170;
      ticks += `<line x1="${(200 + r1 * Math.cos(a)).toFixed(1)}" y1="${(200 + r1 * Math.sin(a)).toFixed(1)}" x2="${(200 + r2 * Math.cos(a)).toFixed(1)}" y2="${(200 + r2 * Math.sin(a)).toFixed(1)}"/>`;
    }
    const labels = d.bands.map((b, i) => `<span style="color:${BAND_COLOR[b.name]}">${b.name} · ${b.kwh != null ? num(b.kwh) : "—"} kWh</span>`).join("");
    return `<div class="e-view e-reactor">
      <div class="e-rwrap"><svg viewBox="0 0 400 400" aria-label="Reattore dell'energia">
        <g class="e-ticks">${ticks}</g>
        <g fill="none" stroke-width="10" transform="rotate(-90 200 200)"><circle cx="200" cy="200" r="160" stroke="rgba(255,255,255,.05)"/>${segs}</g>
        <g fill="none" stroke-width="4" transform="rotate(-90 200 200)"><circle cx="200" cy="200" r="122" stroke="rgba(255,255,255,.06)"/>
          <circle cx="200" cy="200" r="122" stroke="${p > 0.9 ? "var(--danger)" : "var(--accent)"}" stroke-linecap="round" stroke-dasharray="${(p * ci).toFixed(1)} ${ci.toFixed(1)}"/></g>
        <circle cx="200" cy="200" r="96" fill="rgba(79,209,255,.04)" stroke="rgba(79,209,255,.2)"/>
        <text x="200" y="184" text-anchor="middle" class="e-k">ADESSO</text>
        <text x="200" y="226" text-anchor="middle" class="e-big">${d.watts != null ? num(d.watts, 0) : "—"}</text>
        <text x="200" y="250" text-anchor="middle" class="e-s">watt${d.watts != null ? ` · ${num(p * 100, 0)}% del contatore` : ""}</text>
      </svg><div class="e-labels">${labels}</div></div>
      <div class="e-readouts">
        ${d.now ? `<div class="e-ro now"><span class="hc-state">fascia adesso</span><span class="hc-num">${d.now}${d.until ? ` <small>fino alle ${d.until}</small>` : ""}</span></div>` : ""}
        ${d.total != null ? `<div class="e-ro"><span class="hc-state">${d.period.name}</span><span class="hc-num">${num(d.total)}<small>kWh</small>${d.cost != null ? ` · ${num(d.cost, 2)}<small>€</small>` : ""}</span>${d.totalTrend != null ? `<span class="hc-state">${this.trendHTML(d.totalTrend)} sul ${d.period.name} scorso</span>` : ""}</div>` : ""}
        ${this.readoutsHTML(d)}
      </div>
    </div>`;
  },

  // B · the day: today's power over the time bands.
  dayHTML(d) {
    const day = this.energyLive?.day;
    const W = 720, H = 230, x0 = 34, x1 = 710, y0 = 22, y1 = 180;
    const x = (min) => x0 + (min / 1440) * (x1 - x0);
    const pts = day?.points || [];
    const max = Math.max((d.cfg.contract_kw || 3) * 1000, ...pts.map((p) => p[1]), 1);
    const y = (w) => y1 - (w / max) * (y1 - y0);
    let bg = "";
    if (d.cfg.band_mode === "arera") {
      const today = new Date();
      let from = 0, band = areraBand(today, 0);
      for (let h = 1; h <= 24; h++) {
        const b = h < 24 ? areraBand(today, h) : null;
        if (b !== band) {
          bg += `<rect x="${x(from * 60).toFixed(1)}" y="${y0}" width="${(x(h * 60) - x(from * 60)).toFixed(1)}" height="${y1 - y0}" fill="${BAND_COLOR[band]}" opacity=".13"/>
            ${h - from >= 2 ? `<text x="${((x(from * 60) + x(h * 60)) / 2).toFixed(1)}" y="${y0 + 16}" text-anchor="middle" fill="${BAND_COLOR[band]}" class="e-s">${band}</text>` : ""}`;
          from = h; band = b;
        }
      }
    }
    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)} ${y(p[1]).toFixed(1)}`).join(" ");
    const area = pts.length ? `${line} L${x(pts[pts.length - 1][0]).toFixed(1)} ${y1} L${x(pts[0][0]).toFixed(1)} ${y1} Z` : "";
    const nowX = x(day?.now_min ?? 0);
    const grid = [0.25, 0.5, 0.75].map((f) => `<line x1="${x0}" y1="${y(max * f).toFixed(1)}" x2="${x1}" y2="${y(max * f).toFixed(1)}"/><text x="0" y="${(y(max * f) + 4).toFixed(1)}" class="e-s">${num((max * f) / 1000)}${f === 0.75 ? " kW" : ""}</text>`).join("");
    const todayKwh = day?.kwh ? Object.values(day.kwh).reduce((s, v) => s + v, 0) : null;
    return `<div class="e-view e-day">
      <svg viewBox="0 0 ${W} ${H}" aria-label="Potenza di oggi">${bg}
        <g class="e-grid">${grid}</g>
        <g class="e-s">${[0, 6, 12, 18, 24].map((h) => `<text x="${x(h * 60).toFixed(1)}" y="${H - 28}" text-anchor="middle">${h}</text>`).join("")}</g>
        ${pts.length ? `<path d="${area}" class="e-area"/><path d="${line}" class="e-line"/>
          <line x1="${nowX.toFixed(1)}" y1="${y0}" x2="${nowX.toFixed(1)}" y2="${y1}" class="e-now"/>
          ${d.watts != null ? `<text x="${Math.min(nowX + 6, W - 120).toFixed(1)}" y="${y0 + 36}" class="e-nowtxt">adesso ${num(d.watts, 0)} W</text>` : ""}`
        : `<text x="${W / 2}" y="${(y0 + y1) / 2}" text-anchor="middle" class="e-s">${d.cfg.power ? "Carico la giornata…" : "Scegli il sensore della potenza in Configura."}</text>`}
      </svg>
      <div class="e-stats">
        <div><span class="hc-state">oggi</span><span class="hc-num">${todayKwh != null ? num(todayKwh) : "—"} <small>kWh</small></span>${day?.kwh && d.cfg.band_mode === "arera" ? `<span class="hc-state">${BANDS.map((b) => `${b} ${num(day.kwh[b])}`).join(" · ")}</span>` : ""}</div>
        ${d.total != null ? `<div><span class="hc-state">${d.period.name}</span><span class="hc-num">${num(d.total)} <small>kWh</small></span>${d.totalTrend != null ? `<span class="hc-state">${this.trendHTML(d.totalTrend)} sul precedente</span>` : ""}</div>` : ""}
        ${d.cost != null ? `<div><span class="hc-state">spesa</span><span class="hc-num">${num(d.cost, 2)} <small>€</small></span>${d.projection != null ? `<span class="hc-state">fine ${d.period.name} ≈ ${num(d.projection, 0)} €</span>` : ""}</div>` : ""}
        ${this.readoutsHTML(d, "e-stat")}
      </div>
    </div>`;
  },

  // C · the bill: what you will pay, the bands compared, a hint when one grows.
  billHTML(d) {
    const total = d.bands.reduce((s, b) => s + (b.kwh || 0), 0);
    const up = d.cfg.band_mode === "arera" ? d.bands.filter((b) => b.trend > 0.25 && BAND_HINT[b.name]).sort((a, b) => b.trend - a.trend)[0] : null;
    const head = d.cost != null
      ? `<div><span class="hc-kick">${d.period.name} in corso · giorno ${d.period.day} di ${d.period.days}</span><div class="e-bill">${num(d.cost, 2)}<small> €</small></div></div>
         ${d.projection != null ? `<div class="e-proj"><span class="hc-state">al ritmo di oggi</span><span class="hc-num">≈ ${num(d.projection, 0)} € a fine ${d.period.name}</span>${d.totalTrend != null ? `<span class="hc-state">${this.trendHTML(d.totalTrend)} rispetto al ${d.period.name} scorso</span>` : ""}</div>` : ""}`
      : `<div><span class="hc-kick">${d.period.name} in corso · giorno ${d.period.day} di ${d.period.days}</span><div class="e-bill">${d.total != null ? num(d.total) : "—"}<small> kWh</small></div></div>
         <div class="e-proj"><span class="hc-state">per la stima in euro scegli i prezzi o la spesa in Configura</span></div>`;
    return `<div class="e-view e-billview">
      <div class="e-billhead">${head}</div>
      <div class="e-track" aria-hidden="true"><i class="done" style="width:${(d.period.frac * 100).toFixed(1)}%"></i><i class="proj" style="left:${(d.period.frac * 100).toFixed(1)}%;width:${(100 - d.period.frac * 100).toFixed(1)}%"></i>
        ${d.period.frac < 0.9 ? `<b style="left:${(d.period.frac * 100).toFixed(1)}%"><span>oggi</span></b>` : ""}<b style="left:100%"><span>fine</span></b></div>
      ${d.bands.length ? `<div class="e-rows">${d.bands.map((b) => `<div class="e-row ${b.name === d.now ? "now" : ""}"><span>${b.name}${b.name === d.now ? " · ora" : ""}</span>
          <span class="e-bar"><i style="width:${total ? ((b.kwh || 0) / total) * 100 : 0}%;background:${BAND_COLOR[b.name]}"></i></span>
          <span class="hc-num">${b.kwh != null ? num(b.kwh) : "—"} <small>kWh</small></span><span class="e-trend">${this.trendHTML(b.trend)}</span><span class="hc-state">${total ? num(((b.kwh || 0) / total) * 100, 0) : 0}%</span></div>`).join("")}</div>` : ""}
      ${up ? `<div class="e-tip"><b>${up.name} è salita del ${num(up.trend * 100, 0)}%.</b> ${BAND_HINT[up.name]}</div>` : ""}
      <div class="e-mini">${d.watts != null ? `<span>adesso <b>${num(d.watts, 0)} W</b></span>` : ""}${(d.cfg.readouts || []).filter((e) => this.st(e)).map((e) => `<span>${esc(this.st(e).n.toLowerCase())} <b>${esc(this.value(e))}</b></span>`).join("")}</div>
    </div>`;
  },

  // ---------------------------------------------------------------- configuration
  ePickField(field, label, hint = "") {
    const c = this.energyEdit;
    const val = field.startsWith("bands.") ? c.bands[field.slice(6)] : field.startsWith("prices.") ? c.prices[field.slice(7)] : c[field];
    const picking = this.ePick === field;
    return `<div class="e-field"><span>${label}</span><span class="e-pickval">
      <button class="e-ent" data-act="epick" data-f="${field}">${val ? `${esc(this.st(val)?.n || val)} <small>${esc(val)}</small>` : `<small>${hint || "scegli…"}</small>`}</button>
      ${val ? `<button class="hc-link" data-act="epick-clear" data-f="${field}" aria-label="Togli">togli</button>` : ""}</span></div>
      ${picking ? this.ePickerHTML() : ""}`;
  },

  ePickerHTML() {
    return `<div class="e-picker"><input id="epick-find" class="hc-input" placeholder="cerca per nome o entity_id…" value="${esc(this.ePickQ || "")}" autocomplete="off">
      <div class="hc-cands" id="epick-cands">${this.ePickCandsHTML()}</div></div>`;
  },

  ePickCandsHTML() {
    return (this.ePickCands || []).slice(0, 10).map((x) => `<button class="hc-cand" data-act="epick-set" data-e="${esc(x.entity_id)}"><span>${esc(x.name)}</span><span class="mono">${esc(x.entity_id)}</span></button>`).join("") || `<p class="casa-muted">Scrivi per cercare.</p>`;
  },

  async ePickSearch(q) {
    this.ePickQ = q;
    try { this.ePickCands = await (await this.api(`/api/casa/entities?all=1&q=${encodeURIComponent(q)}`)).json(); } catch { this.ePickCands = []; }
    const box = this.root.querySelector("#epick-cands");
    if (box) box.innerHTML = this.ePickCandsHTML();
  },

  eSet(field, eid) {
    const c = this.energyEdit;
    if (field === "readouts+") { if (eid && !c.readouts.includes(eid)) c.readouts.push(eid); }
    else if (field.startsWith("bands.")) { if (eid) c.bands[field.slice(6)] = eid; else delete c.bands[field.slice(6)]; }
    else if (field.startsWith("prices.")) { if (eid) c.prices[field.slice(7)] = eid; else delete c.prices[field.slice(7)]; }
    else c[field] = eid || null;
  },

  energyCfgHTML() {
    const c = this.energyEdit;
    const tab = (act, value, label, cur) => `<button class="hc-tab ${cur === value ? "sel" : ""}" data-act="${act}" data-v="${value}">${label}</button>`;
    return `<div class="e-cfg">
      <section><span class="hc-kick">Viste da mostrare</span>
        <div class="e-views">${VIEWS.map(([v, label]) => `<label class="e-vtog"><button class="casa-switch ${c.views.includes(v) ? "on" : ""}" data-act="eview" data-v="${v}" role="switch" aria-checked="${c.views.includes(v)}" aria-label="${label}"></button>${label}</label>`).join("")}</div></section>
      <section><span class="hc-kick">Fascia oraria</span>
        <div class="hc-tabs">${tab("eband", "arera", "Calendario ARERA (F1/F2/F3)", c.band_mode)}${tab("eband", "sensor", "Da un mio sensore", c.band_mode)}${tab("eband", "single", "Tariffa unica", c.band_mode)}</div>
        ${c.band_mode === "sensor" ? this.ePickField("band_sensor", "Fascia", "entità con stato F1 / F2 / F3") : ""}
        ${c.band_mode === "arera" ? `<p class="casa-muted">Calcolata da HubNEX, festivi nazionali compresi.</p>` : ""}</section>
      ${c.band_mode === "single"
        ? `<section><span class="hc-kick">Consumo</span>${this.ePickField("total", "kWh del periodo", "es. un contatore di Home Assistant")}</section>`
        : `<section><span class="hc-kick">Consumo per fascia (kWh del periodo)</span>
            ${BANDS.map((b) => this.ePickField(`bands.${b}`, b)).join("")}
            <span class="hc-kick" style="margin-top:8px">Prezzi €/kWh (facoltativi)</span>
            ${BANDS.map((b) => this.ePickField(`prices.${b}`, b, "es. input_number")).join("")}</section>`}
      <section><span class="hc-kick">Spesa e periodo</span>
        ${this.ePickField("cost", "Spesa €", "facoltativo: se Home Assistant la calcola")}
        <div class="e-field"><span>Periodo</span><span class="hc-tabs">${tab("ecycle", "monthly", "mese", c.cycle)}${tab("ecycle", "bimonthly", "bimestre", c.cycle)}</span></div>
        <p class="casa-muted">Se i contatori sono "utility meter" di Home Assistant, inizio del periodo e confronto col precedente vengono da loro.</p></section>
      <section><span class="hc-kick">Potenza</span>
        ${this.ePickField("power", "Adesso (W)")}
        <div class="e-field"><span>Contatore</span><span><input id="e-contract" class="hc-input e-kw" type="number" min="0.5" max="100" step="0.5" value="${c.contract_kw}"> kW</span></div></section>
      <section><span class="hc-kick">Altri valori</span>
        ${c.readouts.map((e) => `<div class="e-field"><span></span><span class="e-pickval"><span class="e-ent">${esc(this.st(e)?.n || e)} <small>${esc(e)}</small></span><button class="hc-link" data-act="eread-rm" data-e="${esc(e)}">togli</button></span></div>`).join("")}
        <button class="hc-link" data-act="epick" data-f="readouts+">+ aggiungi (tensione, fattore di potenza, energia prelevata…)</button>
        ${this.ePick === "readouts+" ? this.ePickerHTML() : ""}</section>
      <div class="casa-actions"><button class="hc-btn primary" data-act="ecfg-save">Salva</button><button class="hc-link" data-act="ecfg-cancel">Annulla</button></div>
    </div>`;
  },

  // Returns true when it handled the click.
  async energyClick(act, el) {
    const c = this.energyEdit;
    switch (act) {
      case "energy":
        this.energyOpen = true; this.energyEdit = null;
        this.loadEnergy();
        clearInterval(this._energyTimer);
        this._energyTimer = setInterval(() => (this.energyOpen && this.visible ? this.loadEnergy() : clearInterval(this._energyTimer)), 60000);
        break;
      case "energy-close": this.energyOpen = false; this.energyEdit = null; clearInterval(this._energyTimer); break;
      case "energy-cfg": {
        const cur = this.ecfg();
        this.energyEdit = JSON.parse(JSON.stringify({ views: [], bands: {}, prices: {}, readouts: [], band_mode: "arera", cycle: "bimonthly", contract_kw: 3, ...cur }));
        this.ePick = null;
        break;
      }
      case "ecfg-cancel": this.energyEdit = null; this.ePick = null; break;
      case "eview": c.views = c.views.includes(el.dataset.v) ? c.views.filter((v) => v !== el.dataset.v) : VIEWS.map(([v]) => v).filter((v) => v === el.dataset.v || c.views.includes(v)); break;
      case "eband": c.band_mode = el.dataset.v; break;
      case "ecycle": c.cycle = el.dataset.v; break;
      case "epick": this.ePick = this.ePick === el.dataset.f ? null : el.dataset.f; this.ePickQ = ""; this.ePickCands = []; break;
      case "epick-clear": this.eSet(el.dataset.f, null); break;
      case "epick-set": {
        const cand = (this.ePickCands || []).find((x) => x.entity_id === el.dataset.e);
        if (cand?.state && !this.data.states[cand.entity_id]) this.data.states[cand.entity_id] = cand.state;
        this.eSet(this.ePick, el.dataset.e);
        this.ePick = null;
        break;
      }
      case "eread-rm": c.readouts = c.readouts.filter((e) => e !== el.dataset.e); break;
      case "ecfg-save": {
        const kw = parseFloat(this.root.querySelector("#e-contract")?.value);
        if (!isNaN(kw)) c.contract_kw = kw;
        try {
          await this.api("/api/casa/energy/config", { method: "POST", body: JSON.stringify(c) });
          this.energyEdit = null; this.ePick = null;
          this.toast("Pannello Energia salvato");
          await this.reload(true);
          this.loadEnergy();
        } catch (err) { this.toast(`⚠ ${err.message}`); }
        return true;
      }
      default: return false;
    }
    if (c && act !== "energy-cfg") { const kw = parseFloat(this.root.querySelector("#e-contract")?.value); if (!isNaN(kw)) c.contract_kw = kw; }
    this.render(true);
    return true;
  },
};
