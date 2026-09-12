"""Render the payload into one self-contained HTML file.

Ported from ``02-Maintain/portfolio-dashboard/portfolio_dashboard/render.py``.
CSS, JavaScript and the data are all inlined so the page opens from a ``file://``
URL with no server and no fetches of its own - which is also what lets the
refresh job and the page be completely decoupled.

The one external dependency is the map tile layer, loaded lazily and only when
the map scrolls into view. That is deliberate and it is why this page targets
GitHub Pages rather than a Claude Artifact: the Artifact CSP blocks tile
requests silently.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent / "templates"


def render(data: dict, out: Path) -> Path:
    """Write the page to ``out`` and return the path."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(default=False),
    )
    template = env.get_template("page.html.j2")

    html = template.render(
        styles=(TEMPLATES / "styles.css").read_text(encoding="utf-8"),
        app=(TEMPLATES / "app.js").read_text(encoding="utf-8"),
        payload=_embed(data),
        generated=data["meta"]["generated"].replace("T", " "),
    )

    out.write_text(html, encoding="utf-8")
    return out


def _embed(data: dict) -> str:
    """Serialise the payload for inlining inside a <script> block.

    ``</script>`` anywhere in the data would close the block early, and ``<!--``
    opens an HTML comment inside it. Both are escaped at the JSON level, which
    leaves the parsed values identical. Headlines are user-supplied text from
    third-party feeds, so this is load-bearing, not theoretical.
    """
    text = json.dumps(data, separators=(",", ":"), allow_nan=False, default=str)
    return text.replace("<\\/", "<\\\\/").replace("</", "<\\/").replace("<!--", "\\u003c!--")
