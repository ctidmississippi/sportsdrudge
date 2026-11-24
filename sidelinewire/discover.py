#!/usr/bin/env python3
"""Find direct RSS/Atom feeds for outlets currently read through Google News.
Writes discovered.json next to this file. Standard library only."""
import json, re, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; PregameNotesBot/1.0)", "Accept": "*/*"}
PATHS = ["/feed", "/feed/", "/rss", "/rss.xml", "/feeds/rss", "/index.xml", "/rss/index.xml", "/feed.xml", "/atom.xml"]


def get(url, limit=400000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read(limit).decode("utf-8", "replace")


def parse(s):
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def check(url):
    try:
        body = get(url)
        head = body[:3000].lower()
        if "<rss" not in head and "<feed" not in head and "<rdf" not in head:
            return None
        root = ET.fromstring(body.encode("utf-8", "replace"))
    except Exception:
        return None
    items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    newest = None
    for e in items:
        for ch in e:
            if ch.tag.split("}")[-1] in ("pubDate", "published", "updated", "date") and ch.text:
                d = parse(ch.text)
                if d and (newest is None or d > newest):
                    newest = d
    age = round((datetime.now(timezone.utc) - newest).total_seconds() / 3600, 1) if newest else None
    return {"url": url, "items": len(items), "newest_age_h": age}


def find(domain):
    host = domain.split("/")[0]
    cands, base = [], "https://" + host
    for h in ["https://" + host, "https://www." + host if not host.startswith("www.") else None]:
        if not h:
            continue
        try:
            body = get(h + "/", 250000)
        except Exception:
            continue
        base = h
        for m in re.finditer(r"<link[^>]+>", body, re.I):
            tag = m.group(0)
            if re.search(r"application/(rss|atom)\+xml", tag, re.I):
                hm = re.search(r"href=[\"']([^\"']+)", tag, re.I)
                if hm:
                    cands.append(urllib.parse.urljoin(h + "/", hm.group(1).replace("&amp;", "&")))
        break
    for p in PATHS:
        cands.append(base + p)
    seen, out = set(), []
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        r = check(c)
        if r and r["items"] >= 3:
            out.append(r)
        if len(out) >= 4 or len(seen) >= 12:
            break
    return out


def domain_of(f):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(f["url"]).query).get("q", [""])[0]
    m = re.search(r"site:(\S+)", q)
    if not m:
        return None, q
    extra = re.sub(r"site:\S+|when:\S+", "", q).strip()
    return m.group(1).strip("/"), extra


def main():
    feeds = json.load(open(ROOT / "feeds.json"))["feeds"]
    todo = []
    for f in feeds:
        if "news.google.com" not in f["url"]:
            continue
        d, extra = domain_of(f)
        if d:
            todo.append((f, d, extra))
    domains = sorted({d for _, d, _ in todo})

    def work(d):
        try:
            return d, find(d)
        except Exception:
            return d, []

    with ThreadPoolExecutor(12) as ex:
        found = dict(ex.map(work, domains))
    res = [{"name": f["name"], "tag": f["tag"], "w": f["w"], "domain": d, "extra": extra, "candidates": found.get(d, [])}
           for f, d, extra in todo]
    json.dump(res, open(ROOT / "discovered.json", "w"), indent=0)
    print(len(domains), "domains;", sum(1 for d in domains if found.get(d)), "with a direct feed")


if __name__ == "__main__":
    main()
