# Personal Agents

This repository is is for my agent skills and helper files.

Each skill lives under `skills/<name>/` and can include:

- `SKILL.md` for the main instructions, triggers, workflow, and output shape
- `agents/` for provider-specific configuration such as `openai.yaml`
- `references/` for rubrics, schemas, and background notes
- `scripts/` for small helper utilities that support the agent

The repo is intentionally simple. It is a versioned collection of prompt assets and helpers, not a packaged framework.

## Current Agents

| Agent | Runtime | Purpose |
| --- | --- | --- |
| `experience-planner` | Live web research | Turns vague leisure requests into concrete, live-verified local plans with optional history tracking. |
| `brainrotify` | Local-only rewrite script | Rewrites comments, docstrings, Markdown, and README-style text into brainrot while preserving executable code. Supports `L`, `Mid`, and `W` intensity levels, with `Mid` as the default. |

## Conventions

- Use `kebab-case` for agent folder names and skill names.
- Keep one agent per folder.
- Put stable core behavior in `SKILL.md`.
- Move long rubrics, schemas, or research checklists into `references/`.
- Keep scripts small and task-focused.
- Store local runtime data outside the skill folder, usually in a hidden workspace directory such as `.my-agent/`.
