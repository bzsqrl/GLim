"""Write USER_MANUAL.html (for the package) from USER_MANUAL.md: one
self-contained page, with a table of contents, that follows the system's
light or dark mode and prints cleanly.

Usage: venv\\Scripts\\python tools\\build_manual.py [OUT_DIR]   (default: dist)
compile.py runs it after each build. Needs the markdown package
(requirements.txt)."""
import html
import os
import re
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glim import __version__                                     # noqa: E402

ITEM = re.compile(r" *([-*] |\d+\. )")
LIST_ITEM = re.compile(r"^( +)(?=[-*] |\d+\. )")        # a nested one

CSS = """
:root {
  --bg: #ffffff; --panel: #f4f5f8; --fg: #1d2129; --dim: #5d6675; --line: #dde1e8;
  --accent: #4b4bc4; --code-bg: #eef0f4;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0f1217; --panel: #171b22; --fg: #e6e9ef; --dim: #8b95a5; --line: #2a313c;
    --accent: #8f8ff0; --code-bg: #1c2129;
  }
}
:root[data-theme="dark"] {
  --bg: #0f1217; --panel: #171b22; --fg: #e6e9ef; --dim: #8b95a5; --line: #2a313c;
  --accent: #8f8ff0; --code-bg: #1c2129;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 "Segoe UI Variable Text", "Segoe UI", -apple-system, BlinkMacSystemFont,
        "Helvetica Neue", Arial, sans-serif;
}
.page { display: flex; max-width: 1180px; margin: 0 auto; }
nav {
  position: sticky; top: 0; align-self: flex-start; width: 250px; flex: none;
  max-height: 100vh; overflow-y: auto; padding: 32px 16px 32px 24px; font-size: 14px;
}
nav .title { font-weight: 650; font-size: 15px; margin-bottom: 2px; }
nav .version { color: var(--dim); font-size: 13px; margin-bottom: 16px; }
nav ul { list-style: none; margin: 0; padding: 0; }
nav li { margin: 0; }
nav a { display: block; padding: 3px 8px; border-radius: 6px; color: var(--dim); text-decoration: none; }
nav a:hover { background: var(--panel); color: var(--fg); }
main { flex: 1; min-width: 0; padding: 32px 32px 80px; }
h1 { font-size: 30px; line-height: 1.25; margin: 0 0 4px; }
.subtitle { color: var(--dim); margin: 0 0 24px; }
h2 { font-size: 22px; margin: 44px 0 10px; padding-top: 16px; border-top: 1px solid var(--line); }
h3 { font-size: 18px; margin: 28px 0 8px; }
h4 { font-size: 16px; margin: 22px 0 6px; }
h2, h3, h4 { scroll-margin-top: 16px; }
hr { display: none; }                       /* the sections' own rules separate them */
a { color: var(--accent); }
ul, ol { padding-left: 24px; }
li { margin: 3px 0; }
li > ul, li > ol { margin: 4px 0; }
code {
  font: 0.88em/1.4 "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace;
  background: var(--code-bg); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere;
}
pre { background: var(--code-bg); padding: 12px 14px; border-radius: 8px; overflow-x: auto; }
pre code { background: none; padding: 0; overflow-wrap: normal; }
.table-wrap { overflow-x: auto; margin: 12px 0; }
table { border-collapse: collapse; font-size: 15px; }
th, td { text-align: left; vertical-align: top; padding: 7px 12px; border-bottom: 1px solid var(--line); }
th { color: var(--dim); font-weight: 600; }
thead tr:only-child th:empty { display: none; }
@media (max-width: 860px) {
  .page { display: block; }
  nav { position: static; width: auto; max-height: none; padding: 20px 16px 0; }
  nav ul { columns: 2; column-gap: 16px; }
  main { padding: 16px 16px 60px; }
}
@media print {
  nav { display: none; }
  main { padding: 0; }
  body { background: #fff; color: #000; font-size: 11pt; }
  a { color: inherit; }
  h2 { break-after: avoid; }
}
"""


def github_lists(md):
    """Lists as GitHub reads them, for Python-Markdown: nested items are
    indented by 2 spaces in the manual (Python-Markdown needs 4), and a list
    may follow a paragraph line directly (Python-Markdown needs a blank line)."""
    out = []
    for line in md.split("\n"):
        prev = out[-1] if out else ""
        if ITEM.match(line) and prev.strip() and not ITEM.match(prev) and not prev.startswith(("|", "#", "```")):
            out.append("")
        out.append(LIST_ITEM.sub(lambda m: m.group(1) * 2, line))
    return "\n".join(out)


def main(out_dir):
    with open(os.path.join(ROOT, "USER_MANUAL.md"), encoding="utf-8") as f:
        md = f.read().replace("\r\n", "\n")
    title_line, _, rest = md.partition("\n")
    title = title_line.lstrip("# ").strip()
    conv = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                             extension_configs={"toc": {"toc_depth": "2-2"}})
    body = conv.convert(github_lists(rest))
    body = re.sub(r"<table>(.*?)</table>", r'<div class="table-wrap"><table>\1</table></div>', body, flags=re.S)
    body = re.sub(r'<a href="(https?://[^"]+)">', r'<a href="\1" target="_blank" rel="noopener">', body)
    toc = "".join(f'<li><a href="#{t["id"]}">{html.escape(t["name"], quote=False)}</a></li>'
                  for t in conv.toc_tokens)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">
<nav aria-label="Contents">
<div class="title">GLim</div>
<div class="version">Version {html.escape(__version__)}</div>
<ul>{toc}</ul>
</nav>
<main>
<h1>{html.escape(title)}</h1>
<p class="subtitle">For GLim {html.escape(__version__)}</p>
{body}
</main>
</div>
</body>
</html>
"""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "USER_MANUAL.html")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"wrote {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist"))
