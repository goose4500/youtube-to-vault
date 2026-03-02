---
name: yt
description: >
  YouTube video -> Obsidian knowledge graph pipeline. Fetches a YouTube transcript,
  decomposes it into topics and first principles, researches each topic, analyzes the
  vault knowledge graph, writes optimally-connected notes, and injects backlinks.
  Adapts to any vault's conventions using vault-profile.json auto-detection.
  Use when the user says "learn from this video", "add this YouTube video to my vault",
  "research this video", "extract knowledge from", or pastes a YouTube URL.
---

# YouTube -> Vault Knowledge Pipeline

Transforms any YouTube video into deeply-researched, optimally-connected Obsidian notes. Adapts to your vault's conventions automatically.

## Setup

On first run, check that these exist in the project root (parent of `.claude/`):
- `config.yaml` — user settings (vault path, frontmatter prefs, backlink config)
- `vault-profile.json` — auto-detected vault conventions

If missing, tell the user to run `bash setup.sh` first.

**Load both files at the start of every run.** They tell you:
- Where the vault is (`config.vault_path`)
- What frontmatter fields to use (`vault-profile.json → frontmatter_fields`)
- What tags already exist (`vault-profile.json → tags`)
- What link style to use (`vault-profile.json → link_style.primary`)
- Where to place notes (`config.output_folder`, `config.folder_routing`, `vault-profile.json → folder_type_mapping`)
- Daily note conventions (`config.daily_notes`, `vault-profile.json → daily_notes`)

## Script Locations

All scripts live relative to this skill file:

| Script | Path | Purpose |
|--------|------|---------|
| get_transcript.py | `{skill_dir}/scripts/get_transcript.py` | Fetch YouTube transcript + metadata |
| scan_vault.py | `{skill_dir}/scripts/scan_vault.py` | Detect vault conventions → vault-profile.json |
| find_related.py | `{skill_dir}/scripts/find_related.py` | Score note relatedness against vault |
| inject_backlinks.py | `{skill_dir}/scripts/inject_backlinks.py` | Bidirectional backlink injection |
| tags_overview.py | `{skill_dir}/scripts/tags_overview.py` | Tag aggregation across vault |

Run scripts with: `uv run {skill_dir}/scripts/{script}.py [args]`

Where `{skill_dir}` = the directory containing this SKILL.md file.

## Two Modes

### Default Mode (videos under 20 min, or user just wants quick capture)
Run all phases yourself in a single pass. No agent team needed.

### Deep Mode (videos 20+ min, user says "deep", "research", or "deep dive")
Spawn a parallel agent team for research. Use `TeamCreate` + `Agent` tool.

---

## Full Pipeline

### Phase 1 — Fetch Transcript

```bash
uv run {skill_dir}/scripts/get_transcript.py "<YOUTUBE_URL>"
```

Parse the JSON output. Extract `transcript`, `word_count`, `duration_minutes`.

**Multi-URL support:** Pass multiple URLs as separate arguments. Returns an array.

---

### Phase 2 — Decompose into Topics & First Principles

Analyze the transcript and extract:

```
1. CORE TOPICS (3-8): Main distinct subjects. Each should be a standalone concept.

2. FIRST PRINCIPLES (per topic): Foundational truths and mechanisms — the "why"
   and "how" that let someone reason from scratch. Not summaries.

3. KEY CLAIMS: Specific assertions, frameworks, statistics, or methods.

4. DOMAIN TAGS: What domain each topic belongs to (for folder routing).

Output as JSON:
{
  "video_title": "...",
  "core_topics": ["topic1", "topic2"],
  "topic_details": {
    "topic1": {
      "summary": "...",
      "first_principles": ["...", "..."],
      "key_claims": ["...", "..."],
      "domain": "ai|automation|business|dev|general"
    }
  }
}
```

---

### Phase 3 — Research (Deep Mode only)

In Default Mode, skip this phase — write notes directly from the transcript.

In Deep Mode, spawn agents:
- **Research agents** (one per core topic, `general-purpose` subagent type): WebSearch for 3-5 sources, cross-reference claims, expand first principles
- **Vault analyzer** (one, `Explore` subagent type): Run `scan_vault.py` and `tags_overview.py`, search vault for related existing notes

Spawn all agents in a SINGLE message for parallel execution.

**Research agent prompt template:**
```
You are a deep research agent. Research this topic from a YouTube video
and write a comprehensive Obsidian note.

TOPIC: {topic_name}
SUMMARY: {topic_summary}
FIRST PRINCIPLES: {first_principles}
KEY CLAIMS: {key_claims}

Instructions:
1. Use WebSearch to find 3-5 high-quality sources
2. Cross-reference the video's claims with what you find
3. Expand the first principles with additional depth
4. Write a comprehensive markdown note (see Note Format below)
5. Report back: note content + 2-sentence summary
```

**Vault analyzer prompt template:**
```
You are a knowledge graph analyst. Analyze the vault and report a map
of existing knowledge to plan integration of new research notes.

1. Run: uv run {skill_dir}/scripts/tags_overview.py --config {project_root}/config.yaml
2. For each incoming topic ({topic_list}):
   - Search the vault using Grep for related terms
   - Identify existing notes that should link to/from new notes
3. Report: existing related notes per topic, recommended connections,
   suggested folder placement, duplicate/overlap risks
```

---

### Phase 4 — Write Notes

For each topic, write a note to the vault. Use vault-profile.json to match conventions:

**Frontmatter:** Use fields that already exist in the vault (check `vault-profile.json → frontmatter_fields`). Always include fields from `config.frontmatter`. Example:

```yaml
---
type: reference          # or config.frontmatter.type
tags:
  - youtube-import       # from config.frontmatter.default_tags
  - {domain}             # from topic decomposition
  - {relevant tags from vault-profile.json → tags}
source: {video_url}      # if config.frontmatter.include_source_url
created: {today}         # if config.frontmatter.include_created
updated: {today}         # if config.frontmatter.include_updated
---
```

**Link style:** Use wikilinks (`[[note-name]]`) if `vault-profile.json → link_style.primary` is "wikilinks", otherwise use markdown links.

**Folder placement priority:**
1. `config.folder_routing` — if a domain keyword matches
2. `vault-profile.json → folder_type_mapping` — match type to the folder where that type is most common
3. `config.output_folder` — fallback

**Note structure:**
```markdown
# {Topic Name}

## Core Concept
[1-2 sentence definition]

## First Principles
[Numbered list of foundational truths]

## How It Works
[Mechanism/framework]

## Key Claims & Evidence
[Bullet points with sources]

## Practical Applications
[How to use this]

## Related Notes
[Populated in Phase 5]

## Sources
[YouTube URL + any research URLs]
```

---

### Phase 5 — Backlink Injection

After writing all notes, connect them to the existing vault.

**Step 1: Score relatedness**
```bash
uv run {skill_dir}/scripts/find_related.py --config {project_root}/config.yaml "{new_note_path}"
```

**Step 2: Inject outgoing links** (if `config.backlinks.auto_inject_outgoing` is true)
```bash
uv run {skill_dir}/scripts/inject_backlinks.py \
  --config {project_root}/config.yaml \
  --new-notes "{note1.md},{note2.md}" \
  --min-score {config.backlinks.min_score} \
  --max-per-note {config.backlinks.max_suggestions}
```

**Step 3: Incoming links** (if `config.backlinks.prompt_before_incoming` is true, do a dry run first)
```bash
# Show what would change
uv run {skill_dir}/scripts/inject_backlinks.py \
  --config {project_root}/config.yaml \
  --new-notes "{note1.md},{note2.md}" \
  --incoming --dry-run

# If user approves:
uv run {skill_dir}/scripts/inject_backlinks.py \
  --config {project_root}/config.yaml \
  --new-notes "{note1.md},{note2.md}" \
  --incoming
```

If `prompt_before_incoming` is false, run incoming injection directly (no dry run).

---

### Phase 6 — Daily Note Entry (optional)

If `config.daily_notes` is configured:

1. Find or create today's daily note at `{vault_path}/{daily_notes.folder}/{today}.md`
2. Find the section matching `daily_notes.insight_section` (default: `## Insights`)
3. Append: `- Processed YouTube video: {title}. Added {N} notes on: {topics}. Created {M} vault connections.`

---

### Phase 7 — Diagram (optional, Deep Mode only)

Only if `config.diagrams.enabled` is true AND the excalidraw MCP server is available.

Generate an Excalidraw concept map showing:
- Core topic nodes (one per topic)
- Relationship arrows between topics
- Vault connection indicators (links to existing notes)

Save to: `{vault_path}/{config.diagrams.output_folder}/{slugified-title}.excalidraw`

---

## Multi-Video Strategy

- **2-3 videos, same topic**: Fetch all transcripts, decompose TOGETHER as one unified topic map
- **Videos on different topics**: Decompose independently, spawn separate research agents
- **5+ videos**: Process in batches of 4-5 to stay within context budget

## Tips

- **Short videos (<10 min)**: Default Mode, skip research, write directly from transcript
- **Medium videos (10-30 min)**: Default Mode with thorough decomposition
- **Long videos (30+ min)**: Deep Mode with agent team
- **Courses / playlists**: Split into chapters, treat each as a separate topic
- **Sequential thinking**: If the `sequential-thinking` MCP server is available, use it during synthesis for higher-quality connections. Not required.
- **Quality check**: After writing notes, Grep for the new filenames to confirm they exist

## Example Usage

User: "Add this to my vault: https://www.youtube.com/watch?v=abc123"

1. Load config.yaml + vault-profile.json
2. Run get_transcript.py → get text
3. Decompose → extract topics
4. Write notes (Default Mode) or spawn research team (Deep Mode)
5. Run backlink injection
6. Update daily note (if configured)
7. Confirm: list notes written + connections made
