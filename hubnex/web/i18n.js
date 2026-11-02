// Languages of the dashboard. The Italian text is the key ("gettext style"): t("Salva") is
// "Salva" in Italian and EN["Salva"] in English. Variables: t("{n} luci accese", { n }).
// A test (tests/ui/i18n.test.cjs) checks that every t("…") in the code has its English.
import { EN } from "./i18n-en.js";

export const LANGS = { it: "Italiano", en: "English" };

// Chosen once, before anything is drawn: the viewer's preference, else the language of their
// Home Assistant (the page runs inside it), else the browser's. Not Italian means English.
function pick() {
  let lang = "";
  try { lang = localStorage.getItem("hq_lang") || ""; } catch {}
  if (!LANGS[lang]) {
    try { lang = window.parent.document.querySelector("home-assistant")?.hass?.language || ""; } catch {}
    lang = lang || navigator.language || "it";
  }
  return String(lang).toLowerCase().startsWith("it") ? "it" : "en";
}

export const LANG = pick();
export const LOCALE = LANG === "it" ? "it-IT" : "en-GB";
document.documentElement.lang = LANG;

export function t(text, vars) {
  let out = LANG === "it" ? text : EN[text] ?? text;
  if (LANG !== "it" && EN[text] === undefined) (window.__i18nMissing ||= new Set()).add(text);
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
