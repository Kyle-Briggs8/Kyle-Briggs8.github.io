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

Phase 4 polish pass (2026-07-02): placeholder seed notes WIPED — the garden now
holds only the owner's real captures, the 17 hub pages, and
`private-test-note.md` (publish-guardrail canary — never delete). Catppuccin
theme applied (quartz-themes plugin + Latte/Mocha base colors); template CSS in
`quartz/styles/custom.scss` (hides empty "My thoughts", AI-label badge, source
link cards); graph tuned (tags hidden, radial global view); `/timeline` and
`/now` pages exist. Landing page, timeline, and /now were filled from the
owner's resume 2026-07-03 (UVA CS/Econ '28, Microsoft Federal Cloud & AI,
Galant, R.A.I.S.E., AI4ALL, Spectric, NGA ×2, RII; phone/SAT deliberately
omitted from the public site). GoatCounter analytics live (code kyle-briggs). The `publish: true` guardrail is fail-closed via
the explicit-publish plugin — verified against pages, graph, search, sitemap,
RSS. NOTE: the repo is public, so `publish: false` hides notes from the site but
NOT from the repo source — never sync truly private notes here.

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

## Tags — organic with a canonicalization guard (owner decision 2026-07-02)

Tags EMERGE from captured content; there is no fixed vocabulary. The danger of
organic tags is fragmentation ("agents" vs "ai-agents" vs "agentic-systems"
turns the graph to mush), so the pipeline runs TWO passes:

1. **Propose:** the summarizer LLM suggests 1–3 kebab-case categories — broad
   enough to recur across many items, never one-off descriptors.
2. **Canonicalize:** a second LLM pass compares every proposed tag against ALL
   tags already used in the garden and maps synonyms/near-duplicates onto the
   existing tag. Only genuinely distinct concepts survive as new tags. (Plus a
   cheap algorithmic fold for case/plural variants before the LLM pass.)

Rules:
1. Every note gets 1–3 tags. Never more than 3; zero ⇒ `needs-attention`.
2. No `misc` tag. If a note is untaggable, flag it instead of forcing a tag.
3. Each tag gets a hub page at `content/tags/<tag>.md` (NOT in the garden
   folder), AUTO-CREATED by the pipeline the first time the tag is used —
   never pre-created empty. Quartz renders the hub's framing text with the
   auto-generated listing of ALL tagged content underneath (owner request
   2026-07-04: clicking #ransomware shows everything with that tag). Hub files
   carry NO tags frontmatter (they'd list themselves). Hubs are the graph's
   gravitational centers but stay OUT of the garden feed (owner decision
   2026-07-03: `/notes` is a pure newest-first list of captures).
4. Never mass-rename tags without checking every note that uses them —
   EXCEPT via the gardener (below), which exists for exactly this.
5. **The taxonomy self-regulates at scale** (owner decision 2026-07-05, "I
   don't want to keep folding"): `scripts/gardener.py` runs weekly
   (`gardener.yml`, Mondays) and (a) folds tags with <2 notes past a 14-day
   grace period into their best-fit healthy tag — rewriting notes, deleting
   the hub — and (b) retags any zero-tag notes from the existing tag set.
   A hub with `pinned: true` frontmatter is never folded (editable in Pages
   CMS; currently pinned: llm-evals, rag-and-retrieval, economics). The
   brain also renders hub prominence proportional to note count, so thin
   tags are visually quiet until they earn their glow.

## Note template — every garden note follows this shape

Frontmatter:
```yaml
title:        # descriptive, human-readable
source:       # original URL
author:       # creator of the source content
media: article | podcast | video | tweet
date:         # date saved, YYYY-MM-DD
tags: []      # 1–3 organic tags (canonicalized against existing tags)
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
  summary + organic tags → canonicalization pass dedupes tags against the garden →
  auto-create hub pages for new tags → commit templated note → Quartz rebuilds.
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
