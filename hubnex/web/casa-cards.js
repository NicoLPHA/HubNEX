// The house view's cards, in the HQ's holographic style: a dashboard (HUD) at the top of the
// house, a card drawn for each kind of entity, and the quick card of a room. Mixed into
// CasaView (casa.js), so `this` is the view: st(), value(), call()…

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export const num = (v, d = 1) => Number(v).toLocaleString("it-IT", { maximumFractionDigits: d });
const OPENING = new Set(["door", "window", "opening", "garage_door"]);
const DANGER = new Set(["smoke", "moisture", "gas", "safety", "problem", "carbon_monoxide"]);
const PRESENCE = new Set(["motion", "occupancy", "presence"]);
const HVAC = { heat: "Caldo", cool: "Freddo", auto: "Auto", heat_cool: "Auto", off: "Spento", dry: "Deum.", fan_only: "Ventola" };
const ACTION = { heating: "Scalda", cooling: "Raffredda", idle: "In attesa", off: "", drying: "Deumidifica", fan: "Ventola" };

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
};
export const icon = (name, cls = "hc-ico") => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${PATHS[name] || PATHS.gauge}</svg>`;

// "da 35 min", "da 2 h", "da ieri"…
export function since(iso) {
  if (!iso) return "";
  const m = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
  if (m < 1) return "ora";
  if (m < 60) return `da ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `da ${h} h`;
  const d = Math.round(h / 24);
  return d === 1 ? "da ieri" : `da ${d} giorni`;
}

// A ring with tick marks, like Jarvis's instruments.
export function ring({ size = 72, pct = 0, color = "var(--accent)", label = "", sub = "", ticks = 24 }) {
  const cx = size / 2, r = size / 2 - 11, c = 2 * Math.PI * r;
  let t = "";
  for (let i = 0; i < ticks; i++) {
    const a = (i / ticks) * 2 * Math.PI - Math.PI / 2, r1 = size / 2 - 2, r2 = size / 2 - (i % 6 === 0 ? 6 : 4);
    t += `<line x1="${(cx + r1 * Math.cos(a)).toFixed(1)}" y1="${(cx + r1 * Math.sin(a)).toFixed(1)}" x2="${(cx + r2 * Math.cos(a)).toFixed(1)}" y2="${(cx + r2 * Math.sin(a)).toFixed(1)}"/>`;
  }
  const p = Math.max(0, Math.min(1, pct || 0));
  return `<div class="hc-ring" style="width:${size}px;height:${size}px;--rc:${color}"><svg viewBox="0 0 ${size} ${size}" aria-hidden="true">
      <g class="ticks">${t}</g><circle class="track" cx="${cx}" cy="${cx}" r="${r}"/>
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
    const power = d.energy.power && this.st(d.energy.power);
    const watts = power ? parseFloat(power.s) * (/kw/i.test(power.a.unit_of_measurement || "") ? 1000 : 1) : NaN;
    const cams = d.areas.reduce((n, a) => n + a.entities.filter((e) => this.st(e)?.k === "camera").length, 0);
    const parts = [];
    if (people.length) {
      const home = people.filter((e) => this.st(e).s === "home").length;
      parts.push(`<div class="hud-item"><div class="hc-people">${people.map((e) => {
        const s = this.st(e), at = s.s === "home";
        const where = at ? "a casa" : s.s === "not_home" ? "fuori" : s.s;
        return `<span class="hc-avatar ${at ? "home" : ""}" title="${esc(s.n)}: ${esc(where)} ${esc(since(s.lc))}">${esc((s.n || "?").trim()[0] || "?")}</span>`;
      }).join("")}</div><span class="hud-sub">${home ? `${home} in casa` : "nessuno in casa"}</span></div>`);
    }
    if (alarm) {
      const s = this.st(alarm), armed = s.s !== "disarmed", bad = s.s === "triggered";
      parts.push(`<button class="hud-item" data-act="alarm-panel"><span class="hud-dot ${bad ? "bad" : armed ? "ok" : ""}"></span><span><span class="hud-lbl">Allarme</span><span class="hud-val">${esc(this.value(alarm).toLowerCase())}</span></span></button>`);
    }
    if (avg != null) {
      parts.push(`<div class="hud-item">${ring({ size: 38, pct: (avg - 14) / 14 })}<span><span class="hud-big">${num(avg)}<small>°</small></span><span class="hud-sub">${outside != null ? `esterno ${num(outside)}°` : "media della casa"}</span></span></div>`);
    }
    if (allLights.length) {
      parts.push(`<div class="hud-item">${ring({ size: 38, pct: lightsOn.length / allLights.length, color: "var(--warn)" })}<span><span class="hud-big">${lightsOn.length}<small>/${allLights.length}</small></span><span class="hud-sub">luci accese</span></span></div>`);
    }
    if (power) {
      parts.push(`<div class="hud-item"><span><span class="hud-big">${isNaN(watts) ? "—" : num(watts / 1000, 2)}<small>kW</small></span><span class="hud-sub">${d.energy.today ? `oggi ${esc(this.value(d.energy.today))}` : "adesso"}</span></span></div>`);
    }
    if (cams) {
      parts.push(`<button class="hud-item" data-act="cams">${icon("cam")}<span><span class="hud-val">${cams} ${cams === 1 ? "telecamera" : "telecamere"}</span><span class="hud-sub">tocca per vederle</span></span></button>`);
    }
    const scenes = d.scenes.map((e) => `<button class="hc-scene" data-act="scene" data-e="${e}">${esc(this.st(e)?.n || e)}</button>`).join("");
    return `<div class="hud-row">${parts.join("")}</div>
      <div class="hud-actions"><div class="hc-scenes">${scenes}</div><button class="hc-link" data-act="layout" title="Modifica la piantina">Piantina</button></div>`;
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
      case "camera": html = `<div class="hc hc-camcard">${this.camHTML(eid)}</div>`; break;
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
    const state = s.s === "unavailable" ? "non disponibile" : on ? `accesa${dim ? ` · ${pct}%` : ""}` : "spenta";
    return `<article class="hc hc-light ${on ? "on" : ""}" data-act="toggle" data-e="${eid}" role="button" tabindex="0" aria-pressed="${on}" aria-label="${esc(s.n)}">
      ${this.head(s.nk ? "Luce (relè)" : "Luce", s, icon("bulb"))}
      <div class="hc-line"><span class="hc-state">${state}</span>${color}${kelvin}</div>
      ${dim ? `<input class="hc-range" type="range" min="1" max="100" value="${pct || 1}" data-act="bright" data-e="${eid}" aria-label="Luminosità ${esc(s.n)}" ${on ? "" : "disabled"}>` : `<div class="hc-bar"><i style="width:${on ? 100 : 0}%"></i></div>`}
    </article>`;
  },

  switchCard(eid, s) {
    const on = this.isOn(eid);
    const pw = this.data.power?.[eid] && this.st(this.data.power[eid]);
    const domain = eid.split(".")[0];
    const kick = domain === "fan" ? "Ventilatore" : domain === "vacuum" ? "Aspirapolvere" : domain === "humidifier" ? "Umidificatore" : domain === "input_boolean" ? "Interruttore" : "Presa / interruttore";
    return `<article class="hc hc-switch ${on ? "on" : ""}">
      ${this.head(kick, s, this.switchHTML(eid))}
      ${pw ? `<div class="hc-watt"><b>${esc(num(parseFloat(pw.s) || 0, 0))}</b><span class="hc-state">${esc(pw.a.unit_of_measurement || "W")} adesso</span></div>` : `<div class="hc-line"><span class="hc-state">${on ? "acceso" : s.s === "unavailable" ? "non disponibile" : "spento"}</span></div>`}
    </article>`;
  },

  mediaCard(eid, s) {
    const f = Number(s.a.supported_features) || 0;
    const active = ["playing", "paused", "buffering"].includes(s.s);
    if (!active) {
      const note = { idle: "inattivo", off: "spento", on: "acceso", standby: "in standby", unavailable: "non disponibile" }[s.s] || s.s;
      return `<article class="hc hc-media ${s.s === "on" || s.s === "idle" ? "" : ""}">
        ${this.head("Media", s, this.switchHTML(eid))}
        <div class="hc-line"><span class="hc-state">${esc(note)}</span>${s.s !== "off" && (f & 16384 || f & 1) ? `<button class="hc-round" data-act="media" data-s="media_play_pause" data-e="${eid}" aria-label="Riproduci">${icon("play", "hc-ico sm")}</button>` : ""}</div>
      </article>`;
    }
    const title = s.a.media_title || "In riproduzione";
    const artist = s.a.media_artist || "";
    let pos = Number(s.a.media_position);
    const dur = Number(s.a.media_duration);
    if (s.s === "playing" && s.a.media_position_updated_at && !isNaN(pos)) pos += (Date.now() - Date.parse(s.a.media_position_updated_at)) / 1000;
    const pct = dur > 0 && !isNaN(pos) ? Math.min(100, (pos / dur) * 100) : null;
    const t = (x) => { x = Math.max(0, Math.round(x)); const h = Math.floor(x / 3600), m = Math.floor((x % 3600) / 60), sec = x % 60; return `${h ? h + ":" + String(m).padStart(2, "0") : m}:${String(sec).padStart(2, "0")}`; };
    const art = s.a.entity_picture ? `<img src="${esc(s.a.entity_picture)}" alt="" onerror="this.remove()">` : "";
    const playing = s.s === "playing";
    return `<article class="hc hc-media wide on">
      ${this.head("Media", s, `<span class="hc-eq ${playing ? "" : "still"}" aria-hidden="true"><i></i><i></i><i></i><i></i></span>`)}
      <div class="hc-now"><div class="hc-art">${art}</div>
        <div class="hc-nowtxt"><b>${esc(title)}</b><span class="hc-state">${esc(artist)}${pct != null ? `${artist ? " · " : ""}${t(pos)} / ${t(dur)}` : ""}</span>${pct != null ? `<div class="hc-bar thin"><i style="width:${pct}%"></i></div>` : ""}</div></div>
      <div class="hc-transport">
        ${f & 16 ? `<button class="hc-round" data-act="media" data-s="media_previous_track" data-e="${eid}" aria-label="Precedente">${icon("prev", "hc-ico sm")}</button>` : ""}
        <button class="hc-round big" data-act="media" data-s="media_play_pause" data-e="${eid}" aria-label="${playing ? "Pausa" : "Riproduci"}">${icon(playing ? "pause" : "play", "hc-ico sm")}</button>
        ${f & 32 ? `<button class="hc-round" data-act="media" data-s="media_next_track" data-e="${eid}" aria-label="Successivo">${icon("next", "hc-ico sm")}</button>` : ""}
        ${s.a.volume_level != null ? `<label class="hc-vol"><span>VOL</span><input class="hc-range" type="range" min="0" max="100" value="${Math.round(s.a.volume_level * 100)}" data-act="volume" data-e="${eid}" aria-label="Volume ${esc(s.n)}"></label>` : ""}
        ${this.switchHTML(eid)}
      </div>
    </article>`;
  },

  climateCard(eid, s) {
    const cur = s.a.current_temperature, target = s.a.temperature;
    const action = ACTION[s.a.hvac_action] ?? "";
    const modes = (s.a.hvac_modes || []).map((m) => `<button class="hc-tab ${s.s === m ? "sel" : ""}" data-act="hvac" data-e="${eid}" data-m="${m}">${HVAC[m] || m}</button>`).join("");
    return `<article class="hc hc-climate ${s.s !== "off" ? "on" : ""}">
      ${this.head("Clima", s, action ? `<span class="hc-state">${action.toLowerCase()}</span>` : "")}
      <div class="hc-dialrow"><span class="hc-temp">${cur != null ? num(cur) : "—"}<small>°</small></span>
        ${target != null ? `<span class="hc-target"><span class="hc-state">obiettivo ${num(target)}°</span><span class="hc-steps row"><button class="hc-step" data-act="temp" data-e="${eid}" data-d="-1" aria-label="Abbassa">−</button><button class="hc-step" data-act="temp" data-e="${eid}" data-d="1" aria-label="Alza">+</button></span></span>` : ""}</div>
      <div class="hc-tabs">${modes}</div>
      ${s.a.current_humidity != null ? `<span class="hc-state">umidità ${num(s.a.current_humidity, 0)}%</span>` : ""}
    </article>`;
  },

  coverCard(eid, s) {
    const pos = s.a.current_position ?? (s.s === "open" ? 100 : s.s === "closed" ? 0 : 50);
    const state = s.a.current_position != null ? `${pos}% aperta` : { open: "aperta", closed: "chiusa", opening: "si alza…", closing: "si abbassa…" }[s.s] || s.s;
    return `<article class="hc hc-cover">
      ${this.head(this.dc(eid) === "awning" ? "Tenda" : this.dc(eid) === "garage" ? "Garage" : "Tapparella", s, `<span class="hc-state">${esc(state)}</span>`)}
      <div class="hc-blind"><div class="hc-window"><div class="hc-slats" style="height:${100 - pos}%"></div></div>
        <div class="hc-blind-ctl">
          <button class="hc-btn" data-act="cover" data-s="open_cover" data-e="${eid}">▲ Su</button>
          <button class="hc-btn" data-act="cover" data-s="stop_cover" data-e="${eid}">■ Stop</button>
          <button class="hc-btn" data-act="cover" data-s="close_cover" data-e="${eid}">▼ Giù</button>
        </div></div>
    </article>`;
  },

  valveCard(eid, s) {
    const open = s.s === "open" || s.s === "opening";
    const f = Number(s.a.supported_features) || 0;
    const pos = s.a.current_position;
    return `<article class="hc hc-valve ${open ? "on" : ""}">
      ${this.head("Valvola", s, `<span class="hc-state ${open ? "warm" : ""}">${esc(this.value(eid).toLowerCase())}${open && s.lc ? ` ${since(s.lc)}` : ""}</span>`)}
      <div class="hc-dialrow">
        <svg class="hc-pipe" viewBox="0 0 64 64" aria-hidden="true"><path class="tube" d="M6 34h52"/>${open ? '<path class="flow" d="M6 34h52"/>' : ""}<rect class="wheel" x="24" y="14" width="16" height="10" rx="2"/><path class="wheel" d="M32 24v6"/></svg>
        <div class="hc-tabs">
          <button class="hc-tab ${open ? "sel" : ""}" data-act="valve" data-s="open_valve" data-e="${eid}">Apri</button>
          ${f & 8 ? `<button class="hc-tab" data-act="valve" data-s="stop_valve" data-e="${eid}">Ferma</button>` : ""}
          <button class="hc-tab ${open ? "" : "sel"}" data-act="valve" data-s="close_valve" data-e="${eid}">Chiudi</button>
        </div>
      </div>
      ${pos != null ? `<div class="hc-bar"><i style="width:${pos}%"></i></div>` : ""}
    </article>`;
  },

  gateCard(eid, s) {
    const state = { open: "aperto", opening: "apre…", closed: "chiuso", closing: "chiude…", locked: "bloccata", unlocked: "sbloccata" }[s.s] || "";
    return `<article class="hc hc-gate">
      ${this.head("Cancello / porta", s, icon("gate"))}
      <div class="hc-line">${state ? `<span class="hc-state">${state}</span>` : ""}<button class="hc-btn primary" data-act="gate" data-e="${eid}">▶ Comanda</button></div>
    </article>`;
  },

  lockCard(eid, s) {
    const locked = s.s === "locked";
    const asking = this.lockAsk === eid;
    const body = asking
      ? `<div class="hc-ask"><span>Sbloccare ${esc(s.n)}?</span><span class="hc-modes"><button class="hc-btn primary" data-act="lock-yes" data-e="${eid}">Sì, sblocca</button><button class="hc-btn" data-act="lock-no">No</button></span></div>`
      : `<button class="hc-link" data-act="lock" data-e="${eid}">${locked ? "Sblocca" : "Blocca"}</button>`;
    return `<article class="hc hc-lock ${locked ? "" : "warn"}">
      ${this.head("Serratura", s, `<span class="hc-state ${locked ? "good" : "warm"}">${esc(this.value(eid).toLowerCase())}</span>`)}
      ${body}
    </article>`;
  },

  alarmCard(eid, s) {
    const f = Number(s.a.supported_features) || 0;
    const arm = [[1, "alarm_arm_home", "In casa"], [2, "alarm_arm_away", "Fuori"], [4, "alarm_arm_night", "Notte"], [32, "alarm_arm_vacation", "Vacanza"]].filter(([bit]) => f & bit);
    const armed = s.s !== "disarmed";
    const current = { armed_home: "alarm_arm_home", armed_away: "alarm_arm_away", armed_night: "alarm_arm_night", armed_vacation: "alarm_arm_vacation" }[s.s];
    return `<article class="hc hc-alarm ${s.s === "triggered" ? "alert" : ""}">
      ${this.head("Allarme", s, `<span class="hc-state ${s.s === "triggered" ? "bad" : armed ? "good" : ""}">${esc(this.value(eid).toLowerCase())}</span>`)}
      <div class="hc-tabs">${arm.map(([, svc, label]) => `<button class="hc-tab ${current === svc ? "sel ok" : ""}" data-act="alarm" data-s="${svc}" data-e="${eid}" ${armed ? "disabled" : ""}>${label}</button>`).join("")}</div>
      ${armed ? `<button class="hc-btn primary" data-act="alarm" data-s="alarm_disarm" data-e="${eid}">Disinserisci</button>` : ""}
    </article>`;
  },

  binaryCard(eid, s) {
    const dc = s.a.device_class, on = s.s === "on";
    const opening = OPENING.has(dc), danger = DANGER.has(dc), presence = PRESENCE.has(dc);
    const alert = on && (opening || danger);
    const kick = { door: "Porta", window: "Finestra", garage_door: "Basculante", opening: "Apertura", smoke: "Fumo", moisture: "Allagamento", gas: "Gas", carbon_monoxide: "Monossido", motion: "Movimento", occupancy: "Presenza", presence: "Presenza" }[dc] || "Sensore";
    return `<article class="hc hc-binary ${alert ? "alert" : presence && on ? "live" : ""}">
      ${this.head(kick, s, `<span class="hc-state ${alert ? "bad" : presence && on ? "warm" : ""}">${esc(this.value(eid).toLowerCase())} ${esc(since(s.lc))}</span>`)}
    </article>`;
  },

  sensorCard(eid, s) {
    const n = parseFloat(s.s);
    const numeric = !isNaN(n) && !/[^\d.,\-e]/i.test(s.s);
    const kick = { temperature: "Temperatura", humidity: "Umidità", power: "Potenza", energy: "Energia", battery: "Batteria", illuminance: "Luce", pressure: "Pressione", carbon_dioxide: "CO₂", pm25: "PM2.5" }[s.a.device_class] || "Sensore";
    const hist = this.hist?.[eid];
    const vals = (hist || []).map((p) => p[1]);
    return `<article class="hc hc-sensor">
      ${this.head(kick, s, `<span class="hc-num">${numeric ? `${num(n)}<small>${esc(s.a.unit_of_measurement || "")}</small>` : esc(this.value(eid).toLowerCase())}</span>`)}
      ${numeric ? spark(hist) : ""}
      ${vals.length > 1 ? `<span class="hc-state">24 ore · min ${num(Math.min(...vals))} · max ${num(Math.max(...vals))}</span>` : ""}
    </article>`;
  },

  personCard(eid, s) {
    const home = s.s === "home";
    const where = home ? "A casa" : s.s === "not_home" ? "Fuori casa" : s.s;
    return `<article class="hc hc-personcard">
      ${this.head(eid.startsWith("person.") ? "Persona" : "Posizione", s)}
      <div class="hc-line"><span class="hc-person ${home ? "home" : ""}"><span class="hc-avatar big">${esc((s.n || "?").trim()[0] || "?")}</span></span>
        <span class="hc-nowtxt"><span>${esc(where)}</span><span class="hc-state">${esc(since(s.lc))}${s.a.battery_level != null ? ` · batteria ${s.a.battery_level}%` : ""}</span></span></div>
    </article>`;
  },

  sirenCard(eid, s) {
    const on = s.s === "on";
    return `<article class="hc hc-siren ${on ? "alert" : ""}">
      ${this.head("Sirena", s, this.switchHTML(eid))}
      <div class="hc-line"><span class="hc-state ${on ? "bad" : ""}">${on ? "suona" : "spenta"}</span></div>
    </article>`;
  },

  plainCard(eid, s) {
    return `<article class="hc hc-plain">${this.head(eid.split(".")[0].replace(/_/g, " "), s, `<span class="hc-state">${esc(String(this.value(eid)).toLowerCase())}</span>`)}</article>`;
  },

  // ---------------------------------------------------------------- quick card of a room
  quickHTML(a) {
    const lights = this.lightsOf(a);
    const climate = a.entities.find((e) => this.st(e)?.k === "climate");
    const t = this.temp(a);
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
    const figures = [t != null ? `${num(t)}°` : "", hum ? `${num(parseFloat(hum.s), 0)}%` : ""].filter(Boolean).join(" · ");
    const watchRow = (e) => {
      const s = this.st(e);
      const pw = this.data.power?.[e] && this.st(this.data.power[e]);
      const right = s.k === "lock" ? `<button class="hc-btn" data-act="lock" data-e="${e}">Blocca</button>`
        : s.k === "valve" ? `<button class="hc-btn" data-act="valve" data-s="close_valve" data-e="${e}">Chiudi</button>`
        : s.k === "switch" || s.k === "siren" ? this.switchHTML(e) : "";
      const what = s.k === "switch" && pw ? `${num(parseFloat(pw.s), 0)} ${pw.a.unit_of_measurement || "W"} · ${since(s.lc)}` : `${this.value(e).toLowerCase()} ${since(s.lc)}`;
      return `<div class="hc-watch"><span>${esc(s.n)} <span class="hc-state bad">${esc(what)}</span></span>${right}</div>`;
    };
    return `
      <section class="hc casa-quick">
        <div class="hc-grab" data-act="unselect" aria-hidden="true"></div>
        <div class="hc-head"><div><h2>${esc(a.name)}</h2></div>
          <span class="hc-num">${figures}</span><button class="casa-x" data-act="unselect" aria-label="Chiudi">×</button></div>
        ${lights.length ? `<span class="hc-kick">Luci</span><div class="hc-tiles">${lights.slice(0, 8).map((e) => {
          const s = this.st(e), on = s.s === "on";
          const pct = on && s.a.brightness != null ? Math.round((s.a.brightness / 255) * 100) : on ? 100 : 0;
          return `<button class="hc-tile ${on ? "on" : ""}" data-act="toggle" data-e="${e}" aria-pressed="${on}"><b>${esc(s.n)}</b><span class="hc-state">${on ? `accesa${pct < 100 ? ` · ${pct}%` : ""}` : "spenta"}</span><span class="hc-bar thin"><i style="width:${pct}%"></i></span></button>`;
        }).join("")}</div>${lights.length > 8 ? `<p class="casa-muted">+ altre ${lights.length - 8}</p>` : ""}` : ""}
        ${climate ? this.climateMini(climate) : ""}
        ${watch.length ? `<span class="hc-kick">Da tenere d'occhio</span>${watch.map(watchRow).join("")}` : ""}
        ${cam ? this.camHTML(cam) : ""}
        ${!a.entities.length ? `<p class="casa-muted">Nessuna entità in quest'area. Aprila e aggiungine con "Modifica stanza".</p>` : ""}
        <div class="casa-actions">
          <button class="hc-open" data-act="open" data-area="${a.id}">Apri stanza →</button>
          ${lights.some((e) => this.isOn(e)) ? `<button class="hc-link" data-act="all-off" data-area="${a.id}">Spegni luci</button>` : ""}
        </div>
      </section>`;
  },

  climateMini(eid) {
    const s = this.st(eid), target = s.a.temperature;
    return `<div class="hc-climini"><span>${esc(s.n)} <span class="hc-state">${esc((HVAC[s.s] || s.s).toLowerCase())}${s.a.current_temperature != null ? ` · ${num(s.a.current_temperature)}°` : ""}</span></span>
      ${target != null ? `<span class="hc-steps row"><button class="hc-step" data-act="temp" data-e="${eid}" data-d="-1" aria-label="Abbassa">−</button><b>${num(target)}°</b><button class="hc-step" data-act="temp" data-e="${eid}" data-d="1" aria-label="Alza">+</button></span>` : ""}</div>`;
  },

  // Overview (no room chosen): lights on and what needs attention, as compact cards.
  overviewHTML() {
    const lightsOn = this.data.areas.flatMap((a) => this.lightsOf(a).filter((e) => this.isOn(e)).map((e) => [e, a]));
    const sec = this.data.areas.flatMap((a) => a.entities.filter((e) => {
      const s = this.st(e);
      return (s?.k === "binary" && (OPENING.has(s.a.device_class) || DANGER.has(s.a.device_class)) && s.s === "on") || s?.k === "lock" || (s?.k === "siren" && s.s === "on");
    }).map((e) => [e, a]));
    const row = (e, a, right) => `<div class="hc-watch"><span>${esc(this.st(e).n)} <span class="hc-state">${esc(a.name)}</span></span>${right}</div>`;
    return `
      <section class="hc">
        <span class="hc-kick">Luci accese</span>
        ${lightsOn.map(([e, a]) => row(e, a, this.switchHTML(e))).join("") || `<p class="casa-muted">Tutte spente.</p>`}
      </section>
      <section class="hc">
        <span class="hc-kick">Porte, finestre, serrature</span>
        ${sec.map(([e, a]) => row(e, a, this.st(e).k === "lock" ? `<button class="hc-link" data-act="lock" data-e="${e}">${this.st(e).s === "locked" ? "Sblocca" : "Blocca"}</button>` : `<span class="hc-state ${this.valueClass(e)}">${esc(this.value(e).toLowerCase())}</span>`)).join("") || `<p class="casa-muted">Porte e finestre chiuse.</p>`}
      </section>`;
  },
};
