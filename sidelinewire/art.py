"""Original, sport-matched illustrations used as the lead image when no
user-supplied photo matches the top story. Pure SVG, no external assets."""
import base64

W, H = 410, 273
BG = '<rect width="410" height="273" fill="#e9e6df"/>'
INK = "#222"

def _svg(body, bg=BG):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">{bg}{body}</svg>'

FOOTBALL = _svg(
    '<g stroke="#222" stroke-width="3" opacity=".22"><path d="M0 55H410M0 110H410M0 165H410M0 220H410"/></g>'
    '<g transform="rotate(-22 205 136)"><ellipse cx="205" cy="136" rx="125" ry="70" fill="#7a3b1e" stroke="#222" stroke-width="5"/>'
    '<path d="M80 136H330" stroke="#fff" stroke-width="4"/>'
    '<g stroke="#fff" stroke-width="4"><path d="M168 117v38M188 113v46M208 111v50M228 113v46M248 117v38"/></g>'
    '<path d="M118 98Q132 136 118 174M292 98Q278 136 292 174" stroke="#fff" stroke-width="7" fill="none"/></g>')

BASKETBALL = _svg(
    '<rect y="205" width="410" height="68" fill="#caa46a"/><path d="M0 205H410" stroke="#222" stroke-width="3"/>'
    '<circle cx="205" cy="125" r="98" fill="#d9702b" stroke="#222" stroke-width="5"/>'
    '<g stroke="#222" stroke-width="5" fill="none"><path d="M205 27V223M107 125H303"/>'
    '<path d="M137 56Q180 125 137 194M273 56Q230 125 273 194"/></g>')

BASEBALL = _svg(
    '<path d="M0 215Q205 175 410 215V273H0Z" fill="#8fae6b" opacity=".6"/>'
    '<circle cx="205" cy="128" r="100" fill="#fbfaf5" stroke="#222" stroke-width="5"/>'
    '<g stroke="#c00" stroke-width="4" fill="none"><path d="M138 60Q172 128 138 196M272 60Q238 128 272 196"/></g>'
    '<g stroke="#c00" stroke-width="3"><path d="M146 80l22 6M152 104l24 4M155 128h26M152 152l24-4M146 176l22-6"/>'
    '<path d="M264 80l-22 6M258 104l-24 4M255 128h-26M258 152l-24-4M264 176l-22-6"/></g>')

HOCKEY = _svg(
    '<rect width="410" height="273" fill="#dde7ee"/><circle cx="205" cy="136" r="70" fill="none" stroke="#2a5da8" stroke-width="3" opacity=".5"/>'
    '<path d="M205 0V273" stroke="#c00" stroke-width="4" opacity=".5"/>'
    '<ellipse cx="205" cy="168" rx="92" ry="30" fill="#111"/><rect x="113" y="128" width="184" height="40" fill="#111"/>'
    '<ellipse cx="205" cy="128" rx="92" ry="30" fill="#2b2b2b" stroke="#000" stroke-width="3"/>'
    '<path d="M40 230L190 150" stroke="#8a5a2b" stroke-width="12" stroke-linecap="round"/>', bg='')

SOCCER = _svg(
    '<path d="M0 205H410V273H0Z" fill="#6f9a5a" opacity=".55"/>'
    '<circle cx="205" cy="128" r="98" fill="#fff" stroke="#222" stroke-width="5"/>'
    '<polygon points="205,92 238,116 226,155 184,155 172,116" fill="#222"/>'
    '<g stroke="#222" stroke-width="4"><path d="M205 92V32M238 116L295 98M226 155L262 205M184 155L148 205M172 116L115 98"/></g>'
    '<g fill="#222"><polygon points="205,30 232,40 222,60 188,60 178,40"/><polygon points="296,96 318,122 300,140 280,122"/><polygon points="114,96 92,122 110,140 130,122"/></g>')

GOLF = _svg(
    '<path d="M0 190Q205 150 410 190V273H0Z" fill="#7fa866"/>'
    '<path d="M262 30V160" stroke="#222" stroke-width="5"/><path d="M262 30L330 56L262 82Z" fill="#c00"/>'
    '<circle cx="190" cy="168" r="42" fill="#fff" stroke="#222" stroke-width="4"/>'
    '<g fill="#bbb"><circle cx="176" cy="156" r="3"/><circle cx="194" cy="150" r="3"/><circle cx="208" cy="162" r="3"/><circle cx="182" cy="176" r="3"/><circle cx="200" cy="180" r="3"/><circle cx="168" cy="172" r="3"/></g>')

RACING = _svg(
    '<g fill="#222">' + ''.join(f'<rect x="{x}" y="{y}" width="41" height="41"/>' for y in range(0, 273, 41) for x in range(0, 410, 41) if ((x // 41) + (y // 41)) % 2 == 0) + '</g>'
    '<rect x="95" y="96" width="220" height="80" rx="10" fill="#c00" stroke="#fff" stroke-width="5"/>'
    '<text x="205" y="148" font-family="Impact,Arial Black,sans-serif" font-size="46" fill="#fff" text-anchor="middle">GO</text>', bg='')

STADIUM = _svg(
    '<path d="M0 205Q205 160 410 205V273H0Z" fill="#8fae6b" opacity=".6"/>'
    '<g stroke="#222" stroke-width="5"><path d="M70 40V205M340 40V205"/></g>'
    '<g fill="#fff" stroke="#222" stroke-width="4"><rect x="40" y="22" width="60" height="30"/><rect x="310" y="22" width="60" height="30"/></g>'
    '<g stroke="#f4c542" stroke-width="3" opacity=".7"><path d="M70 52L20 120M70 52L70 120M70 52L120 120M340 52L290 120M340 52L340 120M340 52L390 120"/></g>'
    '<path d="M110 205A95 95 0 0 1 300 205Z" fill="#d8d3c6" stroke="#222" stroke-width="4"/>')

ART = {"nfl": FOOTBALL, "cfb": FOOTBALL, "nba": BASKETBALL, "cbb": BASKETBALL, "mlb": BASEBALL,
       "nhl": HOCKEY, "soccer": SOCCER}

def pick(sport, text=""):
    t = (text or "").lower()
    if sport in ART: return ART[sport]
    if any(k in t for k in ("golf", "pga", "masters", "ryder")): return GOLF
    if any(k in t for k in ("f1", "formula", "nascar", "grand prix", "indycar", "racing", "verstappen")): return RACING
    return STADIUM

def data_uri(sport, text=""):
    svg = pick(sport, text)
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
