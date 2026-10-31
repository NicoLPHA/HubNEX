import { PlanEditor } from "./plan-editor.js";
import { Cards } from "./casa-cards.js";

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
  ["switch", "Prese e interruttori"], ["people", "Persone"], ["security", "Sicurezza"], ["camera", "Telecamere"], ["sensor", "Sensori"], ["action", "Azioni"], ["other", "Altro"],
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
  }

  close() { this.visible = false; document.body.classList.remove("casa-sheet"); }

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
      return isNaN(n) || /[^\d.,\-e]/i.test(s.s) ? s.s : `${num(n)}${s.a.unit_of_measurement ? " " + s.a.unit_of_measurement : ""}`;
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
    switch (act) {
      case "room":
        this.selected = this.selected === area ? null : area;
        // On a phone the card sits under the plan: bring it up after drawing it.
        if (this.selected && innerWidth < 1100) setTimeout(() => this.root.querySelector(".casa-quick")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
        break;
      case "open": this.page = area; this.selected = area; this.editing = false; this.root.scrollTop = 0; break;
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
    if (!force && active && this.root.contains(active) && (active.type === "range" || active.tagName === "TEXTAREA" || active.id === "casa-find")) {
      this.dirty = true; // don't yank the control from under the finger: redraw on blur
      return;
    }
    this.dirty = false;
    const scroll = this.root.scrollTop;
    let html;
    if (this.error) html = `<div class="casa-empty panel">⚠ ${esc(this.error)}</div>`;
    else if (!this.data) html = `<div class="casa-empty panel">Collegamento a Home Assistant…</div>`;
    else if (!this.data.ready) html = `<div class="casa-empty panel">Home Assistant non è ancora collegato: riprovo…</div>`;
    else html = this.page && this.area(this.page) ? this.roomHTML(this.area(this.page)) : this.homeHTML();
    if (this.layout) html += this.layoutHTML();
    if (this.alarmOpen && this.data?.alarms?.length) {
      html += `<div class="casa-modal" role="dialog" aria-label="Allarme"><section class="panel casa-panel casa-alarm-modal">
        <h3>Allarme <button class="casa-x" data-act="alarm-close" aria-label="Chiudi">×</button></h3>
        <div class="hc-grid">${this.data.alarms.filter((e) => this.st(e)).map((e) => this.cardHTML(e)).join("")}</div></section></div>`;
    }
    if (this.pad) html += this.padHTML();
    this.root.innerHTML = html;
    this.root.scrollTop = scroll;
    document.body.classList.toggle("casa-sheet", !!(this.data && !this.page && this.selected && this.area(this.selected)));
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
    const sections = SECTIONS.filter(([k]) => groups[k]?.length).map(([k, title]) => this.sectionHTML(k, title, groups[k], a)).join("");
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

  sectionHTML(kind, title, eids, a) {
    const extra = kind === "light" && eids.some((e) => this.isOn(e)) ? `<button class="hc-btn" data-act="all-off" data-area="${a.id}">Spegni tutte</button>` : "";
    const body = kind === "action"
      ? `<div class="hc-scenes">${eids.map((e) => `<button class="hc-scene" data-act="scene" data-e="${e}">${esc(this.st(e).n)}</button>`).join("")}</div>`
      : `<div class="hc-grid">${eids.map((e) => this.cardHTML(e)).join("")}</div>`;
    return `<section class="hc-sec hc-sec-${kind}"><h3 class="hc-sectitle"><span>${title}</span>${extra}</h3>${body}</section>`;
  }

  // The last day of the room's sensors, for the little charts on their cards.
  async loadHistory(a) {
    this.hist ||= {};
    this.histAt ||= {};
    if (this.histAt[a.id] && Date.now() - this.histAt[a.id] < 300000) return;
    this.histAt[a.id] = Date.now();
    const eids = a.entities.filter((e) => { const s = this.st(e); return s?.k === "sensor" && !isNaN(parseFloat(s.s)); });
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

Object.assign(CasaView.prototype, Cards);
