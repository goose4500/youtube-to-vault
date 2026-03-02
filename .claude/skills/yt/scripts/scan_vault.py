#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-frontmatter>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""Vault profiler — detects conventions and outputs a vault-profile.json.

Scans an Obsidian vault and detects:
- Folder structure with note counts
- Frontmatter field frequency
- type and status field value distributions
- Tag vocabulary (frontmatter + inline, sorted by frequency)
- Daily note detection (folder of YYYY-MM-DD.md files)
- Template folder detection
- Link style (wikilinks vs markdown links)
- Folder-to-type mapping

Usage: uv run scan_vault.py <vault_path>
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import frontmatter

WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]+)", re.MULTILINE)
DAILY_NOTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
DAILY_FORMAT_PATTERNS = {
    r"^\d{4}-\d{2}-\d{2}\.md$": "YYYY-MM-DD",
    r"^\d{4}_\d{2}_\d{2}\.md$": "YYYY_MM_DD",
    r"^\d{2}-\d{2}-\d{4}\.md$": "MM-DD-YYYY",
    r"^\d{8}\.md$": "YYYYMMDD",
}


def scan_notes(vault_path: Path) -> list[Path]:
    return [
        p for p in sorted(vault_path.rglob("*.md"))
        if ".obsidian" not in p.parts
    ]


def detect_daily_notes(vault_path: Path) -> dict | None:
    """Find folder containing daily notes by date-format filenames."""
    candidates = {}
    for p in vault_path.rglob("*.md"):
        if ".obsidian" in p.parts:
            continue
        for pattern, fmt in DAILY_FORMAT_PATTERNS.items():
            if re.match(pattern, p.name):
                folder = str(p.parent.relative_to(vault_path))
                if folder == ".":
                    folder = "/"
                key = (folder, fmt)
                candidates[key] = candidates.get(key, 0) + 1
                break

    if not candidates:
        return None

    (folder, fmt), count = max(candidates.items(), key=lambda x: x[1])
    if count < 3:
        return None
    return {"folder": folder, "date_format": fmt, "count": count}


def detect_templates(vault_path: Path) -> dict | None:
    """Check for template folders and Obsidian templates config."""
    template_dirs = ["_templates", "templates", "Templates"]
    for d in template_dirs:
        candidate = vault_path / d
        if candidate.is_dir():
            templates = list(candidate.glob("*.md"))
            if templates:
                return {
                    "folder": d,
                    "count": len(templates),
                    "names": [t.stem for t in templates[:10]],
                }

    config = vault_path / ".obsidian" / "templates.json"
    if config.exists():
        data = json.loads(config.read_text())
        folder = data.get("folder", "")
        if folder:
            candidate = vault_path / folder
            if candidate.is_dir():
                templates = list(candidate.glob("*.md"))
                return {
                    "folder": folder,
                    "count": len(templates),
                    "names": [t.stem for t in templates[:10]],
                }
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: scan_vault.py <vault_path>", file=sys.stderr)
        sys.exit(1)

    vault_path = Path(sys.argv[1]).resolve()
    if not vault_path.is_dir():
        print(f"Error: {vault_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    notes = scan_notes(vault_path)

    # Folder counts
    dir_counts = Counter()
    # Frontmatter field frequency
    fm_field_freq = Counter()
    # type and status distributions
    type_dist = Counter()
    status_dist = Counter()
    # Tag vocabulary
    tag_freq = Counter()
    # Link style sampling
    wikilink_count = 0
    mdlink_count = 0
    # Folder-to-type mapping
    folder_types: dict[str, Counter] = {}

    for p in notes:
        raw = p.read_text(encoding="utf-8-sig")
        try:
            post = frontmatter.loads(raw)
        except Exception:
            # Skip notes with malformed frontmatter
            dir_name = str(p.parent.relative_to(vault_path))
            if dir_name == ".":
                dir_name = "/"
            dir_counts[dir_name] += 1
            wikilink_count += len(WIKILINK_RE.findall(raw))
            mdlink_count += len(MD_LINK_RE.findall(raw))
            continue

        dir_name = str(p.parent.relative_to(vault_path))
        if dir_name == ".":
            dir_name = "/"
        dir_counts[dir_name] += 1

        # Frontmatter fields
        for key in post.metadata:
            fm_field_freq[key] += 1

        note_type = post.metadata.get("type")
        if note_type:
            type_dist[note_type] += 1
            if dir_name not in folder_types:
                folder_types[dir_name] = Counter()
            folder_types[dir_name][note_type] += 1

        status = post.metadata.get("status")
        if status:
            status_dist[status] += 1

        # Tags
        fm_tags = post.metadata.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [fm_tags]
        inline_tags = TAG_RE.findall(post.content)
        for t in fm_tags + inline_tags:
            tag_freq[t.lower().lstrip("#")] += 1

        # Link style
        wikilink_count += len(WIKILINK_RE.findall(post.content))
        mdlink_count += len(MD_LINK_RE.findall(post.content))

    # Folder-to-type mapping (most common type per folder)
    folder_type_map = {}
    for folder, types in folder_types.items():
        most_common = types.most_common(1)[0]
        folder_type_map[folder] = {
            "primary_type": most_common[0],
            "count": most_common[1],
            "total_typed": sum(types.values()),
        }

    # Link style determination
    total_links = wikilink_count + mdlink_count
    if total_links > 0:
        wiki_pct = round(wikilink_count / total_links * 100, 1)
        link_style = "wikilinks" if wiki_pct > 60 else "markdown" if wiki_pct < 40 else "mixed"
    else:
        link_style = "unknown"
        wiki_pct = 0

    profile = {
        "vault_path": str(vault_path),
        "total_notes": len(notes),
        "directories": dict(dir_counts.most_common()),
        "frontmatter_fields": dict(fm_field_freq.most_common()),
        "type_distribution": dict(type_dist.most_common()),
        "status_distribution": dict(status_dist.most_common()),
        "tags": [
            {"tag": tag, "count": count}
            for tag, count in tag_freq.most_common(50)
        ],
        "total_unique_tags": len(tag_freq),
        "link_style": {
            "primary": link_style,
            "wikilinks": wikilink_count,
            "markdown_links": mdlink_count,
            "wikilink_percentage": wiki_pct,
        },
        "daily_notes": detect_daily_notes(vault_path),
        "templates": detect_templates(vault_path),
        "folder_type_mapping": folder_type_map,
    }

    json.dump(profile, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
