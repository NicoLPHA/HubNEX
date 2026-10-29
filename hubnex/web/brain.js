// Neural map: what the team knows, as a living 3D graph.
// Own scene, camera, controls and label layer; app.js decides which view is rendered.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";

export const TYPES = {
  core: { label: "Assistente", color: "#4fd1ff", size: 7 },
  company: { label: "Aziende", color: "#4fd1ff", size: 5 },
  department: { label: "Reparti", color: null, size: 4 },
  agent: { label: "Agenti", color: null, size: 5 },
  memory: { label: "Memorie", color: "#e6f3ff", size: 2.2 },
  task: { label: "Compiti", color: "#7fb8ff", size: 1.8 },
  deadline: { label: "Scadenze", color: "#ffb547", size: 2.6 },
  draft: { label: "Bozze", color: "#3ddc97", size: 2.6 },
  keyword: { label: "Parole chiave", color: "#4fd1ff", size: 1.4 },
};
const SINGULAR = { core: "Assistente", company: "Azienda", department: "Reparto", agent: "Agente", memory: "Memoria", task: "Compito", deadline: "Scadenza", draft: "Bozza", keyword: "Parola chiave" };
const FIRE = new THREE.Color("#ff4d6d");
const REST = { structure: 9, memory: 4, task: 3.5, deadline: 4, draft: 4, keyword: 5 };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const vertexShader = `
  attribute float size;
  attribute vec3 color;
  attribute float alpha;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vColor = color;
    vAlpha = alpha;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = size * (300.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }`;
const fragmentShader = `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    float core = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(vColor * (0.6 + core), pow(core, 1.6) * vAlpha);
  }`;

export class Brain {
  constructor(renderer, container, { onPick } = {}) {
    this.renderer = renderer;
    this.onPick = onPick;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x02040a);
    this.camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 2000);
    this.camera.position.set(0, 22, 120);
    this._fit();

    this.labels = new CSS2DRenderer();
    this.labels.setSize(innerWidth, innerHeight);
    Object.assign(this.labels.domElement.style, { position: "absolute", top: "0", pointerEvents: "none", display: "none" });
    container.appendChild(this.labels.domElement);

    this.controls = new OrbitControls(this.camera, renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.35;
    this.controls.minDistance = 15;
    this.controls.maxDistance = 400;
    this.controls.enabled = false;

    this.composer = new EffectComposer(renderer);
    this.composer.addPass(new RenderPass(this.scene, this.camera));
    this.composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 1.1, 0.7, 0.05));
    this.composer.addPass(new OutputPass());

    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.nodes = [];
    this.byId = new Map();
    this.links = [];
    this.hidden = new Set();
    this.query = "";
    this.active = new Map(); // agent id -> status
    this.pulses = [];
    this.alpha = 0;
    this.raycaster = new THREE.Raycaster();
    this.raycaster.params.Points.threshold = 1.2;
    this._dust();
  }

  // Decorative synapse dust: gives the "brain" its density, carries no data.
  _dust() {
    const n = 2600, pos = new Float32Array(n * 3), col = new Float32Array(n * 3), size = new Float32Array(n), alpha = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const r = 38 * Math.cbrt(Math.random()), th = Math.random() * Math.PI * 2, ph = Math.acos(2 * Math.random() - 1);
      pos.set([r * Math.sin(ph) * Math.cos(th) * 1.25, r * Math.cos(ph) * 0.8, r * Math.sin(ph) * Math.sin(th)], i * 3);
      col.set([0.45, 0.65, 1.0], i * 3);
      size[i] = 0.35 + Math.random() * 0.5;
      alpha[i] = 0.15 + Math.random() * 0.35;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.setAttribute("size", new THREE.BufferAttribute(size, 1));
    g.setAttribute("alpha", new THREE.BufferAttribute(alpha, 1));
    this.dust = new THREE.Points(g, this._material());
    this.scene.add(this.dust);
  }

  _material() {
    return new THREE.ShaderMaterial({ vertexShader, fragmentShader, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
  }

  setData(graph) {
    const old = this.byId;
    const fresh = !old.size;
    this.nodes = graph.nodes.map((n) => {
      const prev = old.get(n.id);
      const t = TYPES[n.type] || TYPES.memory;
      return {
        ...n,
        color: new THREE.Color(n.color || t.color || "#9fc7ff"),
        size: t.size,
        pos: prev ? prev.pos : null,
        vel: prev ? prev.vel : new THREE.Vector3(),
        born: prev ? prev.born : fresh ? 0 : performance.now(),
        degree: 0,
      };
    });
    this.byId = new Map(this.nodes.map((n) => [n.id, n]));
    this.links = graph.links
      .map((l) => ({ ...l, a: this.byId.get(l.source), b: this.byId.get(l.target) }))
      .filter((l) => l.a && l.b);
    for (const l of this.links) { l.a.degree++; l.b.degree++; }
    // Place new nodes next to what they're linked to, structure on a wide shell.
    for (const n of this.nodes) {
      if (n.pos) continue;
      const anchor = this.links.find((l) => l.b === n && l.a.pos)?.a || this.links.find((l) => l.a === n && l.b.pos)?.b;
      const spread = n.type === "core" ? 0 : ["company", "department", "agent"].includes(n.type) ? 25 : 8;
      const base = anchor ? anchor.pos : new THREE.Vector3();
      n.pos = base.clone().add(new THREE.Vector3().randomDirection().multiplyScalar(spread * (0.5 + Math.random())));
    }
    for (const n of this.nodes) if (n.type === "keyword" || n.type === "memory") n.size *= 1 + Math.min(n.degree, 8) * 0.12;
    this.alpha = fresh ? 1 : Math.max(this.alpha, 0.5);
    this._buildObjects();
    if (fresh) for (let i = 0; i < 160; i++) this._tick(); // settle before the first frame
  }

  _buildObjects() {
    for (const o of [this.points, this.lines]) if (o) { this.group.remove(o); o.geometry.dispose(); }
    for (const l of this.labelObjs || []) { this.group.remove(l); l.element.remove(); }
    const n = this.nodes.length;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute("size", new THREE.BufferAttribute(new Float32Array(n), 1));
    g.setAttribute("alpha", new THREE.BufferAttribute(new Float32Array(n), 1));
    this.points = new THREE.Points(g, this._material());
    this.group.add(this.points);

    const lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(this.links.length * 6), 3));
    lg.setAttribute("color", new THREE.BufferAttribute(new Float32Array(this.links.length * 6), 3));
    this.lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.group.add(this.lines);

    // Labels: structure always, the busiest keywords as small cyan tags, others on demand.
    const topKeywords = new Set(this.nodes.filter((x) => x.type === "keyword").sort((a, b) => b.degree - a.degree).slice(0, 18).map((x) => x.id));
    this.labelObjs = [];
    for (const node of this.nodes) {
      const el = document.createElement("div");
      el.className = `brain-label t-${node.type}`;
      el.textContent = node.label;
      if (["core", "agent", "company", "department"].includes(node.type)) el.style.borderColor = `#${node.color.getHexString()}`;
      const obj = new CSS2DObject(el);
      obj.userData.node = node;
      node.label3d = obj;
      node.labelAlways = ["core", "company", "agent"].includes(node.type) || topKeywords.has(node.id);
      this.group.add(obj);
      this.labelObjs.push(obj);
    }
    this._applyFilters();
  }

  _tick() {
    const nodes = this.nodes.filter((n) => !this.hidden.has(n.type));
    const k = this.alpha;
    if (k < 0.002) return;
    // repulsion
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        const dx = a.pos.x - b.pos.x, dy = a.pos.y - b.pos.y, dz = a.pos.z - b.pos.z;
        let d2 = dx * dx + dy * dy + dz * dz;
        if (d2 > 625) continue;
        d2 = Math.max(d2, 0.5);
        const f = (k * 18) / d2;
        a.vel.x += dx * f; a.vel.y += dy * f; a.vel.z += dz * f;
        b.vel.x -= dx * f; b.vel.y -= dy * f; b.vel.z -= dz * f;
      }
    }
    // springs
    for (const l of this.links) {
      if (this.hidden.has(l.a.type) || this.hidden.has(l.b.type)) continue;
      const d = l.b.pos.clone().sub(l.a.pos);
      const len = d.length() || 0.01;
      const f = ((len - (REST[l.kind] || 5)) / len) * 0.06 * k;
      d.multiplyScalar(f);
      l.a.vel.add(d);
      l.b.vel.sub(d);
    }
    for (const n of nodes) {
      if (n.type === "core") { n.pos.multiplyScalar(0.9); n.vel.set(0, 0, 0); continue; }
      n.vel.addScaledVector(n.pos, -0.009 * k); // gravity: keeps the cloud compact
      n.vel.multiplyScalar(0.82);
      n.pos.add(n.vel);
    }
    this.alpha *= 0.985;
  }

  setActive(agentId, status) {
    const busy = status && status !== "sleeping" && status !== "error";
    const was = this.active.has(agentId);
    if (busy) this.active.set(agentId, status); else this.active.delete(agentId);
    if (busy && !was) this.fire(`a:${agentId}`);
  }

  // Send impulses from Jarvis to an agent and from the agent to its knowledge.
  fire(id) {
    const target = this.byId.get(id);
    if (!target) return;
    const path = this._path("jarvis", id);
    for (let i = 0; i + 1 < path.length; i++) this.pulses.push({ a: path[i], b: path[i + 1], t: -i * 0.6 });
    for (const l of this.links.filter((x) => x.a === target).slice(0, 12)) this.pulses.push({ a: target, b: l.b, t: -path.length * 0.6 - Math.random() });
  }

  _path(from, to) {
    // Structure is a tree: walk up from the target.
    const parent = new Map(this.links.filter((l) => l.kind === "structure").map((l) => [l.b.id, l.a]));
    const out = [this.byId.get(to)];
    while (out[0] && out[0].id !== from && parent.has(out[0].id)) out.unshift(parent.get(out[0].id));
    return out.filter(Boolean);
  }

  flash(id) {
    const n = this.byId.get(id);
    if (n) n.born = performance.now();
  }

  setHidden(type, hidden) {
    if (hidden) this.hidden.add(type); else this.hidden.delete(type);
    this._applyFilters();
  }

  search(q) {
    this.query = q.trim().toLowerCase();
    this._applyFilters();
    if (!this.query) return 0;
    const hits = this.nodes.filter((n) => n.match);
    if (hits.length) {
      const c = hits.reduce((acc, n) => acc.add(n.pos), new THREE.Vector3()).multiplyScalar(1 / hits.length);
      this.controls.autoRotate = false;
      this.controls.target.lerp(c, 0.7);
    }
    return hits.length;
  }

  _applyFilters() {
    for (const n of this.nodes) {
      n.match = !!this.query && `${n.label} ${n.detail || ""}`.toLowerCase().includes(this.query);
      n.visible = !this.hidden.has(n.type);
    }
  }

  pick(event) {
    const p = new THREE.Vector2((event.clientX / innerWidth) * 2 - 1, -(event.clientY / innerHeight) * 2 + 1);
    this.raycaster.setFromCamera(p, this.camera);
    // Tolerance grows with distance; among the candidates take the one closest to the ray,
    // favouring big nodes (agents) over the small ones around them.
    this.raycaster.params.Points.threshold = Math.max(1.2, this.camera.position.distanceTo(this.controls.target) / 60);
    const hit = this.raycaster
      .intersectObject(this.points)
      .filter((h) => this.nodes[h.index]?.visible)
      .sort((a, b) => a.distanceToRay / this.nodes[a.index].size - b.distanceToRay / this.nodes[b.index].size)[0];
    if (!hit) return null;
    this.selected = this.nodes[hit.index];
    this.controls.autoRotate = false;
    return this.selected;
  }

  update(now) {
    if (!this.points) { this.controls.update(); return; } // graph still loading
    this._tick();
    this._tick();
    const t = now / 1000;
    const pos = this.points.geometry.attributes.position, col = this.points.geometry.attributes.color;
    const size = this.points.geometry.attributes.size, alpha = this.points.geometry.attributes.alpha;
    const searching = !!this.query;
    const tmp = new THREE.Color();
    this.nodes.forEach((n, i) => {
      pos.setXYZ(i, n.pos.x, n.pos.y, n.pos.z);
      const agentId = n.type === "agent" ? n.id.slice(2) : n.type === "core" ? "jarvis" : null;
      const firing = agentId && this.active.has(agentId);
      const age = n.born ? (now - n.born) / 1000 : 99;
      tmp.copy(n.color);
      if (firing) tmp.lerp(FIRE, 0.65 + Math.sin(t * 8) * 0.25);
      if (age < 3) tmp.lerp(FIRE, 1 - age / 3);
      if (n.match) tmp.lerp(FIRE, 0.8);
      col.setXYZ(i, tmp.r, tmp.g, tmp.b);
      let s = n.size * (firing ? 1.6 + Math.sin(t * 8) * 0.3 : 1) * (age < 3 ? 1 + (3 - age) : 1) * (n === this.selected ? 1.8 : 1);
      if (n.match) s *= 2;
      size.setX(i, n.visible ? s : 0);
      alpha.setX(i, !n.visible ? 0 : searching && !n.match && !["core", "agent"].includes(n.type) ? 0.25 : 0.95);
      const l = n.label3d;
      if (l) {
        const show = n.visible && (n.labelAlways || n.match || firing || n === this.selected || age < 6);
        l.visible = show; // CSS2DRenderer owns style.display: drive it through visibility
        l.element.classList.toggle("fire", !!(firing || n.match || age < 6));
        l.position.copy(n.pos);
      }
    });
    pos.needsUpdate = col.needsUpdate = size.needsUpdate = alpha.needsUpdate = true;

    const lp = this.lines.geometry.attributes.position, lc = this.lines.geometry.attributes.color;
    this.links.forEach((l, i) => {
      const vis = l.a.visible && l.b.visible;
      lp.setXYZ(i * 2, l.a.pos.x, l.a.pos.y, l.a.pos.z);
      lp.setXYZ(i * 2 + 1, l.b.pos.x, l.b.pos.y, l.b.pos.z);
      const hot = this.active.has(l.a.id.slice(2)) || l.a.match || l.b.match;
      const c = !vis ? [0, 0, 0] : hot ? [0.9, 0.25, 0.35] : l.kind === "keyword" ? [0.12, 0.3, 0.45] : [0.25, 0.45, 0.7];
      lc.setXYZ(i * 2, ...c);
      lc.setXYZ(i * 2 + 1, ...c);
    });
    lp.needsUpdate = lc.needsUpdate = true;

    this._updatePulses();
    this.dust.rotation.y = t * 0.02;
    this.controls.update();
  }

  _updatePulses() {
    if (!this.pulseMesh) {
      const g = new THREE.BufferGeometry();
      for (const [name, n] of [["position", 3], ["color", 3], ["size", 1], ["alpha", 1]]) g.setAttribute(name, new THREE.BufferAttribute(new Float32Array(256 * n), n));
      this.pulseMesh = new THREE.Points(g, this._material());
      this.group.add(this.pulseMesh);
    }
    this.pulses = this.pulses.filter((p) => p.t < 1).slice(-256);
    const a = this.pulseMesh.geometry.attributes;
    for (let i = 0; i < 256; i++) {
      const p = this.pulses[i];
      if (!p) { a.size.setX(i, 0); continue; }
      p.t += 0.035;
      const v = p.a.pos.clone().lerp(p.b.pos, Math.max(0, Math.min(1, p.t)));
      a.position.setXYZ(i, v.x, v.y, v.z);
      a.color.setXYZ(i, 1, 0.35, 0.45);
      a.size.setX(i, p.t < 0 ? 0 : 3.2);
      a.alpha.setX(i, 1);
    }
    for (const k of ["position", "color", "size", "alpha"]) a[k].needsUpdate = true;
  }

  render() {
    this.composer.render();
    this.labels.render(this.scene, this.camera);
  }

  show(on) {
    this.controls.enabled = on;
    this.labels.domElement.style.display = on ? "" : "none";
  }

  // Portrait screens need the camera further back to fit the whole cloud.
  _fit() {
    const k = Math.min(Math.max(1, Math.sqrt(1.3 / this.camera.aspect)), 2);
    this.camera.position.setLength(Math.hypot(22, 120) * k);
  }

  resize() {
    this.camera.aspect = innerWidth / innerHeight;
    this.camera.updateProjectionMatrix();
    this._fit();
    this.composer.setSize(innerWidth, innerHeight);
    this.labels.setSize(innerWidth, innerHeight);
  }

  describe(n) {
    const when = n.ts ? new Date(n.ts * 1000).toLocaleString("it-IT", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
    const neighbours = this.links.filter((l) => l.a === n || l.b === n).map((l) => (l.a === n ? l.b : l.a));
    return { type: SINGULAR[n.type] || n.type, label: n.label, detail: n.detail, when, neighbours: neighbours.slice(0, 12).map((x) => esc(x.label)) };
  }
}
