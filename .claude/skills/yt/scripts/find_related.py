#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-frontmatter>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""Find related notes — scores notes by backlinks, shared tags, outgoing links, same type.

Scoring:
  - Backlink (another note links to this one): +3
  - Outgoing link (this note links to another): +2
  - Each shared tag: +1
  - Same frontmatter type: +1

Usage: uv run find_related.py "path/to/note"
       uv run find_related.py --config config.yaml "path/to/note"
"""

import json
import os
import re
import sys
from pathlib import Path

import frontmatter
import yaml

WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]+)", re.MULTILINE)


def get_vault_path(args: list[str]) -> tuple[Path, list[str]]:
    """Resolve vault path from --config flag, env var, or current directory."""
    remaining = list(args)

    if "--config" in remaining:
        idx = remaining.index("--config")
        if idx + 1 < len(remaining):
            config_path = Path(remaining[idx + 1])
            remaining.pop(idx)  # remove --config
            remaining.pop(idx)  # remove the path value
            if config_path.exists():
                with open(config_path) as f:
                    cfg = yaml.safe_load(f)
                if cfg and cfg.get("vault_path"):
                    return Path(cfg["vault_path"]).resolve(), remaining

    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path).resolve(), remaining

    return Path.cwd().resolve(), remaining


def resolve_path(vault_path: Path, rel_path: str) -> Path:
    cleaned = rel_path.lstrip("/")
    full = vault_path / cleaned
    if not full.suffix and not full.exists():
        full = full.with_suffix(".md")
    return full


def parse_note(path: Path, vault_path: Path) -> dict | None:
    if not path.exists() or not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8-sig")
    try:
        post = frontmatter.loads(raw)
    except Exception:
        return None

    wikilinks = WIKILINK_RE.findall(post.content)
    fm_tags = post.metadata.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [fm_tags]
    inline_tags = TAG_RE.findall(post.content)
    all_tags = sorted(set(fm_tags + inline_tags))

    return {
        "path": str(path.relative_to(vault_path)),
        "frontmatter": dict(post.metadata),
        "tags": all_tags,
        "wikilinks": wikilinks,
        "link_stems": {link.split("/")[-1].lower() for link in wikilinks},
    }


def scan_vault(vault_path: Path) -> list[Path]:
    return [
        p for p in sorted(vault_path.rglob("*.md"))
        if ".obsidian" not in p.parts
    ]


def main():
    vault_path, remaining = get_vault_path(sys.argv[1:])

    if not remaining:
        json.dump({"error": "Usage: find_related.py [--config config.yaml] <vault-relative-path>"}, sys.stdout)
        print()
        return

    resolved = resolve_path(vault_path, remaining[0])
    source = parse_note(resolved, vault_path)
    if source is None:
        json.dump({"error": f"Note not found: {remaining[0]}"}, sys.stdout)
        print()
        return

    source_tags = set(source["tags"])
    source_link_stems = source["link_stems"]
    source_stem = resolved.stem.lower()
    src_type = source["frontmatter"].get("type")

    related = []

    for p in scan_vault(vault_path):
        if p == resolved:
            continue
        note = parse_note(p, vault_path)
        if note is None:
            continue

        score = 0
        reasons = []

        if source_stem in note["link_stems"]:
            score += 3
            reasons.append("backlink")

        if p.stem.lower() in source_link_stems:
            score += 2
            reasons.append("outgoing_link")

        note_tags = set(note.get("tags", []))
        shared = source_tags & note_tags
        if shared:
            score += len(shared)
            reasons.append(f"shared_tags: {sorted(shared)}")

        note_type = note["frontmatter"].get("type")
        if src_type and src_type == note_type:
            score += 1
            reasons.append("same_type")

        if score > 0:
            related.append({"path": note["path"], "score": score, "reasons": reasons})

    sorted_related = sorted(related, key=lambda x: x["score"], reverse=True)
    result = {
        "source": remaining[0],
        "total_related": len(sorted_related),
        "related": sorted_related[:20],
    }

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
