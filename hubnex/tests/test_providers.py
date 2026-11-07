"""Other AI providers: the translation to OpenAI's API and back, and an agent run on them."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

import httpx

from hubnex import providers
from hubnex.pricing import call_cost
from hubnex.providers import from_openai, split_model, to_openai_messages, to_openai_tools
from hubnex.tools import web


def test_the_prefix_picks_the_provider():
    assert split_model("claude-sonnet-5-5") == ("anthropic", "claude-sonnet-5-5")
    assert split_model("openai:gpt-5-mini") == ("openai", "gpt-5-mini")
    assert split_model("ollama:qwen3:14b") == ("ollama", "qwen3:14b")  # the tag stays
    assert split_model("compat:meta/llama-4") == ("compat", "meta/llama-4")
    assert split_model("something:else") == ("anthropic", "something:else")


def test_messages_tools_and_replies_are_translated():
    msgs = to_openai_messages("Sei Jarvis.", [
        {"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}},
            {"type": "document", "title": "nota.txt", "source": {"type": "text", "media_type": "text/plain", "data": "ciao"}},
            {"type": "text", "text": "Cosa vedi?"},
        ]},
        {"role": "assistant", "content": [NS(type="thinking", thinking="…"), NS(type="text", text="Guardo."),
                                          NS(type="tool_use", id="t1", name="memory_search", input={"q": "x"})]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "niente", "is_error": True}]},
    ])
    assert msgs[0] == {"role": "system", "content": "Sei Jarvis."}
    parts = msgs[1]["content"]
    assert parts[0]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
    assert parts[1]["text"] == "«nota.txt»:\nciao" and parts[2]["text"] == "Cosa vedi?"
    assert msgs[2]["content"] == "Guardo."  # no thinking
    assert msgs[2]["tool_calls"][0]["function"] == {"name": "memory_search", "arguments": '{"q": "x"}'}
    assert msgs[3] == {"role": "tool", "tool_call_id": "t1", "content": "Errore: niente"}
    # Anthropic's own tools (web search) are left out, the others become functions
    tools = to_openai_tools([{"type": "web_search_20260209", "name": "web_search"},
                             {"name": "memory_save", "description": "Salva", "input_schema": {"type": "object"}}])
    assert tools == [{"type": "function", "function": {"name": "memory_save", "description": "Salva", "parameters": {"type": "object"}}}]
    # a reply with a tool call, even when the server says "stop"
    r = from_openai({"choices": [{"finish_reason": "stop", "message": {"content": None, "tool_calls": [
        {"id": "c1", "function": {"name": "memory_save", "arguments": '{"testo": "a"}'}}]}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 7, "prompt_tokens_details": {"cached_tokens": 40}}})
    assert r.stop_reason == "tool_use" and r.content[0].input == {"testo": "a"}
    assert (r.usage.input_tokens, r.usage.cache_read_input_tokens, r.usage.output_tokens) == (60, 40, 7)


def test_a_pdf_reaches_other_models_as_text():
    import io

    from PIL import Image

    b = io.BytesIO()
    Image.new("RGB", (50, 50), "white").save(b, "PDF")  # a scan: no text inside
    assert "senza testo" in providers.pdf_text(b.getvalue())
    assert "illeggibile" in providers.pdf_text(b"not a pdf")


def openai_server(replies: list[dict], seen: list[dict]):
    """A pretend OpenAI-compatible server: records the requests, answers in order."""

    def handle(req: httpx.Request) -> httpx.Response:
        seen.append({"url": str(req.url), "auth": req.headers.get("authorization"), "body": json.loads(req.content)})
        return httpx.Response(200, json=replies.pop(0))

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def reply(content=None, calls=None):
    msg = {"content": content}
    if calls:
        msg["tool_calls"] = [{"id": f"c{i}", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]
    return {"choices": [{"finish_reason": "tool_calls" if calls else "stop", "message": msg}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10}}


async def test_jarvis_runs_on_a_local_model_with_his_tools(make_hq, settings):
    settings.model = "ollama:qwen3:14b"
    settings.ollama_url = "http://192.168.1.20:11434"
    hq = make_hq([])
    seen: list[dict] = []
    hq.client._http = openai_server([
        reply(calls=[("memory_save", {"topic": "Garage", "content": "Il garage si chiude alle 22"})]),
        reply("Me lo ricordo."),
    ], seen)
    answer = await hq.chat("dashboard", "ricorda che il garage si chiude alle 22")
    assert answer == "Me lo ricordo."
    assert hq.client.requests == []  # nothing went to Anthropic
    first, second = seen
    assert first["url"] == "http://192.168.1.20:11434/v1/chat/completions" and first["auth"] is None
    body = first["body"]
    assert body["model"] == "qwen3:14b" and body["messages"][0]["role"] == "system"
    names = {t["function"]["name"] for t in body["tools"]}
    assert {"delegate", "memory_save"} <= names and "web_search" not in names
    assert "thinking" not in body and "reasoning_effort" not in body
    tool_msg = second["body"]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c0"
    assert "Il garage si chiude alle 22" in str(await hq.store.memories())
    # local models cost nothing
    assert sum(r["cost"] for r in await hq.store.usage_by("model", "2000-01-01", "2999-12-31")) == 0


async def test_an_agent_on_openai_gets_hubnex_web_fetch_and_its_key(make_hq, settings):
    settings.openai_api_key = "sk-test"
    hq = make_hq([])
    spec = next(a for a in hq.org.agents if "web_fetch" in a.tools)
    spec.model = "openai:gpt-5-mini"
    seen: list[dict] = []
    hq.client._http = openai_server([reply("Fatto.")], seen)
    assert await hq.run_agent(spec.id, "leggi la pagina") == "Fatto."
    assert seen[0]["url"] == "https://api.openai.com/v1/chat/completions" and seen[0]["auth"] == "Bearer sk-test"
    names = {t["function"]["name"] for t in seen[0]["body"]["tools"]}
    assert "web_fetch" in names and "web_search" not in names
    assert seen[0]["body"]["reasoning_effort"] == spec.effort.replace("xhigh", "high").replace("max", "high")


async def test_missing_settings_and_server_errors_are_said_plainly(make_hq, settings):
    hq = make_hq([])
    spec = hq.org.agents[0]
    spec.model = "ollama:qwen3"
    assert "manca l'indirizzo" in await hq.run_agent(spec.id, "ciao")
    settings.compat_base_url = "http://lmstudio.local:1234/v1"
    spec.model = "compat:qwen"
    hq.client._http = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(404, json={"error": {"message": "model 'qwen' not found"}})))
    assert "compat 404: model 'qwen' not found" in await hq.run_agent(spec.id, "ciao")


def test_costs_by_provider():
    u = NS(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    assert call_cost("ollama:qwen3", u, (5, 5)) == 0
    assert call_cost("openai:gpt-5-mini", u) == 0  # no price given: not counted
    assert call_cost("openai:gpt-5-mini", u, (0.25, 2.0)) == 2.25
    assert call_cost("claude-sonnet-5-5", u) == 12.0  # Claude: its own price list, as before


async def test_web_fetch_reads_public_pages_only(monkeypatch):
    async def public(host):
        return host == "example.com"

    monkeypatch.setattr(web, "public_host", public)
    page = "<html><head><title>Esempio</title><style>x{}</style></head><body><h1>Ciao</h1><script>no()</script><p>Mondo</p></body></html>"
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=page, headers={"content-type": "text/html"})))
    out = await web.fetch("https://example.com/", client)
    assert out["titolo"] == "Esempio" and out["testo"] == "Ciao\nMondo"
    for url in ("http://192.168.1.1/", "http://localhost:8123/", "file:///etc/passwd"):
        assert "errore" in await web.fetch(url, client)


async def test_public_host_refuses_the_house():
    assert await web.public_host("127.0.0.1") is False
    assert await web.public_host("192.168.1.10") is False
    assert await web.public_host("169.254.169.254") is False
