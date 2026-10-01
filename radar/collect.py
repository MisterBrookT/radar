"""Stage 1: collect candidates. All free: arXiv (OAI-PMH), alphaXiv signals, Hacker News, optional X via `bird`."""
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import httpx

from .common import save
from .topics import load_topic

# Historical names remain aliases; all topic choices live in data presets.
PAPER_TERMS = load_topic().get('paper_terms', [])
X_QUERIES = load_topic()['search_queries']
X_MIN_LIKES = 20
ATOM = "{http://www.w3.org/2005/Atom}"


OAI = "https://oaipmh.arxiv.org/oai"
OAI_NS = {"o": "http://www.openarchives.org/OAI/2.0/", "a": "http://arxiv.org/OAI/arXiv/"}
CATS = set(load_topic().get('arxiv_categories', []))


def relevant(title: str, abstract: str, cats: set) -> bool:
    topic = load_topic()
    t = f"{title} {abstract}".lower()
    if any(term.lower() in t for term in topic.get('paper_terms', [])):
        return True
    return bool(topic.get('hci_ai_interface_fallback') and "cs.HC" in cats and re.search(r"\b(interface|ui|gui)s?\b", t)
                and re.search(r"\b(llm|agent|generative|language model)s?\b", t))


def date_window(days: int = 7, end_date=None):
    """Inclusive UTC calendar dates; successive seven-day endpoints do not overlap."""
    if days < 1:
        raise ValueError('Collection days must be positive')
    end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    end = end or datetime.now(timezone.utc).date()
    return end - timedelta(days=days-1), end


def arxiv_papers(days: int, max_pages: int | None = None, end_date=None) -> list[dict]:
    """arXiv OAI-PMH bulk feed: free, no key, and reachable where the search API is blocked."""
    if max_pages is not None and max_pages < 1:
        raise ValueError('arXiv page bound must be positive')
    start, end = date_window(days, end_date)
    since = start.isoformat()
    # OAI datestamps describe metadata updates, not publication dates. An upper
    # OAI bound would hide in-window papers updated after that week ended.
    # Fetch updates from the start and enforce the created-date window below.
    params, out = {"verb": "ListRecords", "metadataPrefix": "arXiv", "set": load_topic().get('arxiv_set', 'cs'), "from": since}, []
    pages = 0
    while params and (max_pages is None or pages < max_pages):
        r = httpx.get(OAI, params=params, timeout=45 if max_pages else 180)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        error = root.find("o:error", OAI_NS)
        if error is not None and error.get("code") != "noRecordsMatch":
            raise ValueError(f"arXiv OAI error: {error.get('code')}")
        pages += 1
        for rec in root.iter(f"{{{OAI_NS['o']}}}record"):
            m = rec.find(".//a:arXiv", OAI_NS)
            if m is None:
                continue
            created = m.findtext("a:created", "", OAI_NS)
            if not since <= created <= end.isoformat():  # old revisions are not new publications
                continue
            cats = set(m.findtext("a:categories", "", OAI_NS).split())
            title = " ".join(m.findtext("a:title", "", OAI_NS).split())
            abstract = " ".join(m.findtext("a:abstract", "", OAI_NS).split())
            allowed = set(load_topic().get('arxiv_categories', []))
            if (allowed and not cats & allowed) or not relevant(title, abstract, cats):
                continue
            aid = m.findtext("a:id", "", OAI_NS)
            authors = [" ".join(filter(None, [a.findtext("a:forenames", "", OAI_NS), a.findtext("a:keyname", "", OAI_NS)]))
                       for a in m.findall("a:authors/a:author", OAI_NS)][:4]
            out.append({"kind": "paper", "id": aid, "title": title, "text": abstract, "authors": authors,
                        "date": created, "url": f"https://arxiv.org/abs/{aid}"})
        if max_pages:
            print(f"  arXiv page {pages}/{max_pages}: {len(out)} candidates", flush=True)
        tok = root.find(".//o:resumptionToken", OAI_NS)
        params = {"verb": "ListRecords", "resumptionToken": tok.text} if tok is not None and tok.text else None
    return out


def hn_stories(days: int, end_date=None) -> list[dict]:
    """Hacker News via Algolia: free builder/startup signal (points, comments)."""
    start, end = date_window(days, end_date)
    since = int(datetime.combine(start, datetime.min.time(), timezone.utc).timestamp())
    until = int(datetime.combine(end+timedelta(days=1), datetime.min.time(), timezone.utc).timestamp())
    seen, out = set(), []
    for q in load_topic()['search_queries']:
        r = httpx.get("https://hn.algolia.com/api/v1/search", timeout=30, params={
            "query": q, "tags": "story", "numericFilters": f"created_at_i>={since},created_at_i<{until}"})
        r.raise_for_status()
        for h in r.json().get("hits", []):
            if h["objectID"] in seen:
                continue
            seen.add(h["objectID"])
            out.append({"kind": "hn", "id": h["objectID"], "title": h["title"],
                        "text": h["title"] + (" " + h["story_text"] if h.get("story_text") else ""),
                        "authors": [h.get("author", "")], "date": h["created_at"][:10],
                        "url": f"https://news.ycombinator.com/item?id={h['objectID']}", "link": h.get("url"),
                        "signals": {"points": h.get("points", 0), "comments": h.get("num_comments", 0)},
                        "image": None})
    return out


def alphaxiv_signals(p: dict) -> dict:
    try:
        r = httpx.get(f"https://api.alphaxiv.org/papers/v3/legacy/{p['id']}", timeout=20)
        g = r.json()["paper"]["paper_group"]
        m = g.get("metrics", {})
        v = m.get("visits_count", {})
        p["signals"] = {"votes": m.get("public_total_votes", 0), "visits": v.get("all", 0),
                        "visits_24h": v.get("last24Hours", 0)}
    except Exception:
        p["signals"] = {"votes": 0, "visits": 0, "visits_24h": 0}
    p["image"] = None
    return p


def x_posts(days: int, end_date=None, min_likes: int = X_MIN_LIKES) -> list[dict]:
    """Free: `bird` reads X with your own browser login. No paid API. Skipped if unavailable."""
    import shutil
    if not shutil.which("bird") or os.environ.get("GENUI_NO_X"):
        print("  X skipped")
        return []
    env = {**os.environ, "NODE_USE_ENV_PROXY": "1",
           "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")}
    start, end = date_window(days, end_date)
    since, until = start.isoformat(), (end+timedelta(days=1)).isoformat()
    seen, out = set(), []
    for q in load_topic()['search_queries']:
        query = f"{q} min_faves:{min_likes} -filter:replies since:{since} until:{until}"
        res = subprocess.run(["bird", "--cookie-source", "chrome", "search", query, "-n", "30", "--json"],
                             capture_output=True, text=True, env=env, timeout=120)
        try:
            tweets = json.loads(res.stdout)
        except json.JSONDecodeError:
            print(f"  X query failed: {q}")
            continue
        for t in tweets:
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            art = t.get("article") or {}
            media = [m.get("url") for m in t.get("media", []) if m.get("url")]
            out.append({
                "kind": "tweet", "id": t["id"],
                "title": art.get("title") or t["text"][:80],
                "text": (t["text"] + " " + art.get("previewText", "")).strip(),
                "authors": [f"@{t['author']['username']}"],
                "date": datetime.strptime(t["createdAt"], "%a %b %d %H:%M:%S %z %Y").astimezone(timezone.utc).date().isoformat(),
                "url": f"https://x.com/{t['author']['username']}/status/{t['id']}",
                "signals": {"likes": t["likeCount"], "reposts": t["retweetCount"], "replies": t["replyCount"]},
                "image": media[0] if media else None,
            })
    return out


def github_releases(days, end_date=None):
    start, end = date_window(days, end_date)
    out, coverage = [], {}
    for repo in load_topic().get('github_repositories', []):
        try:
            response = httpx.get(f'https://api.github.com/repos/{repo}/releases',
                                 params={'per_page': 100}, timeout=20, follow_redirects=True)
            response.raise_for_status()
            coverage[repo] = 'ok'
            for release in response.json():
                published = (release.get('published_at') or '')[:10]
                if release.get('draft') or not start.isoformat() <= published <= end.isoformat():
                    continue
                out.append({'kind': 'release', 'id': repo+':'+str(release['id']),
                            'title': repo+' '+(release.get('name') or release['tag_name']),
                            'text': release.get('body') or '', 'date': published,
                            'url': release['html_url'], 'authors': [repo.split('/')[0]], 'signals': {}})
        except (httpx.HTTPError, ValueError) as exc:
            coverage[repo] = type(exc).__name__
    return out, coverage


def run(day_dir, days: int = 7, paper_days: int | None = None, max_pages: int | None = None,
        end_date=None, allow_empty=False, min_likes=X_MIN_LIKES, official=False):
    paper_days = days if paper_days is None else paper_days
    start, end = date_window(days, end_date)
    status = {'window': {'start': start.isoformat(), 'end_inclusive': end.isoformat(), 'timezone': 'UTC'},
              'paper_days': paper_days}
    try:
        raw_papers = arxiv_papers(paper_days, max_pages=max_pages, end_date=end)
        papers = [alphaxiv_signals(p) for p in raw_papers]
        status["arxiv"] = "ok"
    except (httpx.HTTPError, ET.ParseError) as exc:
        papers = []
        status["arxiv"] = type(exc).__name__
        print(f"  arXiv unavailable: {type(exc).__name__}; continuing with other sources", flush=True)
    tweets = x_posts(days, end_date=end, min_likes=min_likes)
    try:
        hn = hn_stories(days, end_date=end)
        status['hn'] = 'ok'
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        hn = []
        status['hn'] = type(exc).__name__
    def in_window(item, length):
        lower, upper = date_window(length, end)
        return lower.isoformat() <= item.get('date', '') <= upper.isoformat()
    papers = [p for p in papers if in_window(p, paper_days)]
    tweets = [p for p in tweets if in_window(p, days)]
    hn = [p for p in hn if in_window(p, days)]
    status.update(x="empty_or_skipped" if not tweets else "ok", bounded=bool(max_pages))
    releases = []
    if official:
        releases, official_status = github_releases(days, end)
        status['official_releases'] = official_status
    save(day_dir / "collection-status.json", status)
    print(f"  collected {len(papers)} papers, {len(tweets)} X posts, {len(hn)} HN stories")
    if not (papers or tweets or hn or releases) and not allow_empty:
        raise ValueError("all sources empty; refusing to generate an ungrounded briefing")
    save(day_dir / "candidates.json", papers + tweets + hn + releases)
