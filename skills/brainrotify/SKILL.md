---
name: brainrotify
description: >-
  Rewrite developer-facing prose into playful Gen-Z "brainrot" language
  without changing executable code. Use when an AI coding agent or assistant
  needs to transform comments, docstrings, Markdown, README files, or other
  documentation text surfaces in one file or a directory while preserving
  syntax, logic, formatting, and code fences. Support optional backup creation
  and three intensity levels: `L`, `Mid`, and `W`.
---

# Brainrotify

Rewrite eligible text surfaces into meme-heavy prose while leaving program structure intact. Prefer the bundled script for file-based work because it handles file discovery, safe backups, comment targeting, and reporting more reliably than ad hoc edits.

This skill is agent-agnostic. Use the same workflow with Codex, Claude, or similar AI coding agents that can read files, run a script, and present a diff or summary.

## Workflow

1. Initialize the skill clearly.
In the first user-facing update, explicitly say that `brainrotify` runs locally for normal rewrites, list the available intensity levels (`L`, `Mid`, and `W`), and present the scope options up front: single file, folder, or preview-only.

Recommended opening prompt:
`brainrotify` runs locally for normal rewrites. Available intensity levels are `L`, `Mid`, and `W`, and I will use `Mid` by default unless you want a quieter or louder tone.

I can brainrotify a single file, a folder, or do a preview-only pass first. What path do you want me to target, and do you want a timestamped backup in `.brainrot-backup/` before I write changes?

2. Confirm scope.
Identify whether the user wants a single file, a folder, or a preview-only pass. Default to `Mid` unless the user asks for a quieter or louder tone.

3. Offer a backup before writes.
Ask once whether to create a timestamped backup in `.brainrot-backup/<timestamp>/`. Do not skip this question unless the user already said `no backup`, `overwrite`, or `preview only`.

4. Run the helper script.
Use the script for real file rewrites. Prefer `--dry-run --show-diff` first for large batches or unfamiliar file types.

```bash
python3 <path-to-skill>/scripts/brainrotify.py README.md --intensity L --dry-run --show-diff
python3 <path-to-skill>/scripts/brainrotify.py docs/ src/ --intensity Mid --backup
python3 <path-to-skill>/scripts/brainrotify.py . --intensity W --no-backup
```

5. Review the result.
Report how many files were brainrotified, how many were unchanged, and how many were skipped. Mention the backup location when one was created.

## Safety Rules

- Rewrite comments, Markdown, README files, HTML comments, and real docstrings only.
- Do not rewrite fenced code blocks, inline code, imports, identifiers, signatures, executable statements, or non-docstring string literals.
- Keep headings, list structure, indentation, comment markers, and surrounding formatting intact.
- Use `--dry-run --show-diff` before bulk writes when the support matrix is only partially relevant to the target tree.
- Fall back to manual inspection when the file type is unsupported or the diff looks risky.

## Script Notes

The script supports:

- Markdown and plain text docs outside fenced code blocks and frontmatter
- Python `#` comments and true docstrings
- `//` and `/* */` comments in common JS/TS/C-family files
- `#` comments in shell and config files when they are outside quoted strings
- `<!-- -->` comments in HTML-like files
- A separate lexicon file at `scripts/brainrot_lexicon.json`, so vocabulary updates do not require Python edits

The script defaults to `Mid` intensity. In non-interactive mode it refuses to rewrite unless `--backup` or `--no-backup` is provided explicitly, which prevents silent destructive runs.

Keep runtime rewrites network-free. If you want fresher slang, update the lexicon file offline or add a separate refresh script that fetches and compacts terms into the local JSON cache. Do not make live scraping a requirement for normal rewrites.

## Intensity Guide

- `L`: keep the text readable; add a few slang substitutions and light emphasis
- `Mid`: push harder on meme phrasing while keeping the message easy to follow
- `W`: lean into chat-brained phrasing, but keep the meaning recoverable

Use [tone-guide.md](references/tone-guide.md) when you need to reason about style choices or explain the intensity differences before rewriting.
