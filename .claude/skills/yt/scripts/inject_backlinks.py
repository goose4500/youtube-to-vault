#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-frontmatter>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""Bidirectional backlink injection engine.

For each new note, scores relatedness against the entire vault and injects
wikilinks into "Related Notes" / "See Also" sections.

Usage:
  uv run inject_backlinks.py --config config.yaml --new-notes "note1.md,note2.md"
  uv run inject_backlinks.py --config config.yaml --new-notes "note1.md" --dry-run
  uv run inject_backlinks.py --config config.yaml --new-notes "note1.md" --incoming
  uv run inject_backlinks.py --config config.yaml --new-notes "note1.md" --min-score 4 --max-per-note 5
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
RELATED_SECTION_RE = re.compile(r"^## .*(?:[Rr]elated|See Also|Links)\s*$", re.MULTILINE)


def parse_args(argv: list[str]) -> dict:
    args = {
        "config": None,
        "new_notes": [],
        "min_score": 3,
        "max_per_note": 10,
        "dry_run": False,
        "incoming": False,
    }
    i = 0
    while i < len(argv):
        if argv[i] == "--config" and i + 1 < len(argv):
            args["config"] = argv[i + 1]
            i += 2
        elif argv[i] == "--new-notes" and i + 1 < len(argv):
            args["new_notes"] = [n.strip() for n in argv[i + 1].split(",") if n.strip()]
            i += 2
        elif argv[i] == "--min-score" and i + 1 < len(argv):
            args["min_score"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--max-per-note" and i + 1 < len(argv):
            args["max_per_note"] = int(argv[i + 1])
            i += 2
        elif argv[i] == "--dry-run":
            args["dry_run"] = True
            i += 1
        elif argv[i] == "--incoming":
            args["incoming"] = True
            i += 1
        else:
            i += 1
    return args


def get_vault_path(config_path: str | None) -> Path:
    if config_path:
        p = Path(config_path)
        if p.exists():
            with open(p) as f:
                cfg = yaml.safe_load(f)
            if cfg and cfg.get("vault_path"):
                return Path(cfg["vault_path"]).resolve()

    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path).resolve()

    return Path.cwd().resolve()


def scan_vault(vault_path: Path) -> list[Path]:
    return [
        p for p in sorted(vault_path.rglob("*.md"))
        if ".obsidian" not in p.parts
    ]


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
        "content": raw,
    }


def score_relatedness(source: dict, candidate: dict, source_path: Path, candidate_path: Path) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    source_stem = source_path.stem.lower()
    candidate_stem = candidate_path.stem.lower()

    source_links = {link.split("/")[-1].lower() for link in source.get("wikilinks", [])}
    candidate_links = {link.split("/")[-1].lower() for link in candidate.get("wikilinks", [])}

    if source_stem in candidate_links:
        score += 3
        reasons.append("backlink")

    if candidate_stem in source_links:
        score += 2
        reasons.append("outgoing_link")

    source_tags = set(source.get("tags", []))
    candidate_tags = set(candidate.get("tags", []))
    shared = source_tags & candidate_tags
    if shared:
        score += len(shared)
        reasons.append(f"shared_tags: {sorted(shared)}")

    src_type = source["frontmatter"].get("type")
    cand_type = candidate["frontmatter"].get("type")
    if src_type and src_type == cand_type:
        score += 1
        reasons.append("same_type")

    return score, reasons


def existing_wikilinks_in_section(content: str, section_match: re.Match) -> set[str]:
    """Extract existing wikilinks from a Related/See Also section."""
    start = section_match.end()
    next_heading = re.search(r"^## ", content[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content)
    section_text = content[start:end]
    return {link.lower() for link in WIKILINK_RE.findall(section_text)}


def inject_links_into_note(note_path: Path, links_to_add: list[str], dry_run: bool) -> list[str]:
    """Inject wikilinks into a note's Related Notes section. Returns list of actually injected links."""
    content = note_path.read_text(encoding="utf-8-sig")

    # Find existing related section
    match = RELATED_SECTION_RE.search(content)

    # Deduplicate against existing links in section
    existing = set()
    if match:
        existing = existing_wikilinks_in_section(content, match)

    # Also check whole-document wikilinks to avoid redundancy
    all_existing = {link.split("/")[-1].lower() for link in WIKILINK_RE.findall(content)}

    injected = []
    new_links_block = ""
    for link in links_to_add:
        stem = link.lower()
        if stem not in existing and stem not in all_existing:
            new_links_block += f"- [[{link}]]\n"
            injected.append(link)

    if not injected:
        return []

    if dry_run:
        return injected

    if match:
        # Insert after the section heading
        insert_pos = match.end()
        # Find where current section content starts (skip blank lines)
        remaining = content[insert_pos:]
        leading_newlines = len(remaining) - len(remaining.lstrip("\n"))
        insert_pos += leading_newlines
        content = content[:insert_pos] + "\n" + new_links_block + content[insert_pos:]
    else:
        # Append a new Related Notes section
        content = content.rstrip("\n") + "\n\n## Related Notes\n\n" + new_links_block

    note_path.write_text(content, encoding="utf-8")
    return injected


def main():
    args = parse_args(sys.argv[1:])

    if not args["new_notes"]:
        json.dump({"error": "Usage: inject_backlinks.py --config config.yaml --new-notes 'note1.md,note2.md' [--dry-run] [--incoming]"}, sys.stdout)
        print()
        return

    vault_path = get_vault_path(args["config"])
    min_score = args["min_score"]
    max_per_note = args["max_per_note"]
    dry_run = args["dry_run"]
    do_incoming = args["incoming"]

    all_vault_notes = scan_vault(vault_path)
    report = {
        "outgoing_injected": [],
        "incoming_candidates": [],
        "skipped_duplicates": 0,
        "dry_run": dry_run,
    }

    for new_note_rel in args["new_notes"]:
        new_note_path = vault_path / new_note_rel.lstrip("/")
        if not new_note_path.suffix:
            new_note_path = new_note_path.with_suffix(".md")

        new_note = parse_note(new_note_path, vault_path)
        if new_note is None:
            report["outgoing_injected"].append({
                "note": new_note_rel,
                "error": "Note not found",
            })
            continue

        # Score against all vault notes
        scored = []
        for p in all_vault_notes:
            if p == new_note_path:
                continue
            candidate = parse_note(p, vault_path)
            if candidate is None:
                continue

            score, reasons = score_relatedness(new_note, candidate, new_note_path, p)
            if score >= min_score:
                scored.append({
                    "path": str(p.relative_to(vault_path)),
                    "stem": p.stem,
                    "score": score,
                    "reasons": reasons,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:max_per_note]

        # Outgoing: inject links from new note → existing notes
        links_to_add = [s["stem"] for s in top]
        injected = inject_links_into_note(new_note_path, links_to_add, dry_run)

        report["outgoing_injected"].append({
            "note": new_note_rel,
            "injected": injected,
            "candidates_scored": len(scored),
            "top_matches": top[:5],
        })
        report["skipped_duplicates"] += len(links_to_add) - len(injected)

        # Incoming: inject links from existing notes → new note
        if do_incoming:
            for match in top:
                existing_path = vault_path / match["path"]
                existing_note = parse_note(existing_path, vault_path)
                if existing_note is None:
                    continue

                reverse_score, reverse_reasons = score_relatedness(
                    existing_note, new_note, existing_path, new_note_path
                )
                if reverse_score >= min_score:
                    incoming_injected = inject_links_into_note(
                        existing_path, [new_note_path.stem], dry_run
                    )
                    report["incoming_candidates"].append({
                        "existing_note": match["path"],
                        "new_note": new_note_rel,
                        "score": reverse_score,
                        "reasons": reverse_reasons,
                        "injected": incoming_injected,
                    })

    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
