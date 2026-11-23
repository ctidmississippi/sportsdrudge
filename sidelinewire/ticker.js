(function () {
  var el = document.getElementById("ticker");
  if (!el) return;
  var LEAGUES = [
    ["football/nfl", "NFL"], ["basketball/nba", "NBA"], ["hockey/nhl", "NHL"],
    ["football/college-football", "CFB"], ["basketball/mens-college-basketball", "CBB"],
    ["baseball/mlb", "MLB"], ["soccer/eng.1", "EPL"], ["soccer/usa.1", "MLS"]
  ];
  var BASE = "https://site.api.espn.com/apis/site/v2/sports/";
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function name(x) { return (x.team && (x.team.abbreviation || x.team.shortDisplayName)) || "?"; }
  function one(ev) {
    var c = ev.competitions && ev.competitions[0];
    if (!c) return null;
    var t = (ev.status && ev.status.type) || {};
    var h, a;
    (c.competitors || []).forEach(function (x) { if (x.homeAway === "home") h = x; else a = x; });
    if (!h || !a) return null;
    var detail = t.shortDetail || "";
    if (t.state === "pre") { var d = new Date(ev.date), when = isNaN(d) ? detail : d.toLocaleString([], {weekday: "short", hour: "numeric", minute: "2-digit"}); return {kind: "next", text: name(a) + " at " + name(h) + " (" + when + ")"}; }
    var score = name(a) + " " + a.score + ", " + name(h) + " " + h.score;
    if (t.state === "in") return {kind: "live", text: score + " (" + detail + ")"};
    return {kind: "final", text: score + " (" + (t.completed ? "FINAL" : detail) + ")"};
  }
  function row(groups, kinds, badge, cls) {
    var html = "", n = 0;
    groups.forEach(function (g) {
      var items = [];
      kinds.forEach(function (k) { g.items.forEach(function (it) { if (it.kind === k) items.push(it); }); });
      if (!items.length) return;
      html += '<span class="lg">' + esc(g.label) + "</span>";
      items.forEach(function (it) {
        n++;
        html += '<span class="' + (it.kind === "live" ? "live" : "") + '">' + esc(it.text) + "</span> &nbsp;|&nbsp; ";
      });
    });
    if (!n) return "";
    var dur = Math.max(40, Math.round(html.length / 18));
    return '<div class="row ' + cls + '"><span class="badge">' + badge + '</span><div class="win"><div class="track" style="animation-duration:' + dur + 's">' + html + "</div></div></div>";
  }
  function load() {
    Promise.all(LEAGUES.map(function (l) {
      return fetch(BASE + l[0] + "/scoreboard").then(function (r) { return r.json(); }).then(function (j) {
        return {label: l[1], items: (j.events || []).map(one).filter(Boolean)};
      }).catch(function () { return {label: l[1], items: []}; });
    })).then(function (groups) {
      var hasLive = groups.some(function (g) { return g.items.some(function (it) { return it.kind === "live"; }); });
      var html = (hasLive ? row(groups, ["live"], "LIVE", "livebar") : row(groups, ["next"], "NEXT", "livebar")) + row(groups, ["final"], "FINAL", "finalbar");
      if (!html) { el.style.display = "none"; return; }
      el.style.display = "block";
      el.innerHTML = html;
    });
  }
  load();
  setInterval(load, 60000);
})();
