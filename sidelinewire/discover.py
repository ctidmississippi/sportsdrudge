#!/usr/bin/env python3
"""Find direct RSS/Atom feeds for outlets currently read through Google News.
Writes discovered.json next to this file and records why a site failed.
Standard library only."""
import json, re, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
}
PATHS = [
    "/feed", "/feed/", "/rss", "/rss.xml", "/feeds/rss", "/index.xml", "/rss/index.xml", "/feed.xml", "/atom.xml",
    "/arc/outboundfeeds/rss/?outputType=xml", "/arc/outboundfeeds/rss/category/sports/?outputType=xml",
    "/rss/sports", "/sports/rss", "/sports/feed", "/feed/sports", "/category/sports/feed", "/rss/sports.xml",
    "/rss/latest", "/rss/news", "/rss/all", "/?feed=rss2", "/feeds/posts/default", "/rss/headlines",
]


def get(url, limit=400000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=8) as r:
        return r.read(limit).decode("utf-8", "replace")


def err_name(e):
    code = getattr(e, "code", None)
    return str(code) if code else type(e).__name__


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
    parts = domain.split("/", 1)
    host = parts[0]
    section = "/" + parts[1].strip("/") if len(parts) > 1 else ""
    cands, base, error = [], "https://" + host, None
    for h in ["https://" + host, "https://www." + host if not host.startswith("www.") else None]:
        if not h:
            continue
        try:
            body = get(h + "/" + section.strip("/"), 300000)
        except Exception as e:
            error = error or err_name(e)
            continue
        error = None
        base = h
        for m in re.finditer(r"<link[^>]+>", body, re.I):
            tag = m.group(0)
            if re.search(r"application/(rss|atom)\+xml", tag, re.I):
                hm = re.search(r"href=[\"']([^\"']+)", tag, re.I)
                if hm:
                    cands.append(urllib.parse.urljoin(h + "/", hm.group(1).replace("&amp;", "&")))
        n = 0
        for m in re.finditer(r"href=[\"']([^\"'#]+)[\"']", body, re.I):
            u = m.group(1).replace("&amp;", "&")
            if re.search(r"(rss|/feed|\.xml|outboundfeeds)", u, re.I) and not re.search(r"sitemap|\.(css|js|png|jpg)", u, re.I):
                cands.append(urllib.parse.urljoin(h + "/", u))
                n += 1
                if n >= 6:
                    break
        break
    if section:
        for p in ("/feed", "/feed/", "/rss", "/rss.xml", "/?outputType=xml", "/rss/index.xml", "/index.xml"):
            cands.append(base + section + p)
        for p in ("/arc/outboundfeeds/rss/category" + section + "/?outputType=xml",):
            cands.append(base + p)
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
        if len(out) >= 4 or len(seen) >= 30:
            break
    return out, error


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
        except Exception as e:
            return d, ([], err_name(e))

    with ThreadPoolExecutor(16) as ex:
        found = dict(ex.map(work, domains))
    res = [{"name": f["name"], "tag": f["tag"], "w": f["w"], "domain": d, "extra": extra,
            "candidates": found.get(d, ([], None))[0], "error": found.get(d, ([], None))[1]}
           for f, d, extra in todo]
    json.dump(res, open(ROOT / "discovered.json", "w"), indent=0)
    good = [d for d in domains if found.get(d, ([], None))[0]]
    errs = {}
    for d in domains:
        e = found.get(d, ([], None))[1]
        if e and not found[d][0]:
            errs[e] = errs.get(e, 0) + 1
    print(len(domains), "domains;", len(good), "with a direct feed; homepage errors:", errs)


if __name__ == "__main__":
    main()
