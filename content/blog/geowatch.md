---
title: "GeoWatch: open-source GEOINT from live news"
date: 2026-07-01
description: How I built a tool that turns a location name into a mapped, severity-scored intelligence dashboard using free news APIs and an LLM.
publish: true
---

*[Live demo](https://geowatch-ej66.onrender.com) · [Source on GitHub](https://github.com/Kyle-Briggs8/Geowatch)*

Type "Ukraine" into a box, wait about a minute, and get back an interactive map of severity-colored events, an escalation trend chart, and a scrollable timeline of everything that happened there in the last 30 days — each event classified by type, severity, and the entities involved. That's GeoWatch: open-source geospatial intelligence built entirely on free tiers.

<!-- TODO: personal hook — why I started this (NGA experience? class project? curiosity?) -->

## What it does

GeoWatch takes any world location and produces an intelligence dashboard with three main views:

- **An interactive map** (Folium/Leaflet) with severity-colored markers — green for low, red for critical — that cluster and expand, each popping open the underlying article.
- **A severity escalation chart** — weekly stacked bars that make it obvious at a glance whether a situation is heating up or cooling down, with a computed trend label.
- **An event swimlane** — a scrollable timeline grouped by event type (conflict, political, natural disaster, economic, protest, terrorism), where every dot is a classified news event you can click for details.

There's also a comparison mode that runs two locations in parallel — Ukraine vs. Taiwan on one combined map with side-by-side charts — a `--brief` flag that generates a one-page markdown intelligence report, and an alert threshold that flags when more than 30% of recent events cross a severity line.

## How it works

The pipeline has four stages:

**1. Fetch.** News comes from two sources in parallel — NewsAPI and GDELT — with the date range split into per-day windows fetched concurrently via a thread pool. Dual-sourcing matters because each API alone is spotty: NewsAPI's free tier only reaches back 30 days and skews toward major outlets, while GDELT reaches 90 days with broader (but noisier) coverage.

**2. Classify.** Each article goes to a Groq-hosted `llama-3.3-70b-versatile` with a system prompt that casts the model as an intelligence analyst. It returns strict JSON: event type, severity (low → critical), key entities, the most specific location mentioned, and a one-line summary. If the response doesn't parse as JSON, the article is dropped rather than guessed at.

**3. Map.** Extracted locations get geocoded and plotted. Severity drives the marker color; clusters expand on click.

**4. Render.** Everything is assembled into a single self-contained HTML dashboard — no backend needed to view it after generation.

The web UI is a small Flask app: pick single or compare mode, set the days slider and article count, hit run. The analysis executes in a background thread with a polling loading page, which is what lets a multi-minute pipeline live behind gunicorn on Render's free tier without hitting request timeouts.

## Design decisions

- **Free tiers only.** NewsAPI, GDELT, Groq, and Render all cost $0. The constraint shaped the architecture — e.g., per-day windowed fetching exists to squeeze maximum coverage out of NewsAPI's free-tier limits.
- **LLM as a structured extractor, not a writer.** The model's only job is classification into a fixed schema. Tight output constraints (raw JSON, enumerated event types and severities) make a fast 70B model reliable enough for this.
- **Self-contained HTML output.** Dashboards are single files you can email, archive, or host anywhere. No database, no state.

## What I learned

<!-- TODO: replace/expand with your real takeaways. Some candidates based on the code: -->

- Getting an LLM to emit *strictly parseable* JSON is a prompt-engineering problem you solve once and defend forever — the "no preamble, no markdown, just raw JSON" instruction exists because every softer phrasing eventually failed.
- Free news APIs disagree with each other constantly. Merging NewsAPI and GDELT meant dealing with duplicates, conflicting metadata, and very different notions of what counts as "news about Ukraine."
- Long-running requests on free-tier hosting are a real design constraint, not an afterthought — the background-thread-plus-polling pattern was the difference between "works locally" and "works deployed."

## What's next

<!-- TODO: your actual roadmap, if any — some ideas: entity-relationship graphs across events, scheduled monitoring with diffs, source credibility weighting -->
