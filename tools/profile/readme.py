"""Rewrite only the content between <!-- terminal:start --> / <!-- terminal:end --> in README.md."""

import sys
from html import escape

from render import ABOUT, ABOUT_LEAD, LINKS, PROJECTS, ROOT, SETUP, SETUP_URL, STACK, STATS

README = ROOT / "README.md"


def img(name, alt, width="100%"):
    # Percent widths: every piece scales by the same factor when the column is narrower than 840px.
    return f'<img src="./assets/{name}.svg" alt="{escape(alt)}" width="{width}" align="top">'


def linked(url, image):
    return f'<a href="{url}">{image}</a>' if url else image


def terminal(stats):
    about = ABOUT_LEAD + " " + " ".join(f"{k.capitalize()}: {v}" for k, v, _ in ABOUT)
    cards = [linked(url, img(f"project-{i + 1}", f"{name}: {desc} {outcome}. {stack}.", "50%"))
             for i, (name, _, desc, outcome, stack, url) in enumerate(PROJECTS)]
    rows = ["".join(cards[i:i + 2]) for i in range(0, len(cards), 2)]  # must touch: whitespace shows as a gap
    return "\n".join([
        '<div align="center">',
        img("header", "Lucas Bittar: full-stack software engineer. React, TypeScript, Go, PostgreSQL. "
                      "10+ years, Campinas, Brazil, remote. Top 3% on Toptal. Open to roles."),
        "".join(linked(url, img(name, label.replace("open --", "").upper(), "25%")) for name, label, url in LINKS),
        img("about", about),
        img("stats", f"GitHub stats: {stats['prs_merged']:,} public pull requests merged, "
                     f"{stats['contributions_last_year']:,} contributions in the last 12 months"),
        img("activity", "Contribution activity for the last 53 weeks, one bar per week"),
        img("projects", "Projects"),
        *rows,
        img("stack", "Stack: " + "; ".join(f"{k}: {v}" for k, v in STACK)),
        linked(SETUP_URL, img("setup", f"Setup: {SETUP}")),
        img("footer", "Thanks for reading. Say hi at lucasbittar.dev"),
        "</div>",
    ])


def replace_zone(text, name, content):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        sys.exit(f"README.md must contain exactly one {start} and one {end}")
    head, rest = text.split(start)
    _, tail = rest.split(end)
    return f"{head}{start}\n{content}\n{end}{tail}"


def main():
    import json
    stats = json.loads(STATS.read_text())
    README.write_text(replace_zone(README.read_text(), "terminal", terminal(stats)))


if __name__ == "__main__":
    main()
