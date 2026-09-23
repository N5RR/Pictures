#!/usr/bin/env python3
"""
update_gallery.py

Regenerates index.html's hardcoded `files` array from whatever images
actually exist in the repo, so the picture gallery never needs manual
editing again.

How it works
------------
1. Scans the repo root for image files.
2. Looks up each file's category in categories.json.
3. Any file NOT already in categories.json gets a category guessed from
   its filename, and that guess is written into categories.json so you
   can correct it by hand later (edits you make persist across runs --
   this script only ever *adds* new files, it never overwrites an
   existing entry).
4. Removes categories.json entries for files that no longer exist.
5. Rewrites the `const files = [...]` block inside index.html.

Run it from the repo root:
    python3 scripts/update_gallery.py

Exits 0 with no changes if nothing needs updating.
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATEGORIES_PATH = REPO_ROOT / "categories.json"
INDEX_PATH = REPO_ROOT / "index.html"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Directories / files to never treat as gallery images.
EXCLUDE_DIRS = {".git", ".github", "scripts", "node_modules"}

VALID_CATEGORIES = {"ares", "license", "weather", "equipment", "other"}

# Keyword -> category. Checked against the lowercased filename.
# Order matters: first match wins.
KEYWORD_RULES = [
    ("ares", "ares"),
    ("license", "license"),
    ("fcc", "license"),
    ("extra", "license"),
    ("gentel", "license"),
    ("cswn", "weather"),
    ("nws", "weather"),
    ("skywarn", "weather"),
    ("weather", "weather"),
    ("radar", "weather"),
    ("goes", "weather"),
    ("hwo", "weather"),
    ("afd", "weather"),
    ("alert", "weather"),
    ("rainfall", "weather"),
    ("mesoscale", "weather"),
    ("equipment", "equipment"),
    ("mic", "equipment"),
    ("rj45", "equipment"),
    ("motorola", "equipment"),
    ("ft2500", "equipment"),
    ("hmn3000", "equipment"),
]


def guess_category(filename: str) -> str:
    lower = filename.lower()
    for keyword, category in KEYWORD_RULES:
        if keyword in lower:
            return category
    return "other"


def find_image_files() -> list[str]:
    found = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        found.append(path.relative_to(REPO_ROOT).as_posix())
    return found


def load_categories() -> dict:
    if CATEGORIES_PATH.exists():
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_categories(categories: dict) -> None:
    with open(CATEGORIES_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(categories.items(), key=lambda kv: kv[0].lower())),
                   f, indent=2, ensure_ascii=False)
        f.write("\n")


def build_files_js(categories: dict, image_files: list[str]) -> str:
    lines = ["        const files = ["]
    for name in sorted(image_files, key=str.lower):
        category = categories.get(name, "other")
        if category not in VALID_CATEGORIES:
            category = "other"
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"            {{ name: '{escaped}', type: '{category}' }},")
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("        ];")
    return "\n".join(lines)


def update_index_html(files_js: str) -> bool:
    html = INDEX_PATH.read_text(encoding="utf-8")

    # Replace the files array.
    pattern = re.compile(r"        const files = \[.*?\];", re.DOTALL)
    if not pattern.search(html):
        print("ERROR: could not find 'const files = [...]' block in index.html", file=sys.stderr)
        sys.exit(1)
    new_html = pattern.sub(files_js.replace("\\", "\\\\"), html, count=1)

    # Make sure baseUrl points at the current repo/branch.
    base_url_pattern = re.compile(r"const baseUrl = '.*?';")
    new_html = base_url_pattern.sub(
        "const baseUrl = 'https://raw.githubusercontent.com/N5RR/Pictures/main/';",
        new_html,
        count=1,
    )

    if new_html == html:
        return False

    INDEX_PATH.write_text(new_html, encoding="utf-8")
    return True


def main() -> None:
    categories = load_categories()
    image_files = find_image_files()
    image_file_set = set(image_files)

    added = []
    for name in image_files:
        if name not in categories:
            categories[name] = guess_category(name)
            added.append(name)

    removed = [name for name in list(categories.keys()) if name not in image_file_set]
    for name in removed:
        del categories[name]

    save_categories(categories)

    if added:
        print(f"Added {len(added)} new file(s) with guessed categories:")
        for name in added:
            print(f"  {name} -> {categories[name]}")
        print("Edit categories.json to correct any of these if needed.")

    if removed:
        print(f"Removed {len(removed)} file(s) no longer in the repo:")
        for name in removed:
            print(f"  {name}")

    files_js = build_files_js(categories, image_files)
    changed = update_index_html(files_js)

    if changed:
        print("index.html updated.")
    else:
        print("index.html already up to date.")


if __name__ == "__main__":
    main()
