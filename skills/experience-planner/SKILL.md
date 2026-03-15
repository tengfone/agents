---
name: experience-planner
description: Convert vague real-world leisure requests into concrete activity plans. Use when the user says they are bored, asks what to do tonight or this weekend, wants date ideas, solo outings, hangouts, nearby classes, or short itineraries that should account for location, time, weather, budget, companions, travel time, and prior activity history. Use live web research to verify current venues, events, weather, and local trend signals before recommending a small executable plan, and optionally record the outcome and feedback in a local history file.
metadata:
  history_path: .experience-planner/history.json
  primary_script: scripts/activity_history.py
  requires_live_research: true
  requires_web_browsing: true
  output_sections:
    - assumptions
    - recommended plan
    - booking notes
    - backups
    - history update
tags:
  - planning
  - leisure
  - local-activities
  - itinerary
  - weather-aware
  - budget-aware
  - history-aware
  - trend-aware
  - live-research
---

# Experience Planner

Convert a loose desire for something to do into a short, executable plan with live-verified options, local momentum signals, estimated spend, travel time, and booking notes.

Prefer real, current options over generic idea lists. Use live web browsing for time-sensitive facts and do not present results as current unless you verified them in-session.

## Skill Summary

| Field | Value |
| --- | --- |
| Name | `experience-planner` |
| Description | Convert vague leisure requests into executable, location-aware activity plans with live web verification and local trend checks. |
| Metadata | `history_path=.experience-planner/history.json`; `primary_script=scripts/activity_history.py`; `requires_live_research=true`; `requires_web_browsing=true`; `output_sections=assumptions,recommended plan,booking notes,backups,history update` |
| Tags | `planning`, `leisure`, `local-activities`, `itinerary`, `weather-aware`, `budget-aware`, `history-aware`, `trend-aware`, `live-research` |

## Workflow

1. Lock the planning window.
Translate phrases like `tonight`, `after work`, or `this weekend` into absolute dates and times in the user's locale. State assumptions briefly when the user is vague.

2. Load or create history.
Use the bundled script to create or inspect a local history file before searching. Keep the file in the current workspace, not inside the skill directory.

```bash
python3 <path-to-skill>/scripts/activity_history.py ensure
python3 <path-to-skill>/scripts/activity_history.py summary --limit 20
python3 <path-to-skill>/scripts/activity_history.py recent --limit 10
```

Default history path: `.experience-planner/history.json`

3. Gather the minimum planning context.
Collect only the signals that materially affect the recommendation:

- starting area or neighborhood
- social context: `solo`, `partner`, `friends`, `family`, `team`
- budget ceiling or price sensitivity
- transport mode and max travel time
- indoor or outdoor preference and weather tolerance
- energy level, pace, and vibe
- dietary, accessibility, age, or hard schedule constraints
- willingness to book ahead versus walk-in only

If key context is missing, ask at most one or two short questions. Otherwise, make a reasonable assumption and say so.

4. Research live options and area trends.
Use web browsing for every time-sensitive recommendation. At minimum, verify the planning window against current weather, opening hours, event schedules, class times, ticket availability, and booking links. Also gather local momentum signals such as highly rated or busy area spots, recent openings, current event buzz, and recent neighborhood coverage. Prefer the workflow in [live-research.md](references/live-research.md). Gather roughly five to ten candidates across a few categories before narrowing.

5. Score candidates.
Use [planning-rubric.md](references/planning-rubric.md). Reject candidates that are closed, sold out, clearly outside budget, or too far away for the available window. Reward fit, proximity, novelty, and reliability.

6. Build a small itinerary.
Produce one primary plan and one or two backup plans. Make the primary plan feel executable, not theoretical:

- main activity
- food or drink stop that fits the same area and budget
- optional follow-up if time and energy remain

For each plan, include:

- expected start time and duration
- travel time between legs
- estimated total cost
- why it fits this user and this moment
- what made it a strong live pick right now, for example current availability, popularity, or recency
- booking or walk-in guidance
- source links for anything time-sensitive or spend-related

If browsing or internet access is unavailable, say so clearly and do not imply the results are live. Offer either:

- a generic non-live plan based on stable knowledge, or
- a request for the user to enable browsing and rerun

7. Close the loop.
When the user reports what they did or whether they liked it, record it so future recommendations avoid repetition and improve variety.

```bash
python3 <path-to-skill>/scripts/activity_history.py record \
  --title "Bouldering at Boulder Planet" \
  --date 2026-03-15 \
  --companions friends \
  --category fitness \
  --cost 32 \
  --rating 4 \
  --tag indoor \
  --tag active \
  --notes "Good difficulty spread; crowded after 8pm"
```

## Planning Rules

- Prefer concrete nearby options that can be acted on now over broad idea dumps.
- Use live web research instead of memory for hours, schedules, pricing, weather, and availability.
- Treat "popular nearby" or "what's trending" as a required search dimension whenever the user wants the best current options, not as an optional extra.
- Mix novelty with reliability. Include at least one low-friction option when the user sounds indecisive or last-minute.
- Penalize recent repeats in the same category, venue, or neighborhood unless the user explicitly asks for them.
- Prefer indoor, bookable, or low-weather-risk plans when the forecast is poor.
- Prefer low-coordination plans when the user's request is vague and immediate.
- Widen the radius or switch categories before giving up on a thin search result set.
- Do not recommend a time-sensitive venue or event from a single weak source when a stronger primary source is available.

## Output Shape

Keep the final answer short and actionable:

1. `Assumptions`
Only include this if you had to infer missing context.

2. `Recommended plan`
Give the itinerary in order with times, travel, cost, and one-sentence rationale.

3. `Booking notes`
Call out reservations, ticket links, or opening-hour constraints.

4. `Backups`
Give one or two credible alternatives, not a long list.

5. `History update`
If the user reports the outcome, record it and mention the logged takeaway that will affect future recommendations.

Always include source links for the primary plan and any booking-critical backup.

## Reference Map

- [planning-rubric.md](references/planning-rubric.md): scoring dimensions, search strategy, and itinerary heuristics
- [live-research.md](references/live-research.md): required live-search workflow, source priority, freshness checks, and fallback behavior
- [history-schema.md](references/history-schema.md): local history format, storage rules, and script behavior
