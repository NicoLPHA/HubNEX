import { PlanEditor } from "./plan-editor.js";
import { Cards } from "./casa-cards.js";
import { Energy } from "./casa-energy.js";

// The house view: Home Assistant areas on the owner's floor plan, live.
// Tap a room for its quick card, "Apri stanza" for all its entities; buttons call Home
// Assistant directly (no AI, no credit). Rooms are HA areas: entities can be moved between
// areas (in HA) or just shown/hidden here.

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (v, d = 1) => Number(v).toLocaleString("it-IT", { maximumFractionDigits: d });
const ALERT = new Set(["door", "window", "opening", "garage_door", "smoke", "moisture", "gas", "safety", "problem", "carbon_monoxide"]);
const OPENING = new Set(["door", "window", "opening", "garage_door"]);
const PRESENCE = new Set(["motion", "occupancy", "presence"]);
const SECURITY_CLASSES = new Set([...ALERT, ...PRESENCE, "lock", "tamper", "vibration", "sound"]);
const APPLIANCE = /bollitor|kettle|boiler|caldai|scaldabagn|acqua|water|frigo|fridge|freezer|congelat|forno|oven|piastr|lavatric|lavastovigl|asciugatric|cpu|processor|chip|batter|intern|motor|esterna|outdoor|pompa|pump|vasca|piscina|pool/i;
const SHOW_AS = [["", "Come in Home Assistant"], ["light", "Luce"], ["switch", "Presa / interruttore"], ["gate", "Cancello / porta (impulso)"], ["siren", "Sirena"], ["sensor", "Solo stato"]];
const SECTIONS = [
  ["light", "Luci"], ["gate", "Cancelli e porte"], ["climate", "Clima"], ["cover", "Tapparelle e tende"], ["valve", "Valvole e irrigazione"], ["media", "Media"],
  ["switch", "Prese e interruttori"], ["people", "Persone"], ["security", "Sicurezza"], ["camera", "Telecamere"], ["sensor", "Sensori"], ["settings", "Orari e impostazioni"], ["action", "Azioni"], ["other", "Altro"],
];

// Home Assistant's own frontend, when Jarvis is open inside it (same origin): its connection
// gives the same camera streams HA's dashboards use.
function haParent() {
  try {
    const hass = window.parent !== window && window.parent.document.querySelector("home-assistant")?.hass;
    return hass?.connection ? hass : null;
  } catch {
    return null;
  }
}


const scripts = {};
function loadScript(src) {
  scripts[src] ||= new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = ok;
    s.onerror = () => fail(new Error(`non riesco a caricare ${src}`));
    document.head.appendChild(s);
  });
  return scripts[src];
}

export class CasaView {
  constructor(root, { api, token }) {
    this.root = root;
    this.api = api;
    this.token = token || (() => "");
    this.camTick = Date.now();
    this.camSrc = {}; // last frame loaded, per camera
    this.editor = new PlanEditor({
      api, token: this.token,
      onSaved: () => { this.toast("Piantina salvata"); this.reload(true); },
      onText: () => this.openLayout(),
      toast: (t) => this.toast(t),
    });
    this.live = null; // the camera (or camera grid) open over the view
    setInterval(() => this.refreshCameras(), 1000);
    addEventListener("keydown", (e) => { if (e.key === "Escape") this.closeCamera(); });
    this.data = null;
    this.loading = null;
    this.selected = null; // area id of the quick card
    this.page = null; // area id of the full room page
    this.editing = false;
    this.mode = "ha";
    this.floor = 0;
    this.layout = null; // floor plan editor state
    this.dirty = false;
    root.addEventListener("click", (e) => this._click(e));
    root.addEventListener("change", (e) => this._change(e));
    root.addEventListener("input", (e) => this._input(e));
    root.addEventListener("focusout", () => { if (this.dirty) setTimeout(() => this.render(), 0); });
    root.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.matches?.("[role=button][data-act]")) { e.preventDefault(); e.target.click(); }
    });
    root.addEventListener("pointerdown", (e) => this._dragStart(e));
    // Phone: the quick card is a sheet over the plan. Drag it down to close, up to open the room.
    root.addEventListener("touchstart", (e) => { this._touchY = e.target.closest(".hc-grab, .casa-quick > .hc-head") ? e.touches[0].clientY : null; }, { passive: true });
    root.addEventListener("touchend", (e) => {
      if (this._touchY == null || !this.selected) return;
      const dy = e.changedTouches[0].clientY - this._touchY;
      this._touchY = null;
      if (dy > 70) { this.selected = null; this.render(true); }
      else if (dy < -70) { this.page = this.selected; this.render(true); }
    }, { passive: true });
    addEventListener("keydown", (e) => {
      if (!this.pad || !this.visible || e.target.id === "pad-text") return;
      if (/^[0-9]$/.test(e.key)) this.padKey(e.key);
      else if (e.key === "Backspace") this.padKey("back");
      else if (e.key === "Enter") this.padKey("ok");
      else return;
      e.preventDefault();
    });
  }

  // ------------------------------------------------------------------ lifecycle
  async open() {
    this.visible = true;
    if (!this.data) await this.reload();
    else this.render();
    const e = this.data?.energy_panel;
    if (e && (e.power || Object.keys(e.bands || {}).length) && !this.energyLive) this.loadEnergy(); // the band now, for the dashboard
  }

  close() { this.visible = false; document.body.classList.remove("casa-sheet", "casa-modal-open"); }

  async reload(force = false) {
    this.loading ??= (async () => {
      try {
        this.data = await (await this.api("/api/casa")).json();
        this.error = null;
      } catch (err) {
        this.error = err.message;
      } finally {
        this.loading = null;
      }
    })();
    await this.loading;
    this.render(force);
  }

  // Live events from the HQ WebSocket.
  handle(ev) {
    if (ev.type === "casa_changed") { if (this.visible) this.reload(); else this.data = null; return; }
    if (ev.type === "ha" && this.data) {
      if (ev.v) this.data.states[ev.e] = ev.v; else delete this.data.states[ev.e];
      if (this.visible) this.renderSoon();
    }
  }

  // What the chat should know: the room open on screen.
  context() {
    const a = this.page && this.area(this.page);
    return a ? `[Sono nella stanza ${a.name} della vista Casa] ` : "";
  }

  renderSoon() {
    if (this._timer) return;
    this._timer = setTimeout(() => { this._timer = null; this.render(); }, 250);
  }

  // ------------------------------------------------------------------ helpers
  area(id) { return this.data?.areas.find((a) => a.id === id); }
  st(eid) { return this.data?.states[eid]; }
  dc(eid) { return this.st(eid)?.a?.device_class; }
  isOn(eid) { const s = this.st(eid); return !!s && ["on", "open", "opening", "playing", "unlocked", "heat", "cool", "auto", "heat_cool"].includes(s.s); }
  lightsOf(a) { return a.entities.filter((e) => this.st(e)?.k === "light"); }
  lit(a) { return this.lightsOf(a).some((e) => this.isOn(e)); }

  alerts(a) {
    return a.entities.filter((e) => { const s = this.st(e); return s?.s === "on" && ((s.k === "binary" && ALERT.has(s.a.device_class)) || s.k === "siren"); });
  }

  // Everything in the room that measures a temperature: thermostats and temperature sensors.
  tempSources(a) {
    return a.entities.filter((e) => {
      const s = this.st(e);
      return (s?.k === "climate" && s.a.current_temperature != null) || (s?.k === "sensor" && s.a.device_class === "temperature");
    });
  }

  readTemp(eid) {
    const s = this.st(eid);
    if (!s) return null;
    const v = s.k === "climate" ? Number(s.a.current_temperature) : parseFloat(s.s);
    return isNaN(v) ? null : v;
  }

  // The room's temperature: the source the owner picked, else a thermostat, else a sensor that
  // isn't measuring an appliance (kettle, fridge, boiler…).
  tempSource(a) {
    const sources = this.tempSources(a);
    if (a.temp && sources.includes(a.temp)) return a.temp;
    const ok = (e) => this.readTemp(e) != null;
    return sources.find((e) => this.st(e).k === "climate" && ok(e))
      || sources.find((e) => ok(e) && !APPLIANCE.test(`${e} ${this.st(e).n}`))
      || sources.find(ok) || null;
  }

  temp(a) {
    const e = this.tempSource(a);
    return e ? this.readTemp(e) : null;
  }

  value(eid) {
    const s = this.st(eid);
    if (!s) return "—";
    if (["unavailable", "unknown"].includes(s.s)) return s.s === "unknown" ? "—" : "N/D";
    if (s.k === "binary") {
      const dc = s.a.device_class;
      if (OPENING.has(dc)) return s.s === "on" ? "APERTA" : "CHIUSA";
      if (PRESENCE.has(dc)) return s.s === "on" ? "RILEVATO" : "NESSUNO";
      if (dc === "moisture") return s.s === "on" ? "ACQUA!" : "ASCIUTTO";
      if (dc === "smoke" || dc === "gas" || dc === "carbon_monoxide") return s.s === "on" ? "ALLARME!" : "OK";
      return s.s === "on" ? "ON" : "OFF";
    }
    if (s.k === "valve") return { open: "APERTA", closed: "CHIUSA", opening: "APRE…", closing: "CHIUDE…" }[s.s] || s.s.toUpperCase();
    if (s.k === "person") return s.s === "home" ? "A CASA" : s.s === "not_home" ? "FUORI CASA" : s.s.toUpperCase(); // or the zone's name
    if (s.k === "lock") return { locked: "BLOCCATA", unlocked: "SBLOCCATA", locking: "BLOCCO…", unlocking: "SBLOCCO…", jammed: "INCEPPATA", open: "APERTA" }[s.s] || s.s.toUpperCase();
    if (s.k === "alarm") return { disarmed: "DISINSERITO", armed_home: "IN CASA", armed_away: "INSERITO", armed_night: "NOTTE", triggered: "SCATTATO!", pending: "IN ATTESA", arming: "INSERIMENTO" }[s.s] || s.s;
    if (s.k === "sensor") {
      const n = parseFloat(s.s);
      return isNaN(n) || /[^\d.,\-e]/i.test(s.s) ? s.s : `${num(n, Math.abs(n) < 10 && n % 1 ? 2 : 1)}${s.a.unit_of_measurement ? " " + s.a.unit_of_measurement : ""}`;
    }
    return s.s;
  }

  valueClass(eid) {
    const s = this.st(eid);
    if (!s) return "";
    if (s.k === "binary" && ALERT.has(s.a.device_class)) return s.s === "on" ? "bad" : "good";
    if (s.k === "lock") return s.s === "locked" ? "good" : "warn";
    if (s.k === "valve") return s.s === "open" || s.s === "opening" ? "warm" : "";
    if (s.k === "person") return s.s === "home" ? "good" : "";
    if (s.k === "alarm") return s.s === "triggered" ? "bad" : s.s === "disarmed" ? "" : "good";
    return "";
  }

  section(eid) {
    const s = this.st(eid);
    if (!s) return "other";
    if (["light", "gate", "climate", "cover", "valve", "media", "switch"].includes(s.k)) return s.k;
    if (s.k === "person") return "people";
    if (s.k === "lock" || s.k === "alarm" || s.k === "siren") return "security";
    if (s.k === "binary") return SECURITY_CLASSES.has(s.a.device_class) ? "security" : "sensor";
    if (s.k === "sensor") return "sensor";
    if (s.k === "scene" || s.k === "script" || s.k === "button") return "action";
    if (s.k === "camera") return "camera";
    if (["datetime", "number", "select", "text"].includes(s.k)) return "settings";
    return "other";
  }

  // A gate/door command: press a button, run a script, or give a relay a one-second impulse.
  gate(eid) {
    const domain = eid.split(".")[0];
    const s = this.st(eid);
    if (domain === "button" || domain === "input_button") this.call(domain, "press", { entity_id: eid });
    else if (domain === "script" || domain === "scene") this.call(domain, "turn_on", { entity_id: eid });
    else if (domain === "cover") this.call("cover", "toggle", { entity_id: eid });
    else if (domain === "lock") return this.lock(eid);
    else {
      this.call("homeassistant", "turn_on", { entity_id: eid });
      setTimeout(() => this.call("homeassistant", "turn_off", { entity_id: eid }), 1000);
    }
    this.toast(`▶ ${s?.n || eid}`);
  }

  // ---------------------------------------------------------------- cameras
  // Thumbnails are still frames through the add-on. A new frame replaces the old one only
  // once it has loaded, and redraws reuse the last loaded frame: they never go black.
  camURL(eid, tick = Date.now(), stream = false) {
    const t = this.token();
    const q = [stream ? "" : `t=${tick}`, t ? `token=${encodeURIComponent(t)}` : ""].filter(Boolean).join("&");
    return `api/casa/camera/${encodeURIComponent(eid)}${stream ? "/stream" : ""}${q ? "?" + q : ""}`;
  }

  camHTML(eid) {
    const s = this.st(eid);
    const live = { streaming: "IN DIRETTA", recording: "REGISTRA" }[s?.s] || "";
    this.camSrc[eid] ||= this.camURL(eid);
    return `<button class="casa-cam" data-act="cam" data-e="${eid}" aria-label="Telecamera ${esc(s?.n || eid)}">
      <img data-cam="${eid}" src="${this.camSrc[eid]}" alt="">
      <span class="casa-cam-label">${esc(s?.n || eid)}${live ? ` · ${live}` : ""}</span></button>`;
  }

  refreshCameras() {
    if (!this.visible || document.hidden || Date.now() - this.camTick < 5000) return;
    this.camTick = Date.now();
    const eids = new Set([...document.querySelectorAll("img[data-cam]")].map((i) => i.dataset.cam));
    for (const eid of eids) {
      const url = this.camURL(eid);
      const next = new Image();
      next.onload = () => {
        this.camSrc[eid] = url;
        document.querySelectorAll(`img[data-cam="${CSS.escape(eid)}"]`).forEach((i) => { i.src = url; });
      };
      next.src = url;
    }
  }

  // All cameras at a glance (the chip at the top of the house view).
  openCameraGrid() {
    const cams = this.data.areas.flatMap((a) => a.entities.filter((e) => this.st(e)?.k === "camera"));
    const box = this.overlay("Telecamere", `<div class="casa-cams">${cams.map((e) => this.camHTML(e)).join("")}</div>`);
    box.addEventListener("click", (e) => {
      const cam = e.target.closest("[data-act='cam']");
      if (cam) this.openCamera(cam.dataset.e);
    });
  }

  // Live video: the player Home Assistant itself uses (HLS stream from HA) when Jarvis runs
  // inside Home Assistant, otherwise MJPEG through the add-on. It sits outside the view's
  // HTML, so the view's redraws never restart it.
  // Tries, in order: HA's own HLS stream (inside Home Assistant), MJPEG through the add-on,
  // and as a last resort a still frame every second. The header says which one is running and,
  // if video failed, why.
  async openCamera(eid) {
    const s = this.st(eid);
    const box = this.overlay(s?.n || eid, `<div class="cam-mode">Avvio video…</div><div class="cam-stage"><img class="cam-still" src="${this.camSrc[eid] || this.camURL(eid)}" alt=""></div>`, true);
    const stage = box.querySelector(".cam-stage");
    const mode = (text, on = false) => { const m = box.querySelector(".cam-mode"); m.textContent = text; m.classList.toggle("on", on); };
    const live = this.live;
    const why = [];
    const hass = haParent();
    if (!hass) why.push("HLS: HubNEX non è aperto dentro Home Assistant");
    else if (!(Number(s?.a.supported_features) & 2)) why.push("HLS: la telecamera non offre un flusso video");
    else {
      try {
        const { url } = await hass.connection.sendMessagePromise({ type: "camera/stream", entity_id: eid, format: "hls" });
        if (this.live !== live) return;
        await this.playHLS(stage, url, live);
        mode("● LIVE", true);
        return;
      } catch (err) {
        why.push(`HLS: ${err.message || err.code || err}`);
        this.stopVideo(live);
        if (this.live !== live) return;
      }
    }
    try {
      await this.playMJPEG(stage, eid, live);
      mode("● LIVE · MJPEG", true);
      return;
    } catch (err) {
      why.push(`MJPEG: ${err.message}`);
      if (live.img) { live.img.src = ""; live.img.remove(); live.img = null; }
      if (this.live !== live) return;
    }
    mode(`Istantanee ogni secondo — video non disponibile (${why.join("; ")})`);
    const still = stage.querySelector(".cam-still");
    live.timer = setInterval(() => {
      const url = this.camURL(eid);
      const next = new Image();
      next.onload = () => { if (still) still.src = url; };
      next.src = url;
    }, 1000);
  }

  // Resolves once the video really plays; rejects on error or after 12 s of nothing.
  async playHLS(stage, url, live) {
    const video = document.createElement("video");
    Object.assign(video, { muted: true, autoplay: true, playsInline: true });
    video.className = "cam-live";
    stage.appendChild(video);
    live.video = video;
    // Like Home Assistant: hls.js wherever it works (Android, PC), native HLS only otherwise
    // (iPhone). Some Android WebViews say they play HLS natively but then don't.
    await loadScript("static/vendor/hls/hls.light.min.js").catch(() => {});
    const playing = new Promise((ok, fail) => {
      const timer = setTimeout(() => fail(new Error("nessuna immagine dopo 12 secondi")), 12000);
      video.addEventListener("playing", () => { clearTimeout(timer); ok(); }, { once: true });
      video.addEventListener("error", () => { clearTimeout(timer); fail(new Error(`errore del video (${video.error?.code})`)); }, { once: true });
      if (window.Hls?.isSupported()) {
        const hls = (live.hls = new window.Hls({ backBufferLength: 10, liveSyncDurationCount: 2 }));
        hls.on(window.Hls.Events.ERROR, (_, d) => { if (d.fatal) { clearTimeout(timer); fail(new Error(d.details || d.type)); } });
        hls.loadSource(url);
        hls.attachMedia(video);
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = url;
      } else {
        clearTimeout(timer);
        fail(new Error("il browser non riproduce HLS"));
      }
    });
    video.play().catch(() => {});
    await playing;
    stage.querySelector(".cam-still")?.remove();
  }

  stopVideo(live) {
    live.hls?.destroy();
    live.hls = null;
    if (live.video) { live.video.pause(); live.video.removeAttribute("src"); live.video.load(); live.video.remove(); live.video = null; }
  }

  // MJPEG from the add-on: resolves at the first frame.
  async playMJPEG(stage, eid, live) {
    const img = document.createElement("img");
    img.className = "cam-live";
    img.alt = "";
    img.src = this.camURL(eid, 0, true);
    stage.appendChild(img);
    live.img = img;
    const start = Date.now();
    while (!img.naturalWidth) {
      if (this.live !== live) return;
      if (Date.now() - start > 10000) throw new Error("nessuna immagine dopo 10 secondi");
      await new Promise((r) => setTimeout(r, 250));
    }
  }

  overlay(title, body, isLive = false) {
    this.closeCamera();
    const box = document.createElement("div");
    box.className = "casa-modal casa-overlay";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-label", title);
    box.innerHTML = `<section class="panel casa-panel ${isLive ? "casa-cam-modal" : "casa-cam-grid"}">
      <h3>${esc(title)} <button class="casa-x" aria-label="Chiudi">×</button></h3>${body}</section>`;
    box.querySelector(".casa-x").addEventListener("click", () => this.closeCamera());
    box.addEventListener("click", (e) => { if (e.target === box) this.closeCamera(); });
    document.body.appendChild(box);
    this.live = { box };
    return box;
  }

  closeCamera() {
    const live = this.live;
    if (!live) return;
    this.live = null;
    clearInterval(live.timer);
    this.stopVideo(live);
    if (live.img) live.img.src = ""; // closes the MJPEG connection
    live.box.remove();
  }

  // ---------------------------------------------------------------- alarm
  // Locks are not alarms: with a code in Home Assistant the keypad, otherwise a "Sì / No"
  // inside the card. Locking needs no confirmation.
  lock(eid) {
    const s = this.st(eid);
    if (!s) return;
    if (s.s !== "locked") { this.call("lock", "lock", { entity_id: eid }, eid); this.toast(`Blocco ${s.n}…`); return; }
    if (s.a.code_format) this.pad = { eid, domain: "lock", service: "unlock", code: "", error: "", busy: false };
    else this.lockAsk = eid;
    this.render(true);
  }

  alarm(eid, service) {
    const s = this.st(eid);
    const disarm = service === "alarm_disarm";
    if (s.a.code_format && (disarm || s.a.code_arm_required !== false)) {
      // The keypad is the confirmation: nothing happens until the code is sent.
      this.pad = { eid, domain: "alarm_control_panel", service, code: "", error: "", busy: false };
      this.render(true);
      return;
    }
    if (disarm && !confirm(`Disinserire ${s.n}?`)) return;
    this.call("alarm_control_panel", service, { entity_id: eid }, eid);
    this.toast(disarm ? "Disinserisco l'allarme…" : "Inserisco l'allarme…");
  }

  padKey(key) {
    const p = this.pad;
    if (!p || p.busy) return;
    if (key === "back") p.code = p.code.slice(0, -1);
    else if (key === "ok") return this.padSend();
    else if (p.code.length < 12) p.code += key;
    p.error = "";
    const dots = this.root.querySelector(".pad-dots");
    if (dots) { dots.textContent = "●".repeat(p.code.length) || "—"; this.root.querySelector(".pad-error").textContent = ""; }
  }

  async padSend() {
    const p = this.pad;
    if (!p?.code) return;
    p.busy = true;
    const disarm = p.service === "alarm_disarm";
    try {
      await this.api("/api/casa/call", { method: "POST", body: JSON.stringify({ domain: p.domain, service: p.service, data: { entity_id: p.eid, code: p.code } }) });
      this.pad = null;
      this.toast(p.domain === "lock" ? "Sblocco…" : disarm ? "Disinserisco l'allarme…" : "Inserisco l'allarme…");
    } catch (err) {
      // Wrong code (or the alarm said no): stay on the keypad.
      Object.assign(p, { busy: false, code: "", error: /code|codice/i.test(err.message) ? "Codice errato" : `⚠ ${err.message.replace(/^\{"detail":"|"\}$/g, "")}` });
    }
    this.render(true);
  }

  padHTML() {
    const p = this.pad, s = this.st(p.eid);
    const label = { unlock: "Sblocca", alarm_disarm: "Disinserisci", alarm_arm_home: "Inserisci · In casa", alarm_arm_away: "Inserisci · Fuori", alarm_arm_night: "Inserisci · Notte", alarm_arm_vacation: "Inserisci · Vacanza" }[p.service] || p.service;
    const numeric = s?.a.code_format !== "text";
    const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "ok"];
    const body = numeric
      ? `<div class="pad-dots" aria-live="polite">${"●".repeat(p.code.length) || "—"}</div>
         <div class="pad-keys">${keys.map((k) => `<button data-act="pad" data-k="${k}" class="${k === "ok" ? "ok" : ""}" aria-label="${k === "back" ? "Cancella" : k === "ok" ? "Conferma" : k}">${k === "back" ? "⌫" : k === "ok" ? "✓" : k}</button>`).join("")}</div>`
      : `<input type="password" id="pad-text" autocomplete="off" aria-label="Codice"><div class="casa-actions"><button class="casa-primary" data-act="pad-text">Conferma</button></div>`;
    return `<div class="casa-modal" role="dialog" aria-label="Codice"><section class="panel casa-panel casa-pad ${p.service === "alarm_disarm" || p.service === "unlock" ? "disarm" : ""}">
      <h3>${esc(label)} <button class="casa-x" data-act="pad-close" aria-label="Annulla">×</button></h3>
      <div class="casa-sub">${esc(s?.n || p.eid)}</div>
      ${body}
      <div class="pad-error" role="alert">${esc(p.error || "")}</div>
    </section></div>`;
  }

  async call(domain, service, data, eid) {
    try {
      await this.api("/api/casa/call", { method: "POST", body: JSON.stringify({ domain, service, data }) });
    } catch (err) {
      this.toast(`⚠ ${err.message}`);
      if (eid) this.reload();
    }
  }

  toast(text) {
    // Outside the view's own HTML, or the next live redraw would wipe it.
    let t = document.querySelector(".casa-toast");
    if (!t) { t = document.createElement("div"); t.className = "casa-toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
    t.textContent = text;
    t.classList.add("on");
    clearTimeout(this._toast);
    this._toast = setTimeout(() => t.classList.remove("on"), 4000);
  }

  // ------------------------------------------------------------------ events
  async _click(e) {
    const el = e.target.closest("[data-act]");
    if (!el || !this.root.contains(el)) return;
    const { act, e: eid, area } = el.dataset;
    const domain = eid?.split(".")[0];
    if (this.editing && act === "toggle" && el.tagName === "ARTICLE") return; // arranging, not switching
    if (await this.energyClick(act, el)) return;
    switch (act) {
      case "room":
        this.selected = this.selected === area ? null : area;
        // On a phone the card sits under the plan: bring it up after drawing it.
        if (this.selected && innerWidth < 1100) setTimeout(() => this.root.querySelector(".casa-quick")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
        break;
      case "open": this.page = area; this.selected = area; this.editing = false; this.energyOpen = false; this.root.scrollTop = 0; break;
      case "home": this.page = null; this.editing = false; break;
      case "unselect": this.selected = null; break;
      case "floor": this.floor = Number(el.dataset.i); break;
      case "toggle": {
        const s = this.st(eid);
        if (s) s.s = s.s === "on" ? "off" : "on"; // optimistic: the live event confirms it
        this.call(domain === "media_player" ? "media_player" : domain, "toggle", { entity_id: eid }, eid);
        break;
      }
      case "scene": this.call(domain, domain === "button" || domain === "input_button" ? "press" : "turn_on", { entity_id: eid }); this.toast(`▶ ${this.st(eid)?.n || eid}`); return;
      case "all-off": {
        const lights = this.lightsOf(this.area(area)).filter((x) => this.isOn(x));
        // homeassistant.turn_off: the "lights" may be relays shown as lights (switch.*)
        if (lights.length) this.call("homeassistant", "turn_off", { entity_id: lights });
        lights.forEach((x) => { this.st(x).s = "off"; });
        break;
      }
      case "temp": {
        const s = this.st(eid);
        const step = Number(s.a.target_temp_step) || 0.5;
        const t = Math.round(((Number(s.a.temperature) || 20) + step * Number(el.dataset.d)) * 10) / 10;
        s.a.temperature = t;
        this.call("climate", "set_temperature", { entity_id: eid, temperature: t });
        break;
      }
      case "gate": this.gate(eid); return;
      case "alarm": this.alarm(eid, el.dataset.s); return;
      case "cam": this.openCamera(eid); return;
      case "cams": this.openCameraGrid(); return;
      case "pad": this.padKey(el.dataset.k); return;
      case "pad-text": this.pad.code = this.root.querySelector("#pad-text")?.value || ""; this.padSend(); return;
      case "pad-close": this.pad = null; break;
      case "alarm-panel": this.alarmOpen = true; break;
      case "alarm-close": this.alarmOpen = false; break;
      case "kind": return;
      case "hvac": this.st(eid).s = el.dataset.m; this.call("climate", "set_hvac_mode", { entity_id: eid, hvac_mode: el.dataset.m }); break;
      case "cover": this.call(domain, el.dataset.s, { entity_id: eid }); return;
      case "valve": this.call("valve", el.dataset.s, { entity_id: eid }, eid); return;
      case "media": this.call("media_player", el.dataset.s, { entity_id: eid }, eid); return;
      case "lock": this.lock(eid); return;
      case "lock-yes": this.lockAsk = null; this.call("lock", "unlock", { entity_id: eid }, eid); this.toast(`Sblocco ${this.st(eid)?.n || eid}…`); break;
      case "lock-no": this.lockAsk = null; break;
      case "edit": this.editing = !this.editing; if (this.editing) this.search(""); break;
      // helpers (time of day, numbers, lists)
      case "pick": { const input = el.parentElement.querySelector("input[data-act='dt']"); try { input.showPicker(); } catch { input.focus(); } return; }
      case "nudge": {
        const st = this.st(eid), t = (String(st?.s).match(/\d{2}:\d{2}/) || ["00:00"])[0];
        const m = (((Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5)) + Number(el.dataset.d)) % 1440) + 1440) % 1440;
        this.setDateTime(eid, `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`);
        break;
      }
      case "numstep": {
        const st = this.st(eid), step = Number(st.a.step ?? 1);
        const v = Math.min(Number(st.a.max ?? Infinity), Math.max(Number(st.a.min ?? -Infinity), (parseFloat(st.s) || 0) + step * Number(el.dataset.d)));
        this.setNumber(eid, Math.round(v / step) * step);
        break;
      }
      case "selopt": if (el.tagName === "SELECT") return; this.setOption(eid, el.dataset.v); break;
      // the room's cards, arranged by the owner
      case "move": this.moveItem(el.dataset.id, Number(el.dataset.d)); return;
      case "size": {
        const id = el.dataset.id, w = el.dataset.w;
        if (id.startsWith("card:")) {
          const a = this.area(this.page), card = a.cards.find((c) => `card:${c.id}` === id);
          if (card) { card.size = w; this.api(`/api/casa/rooms/${encodeURIComponent(a.id)}/cards`, { method: "POST", body: JSON.stringify(card) }).catch((err) => this.toast(`⚠ ${err.message}`)); }
        } else {
          (this.data.sizes ||= {})[id] = w;
          if (w !== "wide") delete this.data.sizes[id];
          this.api(`/api/casa/entities/${encodeURIComponent(id)}/display`, { method: "POST", body: JSON.stringify({ size: w }) }).catch((err) => this.toast(`⚠ ${err.message}`));
        }
        break;
      }
      case "rename": this.renaming = { eid, name: this.st(eid)?.n || "" }; break;
      case "rename-close": this.renaming = null; break;
      case "rename-save": case "rename-reset": {
        const name = act === "rename-reset" ? null : this.root.querySelector("#casa-rename").value.trim() || null;
        const e = this.renaming.eid;
        this.renaming = null;
        await this.api(`/api/casa/entities/${encodeURIComponent(e)}/display`, { method: "POST", body: JSON.stringify({ name }) }).catch((err) => this.toast(`⚠ ${err.message}`));
        await this.reload(true);
        return;
      }
      case "order-reset": this.saveOrder([]); break;
      case "card-new": this.cardEdit = { area: this.page, id: null, name: "", entities: [], size: "wide", group: "", enable: null, nochart: [], q: "", cands: [] }; this.cardSearch(""); break;
      case "card-edit": {
        const card = this.area(this.page).cards.find((c) => c.id === el.dataset.id);
        this.cardEdit = { area: this.page, id: card.id, name: card.name, entities: [...card.entities], size: card.size, group: card.group || "", enable: card.enable ?? null, nochart: [...(card.nochart || [])], q: "", cands: [] };
        this.cardSearch("");
        break;
      }
      case "card-del": {
        const card = this.area(this.page).cards.find((c) => c.id === el.dataset.id);
        if (!confirm(`Togliere la card "${card?.name}"? Le entità restano in Home Assistant.`)) return;
        await this.api(`/api/casa/rooms/${encodeURIComponent(this.page)}/cards/${encodeURIComponent(el.dataset.id)}/remove`, { method: "POST" }).catch((err) => this.toast(`⚠ ${err.message}`));
        await this.reload(true);
        return;
      }
      case "card-close": this.cardEdit = null; break;
      case "card-add": {
        const cand = this.cardEdit.cands.find((x) => x.entity_id === eid);
        if (cand?.state && !this.data.states[eid]) this.data.states[eid] = cand.state; // preview before saving
        if (!this.cardEdit.entities.includes(eid)) this.cardEdit.entities.push(eid);
        this.cardKeep();
        break;
      }
      case "card-rm": this.cardEdit.entities = this.cardEdit.entities.filter((x) => x !== eid); this.cardKeep(); break;
      case "card-up": case "card-down": {
        const list = this.cardEdit.entities, i = list.indexOf(eid), j = i + (act === "card-up" ? -1 : 1);
        if (j >= 0 && j < list.length) [list[i], list[j]] = [list[j], list[i]];
        this.cardKeep();
        break;
      }
      case "card-size": this.cardKeep(); this.cardEdit.size = el.dataset.w; break;
      case "card-chart": {
        this.cardKeep();
        const list = this.cardEdit.nochart;
        if (list.includes(eid)) list.splice(list.indexOf(eid), 1); else list.push(eid);
        break;
      }
      case "chart": {
        const off = (this.data.nochart ||= []).includes(eid);
        this.data.nochart = off ? this.data.nochart.filter((x) => x !== eid) : [...this.data.nochart, eid];
        this.api(`/api/casa/entities/${encodeURIComponent(eid)}/display`, { method: "POST", body: JSON.stringify({ chart: off }) }).catch((err) => this.toast(`⚠ ${err.message}`));
        break;
      }
      case "card-save": {
        this.cardKeep();
        const c = this.cardEdit;
        if (!c.entities.length) { this.toast("Aggiungi almeno un'entità"); return; }
        try {
          await this.api(`/api/casa/rooms/${encodeURIComponent(c.area)}/cards`, { method: "POST", body: JSON.stringify({ id: c.id, name: c.name || "Card", entities: c.entities, size: c.size, group: c.group || null, enable: c.enable && !c.entities.includes(c.enable) ? null : c.enable, nochart: c.nochart.filter((e) => c.entities.includes(e)) }) });
          this.cardEdit = null;
          this.toast("Card salvata");
          await this.reload(true);
        } catch (err) { this.toast(`⚠ ${err.message.replace(/^\{"detail":"|"\}$/g, "")}`); }
        return;
      }
      case "hide": await this.api(`/api/casa/rooms/${encodeURIComponent(area)}/entities/${encodeURIComponent(eid)}/remove`, { method: "POST" }).catch((err) => this.toast(`⚠ ${err.message}`)); return;
      case "add": {
        try {
          await this.api(`/api/casa/rooms/${encodeURIComponent(area)}/entities`, { method: "POST", body: JSON.stringify({ entity_id: eid, mode: this.mode }) });
          this.toast(this.mode === "ha" ? "Spostata anche in Home Assistant" : "Aggiunta solo alla plancia");
          this.search(this.query || "");
        } catch (err) {
          this.toast(`⚠ ${err.message.replace(/^\{"detail":"|"\}$/g, "")}`);
        }
        return;
      }
      case "layout": this.editor.open().catch((err) => this.toast(`⚠ ${err.message}`)); return;
      case "layout-close": this.layout = null; document.activeElement?.blur(); break;
      case "layout-save": await this.saveLayout(); return;
      default: return;
    }
    this.render(true);
  }

  _change(e) {
    const el = e.target;
    if (el.dataset.act === "bright") {
      this.call("light", "turn_on", { entity_id: el.dataset.e, brightness_pct: Number(el.value) });
    } else if (el.id === "card-enable" || el.id === "card-group") {
      this.cardKeep();
      this.render(true);
    } else if (el.dataset.act === "dt") {
      this.setDateTime(el.dataset.e, el.value);
    } else if (el.dataset.act === "numval") {
      this.setNumber(el.dataset.e, Number(el.value));
    } else if (el.dataset.act === "selopt" && el.tagName === "SELECT") {
      this.setOption(el.dataset.e, el.value);
      el.blur();
    } else if (el.dataset.act === "textval") {
      const domain = el.dataset.e.split(".")[0];
      this.call(domain, "set_value", { entity_id: el.dataset.e, value: el.value }, el.dataset.e);
      el.blur();
    } else if (el.dataset.act === "volume") {
      this.call("media_player", "volume_set", { entity_id: el.dataset.e, volume_level: Number(el.value) / 100 });
    } else if (el.name === "casa-mode") {
      this.mode = el.value;
    } else if (el.dataset.act === "kind") {
      const eid = el.dataset.e;
      this.api(`/api/casa/entities/${encodeURIComponent(eid)}/kind`, { method: "POST", body: JSON.stringify({ kind: el.value || null }) })
        .then(() => this.toast(el.value ? `${this.st(eid)?.n}: ${SHOW_AS.find(([k]) => k === el.value)[1].toLowerCase()}` : "Tipo come in Home Assistant"))
        .catch((err) => this.toast(`⚠ ${err.message}`));
      if (this.st(eid)) this.st(eid).k = el.value || this.st(eid).nk || this.st(eid).k; // shown at once
      el.blur();
      this.render(true);
    } else if (el.dataset.act === "temp-src") {
      const area = this.area(el.dataset.area);
      if (area) area.temp = el.value || null; // shown at once; the server confirms with casa_changed
      this.api(`/api/casa/rooms/${encodeURIComponent(el.dataset.area)}/temperature`, { method: "POST", body: JSON.stringify({ entity_id: el.value || null }) })
        .then(() => this.toast(el.value ? "Temperatura della stanza impostata" : "Temperatura automatica"))
        .catch((err) => this.toast(`⚠ ${err.message}`));
      el.blur();
      this.render(true);
    }
  }

  _input(e) {
    if (e.target.id === "epick-find") {
      clearTimeout(this._find);
      this._find = setTimeout(() => this.ePickSearch(e.target.value), 250);
      return;
    }
    if (e.target.id === "card-find") {
      clearTimeout(this._find);
      this._find = setTimeout(() => this.cardSearch(e.target.value), 250);
      return;
    }
    if (e.target.id === "casa-find") {
      clearTimeout(this._find);
      this._find = setTimeout(() => this.search(e.target.value), 250);
    }
  }

  async search(q) {
    this.query = q;
    try {
      this.cands = await (await this.api(`/api/casa/entities?q=${encodeURIComponent(q)}&area=${encodeURIComponent(this.page || "")}`)).json();
    } catch { this.cands = []; }
    const box = this.root.querySelector("#casa-cands");
    if (box) box.innerHTML = this.candsHTML();
  }

  async openLayout() {
    try {
      this.layout = await (await this.api("/api/casa/layout")).json();
    } catch (err) { this.toast(`⚠ ${err.message}`); return; }
    this.render();
  }

  async saveLayout() {
    const text = this.root.querySelector("#casa-layout-text").value;
    try {
      await this.api("/api/casa/layout", { method: "POST", body: JSON.stringify({ text }) });
      this.layout = null;
      document.activeElement?.blur(); // a tap on Save can leave the keyboard on the text
      this.toast("Piantina salvata");
      await this.reload(true);
    } catch (err) {
      const box = this.root.querySelector(".layout-error");
      box.textContent = err.message.replace(/^\{"detail":"|"\}$/g, "");
    }
  }

  // ------------------------------------------------------------------ rendering
  // `force`: drawn because of something the owner did; otherwise a live update, which waits
  // while a slider, the search or the floor plan text is in use.
  render(force = false) {
    if (!this.visible) return;
    const active = document.activeElement;
    if (!force && active && this.root.contains(active) && (active.type === "range" || active.tagName === "TEXTAREA" || active.tagName === "SELECT" || active.id === "casa-find" || active.closest(".casa-modal") || active.classList.contains("hc-input"))) {
      this.dirty = true; // don't yank the control from under the finger: redraw on blur
      return;
    }
    this.dirty = false;
    const scroll = this.root.scrollTop;
    const panelScroll = this.root.querySelector(".casa-modal .panel")?.scrollTop || 0; // a dialog keeps its place too
    let html;
    if (this.error) html = `<div class="casa-empty panel">⚠ ${esc(this.error)}</div>`;
    else if (!this.data) html = `<div class="casa-empty panel">Collegamento a Home Assistant…</div>`;
    else if (!this.data.ready) html = `<div class="casa-empty panel">Home Assistant non è ancora collegato: riprovo…</div>`;
    else if (this.energyOpen) html = this.energyHTML();
    else html = this.page && this.area(this.page) ? this.roomHTML(this.area(this.page)) : this.homeHTML();
    if (this.layout) html += this.layoutHTML();
    if (this.alarmOpen && this.data?.alarms?.length) {
      html += `<div class="casa-modal" role="dialog" aria-label="Allarme"><section class="panel casa-panel casa-alarm-modal">
        <h3>Allarme <button class="casa-x" data-act="alarm-close" aria-label="Chiudi">×</button></h3>
        <div class="hc-grid">${this.data.alarms.filter((e) => this.st(e)).map((e) => this.cardHTML(e)).join("")}</div></section></div>`;
    }
    if (this.pad) html += this.padHTML();
    if (this.cardEdit) html += this.cardEditHTML();
    if (this.renaming) html += this.renameHTML();
    this.root.innerHTML = html;
    this.root.scrollTop = scroll;
    const panel = this.root.querySelector(".casa-modal .panel");
    if (panel) panel.scrollTop = panelScroll;
    document.body.classList.toggle("casa-sheet", !!(this.data && !this.page && this.selected && this.area(this.selected)));
    document.body.classList.toggle("casa-modal-open", !!(this.cardEdit || this.renaming || this.pad || this.layout || this.alarmOpen));
    if (this.editing && this.cands) {
      const box = this.root.querySelector("#casa-cands");
      if (box) box.innerHTML = this.candsHTML();
    }
    if (this.data && !this.data.ready) setTimeout(() => this.visible && this.reload(), 5000);
  }

  homeHTML() {
    return `
      ${this.hudHTML()}
      <div class="casa-body">
        <aside class="casa-col casa-left">${this.climateHTML()}</aside>
        <main class="casa-center">${this.planHTML()}</main>
        <aside class="casa-col casa-right">${this.selected && this.area(this.selected) ? this.quickHTML(this.area(this.selected)) : this.overviewHTML()}</aside>
      </div>`;
  }

  climateHTML() {
    const rows = this.data.areas.filter((a) => !a.outside).map((a) => [a, this.temp(a)]).filter(([, t]) => t != null);
    const outside = this.data.weather && this.st(this.data.weather)?.a;
    if (!rows.length && !outside) return "";
    const avg = rows.length ? rows.reduce((s, [, t]) => s + t, 0) / rows.length : null;
    return `
      <section class="hc">
        <span class="hc-kick">Temperatura delle stanze</span>
        ${rows.map(([a, t]) => `<button class="hc-temprow" data-act="room" data-area="${a.id}"><span>${esc(a.name)}</span><span class="hc-tbar"><i style="width:${Math.max(4, Math.min(100, ((t - 14) / 14) * 100))}%"></i></span><span class="mono">${num(t)}°</span></button>`).join("")}
        ${outside?.temperature != null ? `<div class="hc-temprow out"><span>Esterno</span><span></span><span class="mono">${num(outside.temperature)}°</span></div>` : ""}
      </section>`;
  }

  planHTML() {
    const d = this.data;
    const floors = d.floors;
    const tiles = (list) => list.map((a) => {
      const cls = [this.lit(a) ? "lit" : "", this.alerts(a).length ? "alert" : "", this.selected === a.id ? "sel" : ""].join(" ");
      const t = this.temp(a);
      return `<button class="casa-tile ${cls}" data-act="room" data-area="${a.id}"><b>${esc(a.name)}</b><span>${t != null ? num(t) + "°" : ""}${this.lit(a) ? " · luce" : ""}${this.alerts(a).length ? " · aperta" : ""}</span></button>`;
    }).join("");
    const outside = d.areas.filter((a) => a.outside);
    const others = d.areas.filter((a) => !a.placed);
    let plan = "";
    if (floors.length) {
      const f = floors[Math.min(this.floor, floors.length - 1)];
      const rooms = [...f.rooms].sort((a, b) => b.outline - a.outline).map((r) => {
        const a = r.area_id && this.area(r.area_id);
        const geo = `left:${r.x}%;top:${r.y}%;width:${r.w}%;height:${r.h}%`;
        const small = r.w < 12 || r.h < 12;
        const tall = r.w < 12 && r.h > 30; // a narrow strip: the name runs along it
        if (!a) return `<div class="plan-room ${r.outline ? "outline" : "ghost"}" style="${geo}"><b>${esc(r.name)}</b></div>`;
        const cls = [r.outline ? "outline" : "", this.lit(a) ? "lit" : "", this.alerts(a).length ? "alert" : "", this.selected === a.id ? "sel" : "", small ? "small" : "", tall ? "tall" : ""].join(" ");
        const t = this.temp(a);
        const tag = this.lit(a) ? "LUCE" : this.alerts(a).length ? "APERTA" : "";
        return `<button class="plan-room ${cls}" style="${geo}" data-act="room" data-area="${a.id}" aria-label="${esc(a.name)}">
          <b>${esc(a.name)}</b><span class="plan-meta"><span class="mono">${t != null && !small ? num(t) + "°" : ""}</span><span class="plan-tag">${small ? "" : tag}</span></span></button>`;
      }).join("");
      const tabs = floors.length > 1 ? `<div class="casa-floors">${floors.map((x, i) => `<button class="${i === this.floor ? "on" : ""}" data-act="floor" data-i="${i}">${esc(x.name)}</button>`).join("")}</div>` : `<div class="casa-floor-name">${esc(f.name)} · tocca una stanza</div>`;
      // The real drawing, faint under the hologram (light lines on the dark background).
      const t = this.token();
      const img = f.image ? ` has-image" style="aspect-ratio:${f.aspect};--plan-img:url('api/casa/plan-image/${f.image}${t ? "?token=" + encodeURIComponent(t) : ""}')` : `" style="aspect-ratio:${f.aspect}`;
      plan = `${tabs}<div class="plan-wrap"><div class="plan${img}">${rooms}</div></div>`;
    } else if (!d.layout_error) {
      plan = `<div class="casa-hint panel">Nessuna piantina ancora (<span class="mono">${esc(d.layout_file)}</span>): le stanze sono le aree di Home Assistant. <button data-act="layout">⚙ Disegna la piantina</button></div>`;
    }
    if (d.layout_error) {
      plan = `<div class="casa-hint panel bad">La piantina in <span class="mono">${esc(d.layout_file)}</span> ha un errore: <b>${esc(d.layout_error)}</b> <button data-act="layout">⚙ Correggi</button></div>` + plan;
    }
    const alerts = d.areas.flatMap((a) => this.alerts(a).map((e) => `<button class="chip bad" data-act="room" data-area="${a.id}">${esc(this.st(e).n)} · ${esc(a.name)}</button>`)).join("");
    return `${plan}
      ${outside.length ? `<div class="casa-group"><span class="casa-lbl">Fuori casa</span><div class="casa-tiles out">${tiles(outside)}</div></div>` : ""}
      ${others.length ? `<div class="casa-group"><span class="casa-lbl">${floors.length ? "Altre aree" : "Aree"}</span><div class="casa-tiles">${tiles(others)}</div></div>` : ""}
      ${alerts ? `<div class="casa-alerts">${alerts}</div>` : ""}`;
  }

  switchHTML(eid) {
    return `<button class="casa-switch ${this.isOn(eid) ? "on" : ""}" data-act="toggle" data-e="${eid}" aria-pressed="${this.isOn(eid)}" aria-label="${esc(this.st(eid)?.n)}"></button>`;
  }

  // What the room shows: the composed cards, then the entities not inside one of them; in the
  // owner's order when there is one.
  // The room's groups (Luci, Clima…), each with its cards in the owner's order. A composed card
  // sits in the group chosen for it, or in the group of its first entity.
  roomGroups(a) {
    const inCards = new Set((a.cards || []).flatMap((c) => c.entities));
    const groups = {};
    for (const c of a.cards || []) (groups[this.cardGroup(c)] ||= []).push(`card:${c.id}`);
    for (const e of a.entities) if (!inCards.has(e)) (groups[this.section(e)] ||= []).push(e);
    const rank = new Map((a.order || []).map((x, i) => [x, i]));
    const sort = (list) => list.map((x, i) => [x, rank.has(x) ? rank.get(x) : 1e6 + i]).sort((p, q) => p[1] - q[1]).map(([x]) => x);
    return SECTIONS.map(([k, title]) => [k, title, sort(groups[k] || [])]).filter(([, , ids]) => ids.length);
  }

  roomItems(a) { return this.roomGroups(a).flatMap(([, , ids]) => ids); }

  cardGroup(card) {
    if (card.group && SECTIONS.some(([k]) => k === card.group)) return card.group;
    const first = card.entities.find((e) => this.st(e));
    return first ? this.section(first) : "other";
  }

  itemHTML(id, a) {
    let html;
    if (id.startsWith("card:")) {
      const card = (a.cards || []).find((c) => `card:${c.id}` === id);
      if (!card) return "";
      html = this.composedCard(card);
    } else {
      html = this.cardHTML(id);
      if (!html) return "";
      if (this.data.sizes?.[id] === "wide") html = html.replace('class="hc ', 'class="hc wide ');
    }
    if (!this.editing) return html;
    const card = id.startsWith("card:");
    const wide = card ? (a.cards.find((c) => `card:${c.id}` === id)?.size === "wide") : this.data.sizes?.[id] === "wide" || /class="hc wide/.test(html);
    const bar = `<div class="hc-editbar">
        <button class="hc-handle" data-drag="${esc(id)}" aria-label="Trascina per spostare">⋮⋮</button>
        <button data-act="move" data-d="-1" data-id="${esc(id)}" aria-label="Sposta prima">‹</button><button data-act="move" data-d="1" data-id="${esc(id)}" aria-label="Sposta dopo">›</button>
        ${card ? `<button data-act="card-edit" data-id="${esc(id.slice(5))}">Modifica</button>` : `<button data-act="rename" data-e="${esc(id)}">Rinomina</button>`}
        ${!card && this.st(id)?.k === "sensor" && !isNaN(parseFloat(this.st(id).s)) ? `<button data-act="chart" data-e="${esc(id)}">${(this.data.nochart || []).includes(id) ? "Mostra grafico" : "Togli grafico"}</button>` : ""}
        <button data-act="size" data-id="${esc(id)}" data-w="${wide ? "small" : "wide"}">${wide ? "Piccola" : "Larga"}</button>
        ${card ? `<button data-act="card-del" data-id="${esc(id.slice(5))}">Togli</button>` : `<button data-act="hide" data-area="${a.id}" data-e="${esc(id)}">Togli</button>`}
      </div>`;
    return html.replace(/<\/(article|div)>\s*$/, `${bar}</$1>`).replace(/^(\s*<(?:article|div) class="hc )/, `$1hc-edit `).replace(/^(\s*<(?:article|div) )/, `$1data-item="${esc(id)}" `);
  }

  roomHTML(a) {
    const groups = {};
    for (const e of a.entities) (groups[this.section(e)] ||= []).push(e);
    const lights = groups.light || [];
    const t = this.temp(a);
    const presence = a.entities.find((e) => PRESENCE.has(this.dc(e)));
    const sources = this.tempSources(a);
    const chosen = this.tempSource(a);
    const tempLabel = sources.length > 1
      ? `<label class="casa-temp-src"><span>temperatura da</span><select data-act="temp-src" data-area="${a.id}" aria-label="Sensore della temperatura della stanza">
          <option value="" ${a.temp ? "" : "selected"}>Automatico</option>
          ${sources.map((e) => `<option value="${e}" ${a.temp === e ? "selected" : ""}>${esc(this.st(e).n)} (${num(this.readTemp(e) ?? 0)}°)</option>`).join("")}
        </select></label>`
      : `<span>temperatura</span>`;
    this.loadHistory(a);
    const watts = a.entities.map((e) => this.data.power?.[e]).filter(Boolean).reduce((sum, p) => sum + (parseFloat(this.st(p)?.s) || 0), 0);
    const stats = [
      t != null || sources.length ? `<div><b>${t != null ? num(t) + "°" : "—"}</b>${tempLabel}</div>` : "",
      lights.length ? `<div><b class="warm">${lights.filter((e) => this.isOn(e)).length} / ${lights.length}</b><span>luci accese</span></div>` : "",
      presence ? `<div><b>${this.isOn(presence) ? "Sì" : "No"}</b><span>presenza</span></div>` : "",
      watts ? `<div><b>${num(watts, 0)} W</b><span>consumo</span></div>` : "",
      `<div><b>${a.entities.length}</b><span>entità</span></div>`,
    ].join("");
    const pills = this.data.areas.map((x) => `<button class="casa-pill ${x.id === a.id ? "on" : ""}" data-act="open" data-area="${x.id}">${esc(x.name)}</button>`).join("");
    const sections = this.roomGroups(a).map(([k, title, ids]) => this.sectionHTML(k, title, ids, a)).join("");
    return `
      <div class="casa-room">
        <header class="casa-room-head">
          <button class="casa-back" data-act="home">← Casa</button>
          <div><span class="casa-lbl">${a.outside ? "Fuori casa" : esc(a.floor || "Stanza")}</span><h1>${esc(a.name)}</h1></div>
          <div class="casa-stats">${stats}</div>
          <button class="casa-edit ${this.editing ? "on" : ""}" data-act="edit" aria-pressed="${this.editing}">${this.editing ? "Fine modifica" : "Modifica stanza"}</button>
        </header>
        <nav class="casa-pills" aria-label="Altre stanze">${pills}</nav>
        ${this.editing ? this.editHTML(a) : ""}
        <div class="casa-sections">${sections || `<p class="panel casa-panel casa-muted">Nessuna entità: premi "Modifica stanza" per aggiungerne.</p>`}</div>
      </div>`;
  }

  sectionHTML(kind, title, ids, a) {
    const extra = kind === "light" && ids.some((e) => !e.startsWith("card:") && this.isOn(e)) ? `<button class="hc-link" data-act="all-off" data-area="${a.id}">Spegni tutte</button>` : "";
    const body = kind === "action" && !this.editing && ids.every((e) => !e.startsWith("card:"))
      ? `<div class="hc-scenes">${ids.map((e) => `<button class="hc-scene" data-act="scene" data-e="${e}">${esc(this.st(e)?.n || e)}</button>`).join("")}</div>`
      : `<div class="hc-grid ${this.editing ? "editing" : ""}" data-group="${kind}">${ids.map((id) => this.itemHTML(id, a)).join("")}</div>`;
    return `<section class="hc-sec hc-sec-${kind}"><h3 class="hc-sectitle"><span>${title}</span>${extra}</h3>${body}</section>`;
  }

  // The last day of the room's sensors, for the little charts on their cards.
  async loadHistory(a) {
    this.hist ||= {};
    this.histAt ||= {};
    if (this.histAt[a.id] && Date.now() - this.histAt[a.id] < 300000) return;
    this.histAt[a.id] = Date.now();
    const eids = [...new Set([...a.entities, ...(a.cards || []).flatMap((c) => c.entities)])]
      .filter((e) => { const s = this.st(e); return s?.k === "sensor" && !isNaN(parseFloat(s.s)); });
    if (!eids.length) return;
    try {
      const data = await (await this.api(`/api/casa/history?e=${encodeURIComponent(eids.join(","))}`)).json();
      Object.assign(this.hist, data);
      if (this.page === a.id) this.renderSoon();
    } catch { /* no charts: the values are still there */ }
  }

  editHTML(a) {
    return `
      <section class="panel casa-panel casa-editor">
        <div class="casa-edit-col">
          <div class="hc-edit-actions"><button class="hc-btn primary" data-act="card-new">+ Nuova card</button>
            ${(a.order || []).length ? `<button class="hc-link" data-act="order-reset">Ordine automatico</button>` : ""}</div>
          <p class="casa-muted">Sotto, ogni card ha i suoi comandi: trascinala (⋮⋮) o spostala con ‹ › dentro il suo gruppo, rinominala, rendila larga o piccola. Una card nuova raccoglie più entità, ad esempio la stufa con i suoi orari, e va nel gruppo che scegli.</p>
          <h3>Entità in ${esc(a.name)}</h3>
          ${a.entities.map((e) => {
            const s = this.st(e);
            const cur = s?.nk ? s.k : "";
            const opts = SHOW_AS.map(([k, label]) => `<option value="${k}" ${k === cur ? "selected" : ""}>${label}</option>`).join("");
            return `<div class="casa-row casa-entity"><span>${esc(s?.n || e)} <small class="mono">${e}</small></span>
              <select data-act="kind" data-e="${e}" aria-label="Mostra ${esc(s?.n || e)} come">${opts}</select>
              <button class="casa-mini" data-act="hide" data-area="${a.id}" data-e="${e}">Togli</button></div>`;
          }).join("") || `<p class="casa-muted">Ancora nessuna.</p>`}
          <p class="casa-muted">Il tipo cambia solo come la vedi qui (es. un relè che accende una luce conta tra le luci; un cancello ha il pulsante a impulso). "Togli" la nasconde da questa plancia. In Home Assistant non cambia nulla.</p>
        </div>
        <div class="casa-edit-col">
          <h3>Aggiungi entità</h3>
          <label class="casa-lbl" for="casa-find">Cerca tra le entità di Home Assistant</label>
          <input id="casa-find" placeholder="es. lampada, presa, sensore…" autocomplete="off" value="${esc(this.query || "")}">
          <div id="casa-cands"></div>
          <fieldset class="casa-mode">
            <legend class="casa-lbl">Dove salvare</legend>
            <label><input type="radio" name="casa-mode" value="ha" ${this.mode === "ha" ? "checked" : ""}> Sposta l'area anche in Home Assistant (consigliato)</label>
            <label><input type="radio" name="casa-mode" value="local" ${this.mode === "local" ? "checked" : ""}> Solo nella plancia di HubNEX</label>
          </fieldset>
        </div>
      </section>`;
  }

  // ---------------------------------------------------------------- helpers: service calls
  setDateTime(eid, value) {
    const s = this.st(eid), domain = eid.split(".")[0];
    if (!s || !value) return;
    const { hasDate, hasTime } = this.dtParts(eid, s);
    const time = (value.match(/\d{2}:\d{2}/) || [""])[0], date = (value.match(/\d{4}-\d{2}-\d{2}/) || [""])[0];
    let service = "set_value", data = { entity_id: eid };
    if (domain === "input_datetime") {
      service = "set_datetime";
      if (hasDate && hasTime) data.datetime = `${date} ${time}:00`;
      else if (hasDate) data.date = date;
      else data.time = `${time}:00`;
    } else if (domain === "time") data.time = `${time}:00`;
    else if (domain === "date") data.date = date;
    else data.datetime = `${date} ${time}:00`;
    s.s = hasDate && hasTime ? `${date} ${time}:00` : hasDate ? date : `${time}:00`; // shown at once
    this.call(domain, service, data, eid);
    this.render(true);
  }

  setNumber(eid, value) {
    const s = this.st(eid);
    if (!s || isNaN(value)) return;
    s.s = String(value);
    this.call(eid.split(".")[0], "set_value", { entity_id: eid, value }, eid);
  }

  setOption(eid, option) {
    const s = this.st(eid);
    if (!s || option == null) return;
    s.s = option;
    this.call(eid.split(".")[0], "select_option", { entity_id: eid, option }, eid);
  }

  // ---------------------------------------------------------------- the room's arrangement
  saveOrder(items) {
    const a = this.area(this.page);
    if (!a) return;
    a.order = items;
    this.api(`/api/casa/rooms/${encodeURIComponent(a.id)}/order`, { method: "POST", body: JSON.stringify({ items }) }).catch((err) => this.toast(`⚠ ${err.message}`));
  }

  // Moving stays inside the card's group; the saved order is the whole room, group by group.
  moveItem(id, delta) {
    const a = this.area(this.page);
    const groups = this.roomGroups(a).map(([, , ids]) => ids);
    const list = groups.find((ids) => ids.includes(id));
    const i = list?.indexOf(id), j = i + delta;
    if (!list || j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    this.saveOrder(groups.flat());
    this.render(true);
  }

  // Drag a card by its handle (mouse or finger) and drop it on another one.
  _dragStart(e) {
    const handle = e.target.closest("[data-drag]");
    if (!handle || !this.editing) return;
    e.preventDefault();
    const id = handle.dataset.drag;
    const card = handle.closest("[data-item]");
    card?.classList.add("dragging");
    let over = null;
    const group = card?.closest("[data-group]");
    const move = (ev) => {
      let el = document.elementFromPoint(ev.clientX, ev.clientY)?.closest("[data-item]");
      if (el && el.closest("[data-group]") !== group) el = null; // only inside its own group
      if (over && over !== el) over.classList.remove("drop");
      over = el && el !== card ? el : null;
      over?.classList.add("drop");
    };
    const up = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
      card?.classList.remove("dragging");
      if (!over) return;
      const groups = this.roomGroups(this.area(this.page)).map(([, , ids]) => ids);
      const list = groups.find((ids) => ids.includes(id));
      list.splice(list.indexOf(id), 1);
      list.splice(list.indexOf(over.dataset.item), 0, id);
      this.saveOrder(groups.flat());
      this.render(true);
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  }

  renameHTML() {
    const r = this.renaming;
    return `<div class="casa-modal" role="dialog" aria-label="Rinomina"><section class="panel casa-panel hc-dialog">
      <h3>Rinomina <button class="casa-x" data-act="rename-close" aria-label="Chiudi">×</button></h3>
      <p class="casa-muted">Il nome cambia solo in HubNEX; in Home Assistant resta com'è (<span class="mono">${esc(r.eid)}</span>).</p>
      <input id="casa-rename" class="hc-input" value="${esc(r.name)}" maxlength="60" aria-label="Nuovo nome">
      <div class="casa-actions"><button class="hc-btn primary" data-act="rename-save">Salva</button><button class="hc-link" data-act="rename-reset">Torna al nome di Home Assistant</button></div>
    </section></div>`;
  }

  // ---------------------------------------------------------------- composing a card
  cardKeep() {
    const n = this.root.querySelector("#card-name"), g = this.root.querySelector("#card-group"), en = this.root.querySelector("#card-enable");
    if (n && this.cardEdit) this.cardEdit.name = n.value;
    if (g && this.cardEdit) this.cardEdit.group = g.value;
    if (en && this.cardEdit) this.cardEdit.enable = en.value === "auto" ? null : en.value;
  }

  async cardSearch(q) {
    if (!this.cardEdit) return;
    this.cardEdit.q = q;
    try {
      this.cardEdit.cands = await (await this.api(`/api/casa/entities?all=1&q=${encodeURIComponent(q)}&area=${encodeURIComponent(this.cardEdit.area || "")}`)).json();
    } catch { this.cardEdit.cands = []; }
    const box = this.root.querySelector("#card-cands");
    if (box) box.innerHTML = this.cardCandsHTML();
    else this.render(true);
  }

  cardCandsHTML() {
    const c = this.cardEdit;
    return c.cands.filter((x) => !c.entities.includes(x.entity_id)).slice(0, 12).map((x) => `<button class="hc-cand" data-act="card-add" data-e="${esc(x.entity_id)}"><span>${esc(x.name)}</span><span class="mono">${esc(x.entity_id)}</span></button>`).join("") || `<p class="casa-muted">Nessuna entità trovata.</p>`;
  }

  cardEditHTML() {
    const c = this.cardEdit;
    const preview = this.composedCard({ id: "preview", name: c.name || "Card", entities: c.entities, size: c.size, enable: c.enable, nochart: c.nochart }).replace(/data-act="[^"]*"/g, "");
    const numeric = (e) => { const s = this.st(e); return s?.k === "sensor" && !isNaN(parseFloat(s.s)); };
    const toggles = c.entities.filter((e) => ["input_boolean", "switch"].includes(e.split(".")[0]));
    const hasTimes = c.entities.filter((e) => this.st(e)?.k === "datetime").length >= 2;
    const guessed = this.cardEnable({ entities: c.entities });
    return `<div class="casa-modal" role="dialog" aria-label="Card"><section class="panel casa-panel hc-dialog hc-cardedit">
      <h3>${c.id ? "Modifica card" : "Nuova card"} <button class="casa-x" data-act="card-close" aria-label="Chiudi">×</button></h3>
      <div class="hc-cardedit-cols">
        <div>
          <label class="hc-kick" for="card-name">Nome</label>
          <input id="card-name" class="hc-input" value="${esc(c.name)}" maxlength="60" placeholder="es. Stufa">
          <span class="hc-kick" style="margin-top:12px">Entità nella card</span>
          <div class="hc-chosen">${c.entities.map((e, i) => `<div class="hc-chosen-item"><span>${esc(this.st(e)?.n || e)}<small class="mono">${esc(e)}</small></span>
            <span class="hc-chosen-ctl">${numeric(e) ? `<label class="hc-chart-tg">grafico<button class="casa-switch ${c.nochart.includes(e) ? "" : "on"}" data-act="card-chart" data-e="${esc(e)}" role="switch" aria-checked="${!c.nochart.includes(e)}" aria-label="Grafico di ${esc(this.st(e)?.n || e)}"></button></label>` : ""}<button data-act="card-up" data-e="${esc(e)}" aria-label="Su" ${i ? "" : "disabled"}>↑</button><button data-act="card-down" data-e="${esc(e)}" aria-label="Giù" ${i < c.entities.length - 1 ? "" : "disabled"}>↓</button><button data-act="card-rm" data-e="${esc(e)}" aria-label="Togli">×</button></span></div>`).join("") || `<p class="casa-muted">Ancora nessuna: cercale qui sotto.</p>`}</div>
          <label class="hc-kick" for="card-find" style="margin-top:12px">Aggiungi entità</label>
          <input id="card-find" class="hc-input" value="${esc(c.q)}" placeholder="cerca per nome o entity_id…" autocomplete="off">
          <div id="card-cands" class="hc-cands">${this.cardCandsHTML()}</div>
        </div>
        <div>
          <label class="hc-kick" for="card-group">Gruppo</label>
          <select id="card-group" class="hc-select" style="margin-bottom:14px">
            <option value="">Automatico${c.entities.length ? ` (${esc((SECTIONS.find(([k]) => k === this.cardGroup({ entities: c.entities })) || ["", "Altro"])[1])})` : ""}</option>
            ${SECTIONS.map(([k, title]) => `<option value="${k}" ${c.group === k ? "selected" : ""}>${title}</option>`).join("")}
          </select>
          ${hasTimes && toggles.length ? `<label class="hc-kick" for="card-enable">Gli orari valgono quando è acceso</label>
          <select id="card-enable" class="hc-select" style="margin-bottom:14px">
            <option value="auto" ${c.enable == null ? "selected" : ""}>Automatico${guessed ? ` (${esc(this.st(guessed)?.n || guessed)})` : " (nessuno)"}</option>
            ${toggles.map((e) => `<option value="${esc(e)}" ${c.enable === e ? "selected" : ""}>${esc(this.st(e)?.n || e)}</option>`).join("")}
            <option value="" ${c.enable === "" ? "selected" : ""}>Nessuno: gli orari valgono sempre</option>
          </select>` : ""}
          <span class="hc-kick">Dimensione</span>
          <div class="hc-tabs" style="margin:6px 0 16px"><button class="hc-tab ${c.size === "small" ? "sel" : ""}" data-act="card-size" data-w="small">Piccola</button><button class="hc-tab ${c.size === "wide" ? "sel" : ""}" data-act="card-size" data-w="wide">Larga</button></div>
          <span class="hc-kick">Anteprima</span>
          <div class="hc-preview">${c.entities.length ? preview : `<p class="casa-muted">La card compare qui mentre la componi.</p>`}</div>
          <div class="casa-actions"><button class="hc-btn primary" data-act="card-save">Salva card</button><button class="hc-link" data-act="card-close">Annulla</button></div>
        </div>
      </div>
    </section></div>`;
  }

  candsHTML() {
    const area = this.page;
    return (this.cands || []).map((c) => `
      <div class="casa-row"><span>${esc(c.name)}<small class="${c.area ? "warm" : ""}">${c.area ? "ora in: " + esc(c.area) : "senza area"}${c.hidden ? " · nascosta in HA" : ""}</small><small class="mono">${esc(c.entity_id)}</small></span>
      <button class="casa-mini add" data-act="add" data-area="${area}" data-e="${c.entity_id}">+ Aggiungi</button></div>`).join("") || `<p class="casa-muted">Nessuna entità trovata.</p>`;
  }

  layoutHTML() {
    const l = this.layout;
    return `
      <div class="casa-modal" role="dialog" aria-label="Piantina">
        <section class="panel casa-panel">
          <h3>Piantina <button class="casa-x" data-act="layout-close" aria-label="Chiudi">×</button></h3>
          <p class="casa-muted">Incolla qui la piantina (YAML) e premi Salva: viene scritta in <span class="mono">${esc(l.file)}</span>. Le stanze vanno chiamate come le aree di Home Assistant:</p>
          <div class="casa-area-names">${l.areas.map((n) => `<span class="chip">${esc(n)}</span>`).join("")}</div>
          <textarea id="casa-layout-text" spellcheck="false">${esc(l.text)}</textarea>
          <div class="layout-error">${esc(l.error || "")}</div>
          <div class="casa-actions"><button class="casa-primary" data-act="layout-save">Salva piantina</button><button data-act="layout-close">Annulla</button></div>
        </section>
      </div>`;
  }
}

Object.assign(CasaView.prototype, Cards, Energy);
