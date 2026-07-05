---
title: "I built a second brain that organizes itself"
date: 2026-07-05
description: "Share a link from my phone; two minutes later it's a summarized, categorized, glowing node in a knowledge graph. Here's the architecture — total cost: $0/month."
publish: true
---

<!-- DRAFT for your edit. TODOs mark places that need your voice. The technical claims are all accurate to the real system. -->

Here's the loop my reading life runs on now: I find something worth keeping — an essay, a podcast, a video — and hit share on my phone. About two minutes later, it exists as a published note on this site: summarized, categorized, cross-linked to related things I've read, and glowing as a new node in [an interactive graph of everything I know](/static/brain/). I didn't type anything. I didn't organize anything. The system did.

This post is about how that works, and what broke along the way.

<!-- TODO: a sentence on WHY you wanted this — what wasn't working about how you consumed content before -->

## The pipeline

Everything hangs off one GitHub Actions workflow. Three ways in:

- **iOS share sheet** → a Shortcut fires a `repository_dispatch` at my repo
- **A browser bookmarklet** → same API call from any page on desktop
- **A GitHub issue form** → the zero-setup fallback that works from anywhere

The workflow detects the media type from the URL and fetches accordingly: readability-style extraction for articles, transcripts for YouTube (with a description fallback, because YouTube blocks transcript fetches from datacenter IPs), tweet text via the keyless oEmbed API, and podcasts via a chain I'm disproportionately proud of — Spotify's pages are a JavaScript wall, so the pipeline takes the episode title from Spotify's oEmbed, finds the show's public RSS feed through Apple's iTunes Search API, and pulls the real show notes from there.

Then one Gemini call (free tier) writes a TL;DR and summary. Every note is honest about authorship: machine text carries a visible "AI-generated" badge, and the "My thoughts" section is reserved for me.

## Categories that grow themselves

I didn't want to design a taxonomy. Early versions had a fixed list of tags I'd guessed in advance — it felt dead on arrival, categories for content I hadn't read yet. So tags are **organic**: the LLM proposes 1–3 categories from the content itself.

The obvious failure mode is fragmentation — "agents" vs "ai-agents" vs "agentic-systems" splitting one cluster into three. So there's a second LLM pass that compares every proposed tag against every tag already in the garden and merges near-duplicates onto the existing one. Only genuinely new concepts survive. When one does, the pipeline auto-creates its hub page, which renders my framing of the category above an auto-generated list of everything tagged with it.

The taxonomy this produced is *mine* in a way no upfront design would have been — `agentic-systems` and `venture-capital` sit next to `luxury-industry`, which exists because I listened to one podcast about LVMH.

## The brain

Every note links to its category hubs, and a third LLM pass adds "see also" links between notes whose ideas genuinely connect. All of it renders as [a full-screen force-directed graph](/static/brain/) — hubs glow as gravitational centers, notes orbit them, and clicking any node opens a preview you can dive into. There's a time-lapse slider that replays the graph growing from day one, and the [social preview card](/static/og-card.png) for this site is a screenshot of the real graph, regenerated on every deploy.

## What broke (the fun part)

Building an unattended pipeline means every edge case eventually fires:

- **Race conditions.** Captures, CMS edits, and my own pushes all write to one repo. Two writers hit the same homepage file, the naive `git pull --rebase` died mid-conflict on a CI runner with no human to resolve it, and a capture vanished. The workflow now resolves that exact conflict itself — takes the remote version, replays just its own change, retries.
- **Silent queue drops.** GitHub's workflow concurrency keeps only *one* pending run per group — share three links fast and the middle one gets cancelled without a trace. Serialization had to go entirely; parallel runs are safe now that pushes self-heal.
- **A shadowed variable** (`today = today()`) that crashed every new capture for half a day. The duplicate-detection path didn't call it, so re-shares "worked" while new links died — a genuinely misleading failure signature.
- **Timezones.** GitHub runners live in UTC, so everything I captured after 8pm got tomorrow's date. Dates are stamped in Eastern now, and displayed dates come from frontmatter instead of git history, which rebases kept rewriting.

<!-- TODO: pick your favorite war story and add a line about how it felt / what you learned -->

## The bill

| Piece | Service | Cost |
|---|---|---|
| Hosting | GitHub Pages | $0 |
| Compute | GitHub Actions | $0 |
| Summarization + tagging | Gemini free tier | $0 |
| Content fetching | oEmbed, iTunes Search, RSS | $0 |
| Analytics | GoatCounter | $0 |
| Editing UI | Pages CMS | $0 |

**Total: $0/month.** The constraint shaped the architecture — no database (git is the database), no server (everything is build-time or client-side), no paid APIs (keyless endpoints and free tiers everywhere).

## What's next

<!-- TODO: your actual ambitions for it — some candidates: semantic search over the garden, weekly auto-digests, capturing X threads -->

The garden grows every time I read something worth keeping. That's the whole point: the site is alive because the reading is real — the infrastructure just makes sure nothing gets lost.

*The entire system is open source: [github.com/Kyle-Briggs8/Kyle-Briggs8.github.io](https://github.com/Kyle-Briggs8/Kyle-Briggs8.github.io)*
