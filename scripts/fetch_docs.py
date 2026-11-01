import pathlib
import re

import requests

REPO_RAW = "https://raw.githubusercontent.com/fastapi/fastapi/master"
DOCS_RAW = f"{REPO_RAW}/docs/en/docs"
PAGES = {
    "first-steps.md": f"{DOCS_RAW}/tutorial/first-steps.md",
    "path-params.md": f"{DOCS_RAW}/tutorial/path-params.md",
    "query-params.md": f"{DOCS_RAW}/tutorial/query-params.md",
    "body.md": f"{DOCS_RAW}/tutorial/body.md",
    "handling-errors.md": f"{DOCS_RAW}/tutorial/handling-errors.md",
}

# Matches placeholders like: {* ../../docs_src/path_params/tutorial001.py hl[6] *}
# Group 1 captures just the "docs_src/....py" part.
INCLUDE = re.compile(r"\{\*\s*\S*?(docs_src/\S+?\.py)[^}]*?\*\}")

_code_cache: dict[str, str | None] = {}


def fetch_code(rel_path: str) -> str | None:
    """Download one example file (cached so each file is fetched once)."""
    if rel_path not in _code_cache:
        try:
            r = requests.get(f"{REPO_RAW}/{rel_path}", timeout=30)
            r.raise_for_status()
            _code_cache[rel_path] = r.text
        except requests.RequestException:
            _code_cache[rel_path] = None
    return _code_cache[rel_path]


def inline_code(match: re.Match) -> str:
    rel_path = match.group(1)
    code = fetch_code(rel_path)
    if code is None:
        print(f"    WARNING: could not fetch {rel_path}")
        return ""
    return f"```python\n{code.rstrip()}\n```"


out = pathlib.Path("data")
out.mkdir(exist_ok=True)

for name, url in PAGES.items():
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    text = r.text
    n_includes = len(INCLUDE.findall(text))
    text = INCLUDE.sub(inline_code, text)
    (out / name).write_text(text, encoding="utf-8")
    print(f"saved {name}: {n_includes} code examples inlined ({len(text)} chars)")