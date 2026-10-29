"""What each Claude call costs, to show the remaining Anthropic credit in the dashboard.

Anthropic has no API to read the prepaid balance with a normal API key, so the HQ keeps its
own estimate: credit entered by the owner minus the cost of every call made since.
Prices in USD per million tokens (Claude API, October 2026).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float

    @property
    def cache_write(self) -> float:  # 5-minute cache writes cost 1.25x input
        return self.input * 1.25


PRICES: dict[str, Price] = {
    "claude-sonnet-5-5": Price(2.00, 10.00, 0.20),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.01),
    "claude-opus-5-5": Price(4.00, 20.00, 0.20),
    "claude-opus-5": Price(5.00, 25.00, 0.50),
    "claude-fable-5-1": Price(10.00, 50.00, 0.25),
}
# Haiku 5.5 bills prompts above 100K tokens at a higher rate.
HAIKU_LONG = Price(0.50, 2.50, 0.05)
WEB_SEARCH_USD = 10.00 / 1000  # per search
FALLBACK_PRICE = PRICES["claude-opus-5-5"]  # unknown model: estimate high rather than low


def call_cost(model: str, usage) -> float:
    price = PRICES.get(model, FALLBACK_PRICE)
    fresh = usage.input_tokens or 0
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    if model == "claude-haiku-5-5" and fresh + read + write > 100_000:
        price = HAIKU_LONG
    cost = (
        fresh * price.input
        + read * price.cache_read
        + write * price.cache_write
        + (usage.output_tokens or 0) * price.output
    ) / 1_000_000
    server = getattr(usage, "server_tool_use", None)
    searches = (getattr(server, "web_search_requests", 0) or 0) if server else 0
    return cost + searches * WEB_SEARCH_USD
