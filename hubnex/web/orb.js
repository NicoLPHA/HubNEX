// Jarvis' "arc reactor": the face of the conversation. Appears while you talk to Jarvis,
// reacts to your voice while listening, spins while thinking and pulses with his voice while
// he speaks (real audio levels from the Web Audio API).

const STATES = {
  listening: { color: [79, 209, 255], caption: "In ascolto…", spin: 0.6 },
  thinking: { color: [178, 107, 255], caption: "Sto pensando…", spin: 2.2 },
  working: { color: [255, 181, 71], caption: "Al lavoro…", spin: 1.6 },
  speaking: { color: [120, 230, 255], caption: "", spin: 0.9 },
  idle: { color: [79, 209, 255], caption: "", spin: 0.3 },
};

export class Orb {
  constructor(root) {
    this.root = root;
    this.canvas = root.querySelector("canvas");
    this.ctx = this.canvas.getContext("2d");
    this.captionEl = root.querySelector(".orb-caption");
    this.state = "idle";
    this.color = [...STATES.idle.color];
    this.level = 0; // 0..1 smoothed loudness
    this.bins = new Float32Array(64); // smoothed spectrum for the radial bars
    this.analyser = null;
    this.synthetic = 0; // fake voice level while text is being "typed" without audio
    this.angle = 0;
    this.particles = Array.from({ length: 70 }, () => ({ a: Math.random() * Math.PI * 2, r: 0.55 + Math.random() * 0.4, s: 0.3 + Math.random(), z: Math.random() }));
    this.visible = false;
    this.hideTimer = null;
    this._resize();
    addEventListener("resize", () => this._resize());
    requestAnimationFrame((t) => this._frame(t));
  }

  _resize() {
    const size = this.root.clientWidth || 220;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = this.canvas.height = size * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.size = size;
  }

  show(state, caption) {
    clearTimeout(this.hideTimer);
    this.state = state;
    this.visible = true;
    this.root.classList.add("on");
    document.body.classList.add("orb-on"); // the arena's labels step back
    this.root.dataset.state = state;
    this.caption(caption ?? STATES[state].caption);
  }

  caption(text) {
    if (text !== undefined) this.captionEl.textContent = text || "";
  }

  // Let it breathe for a moment after the last word, then fade away.
  done(delay = 2500) {
    this.state = "idle";
    this.root.dataset.state = "idle";
    this.caption("");
    this.synthetic = 0;
    clearTimeout(this.hideTimer);
    this.hideTimer = setTimeout(() => {
      this.visible = false;
      this.root.classList.remove("on");
      document.body.classList.remove("orb-on");
    }, delay);
  }

  useAnalyser(analyser) { this.analyser = analyser; }

  get voiceLevel() { return this.visible ? this.level : 0; }

  _read() {
    let target = 0;
    if (this.analyser && this.state === "speaking") {
      const data = new Uint8Array(this.analyser.frequencyBinCount);
      this.analyser.getByteFrequencyData(data);
      const step = Math.max(1, Math.floor(data.length / 2 / this.bins.length)); // voice lives in the lower half
      let sum = 0;
      for (let i = 0; i < this.bins.length; i++) {
        const v = data[i * step] / 255;
        this.bins[i] += (v - this.bins[i]) * 0.35;
        sum += v;
      }
      target = Math.min(1, (sum / this.bins.length) * 2.2);
    } else {
      const t = performance.now() / 1000;
      const base = this.state === "speaking" || this.state === "listening" ? this.synthetic : this.state === "thinking" ? 0.12 : 0.04;
      for (let i = 0; i < this.bins.length; i++) {
        const v = base * (0.5 + 0.5 * Math.sin(t * 6 + i * 0.7) * Math.sin(t * 2.3 + i * 0.31));
        this.bins[i] += (Math.abs(v) - this.bins[i]) * 0.2;
      }
      target = base;
    }
    this.level += (target - this.level) * 0.25;
  }

  _frame(now) {
    requestAnimationFrame((t) => this._frame(t));
    if (!this.visible && this.level < 0.01) return;
    this._read();
    const st = STATES[this.state] || STATES.idle;
    for (let i = 0; i < 3; i++) this.color[i] += (st.color[i] - this.color[i]) * 0.08;
    this.angle += 0.016 * st.spin;
    const { ctx, size } = this;
    const c = size / 2;
    const [r, g, b] = this.color.map(Math.round);
    const rgba = (a) => `rgba(${r},${g},${b},${a})`;
    ctx.clearRect(0, 0, size, size);
    ctx.save();
    ctx.translate(c, c);
    ctx.globalCompositeOperation = "lighter";

    // Core glow: grows with the voice.
    const core = size * (0.11 + this.level * 0.09);
    const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, core * 2.6);
    glow.addColorStop(0, "rgba(255,255,255,0.95)");
    glow.addColorStop(0.25, rgba(0.85));
    glow.addColorStop(1, rgba(0));
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(0, 0, core * 2.6, 0, Math.PI * 2);
    ctx.fill();

    // Radial bars: the spectrum of his (or your) voice around the core.
    const inner = size * 0.24, maxLen = size * 0.14;
    ctx.lineWidth = Math.max(1.5, size / 110);
    ctx.lineCap = "round";
    for (let i = 0; i < this.bins.length; i++) {
      const a = (i / this.bins.length) * Math.PI * 2 + this.angle * 0.3;
      const len = 2 + this.bins[i] * maxLen;
      ctx.strokeStyle = rgba(0.35 + this.bins[i] * 0.65);
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
      ctx.lineTo(Math.cos(a) * (inner + len), Math.sin(a) * (inner + len));
      ctx.stroke();
    }

    // Segmented rings, each spinning at its own pace (the "arc reactor").
    const rings = [
      { r: 0.18, w: 2.5, seg: 3, gap: 0.5, speed: -1.4, a: 0.9 },
      { r: 0.42, w: 1.5, seg: 12, gap: 0.35, speed: 0.8, a: 0.55 },
      { r: 0.46, w: 4, seg: 3, gap: 0.45, speed: -0.5, a: 0.75 },
      { r: 0.49, w: 1, seg: 60, gap: 0.6, speed: 0.15, a: 0.35 },
    ];
    for (const ring of rings) {
      const rad = size * ring.r * (1 + this.level * 0.05);
      const span = (Math.PI * 2) / ring.seg;
      ctx.lineWidth = ring.w;
      ctx.strokeStyle = rgba(ring.a);
      for (let s = 0; s < ring.seg; s++) {
        const start = s * span + this.angle * ring.speed;
        ctx.beginPath();
        ctx.arc(0, 0, rad, start, start + span * (1 - ring.gap));
        ctx.stroke();
      }
    }

    // Thinking / working: particles orbit faster and closer.
    if (this.state === "thinking" || this.state === "working") {
      for (const p of this.particles) {
        p.a += 0.01 * p.s * st.spin;
        const pr = size * 0.5 * p.r * (0.92 + 0.08 * Math.sin(now / 400 + p.z * 10));
        ctx.fillStyle = rgba(0.3 + p.z * 0.6);
        ctx.beginPath();
        ctx.arc(Math.cos(p.a) * pr, Math.sin(p.a) * pr * 0.92, 0.8 + p.z * 1.6, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }
}

// Phrases for what Jarvis is doing, from the tool names the HQ reports.
export function describeTool(name, agentName) {
  if (!name) return null;
  if (name.startsWith("ha_")) return "Controllo la casa…";
  if (name.includes("__")) return `Consulto ${name.split("__")[0].replace(/_/g, " ")}…`; // a connector  if (name.startsWith("mail_")) return "Leggo la posta…";
  if (name === "delegate") return "Coinvolgo il team…";
  if (name === "web_search" || name === "web_fetch") return "Cerco sul web…";
  if (name.startsWith("memory_")) return "Consulto la memoria…";
  if (name.startsWith("deadline_")) return "Controllo le scadenze…";
  if (name === "notify_owner") return "Ti scrivo su Telegram…";
  return agentName ? `${agentName} al lavoro…` : "Al lavoro…";
}
