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
  await panel.evaluate((el) => { el.scrollTop = 300; });
  const scrolled = await panel.evaluate((el) => el.scrollTop);
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

test("preferenze: il backup si scarica", { timeout: 30000 }, async () => {
  const page = await open();
  await page.click("#ha-prefs");
  const [download] = await Promise.all([page.waitForEvent("download"), page.click("#backup-get")]);
  assert.match(download.suggestedFilename(), /^hubnex-backup-\d{8}-\d{4}\.zip$/);
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
