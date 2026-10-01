"""Stages 2-3: drop off-topic items (cheap LLM), then rank by platform signals only."""
import html
import os
import re

import httpx

PROXY = os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")

from .common import STRONG_MODEL, llm, load, save

TOPIC = ("Generative UI: AI or agents that generate, adapt, or render user interfaces "
         "(e.g. agent-to-UI protocols, UI generation models, adaptive/malleable interfaces, "
         "tools that turn prompts into apps or UI).")


def on_topic(items: list[dict]) -> list[dict]:
    keep = []
    for i in range(0, len(items), 25):
        batch = items[i:i + 25]
        listing = "\n".join(f"{j}. {it['title']} :: {it['text'][:400]}" for j, it in enumerate(batch))
        res = llm(f"Topic: {TOPIC}\nFor each item, is it substantively about this topic "
                  f"(a paper, product, release, demo, or argument centered on generating/adapting UI)? "
                  f"Reject: any listicle or roundup thread ('20 projects', '12 skills', '100 AI tools', 'repos people are building'), MCP servers/infra without a UI-generation angle, generic agent/model news, "
                  f"job posts, UI design shots without AI generation, off-topic non-English posts.\n"
                  f"Return JSON {{\"keep\": [indices]}}.\n\n{listing}",
                  model=STRONG_MODEL)
        keep += [batch[j] for j in res.get("keep", []) if j < len(batch)]
    return keep


def enrich(it: dict) -> None:
    """Posts are short: append readable text from the first linked page (skip x.com itself)."""
    for url in re.findall(r"https://t\.co/\w+", it["text"]):
        try:
            r = httpx.get(url, follow_redirects=True, timeout=20, proxy=PROXY,
                          headers={"User-Agent": "Mozilla/5.0"})
        except Exception:
            continue
        if "x.com" in r.url.host or "twitter.com" in r.url.host or "text/html" not in r.headers.get("content-type", ""):
            continue
        body = re.sub(r"(?s)<(script|style|nav|footer|header).*?</\1>", " ", r.text)
        text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()
        it["link"] = str(r.url)
        it["text"] += f"\n[Linked page {r.url}]: {text[:2500]}"
        return


def score(it: dict) -> float:
    s = it["signals"]
    if it["kind"] == "paper":
        return s["votes"] * 10 + s["visits"]
    if it["kind"] == "hn":
        return s["points"] + 2 * s["comments"]
    return s["likes"] + 3 * s["reposts"] + 2 * s["replies"]


def fetch_page(url: str, proxy=None) -> tuple[str, str] | None:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=20, proxy=proxy, headers={"User-Agent": "Mozilla/5.0"})
    except Exception:
        return None
    if "text/html" not in r.headers.get("content-type", ""):
        return None
    body = re.sub(r"(?s)<(script|style|nav|footer|header).*?</\1>", " ", r.text)
    return str(r.url), html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))).strip()


def run(day_dir, top: int = 5):
    """Top items by platform signal, normalised within each source so papers, X and HN all get a voice."""
    items = on_topic(load(day_dir / "candidates.json"))
    for it in items:
        it["score"] = score(it)
    groups = {}
    for it in sorted(items, key=lambda i: -i["score"]):
        groups.setdefault(it["kind"], []).append(it)
    picked = [g[0] for g in groups.values()] + [g[1] for g in groups.values() if len(g) > 1]
    picked = picked[:top]
    rest = [it for g in groups.values() for it in g if it not in picked]
    rest.sort(key=lambda i: -i["score"] / (groups[i["kind"]][0]["score"] or 1))
    picked += rest[: max(0, top - len(picked))]
    for it in picked:
        if it["kind"] == "tweet":
            enrich(it)
        elif it["kind"] == "hn" and it.get("link"):
            page = fetch_page(it["link"])
            if page:
                it["text"] += f"\n[Linked page {page[0]}]: {page[1][:2500]}"
    print(f"  on-topic {len(items)} -> selected {len(picked)} " + str({k: len(v) for k, v in groups.items()}))
    save(day_dir / "selected.json", picked)
