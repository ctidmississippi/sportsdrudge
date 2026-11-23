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
    if (t.state === "pre") return {rank: 2, live: false, text: name(a) + " at " + name(h) + " (" + detail + ")"};
    var score = name(a) + " " + a.score + ", " + name(h) + " " + h.score;
    if (t.state === "in") return {rank: 0, live: true, text: score + " (" + detail + ")"};
    return {rank: 1, live: false, text: score + " (" + (t.completed ? "FINAL" : detail) + ")"};
  }
  function load() {
    Promise.all(LEAGUES.map(function (l) {
      return fetch(BASE + l[0] + "/scoreboard").then(function (r) { return r.json(); }).then(function (j) {
        var items = (j.events || []).map(one).filter(Boolean);
        items.sort(function (x, y) { return x.rank - y.rank; });
        return {label: l[1], items: items};
      }).catch(function () { return {label: l[1], items: []}; });
    })).then(function (groups) {
      var html = "", n = 0;
      groups.forEach(function (g) {
        if (!g.items.length) return;
        html += '<span class="lg">' + esc(g.label) + "</span>";
        g.items.forEach(function (it) {
          n++;
          html += '<span class="' + (it.live ? "live" : "") + '">' + esc(it.text) + "</span> &nbsp;|&nbsp; ";
        });
      });
      if (!n) { el.style.display = "none"; return; }
      el.style.display = "block";
      el.innerHTML = '<div class="track">' + html + "</div>";
      var tr = el.firstChild;
      tr.style.animationDuration = Math.max(40, Math.round(html.length / 18)) + "s";
    });
  }
  load();
  setInterval(load, 60000);
})();
