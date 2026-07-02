# PHASES.md — Build Roadmap

Each phase is independently useful: the project is never a half-broken pile.
Finish a phase, update "Current phase" in CLAUDE.md, move on.

---

## Phase 1 — Site skeleton (one evening)

**Goal:** a live personal website on GitHub Pages. No garden, no pipeline.

Tasks:
1. Fork/clone Quartz v4, run it locally, get a feel for the config
   (`quartz.config.ts`, `quartz.layout.ts`).
2. Set up the GitHub repo + GitHub Pages deploy via Quartz's official GitHub
   Actions workflow. Confirm the site is live at `<username>.github.io`.
3. Build the landing page: short bio, headshot, links (GitHub / LinkedIn / email),
   work history section (NGA → Spectric → Microsoft MLE, Galant VC), and a simple
   life timeline.
4. Create `/blog` with one real post (the GeoWatch writeup is the obvious first one).
5. Basic styling pass: fonts, colors, dark mode. Clean > clever at this stage.

**Done when:** the site is live, looks presentable on desktop and mobile, and has
a real blog post. This alone is a complete personal website.

---

## Phase 2 — The garden, manually (a weekend)

**Goal:** a populated `/notes` garden with a graph that looks alive. All manual —
no automation yet. Do NOT skip to Phase 3 with an empty garden: the graph looks
pathetic with 3 nodes, the note template can't be designed well without real notes,
and the seed notes become the LLM's taste examples later.

Tasks:
1. Create the 17 tag hub pages. Each gets 1–3 sentences of the owner's framing of
   that concept ("what I mean by agentic-systems and why I care").
2. Hand-write 10–15 seed notes on recently consumed media, using the exact note
   template from CLAUDE.md (fill the AI-summary sections by hand for now — the
   point is the structure). Link every note to its hub page(s).
3. Enable and style the graph view. Tune it so hub pages read as cluster centers.
4. Add the "recent notes" strip to the homepage.
5. Verify `publish: false` works: create one private test note, confirm it does
   not appear anywhere in the public build (pages, graph, search, sitemap, RSS).

**Done when:** the graph shows real clusters around hub pages, notes render the
template nicely (empty "My thoughts" header hidden), and the publish flag is
verified airtight.

---

## Phase 3 — The capture pipeline (a weekend)

**Goal:** URL in, published note out, ~2 minutes, zero manual steps.

Build order (backend first, clients last):

1. **The Action.** A GitHub Actions workflow triggered by `repository_dispatch`
   (payload: `{ url, quick_thought? }`).
2. **Media-type detection** from the URL (youtube.com/youtu.be → video; x.com/
   twitter.com → tweet; known podcast domains/RSS → podcast; else article).
3. **Content fetching**, per type:
   - Article: scrape main text (readability-style extraction).
   - YouTube: pull the transcript; fall back to title + description if unavailable.
   - Tweet: extract text + author; store both in the note body (embed is bonus).
   - Podcast: use the episode's show-notes description. NO audio transcription.
   - Any fetch failure → still create the note, with `needs-attention: true` in
     frontmatter. Never fail silently.
4. **LLM step (Gemini free tier).** One call: generate TL;DR (1–2 sentences),
   summary (short paragraph/bullets), and 1–3 tags STRICTLY from the 17-tag
   vocabulary. If nothing fits, tag with the closest match AND append a suggested
   new tag to `tag-suggestions.md`. Include the seed notes' style as few-shot
   examples if summaries feel off.
5. **Commit the note** using the CLAUDE.md template, descriptive slug filename,
   empty "My thoughts" section, links to hub pages. Push → Quartz auto-rebuilds.
6. **Fallback client first: GitHub Issue form.** Issue template with a URL field;
   Action triggers on issue open, processes it, comments the new note's link,
   closes the issue. Zero client setup — this is also the test harness.
7. **iOS Shortcut.** Share sheet → accepts URL → optional "quick thought?" prompt
   (skippable) → HTTP POST to the `repository_dispatch` endpoint with a GitHub
   fine-grained token stored in the Shortcut.
8. **Windows bookmarklet.** One-click JS bookmark: grabs current page URL, fires
   the same POST. (Browser extension is a later nice-to-have only if the
   bookmarklet feels janky.)

**Done when:** sharing a YouTube video from the phone and clicking the bookmarklet
on the laptop both produce a correct, tagged, published note without touching
anything else.

---

## Phase 4 — Polish (ongoing, forever)

No deadline; a grab bag to pull from:

- Graph styling: colors by tag/cluster, node sizing, hover previews.
- The life timeline page: entries that link INTO the graph (e.g., "Summer 2026 →
  GeoWatch node → geoint cluster").
- Prompt tuning when AI summaries get annoying (they will).
- Custom domain (~$10/yr — the one allowed expense).
- Hub page upgrades: short "state of my thinking" intros that evolve over time.
- OG images / social cards so shared links look good.
- A `/now` page, RSS feed for the blog, analytics (privacy-friendly, free tier).
- Tag vocabulary review: promote suggestions from `tag-suggestions.md` when ~5+
  notes would use one; merge or retire tags that never cluster.

---

## Pre-Phase-1 homework (pure thinking, no code)

List 10–15 recently consumed things (podcasts, tweets, articles, videos) that would
become the seed notes. If naming ten is hard, that's real information about the
capture habit. If twenty come easily, the garden will thrive.
