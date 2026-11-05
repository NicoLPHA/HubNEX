// Browser tests of the dashboard, against dev/demo.py (pretend Home Assistant and Claude).
// Run from the add-on folder:  node --test tests/ui/
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("node:path");
const { chromium } = require("playwright");

const PORT = 18000 + Math.floor(Math.random() * 1000);
const URL = `http://127.0.0.1:${PORT}/`;
let server, browser;

async function waitForServer() {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(URL)).ok) return; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("la demo non parte");
}

before(async () => {
  server = spawn(process.env.PYTHON || "python3", ["dev/demo.py", String(PORT)], {
    cwd: path.resolve(__dirname, "../.."), stdio: ["ignore", "inherit", "inherit"],
  });
  await waitForServer();
  browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
});

after(async () => {
  await browser?.close();
  server?.kill("SIGKILL"); // no graceful shutdown needed: it is a throwaway demo
});

// A page that fails the test on any JavaScript error.
async function open(viewport = { width: 1440, height: 900 }, lang = "it") {
  const page = await browser.newPage({ viewport });
  await page.addInitScript((l) => localStorage.setItem("hq_lang", l), lang);
  page.errors = [];
  page.on("pageerror", (e) => page.errors.push(e.message));
  await page.goto(URL);
  await page.waitForSelector("#view-casa");
  return page;
}

async function casa(page) {
  await page.click("#view-casa");
  await page.waitForSelector(".plan-room[data-area='soggiorno']");
}

async function done(page) {
  assert.deepEqual(page.errors, [], "errori JavaScript nella pagina");
  await page.close();
}

test("vista Casa: piantina, scheda della stanza, pagina della stanza", { timeout: 30000 }, async () => {
  const page = await open();
  await casa(page);
  assert.equal(await page.locator(".plan-room").count(), 7, "le stanze della piantina");
  assert.match(await page.textContent("#casa"), /Giardino/, "le aree fuori casa sotto la piantina");
  await page.click(".plan-room[data-area='cucina']");
  await page.waitForSelector(".casa-quick");
  assert.match(await page.textContent(".casa-quick"), /Cucina/);
  await page.click(".casa-quick [data-act='open']");
  await page.waitForSelector(".casa-room");
  assert.match(await page.textContent(".casa-room"), /Soffitto cucina/);
  await page.click("[data-act='home']");
  await page.waitForSelector(".plan-room[data-area='cucina']");
  await done(page);
});

test("comando dalla scheda: la luce cambia stato", { timeout: 30000 }, async () => {
  const page = await open();
  await casa(page);
  await page.click(".plan-room[data-area='soggiorno']");
  const card = page.locator(".casa-quick [data-act='toggle'][data-e='light.striscia']").first();
  await card.waitFor();
  const before = await card.textContent();
  await card.click();
  await page.waitForFunction(
    (b) => document.querySelector(".casa-quick [data-act='toggle'][data-e='light.striscia']")?.textContent !== b, before,
  );
  await done(page);
});

test("popup Energia: si apre, resta dov'è con gli aggiornamenti dal vivo, si chiude", { timeout: 30000 }, async () => {
  const page = await open();
  await casa(page);
  await page.click("[data-act='energy']");
  const panel = page.locator(".casa-energy-modal .panel");
  await panel.waitFor();
  // the day's chart arrives a moment after the popup: wait until its height stops changing
  let last = -1;
  for (let i = 0; i < 20; i++) {
    const h = await panel.evaluate((el) => el.scrollHeight);
    if (h === last) break;
    last = h;
    await page.waitForTimeout(300);
  }
  // halfway down: a few pixels more or less at the bottom don't move it
  await panel.evaluate((el) => { el.scrollTop = Math.round((el.scrollHeight - el.clientHeight) / 2); });
  const scrolled = await panel.evaluate((el) => el.scrollTop);
  assert.ok(scrolled > 50, "il popup scorre");
  // something changes in the house while the popup is open
  await page.evaluate(() => fetch("api/casa/call", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain: "light", service: "toggle", data: { entity_id: "light.cucina" } }) }));
  await page.waitForTimeout(1200);
  assert.equal(await panel.evaluate((el) => el.scrollTop), scrolled, "lo scorrimento del popup non torna in alto");
  await page.keyboard.press("Escape");
  await page.waitForSelector(".casa-energy-modal", { state: "detached" });
  await done(page);
});

test("editor delle card: si apre e si chiude", { timeout: 30000 }, async () => {
  const page = await open();
  await casa(page);
  await page.click(".plan-room[data-area='soggiorno']");
  await page.click(".casa-quick [data-act='open']");
  await page.click("[data-act='edit']");
  await page.click("[data-act='card-new']");
  await page.waitForSelector(".hc-cardedit");
  await page.click("[data-act='card-close']");
  await page.waitForSelector(".hc-cardedit", { state: "detached" });
  await done(page);
});

test("chat: Home Assistant da solo, poi la via rapida", { timeout: 30000 }, async () => {
  const page = await open();
  await page.fill("#chat-input", "accendi la lampada da terra");
  await page.keyboard.press("Enter");
  // the answer is written letter by letter: wait for the whole of it
  await page.waitForFunction(() => {
    const m = document.querySelector(".msg.jarvis");
    return m?.dataset.by === "ha" && /Lampada da terra: accesa/.test(m.textContent);
  });
  await page.fill("#chat-input", "abbassa un po' la tapparella");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelectorAll(".msg.jarvis[data-by='quick']").length === 1);
  await done(page);
});

test("chat: la richiesta va a capo e il campo cresce; Invio invia", { timeout: 30000 }, async () => {
  const page = await open();
  const box = page.locator("#chat-input");
  const h0 = (await box.boundingBox()).height;
  // typed in one go (letter by letter is slow with the 3D scene on a machine without a GPU)
  await box.fill("Riassumimi le email di oggi del cliente Rossi e dimmi quali scadenze ci sono questa settimana, poi prepara una bozza");
  await box.press("End");
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.insertText("con tono cordiale.");
  const h1 = (await box.boundingBox()).height;
  assert.ok(h1 > h0 * 1.8, `il campo cresce (${h0} → ${h1})`);
  assert.match(await box.inputValue(), /bozza\ncon tono/, "Shift+Invio va a capo");
  await page.keyboard.press("Enter");
  await page.waitForSelector(".msg.me");
  assert.equal(await box.inputValue(), "", "Invio invia e svuota");
  assert.ok((await box.boundingBox()).height < h0 + 2, "il campo torna a una riga");
  await done(page);
});

test("luci: la card resta semplice, colore e temperatura nel popup", { timeout: 30000 }, async () => {
  const page = await open();
  await casa(page);
  await page.click(".plan-room[data-area='soggiorno']");
  await page.click(".casa-quick [data-act='open']");
  await page.waitForSelector(".casa-room");
  assert.equal(await page.locator(".casa-room [data-act='ktemp'], .casa-room [data-act='lcolor']").count(), 0, "niente controlli in più sulla card");
  assert.equal(await page.locator("[data-act='tone'][data-e='light.faretti_tv']").count(), 0, "solo luminosità: niente pallino");
  // the LED strip (colour only, off): the popup has colours and no temperature
  await page.click("[data-act='tone'][data-e='light.striscia']");
  await page.waitForSelector(".hc-tonebox");
  assert.equal(await page.locator(".hc-tonebox [data-act='ktemp']").count(), 0);
  await page.click(".hc-tonebox [data-act='lcolor'][data-rgb='10,90,255']");
  await page.waitForFunction(() => document.querySelector(".hc-light[data-e='light.striscia']")?.classList.contains("on"));
  await page.keyboard.press("Escape");
  await page.waitForSelector(".hc-tonebox", { state: "detached" });
  // the floor lamp: temperature in the popup
  await page.click("[data-act='tone'][data-e='light.lampada_terra']");
  await page.locator(".hc-tonebox [data-act='ktemp']").evaluate((el) => {
    el.value = 5000;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.click("[data-act='tone-close']");
  await page.waitForFunction(() => /5000 K/.test(document.querySelector(".hc-light[data-e='light.lampada_terra']").textContent));
  await done(page);
});

test("card: robot con mappa, telecamera composta live con i sensori, media completo", { timeout: 30000 }, async () => {
  const page = await open();
  await casa(page);
  // the robot: state, battery, map and commands
  await page.locator("[data-area='corridoio']").first().click();
  await page.click(".casa-quick [data-act='open']");
  await page.waitForSelector(".hc-vacuum");
  assert.match(await page.textContent(".hc-vacuum"), /pulisce/);
  assert.equal(await page.locator(".hc-vacuum .hc-vmap img[data-cam='image.robot_mappa']").count(), 1, "la mappa");
  assert.equal(await page.locator(".hc-vacuum [data-act='vac'][data-s='pause']").count(), 1, "pausa mentre pulisce");
  await page.click("[data-act='home']");
  // the entrance camera: live picture, the vehicle sensor lit over it
  await page.locator("[data-area='giardino']").first().click();
  await page.click(".casa-quick [data-act='open']");
  await page.waitForSelector(".hc-camcomp");
  assert.equal(await page.locator(".hc-camcomp .hc-chip.on").count(), 1, "il veicolo in movimento");
  await page.waitForSelector(".hc-camcomp img[data-live]");
  await page.click(".hc-camcomp .casa-cam");
  await page.waitForFunction(() => /LIVE/.test(document.querySelector(".cam-mode")?.textContent || ""));
  assert.equal(await page.locator("#casa img[data-live]").count(), 0, "la miniatura chiude il suo flusso");
  await page.click(".casa-overlay .casa-x");
  await page.waitForSelector(".hc-camcomp img[data-live]");
  await page.click("[data-act='home']");
  // the kitchen speaker: shuffle, repeat, source
  await page.locator("[data-area='cucina']").first().click();
  await page.click(".casa-quick [data-act='open']");
  await page.waitForSelector(".hc-media-on");
  for (const sel of ["[data-act='mshuffle']", "[data-act='mrepeat']", "[data-act='msrc']", "[data-act='mmute']"])
    assert.equal(await page.locator(`.hc-media-on ${sel}`).count(), 1, sel);
  await done(page);
});

test("preferenze: il backup si scarica", { timeout: 30000 }, async () => {
  const page = await open();
  await page.click("#ha-prefs");
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("#backup-get")]);
  assert.match(download.suggestedFilename(), /^hubnex-backup-\d{8}-\d{4}\.zip$/);
  await done(page);
});

test("spesa Claude: dalla scheda in HQ, per giorno, agente e modello", { timeout: 30000 }, async () => {
  const page = await open();
  await page.click("#view-hq");
  await page.click("[data-costs]");
  await page.waitForSelector(".costs-row");
  assert.equal(await page.locator(".costs-bar").count(), 30, "una barra per giorno");
  assert.match(await page.textContent(".costs"), /Jarvis Mail/);
  assert.match(await page.textContent(".costs"), /claude-haiku-5-5/);
  assert.match(await page.textContent(".costs-budget"), /\$15,00/, "il budget della demo");
  await page.click("[data-span='7']");
  await page.waitForFunction(() => document.querySelectorAll(".costs-bar").length === 7);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator(".costs-modal").count(), 0, "Esc chiude");
  await done(page);
});

test("telefono: la spesa Claude si apre dalle preferenze", { timeout: 30000 }, async () => {
  const page = await open({ width: 390, height: 844 });
  await page.click("#ha-prefs");
  await page.click("#pref-costs");
  await page.waitForSelector(".costs-row");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390, "niente scorrimento laterale");
  await page.click("[data-costs-close]");
  assert.equal(await page.locator(".costs-modal").count(), 0);
  await done(page);
});

test("notifiche della casa: regole, canali, prova", { timeout: 30000 }, async () => {
  const page = await open();
  await page.click("#ha-prefs");
  await page.click("#pref-alerts");
  await page.waitForSelector(".al-rule");
  assert.equal(await page.locator(".al-rule").count(), 7, "sette regole");
  assert.match(await page.textContent(".al-active"), /Finestra camera/, "la finestra aperta col riscaldamento");
  assert.match(await page.textContent(".al-phones"), /Pixel 9/);
  await page.click("[data-al-on='night']");
  await page.waitForSelector(".al-note:has-text('Salvato')");
  assert.ok(await page.locator("[data-al-on='night']").evaluate((b) => !b.classList.contains("on")), "regola spenta e salvata");
  await page.click("[data-al-test]");
  await page.waitForFunction(() => /Prova inviata/.test(document.querySelector(".al-note").textContent));
  await page.keyboard.press("Escape");
  assert.equal(await page.locator(".alerts-modal").count(), 0);
  await done(page);
});

test("telefono: la scheda della stanza sale dal basso", { timeout: 30000 }, async () => {
  const page = await open({ width: 390, height: 844 });
  await casa(page);
  await page.click(".plan-room[data-area='cucina']");
  await page.waitForSelector(".casa-quick");
  assert.ok(await page.evaluate(() => document.body.classList.contains("casa-sheet")));
  const box = await page.locator(".casa-quick").boundingBox();
  assert.ok(box.y > 200 && box.x < 20, "la scheda è in basso e occupa la larghezza");
  await done(page);
});

test("in inglese: Casa, stanza, Energia e preferenze senza testi italiani mancanti", { timeout: 30000 }, async () => {
  const page = await open({ width: 1440, height: 900 }, "en");
  await casa(page);
  assert.match(await page.textContent("#casa"), /Room temperatures/);
  await page.click(".plan-room[data-area='soggiorno']");
  await page.click(".casa-quick [data-act='open']");
  await page.click("[data-act='edit']");
  assert.match(await page.textContent("#casa"), /Done editing/);
  await page.click("[data-act='home']");
  await page.click("[data-act='energy']");
  await page.waitForSelector(".casa-energy-modal");
  assert.match(await page.textContent(".casa-energy-modal"), /Energy/);
  await page.keyboard.press("Escape");
  await page.click("#ha-prefs");
  assert.match(await page.textContent("#prefs"), /Preferences/);
  assert.equal(await page.getAttribute("#chat-input", "placeholder"), "Talk to Jarvis…");
  const missing = await page.evaluate(() => [...(window.__i18nMissing || [])]);
  assert.deepEqual(missing, [], "testi senza inglese mostrati nella pagina");
  await done(page);
});
