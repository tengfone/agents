# Personal Agents

This repository is the source of truth for my reusable agent and skill files.

Each agent lives in its own folder and can include:

- `SKILL.md` for the main instructions, triggers, workflow, and output shape
- `agents/` for provider-specific configuration such as `openai.yaml`
- `references/` for rubrics, schemas, and background notes
- `scripts/` for small helper utilities that support the agent

The repo is intentionally simple. It is a versioned collection of prompt assets and helpers, not a packaged framework.

## Current Agents

| Agent | Purpose |
| --- | --- |
| `experience-planner` | Turns vague leisure requests into concrete, live-verified local plans with optional history tracking. |

## Conventions

- Use `kebab-case` for agent folder names and skill names.
- Keep one agent per folder.
- Put stable core behavior in `SKILL.md`.
- Move long rubrics, schemas, or research checklists into `references/`.
- Keep scripts small and task-focused.
- Store local runtime data outside the skill folder, usually in a hidden workspace directory such as `.my-agent/`.
