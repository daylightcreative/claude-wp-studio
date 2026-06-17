#!/usr/bin/env python3
"""Claude WP Studio — Library Card Catalog. SQLite FTS5 full-text search over the knowledge base.

Lives in the studio's tooling/ and indexes the sibling library/.
Run from the studio root:

    python3 tooling/catalog.py build
    python3 tooling/catalog.py search "divi cache mu-plugin"
    python3 tooling/catalog.py categories
    python3 tooling/catalog.py browse lessons

Set WP_STUDIO_LIBRARY to override the library location if the folders ever move.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

# This file is .../<studio>/tooling/catalog.py
# The library is its sibling: .../<studio>/library
LIBRARY_ROOT = Path(
    os.environ.get("WP_STUDIO_LIBRARY", Path(__file__).resolve().parent.parent / "library")
)
DB_PATH = LIBRARY_ROOT / "catalog.db"

# Top-level library categories that get indexed.
ACTIVE_DIRS = [
    "clients",
    "lessons",
    "playbooks",
    "reference",
]

# Index/meta files are skipped (they aren't knowledge docs themselves).
SKIP_FILES = {"INDEX.md", "CONTRIBUTING.md", "README.md"}


def extract_metadata(text: str) -> dict:
    """Extract title, description, headings, and inline metadata from markdown."""
    lines = text.split("\n")
    meta: dict = {"title": "", "description": "", "headings": [], "date": "", "status": ""}

    # Title: first H1
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            meta["title"] = line[2:].strip()
            break

    # Inline metadata (bold key-value pairs like **Date**: 2026-03-04)
    for line in lines[:30]:
        m = re.match(r"\*\*Date\*\*:\s*(.+)", line)
        if m:
            meta["date"] = m.group(1).strip()
        m = re.match(r"\*\*Status\*\*:\s*(.+)", line)
        if m:
            meta["status"] = m.group(1).strip()

    # Description: first non-empty, non-heading, non-metadata paragraph
    in_code_block = False
    desc_lines = []
    found_title = False
    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not found_title:
            if line.startswith("# ") and not line.startswith("## "):
                found_title = True
            continue
        stripped = line.strip()
        if not desc_lines:
            if not stripped or stripped == "---" or stripped.startswith("**") or stripped.startswith("|"):
                continue
            if stripped.startswith("#"):
                desc_lines.append(stripped.lstrip("#").strip())
                break
        if stripped and not stripped.startswith("#") and stripped != "---":
            desc_lines.append(stripped)
        elif desc_lines:
            break
    meta["description"] = " ".join(desc_lines)[:500]

    # All headings (H2-H4) for searchable content
    headings = []
    in_code_block = False
    for line in lines:
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        m = re.match(r"^(#{2,4})\s+(.+)", line)
        if m:
            headings.append(m.group(2).strip())
    meta["headings"] = headings

    return meta


def categorize(rel_path: str) -> tuple[str, str]:
    """Return (category, subcategory) from relative path."""
    parts = Path(rel_path).parts
    category = parts[0] if parts else ""
    subcategory = parts[1] if len(parts) > 2 else ""
    return category, subcategory


def build_index():
    """Crawl active docs and build the SQLite FTS5 index."""
    if not LIBRARY_ROOT.is_dir():
        print(f"Library not found at {LIBRARY_ROOT}", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(str(DB_PATH))
    db.execute("DROP TABLE IF EXISTS catalog")
    db.execute("DROP TABLE IF EXISTS catalog_fts")

    db.execute("""
        CREATE TABLE catalog (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            category TEXT,
            subcategory TEXT,
            title TEXT,
            description TEXT,
            headings TEXT,
            date TEXT,
            status TEXT
        )
    """)

    db.execute("""
        CREATE VIRTUAL TABLE catalog_fts USING fts5(
            title, description, headings, category, path,
            content='catalog',
            content_rowid='id'
        )
    """)

    count = 0
    for dir_name in ACTIVE_DIRS:
        dir_path = LIBRARY_ROOT / dir_name
        if not dir_path.is_dir():
            continue
        for md_file in sorted(dir_path.rglob("*.md")):
            if md_file.name in SKIP_FILES:
                continue
            rel = str(md_file.relative_to(LIBRARY_ROOT))
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            meta = extract_metadata(text)
            category, subcategory = categorize(rel)
            headings_text = " | ".join(meta["headings"])

            db.execute(
                "INSERT INTO catalog (path, category, subcategory, title, description, headings, date, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rel, category, subcategory, meta["title"], meta["description"], headings_text, meta["date"], meta["status"]),
            )
            count += 1

    db.execute("""
        INSERT INTO catalog_fts (rowid, title, description, headings, category, path)
        SELECT id, title, description, headings, category, path FROM catalog
    """)

    db.commit()
    db.close()
    print(f"Indexed {count} documents into {DB_PATH}")


def search(query: str, category: str | None = None, limit: int = 15, fmt: str = "table"):
    """Search the catalog using FTS5 ranked matching."""
    if not DB_PATH.exists():
        print("No catalog.db found. Run: python3 tooling/catalog.py build", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(str(DB_PATH))

    terms = query.strip().split()
    fts_query = " OR ".join(f'"{t}"*' for t in terms if t)

    sql = """
        SELECT c.path, c.category, c.title, c.description,
               catalog_fts.rank
        FROM catalog_fts
        JOIN catalog c ON c.id = catalog_fts.rowid
        WHERE catalog_fts MATCH ?
    """
    params: list = [fts_query]

    if category:
        sql += " AND c.category = ?"
        params.append(category)

    sql += " ORDER BY catalog_fts.rank LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    db.close()

    if not rows:
        print("No results found.")
        return

    if fmt == "json":
        results = [
            {"path": r[0], "category": r[1], "title": r[2], "description": r[3]}
            for r in rows
        ]
        print(json.dumps(results, indent=2))
    else:
        for i, (path, cat, title, desc, _rank) in enumerate(rows, 1):
            title_display = title or "(untitled)"
            print(f"\n{i}. [{cat}] {title_display}")
            print(f"   {path}")
            if desc:
                truncated = (desc[:120] + "...") if len(desc) > 120 else desc
                print(f"   {truncated}")


def list_categories():
    """List all categories and doc counts."""
    if not DB_PATH.exists():
        print("No catalog.db found. Run: python3 tooling/catalog.py build", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(str(DB_PATH))
    rows = db.execute(
        "SELECT category, COUNT(*) FROM catalog GROUP BY category ORDER BY category"
    ).fetchall()
    db.close()

    total = 0
    for cat, cnt in rows:
        print(f"  {cat:<20} {cnt:>4} docs")
        total += cnt
    print(f"  {'TOTAL':<20} {total:>4} docs")


def browse(category: str, subcategory: str | None = None):
    """List all docs in a category, optionally filtered by subcategory."""
    if not DB_PATH.exists():
        print("No catalog.db found. Run: python3 tooling/catalog.py build", file=sys.stderr)
        sys.exit(1)

    db = sqlite3.connect(str(DB_PATH))
    if subcategory:
        rows = db.execute(
            "SELECT path, title FROM catalog WHERE category = ? AND subcategory = ? ORDER BY path",
            (category, subcategory),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT path, title FROM catalog WHERE category = ? ORDER BY path",
            (category,),
        ).fetchall()
    db.close()

    if not rows:
        print(f"No docs found in '{category}'" + (f"/{subcategory}" if subcategory else ""))
        return

    for path, title in rows:
        title_display = title or "(untitled)"
        print(f"  {path:<65} {title_display}")


def main():
    parser = argparse.ArgumentParser(
        description="Claude WP Studio — Library Card Catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python3 tooling/catalog.py build
  python3 tooling/catalog.py search "divi to gutenberg"
  python3 tooling/catalog.py search "cache" --category lessons
  python3 tooling/catalog.py search "kinsta" --json
  python3 tooling/catalog.py categories
  python3 tooling/catalog.py browse lessons""",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("build", help="Rebuild the search index from active docs")

    sp_search = sub.add_parser("search", help="Search the catalog")
    sp_search.add_argument("query", help="Search terms")
    sp_search.add_argument("-c", "--category", help="Filter by category")
    sp_search.add_argument("-n", "--limit", type=int, default=15, help="Max results (default: 15)")
    sp_search.add_argument("--json", action="store_true", help="Output as JSON")

    sub.add_parser("categories", help="List all categories and doc counts")

    sp_browse = sub.add_parser("browse", help="List docs in a category")
    sp_browse.add_argument("category", help="Category name")
    sp_browse.add_argument("subcategory", nargs="?", help="Optional subcategory")

    args = parser.parse_args()

    if args.command == "build":
        build_index()
    elif args.command == "search":
        search(args.query, category=args.category, limit=args.limit, fmt="json" if args.json else "table")
    elif args.command == "categories":
        list_categories()
    elif args.command == "browse":
        browse(args.category, args.subcategory)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
