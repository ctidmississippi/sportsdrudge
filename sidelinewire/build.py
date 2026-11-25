#!/usr/bin/env python3
"""Fetch sports RSS/Atom feeds, cluster duplicate stories, rank, and render a
Drudge-style front page to public/index.html. Standard library only."""
import argparse, base64, html, json, math, os, re, sys, time
import urllib.request, urllib.error, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import art
SPAM = re.compile(r"\b(promo codes?|bonus|odds|predictions?|parlays?|best bets?|betting|sportsbook|draftkings|fanduel|bet365|caesars|prizepicks|how to watch|live stream|where to watch|tv channels?|kickoff times?|start time|fantasy|start 'em|waiver|dfs|player props|power rankings|subscriber chat|mock draft|trivia|this week in|highlights|video|pregame|postgame|post-game|game day|gameday|live blog|live updates|how to watch|game rewind|rewind|recap|preview|take on|taking on|what to know|everything you need|key matchups|game thread|matchup|how to follow|live updates|live blog|live coverage|live thread|scores, recaps|high school|prep football|how to bet|spread|moneyline|over/under|injury report|newsletter|podcast|quiz|slideshow|gallery|news & analysis|latest news|sports news|mailbag|sports on tv|open thread|game recap|box score|final score|live score|expert picks|staff picks|week \d+ picks|nfl picks)\b", re.I)
TEAMPAGE = re.compile(r"\bnews\s*[-–—|]\s*\w+|[-–—|]\s*(?:college football|college basketball|nfl|nba|nhl|mlb|mls|soccer|football|basketball|hockey|baseball)\s*$|\bnews\s*$", re.I)
POLITICS = re.compile(r"\b(trump|biden|harris|vance|congress|senate|senator|white house|democrat|democrats|republican|republicans|supreme court|nvidia|tariff|tariffs|stock market|wall street|federal reserve|inflation|ukraine|russia|gaza|israel|election|immigration|ceo|ai chip|bitcoin|crypto)\b", re.I)
def offtopic(title):
    """Politics/business headline with no sport keyword anywhere in it."""
    t = title.lower()
    if not POLITICS.search(t):
        return False
    return not any(re.search(p, t) for _, p in KW)
SPAM2 = re.compile(r"\(\s*(?:[A-Za-z]+\s+)?\d{1,2}[ /]+[A-Za-z]+,?\s+\d{4}\s*\)|\(\s*[A-Za-z]+\s+\d{1,2},?\s+\d{4}\s*\)|\(\s*\d{1,2}/\d{1,2}/\d{2,4}\s*\)")
UA = "Mozilla/5.0 (compatible; SidelineWire/1.0; +https://github.com)"
STOP = set("a an the of to in on at for and or vs v with as by is are be from after before over into its it his her their will not out up new says say report reports reportedly per via just".split())

# ---------- config ----------
def load_config():
    cfg = json.load(open(ROOT / "config.json"))
    return cfg

# ---------- fetching ----------
def fetch(feed, timeout, retries=2):
    t0 = time.time(); err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(feed["url"], headers={"User-Agent": UA, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read(3_000_000)
            return feed, parse(data, feed), None, round(time.time() - t0, 1)
        except urllib.error.HTTPError as e:
            err = f"HTTPError: {e.code}"
            if e.code in (429, 503) and attempt < retries:
                time.sleep(8 * (attempt + 1)); continue
            break
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
            break
    return feed, [], err, round(time.time() - t0, 1)

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
        src = feed["name"]
        if title and "news.google.com" in feed["url"] and " - " in title:
            title, src = title.rsplit(" - ", 1)
        if title and link:
            out.append({"title": html.unescape(re.sub(r"<[^>]+>", "", title)), "link": link.strip(), "date": date,
                        "source": src, "tag": feed.get("tag", "general"), "w": float(feed.get("w", 1))})
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
 ("other", r"\b(f1|formula 1|formula one|nascar|indycar|motogp|golf|pga|liv golf|tennis|atp|wta|ufc|mma|boxing|olympic|olympics|nba cup|track and field|athletics|marathon|swimming|gymnastics|cycling|tour de france|rugby|cricket|volleyball|lacrosse|softball|wrestling|skiing|figure skating|curling)\b"),
]
NICHE = [
 ("track", r"track and field|world athletics|marathon|sprinter|diamond league|\bathletics\b"),
 ("swim", r"swimming|swimmer|aquatics|\bdiving\b"),
 ("gym", r"gymnast"),
 ("cycling", r"cycling|tour de france|cyclist"),
 ("rugby", r"rugby"),
 ("cricket", r"cricket|the ashes|\bipl\b"),
 ("mma", r"\bufc\b|\bmma\b|boxing|title fight"),
 ("olympics", r"olympic|\bioc\b"),
 ("volleyball", r"volleyball"),
 ("motor", r"\bf1\b|formula 1|nascar|indycar|motogp"),
 ("tennis", r"tennis|\batp\b|\bwta\b|grand slam"),
 ("golf", r"\bgolf|\bpga\b|\blpga\b"),
 ("winter", r"skiing|biathlon|figure skating|speed skating|curling"),
 ("college", r"lacrosse|wrestling|softball"),
]
def niche(c):
    t = " ".join(i["title"] for i in c["items"][:4]).lower()
    for k, pat in NICHE:
        if re.search(pat, t): return k
    return None

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

def render(cfg, cols, lead, big, topleft, stats, now, lead_img="", media=None):
    css = (ROOT / "style.css").read_text()
    jsf = ROOT / "ticker.js"
    js = jsf.read_text() if jsf.exists() else ""
    img = f'<div class="lead"><a href="{html.escape(lead["link"])}"><img src="{lead_img}" alt=""></a></div>' if lead_img else ""
    def a(it, cls="", n=None):
        srcs = sorted({i["source"] for i in it["cluster"]})
        tip = ", ".join(srcs)
        return f'<a class="{cls}" href="{html.escape(it["link"])}" title="{html.escape(tip)}" rel="noopener">{html.escape(it["text"])}</a>'
    tl = "\n".join(a(i) for i in topleft)
    hl = "\n".join(a(i) for i in big)
    desc = html.escape(cfg.get("site_description", ""))
    site = html.escape(cfg["site_name"])
    surl = html.escape(cfg.get("site_url", ""))
    mediahtml = ('<div class="media"><span class="mh">SPORTS MEDIA</span>' + "\n".join(a(i) for i in media) + "</div>") if media else ""
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
<title>{site}</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="website"><meta property="og:title" content="{site}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{surl}">
<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{site}"><meta name="twitter:description" content="{desc}">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%23c00'/%3E%3Ctext x='32' y='46' font-size='40' font-weight='bold' text-anchor='middle' fill='white' font-family='Arial'%3EP%3C/text%3E%3C/svg%3E">
<style>{css}</style></head><body>
<div id="ticker"></div>
<div class="tl">
{tl}
</div>
{img}
<div class="hl">
{hl}
</div>
<div class="logo">{html.escape(cfg['site_name'].upper())}</div>
{mediahtml}
<div class="cols">
{''.join(f'<div class="col">{c}</div>' for c in colhtml)}
</div>
<div class="foot">{stamp} · {stats['ok']} of {stats['total']} sources reporting. Headlines link to the original outlets.</div>
<script>{js}</script>
</body></html>"""

# ---------- lead image ----------
def pick_lead_image(cfg, lead):
    """A user-supplied photo whose keywords match the top story wins; otherwise
    an original sport-matched illustration. Rules live in assets/leads.json:
    [{"keywords": ["chiefs", "mahomes"], "file": "assets/leads/chiefs.jpg"}]"""
    text = " ".join(i["title"] for i in lead.get("cluster", [])).lower() if lead.get("cluster") else lead.get("text", "").lower()
    rules = ROOT / "assets" / "leads.json"
    if rules.exists():
        try:
            for r in json.load(open(rules)):
                if any(re.search(r"\b" + re.escape(k.lower()) + r"\b", text) for k in r.get("keywords", [])):
                    p = ROOT / r["file"]
                    if p.exists():
                        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
                        return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
        except Exception as e:
            print("leads.json problem:", e, file=sys.stderr)
    lp = ROOT / str(cfg.get("lead_image", ""))
    if cfg.get("lead_image") and lp.is_file():
        mime = "image/png" if lp.suffix.lower() == ".png" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(lp.read_bytes()).decode()
    return art.data_uri(lead.get("sport", ""), text)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="directory of local .xml files instead of network (testing)")
    ap.add_argument("--out", default=str(ROOT / "public" / "index.html"))
    ap.add_argument("--reuse", help="items.json from a previous run: re-render without fetching")
    args = ap.parse_args()
    cfg = load_config()
    feeds = json.load(open(ROOT / "feeds.json"))["feeds"]
    now = datetime.now(timezone.utc)

    if args.reuse:
        results = []
    elif args.fixtures:
        results = []
        for f in sorted(Path(args.fixtures).glob("*.xml")):
            feed = {"name": f.stem.replace("_", " "), "url": str(f), "tag": "general", "w": 1.0}
            tg = re.match(r"(.*)__(\w+)__([\d.]+)$", f.stem)
            if tg: feed.update(name=tg.group(1).replace("_", " "), tag=tg.group(2), w=float(tg.group(3)))
            try: results.append((feed, parse(f.read_bytes(), feed), None, 0))
            except Exception as e: results.append((feed, [], str(e), 0))
    else:
        gn = [f for f in feeds if "news.google.com" in f["url"]]
        other = [f for f in feeds if "news.google.com" not in f["url"]]
        def run_gn():
            out = []
            for f in gn:
                out.append(fetch(f, cfg.get("timeout", 15)))
                time.sleep(cfg.get("gn_delay", 1.5))
            return out
        with ThreadPoolExecutor(max_workers=cfg.get("workers", 24) + 1) as ex:
            gf = ex.submit(run_gn)
            results = list(ex.map(lambda f: fetch(f, cfg.get("timeout", 15)), other))
            results += gf.result()

    report, items = [], []
    cutoff = now - timedelta(hours=cfg.get("max_age_hours", 40))
    for feed, its, err, secs in results:
        fresh = [i for i in its if i["date"] is None or cutoff <= i["date"] <= now + timedelta(hours=2)]
        report.append({"name": feed["name"], "url": feed["url"], "ok": err is None and len(its) > 0,
                       "items": len(its), "fresh": len(fresh), "error": err, "secs": secs})
        items += fresh
    fetched = now
    if args.reuse:
        data = json.load(open(args.reuse))
        report = data["report"]
        items = [dict(i, date=parse_date(i["date"])) for i in data["items"]]
        fetched = parse_date(data["fetched_at"]) or now
    ok = sum(1 for r in report if r["ok"])
    (ROOT / "feed_report.json").write_text(json.dumps(report, indent=1))
    print(f"feeds ok: {ok}/{len(report)}  items: {len(items)}", file=sys.stderr)
    keep = Path(args.out).parent / "items.json"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(json.dumps({"fetched_at": fetched.isoformat(), "report": report, "items": [dict({k: v for k, v in i.items() if not k.startswith("_")}, date=i["date"].isoformat() if i["date"] else None) for i in items]}))
    if len(items) < cfg.get("min_items", 20):
        print("Too few items; refusing to overwrite the page.", file=sys.stderr); sys.exit(2)

    before = len(items)
    items = [i for i in items if len(i["title"]) >= 15 and not SPAM.search(i["title"]) and not SPAM2.search(i["title"]) and not TEAMPAGE.search(i["title"]) and not offtopic(i["title"])]
    print(f"filtered {before - len(items)} promo/betting items", file=sys.stderr)
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

    def short_pick(c, maxlen):
        cand = [i for i in c["items"] if 28 <= len(clean_title(i["title"], 400)) <= maxlen and len(i["title"].split()) >= 4 and not (maxlen <= 62 and re.search(r"\b\d{1,3}-\d{1,3}\b", i["title"]))]
        return sorted(cand, key=lambda i: (-i["w"], len(i["title"])))[0] if cand else None

    nh = cfg.get("headline_lines", 2)
    lead_n, lead_w = cfg.get("lead_min_sources", 3), cfg.get("lead_min_weight", 1.0)

    def choose(strict):
        top, topleft, used = [], [], set()
        for c in clusters:
            if c["sport"] == "media": continue
            trusted = c["n"] >= lead_n and max(i["w"] for i in c["items"]) >= lead_w
            if len(top) < nh and (trusted or not strict):
                p = short_pick(c, 62)
                if p:
                    c["rep"] = p; top.append(mk(c, 62)); used.add(id(c)); continue
            if len(topleft) < 4 and (c["n"] >= 2 or not strict):
                p = short_pick(c, 95)
                if p:
                    c["rep"] = p; topleft.append(mk(c, 95)); used.add(id(c))
            if len(top) >= nh and len(topleft) >= 4: break
        return top, topleft, used

    top, topleft, used = choose(True)
    if len(top) < nh or len(topleft) < 4:
        top, topleft, used = choose(False)
    for t in top: t["text"] = t["text"].upper()
    for t in topleft: t["text"] = t["text"].upper() + "..."
    rest = [c for c in clusters if id(c) not in used]
    mcl = [c for c in rest if c["sport"] == "media"][: cfg.get("media_items", 8)]
    mused = {id(c) for c in mcl}
    rest = [c for c in rest if id(c) not in mused]
    media = []
    for c in mcl:
        m = mk(c); m["text"] += "..."; media.append(m)

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
        if "other" in g:
            rk = {id(x): n for n, x in enumerate(rest)}
            have = {id(x) for x in col}
            seen_n = {niche(x) for x in col}
            wmin, wslots = cfg.get("wild_min_sources", 2), cfg.get("wild_slots", 6)
            extra = []
            for x in rest:
                if x["sport"] != "other" or id(x) in have or x["n"] < wmin: continue
                nk = niche(x)
                if nk and nk not in seen_n:
                    extra.append(x); seen_n.add(nk)
                if len(extra) >= wslots: break
            if extra:
                col = sorted(col[: max(0, per - len(extra))] + extra, key=lambda x: rk[id(x)])
        items_ = []
        for k, c in enumerate(col):
            m = mk(c); m["text"] += "..."
            if c["n"] >= cfg.get("hot_sources", 5): m["hot"] = True; m["text"] = m["text"].upper()
            items_.append(m)
        cols.append(items_)
    lead = top[0] if top else {"link": "#"}
    lead_img = pick_lead_image(cfg, lead)
    page = render(cfg, cols, lead, top, topleft, {"ok": ok, "total": len(report), "clusters": len(clusters)}, fetched, lead_img, media)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(page)
    print(f"wrote {out} ({len(page)//1024} KB)", file=sys.stderr)

if __name__ == "__main__":
    main()
