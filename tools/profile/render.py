"""Render data/stats.json into SVG slices under assets/. Same data -> byte-identical output.

The README is one tall terminal window cut into slices (one <img> each, so cards
can be links). Brand: lucasbittar.dev (src/css/styles.css in lucasbittar/personal-site).
"""

import base64
import io
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
FONTS = Path(__file__).parent / "fonts"
STATS = Path(__file__).parent / "data" / "stats.json"

# Brand tokens from lucasbittar.dev
BG, TERM, BAR, BORDER = "#020202", "#0a0a0a", "#151515", "#2a2a2a"
PRIMARY, MUTED, DIM = "#d0d0d0", "#8a8a8a", "#4a4a4a"
ACCENT, GREEN, AMBER, RED, WHITE = "#9c479b", "#4ade80", "#fbbf24", "#ef4444", "#ffffff"

W = 840          # page width
WX0, WX1 = 16, 824  # terminal window edges
PAD = 44         # text inset
FONT_FILES = {"r": "JetBrainsMonoNL-Regular.ttf", "b": "JetBrainsMonoNL-Bold.ttf"}

# ---------------------------------------------------------------- content
# Every line here is on the resume or the site. Keep them in sync.

LINKS = [  # (file, label, url)
    ("link-site", "open --site", "https://lucasbittar.dev"),
    ("link-linkedin", "open --linkedin", "https://www.linkedin.com/in/lucasbittar"),
    ("link-resume", "open --resume", "https://lucasbittar.dev/resume.pdf"),
    ("link-writing", "open --writing", "https://substack.com/@lucasbittar"),
]

ABOUT_LEAD = "I build full-stack web apps that hold up when real people show up."
ABOUT = [  # (key, value, color)
    ("now", "Full-stack engineer at Index Risk (via Toptal): React and TypeScript on the "
            "product, Go and PostgreSQL APIs built with AI coding agents, every change reviewed by me.", PRIMARY),
    ("before", "10 years as a Toptal engineer (top 3%) for Gartner, Zobrist (The North Face, "
               "VANS, Timberland) and others.", PRIMARY),
    ("learning", "Go, data structures and system design.", PRIMARY),
    ("open to", "Full-stack Engineer · Senior Frontend Engineer · Product Engineer (remote)", GREEN),
]

PROJECTS = [  # (name, kind, description, outcome, stack, url)
    ("pv7", "live", "Official album-rollout site for Pabllo Vittar: 5 campaign phases "
                    "switched live from an admin panel, no redeploy.",
     "~20,000 visitors on launch day", "Next.js · TypeScript · Supabase · Redis",
     "https://pabllovittar.digital"),
    ("carta-de-adeus", "code", "Fan tribute to Fresno: letters pinned on a 3D globe, locations "
                               "coarsened to ~1 km for LGPD, rate-limited API.",
     "~22,000 visitors, API cached at the CDN", "Next.js · React Three Fiber · Supabase",
     "https://github.com/lucasbittar/cartadeadeus"),
    ("myscrobble", "code", "Spotify listening dashboard with Gemini AI concert discovery and "
                           "server-rendered share cards.",
     "Waitlist inside Spotify's 25-user cap", "Next.js · TypeScript · Gemini API",
     "https://github.com/lucasbittar/myscrobble"),
    ("weather-terminal", "code", "CRT-style weather app with Gemini AI suggestions, moved from "
                                 "Webpack to Vite.",
     "Tests + CI gate every deploy", "React · TypeScript · Vitest · GitHub Actions",
     "https://github.com/lucasbittar/weatherapp"),
]

STACK = [
    ("languages", "TypeScript, JavaScript, SQL, HTML, CSS, Go (growing)"),
    ("frontend", "React, Next.js, TanStack Query, Zod, Tailwind CSS, shadcn/ui, Vite, Vitest"),
    ("backend", "PostgreSQL, REST and OpenAPI, Server-Sent Events, Node.js, Supabase, Redis"),
    ("delivery", "AWS (S3), GitHub Actions, Docker, Vercel, Google Cloud"),
    ("practices", "Design docs and ERDs, AI coding agents (Claude Code, Cursor), code review"),
]

SETUP = "Ghostty · tmux · Neovim · zsh · fzf · gh · Claude Code"
SETUP_URL = "https://github.com/lucasbittar/dotfiles"

ASCII = """\
██╗     ██╗   ██╗ ██████╗ █████╗ ███████╗
██║     ██║   ██║██╔════╝██╔══██╗██╔════╝
██║     ██║   ██║██║     ███████║███████╗
██║     ██║   ██║██║     ██╔══██║╚════██║
███████╗╚██████╔╝╚██████╗██║  ██║███████║
╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝
██████╗ ██╗████████╗████████╗ █████╗ ██████╗
██╔══██╗██║╚══██╔══╝╚══██╔══╝██╔══██╗██╔══██╗
██████╔╝██║   ██║      ██║   ███████║██████╔╝
██╔══██╗██║   ██║      ██║   ██╔══██║██╔══██╗
██████╔╝██║   ██║      ██║   ██║  ██║██║  ██║
╚═════╝ ╚═╝   ╚═╝      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝""".splitlines()

# ---------------------------------------------------------------- text helpers


def width(s, size):
    """JetBrains Mono is monospaced: every glyph advances 600/1000 em."""
    return len(s) * size * 0.6


def wrap(s, size, w, max_lines=4):
    per = max(1, int(w // (size * 0.6)))
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if len(trial) <= per:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: per - 3].rstrip(" .,;:") + "..."
    return lines


def text(x, y, s, size, fill=PRIMARY, bold=False, extra=""):
    cls = "b" if bold else "r"
    return f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size:g}" fill="{fill}"{extra}>{escape(s)}</text>'


def prompt(x, y, cmd, size=15):
    """`$ cmd` the way the site prints it: green prompt, amber command."""
    return text(x, y, "$", size, GREEN, True) + text(x + width("$ ", size), y, cmd, size, AMBER)


TEXT_RE = re.compile(r'<text[^>]*class="([rb])"[^>]*>(.*?)</text>')


def font_face(cls, chars):
    f = TTFont(FONTS / FONT_FILES[cls], recalcTimestamp=False)
    cmap = f.getBestCmap()
    missing = {c for c in chars if ord(c) not in cmap}
    assert not missing, f"font lacks glyphs: {''.join(sorted(missing))!r}"
    opts = Options()
    opts.flavor = "woff2"
    opts.drop_tables += ["FFTM"]
    opts.layout_features = []  # no ligatures: a terminal shows what you typed
    sub = Subsetter(opts)
    sub.populate(text=chars)
    sub.subset(f)
    buf = io.BytesIO()
    f.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:jbm-{cls};src:url(data:font/woff2;base64,{b64})}}"
            f".{cls}{{font-family:jbm-{cls},monospace;white-space:pre}}")


# ---------------------------------------------------------------- the slice


def slice_svg(h, body, css="", w=W, left=True, right=True, top=False, bottom=False):
    """One piece of the terminal window. Only the header draws the title bar and only
    the footer draws the rounded bottom. Half-width pieces draw only their own side."""
    used = {}
    for cls, s in TEXT_RE.findall(body):
        s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        used[cls] = used.get(cls, "") + s
    faces = "".join(font_face(c, "".join(sorted(set(t)))) for c, t in sorted(used.items()))
    x0 = WX0 + 0.5 if left else -1
    x1 = (w - (W - WX1)) - 0.5 if right else w + 1
    y0 = WX0 + 0.5 if top else -1
    y1 = h - WX0 - 0.5 if bottom else h + 1
    r = 12
    if top:
        win = f"M{x0} {y1}V{y0 + r}q0-{r} {r}-{r}H{x1 - r}q{r} 0 {r} {r}V{y1}"
    elif bottom:
        win = f"M{x0} {y0}V{y1 - r}q0 {r} {r} {r}H{x1 - r}q{r} 0 {r}-{r}V{y0}"
    else:
        win = f"M{x0} {y0}V{y1}M{x1} {y0}V{y1}"
    fill = (f"M{x0} {y1}V{y0 + r}q0-{r} {r}-{r}H{x1 - r}q{r} 0 {r} {r}V{y1}z" if top else
            f"M{x0} {y0}V{y1 - r}q0 {r} {r} {r}H{x1 - r}q{r} 0 {r}-{r}V{y0}z" if bottom else
            f"M{x0} {y0}H{x1}V{y1}H{x0}z")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>{faces}
.glow{{filter:url(#glow)}}
{css}</style>
<defs>
<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="{WHITE}" fill-opacity=".03"/></pattern>
<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="{w}" height="{h}" fill="{BG}"/>
<path d="{fill}" fill="{TERM}"/>
<path d="{win}" fill="none" stroke="{BORDER}"/>
{body}
<rect width="{w}" height="{h}" fill="url(#scan)"/>
</svg>
"""


# ---------------------------------------------------------------- pieces


def header():
    h = 340
    css = ""
    # title bar
    bar_y0, bar_y1, r = WX0 + 0.5, 56, 12
    x0, x1 = WX0 + 0.5, WX1 - 0.5
    body = (f'<path d="M{x0} {bar_y1}V{bar_y0 + r}q0-{r} {r}-{r}H{x1 - r}q{r} 0 {r} {r}V{bar_y1}z" fill="{BAR}"/>'
            f'<path d="M{x0} {bar_y1 + .5}H{x1}" stroke="{BORDER}"/>')
    for i, c in enumerate((RED, AMBER, GREEN)):
        body += f'<circle cx="{40 + i * 20}" cy="36" r="6" fill="{c}"/>'
    body += text(W / 2, 41, "lucas@github:~", 13, MUTED, extra=' text-anchor="middle"')
    body += f'<circle class="pulse" cx="{WX1 - 132}" cy="36.5" r="4" fill="{GREEN}"/>'
    body += text(WX1 - 120, 41, "open to roles", 13, GREEN)
    css += f".pulse{{animation:pulse 2s ease-in-out infinite}}@keyframes pulse{{50%{{opacity:.35}}}}"

    # `$ whoami`, typed out
    y, size = 96, 15
    body += text(PAD, y, "$", size, GREEN, True)
    cmd, start, step = "whoami", 0.4, 0.12
    cx = PAD + width("$ ", size)
    for i, ch in enumerate(cmd):
        body += text(cx + width(cmd[:i], size), y, ch, size, AMBER,
                     extra=f' style="opacity:0;animation:on .01s {start + i * step:.2f}s forwards"')
    css += "@keyframes on{to{opacity:1}}"
    n = len(cmd)
    frames = "".join(f"{i / n * 100:.1f}%{{transform:translateX({width(cmd[:i], size):.1f}px)}}" for i in range(n + 1))
    css += (f".cursor{{animation:type {n * step:.2f}s steps(1,end) {start}s forwards,blink 1s steps(1,end) {start + n * step:.2f}s infinite}}"
            f"@keyframes type{{{frames}}}@keyframes blink{{50%{{opacity:0}}}}")
    body += f'<rect class="cursor" x="{cx:.1f}" y="{y - 13}" width="9" height="17" fill="{GREEN}"/>'

    # ASCII name, glowing like the site's hero
    asz, lh = 10.4, 11.2
    art = "".join(text(PAD, 128 + i * lh, line, asz, ACCENT) for i, line in enumerate(ASCII))
    body += f'<g class="glow">{art}</g>'

    # right column
    rx = 400
    body += text(rx, 150, "Full-stack", 30, WHITE, True)
    body += text(rx, 188, "software engineer", 30, WHITE, True)
    body += text(rx, 224, "React · TypeScript · Go · PostgreSQL", 16, PRIMARY)
    body += text(rx, 250, "10+ years · Campinas, BR · remote", 14, MUTED)
    badge = "◆ TOP 3% ON TOPTAL"
    bw = width(badge, 13) + 28
    body += (f'<rect x="{rx + .5}" y="270.5" width="{bw:.0f}" height="30" rx="4" fill="{ACCENT}" fill-opacity=".08" stroke="{ACCENT}"/>'
             + text(rx + 14, 290, badge, 13, ACCENT, extra=' letter-spacing=".5"'))
    return slice_svg(h, body, css, top=True)


def links():
    """4 equal 210px cells (each img is width=25%, so the row scales as one).
    Buttons are 160px with even 40px gaps between x=40 and x=800."""
    cell, bw, gap, edge = W // len(LINKS), 160, 40, 40
    out = {}
    for i, (name, label, _) in enumerate(LINKS):
        x = edge + i * (bw + gap) - i * cell
        assert 0 <= x and x + bw <= cell
        body = (f'<rect x="{x + .5}" y="14.5" width="{bw}" height="36" rx="4" fill="{ACCENT}" fill-opacity=".1" stroke="{ACCENT}"/>'
                + text(x + 16, 37, "▸", 13, ACCENT, True)
                + text(x + 16 + width("▸ ", 13), 37, label, 13, WHITE))
        out[f"{name}.svg"] = slice_svg(64, body, w=cell, left=i == 0, right=i == len(LINKS) - 1)
    return out


def about():
    body = prompt(PAD, 40, "cat about.txt")
    body += text(PAD, 76, ABOUT_LEAD, 16, WHITE, True)
    y, kx, vx = 110, PAD, PAD + 100
    for key, value, color in ABOUT:
        body += text(kx, y, key, 14, MUTED)
        for line in wrap(value, 14, WX1 - 28 - vx):
            body += text(vx, y, line, 14, color)
            y += 21
        y += 7
    return slice_svg(math.ceil((y + 4) / 8) * 8, body)


def data_end(stats):
    """The last day in the data stands in for 'today', so output never depends on the clock."""
    return date.fromisoformat(max(stats["contributions"]))


def stats_panel(stats):
    end = data_end(stats)
    created = date.fromisoformat(stats["created_at"][:10])
    years = end.year - created.year - ((end.month, end.day) < (created.month, created.day))
    tiles = [
        (f"{years}", "years on", "github"),
        (f"{stats['public_repos']:,}", "public", "repos"),
        (f"{stats['prs_merged']:,}", "public PRs", "merged"),
        (f"{stats['contributions_last_year']:,}", "contributions", "last 12 months"),
        (f"{stats['streak_current']:,}d", "current", "streak"),
        (f"{stats['streak_longest']:,}d", "longest", "streak"),
    ]
    body = prompt(PAD, 40, f"gh stats --user {stats['login']}")
    n, gap = len(tiles), 12
    tw = (W - 2 * PAD - (n - 1) * gap) / n
    for i, (value, l1, l2) in enumerate(tiles):
        x = PAD + i * (tw + gap)
        body += (f'<rect x="{x + .5:.1f}" y="62.5" width="{tw - 1:.1f}" height="92" rx="4" fill="{WHITE}" fill-opacity=".02" stroke="{BORDER}"/>'
                 f'<rect x="{x + 1:.1f}" y="63" width="{tw - 2:.1f}" height="2" fill="{ACCENT}"/>')
        body += f'<g class="glow">{text(x + 14, 104, value, 26, GREEN, True)}</g>'
        body += text(x + 14, 126, l1, 11, MUTED)
        body += text(x + 14, 141, l2, 11, MUTED)
    return slice_svg(176, body)


def activity(stats):
    """cava, the terminal audio visualizer, playing your last 53 weeks of commits."""
    days = stats["contributions"]
    end = data_end(stats)
    first = end - timedelta(days=(end.weekday() + 1) % 7) - timedelta(weeks=52)  # a Sunday, 53 weeks back
    weeks = []
    for wk in range(53):
        start = first + timedelta(weeks=wk)
        total = sum(days.get((start + timedelta(days=d)).isoformat(), 0) for d in range(7) if start + timedelta(days=d) <= end)
        weeks.append((start, total))
    total = sum(t for _, t in weeks)
    top = max((t for _, t in weeks), default=1) or 1

    segs, seg_h, seg_gap = 20, 5, 2
    pitch = seg_h + seg_gap
    base = 92 + segs * pitch
    area = W - 2 * PAD
    col = area / 53
    bw = col - 4
    bars, ghosts, labels = [], [], []
    for i, (start, t) in enumerate(weeks):
        x = PAD + i * col + 2
        lit = 0 if not t else max(1, math.ceil(segs * math.sqrt(t / top)))
        g = []
        for s in range(segs):
            y = base - (s + 1) * pitch + seg_gap
            if s < lit:
                color = GREEN if s == lit - 1 else (ACCENT if s >= segs * 0.35 else "#6b2f6a")
                g.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="{seg_h}" fill="{color}"/>')
            else:
                ghosts.append(f"M{x:.1f} {y}h{bw:.1f}v{seg_h}h{-bw:.1f}z")
        if g:
            bars.append(f'<g class="bar" style="animation-delay:{i * 0.02:.2f}s">{"".join(g)}</g>')
        # month label on the first week that starts a month
        if start.day <= 7:
            labels.append(text(x, base + 20, start.strftime("%b").lower(), 11, MUTED))
    css = (".bar{transform-box:fill-box;transform-origin:50% 100%;animation:rise .9s cubic-bezier(.2,.8,.2,1) both}"
           "@keyframes rise{from{transform:scaleY(0)}to{transform:scaleY(1)}}")
    body = prompt(PAD, 40, "cava --input=contributions")
    body += text(PAD, 64, f"last 53 weeks · {total:,} contributions · one bar per week", 12, MUTED)
    body += f'<path d="{"".join(ghosts)}" fill="{WHITE}" fill-opacity=".035"/>'
    body += f'<g class="glow">{"".join(bars)}</g>'
    body += "".join(labels)
    return slice_svg(base + 40, body, css)


def section(cmd):
    return slice_svg(56, prompt(PAD, 40, cmd))


def project_card(name, kind, desc, outcome, stack, side):
    """Half-width card. Panels mirror around the page center (x=40..412 | 428..800)."""
    px, pw = (40, 372) if side == "left" else (8, 372)
    body = (f'<rect x="{px + .5}" y="10.5" width="{pw - 1}" height="168" rx="6" fill="{WHITE}" fill-opacity=".02" stroke="{BORDER}"/>'
            f'<rect x="{px + 1}" y="11" width="3" height="167" fill="{ACCENT}"/>')
    ix = px + 20
    body += text(ix, 40, f"{name}/", 17, WHITE, True)
    tag = f"{kind} ↗"
    body += text(px + pw - 18, 40, tag, 12, ACCENT, extra=' text-anchor="end"')
    for i, line in enumerate(wrap(desc, 12.5, pw - 40, 3)):
        body += text(ix, 66 + i * 18, line, 12.5, PRIMARY)
    assert width("✓ " + outcome, 12.5) <= pw - 40, outcome
    body += text(ix, 132, "✓ " + outcome, 12.5, GREEN)
    body += f'<path d="M{ix} 146.5H{px + pw - 20}" stroke="{BORDER}"/>'
    body += text(ix, 166, stack.lower(), 11, MUTED)
    return slice_svg(188, body, w=W // 2, left=side == "left", right=side == "right")


def tech_stack():
    body = prompt(PAD, 40, "cat stack.txt")
    y, vx = 76, PAD + 110
    for key, value in STACK:
        body += text(PAD, y, key, 13, ACCENT, True)
        for line in wrap(value, 14, WX1 - 28 - vx):
            body += text(vx, y, line, 14, PRIMARY)
            y += 21
        y += 6
    return slice_svg(math.ceil((y + 2) / 8) * 8, body)


def setup():
    body = prompt(PAD, 40, "ls ~/.dotfiles")
    body += text(PAD, 70, "I live in the terminal:", 14, MUTED)
    body += text(PAD + width("I live in the terminal: ", 14), 70, SETUP, 14, PRIMARY)
    return slice_svg(96, body)


def footer():
    h = 136
    css = "@keyframes blink{50%{opacity:0}}.blink{animation:blink 1s steps(1,end) infinite}"
    body = prompt(PAD, 40, "exit")
    body += text(PAD, 66, "logout · thanks for reading. Say hi at lucasbittar.dev", 13, MUTED)
    body += text(PAD, 92, "$", 15, GREEN, True)
    body += f'<rect class="blink" x="{PAD + width("$ ", 15):.1f}" y="79" width="9" height="17" fill="{GREEN}"/>'
    return slice_svg(h, body, css, bottom=True)


def render(stats):
    """{filename: svg} for every slice."""
    out = {
        "header.svg": header(),
        "about.svg": about(),
        "stats.svg": stats_panel(stats),
        "activity.svg": activity(stats),
        "projects.svg": section("ls ~/projects"),
        "stack.svg": tech_stack(),
        "setup.svg": setup(),
        "footer.svg": footer(),
    }
    out.update(links())
    for i, (name, kind, desc, outcome, stack, _) in enumerate(PROJECTS):
        out[f"project-{i + 1}.svg"] = project_card(name, kind, desc, outcome, stack, ("left", "right")[i % 2])
    return out


def main():
    stats = json.loads(STATS.read_text())
    ASSETS.mkdir(exist_ok=True)
    for name, svg in render(stats).items():
        (ASSETS / name).write_text(svg)


if __name__ == "__main__":
    main()
