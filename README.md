# GoTAU — trip passport with AI-assisted readiness check

Student project for StartUp Battle — IT FEST 2026 (Kazakhstan). Team: German Shegay, Sofiya Kopotilova, Ashraf Daurov.

GoTAU helps the organizer of a mountain hike near Almaty check whether the group is ready for a specific route on a specific day. It combines the real forecast for the route's start and highest point, terrain from the GPS track and deterministic safety rules. An AI model (Claude or OpenAI) explains risks for specific people and builds packing lists; every AI claim is checked against the data, and the organizer accepts or rejects each recommendation.

## Run

Python 3.10+, no dependencies for the rules mode.

```
cd mountain_site
python app.py
```

Open http://127.0.0.1:8000. To enable AI: `pip install -r requirements.txt` and set the `ANTHROPIC_API_KEY` (Claude) or `OPENAI_API_KEY` (OpenAI) environment variable. Without a key the app works in rules-only mode and says so on screen.

Tests: `python -m unittest discover -s tests` (inside `mountain_site`).

## Contents

- `mountain_site/` — working prototype: server, rules engine, AI layer, terrain analysis, UI, tests. Detailed description (in Russian): [mountain_site/README.md](mountain_site/README.md).
- `docs/` — feature audit and research, AI card, 24-month financial plan (in Russian).

## Status and limits

Prototype, not a navigation or rescue tool. No offline maps, no GPS tracking, nothing is sent to emergency services. Coordinates of the 15 hand-made catalog routes are approximate; OpenStreetMap tracks are not field-checked. Live AI has been checked on a single trip with OpenAI `gpt-5-mini` (21 Nov 2026); the full 28-scenario evaluation with a live model and a live Claude run have not been done yet.

The code was written with AI coding assistants (Claude Code) under the team's direction.

## Data and licenses

- Routes in `mountain_site/catalog/osm_routes.json`: © OpenStreetMap contributors, ODbL 1.0.
- Map tiles: © OpenTopoMap (CC-BY-SA). Weather and elevation: Open-Meteo (CC BY 4.0).
- Leaflet 1.9.4 (BSD-2-Clause) in `mountain_site/static/vendor`.
