"""The neural map: what the team knows, as a graph.

Structure (Jarvis → companies → departments → agents) plus everything the agents produced
(memories, tasks, deadlines, email drafts), linked to their author and to the keywords they
share: shared keywords are what pull related knowledge together into clusters.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hubnex.hq import HQ

MAX_KEYWORDS = 80
KEYWORDS_PER_ITEM = 4
WORD = re.compile(r"[a-zàèéìòù]{5,}")
STOPWORDS = set(
    """
    alla alle allo anche ancora avere aveva abbiamo avete hanno quando quanto quale quali questa
    queste questi questo quella quelle quelli quello sono stata stato stati state siamo siete
    della delle dello degli dalla dalle dallo dagli nella nelle nello negli sulla sulle sullo
    sugli come cosa cose dove dopo prima perché perche però pero poiché mentre oppure senza
    sempre tutti tutte tutto tutta molto molti molte poco ogni altro altri altra altre essere
    fatto fare fatta fatte stesso stessa nostro nostra vostro vostra loro presso circa ultimo
    ultima nuovo nuova grazie buongiorno buonasera saluti cordiali gentile ciao signore
    compito risultato richiesta risposta email messaggio proprietario utente jarvis agente
    oggi domani ieri giorno giorni mese anno parte punto
    """.split()
)


def _words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if w not in STOPWORDS}


def _short(text: str, n: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


async def build_graph(hq: "HQ") -> dict:
    nodes: list[dict] = []
    links: list[dict] = []
    org = hq.org

    def node(id_: str, type_: str, label: str, color: str | None = None, detail: str = "", ts: float | None = None):
        nodes.append({"id": id_, "type": type_, "label": label, "color": color, "detail": detail, "ts": ts})

    def link(a: str, b: str, kind: str):
        links.append({"source": a, "target": b, "kind": kind})

    # --- structure
    node("jarvis", "core", org.boss_name, "#4fd1ff", "Il capo del team")
    agent_color: dict[str, str] = {}
    for c in org.companies:
        node(f"c:{c.id}", "company", c.name, "#4fd1ff", c.description)
        link("jarvis", f"c:{c.id}", "structure")
        for d in c.departments:
            node(f"d:{c.id}/{d.id}", "department", d.name, d.color)
            link(f"c:{c.id}", f"d:{c.id}/{d.id}", "structure")
    for a in org.agents:
        dept = next(d for c in org.companies if c.id == a.company for d in c.departments if d.id == a.department)
        agent_color[a.id] = a.color or dept.color
        node(f"a:{a.id}", "agent", a.name, agent_color[a.id], a.role)
        link(f"d:{a.company}/{a.department}", f"a:{a.id}", "structure")

    def owner(agent_id: str | None, company: str | None = None) -> str:
        if agent_id and f"a:{agent_id}" in ids:
            return f"a:{agent_id}"
        if company and f"c:{company}" in ids:
            return f"c:{company}"
        return "jarvis"

    ids = {n["id"] for n in nodes}

    # --- knowledge
    items: list[tuple[str, str]] = []  # (node id, text for keywords)
    for m in await hq.store.memories():
        nid = f"m:{m['id']}"
        node(nid, "memory", _short(m["topic"], 40), None, m["content"], m["ts"])
        link(owner(m.get("agent_id"), m["scope"] if m["scope"] != "global" else None), nid, "memory")
        items.append((nid, f"{m['topic']} {m['content']}"))
    for t in await hq.store.recent_tasks():
        if t["agent_id"] not in agent_color:
            continue
        nid = f"t:{t['id']}"
        node(nid, "task", _short(t["task"], 40), None, (t["result"] or "")[:1500], t["created"])
        link(f"a:{t['agent_id']}", nid, "task")
        items.append((nid, f"{t['task']} {(t['result'] or '')[:500]}"))
    for d in await hq.store.deadlines(include_done=False):
        nid = f"s:{d['id']}"
        node(nid, "deadline", _short(d["title"], 40), None, f"Scade: {d['due']}\n{d['notes'] or ''}".strip(), d["created"])
        link(owner(d["agent_id"], d["company"]), nid, "deadline")
        items.append((nid, f"{d['title']} {d['notes'] or ''}"))
    for b in await hq.store.drafts_open():
        nid = f"b:{b['id']}"
        node(nid, "draft", _short(b["subject"], 40), None, f"A: {b['to_addr']}\n\n{b['body']}", b["created"])
        link(owner("mail"), nid, "draft")
        items.append((nid, f"{b['subject']} {b['body'][:500]}"))

    # --- shared keywords
    words = {nid: _words(text) for nid, text in items}
    df = Counter(w for ws in words.values() for w in ws)
    # With little knowledge every shared word is useful; with a lot, words found in more than
    # half of everything stop telling things apart.
    limit = len(items) if len(items) < 10 else int(len(items) * 0.5)
    keep = {w for w, n in df.most_common(MAX_KEYWORDS) if 2 <= n <= limit}
    for w in keep:
        node(f"k:{w}", "keyword", w)
    for nid, ws in words.items():
        for w in sorted(ws & keep, key=lambda w: -df[w])[:KEYWORDS_PER_ITEM]:
            link(nid, f"k:{w}", "keyword")

    counts = Counter(n["type"] for n in nodes)
    return {
        "nodes": nodes,
        "links": links,
        "stats": {
            "nodes": len(nodes),
            "links": len(links),
            "memories": counts["memory"],
            "tasks": counts["task"],
            "keywords": counts["keyword"],
        },
    }
