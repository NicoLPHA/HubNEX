// Languages of the dashboard. The Italian text is the key ("gettext style"): t("Salva") is
// "Salva" in Italian, EN["Salva"] in English and NL["Salva"] in Dutch. Variables: t("{n} luci accese", { n }).
// A test (tests/ui/i18n.test.cjs) checks that every t("…") in the code has its English and Dutch.
import { EN } from "./i18n-en.js";
import { NL } from "./i18n-nl.js";

export const LANGS = { it: "Italiano", en: "English", nl: "Nederlands" };
const DICTS = { en: EN, nl: NL };
const LOCALES = { it: "it-IT", en: "en-GB", nl: "nl-NL" };

// Chosen once, before anything is drawn: the viewer's preference, else the language of their
// Home Assistant (the page runs inside it), else Dutch. Italian and Dutch have their own texts;
// any other Home Assistant language means English.
function pick() {
  let lang = "";
  try { lang = localStorage.getItem("hq_lang") || ""; } catch {}
  if (!LANGS[lang]) {
    try { lang = window.parent.document.querySelector("home-assistant")?.hass?.language || ""; } catch {}
    lang = lang || "nl";
  }
  const code = String(lang).toLowerCase();
  return code.startsWith("it") ? "it" : code.startsWith("nl") ? "nl" : "en";
}

export const LANG = pick();
export const LOCALE = LOCALES[LANG];
document.documentElement.lang = LANG;

export function t(text, vars) {
  const dict = DICTS[LANG];
  let out = dict ? dict[text] ?? text : text;
  if (dict && dict[text] === undefined) (window.__i18nMissing ||= new Set()).add(text);
  if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (vars[k] ?? m));
  return out;
}

// Static texts of index.html: data-i18n (the element's text) and data-i18n-attr="placeholder,title".
export function translatePage(root = document) {
  if (LANG === "it") return;
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    // Only the element's own text, before any child element (e.g. <small> or <button>).
    const node = [...el.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
    if (node) node.textContent = node.textContent.replace(node.textContent.trim(), t(node.textContent.trim()));
  });
  root.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    for (const a of el.dataset.i18nAttr.split(",")) if (el.getAttribute(a)) el.setAttribute(a, t(el.getAttribute(a)));
  });
}

// The viewer's choice (Preferenze): "" = automatic. Takes effect on reload.
export function setLang(lang) {
  try { lang ? localStorage.setItem("hq_lang", lang) : localStorage.removeItem("hq_lang"); } catch {}
}

export const num = (v, d = 1) => Number(v).toLocaleString(LOCALE, { maximumFractionDigits: d });
