// The house view's cards, in the HQ's holographic style: a dashboard (HUD) at the top of the
// house, a card drawn for each kind of entity, and the quick card of a room. Mixed into
// CasaView (casa.js), so `this` is the view: st(), value(), call()…

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
import { t, num, LOCALE } from "./i18n.js";
export { num };
const OPENING = new Set(["door", "window", "opening", "garage_door"]);
const DANGER = new Set(["smoke", "moisture", "gas", "safety", "problem", "carbon_monoxide"]);
const PRESENCE = new Set(["motion", "occupancy", "presence"]);
const HVAC = { heat: t("Caldo"), cool: t("Freddo"), auto: "Auto", heat_cool: "Auto", off: t("Spento"), dry: t("Deum."), fan_only: t("Ventola") };
const ACTION = { heating: t("Scalda"), cooling: t("Raffredda"), idle: t("In attesa"), off: "", drying: t("Deumidifica"), fan: t("Ventola") };

// Thin line icons (the colour comes from the text).
const PATHS = {
  bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
  plug: '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
  lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  unlock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 7.6-1.7"/>',
  shield: '<path d="M12 2.8 4.5 5.6v5.7c0 4.6 3.1 8.6 7.5 9.9 4.4-1.3 7.5-5.3 7.5-9.9V5.6Z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
  window: '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M12 3v18M4 12h16"/>',
  door: '<path d="M6 21V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17M4 21h16"/><circle cx="15" cy="12" r=".8"/>',
  drop: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>',
  flame: '<path d="M12 21a6 6 0 0 0 6-6c0-4-3-6-4-10-2 2-3 4-3 6-1-1-2-2-2-4-2 2-3 5-3 8a6 6 0 0 0 6 6z"/>',
  therm: '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/>',
  motion: '<circle cx="13" cy="4" r="2"/><path d="m9 21 2-6 3 3v3M7 12l3-4 4 1 3 3M10 8l-2 5"/>',
  gate: '<path d="M3 21V7l9-4 9 4v14M7 21v-9h10v9M7 15h10"/>',
  media: '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M10 9l5 3-5 3z"/>',
  fan: '<circle cx="12" cy="12" r="2"/><path d="M12 10c0-4 1-7 4-7 2 0 2 3-1 5M14 12c4 0 7 1 7 4 0 2-3 2-5-1M12 14c0 4-1 7-4 7-2 0-2-3 1-5M10 12c-4 0-7-1-7-4 0-2 3-2 5 1"/>',
  siren: '<path d="M7 18v-6a5 5 0 0 1 10 0v6M5 18h14v3H5zM12 3v2M4.2 6.2l1.4 1.4M19.8 6.2l-1.4 1.4"/>',
  gauge: '<path d="M4 18a8 8 0 1 1 16 0"/><path d="m12 14 4-5"/>',
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  cam: '<path d="M3 7.5h3l1.6-2.2h6.8L16 7.5h3a1.5 1.5 0 0 1 1.5 1.5v8.5A1.5 1.5 0 0 1 19 19H3a1.5 1.5 0 0 1-1.5-1.5V9A1.5 1.5 0 0 1 3 7.5Z"/><circle cx="11" cy="13" r="3.4"/>',
  play: '<path d="M8 5v14l11-7z" fill="currentColor"/>',
  pause: '<path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor"/>',
  prev: '<path d="M6 6h2v12H6zM9.5 12 18 6v12z" fill="currentColor"/>',
  next: '<path d="M16 6h2v12h-2zM6 6l8.5 6L6 18z" fill="currentColor"/>',
  power: '<path d="M12 3v9M6.3 6.3a8 8 0 1 0 11.4 0"/>',
  robot: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M8 5.6h8"/>',
  dock: '<path d="M4 20h16M6 20V10l6-5 6 5v10"/><path d="M10 20v-5h4v5"/>',
  target: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  shuffle: '<path d="M3 7h3c4 0 6 10 10 10h5M3 17h3c1.5 0 2.7-1.4 3.7-3.2M14.3 10.2C15.3 8.4 16.5 7 18 7h3M18 4l3 3-3 3M18 14l3 3-3 3"/>',
  repeat: '<path d="M4 11V9a3 3 0 0 1 3-3h12M16 3l3 3-3 3M20 13v2a3 3 0 0 1-3 3H5M8 21l-3-3 3-3"/>',
  vol: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6"/>',
  mute: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="m16 9.5 5 5M21 9.5l-5 5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  cloud: '<path d="M7 18h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 18z"/>',
  partly: '<path d="M8 4.5V3M3.6 6.1 2.5 5M3 10H1.5M12.4 6.1 13.5 5"/><path d="M5.3 11.5a3.5 3.5 0 0 1 6.4-2.8"/><path d="M9 20h8a3.5 3.5 0 0 0 .4-7 5 5 0 0 0-9.6 1.4A2.8 2.8 0 0 0 9 20z"/>',
  rain: '<path d="M7 15h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 15z"/><path d="m8 18-1 3M12 18l-1 3M16 18l-1 3"/>',
  snow: '<path d="M7 15h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 15z"/><path d="M8 19h.01M12 21h.01M16 19h.01"/>',
  storm: '<path d="M7 15h10a4 4 0 0 0 .5-8 6 6 0 0 0-11.4 1.6A3.3 3.3 0 0 0 7 15z"/><path d="m12 15-2 4h4l-2 4"/>',
  fog: '<path d="M4 9h16M2 13h20M5 17h14"/>',
  wind: '<path d="M3 9h11a3 3 0 1 0-3-3M3 15h15a3 3 0 1 1-3 3M3 12h8"/>',
  note: '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
  washer: '<rect x="4" y="2.5" width="16" height="19" rx="2"/><circle cx="12" cy="13" r="5"/><path d="M7.5 6h.01M10.5 6h.01"/>',
  cal: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
};
// Home Assistant's weather conditions: icon and words.
const WX = {
  "clear-night": ["moon", t("Sereno")], sunny: ["sun", t("Soleggiato")], partlycloudy: ["partly", t("Poco nuvoloso")],
  cloudy: ["cloud", t("Nuvoloso")], fog: ["fog", t("Nebbia")], rainy: ["rain", t("Pioggia")], pouring: ["rain", t("Pioggia forte")],
  snowy: ["snow", t("Neve")], "snowy-rainy": ["snow", t("Neve e pioggia")], hail: ["rain", t("Grandine")],
  lightning: ["storm", t("Temporale")], "lightning-rainy": ["storm", t("Temporale")], windy: ["wind", t("Vento")],
  "windy-variant": ["wind", t("Vento")], exceptional: ["gauge", t("Allerta meteo")],
};
// Appliances worth a line while they run (and just after they finish), by name.
const APPLIANCE = /lavatric|lavastovigl|asciugatric|forno|bollitore|washing|dishwash|dryer|oven|kettle/i;
const LAUNDRY = /lavatric|lavastovigl|asciugatric|washing|dishwash|dryer/i; // the ones with an icon on the plan
export function ago(iso) {
  if (!iso) return "";
  const m = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (m < 1) return t("ora");
  if (m < 60) return t("{n} min fa", { n: m });
  const h = Math.round(m / 60);
  return h < 24 ? t("{n} h fa", { n: h }) : t("ieri");
}
export const icon = (name, cls = "hc-ico") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${PATHS[name] || PATHS.gauge}</svg>`;

// "da 35 min", "da 2 h", "da ieri"…
export function since(iso) {
  if (!iso) return "";
  const m = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (m < 1) return t("ora");
  if (m < 60) return t("da {n} min", { n: m });
  const h = Math.round(m / 60);
  if (h < 24) return t("da {n} h", { n: h });
  const d = Math.round(h / 24);
  return d === 1 ? t("da ieri") : t("da {n} giorni", { n: d });
}

// A ring with tick marks, like Jarvis's instruments.
export function ring({ size = 72, pct = 0, color = "var(--accent)", label = "", sub = "", ticks = 24 }) {
  const cx = size / 2, r = size / 2 - 11, c = 2 * Math.PI * r;
  let marks = "";
  for (let i = 0; i < ticks; i++) {
    const a = (i / ticks) * 2 * Math.PI - Math.PI / 2, r1 = size / 2 - 2, r2 = size / 2 - (i % 6 === 0 ? 6 : 4);
    marks += `<line x1="${(cx + r1 * Math.cos(a)).toFixed(1)}" y1="${(cx + r1 * Math.sin(a)).toFixed(1)}" x2="${(cx + r2 * Math.cos(a)).toFixed(1)}" y2="${(cx + r2 * Math.sin(a)).toFixed(1)}"/>`;
  }
  const p = Math.max(0, Math.min(1, pct || 0));
  return `<div class="hc-ring" style="width:${size}px;height:${size}px;--rc:${color}"><svg viewBox="0 0 ${size} ${size}" aria-hidden="true">
      <g class="ticks">${marks}</g><circle class="track" cx="${cx}" cy="${cx}" r="${r}"/>
      <circle class="arc" cx="${cx}" cy="${cx}" r="${r}" stroke-dasharray="${(p * c).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 ${cx} ${cx})"/></svg>
    <div class="hc-ring-val"><b style="font-size:${size >= 110 ? 30 : size >= 70 ? 18 : 14}px">${label}</b>${sub ? `<small>${sub}</small>` : ""}</div></div>`;
}

function spark(points) {
  if (!points || points.length < 2) return "";
  const vals = points.map((p) => p[1]);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (max - min < 0.5) { min -= 0.25; max += 0.25; }
  const w = 260, h = 54;
  const xy = vals.map((v, i) => [(i / (vals.length - 1)) * w, h - 5 - ((v - min) / (max - min)) * (h - 12)]);
  const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
  const [lx, ly] = xy[xy.length - 1];
  return `<svg class="hc-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <line class="mid" x1="0" y1="${h / 2}" x2="${w}" y2="${h / 2}"/><path class="area" d="${line}L${w},${h}L0,${h}Z"/>
    <path class="line" d="${line}"/><circle cx="${(lx - 3).toFixed(1)}" cy="${ly.toFixed(1)}" r="3.5"/></svg>`;
}

// Colours offered on lights that have them (any other one from the picker).
const LIGHT_COLORS = [
  ["Rosso", "255,59,48"], ["Arancione", "255,149,0"], ["Giallo", "255,214,10"], ["Verde", "52,199,89"],
  ["Azzurro", "90,200,250"], ["Blu", "10,90,255"], ["Viola", "175,82,222"], ["Rosa", "255,55,155"],
];

export const Cards = {
  // ---------------------------------------------------------------- the house dashboard (HUD)
  hudHTML() {
    const d = this.data;
    const allLights = d.areas.flatMap((a) => this.lightsOf(a));
    const lightsOn = allLights.filter((e) => this.isOn(e));
    const alarm = (d.alarms || []).find((e) => this.st(e));
    const people = (d.people || []).filter((e) => this.st(e));
    const temps = d.areas.filter((a) => !a.outside).map((a) => this.temp(a)).filter((t) => t != null);
    const avg = temps.length ? temps.reduce((s, t) => s + t, 0) / temps.length : null;
    const outside = d.weather && this.st(d.weather)?.a?.temperature;
    const ecfg = d.energy_panel || {};
    const powerId = ecfg.power || d.energy.power;
    const power = powerId && this.st(powerId);
    const energyOn = !!power || Object.keys(ecfg.bands || {}).length || ecfg.total;
    const watts = power ? parseFloat(power.s) * (/kw/i.test(power.a.unit_of_measurement || "") ? 1000 : 1) : NaN;
    const cams = d.areas.reduce((n, a) => n + a.entities.filter((e) => this.st(e)?.k === "camera").length, 0);
    const parts = [];
    if (people.length) {
      const home = people.filter((e) => this.st(e).s === "home").length;
      parts.push(`<div class="hud-item"><div class="hc-people">${people.map((e) => {
        const s = this.st(e), at = s.s === "home";
        const where = at ? t("a casa") : s.s === "not_home" ? t("fuori") : s.s;
        return `<span class="hc-avatar ${at ? "home" : ""}" title="${esc(s.n)}: ${esc(where)} ${esc(since(s.lc))}">${esc((s.n || "?").trim()[0] || "?")}</span>`;
      }).join("")}</div><span class="hud-sub">${home ? t("{n} in casa", { n: home }) : t("nessuno in casa")}</span></div>`);
    }
    if (alarm) {
      const s = this.st(alarm), armed = s.s !== "disarmed", bad = s.s === "triggered";
      parts.push(`<button class="hud-item" data-act="alarm-panel"><span class="hud-dot ${bad ? "bad" : armed ? "ok" : ""}"></span><span><span class="hud-lbl">${t("Allarme")}</span><span class="hud-val">${esc(this.value(alarm).toLowerCase())}</span></span></button>`);
    }
    const wx = this.weatherItem();
    if (wx) parts.push(wx);
    if (avg != null) {
      parts.push(`<div class="hud-item">${ring({ size: 38, pct: (avg - 14) / 14 })}<span><span class="hud-big">${num(avg)}<small>°</small></span><span class="hud-sub">${outside != null && !wx ? t("esterno {t}°", { t: num(outside) }) : t("media della casa")}</span></span></div>`);
    }
    if (allLights.length) {
      parts.push(`<div class="hud-item">${ring({ size: 38, pct: lightsOn.length / allLights.length, color: "var(--warn)" })}<span><span class="hud-big">${lightsOn.length}<small>/${allLights.length}</small></span><span class="hud-sub">${t("luci accese")}</span></span></div>`);
    }
    if (energyOn) {
      // A tap opens the energy panel.
      const band = ecfg.band_mode === "arera" ? this.energyLive?.band?.name : null;
      const sub = [band, d.energy.today ? `${t("oggi")} ${this.value(d.energy.today)}` : this.energyLive?.day?.kwh ? `${t("oggi")} ${num(Object.values(this.energyLive.day.kwh).reduce((s, v) => s + v, 0))} kWh` : t("energia")].filter(Boolean).join(" · ");
      parts.push(`<button class="hud-item" data-act="energy"><span><span class="hud-big">${isNaN(watts) ? "—" : num(watts / 1000, 2)}<small>kW</small></span><span class="hud-sub">${esc(sub)}</span></span></button>`);
    }
    if (cams) {
      parts.push(`<button class="hud-item" data-act="cams">${icon("cam")}<span><span class="hud-val">${cams} ${cams === 1 ? t("telecamera") : t("telecamere")}</span><span class="hud-sub">${t("tocca per vederle")}</span></span></button>`);
    }
    const scenes = d.scenes.map((e) => `<button class="hc-scene" data-act="scene" data-e="${e}">${esc(this.st(e)?.n || e)}</button>`).join("");
    return `<div class="hud-row">${parts.join("")}</div>
      <div class="hud-actions"><div class="hc-scenes">${scenes}</div><button class="hc-link" data-act="layout" title="${t("Modifica la piantina")}">${t("Piantina")}</button></div>`;
  },

  // ---------------------------------------------------------------- a card per kind of entity
  cardHTML(eid) {
    const s = this.st(eid);
    if (!s) return "";
    const unavailable = s.s === "unavailable";
    let html;
    switch (s.k) {
      case "light": html = this.lightCard(eid, s); break;
      case "switch": html = this.switchCard(eid, s); break;
      case "media": html = this.mediaCard(eid, s); break;
      case "climate": html = this.climateCard(eid, s); break;
      case "cover": html = this.coverCard(eid, s); break;
      case "valve": html = this.valveCard(eid, s); break;
      case "gate": html = this.gateCard(eid, s); break;
      case "lock": html = this.lockCard(eid, s); break;
      case "alarm": html = this.alarmCard(eid, s); break;
      case "binary": html = this.binaryCard(eid, s); break;
      case "sensor": html = this.sensorCard(eid, s); break;
      case "person": html = this.personCard(eid, s); break;
      case "siren": html = this.sirenCard(eid, s); break;
      case "datetime": html = this.datetimeCard(eid, s); break;
      case "number": html = this.numberCard(eid, s); break;
      case "select": html = this.selectCard(eid, s); break;
      case "text": html = this.textCard(eid, s); break;
      case "scene": case "script": case "button": html = this.actionCard(eid, s); break;
      case "camera": html = `<div class="hc hc-camcard">${this.camHTML(eid)}</div>`; break;
      case "vacuum": html = this.vacuumCard(eid, s); break;
      default: html = this.plainCard(eid, s);
    }
    return unavailable ? html.replace('class="hc ', 'class="hc off ') : html;
  },

  // The kind is clear from the card itself: only the name, and what goes on the right.
  head(kick, s, right = "") {
    return `<header class="hc-head" title="${esc(kick)}"><b class="hc-name">${esc(s.n)}</b>${right}</header>`;
  },

  lightCard(eid, s) {
    const on = s.s === "on";
    const pct = on && s.a.brightness != null ? Math.round((s.a.brightness / 255) * 100) : on ? 100 : 0;
    const dim = (s.a.supported_color_modes || []).some((m) => m !== "onoff") || s.a.brightness != null;
    const color = on && s.a.rgb_color ? `<span class="hc-swatch" style="background:rgb(${s.a.rgb_color.join(",")})"></span>` : "";
    const kelvin = on && s.a.color_temp_kelvin ? `<span class="hc-state">${s.a.color_temp_kelvin} K</span>` : "";
    const state = s.s === "unavailable" ? t("non disponibile") : on ? `${t("accesa")}${dim ? ` · ${pct}%` : ""}` : t("spenta");
    return `<article class="hc hc-light ${on ? "on" : ""}" data-act="toggle" data-e="${eid}" role="button" tabindex="0" aria-pressed="${on}" aria-label="${esc(s.n)}">
      ${this.head(s.nk ? t("Luce (relè)") : t("Luce"), s, icon("bulb"))}
      <div class="hc-line"><span class="hc-state">${state}</span>${color}${kelvin}${this.toneDot(eid, s)}</div>
      ${dim ? `<input class="hc-range" type="range" min="1" max="100" value="${pct || 1}" data-act="bright" data-e="${eid}" aria-label="${t("Luminosità")} ${esc(s.n)}" ${on ? "" : "disabled"}>` : `<div class="hc-bar"><i style="width:${on ? 100 : 0}%"></i></div>`}
    </article>`;
  },

  toneModes(s) {
    const modes = s?.a.supported_color_modes || [];
    return { temp: modes.includes("color_temp"), colour: modes.some((m) => ["hs", "rgb", "rgbw", "rgbww", "xy"].includes(m)) };
  },

  // The small dot on the card that opens colour and temperature: the card stays as it is.
  toneDot(eid, s) {
    const { temp, colour } = this.toneModes(s);
    if (!temp && !colour) return "";
    const label = colour ? t("Colore e temperatura") : t("Temperatura colore");
    return `<button class="hc-tone ${colour ? "" : "temp"}" data-act="tone" data-e="${eid}" title="${label}" aria-label="${label} ${esc(s.n)}"></button>`;
  },

  // The popup: brightness, colour temperature (warm → cold) and colours, only what the bulb has.
  // Choosing a colour on a light that is off lights it in that colour.
  toneHTML(eid) {
    const s = this.st(eid);
    if (!s) return "";
    const on = s.s === "on";
    const pct = on && s.a.brightness != null ? Math.round((s.a.brightness / 255) * 100) : on ? 100 : 0;
    const k = on && s.a.color_temp_kelvin ? `${s.a.color_temp_kelvin} K` : "";
    return `<div class="casa-modal" role="dialog" aria-label="${esc(s.n)}" data-act="tone-bg"><section class="panel casa-panel hc-tonebox">
      <h3>${esc(s.n)} <button class="casa-x" data-act="tone-close" aria-label="${t("Chiudi")}">×</button></h3>
      <p class="hc-state">${on ? `${t("accesa")} · ${pct}%${k ? ` · ${k}` : ""}` : t("spenta")}</p>
      <span class="hc-kick">${t("Luminosità")}</span>
      <input class="hc-range" type="range" min="1" max="100" value="${pct || 1}" data-act="bright" data-e="${eid}" aria-label="${t("Luminosità")} ${esc(s.n)}">
      ${this.lightTone(eid, s)}
    </section></div>`;
  },

  lightTone(eid, s) {
    const { temp, colour } = this.toneModes(s);
    if (!temp && !colour) return "";
    let out = "";
    if (temp) {
      const lo = s.a.min_color_temp_kelvin || 2000, hi = s.a.max_color_temp_kelvin || 6500;
      const k = Math.min(hi, Math.max(lo, s.a.color_temp_kelvin || Math.round((lo + hi) / 2)));
      out += `<span class="hc-kick">${t("Temperatura colore")}</span><input class="hc-range hc-ktemp" type="range" min="${lo}" max="${hi}" step="50" value="${k}" data-act="ktemp" data-e="${eid}" aria-label="${t("Temperatura colore")} ${esc(s.n)}" title="${t("Temperatura colore")}: ${k} K">`;
    }
    if (colour) {
      const cur = s.a.rgb_color ? "#" + s.a.rgb_color.map((v) => v.toString(16).padStart(2, "0")).join("") : "#ffffff";
      out += `<span class="hc-kick">${t("Colore")}</span><div class="hc-colors">${LIGHT_COLORS.map(([name, rgb]) =>
        `<button class="hc-color" style="background:rgb(${rgb})" data-act="lcolor" data-e="${eid}" data-rgb="${rgb}" title="${t(name)}" aria-label="${t(name)} ${esc(s.n)}"></button>`).join("")}
        <label class="hc-color hc-color-pick" title="${t("Altro colore")}"><input type="color" value="${cur}" data-act="lpick" data-e="${eid}" aria-label="${t("Altro colore")} ${esc(s.n)}"></label></div>`;
    }
    return out;
  },

  switchCard(eid, s) {
    const on = this.isOn(eid);
    const pw = this.data.power?.[eid] && this.st(this.data.power[eid]);
    const domain = eid.split(".")[0];
    const kick = domain === "fan" ? t("Ventilatore") : domain === "vacuum" ? t("Aspirapolvere") : domain === "humidifier" ? t("Umidificatore") : domain === "input_boolean" ? t("Interruttore") : t("Presa / interruttore");
    return `<article class="hc hc-switch ${on ? "on" : ""}">
      ${this.head(kick, s, this.switchHTML(eid))}
      ${pw ? `<div class="hc-watt"><b>${esc(num(parseFloat(pw.s) || 0, 0))}</b><span class="hc-state">${esc(pw.a.unit_of_measurement || "W")} ${t("adesso")}</span></div>` : `<div class="hc-line"><span class="hc-state">${on ? t("acceso") : s.s === "unavailable" ? t("non disponibile") : t("spento")}</span></div>`}
    </article>`;
  },

  mediaCard(eid, s) {
    const f = Number(s.a.supported_features) || 0;
    const active = ["playing", "paused", "buffering"].includes(s.s);
    const sources = (f & 2048) && s.a.source_list?.length
      ? `<select class="hc-select hc-msrc" data-act="msrc" data-e="${eid}" aria-label="${t("Sorgente")} ${esc(s.n)}">${s.a.source ? "" : `<option value="">${t("Sorgente")}</option>`}${s.a.source_list.map((o) => `<option ${o === s.a.source ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>` : "";
    const muted = !!s.a.is_volume_muted;
    const volume = s.a.volume_level != null
      ? `<div class="hc-vol">${f & 8 ? `<button class="hc-round" data-act="mmute" data-e="${eid}" data-v="${muted ? 0 : 1}" aria-label="${muted ? t("Riattiva audio") : t("Silenzia")}">${icon(muted ? "mute" : "vol", "hc-ico sm line")}</button>` : ""}<input class="hc-range" type="range" min="0" max="100" value="${Math.round(s.a.volume_level * 100)}" data-act="volume" data-e="${eid}" aria-label="Volume ${esc(s.n)}"><span class="hc-state">${Math.round(s.a.volume_level * 100)}</span></div>` : "";
    if (!active) {
      const note = { idle: t("inattivo"), off: t("spento"), on: t("acceso"), standby: t("in standby"), unavailable: t("non disponibile") }[s.s] || s.s;
      const on = !["off", "standby", "unavailable"].includes(s.s);
      return `<article class="hc hc-media ${on ? "" : "dim"}">
        ${this.head(t("Media"), s, this.switchHTML(eid))}
        <div class="hc-line"><span class="hc-state">${esc(note)}${on && s.a.source ? ` · ${esc(s.a.source)}` : ""}</span>${on && (f & 16384 || f & 1) ? `<button class="hc-round" data-act="media" data-s="media_play_pause" data-e="${eid}" aria-label="${t("Riproduci")}">${icon("play", "hc-ico sm")}</button>` : ""}</div>
        ${on ? `${volume}${sources ? `<div class="hc-mrow">${sources}</div>` : ""}` : ""}
      </article>`;
    }
    const title = s.a.media_title || t("In riproduzione");
    const sub = [s.a.media_artist || s.a.media_series_title, s.a.media_album_name].filter(Boolean).join(" · ");
    const app = s.a.app_name || s.a.source || "";
    let pos = Number(s.a.media_position);
    const dur = Number(s.a.media_duration);
    if (s.s === "playing" && s.a.media_position_updated_at && !isNaN(pos)) pos += (Date.now() - Date.parse(s.a.media_position_updated_at)) / 1000;
    const pct = dur > 0 && !isNaN(pos) ? Math.min(100, (pos / dur) * 100) : null;
    const clock = (x) => { x = Math.max(0, Math.round(x)); const h = Math.floor(x / 3600), m = Math.floor((x % 3600) / 60), sec = x % 60; return `${h ? h + ":" + String(m).padStart(2, "0") : m}:${String(sec).padStart(2, "0")}`; };
    const pic = s.a.entity_picture ? esc(s.a.entity_picture) : "";
    const art = pic ? `<img src="${pic}" alt="" onerror="this.remove()">` : icon("media", "hc-ico");
    const playing = s.s === "playing";
    const repeat = s.a.repeat || "off";
    const nextRepeat = { off: "all", all: "one", one: "off" }[repeat] || "off";
    return `<article class="hc hc-media hc-media-on wide on">
      ${pic ? `<div class="hc-mbg" style="background-image:url('${pic}')" aria-hidden="true"></div>` : ""}
      ${this.head(t("Media"), s, `<span class="hc-eq ${playing ? "" : "still"}" aria-hidden="true"><i></i><i></i><i></i><i></i></span>`)}
      <div class="hc-now"><div class="hc-art big">${art}</div>
        <div class="hc-nowtxt"><b>${esc(title)}</b>${sub ? `<span class="hc-state">${esc(sub)}</span>` : ""}${app ? `<span class="hc-kick">${esc(app)}</span>` : ""}</div></div>
      ${pct != null ? `<div class="hc-prog"><div class="hc-bar thin"><i style="width:${pct}%"></i></div><span class="hc-state">${clock(pos)}</span><span class="hc-state">${clock(dur)}</span></div>` : ""}
      <div class="hc-transport">
        ${f & 32768 ? `<button class="hc-round ${s.a.shuffle ? "lit" : ""}" data-act="mshuffle" data-e="${eid}" data-v="${s.a.shuffle ? 0 : 1}" aria-label="${t("Casuale")}" aria-pressed="${!!s.a.shuffle}">${icon("shuffle", "hc-ico sm line")}</button>` : ""}
        ${f & 16 ? `<button class="hc-round" data-act="media" data-s="media_previous_track" data-e="${eid}" aria-label="${t("Precedente")}">${icon("prev", "hc-ico sm")}</button>` : ""}
        <button class="hc-round big" data-act="media" data-s="media_play_pause" data-e="${eid}" aria-label="${playing ? t("Pausa") : t("Riproduci")}">${icon(playing ? "pause" : "play", "hc-ico")}</button>
        ${f & 32 ? `<button class="hc-round" data-act="media" data-s="media_next_track" data-e="${eid}" aria-label="${t("Successivo")}">${icon("next", "hc-ico sm")}</button>` : ""}
        ${f & 262144 ? `<button class="hc-round ${repeat !== "off" ? "lit" : ""}" data-act="mrepeat" data-e="${eid}" data-v="${nextRepeat}" aria-label="${t("Ripeti")}">${icon("repeat", "hc-ico sm line")}${repeat === "one" ? "<sup>1</sup>" : ""}</button>` : ""}
      </div>
      <div class="hc-mrow">${volume}${sources}</div>
    </article>`;
  },

  // ---------------------------------------------------------------- robot vacuum
  vacuumCard(eid, s) {
    const f = Number(s.a.supported_features) || 0;
    const label = { cleaning: t("pulisce"), docked: t("in base"), returning: t("torna alla base"), paused: t("in pausa"), idle: t("fermo"), error: t("errore"), unavailable: t("non disponibile") }[s.s] || s.s;
    const busy = s.s === "cleaning";
    const bat = s.a.battery_level;
    const batHTML = bat != null ? `<span class="hc-batt ${bat < 20 ? "low" : ""}" title="${t("Batteria")} ${bat}%"><i style="width:${bat}%"></i></span><span class="hc-state">${bat}%</span>` : "";
    const map = s.mp ? `<div class="hc-vmap"><img data-cam="${s.mp}" src="${this.camSrc[s.mp] ||= this.camURL(s.mp)}" alt="${t("Mappa")} ${esc(s.n)}"></div>` : "";
    const fan = s.a.fan_speed_list?.length
      ? `<select class="hc-select" data-act="vfan" data-e="${eid}" aria-label="${t("Potenza di aspirazione")} ${esc(s.n)}">${s.a.fan_speed_list.map((o) => `<option ${o === s.a.fan_speed ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>` : "";
    const btn = (svc, ic, name) => `<button class="hc-btn hc-vbtn" data-act="vac" data-s="${svc}" data-e="${eid}">${icon(ic, ic === "play" || ic === "pause" ? "hc-ico sm" : "hc-ico sm line")}<span>${name}</span></button>`;
    return `<article class="hc hc-vacuum ${map ? "wide" : ""} ${busy ? "on" : ""} ${s.s === "error" ? "alert" : ""}">
      ${this.head(t("Robot"), s, icon("robot"))}
      <div class="hc-line"><span class="hc-state ${s.s === "error" ? "bad" : ""}">${esc(label)}${s.a.status && s.a.status.toLowerCase() !== String(label).toLowerCase() ? ` · ${esc(s.a.status)}` : ""}</span>${batHTML}</div>
      ${map}
      <div class="hc-vctl">
        ${busy ? btn("pause", "pause", t("Pausa")) : btn("start", "play", s.s === "paused" ? t("Riprendi") : t("Pulisci"))}
        ${s.s !== "docked" ? btn("return_to_base", "dock", t("Base")) : ""}
        ${f & 512 ? btn("locate", "target", t("Trova")) : ""}
        ${fan}
      </div>
    </article>`;
  },

  climateCard(eid, s) {
    const cur = s.a.current_temperature, target = s.a.temperature;
    const action = ACTION[s.a.hvac_action] ?? "";
    const modes = (s.a.hvac_modes || []).map((m) => `<button class="hc-tab ${s.s === m ? "sel" : ""}" data-act="hvac" data-e="${eid}" data-m="${m}">${HVAC[m] || m}</button>`).join("");
    return `<article class="hc hc-climate ${s.s !== "off" ? "on" : ""}">
      ${this.head(t("Clima"), s, action ? `<span class="hc-state">${action.toLowerCase()}</span>` : "")}
      <div class="hc-dialrow"><span class="hc-temp">${cur != null ? num(cur) : "—"}<small>°</small></span>
        ${target != null ? `<span class="hc-target"><span class="hc-state">${t("obiettivo")} ${num(target)}°</span><span class="hc-steps row"><button class="hc-step" data-act="temp" data-e="${eid}" data-d="-1" aria-label="${t("Abbassa")}">−</button><button class="hc-step" data-act="temp" data-e="${eid}" data-d="1" aria-label="${t("Alza")}">+</button></span></span>` : ""}</div>
      <div class="hc-tabs">${modes}</div>
      ${s.a.current_humidity != null ? `<span class="hc-state">${t("umidità")} ${num(s.a.current_humidity, 0)}%</span>` : ""}
    </article>`;
  },

  coverCard(eid, s) {
    const pos = s.a.current_position ?? (s.s === "open" ? 100 : s.s === "closed" ? 0 : 50);
    const state = s.a.current_position != null ? t("{n}% aperta", { n: pos }) : { open: t("aperta"), closed: t("chiusa"), opening: t("si alza…"), closing: t("si abbassa…") }[s.s] || s.s;
    return `<article class="hc hc-cover">
      ${this.head(this.dc(eid) === "awning" ? t("Tenda") : this.dc(eid) === "garage" ? "Garage" : t("Tapparella"), s, `<span class="hc-state">${esc(state)}</span>`)}
      <div class="hc-blind"><div class="hc-window"><div class="hc-slats" style="height:${100 - pos}%"></div></div>
        <div class="hc-blind-ctl">
          <button class="hc-btn" data-act="cover" data-s="open_cover" data-e="${eid}">▲ ${t("Su")}</button>
          <button class="hc-btn" data-act="cover" data-s="stop_cover" data-e="${eid}">■ Stop</button>
          <button class="hc-btn" data-act="cover" data-s="close_cover" data-e="${eid}">▼ ${t("Giù")}</button>
        </div></div>
    </article>`;
  },

  valveCard(eid, s) {
    const open = s.s === "open" || s.s === "opening";
    const f = Number(s.a.supported_features) || 0;
    const pos = s.a.current_position;
    return `<article class="hc hc-valve ${open ? "on" : ""}">
      ${this.head(t("Valvola"), s, `<span class="hc-state ${open ? "warm" : ""}">${esc(this.value(eid).toLowerCase())}${open && s.lc ? ` ${since(s.lc)}` : ""}</span>`)}
      <div class="hc-dialrow">
        <svg class="hc-pipe" viewBox="0 0 64 64" aria-hidden="true"><path class="tube" d="M6 34h52"/>${open ? '<path class="flow" d="M6 34h52"/>' : ""}<rect class="wheel" x="24" y="14" width="16" height="10" rx="2"/><path class="wheel" d="M32 24v6"/></svg>
        <div class="hc-tabs">
          <button class="hc-tab ${open ? "sel" : ""}" data-act="valve" data-s="open_valve" data-e="${eid}">${t("Apri")}</button>
          ${f & 8 ? `<button class="hc-tab" data-act="valve" data-s="stop_valve" data-e="${eid}">${t("Ferma")}</button>` : ""}
          <button class="hc-tab ${open ? "" : "sel"}" data-act="valve" data-s="close_valve" data-e="${eid}">${t("Chiudi")}</button>
        </div>
      </div>
      ${pos != null ? `<div class="hc-bar"><i style="width:${pos}%"></i></div>` : ""}
    </article>`;
  },

  gateCard(eid, s) {
    const state = { open: t("aperto"), opening: t("apre…"), closed: t("chiuso"), closing: t("chiude…"), locked: t("bloccata"), unlocked: t("sbloccata") }[s.s] || "";
    return `<article class="hc hc-gate">
      ${this.head(t("Cancello / porta"), s, icon("gate"))}
      <div class="hc-line">${state ? `<span class="hc-state">${state}</span>` : ""}<button class="hc-btn primary" data-act="gate" data-e="${eid}">▶ ${t("Comanda")}</button></div>
    </article>`;
  },

  lockCard(eid, s) {
    const locked = s.s === "locked";
    const asking = this.lockAsk === eid;
    const body = asking
      ? `<div class="hc-ask"><span>${t("Sbloccare {name}?", { name: esc(s.n) })}</span><span class="hc-modes"><button class="hc-btn primary" data-act="lock-yes" data-e="${eid}">${t("Sì, sblocca")}</button><button class="hc-btn" data-act="lock-no">${t("No")}</button></span></div>`
      : `<button class="hc-link" data-act="lock" data-e="${eid}">${locked ? t("Sblocca") : t("Blocca")}</button>`;
    return `<article class="hc hc-lock ${locked ? "" : "warn"}">
      ${this.head(t("Serratura"), s, `<span class="hc-state ${locked ? "good" : "warm"}">${esc(this.value(eid).toLowerCase())}</span>`)}
      ${body}
    </article>`;
  },

  alarmCard(eid, s) {
    const f = Number(s.a.supported_features) || 0;
    const arm = [[1, "alarm_arm_home", t("In casa")], [2, "alarm_arm_away", t("Fuori")], [4, "alarm_arm_night", t("Notte")], [32, "alarm_arm_vacation", t("Vacanza")]].filter(([bit]) => f & bit);
    const armed = s.s !== "disarmed";
    const current = { armed_home: "alarm_arm_home", armed_away: "alarm_arm_away", armed_night: "alarm_arm_night", armed_vacation: "alarm_arm_vacation" }[s.s];
    return `<article class="hc hc-alarm ${s.s === "triggered" ? "alert" : ""}">
      ${this.head(t("Allarme"), s, `<span class="hc-state ${s.s === "triggered" ? "bad" : armed ? "good" : ""}">${esc(this.value(eid).toLowerCase())}</span>`)}
      <div class="hc-tabs">${arm.map(([, svc, label]) => `<button class="hc-tab ${current === svc ? "sel ok" : ""}" data-act="alarm" data-s="${svc}" data-e="${eid}" ${armed ? "disabled" : ""}>${label}</button>`).join("")}</div>
      ${armed ? `<button class="hc-btn primary" data-act="alarm" data-s="alarm_disarm" data-e="${eid}">${t("Disinserisci")}</button>` : ""}
    </article>`;
  },

  binaryCard(eid, s) {
    const dc = s.a.device_class, on = s.s === "on";
    const opening = OPENING.has(dc), danger = DANGER.has(dc), presence = PRESENCE.has(dc);
    const alert = on && (opening || danger);
    const kick = { door: t("Porta"), window: t("Finestra"), garage_door: t("Basculante"), opening: t("Apertura"), smoke: t("Fumo"), moisture: t("Allagamento"), gas: "Gas", carbon_monoxide: t("Monossido"), motion: t("Movimento"), occupancy: t("Presenza"), presence: t("Presenza") }[dc] || t("Sensore");
    return `<article class="hc hc-binary ${alert ? "alert" : presence && on ? "live" : ""}">
      ${this.head(kick, s, `<span class="hc-state ${alert ? "bad" : presence && on ? "warm" : ""}">${esc(this.value(eid).toLowerCase())} ${esc(since(s.lc))}</span>`)}
    </article>`;
  },

  sensorCard(eid, s) {
    const n = parseFloat(s.s);
    const numeric = !isNaN(n) && !/[^\d.,\-e]/i.test(s.s);
    const kick = { temperature: t("Temperatura"), humidity: t("Umidità"), power: t("Potenza"), energy: t("Energia"), battery: t("Batteria"), illuminance: t("Luce"), pressure: t("Pressione"), carbon_dioxide: "CO₂", pm25: "PM2.5" }[s.a.device_class] || t("Sensore");
    const hist = (this.data.nochart || []).includes(eid) ? null : this.hist?.[eid];
    const vals = (hist || []).map((p) => p[1]);
    return `<article class="hc hc-sensor">
      ${this.head(kick, s, `<span class="hc-num">${numeric ? `${num(n)}<small>${esc(s.a.unit_of_measurement || "")}</small>` : esc(this.value(eid).toLowerCase())}</span>`)}
      ${numeric ? spark(hist) : ""}
      ${vals.length > 1 ? `<span class="hc-state">${t("24 ore")} · min ${num(Math.min(...vals))} · max ${num(Math.max(...vals))}</span>` : ""}
    </article>`;
  },

  personCard(eid, s) {
    const home = s.s === "home";
    const where = home ? t("A casa") : s.s === "not_home" ? t("Fuori casa") : s.s;
    return `<article class="hc hc-personcard">
      ${this.head(eid.startsWith("person.") ? t("Persona") : t("Posizione"), s)}
      <div class="hc-line"><span class="hc-person ${home ? "home" : ""}"><span class="hc-avatar big">${esc((s.n || "?").trim()[0] || "?")}</span></span>
        <span class="hc-nowtxt"><span>${esc(where)}</span><span class="hc-state">${esc(since(s.lc))}${s.a.battery_level != null ? ` · ${t("batteria")} ${s.a.battery_level}%` : ""}</span></span></div>
    </article>`;
  },

  sirenCard(eid, s) {
    const on = s.s === "on";
    return `<article class="hc hc-siren ${on ? "alert" : ""}">
      ${this.head(t("Sirena"), s, this.switchHTML(eid))}
      <div class="hc-line"><span class="hc-state ${on ? "bad" : ""}">${on ? t("suona") : t("spenta")}</span></div>
    </article>`;
  },

  plainCard(eid, s) {
    return `<article class="hc hc-plain">${this.head(eid.split(".")[0].replace(/_/g, " "), s, `<span class="hc-state">${esc(String(this.value(eid)).toLowerCase())}</span>`)}</article>`;
  },

  // ---------------------------------------------------------------- helpers set from the dashboard
  // (the stove's start time, a target number, a mode…): Home Assistant stores the value and the
  // owner's automations use it as before.
  dtParts(eid, s) {
    const domain = eid.split(".")[0];
    const hasDate = domain === "date" || domain === "datetime" || (domain === "input_datetime" && s.a.has_date);
    const hasTime = domain === "time" || domain === "datetime" || (domain === "input_datetime" && s.a.has_time !== false);
    const raw = String(s.s || "");
    const date = (raw.match(/\d{4}-\d{2}-\d{2}/) || [""])[0];
    const time = (raw.match(/\d{2}:\d{2}/) || [""])[0];
    return { hasDate, hasTime, date, time };
  },

  dtValueHTML(eid, s, big = true) {
    const { hasDate, hasTime, date, time } = this.dtParts(eid, s);
    const unknown = !date && !time;
    const type = hasDate && hasTime ? "datetime-local" : hasDate ? "date" : "time";
    const value = type === "datetime-local" ? `${date}T${time}` : type === "date" ? date : time;
    const shown = unknown ? "—" : [hasDate && date ? date.split("-").reverse().join("/") : "", hasTime ? time : ""].filter(Boolean).join(" ");
    return `<span class="hc-dt"><button class="hc-timev ${big ? "" : "sm"}" data-act="pick" data-e="${eid}" aria-label="${t("Cambia")} ${esc(s.n)}">${esc(shown)}</button>
      <input type="${type}" value="${esc(value)}" data-act="dt" data-e="${eid}" tabindex="-1" aria-hidden="true">
      ${hasTime && !hasDate ? `<span class="hc-nudge"><button data-act="nudge" data-d="-15" data-e="${eid}">−15</button><button data-act="nudge" data-d="15" data-e="${eid}">+15</button></span>` : ""}</span>`;
  },

  datetimeCard(eid, s) {
    return `<article class="hc hc-datetime">${this.head(t("Orario"), s)}${this.dtValueHTML(eid, s)}</article>`;
  },

  numberCard(eid, s) {
    const v = parseFloat(s.s), min = Number(s.a.min ?? 0), max = Number(s.a.max ?? 100), step = Number(s.a.step ?? 1);
    const unit = s.a.unit_of_measurement || "";
    return `<article class="hc hc-number">
      ${this.head(t("Numero"), s, `<span class="hc-num">${isNaN(v) ? "—" : num(v, 2)}<small>${esc(unit)}</small></span>`)}
      <div class="hc-line"><button class="hc-step" data-act="numstep" data-d="-1" data-e="${eid}" aria-label="${t("Meno")}">−</button>
        <input class="hc-range" type="range" min="${min}" max="${max}" step="${step}" value="${isNaN(v) ? min : v}" data-act="numval" data-e="${eid}" aria-label="${esc(s.n)}" style="flex:1">
        <button class="hc-step" data-act="numstep" data-d="1" data-e="${eid}" aria-label="${t("Più")}">+</button></div>
    </article>`;
  },

  selectCard(eid, s) {
    const opts = s.a.options || [];
    const short = opts.length <= 4 && opts.every((o) => String(o).length <= 14);
    const body = short
      ? `<div class="hc-tabs">${opts.map((o) => `<button class="hc-tab ${o === s.s ? "sel" : ""}" data-act="selopt" data-v="${esc(o)}" data-e="${eid}">${esc(o)}</button>`).join("")}</div>`
      : `<select class="hc-select" data-act="selopt" data-e="${eid}" aria-label="${esc(s.n)}">${opts.map((o) => `<option ${o === s.s ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
    return `<article class="hc hc-selectcard">${this.head(t("Scelta"), s, short ? "" : `<span class="hc-state">${esc(s.s)}</span>`)}${body}</article>`;
  },

  textCard(eid, s) {
    return `<article class="hc hc-text">${this.head(t("Testo"), s)}
      <input class="hc-input" type="text" value="${esc(s.s)}" maxlength="${Number(s.a.max) || 255}" data-act="textval" data-e="${eid}" aria-label="${esc(s.n)}"></article>`;
  },

  actionCard(eid, s) {
    return `<article class="hc hc-action">${this.head(t("Azione"), s, `<button class="hc-link" data-act="scene" data-e="${eid}">${t("Avvia")}</button>`)}</article>`;
  },

  // ---------------------------------------------------------------- a card composed in HubNEX
  composedCard(card) {
    const eids = card.entities.filter((e) => this.st(e));
    const cam = eids.find((e) => e.startsWith("camera."));
    if (cam) return this.cameraComposed(card, cam, eids);
    const label = (e) => {
      const n = this.st(e).n, pre = card.name.toLowerCase();
      return n.toLowerCase().startsWith(pre) && n.length > pre.length + 1 ? n.slice(pre.length).trim() : n;
    };
    // Two times of day (start / stop): the day's band and whether we are inside it.
    const times = eids.filter((e) => this.st(e).k === "datetime" && this.dtParts(e, this.st(e)).hasTime && !this.dtParts(e, this.st(e)).hasDate);
    let status = "", band = "", running = false;
    // What really powers the device (a switch, light or thermostat); an input_boolean such as
    // "automatica" is a setting, not the device being on.
    const power = eids.find((e) => ["switch", "light", "climate", "fan"].includes(e.split(".")[0]));
    if (times.length >= 2) {
      const [a, b] = times.map((e) => this.dtParts(e, this.st(e)).time);
      if (a && b) {
        const m = (t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
        const on = m(a), off = m(b), d = new Date(), now = d.getHours() * 60 + d.getMinutes();
        const inside = on <= off ? now >= on && now < off : now >= on || now < off;
        running = inside;
        status = inside ? t("attiva fino alle {time}", { time: b }) : t("si attiva alle {time}", { time: a });
        const width = ((off - on + 1440) % 1440) / 14.4;
        band = `<div class="hc-band" aria-hidden="true"><i style="left:${on / 14.4}%;width:${width}%"></i>${on + width * 14.4 > 1440 ? `<i style="left:0;width:${(on + width * 14.4 - 1440) / 14.4}%"></i>` : ""}<b style="left:${now / 14.4}%"></b>
          <span><em>0</em><em>6</em><em>12</em><em>18</em><em>24</em></span></div>`;
      }
    }
    // The switch that turns the times on ("automatica"): off, the times don't apply.
    const gate = this.cardEnable(card, eids);
    if (gate && band && !this.isOn(gate)) {
      status = `${label(gate).toLowerCase()} ${t("spenta")} · ${t("orari non attivi")}`;
      running = false;
      band = band.replace('class="hc-band"', 'class="hc-band off"');
    }
    const lit = power ? this.isOn(power) : running;
    if (power) status = `${this.isOn(power) ? t("accesa") : t("spenta")}${status ? ` · ${status}` : ""}`;
    const slot = (e) => {
      const s = this.st(e);
      let body;
      if (s.k === "datetime") body = this.dtValueHTML(e, s, eids.length <= 3);
      else if (["switch", "light", "media", "siren"].includes(s.k)) body = this.switchHTML(e);
      else if (s.k === "number") body = `<span class="hc-line"><button class="hc-step" data-act="numstep" data-d="-1" data-e="${e}" aria-label="${t("Meno")}">−</button><span class="hc-num">${esc(s.s)}<small>${esc(s.a.unit_of_measurement || "")}</small></span><button class="hc-step" data-act="numstep" data-d="1" data-e="${e}" aria-label="${t("Più")}">+</button></span>`;
      else if (s.k === "select") body = `<select class="hc-select" data-act="selopt" data-e="${e}" aria-label="${esc(s.n)}">${(s.a.options || []).map((o) => `<option ${o === s.s ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
      else if (s.k === "climate") body = `<span class="hc-num">${s.a.current_temperature != null ? num(s.a.current_temperature) : "—"}<small>°</small></span>`;
      else if (s.k === "sensor") body = `<span class="hc-num">${esc(this.value(e))}</span>${(card.nochart || []).includes(e) ? "" : spark(this.hist?.[e])}`;
      else body = `<span class="hc-state">${esc(String(this.value(e)).toLowerCase())}</span>`;
      // The line over each entity lights up when it is active: amber, red for an alarm
      // (a window open, water, smoke).
      const alarm = s.k === "binary" && s.s === "on" && (OPENING.has(s.a.device_class) || DANGER.has(s.a.device_class));
      const active = !alarm && (s.k === "binary" ? s.s === "on" : s.k === "lock" ? s.s !== "locked" : this.isOn(e));
      return `<div class="hc-slot ${alarm ? "alert" : active ? "on" : ""}"><span class="hc-state">${esc(label(e))}</span>${body}</div>`;
    };
    // Switches stack in one column, each with its name: the times keep their place.
    const isToggle = (e) => ["switch", "light", "media", "siren"].includes(this.st(e).k);
    const toggles = eids.filter(isToggle);
    const toggleCol = toggles.length
      ? `<div class="hc-slot hc-toggles">${toggles.map((e) => `<div class="hc-toggle-row"><span class="hc-state">${esc(label(e))}</span>${this.switchHTML(e)}</div>`).join("")}</div>`
      : "";
    return `<article class="hc hc-composed ${card.size === "wide" ? "wide" : ""} ${lit ? "on" : ""}" data-card="${card.id}">
      <header class="hc-head"><b class="hc-name">${esc(card.name)}</b>${status ? `<span class="hc-state">${esc(status)}</span>` : ""}</header>
      <div class="hc-slots">${eids.filter((e) => !isToggle(e)).map(slot).join("")}${toggleCol}${eids.length ? "" : `<span class="hc-state">${t("entità non disponibili")}</span>`}</div>
      ${band}
    </article>`;
  },

  // A composed card with a camera: the picture, the binary sensors that go with it (a vehicle,
  // a person, motion) lit over it, anything else below.
  cameraComposed(card, cam, eids) {
    const pre = card.name.toLowerCase();
    const label = (e) => {
      const n = this.st(e).n;
      return n.toLowerCase().startsWith(pre) && n.length > pre.length + 1 ? n.slice(pre.length).trim() : n;
    };
    const bins = eids.filter((e) => this.st(e).k === "binary");
    const rest = eids.filter((e) => e !== cam && !bins.includes(e));
    const live = bins.filter((e) => this.st(e).s === "on");
    const chips = bins.map((e) => {
      const s = this.st(e), on = s.s === "on";
      return `<span class="hc-chip ${on ? "on" : ""}" title="${esc(s.n)}">${esc(label(e))}${s.lc ? `<small>${on ? t("ora") : since(s.lc)}</small>` : ""}</span>`;
    }).join("");
    const status = live.length ? live.map((e) => label(e).toLowerCase()).join(", ") : bins.length ? t("tutto tranquillo") : "";
    const rows = rest.map((e) => `<div class="hc-toggle-row"><span class="hc-state">${esc(label(e))}</span>${["switch", "light", "siren"].includes(this.st(e).k) ? this.switchHTML(e) : `<span class="hc-num sm">${esc(this.value(e))}</span>`}</div>`).join("");
    return `<article class="hc hc-composed hc-camcomp ${card.size === "wide" ? "wide" : ""} ${live.length ? "alert" : ""}" data-card="${card.id}">
      <div class="hc-camwrap">${this.camHTML(cam).replace(/<span class="casa-cam-label">[\s\S]*?<\/span>/, "")}${chips ? `<div class="hc-chips">${chips}</div>` : ""}</div>
      <header class="hc-head"><b class="hc-name">${esc(card.name)}</b>${status ? `<span class="hc-state ${live.length ? "bad" : ""}">${esc(status)}</span>` : ""}</header>
      ${rows ? `<div class="hc-camrows">${rows}</div>` : ""}
    </article>`;
  },

  // Which switch of a composed card turns its times on: the one the owner chose, else one
  // whose name says so (automatica, programma, timer…). "" = none.
  cardEnable(card, eids = card.entities) {
    if (card.enable !== undefined && card.enable !== null) return card.enable && this.st(card.enable) ? card.enable : null;
    return eids.find((e) => ["input_boolean", "switch"].includes(e.split(".")[0]) && /automatic|programm|timer|\bauto\b|schedul/i.test(`${e} ${this.st(e)?.n || ""}`)) || null;
  },

  // ---------------------------------------------------------------- quick card of a room
  quickHTML(a) {
    const lights = this.lightsOf(a);
    const climate = a.entities.find((e) => this.st(e)?.k === "climate");
    const temp = this.temp(a);
    const hum = a.entities.map((e) => this.st(e)).find((s) => s?.k === "sensor" && s.a.device_class === "humidity");
    const watch = a.entities.filter((e) => {
      const s = this.st(e);
      if (!s) return false;
      if (s.k === "binary") return s.s === "on" && (OPENING.has(s.a.device_class) || DANGER.has(s.a.device_class));
      if (s.k === "lock") return s.s !== "locked";
      if (s.k === "siren") return s.s === "on";
      if (s.k === "valve") return s.s === "open";
      if (s.k === "switch" && this.data.power?.[e]) return parseFloat(this.st(this.data.power[e])?.s) > 5;
      return false;
    });
    const cam = a.entities.find((e) => this.st(e)?.k === "camera");
    const figures = [temp != null ? `${num(temp)}°` : "", hum ? `${num(parseFloat(hum.s), 0)}%` : ""].filter(Boolean).join(" · ");
    const watchRow = (e) => {
      const s = this.st(e);
      const pw = this.data.power?.[e] && this.st(this.data.power[e]);
      const right = s.k === "lock" ? `<button class="hc-btn" data-act="lock" data-e="${e}">${t("Blocca")}</button>`
        : s.k === "valve" ? `<button class="hc-btn" data-act="valve" data-s="close_valve" data-e="${e}">${t("Chiudi")}</button>`
        : s.k === "switch" || s.k === "siren" ? this.switchHTML(e) : "";
      const what = s.k === "switch" && pw ? `${num(parseFloat(pw.s), 0)} ${pw.a.unit_of_measurement || "W"} · ${since(s.lc)}` : `${this.value(e).toLowerCase()} ${since(s.lc)}`;
      return `<div class="hc-watch"><span>${esc(s.n)} <span class="hc-state bad">${esc(what)}</span></span>${right}</div>`;
    };
    return `
      <section class="hc casa-quick">
        <div class="hc-grab" data-act="unselect" aria-hidden="true"></div>
        <div class="hc-head"><div><h2>${esc(a.name)}</h2></div>
          <span class="hc-num">${figures}</span><button class="casa-x" data-act="unselect" aria-label="${t("Chiudi")}">×</button></div>
        ${lights.length ? `<span class="hc-kick">${t("Luci")}</span><div class="hc-tiles">${lights.slice(0, 8).map((e) => {
          const s = this.st(e), on = s.s === "on";
          const pct = on && s.a.brightness != null ? Math.round((s.a.brightness / 255) * 100) : on ? 100 : 0;
          return `<button class="hc-tile ${on ? "on" : ""}" data-act="toggle" data-e="${e}" aria-pressed="${on}"><b>${esc(s.n)}</b><span class="hc-state">${on ? `${t("accesa")}${pct < 100 ? ` · ${pct}%` : ""}` : t("spenta")}</span><span class="hc-bar thin"><i style="width:${pct}%"></i></span></button>`;
        }).join("")}</div>${lights.length > 8 ? `<p class="casa-muted">${t("+ altre {n}", { n: lights.length - 8 })}</p>` : ""}` : ""}
        ${climate ? this.climateMini(climate) : ""}
        ${watch.length ? `<span class="hc-kick">${t("Da tenere d'occhio")}</span>${watch.map(watchRow).join("")}` : ""}
        ${cam ? this.camHTML(cam) : ""}
        ${!a.entities.length ? `<p class="casa-muted">${t("Nessuna entità in quest'area. Aprila e aggiungine con \"Modifica stanza\".")}</p>` : ""}
        <div class="casa-actions">
          <button class="hc-open" data-act="open" data-area="${a.id}">${t("Apri stanza")} →</button>
          ${lights.some((e) => this.isOn(e)) ? `<button class="hc-link" data-act="all-off" data-area="${a.id}">${t("Spegni luci")}</button>` : ""}
        </div>
      </section>`;
  },

  climateMini(eid) {
    const s = this.st(eid), target = s.a.temperature;
    return `<div class="hc-climini"><span>${esc(s.n)} <span class="hc-state">${esc((HVAC[s.s] || s.s).toLowerCase())}${s.a.current_temperature != null ? ` · ${num(s.a.current_temperature)}°` : ""}</span></span>
      ${target != null ? `<span class="hc-steps row"><button class="hc-step" data-act="temp" data-e="${eid}" data-d="-1" aria-label="${t("Abbassa")}">−</button><b>${num(target)}°</b><button class="hc-step" data-act="temp" data-e="${eid}" data-d="1" aria-label="${t("Alza")}">+</button></span>` : ""}</div>`;
  },

  // Overview (no room chosen): lights on and what needs attention, as compact cards.
  // ---------------------------------------------------------------- weather
  weatherItem() {
    const w = this.data.weather && this.st(this.data.weather);
    if (!w || w.a.temperature == null) return "";
    const [ic, label] = WX[w.s] || ["gauge", w.s];
    const day = this.forecast?.[0];
    const rain = day?.precipitation_probability;
    const sub = [label, day ? `${num(day.templow, 0)}°/${num(day.temperature, 0)}°` : "", rain >= 20 ? t("pioggia {n}%", { n: num(rain, 0) }) : ""].filter(Boolean).join(" · ");
    return `<button class="hud-item hud-wx" data-act="weather">${icon(ic, "hc-ico wx")}<span><span class="hud-big">${num(w.a.temperature)}<small>°</small></span><span class="hud-sub">${esc(sub)}</span></span></button>`;
  },

  weatherHTML() {
    const w = this.st(this.data.weather);
    const [ic, label] = WX[w.s] || ["gauge", w.s];
    const unit = w.a.wind_speed_unit || "km/h";
    const dayName = (iso, i) => i === 0 ? t("Oggi") : i === 1 ? t("Domani") : new Date(iso).toLocaleDateString(LOCALE, { weekday: "long" });
    const days = (this.forecast || []).slice(0, 6).map((d, i) => {
      const [dic, dlabel] = WX[d.condition] || ["gauge", d.condition || ""];
      const rain = d.precipitation_probability;
      const wet = ["rain", "storm", "snow"].includes(dic); // the words already say it: just the chance
      const chance = rain >= 20 ? ` · ${wet ? `${num(rain, 0)}%` : t("pioggia {n}%", { n: num(rain, 0) })}` : "";
      return `<div class="wx-day"><span class="wx-name">${esc(dayName(d.datetime, i))}</span>${icon(dic, "hc-ico wx")}<span class="wx-what">${esc(dlabel)}${chance}</span><span class="wx-t mono"><b>${num(d.temperature, 0)}°</b> ${d.templow != null ? `${num(d.templow, 0)}°` : ""}</span></div>`;
    }).join("");
    return `<div class="casa-modal" role="dialog" aria-label="${t("Meteo")}"><section class="panel casa-panel casa-wx-modal">
      <h3>${t("Meteo")} <button class="casa-x" data-act="weather-close" aria-label="${t("Chiudi")}">×</button></h3>
      <div class="wx-now">${icon(ic, "hc-ico wx big")}<span class="wx-temp">${num(w.a.temperature)}<small>°</small></span>
        <span class="wx-info"><b>${esc(label)}</b>${w.a.humidity != null ? `<span>${t("Umidità")} ${num(w.a.humidity, 0)}%</span>` : ""}${w.a.wind_speed != null ? `<span>${t("Vento")} ${num(w.a.wind_speed, 0)} ${esc(unit)}</span>` : ""}</span></div>
      ${days ? `<div class="wx-days">${days}</div>` : `<p class="casa-muted">${t("Previsioni non disponibili.")}</p>`}
    </section></div>`;
  },

  // ---------------------------------------------------------------- today: deadlines (owner only)
  todayHTML() {
    const list = this.deadlines?.();
    if (!list) return ""; // family members: the owner's work isn't theirs to see
    const now = Date.now();
    const when = (d) => new Date(d.due.length <= 10 ? d.due + "T09:00" : d.due).getTime();
    const items = list.filter((d) => when(d) - now < 7 * 864e5).slice(0, 4);
    const label = (ms) => {
      const day = new Date(ms), today = new Date();
      const diff = Math.round((new Date(day.toDateString()) - new Date(today.toDateString())) / 864e5);
      if (diff < 0) return t("scaduta");
      if (diff === 0) return t("oggi");
      if (diff === 1) return t("domani");
      return day.toLocaleDateString(LOCALE, { weekday: "short", day: "numeric" });
    };
    const rows = items.map((d) => {
      const ms = when(d), late = ms < now && label(ms) === t("scaduta");
      return `<div class="hc-today ${late ? "late" : ""}"><span class="hc-due">${esc(label(ms))}</span><span class="hc-ttl">${esc(d.title)}</span><button class="hc-done" data-act="ddone" data-id="${d.id}" aria-label="${t("Segna come fatta")}">${icon("check", "hc-ico sm line")}</button></div>`;
    }).join("");
    return `<section class="hc"><span class="hc-kick">${icon("cal", "hc-ico sm line")} ${t("Oggi e prossimi giorni")}</span>${rows || `<p class="casa-muted">${t("Nessuna scadenza nei prossimi 7 giorni.")}</p>`}</section>`;
  },

  // ---------------------------------------------------------------- appliances
  appliances() {
    return Object.entries(this.data.power || {}).flatMap(([eid, pid]) => {
      const s = this.st(eid), p = this.st(pid);
      if (!s || !p || !APPLIANCE.test(s.n || "")) return [];
      const w = parseFloat(p.s) * (/kw/i.test(p.a.unit_of_measurement || "") ? 1000 : 1);
      if (w > 10) return [{ eid, s, on: true, w, area: this.data.areas.find((a) => a.entities.includes(eid)) }];
      if (Date.now() - Date.parse(p.lc) < 3 * 36e5) return [{ eid, s, on: false, lc: p.lc, area: this.data.areas.find((a) => a.entities.includes(eid)) }];
      return [];
    });
  },

  appliancesHTML() {
    const list = this.appliances();
    if (!list.length) return "";
    return `<section class="hc"><span class="hc-kick">${icon("washer", "hc-ico sm line")} ${t("Elettrodomestici")}</span>${list.map((x) =>
      `<div class="hc-watch"><span>${esc(x.s.n)} <span class="hc-state">${esc(x.area?.name || "")}</span></span><span class="hc-state ${x.on ? "warn" : "ok"}">${x.on ? `${t("in funzione")} · ${x.w >= 1000 ? `${num(x.w / 1000, 1)} kW` : `${num(x.w, 0)} W`}` : `${t("finito")} ${ago(x.lc)}`}</span></div>`).join("")}</section>`;
  },

  // ---------------------------------------------------------------- recent events
  activityHTML() {
    const seen = new Set();
    const rows = [];
    const add = (e, area) => {
      const s = this.st(e);
      if (!s || seen.has(e) || !s.lc || Date.now() - Date.parse(s.lc) > 864e5 || s.s === "unavailable") return;
      const k = s.k, dc = s.a.device_class;
      const ok = (k === "binary" && (OPENING.has(dc) || DANGER.has(dc))) || k === "lock" || k === "alarm" || k === "person" || (k === "cover" && dc === "garage");
      if (!ok) return;
      seen.add(e);
      const what = k === "person" ? (s.s === "home" ? t("a casa") : s.s === "not_home" ? t("fuori") : s.s) : this.value(e).toLowerCase();
      rows.push({ lc: s.lc, html: `<div class="hc-watch"><span>${esc(s.n)} <span class="hc-state ${this.valueClass(e)}">${esc(what)}</span></span><span class="hc-state">${esc(ago(s.lc))}</span></div>` });
    };
    for (const a of this.data.areas) for (const e of a.entities) add(e, a);
    for (const e of [...(this.data.people || []), ...(this.data.alarms || [])]) add(e);
    rows.sort((x, y) => Date.parse(y.lc) - Date.parse(x.lc));
    if (!rows.length) return "";
    return `<section class="hc"><span class="hc-kick">${t("Ultimi eventi")}</span>${rows.slice(0, 6).map((r) => r.html).join("")}</section>`;
  },

  // ---------------------------------------------------------------- what's going on in a room, on the plan
  planIcons(a) {
    const out = [];
    const ents = a.entities.map((e) => [e, this.st(e)]).filter(([, s]) => s);
    if (ents.some(([, s]) => s.k === "binary" && PRESENCE.has(s.a.device_class) && s.s === "on")) out.push(icon("person", "hc-ico pi"));
    if (ents.some(([, s]) => s.k === "media" && s.s === "playing")) out.push(icon("note", "hc-ico pi"));
    if (ents.some(([, s]) => s.k === "vacuum" && ["cleaning", "returning"].includes(s.s))) out.push(icon("robot", "hc-ico pi"));
    if (this.appliances().some((x) => x.on && x.area === a && LAUNDRY.test(x.s.n || ""))) out.push(icon("washer", "hc-ico pi"));
    return out.length ? `<span class="plan-icons">${out.slice(0, 3).join("")}</span>` : "";
  },

  overviewHTML() {
    const lightsOn = this.data.areas.flatMap((a) => this.lightsOf(a).filter((e) => this.isOn(e)).map((e) => [e, a]));
    const sec = this.data.areas.flatMap((a) => a.entities.filter((e) => {
      const s = this.st(e);
      return (s?.k === "binary" && (OPENING.has(s.a.device_class) || DANGER.has(s.a.device_class)) && s.s === "on") || s?.k === "lock" || (s?.k === "siren" && s.s === "on");
    }).map((e) => [e, a]));
    const row = (e, a, right) => `<div class="hc-watch"><span>${esc(this.st(e).n)} <span class="hc-state">${esc(a.name)}</span></span>${right}</div>`;
    return `
      ${this.todayHTML()}
      ${this.appliancesHTML()}
      <section class="hc">
        <span class="hc-kick">${t("Luci accese")}</span>
        ${lightsOn.map(([e, a]) => row(e, a, this.switchHTML(e))).join("") || `<p class="casa-muted">${t("Tutte spente.")}</p>`}
      </section>
      <section class="hc">
        <span class="hc-kick">${t("Porte, finestre, serrature")}</span>
        ${sec.map(([e, a]) => row(e, a, this.st(e).k === "lock" ? `<button class="hc-link" data-act="lock" data-e="${e}">${this.st(e).s === "locked" ? t("Sblocca") : t("Blocca")}</button>` : `<span class="hc-state ${this.valueClass(e)}">${esc(this.value(e).toLowerCase())}</span>`)).join("") || `<p class="casa-muted">${t("Porte e finestre chiuse.")}</p>`}
      </section>`;
  },
};
