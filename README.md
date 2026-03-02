# youtube-to-vault

Turn any YouTube video into deeply-connected Obsidian vault notes using Claude Code.

Fetches the transcript, decomposes it into core topics and first principles, optionally deep-researches each topic with parallel AI agents, then writes notes that match your vault's existing conventions and injects bidirectional backlinks.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/goose4500/youtube-to-vault.git
cd youtube-to-vault

# 2. Setup (interactive — asks for your vault path)
bash setup.sh

# 3. Use
# Open this folder in Claude Code, then paste a YouTube URL:
#   "Add this to my vault: https://www.youtube.com/watch?v=..."
```

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's CLI)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (script runner — setup.sh offers to install it)
- An Obsidian vault (any structure, any conventions)

No MCP servers required. No pip install. No virtual environment.

## How It Works

1. **Transcript fetch** — Downloads the video transcript via `youtube-transcript-api`
2. **Topic decomposition** — Extracts 3-8 core topics with first principles, key claims, and domain tags
3. **Research** (Deep Mode) — Spawns parallel AI agents to web-search each topic for additional depth
4. **Vault-aware writing** — Reads your `vault-profile.json` to match your frontmatter conventions, tag vocabulary, folder structure, and link style
5. **Backlink injection** — Scores every new note against your entire vault and injects `[[wikilinks]]` in both directions

## Vault Adaptation

On first run, `setup.sh` scans your vault and generates `vault-profile.json`. This captures:

| Convention | How it's detected |
|---|---|
| Folder structure | Note counts per directory |
| Frontmatter fields | Which YAML keys appear across notes |
| Type/status values | Distribution of `type` and `status` field values |
| Tag vocabulary | All tags sorted by frequency |
| Link style | Wikilinks vs markdown links (sample-based) |
| Daily notes | Folder of date-formatted files |
| Templates | `_templates/`, `templates/`, or `.obsidian/templates.json` |

The skill reads this profile on every run so new notes match your vault's patterns.

## Backlink Scoring

Each new note is scored against every existing note in your vault:

| Signal | Points |
|---|---|
| Existing note links to new note (backlink) | +3 |
| New note links to existing note (outgoing) | +2 |
| Each shared tag | +1 |
| Same frontmatter `type` | +1 |

Notes scoring above the threshold (default: 3) get `[[wikilinks]]` injected into a "Related Notes" section. Incoming links (modifying existing notes) require confirmation by default.

## Configuration

Copy `config.yaml.example` to `config.yaml` and edit:

| Key | Default | Description |
|---|---|---|
| `vault_path` | (required) | Absolute path to your Obsidian vault |
| `output_folder` | `""` | Default folder for new notes (relative to vault) |
| `folder_routing` | (none) | Domain keyword → folder mapping |
| `daily_notes.folder` | (none) | Daily notes folder |
| `frontmatter.type` | `"reference"` | Default `type` frontmatter value |
| `frontmatter.default_tags` | `["youtube-import"]` | Tags added to every note |
| `backlinks.auto_inject_outgoing` | `true` | Auto-add links from new → existing notes |
| `backlinks.prompt_before_incoming` | `true` | Ask before modifying existing notes |
| `backlinks.min_score` | `3` | Minimum score to inject a backlink |
| `backlinks.max_suggestions` | `10` | Max related notes linked per new note |
| `diagrams.enabled` | `false` | Generate Excalidraw concept maps |

## Project Structure

```
youtube-to-vault/
├── CLAUDE.md                          # Project instructions for Claude Code
├── README.md                          # This file
├── LICENSE                            # MIT
├── .gitignore
├── setup.sh                           # First-run setup wizard
├── config.yaml.example                # Documented config template
└── .claude/
    └── skills/
        └── yt/
            ├── SKILL.md               # Skill definition (Claude reads this)
            └── scripts/
                ├── get_transcript.py   # YouTube transcript fetcher
                ├── scan_vault.py       # Vault convention detector
                ├── find_related.py     # Note relatedness scorer
                ├── inject_backlinks.py # Bidirectional backlink engine
                └── tags_overview.py    # Tag aggregation
```

**Generated at runtime** (gitignored):
- `config.yaml` — your settings
- `vault-profile.json` — auto-detected vault conventions

## Two Modes

- **Default** — Single-pass. Claude processes everything inline. Best for videos under 20 minutes.
- **Deep** — Parallel agent team researches each topic via web search. Say "deep dive" or "research this" to activate. Best for longer or more technical videos.

## License

MIT
