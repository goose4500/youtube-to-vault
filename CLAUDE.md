# youtube-to-vault

YouTube video to Obsidian knowledge graph pipeline. Fetches transcripts, decomposes them into topics, researches each topic, writes vault-connected notes, and injects backlinks — all adapted to your vault's existing conventions.

## First-Time Setup

Run `bash setup.sh` to configure your vault path and generate `config.yaml` + `vault-profile.json`.

## Key Files

| File | Purpose |
|------|---------|
| `.claude/skills/yt/SKILL.md` | The skill definition — Claude reads this to know how to process videos |
| `.claude/skills/yt/scripts/get_transcript.py` | Fetches YouTube transcript + metadata |
| `.claude/skills/yt/scripts/scan_vault.py` | Detects vault conventions → vault-profile.json |
| `.claude/skills/yt/scripts/find_related.py` | Scores note relatedness against vault |
| `.claude/skills/yt/scripts/inject_backlinks.py` | Bidirectional backlink injection engine |
| `.claude/skills/yt/scripts/tags_overview.py` | Tag aggregation across vault |
| `config.yaml` | User settings (gitignored) |
| `vault-profile.json` | Auto-detected vault conventions (gitignored) |
| `config.yaml.example` | Documented config template |

## Usage

Paste a YouTube URL and Claude will activate the `/yt` skill automatically.

Trigger phrases: "learn from this video", "add this to my vault", "research this video", "extract knowledge from", or just paste a URL.

## Two Modes

- **Default**: Single-pass processing. Claude handles everything inline. Good for videos under 20 minutes.
- **Deep**: Parallel agent team researches each topic with web search. Use for longer videos or when the user says "deep", "research", or "deep dive".

## Running Scripts

All scripts use PEP 723 inline metadata so `uv run` handles dependencies automatically:

```bash
uv run .claude/skills/yt/scripts/get_transcript.py "<url>"
uv run .claude/skills/yt/scripts/scan_vault.py "/path/to/vault"
uv run .claude/skills/yt/scripts/find_related.py --config config.yaml "path/to/note.md"
uv run .claude/skills/yt/scripts/inject_backlinks.py --config config.yaml --new-notes "note.md" --dry-run
uv run .claude/skills/yt/scripts/tags_overview.py --config config.yaml
```

No pip install, no venv, no requirements.txt needed.

## Optional MCP Servers

Zero MCP servers are required for default mode. These enhance the experience if available:

- **sequential-thinking**: Forces systematic reasoning during synthesis phase
- **excalidraw**: Generates visual concept maps of video topics (requires `config.diagrams.enabled: true`)
