#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-frontmatter>=1.0.0",
#     "pyyaml>=6.0",
# ]
# ///
"""Tags overview — aggregates all tags (frontmatter + inline) with counts.

Usage: uv run tags_overview.py
       uv run tags_overview.py --config config.yaml
"""

import json
import os
import re
import sys
from pathlib import Path

import frontmatter
import yaml

TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_/-]+)", re.MULTILINE)


def get_vault_path(args: list[str]) -> Path:
    """Resolve vault path from --config flag, env var, or current directory."""
    if "--config" in args:
        idx = args.index("--config")
        if idx + 1 < len(args):
            config_path = Path(args[idx + 1])
            if config_path.exists():
                with open(config_path) as f:
                    cfg = yaml.safe_load(f)
                if cfg and cfg.get("vault_path"):
                    return Path(cfg["vault_path"]).resolve()

    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path).resolve()

    return Path.cwd().resolve()


def main():
    vault_path = get_vault_path(sys.argv[1:])
    tag_index = {}

    for p in sorted(vault_path.rglob("*.md")):
        if ".obsidian" in p.parts:
            continue
        raw = p.read_text(encoding="utf-8-sig")
        try:
            post = frontmatter.loads(raw)
        except Exception:
            continue

        fm_tags = post.metadata.get("tags", [])
        if isinstance(fm_tags, str):
            fm_tags = [fm_tags]
        inline_tags = TAG_RE.findall(post.content)
        all_tags = {t.lower().lstrip("#") for t in fm_tags + inline_tags}

        rel = str(p.relative_to(vault_path))
        for tag in all_tags:
            if tag not in tag_index:
                tag_index[tag] = []
            tag_index[tag].append(rel)

    sorted_tags = sorted(tag_index.items(), key=lambda x: len(x[1]), reverse=True)
    result = {
        "total_unique_tags": len(sorted_tags),
        "tags": [
            {"tag": tag, "count": len(paths), "example_notes": paths[:3]}
            for tag, paths in sorted_tags
        ],
    }

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
