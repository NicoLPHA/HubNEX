import { PlanEditor } from "./plan-editor.js";

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
const HVAC = { heat: "Caldo", cool: "Freddo", auto: "Auto", heat_cool: "Auto", off: "Spento", dry: "Deum.", fan_only: "Ventola" };
const SECTIONS = [
  ["light", "Luci"], ["gate", "Cancelli e porte"], ["climate", "Clima"], ["cover", "Tapparelle e tende"], ["media", "Media"],
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

// Thin line icon in the HQ style (the colour comes from the text).
const SHIELD_ICON = `<svg class="casa-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8 4.5 5.6v5.7c0 4.6 3.1 8.6 7.5 9.9 4.4-1.3 7.5-5.3 7.5-9.9V5.6Z"/><path d="m9 12 2.2 2.2L15.5 10"/></svg>`;
const CAM_ICON = `<svg class="casa-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5h3l1.6-2.2h6.8L16 7.5h3a1.5 1.5 0 0 1 1.5 1.5v8.5A1.5 1.5 0 0 1 19 19H3a1.5 1.5 0 0 1-1.5-1.5V9A1.5 1.5 0 0 1 3 7.5Z"/><circle cx="11" cy="13" r="3.4"/><path d="M18.3 10.3h.01"/></svg>`;

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

  close() { this.visible = false; }

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
    if (s.k === "person") return s.s === "home" ? "good" : "";
    if (s.k === "alarm") return s.s === "triggered" ? "bad" : s.s === "disarmed" ? "" : "good";
    return "";
  }

  section(eid) {
    const s = this.st(eid);
    if (!s) return "other";
    if (["light", "gate", "climate", "cover", "media", "switch"].includes(s.k)) return s.k;
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
    else if (domain === "lock") {
      if (s?.s === "locked" && !confirm(`Sbloccare ${s.n}?`)) return;
      this.call("lock", s?.s === "locked" ? "unlock" : "lock", { entity_id: eid });
    } else {
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
  alarmHTML(eid) {
    const s = this.st(eid);
    const f = Number(s.a.supported_features) || 0;
    const arm = [[1, "alarm_arm_home", "In casa"], [2, "alarm_arm_away", "Fuori"], [4, "alarm_arm_night", "Notte"], [32, "alarm_arm_vacation", "Vacanza"]]
      .filter(([bit]) => f & bit);
    const buttons = s.s === "disarmed"
      ? arm.map(([, svc, label]) => `<button class="casa-mini" data-act="alarm" data-s="${svc}" data-e="${eid}">${label}</button>`).join("")
      : `<button class="casa-mini casa-disarm" data-act="alarm" data-s="alarm_disarm" data-e="${eid}">Disinserisci</button>`;
    return `<div class="casa-alarm"><div class="casa-row"><span>${esc(s.n)}</span><span class="casa-val ${this.valueClass(eid)}">${esc(this.value(eid))}</span></div>
      <div class="casa-alarm-btns">${buttons}</div></div>`;
  }

  alarm(eid, service) {
    const s = this.st(eid);
    const disarm = service === "alarm_disarm";
    if (s.a.code_format && (disarm || s.a.code_arm_required !== false)) {
      // The keypad is the confirmation: nothing happens until the code is sent.
      this.pad = { eid, service, code: "", error: "", busy: false };
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
      await this.api("/api/casa/call", { method: "POST", body: JSON.stringify({ domain: "alarm_control_panel", service: p.service, data: { entity_id: p.eid, code: p.code } }) });
      this.pad = null;
      this.toast(disarm ? "Disinserisco l'allarme…" : "Inserisco l'allarme…");
    } catch (err) {
      // Wrong code (or the alarm said no): stay on the keypad.
      Object.assign(p, { busy: false, code: "", error: /code|codice/i.test(err.message) ? "Codice errato" : `⚠ ${err.message.replace(/^\{"detail":"|"\}$/g, "")}` });
    }
    this.render(true);
  }

  padHTML() {
    const p = this.pad, s = this.st(p.eid);
    const label = { alarm_disarm: "Disinserisci", alarm_arm_home: "Inserisci · In casa", alarm_arm_away: "Inserisci · Fuori", alarm_arm_night: "Inserisci · Notte", alarm_arm_vacation: "Inserisci · Vacanza" }[p.service] || p.service;
    const numeric = s?.a.code_format !== "text";
    const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "ok"];
    const body = numeric
      ? `<div class="pad-dots" aria-live="polite">${"●".repeat(p.code.length) || "—"}</div>
         <div class="pad-keys">${keys.map((k) => `<button data-act="pad" data-k="${k}" class="${k === "ok" ? "ok" : ""}" aria-label="${k === "back" ? "Cancella" : k === "ok" ? "Conferma" : k}">${k === "back" ? "⌫" : k === "ok" ? "✓" : k}</button>`).join("")}</div>`
      : `<input type="password" id="pad-text" autocomplete="off" aria-label="Codice"><div class="casa-actions"><button class="casa-primary" data-act="pad-text">Conferma</button></div>`;
    return `<div class="casa-modal" role="dialog" aria-label="Codice allarme"><section class="panel casa-panel casa-pad ${p.service === "alarm_disarm" ? "disarm" : ""}">
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
      case "media": this.call("media_player", el.dataset.s, { entity_id: eid }, eid); return;
      case "lock": {
        const unlock = this.st(eid)?.s === "locked";
        if (unlock && !confirm(`Sbloccare ${this.st(eid)?.n}?`)) return;
        this.call("lock", unlock ? "unlock" : "lock", { entity_id: eid });
        return;
      }
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
        ${this.data.alarms.filter((e) => this.st(e)).map((e) => this.alarmHTML(e)).join("")}</section></div>`;
    }
    if (this.pad) html += this.padHTML();
    this.root.innerHTML = html;
    this.root.scrollTop = scroll;
    if (this.editing && this.cands) {
      const box = this.root.querySelector("#casa-cands");
      if (box) box.innerHTML = this.candsHTML();
    }
    if (this.data && !this.data.ready) setTimeout(() => this.visible && this.reload(), 5000);
  }

  homeHTML() {
    const d = this.data;
    const lightsOn = d.areas.flatMap((a) => this.lightsOf(a).filter((e) => this.isOn(e)).map((e) => [e, a]));
    const alarm = (d.alarms || []).find((e) => this.st(e));
    const power = d.energy.power && this.value(d.energy.power);
    const chips = [
      alarm ? `<button class="chip casa-chip-btn ${this.valueClass(alarm)}" data-act="alarm-panel">${SHIELD_ICON}Allarme: ${esc(this.value(alarm))}</button>` : "",
      `<span class="chip">${lightsOn.length} ${lightsOn.length === 1 ? "luce accesa" : "luci accese"}</span>`,
      power ? `<span class="chip">${esc(power)}</span>` : "",
      d.areas.some((a) => a.entities.some((e) => this.st(e)?.k === "camera")) ? `<button class="chip casa-chip-btn" data-act="cams">${CAM_ICON}Telecamere</button>` : "",
      ...(d.people || []).filter((e) => this.st(e)).map((e) => `<span class="chip casa-person ${this.valueClass(e)}" title="${esc(this.st(e).n)}: ${esc(this.value(e).toLowerCase())}">${esc(this.st(e).n)} · ${esc(this.value(e) === "A CASA" ? "a casa" : this.value(e) === "FUORI CASA" ? "fuori" : this.st(e).s)}</span>`),
    ].join("");
    const scenes = d.scenes.map((e) => `<button class="casa-scene" data-act="scene" data-e="${e}">${esc(this.st(e)?.n || e)}</button>`).join("");
    return `
      <div class="casa-top">
        <div class="casa-scenes">${scenes}</div>
        <div class="casa-chips">${chips}<button class="casa-gear" data-act="layout" title="Modifica la piantina">⚙ Piantina</button></div>
      </div>
      <div class="casa-body">
        <aside class="casa-col casa-left">${this.climateHTML()}${this.energyHTML()}</aside>
        <main class="casa-center">${this.planHTML()}</main>
        <aside class="casa-col casa-right">${this.selected && this.area(this.selected) ? this.quickHTML(this.area(this.selected)) : this.overviewHTML(lightsOn)}</aside>
      </div>`;
  }

  climateHTML() {
    const rows = this.data.areas.filter((a) => !a.outside).map((a) => [a, this.temp(a)]).filter(([, t]) => t != null);
    const outside = this.data.weather && this.st(this.data.weather)?.a;
    if (!rows.length && !outside) return "";
    const avg = rows.length ? rows.reduce((s, [, t]) => s + t, 0) / rows.length : null;
    return `
      <section class="panel casa-panel">
        <h3>Clima</h3>
        ${avg != null ? `<div class="casa-big">${num(avg)}°<span class="casa-lbl">media casa</span></div>` : ""}
        ${outside?.temperature != null ? `<div class="casa-sub">Esterno ${num(outside.temperature)}°</div>` : ""}
        ${rows.map(([a, t]) => `<button class="casa-row" data-act="room" data-area="${a.id}"><span>${esc(a.name)}</span><span class="mono">${num(t)}°</span></button>`).join("")}
      </section>`;
  }

  energyHTML() {
    const { power, today } = this.data.energy;
    if (!power && !today) return "";
    return `
      <section class="panel casa-panel">
        <h3>Energia</h3>
        ${power ? `<div class="casa-big">${esc(this.value(power))}<span class="casa-lbl">adesso</span></div>` : ""}
        ${today ? `<div class="casa-sub">Oggi ${esc(this.value(today))}</div>` : ""}
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

  overviewHTML(lightsOn) {
    const sec = this.data.areas.flatMap((a) => a.entities.filter((e) => {
      const s = this.st(e);
      return (s?.k === "binary" && ALERT.has(s.a.device_class) && s.s === "on") || s?.k === "lock" || s?.k === "siren";
    }).map((e) => [e, a]));
    sec.unshift(...(this.data.alarms || []).filter((e) => this.st(e)).map((e) => [e, null]));
    return `
      <section class="panel casa-panel">
        <h3>Luci accese</h3>
        ${lightsOn.map(([e, a]) => `<div class="casa-row"><span>${esc(this.st(e).n)} <small>${esc(a.name)}</small></span>${this.switchHTML(e)}</div>`).join("") || `<p class="casa-muted">Tutte spente.</p>`}
      </section>
      <section class="panel casa-panel">
        <h3>Sicurezza</h3>
        ${sec.map(([e, a]) => this.rowHTML(e, a?.name)).join("") || `<p class="casa-muted">Porte e finestre chiuse.</p>`}
      </section>
`;
  }

  quickHTML(a) {
    const lights = this.lightsOf(a);
    const climate = a.entities.find((e) => this.st(e)?.k === "climate");
    const key = a.entities.filter((e) => { const s = this.st(e); return s && (s.k === "binary" || s.k === "lock" || (s.k === "sensor" && ["temperature", "humidity"].includes(s.a.device_class))); }).slice(0, 5);
    const status = [this.alerts(a).length ? `${this.alerts(a).length} da controllare` : "", `${a.entities.length} entità`].filter(Boolean).join(" · ");
    return `
      <section class="panel casa-panel casa-quick">
        <div class="casa-quick-head">
          <div><span class="casa-lbl">${a.outside ? "Fuori casa" : "Stanza"}</span><h2>${esc(a.name)}</h2><span class="casa-sub">${status}</span></div>
          <button class="casa-x" data-act="unselect" aria-label="Chiudi">×</button>
        </div>
        ${lights.length ? `<h3>Luci</h3>${lights.slice(0, 6).map((e) => `<div class="casa-row"><span>${esc(this.st(e).n)}</span>${this.switchHTML(e)}</div>`).join("")}${lights.length > 6 ? `<p class="casa-muted">+ altre ${lights.length - 6}</p>` : ""}` : ""}
        ${climate ? `<h3>Clima</h3>${this.climateCardHTML(climate, true)}` : ""}
        ${key.length ? `<h3>Sensori</h3>${key.map((e) => this.rowHTML(e)).join("")}` : ""}
        ${!a.entities.length ? `<p class="casa-muted">Nessuna entità in quest'area. Aprila e aggiungine con "Modifica stanza".</p>` : ""}
        <div class="casa-actions">
          <button class="casa-primary" data-act="open" data-area="${a.id}">Apri stanza →</button>
          ${lights.some((e) => this.isOn(e)) ? `<button data-act="all-off" data-area="${a.id}">Spegni luci</button>` : ""}
        </div>
      </section>`;
  }

  switchHTML(eid) {
    return `<button class="casa-switch ${this.isOn(eid) ? "on" : ""}" data-act="toggle" data-e="${eid}" aria-pressed="${this.isOn(eid)}" aria-label="${esc(this.st(eid)?.n)}"></button>`;
  }

  rowHTML(eid, note) {
    const s = this.st(eid);
    if (s?.k === "alarm") return this.alarmHTML(eid);
    const right = s?.k === "lock"
      ? `<button class="casa-mini" data-act="lock" data-e="${eid}">${s.s === "locked" ? "Sblocca" : "Blocca"}</button>`
      : s?.k === "siren"
        ? `<span class="casa-val ${s.s === "on" ? "bad" : ""}">${s.s === "on" ? "SUONA" : "SPENTA"}</span>${this.switchHTML(eid)}`
        : `<span class="casa-val ${this.valueClass(eid)}">${esc(this.value(eid))}</span>`;
    return `<div class="casa-row"><span>${esc(s?.n || eid)}${note ? ` <small>${esc(note)}</small>` : ""}</span>${s?.k === "lock" ? `<span class="casa-val ${this.valueClass(eid)}">${esc(this.value(eid))}</span>` : ""}${right}</div>`;
  }

  climateCardHTML(eid, compact = false) {
    const s = this.st(eid);
    const cur = s.a.current_temperature, target = s.a.temperature;
    const pct = cur != null ? Math.max(0, Math.min(100, ((cur - 15) / 12) * 100)) : 0;
    const modes = (s.a.hvac_modes || []).map((m) => `<button class="casa-mini ${s.s === m ? "on" : ""}" data-act="hvac" data-e="${eid}" data-m="${m}">${HVAC[m] || m}</button>`).join("");
    return `
      <div class="casa-climate">
        <div class="casa-dial" style="--p:${pct}%"><div><b>${cur != null ? num(cur) + "°" : "—"}</b><span>attuale</span></div></div>
        <div class="casa-climate-ctl">
          ${target != null ? `<div class="casa-target"><button data-act="temp" data-e="${eid}" data-d="-1" aria-label="Abbassa">−</button><div><b>${num(target)}°</b><span>obiettivo</span></div><button data-act="temp" data-e="${eid}" data-d="1" aria-label="Alza">+</button></div>` : ""}
          ${compact ? "" : `<div class="casa-modes">${modes}</div>`}
        </div>
      </div>`;
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
    const stats = [
      t != null || sources.length ? `<div><b>${t != null ? num(t) + "°" : "—"}</b>${tempLabel}</div>` : "",
      lights.length ? `<div><b class="warm">${lights.filter((e) => this.isOn(e)).length} / ${lights.length}</b><span>luci accese</span></div>` : "",
      presence ? `<div><b>${this.isOn(presence) ? "Sì" : "No"}</b><span>presenza</span></div>` : "",
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
    let body;
    if (kind === "light") {
      body = `<div class="casa-lights">${eids.map((e) => {
        const s = this.st(e), on = s.s === "on";
        const pct = on && s.a.brightness != null ? Math.round((s.a.brightness / 255) * 100) : on ? 100 : 0;
        const dim = (s.a.supported_color_modes || []).some((m) => m !== "onoff") || s.a.brightness != null;
        return `<div class="casa-light ${on ? "on" : ""}">
          <button data-act="toggle" data-e="${e}" aria-pressed="${on}"><b>${esc(s.n)}</b><span>${on ? `Accesa${dim ? " · " + pct + "%" : ""}` : s.s === "unavailable" ? "Non disponibile" : "Spenta"}</span></button>
          ${on && dim ? `<input type="range" min="1" max="100" value="${pct}" data-act="bright" data-e="${e}" aria-label="Luminosità ${esc(s.n)}">` : ""}
        </div>`;
      }).join("")}</div>`;
      const anyOn = eids.some((e) => this.isOn(e));
      title += anyOn ? ` <button class="casa-mini" data-act="all-off" data-area="${a.id}">Spegni tutte</button>` : "";
    } else if (kind === "climate") {
      body = eids.map((e) => this.st(e).k === "climate" ? `<div class="casa-sub">${esc(this.st(e).n)}</div>${this.climateCardHTML(e)}` : this.rowHTML(e)).join("");
    } else if (kind === "cover") {
      body = eids.map((e) => {
        const s = this.st(e), pos = s.a.current_position;
        return `<div class="casa-cover"><div class="casa-row"><span>${esc(s.n)}</span><span class="mono">${pos != null ? pos + "% aperta" : esc(s.s)}</span></div>
          <div class="casa-cover-ctl"><div class="casa-bar"><i style="width:${pos ?? (s.s === "open" ? 100 : 0)}%"></i></div>
          <button class="casa-mini" data-act="cover" data-s="open_cover" data-e="${e}" aria-label="Alza">▲</button>
          <button class="casa-mini" data-act="cover" data-s="stop_cover" data-e="${e}" aria-label="Ferma">■</button>
          <button class="casa-mini" data-act="cover" data-s="close_cover" data-e="${e}" aria-label="Abbassa">▼</button></div></div>`;
      }).join("");
    } else if (kind === "gate") {
      body = eids.map((e) => {
        const s = this.st(e);
        const state = { open: "APERTO", opening: "APRE…", closed: "CHIUSO", closing: "CHIUDE…", locked: "BLOCCATA", unlocked: "SBLOCCATA" }[s.s] || "";
        return `<div class="casa-row"><span>${esc(s.n)}${state ? ` <small>${state}</small>` : ""}</span><button class="casa-mini casa-gate" data-act="gate" data-e="${e}">▶ Comanda</button></div>`;
      }).join("");
    } else if (kind === "media" || kind === "switch") {
      body = eids.map((e) => {
        const s = this.st(e);
        const title = [s.a.media_title, s.a.media_artist].filter(Boolean).join(" · ");
        const note = kind === "media" ? (title || ({ playing: "in riproduzione", paused: "in pausa", idle: "inattivo", off: "spento", on: "acceso", standby: "in standby" }[s.s] || s.s)) : "";
        // Players that are on get play/pause and volume; the switch turns them on and off.
        const play = kind === "media" && ["playing", "paused", "idle", "on"].includes(s.s)
          ? `<button class="casa-mini" data-act="media" data-s="media_play_pause" data-e="${e}" aria-label="${s.s === "playing" ? "Pausa" : "Riproduci"}">${s.s === "playing" ? "❚❚" : "▶"}</button>`
          : "";
        const vol = kind === "media" && s.a.volume_level != null && s.s !== "off"
          ? `<input type="range" min="0" max="100" value="${Math.round(s.a.volume_level * 100)}" data-act="volume" data-e="${e}" aria-label="Volume ${esc(s.n)}">`
          : "";
        return `<div class="casa-media"><div class="casa-row"><span>${esc(s.n)}${note ? ` <small>${esc(note)}</small>` : ""}</span>${play}${this.switchHTML(e)}</div>${vol}</div>`;
      }).join("");
    } else if (kind === "camera") {
      body = `<div class="casa-cams">${eids.map((e) => this.camHTML(e)).join("")}</div>`;
    } else if (kind === "action") {
      body = `<div class="casa-scenes">${eids.map((e) => `<button class="casa-scene" data-act="scene" data-e="${e}">${esc(this.st(e).n)}</button>`).join("")}</div>`;
    } else {
      body = eids.map((e) => this.rowHTML(e)).join("");
    }
    return `<section class="panel casa-panel casa-sec-${kind}"><h3>${title}</h3>${body}</section>`;
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
