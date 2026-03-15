# History Schema

Use this file when reading or updating the local experience history.

## Storage Rules

- Default path: `.experience-planner/history.json` in the current working directory
- Keep history local to the workspace or task context
- Do not store the history inside the skill folder
- Override the path with `--history-file` when the user already has a preferred location

## File Shape

The bundled script stores data as JSON:

```json
{
  "version": 1,
  "updated_at": "2026-03-15T03:30:00Z",
  "activities": [
    {
      "id": "a1b2c3d4",
      "title": "Late-night bouldering",
      "date": "2026-03-15",
      "status": "completed",
      "category": "fitness",
      "location": "Boulder Planet",
      "companions": "friends",
      "cost": 32.0,
      "travel_minutes": 18,
      "rating": 4,
      "tags": ["indoor", "active"],
      "notes": "Crowded after 8pm but worth it",
      "source": "https://example.com",
      "created_at": "2026-03-15T03:30:00Z"
    }
  ]
}
```

## Recording Guidance

Record an activity when the user:

- confirms what they actually did
- says they loved or disliked a plan
- wants the system to remember a favorite or avoid a repeat

Prefer `completed` for finished activities. Use `planned` only when the user wants tentative plans recorded.

## Useful Commands

Create the file if it does not exist:

```bash
python3 <path-to-skill>/scripts/activity_history.py ensure
```

Inspect recent entries:

```bash
python3 <path-to-skill>/scripts/activity_history.py recent --limit 10
python3 <path-to-skill>/scripts/activity_history.py summary --limit 20
```

Record a completed activity:

```bash
python3 <path-to-skill>/scripts/activity_history.py record \
  --title "Museum late opening" \
  --date 2026-03-15 \
  --companions partner \
  --category culture \
  --cost 24 \
  --rating 5 \
  --tag indoor \
  --tag date-night
```
