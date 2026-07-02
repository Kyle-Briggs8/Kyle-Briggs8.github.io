# CLAUDE.md — Personal Site + Digital Garden

## What this project is

A personal website with a public "digital garden" (second brain). Clean landing page
(profile, work history, life timeline), a `/blog` for polished writing, and a `/notes`
garden of saved media (articles, tweets, podcasts, videos) with AI-generated summaries,
displayed with an interactive graph view as the centerpiece.

Owner: Kyle — CS/Econ student. Content leans AI/agentic systems, GEOINT, gov-tech,
startups/VC, personal finance.

## Current phase

**Phase 4: polish (ongoing).** Phases 1–3 are COMPLETE. The site is live at
https://kyle-briggs8.github.io (repo: Kyle-Briggs8/Kyle-Briggs8.github.io, deploys
on push to `v5`; pushes from Actions dispatch deploy.yml explicitly since
GITHUB_TOKEN pushes don't trigger it). The capture pipeline (`scripts/capture.py`
+ `.github/workflows/capture.yml`, clients in CAPTURE.md) is verified with all
three clients: issue form, iOS Shortcut (2026-07-02), and bookmarklet (2026-07-02).
`GEMINI_API_KEY` secret is set (Gemini summarizes; Groq fallback unset). Known
limitations: YouTube blocks transcript fetches from GitHub runners (video notes
summarize from the description instead), and some sites' CSP blocks the
bookmarklet (fallback: the issue form).

Still true from Phase 2: the 12 seed notes are machine-drafted placeholders the
owner plans to WIPE and replace with media he actually consumed (fix the homepage
recent-strip and Related links when that happens; keep the 17 hubs and
`private-test-note.md`, the publish-guardrail canary). The `publish: true`
guardrail is fail-closed via the explicit-publish plugin — verified against pages,
graph, search, sitemap, RSS. Deferred by owner: UI/graph styling, hiding empty
"My thoughts" headers, landing-page TODOs. NOTE: the repo is public, so
`publish: false` hides notes from the site but NOT from the repo source — never
sync truly private notes here.

## Stack — decided, do not relitigate

- **Quartz v5** (Obsidian-flavored static site generator) — NOT a custom Next.js/Astro
  build. Prefer configuring Quartz over forking its internals. (v5 uses a YAML config,
  `quartz.config.yaml`, plus a community plugin system. Upstream Quartz remote is
  `upstream`; the default branch is `v5` and deploys trigger on pushes to it.)
- **Obsidian vault** is the content source. Vault syncs to this repo (obsidian-git on
  desktop; mobile only captures via pipeline, never syncs Git directly).
- **GitHub Pages** hosting via GitHub Actions. Budget is $0/month — free tiers only,
  no paid APIs, no paid hosting. (Custom domain later is the one allowed expense.)
- **Gemini free tier** for LLM summarization in the pipeline (same pattern as owner's
  existing events-digest project). Groq/Llama acceptable fallback. Nothing paid.

## Site structure

- `/` — landing page: short bio, work history, life timeline. Clean and professional;
  this is what recruiters see first.
- `/blog` — polished, hand-written essays. Low volume, high effort.
- `/notes` — the garden. High volume, AI-assisted, raw. Graph view lives here.
- Blog and garden stay SEPARATE. Never mix garden notes into the blog index or vice
  versa. Reason: the blog is the owner's voice and signal; garden notes are compost.
- Homepage shows a "recent notes" strip (~5 most recent) as a "current interests" signal.

## Tag vocabulary — the most important rules in this file

Notes are tagged from a CONTROLLED VOCABULARY of exactly these 17 tags:

**Technical / AI:** agentic-systems, llm-evals, rag-and-retrieval, ai-security,
ml-infrastructure, geoint, cybersecurity
**Domain / industry:** gov-tech, startups, venture-capital, big-tech
**Money:** personal-finance, markets-and-investing
**Life / mind:** career-strategy, fitness, math-and-puzzles, ideas-worth-stealing

Rules (reason: freestyle tags fragment the graph into near-duplicate clusters —
"agents" vs "agentic-systems" vs "AI agents" — and the graph turns to mush):

1. Every note gets 1–3 tags. Never more than 3. Never zero.
2. The LLM picks ONLY from the list above. It never invents tags.
3. If nothing fits well, the LLM appends a suggestion to `tag-suggestions.md` for
   human review. A tag is only promoted to the vocabulary by the owner, manually,
   and only when ~5+ notes would use it.
4. No `misc` tag. If a note is untaggable, flag it instead of forcing a tag.
5. Each tag has a hub page (a note named after the concept). Every tagged note links
   to its hub page(s). Hub pages are the gravitational centers of the graph.

## Note template — every garden note follows this shape

Frontmatter:
```yaml
title:        # descriptive, human-readable
source:       # original URL
author:       # creator of the source content
media: article | podcast | video | tweet
date:         # date saved, YYYY-MM-DD
tags: []      # 1–3 from the vocabulary
publish: true # default true; false = excluded from the public build
```

Body, in order:
1. **Embed** — YouTube iframe / tweet embed / podcast player. Plain articles get a
   styled link card instead.
2. **⚡ TL;DR** — 1–2 sentences, AI-generated.
3. **Summary** — short paragraph or a few bullets, AI-generated, with a small italic
   label marking it as AI-generated (honesty: machine voice vs owner's voice).
4. **💭 My thoughts** — created EMPTY. Owner fills in later from Obsidian. Hide the
   section header on the site when empty; style it distinctly when filled.
5. **Related** — links to tag hub pages + any related existing notes.

Filenames/URLs: descriptive slugs (`anthropic-agent-harness-podcast.md`), never
dates or IDs.

Tweets: ALWAYS store the tweet's text and author quoted in the note body. The X
embed is progressive enhancement only. Reason: X embeds are flaky and tweets get
deleted; the note must stand alone.

## Capture pipeline (Phase 3 — not built yet)

- Entry point: `repository_dispatch` GitHub Action. Clients: iOS Shortcut (share
  sheet → HTTP POST) and a browser bookmarklet on Windows. Fallback: GitHub Issue
  form (Action triggers on issue open, processes, closes the issue).
- Flow: receive URL → detect media type → fetch content → LLM generates TL;DR +
  summary + tags (vocabulary-constrained) → commit templated note → Quartz rebuilds.
- Content fetching: article scrape; YouTube via transcript; podcast via the episode's
  SHOW NOTES description, NOT audio transcription (reason: transcription blows the
  $0 budget). Tweet via text extraction.
- Failed fetches: create the note anyway with a `needs-attention` flag in frontmatter.
  Never fail silently.

## Guardrails

- `publish: false` notes must NEVER appear in the public build. Treat this as a
  privacy boundary, not a feature toggle. Never weaken or remove this logic.
- Minimal dependencies. No new services, databases, or frameworks without asking.
- Don't restructure the vault layout without asking — Obsidian sync depends on it.
- Keep this file updated: when a phase completes, update "Current phase" above.
