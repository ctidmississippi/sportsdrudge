#!/usr/bin/env python3
"""Fetch sports RSS/Atom feeds, cluster duplicate stories, rank, and render a
Drudge-style front page to public/index.html. Standard library only."""
import argparse, base64, html, json, math, os, re, sys, time
import urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
UA = "Mozilla/5.0 (compatible; SidelineWire/1.0; +https://github.com)"
STOP = set("a an the of to in on at for and or vs v with as by is are be from after before over into its it his her their will not out up new says say report reports reportedly per via just".split())

# ---------- config ----------
def load_config():
    cfg = json.load(open(ROOT / "config.json"))
    return cfg

# ---------- fetching ----------
def fetch(feed, timeout):
    t0 = time.time()
    try:
        req = urllib.request.Request(feed["url"], headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(3_000_000)
        items = parse(data, feed)
        return feed, items, None, round(time.time() - t0, 1)
    except Exception as e:
        return feed, [], f"{type(e).__name__}: {str(e)[:120]}", round(time.time() - t0, 1)

def tag(el):  # strip namespace
    return el.tag.rsplit("}", 1)[-1].lower()

def parse_date(s):
    if not s: return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def parse(data, feed):
    root = ET.fromstring(data)
    out = []
    for el in root.iter():
        if tag(el) not in ("item", "entry"): continue
        title = link = date = None
        for ch in el:
            t = tag(ch)
            if t == "title": title = "".join(ch.itertext()).strip()
            elif t == "link":
                link = ch.get("href") or (ch.text or "").strip() or link
                if ch.get("rel") not in (None, "alternate") and link and ch.get("href"): 
                    link = link  # keep first
            elif t in ("pubdate", "published", "updated", "date") and not date:
                date = parse_date(ch.text)
        if title and link:
            out.append({"title": html.unescape(re.sub(r"<[^>]+>", "", title)), "link": link.strip(), "date": date,
                        "source": feed["name"], "tag": feed.get("tag", "general"), "w": float(feed.get("w", 1))})
    return out

# ---------- classification ----------
KW = [
 ("nfl", r"\b(nfl|quarterback|touchdown|super bowl|week \d+ (?:picks|preview)|chiefs|eagles|cowboys|packers|patriots|49ers|ravens|bengals|steelers|seahawks|commanders|giants|jets|bills|dolphins|texans|colts|titans|jaguars|broncos|raiders|chargers|rams|cardinals|saints|panthers|falcons|buccaneers|bears|lions|vikings|browns)\b"),
 ("cfb", r"\b(college football|cfp|heisman|ncaa football|sec|big ten|big 12|acc|bowl game|ranked|no\. \d+)\b"),
 ("cbb", r"\b(college basketball|march madness|ncaa tournament|final four|cbb)\b"),
 ("nba", r"\b(nba|wnba|lakers|celtics|warriors|knicks|bucks|heat|spurs|nuggets|suns|clippers|thunder|rockets|mavericks|pistons|cavaliers|pacers|nets|bulls|hawks|magic|wizards|hornets|raptors|grizzlies|pelicans|kings|blazers|timberwolves|jazz|76ers|sixers)\b"),
 ("nhl", r"\b(nhl|stanley cup|hockey|bruins|rangers|maple leafs|canadiens|oilers|flames|canucks|avalanche|golden knights|kraken|predators|stars|blackhawks|red wings|lightning|panthers|hurricanes|devils|islanders|capitals|penguins|flyers|sabres|senators|wild|blues|jets|ducks|sharks|blue jackets|coyotes|mammoth)\b"),
 ("mlb", r"\b(mlb|world series|yankees|dodgers|mets|red sox|cubs|braves|astros|padres|phillies|orioles|rays|blue jays|guardians|tigers|twins|royals|mariners|rangers|angels|athletics|brewers|reds|pirates|cardinals|giants|rockies|diamondbacks|marlins|nationals|white sox|cy young|mvp)\b"),
 ("soccer", r"\b(premier league|la liga|bundesliga|serie a|champions league|mls|world cup|fifa|uefa|manchester|arsenal|chelsea|liverpool|tottenham|real madrid|barcelona|bayern|psg|usmnt|uswnt|nations league|transfer)\b"),
 ("other", r"\b(f1|formula 1|formula one|nascar|golf|pga|liv golf|tennis|atp|wta|ufc|mma|boxing|olympic|nba cup)\b"),
]
def classify(it):
    t = it["title"].lower()
    base = it["tag"]
    if base in ("media",): return "media"
    for k, pat in KW:
        if k == "other" and "nba cup" in t: continue
        if re.search(pat, t): 
            # general or mismatched tag -> trust keywords; specific tag wins ties
            if base not in ("general", k): return base
            return k
    return base if base != "general" else "other"

# ---------- clustering ----------
def norm_tokens(title):
    t = re.sub(r"[^a-z0-9' ]", " ", title.lower())
    return {w for w in t.split() if w not in STOP and len(w) > 1}

def sim(a, b):
    """Similarity of two token sets. Merges on high overall overlap, or on
    several shared distinctive tokens (handles very different phrasing)."""
    if not a or not b: return 0.0
    i = len(a & b)
    j = i / len(a | b)
    oc = i / min(len(a), len(b))
    s = j * 0.5 + oc * 0.5
    if i >= 3 and oc >= 0.45: s = max(s, 0.6)
    return s

def cluster(items, thresh):
    clusters = []
    for it in sorted(items, key=lambda x: -x["w"]):
        tk = norm_tokens(it["title"]); it["_tk"] = tk
        best, bs = None, 0
        for c in clusters:
            s = max(sim(tk, m["_tk"]) for m in c["items"])
            if s > bs: best, bs = c, s
        if best and bs >= thresh:
            best["items"].append(it)
        else:
            clusters.append({"items": [it]})
    return clusters

def score(c, now, half_life_h):
    srcs = {i["source"] for i in c["items"]}
    newest = max((i["date"] for i in c["items"] if i["date"]), default=None)
    age_h = (now - newest).total_seconds() / 3600 if newest else 24
    rec = 0.5 ** (max(age_h, 0) / half_life_h)
    wsum = sum(max(i["w"] for i in c["items"] if i["source"] == s) for s in srcs)
    return (math.log2(1 + len(srcs)) * 3 + wsum * 0.6) * (0.25 + rec)

def rep(c):
    # prefer a heavy-weight source with a reasonably short title
    return sorted(c["items"], key=lambda i: (-i["w"], len(i["title"])))[0]

# ---------- rendering ----------
def clean_title(t, maxlen=110):
    t = re.sub(r"\s+", " ", t).strip().rstrip(".…")
    t = re.sub(r"\s*[|\-–—]\s*(ESPN|CBS Sports|Yahoo Sports|The Athletic|AP News|NBC Sports|Fox Sports|SI\.com|Bleacher Report).*$", "", t, flags=re.I)
    if len(t) > maxlen: t = t[:maxlen].rsplit(" ", 1)[0]
    return t

def render(cfg, cols, lead, big, topleft, stats, now):
    css = (ROOT / "style.css").read_text()
    img = ""
    p = ROOT / cfg.get("lead_image", "assets/lead.jpg")
    if p.exists():
        b64 = base64.b64encode(p.read_bytes()).decode()
        img = f'<div class="lead"><a href="{html.escape(lead["link"])}"><img src="data:image/jpeg;base64,{b64}" alt=""></a></div>'
    def a(it, cls="", n=None):
        srcs = sorted({i["source"] for i in it["cluster"]})
        tip = ", ".join(srcs)
        return f'<a class="{cls}" href="{html.escape(it["link"])}" title="{html.escape(tip)}" rel="noopener">{html.escape(it["text"])}</a>'
    tl = "\n".join(a(i) for i in topleft)
    hl = "\n".join(a(i) for i in big)
    colhtml = []
    for col in cols:
        out = []
        for k, it in enumerate(col):
            if k and k % 3 == 0: out.append("<hr>")
            cls = ("hot " if it.get("hot") else "") + ("it" if k % 2 else "")
            out.append(a(it, cls.strip()))
        colhtml.append("\n".join(out))
    local = now.astimezone(timezone(timedelta(hours=cfg.get("utc_offset", -6))))
    stamp = local.strftime("%A, %B %-d, %Y · updated %-I:%M %p")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(cfg['site_name'])}</title>
<style>{css}</style></head><body>
<div class="tl">
{tl}
</div>
{img}
<div class="hl">
{hl}
</div>
<div class="logo">{html.escape(cfg['site_name'].upper())}</div>
<div class="cols">
{''.join(f'<div class="col">{c}</div>' for c in colhtml)}
</div>
<div class="foot">{stamp} · {stats['ok']} of {stats['total']} sources reporting · {stats['clusters']} stories ranked. Headlines link to the original outlets; hover one to see which outlets ran it.</div>
</body></html>"""

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="directory of local .xml files instead of network (testing)")
    ap.add_argument("--out", default=str(ROOT / "public" / "index.html"))
    args = ap.parse_args()
    cfg = load_config()
    feeds = json.load(open(ROOT / "feeds.json"))["feeds"]
    now = datetime.now(timezone.utc)

    if args.fixtures:
        results = []
        for f in sorted(Path(args.fixtures).glob("*.xml")):
            feed = {"name": f.stem.replace("_", " "), "url": str(f), "tag": "general", "w": 1.0}
            tg = re.match(r"(.*)__(\w+)__([\d.]+)$", f.stem)
            if tg: feed.update(name=tg.group(1).replace("_", " "), tag=tg.group(2), w=float(tg.group(3)))
            try: results.append((feed, parse(f.read_bytes(), feed), None, 0))
            except Exception as e: results.append((feed, [], str(e), 0))
    else:
        with ThreadPoolExecutor(max_workers=cfg.get("workers", 24)) as ex:
            results = list(ex.map(lambda f: fetch(f, cfg.get("timeout", 15)), feeds))

    report, items = [], []
    cutoff = now - timedelta(hours=cfg.get("max_age_hours", 40))
    for feed, its, err, secs in results:
        fresh = [i for i in its if i["date"] is None or cutoff <= i["date"] <= now + timedelta(hours=2)]
        report.append({"name": feed["name"], "url": feed["url"], "ok": err is None and len(its) > 0,
                       "items": len(its), "fresh": len(fresh), "error": err, "secs": secs})
        items += fresh
    ok = sum(1 for r in report if r["ok"])
    (ROOT / "feed_report.json").write_text(json.dumps(report, indent=1))
    print(f"feeds ok: {ok}/{len(report)}  items: {len(items)}", file=sys.stderr)
    if len(items) < cfg.get("min_items", 20):
        print("Too few items; refusing to overwrite the page.", file=sys.stderr); sys.exit(2)

    for it in items:
        it["sport"] = classify(it)
    clusters = cluster(items, cfg.get("cluster_threshold", 0.55))
    for c in clusters:
        c["score"] = score(c, now, cfg.get("half_life_hours", 14))
        r = rep(c); c["rep"] = r
        c["sport"] = max(set(i["sport"] for i in c["items"]), key=[i["sport"] for i in c["items"]].count)
        c["n"] = len({i["source"] for i in c["items"]})
    clusters.sort(key=lambda c: -c["score"])

    def mk(c, maxlen=110):
        r = c["rep"]
        return {"link": r["link"], "text": clean_title(r["title"], maxlen), "cluster": c["items"], "n": c["n"], "sport": c["sport"], "hot": False}

    top = [mk(c, 60) for c in clusters[:cfg.get("headline_lines", 4)]]
    for t in top: t["text"] = t["text"].upper()
    topleft = [mk(c, 80) for c in clusters[cfg.get("headline_lines", 4):cfg.get("headline_lines", 4) + 4]]
    for t in topleft: t["text"] = t["text"].upper() + "..."
    used = set(id(c) for c in clusters[:cfg.get("headline_lines", 4) + 4])
    rest = [c for c in clusters if id(c) not in used]

    groups = cfg["columns"]  # list of lists of sport keys
    per = cfg.get("items_per_column", 36)
    cols = []
    for g in groups:
        pool = [c for c in rest if c["sport"] in g][: per * 2]
        # interleave by score but cap per sport so one sport can't swallow the column
        cap = max(6, per // max(1, len(g)) + 6)
        cnt, col = {}, []
        for c in pool:
            if cnt.get(c["sport"], 0) >= cap: continue
            cnt[c["sport"]] = cnt.get(c["sport"], 0) + 1
            col.append(c)
            if len(col) >= per: break
        items_ = []
        for k, c in enumerate(col):
            m = mk(c); m["text"] += "..."
            if c["n"] >= cfg.get("hot_sources", 5): m["hot"] = True; m["text"] = m["text"].upper()
            items_.append(m)
        cols.append(items_)
    lead = top[0] if top else {"link": "#"}
    page = render(cfg, cols, lead, top, topleft, {"ok": ok, "total": len(report), "clusters": len(clusters)}, now)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(page)
    print(f"wrote {out} ({len(page)//1024} KB)", file=sys.stderr)

if __name__ == "__main__":
    main()
