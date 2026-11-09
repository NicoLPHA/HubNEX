// Every Italian text of the dashboard (t("…") and data-i18n) has its English and its Dutch.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const path = require("node:path");

test("il dizionario inglese è completo", () => {
  const out = execFileSync(process.env.PYTHON || "python3", ["dev/i18n_keys.py", "--missing"], { cwd: path.resolve(__dirname, "../..") });
  assert.deepEqual(JSON.parse(out), [], "testi senza traduzione inglese (aggiungili in web/i18n-en.js)");
});

test("il dizionario olandese è completo", () => {
  const out = execFileSync(process.env.PYTHON || "python3", ["dev/i18n_keys.py", "--missing", "--lang", "nl"], { cwd: path.resolve(__dirname, "../..") });
  assert.deepEqual(JSON.parse(out), [], "testi senza traduzione olandese (aggiungili in web/i18n-nl.js)");
});
test("Nederlands is de starttaal als niets anders bekend is", async () => {
  const { pathToFileURL } = require("node:url");
  const file = pathToFileURL(path.resolve(__dirname, "../../web/i18n.js")).href;
  let n = 0;
  const load = async (stored, ha, browser) => {
    globalThis.localStorage = { getItem: () => stored ?? null, setItem() {}, removeItem() {} };
    globalThis.window = { parent: ha ? { document: { querySelector: () => ({ hass: { language: ha } }) } } : {} };
    globalThis.document = { documentElement: {} };
    Object.defineProperty(globalThis, "navigator", { value: { language: browser }, configurable: true });
    const m = await import(`${file}?x=${n++}`);
    return [m.LANG, m.t("Salva")];
  };
  assert.deepEqual(await load(null, null, "en-US"), ["nl", "Opslaan"], "nothing known: Dutch, not the browser's language");
  assert.deepEqual(await load(null, null, "it-IT"), ["nl", "Opslaan"]);
  assert.deepEqual(await load(null, "en", "nl-NL"), ["en", "Save"], "Home Assistant's own language still wins");
  assert.deepEqual(await load("it", "nl", "nl-NL"), ["it", "Salva"], "the viewer's own choice wins over everything");
});
