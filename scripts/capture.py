#!/usr/bin/env python3
"""BrainSite capture pipeline: URL in, templated garden note out.

Usage (local):
    python scripts/capture.py --url https://... [--thought "..."]

In GitHub Actions the script resolves its inputs from the event payload:
    python scripts/capture.py --from-event

Design rules (from CLAUDE.md):
- Tags are ORGANIC: the LLM proposes 1-3 kebab-case categories from the
  content itself. A second canonicalization pass checks every proposed tag
  against all tags already used in the garden and maps near-duplicates onto
  the existing tag (reason: "agents" vs "ai-agents" vs "agentic-systems"
  fragments the graph into mush).
- A hub page is auto-created in content/notes/ the first time a tag is used.
- Any fetch/LLM failure still creates the note, with `needs-attention: true`
  in frontmatter. Never fail silently.
- Tweets always store text + author in the body; embeds are enhancement only.
- Notes default publish: true (explicit-publish plugin requires the field).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

def today() -> str:
    """Owner-local date (US Eastern) — runners are UTC, which stamped evening
    captures with tomorrow's date."""
    return datetime.datetime.now(ZoneInfo("America/New_York")).date().isoformat()

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = REPO_ROOT / "content" / "notes"   # captures only (the garden feed)
TAGS_DIR = REPO_ROOT / "content" / "tags"     # tag hub pages: framing text +
                                              # Quartz auto-lists tagged content
INDEX_MD = REPO_ROOT / "content" / "index.md"

PODCAST_DOMAINS = (
    "open.spotify.com", "podcasts.apple.com", "overcast.fm", "pca.st",
    "castro.fm", "pocketcasts.com", "podcasts.google.com",
)

MAX_CONTENT_CHARS = 12_000
HTTP_TIMEOUT = 20
UA = {"User-Agent": "Mozilla/5.0 (BrainSite capture pipeline; +https://kyle-briggs8.github.io)"}


# ---------------------------------------------------------------- media type

def detect_media(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    if host in ("youtube.com", "youtu.be", "m.youtube.com"):
        return "video"
    if host in ("x.com", "twitter.com", "mobile.twitter.com"):
        return "tweet"
    if any(host == d or host.endswith("." + d) for d in PODCAST_DOMAINS):
        return "podcast"
    return "article"


# ------------------------------------------------------------------ fetchers

class FetchResult:
    def __init__(self, title="", author="", text="", tweet_text="", ok=True, error=""):
        self.title, self.author, self.text = title, author, text
        self.tweet_text = tweet_text  # verbatim tweet text (stored in note body)
        self.ok, self.error = ok, error


def _youtube_video_id(url: str) -> str | None:
    p = urllib.parse.urlparse(url)
    if p.netloc.endswith("youtu.be"):
        return p.path.lstrip("/").split("/")[0] or None
    qs = urllib.parse.parse_qs(p.query)
    if "v" in qs:
        return qs["v"][0]
    m = re.search(r"/(?:shorts|embed|live)/([\w-]{6,})", p.path)
    return m.group(1) if m else None


def fetch_video(url: str) -> FetchResult:
    title = author = transcript = ""
    errors = []
    try:
        oe = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=HTTP_TIMEOUT, headers=UA,
        )
        oe.raise_for_status()
        data = oe.json()
        title, author = data.get("title", ""), data.get("author_name", "")
    except Exception as e:  # noqa: BLE001 - collect, never crash
        errors.append(f"oEmbed: {e}")

    vid = _youtube_video_id(url)
    if vid:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            try:  # v1.x API
                fetched = YouTubeTranscriptApi().fetch(vid)
                transcript = " ".join(s.text for s in fetched)
            except AttributeError:  # pre-1.0 API
                fetched = YouTubeTranscriptApi.get_transcript(vid)
                transcript = " ".join(s["text"] for s in fetched)
        except Exception as e:  # noqa: BLE001
            errors.append(f"transcript: {e}")
    else:
        errors.append("could not parse video id")

    if not transcript:
        # YouTube blocks transcript fetches from many datacenter IPs (e.g. GitHub
        # runners) — fall back to the watch page's description so the LLM has
        # more than a bare title to work with.
        try:
            page = requests.get(url, timeout=HTTP_TIMEOUT, headers=UA).text
            m = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', page)
            if m:
                desc = m.group(1).encode().decode("unicode_escape", errors="ignore")
                transcript = f"(video description, transcript unavailable)\n{desc}"
        except Exception as e:  # noqa: BLE001
            errors.append(f"description: {e}")

    ok = bool(title or transcript)
    return FetchResult(title, author, transcript, ok=ok, error="; ".join(errors))


def fetch_tweet(url: str) -> FetchResult:
    # publish.twitter.com oEmbed is keyless; normalize x.com -> twitter.com
    norm = re.sub(r"^https?://(www\.)?(x|mobile\.twitter)\.com", "https://twitter.com", url)
    try:
        oe = requests.get(
            "https://publish.twitter.com/oembed",
            params={"url": norm, "omit_script": "true", "dnt": "true"},
            timeout=HTTP_TIMEOUT, headers=UA,
        )
        oe.raise_for_status()
        data = oe.json()
        html = data.get("html", "")
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"(&mdash;.*)$", "", text).strip()  # trim trailing attribution
        author = data.get("author_name", "")
        return FetchResult(
            title=f"Tweet by {author}" if author else "Tweet",
            author=author, text=text, tweet_text=text,
            ok=bool(text), error="" if text else "empty oEmbed html",
        )
    except Exception as e:  # noqa: BLE001
        return FetchResult(ok=False, error=f"tweet oEmbed: {e}")


def _spotify_type_id(url: str) -> tuple[str, str] | None:
    m = re.search(r"open\.spotify\.com/(episode|show|track|album)/([A-Za-z0-9]+)", url)
    return (m.group(1), m.group(2)) if m else None


def _rss_episode_description(show: str, episode_title: str) -> str:
    """Keyless chain to real show notes: iTunes Search maps the show name to
    its public RSS feed; the feed item matching the episode title carries the
    description Spotify won't serve to scrapers."""
    search = requests.get(
        "https://itunes.apple.com/search",
        params={"media": "podcast", "limit": 3, "term": show},
        timeout=HTTP_TIMEOUT, headers=UA,
    ).json()
    for result in search.get("results", []):
        feed_url = result.get("feedUrl")
        if not feed_url:
            continue
        rss = requests.get(feed_url, timeout=HTTP_TIMEOUT, headers=UA).text
        want = re.sub(r"\W+", " ", episode_title).strip().lower()
        for item in re.finditer(r"<item>(.*?)</item>", rss, re.S):
            block = item.group(1)
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
            if not t:
                continue
            have = re.sub(r"\W+", " ", t.group(1)).strip().lower()
            if want and (want == have or want in have or have in want):
                d = (re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.S)
                     or re.search(r"<itunes:summary>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</itunes:summary>", block, re.S))
                if d:
                    text = re.sub(r"<[^>]+>", " ", d.group(1))
                    return re.sub(r"\s+", " ", text).strip()
    return ""


def fetch_spotify(url: str) -> FetchResult:
    """Spotify's episode pages are a JS wall. oEmbed gives episode + show name
    keylessly; the show's public RSS (found via iTunes Search) gives the notes."""
    title = author = desc = ""
    errors = []
    try:
        oe = requests.get("https://open.spotify.com/oembed", params={"url": url},
                          timeout=HTTP_TIMEOUT, headers=UA)
        oe.raise_for_status()
        title = oe.json().get("title", "")
    except Exception as e:  # noqa: BLE001
        errors.append(f"spotify oEmbed: {e}")

    tid = _spotify_type_id(url)
    if tid:
        try:
            page = requests.get(f"https://open.spotify.com/embed/{tid[0]}/{tid[1]}",
                                timeout=HTTP_TIMEOUT, headers=UA).text
            m = re.search(r'"subtitle":"((?:[^"\\]|\\.)*)"', page)
            if m:
                author = json.loads(f'"{m.group(1)}"')
        except Exception as e:  # noqa: BLE001
            errors.append(f"spotify embed page: {e}")

    if title and author:
        try:
            desc = _rss_episode_description(author, title)
        except Exception as e:  # noqa: BLE001
            errors.append(f"rss lookup: {e}")

    if title and author:
        title = f"{title} ({author})"
    ok = bool(title or desc)
    return FetchResult(title, author, desc, ok=ok, error="; ".join(errors))


def fetch_podcast(url: str) -> FetchResult:
    if "open.spotify.com" in url:
        return fetch_spotify(url)
    return fetch_article(url)  # other podcast hosts: scrape the episode page


def fetch_article(url: str) -> FetchResult:
    """Articles AND podcasts (episode page show notes). Readability-style."""
    try:
        import trafilatura
        html = trafilatura.fetch_url(url)
        if not html:
            resp = requests.get(url, timeout=HTTP_TIMEOUT, headers=UA)
            resp.raise_for_status()
            html = resp.text
        meta = trafilatura.extract_metadata(html)
        text = trafilatura.extract(html, include_comments=False) or ""
        title = (meta.title if meta else "") or ""
        author = (meta.author if meta else "") or ""
        return FetchResult(title, author, text, ok=bool(text), error="" if text else "no main text extracted")
    except Exception as e:  # noqa: BLE001
        return FetchResult(ok=False, error=f"article fetch: {e}")


FETCHERS = {"video": fetch_video, "tweet": fetch_tweet, "article": fetch_article, "podcast": fetch_podcast}


# ----------------------------------------------------------------- LLM calls

def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in LLM response")
    return json.loads(raw[start : end + 1])


def call_gemini(prompt: str) -> dict:
    key = os.environ["GEMINI_API_KEY"].strip().lstrip("﻿")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key},  # newer AI-Studio keys reject ?key= query auth
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    return _extract_json(resp.json()["candidates"][0]["content"]["parts"][0]["text"])


def call_groq(prompt: str) -> dict:
    key = os.environ["GROQ_API_KEY"].strip().lstrip("﻿")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return _extract_json(resp.json()["choices"][0]["message"]["content"])


def llm_json(prompt: str) -> tuple[dict | None, str]:
    """Gemini first, Groq fallback. Returns (parsed_json, error_string)."""
    errors = []
    for name, fn, env in (("gemini", call_gemini, "GEMINI_API_KEY"), ("groq", call_groq, "GROQ_API_KEY")):
        if not os.environ.get(env):
            errors.append(f"{name}: no {env}")
            continue
        try:
            return fn(prompt), ""
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    return None, "; ".join(errors)


# ------------------------------------------------------- pass 1: summarize

SUMMARIZE_PROMPT = """You are the summarizer for a personal "digital garden" of saved media.
Given the content below, return STRICT JSON only — no preamble, no markdown fences.

{{
  "title": "descriptive human-readable note title",
  "slug": "kebab-case-filename-slug (short, descriptive, no dates)",
  "author": "creator of the source content, or null",
  "tldr": "1-2 sentence TL;DR",
  "summary_md": "short paragraph OR up to 5 markdown bullets",
  "tags": ["1 to 3 kebab-case topical categories that best describe this content"]
}}

TAG RULES:
- Tags are categories for a knowledge graph: broad enough to recur across many
  saved items (e.g. "agentic-systems", "geoint", "personal-finance"), never
  one-off descriptors (bad: "this-specific-paper", "cool-video").
- Prefer FEWER, BROADER tags: 1-2 is the norm, 3 only when truly warranted.
  Never zero.

MEDIA TYPE: {media}
SOURCE URL: {url}
KNOWN TITLE: {title}
KNOWN AUTHOR: {author}

CONTENT:
{content}
"""


def run_summarize(media: str, url: str, fetched: FetchResult) -> tuple[dict | None, str]:
    prompt = SUMMARIZE_PROMPT.format(
        media=media, url=url,
        title=fetched.title or "(unknown)", author=fetched.author or "(unknown)",
        content=(fetched.text or "(fetch failed — summarize from title/URL only)")[:MAX_CONTENT_CHARS],
    )
    return llm_json(prompt)


# --------------------------------------------- pass 2: tag canonicalization

CANONICALIZE_PROMPT = """You maintain the category system of a personal knowledge graph.
New content proposed these tags: {proposed}

Tags ALREADY IN USE in the graph: {existing}

For each proposed tag decide: can it live under an EXISTING tag (synonym,
singular/plural, narrower/broader phrasing, or a subtopic that would naturally
cluster with it)? If yes, replace it with that existing tag. STRONGLY prefer
existing tags — a graph with few well-fed categories beats one with many thin
ones. Mint a new tag ONLY when the content's core subject fits no existing tag
even loosely; most content should map entirely onto existing tags.

Return STRICT JSON only:
{{
  "tags": ["final 1-3 tags, deduplicated"],
  "new": {{"each-genuinely-new-tag": "one-sentence description of what this category covers"}}
}}

Examples of what MUST be merged: "ai-agents" or "llm-agents" -> "agentic-systems";
"investing" -> "markets-and-investing"; "startup" -> "startups".
"""


def slug_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def existing_tags() -> set[str]:
    """Every tag in the garden: note frontmatter + existing tag hub files."""
    tags: set[str] = set()
    for f in NOTES_DIR.glob("*.md"):
        m = re.search(r"^tags:\s*\[([^\]]*)\]", f.read_text(encoding="utf-8"), re.M)
        if m:
            tags.update(t.strip() for t in m.group(1).split(",") if t.strip())
    if TAGS_DIR.exists():
        tags.update(f.stem for f in TAGS_DIR.glob("*.md") if f.stem != "index")
    return tags


def canonicalize(proposed: list[str], known: set[str]) -> tuple[list[str], dict[str, str], str]:
    """Returns (final_tags, {new_tag: description}, error). Never raises."""
    proposed = [slug_tag(t) for t in proposed if slug_tag(t)][:3]
    if not proposed:
        return [], {}, "no tags proposed"

    # cheap algorithmic folds first: exact + plural/singular matches
    folded = []
    for t in proposed:
        if t in known:
            folded.append(t)
        elif t.rstrip("s") in known:
            folded.append(t.rstrip("s"))
        elif (t + "s") in known:
            folded.append(t + "s")
        else:
            folded.append(t)
    proposed = list(dict.fromkeys(folded))

    novel = [t for t in proposed if t not in known]
    if not novel:  # everything already canonical
        return proposed, {}, ""

    result, err = llm_json(CANONICALIZE_PROMPT.format(
        proposed=json.dumps(proposed), existing=json.dumps(sorted(known))))
    if result is None:
        # LLM check unavailable: keep known tags, accept novel ones as-is
        return proposed, {t: "" for t in novel}, f"canonicalization skipped: {err}"

    final = list(dict.fromkeys(slug_tag(t) for t in result.get("tags", []) if slug_tag(t)))[:3]
    if not final:
        final = proposed
    new = {slug_tag(k): (v or "") for k, v in (result.get("new") or {}).items()
           if slug_tag(k) in final and slug_tag(k) not in known}
    return final, new, ""


def ensure_hub(tag: str, description: str) -> Path | None:
    """Create content/tags/<tag>.md if this tag has no hub page yet.
    Quartz's tag page renders this file's body ABOVE the auto-generated
    listing of all content carrying the tag."""
    TAGS_DIR.mkdir(parents=True, exist_ok=True)
    path = TAGS_DIR / f"{tag}.md"
    if path.exists():
        return None
    title = tag.replace("-", " ").title()
    desc = description.strip() or f"Notes tagged `#{tag}`."
    path.write_text(
        f"---\ntitle: {title}\npublish: true\n---\n\n"
        f"*Hub page for `#{tag}` — auto-created by the capture pipeline.*\n\n{desc}\n",
        encoding="utf-8", newline="\n",
    )
    return path


# --------------------------------------------- pass 3: semantic cross-links

RELATED_PROMPT = """You link a new note into a personal knowledge graph.

NEW NOTE: {title}
TL;DR: {tldr}

EXISTING NOTES (slug | title | tl;dr):
{catalog}

Pick 0-3 existing notes whose IDEAS genuinely connect to the new note —
shared specific concepts, one illuminates the other, same story from another
angle. Do NOT pick notes that merely share a broad topic. Zero is a fine
answer.

Return STRICT JSON only: {{"related": ["slug-1", "slug-2"]}}
"""


def _note_catalog(exclude_slug: str) -> list[tuple[str, str, str]]:
    """(slug, title, tldr) for every published note, for the see-also pass."""
    out = []
    for f in sorted(NOTES_DIR.glob("*.md")):
        if f.stem in ("index", exclude_slug):
            continue
        text = f.read_text(encoding="utf-8")
        if re.search(r"^publish:\s*false", text, re.M):
            continue
        t = re.search(r'^title:\s*"?(.*?)"?\s*$', text, re.M)
        tl = re.search(r"## ⚡ TL;DR\s*\n+([^\n#][^\n]*)", text)
        out.append((f.stem, t.group(1).replace('\\"', '"') if t else f.stem,
                    (tl.group(1).strip() if tl else "")[:220]))
    return out


def find_related(slug: str, title: str, tldr: str) -> list[tuple[str, str]]:
    """LLM picks 0-3 genuinely related existing notes. Never raises."""
    catalog = _note_catalog(exclude_slug=slug)
    if not catalog:
        return []
    listing = "\n".join(f"{s} | {t} | {d}" for s, t, d in catalog)
    result, err = llm_json(RELATED_PROMPT.format(title=title, tldr=tldr, catalog=listing))
    if result is None:
        print(f"::warning::see-also pass skipped: {err}")
        return []
    valid = {s: t for s, t, _ in catalog}
    return [(s, valid[s]) for s in (result.get("related") or [])[:3] if s in valid]


# ------------------------------------------------------------- note assembly

def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60].rstrip("-") or "untitled-capture"


def unique_note_path(slug: str) -> Path:
    path = NOTES_DIR / f"{slug}.md"
    n = 2
    while path.exists():
        path = NOTES_DIR / f"{slug}-{n}.md"
        n += 1
    return path


def yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_embed(media: str, url: str, title: str, fetched: FetchResult) -> str:
    if media == "video":
        return f"![]({url})"
    if media == "tweet":
        text = fetched.tweet_text or "(tweet text unavailable — see needs-attention)"
        author = fetched.author or "unknown author"
        return f"> {text}\n>\n> — {author}\n\n*Original: [{url}]({url})*"
    if media == "podcast":
        tid = _spotify_type_id(url)
        if tid:  # real player embed; the plain link below it is the fallback
            return (f'<iframe src="https://open.spotify.com/embed/{tid[0]}/{tid[1]}" '
                    f'width="100%" height="152" frameborder="0" loading="lazy" '
                    f'allow="encrypted-media"></iframe>\n\n'
                    f"🎧 [{title or url}]({url})")
        return f"🎧 [{title or url}]({url})"
    return f"🔗 [{title or url}]({url})"


def build_note(url, media, thought, fetched, llm, llm_error, tags, see_also=()) -> tuple[Path, str]:
    date_str = today()
    needs_attention = (not fetched.ok) or (llm is None) or (not tags)

    title = (llm or {}).get("title") or fetched.title or url
    author = (llm or {}).get("author") or fetched.author or ""
    slug = slugify((llm or {}).get("slug") or title)

    tldr = (llm or {}).get("tldr") or "_(summary pending — automatic capture could not summarize this source)_"
    summary = (llm or {}).get("summary_md") or f"_(no summary generated: {llm_error or fetched.error or 'unknown'})_"

    fm = ["---", f"title: {yaml_escape(title)}", f"source: {url}"]
    if author:
        fm.append(f"author: {yaml_escape(author)}")
    fm += [f"media: {media}", f"date: {date_str}", f"tags: [{', '.join(tags)}]", "publish: true"]
    if needs_attention:
        fm.append("needs-attention: true")
    fm.append("---")

    body = [build_embed(media, url, title, fetched), "", "## ⚡ TL;DR", "", tldr, "",
            "## Summary", "", "*Summary is AI-generated — machine voice, not mine.*", "", summary, "",
            "## 💭 My thoughts", ""]
    if thought:
        body += [thought, ""]
    related = " · ".join(f"[[{t}]]" for t in tags) or "_(untagged — needs attention)_"
    body += ["## Related", "", related, ""]
    if see_also:
        body += ["**See also:** " + " · ".join(f"[[{s}|{t}]]" for s, t in see_also), ""]

    path = unique_note_path(slug)
    path.write_text("\n".join(fm) + "\n\n" + "\n".join(body), encoding="utf-8", newline="\n")
    return path, title


RECENT_START = "<!-- RECENT-NOTES:START -->"
RECENT_END = "<!-- RECENT-NOTES:END -->"
MAX_RECENT = 6


def update_recent_strip(slug: str, title: str, media: str) -> bool:
    """Prepend a card for the new note to the homepage strip (between markers)."""
    if not INDEX_MD.exists():
        return False
    text = INDEX_MD.read_text(encoding="utf-8")
    if RECENT_START not in text or RECENT_END not in text:
        return False
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
    card = (f'<a class="card" href="/notes/{slug}">'
            f'<span class="card-kind">{media}</span>'
            f'<span class="card-title">{safe_title}</span></a>')
    before, rest = text.split(RECENT_START, 1)
    inside, after = rest.split(RECENT_END, 1)
    items = [ln for ln in inside.splitlines()
             if ln.strip().startswith('<a class="card"') and f'href="/notes/{slug}"' not in ln]
    items.insert(0, card)
    new_inside = "\n" + "\n".join(items[:MAX_RECENT]) + "\n"
    INDEX_MD.write_text(before + RECENT_START + new_inside + RECENT_END + after,
                        encoding="utf-8", newline="\n")
    return True


# -------------------------------------------------------------- event inputs

def params_from_event() -> tuple[str, str]:
    """Resolve (url, thought) from the GitHub Actions event payload."""
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    event = json.loads(Path(event_path).read_text(encoding="utf-8")) if event_path else {}

    if event_name == "repository_dispatch":
        payload = event.get("client_payload", {}) or {}
        return payload.get("url", ""), payload.get("quick_thought", "") or ""

    if event_name == "workflow_dispatch":
        inputs = event.get("inputs", {}) or {}
        return inputs.get("url", ""), inputs.get("quick_thought", "") or ""

    if event_name == "issues":
        body = (event.get("issue", {}) or {}).get("body", "") or ""
        url_match = re.search(r"https?://\S+", body)
        url = url_match.group(0).rstrip(">)],.") if url_match else ""
        thought = ""
        m = re.search(r"###\s*Quick thought[^\n]*\n+(.*?)(?=\n###|\Z)", body, re.S)
        if m:
            candidate = m.group(1).strip()
            if candidate and candidate.lower() != "_no response_":
                thought = candidate
        return url, thought

    return "", ""


# ----------------------------------------------------------------------- main

def find_existing_capture(url: str) -> Path | None:
    """Exact-URL duplicate check against every note's `source:` frontmatter."""
    for f in NOTES_DIR.glob("*.md"):
        if f.stem == "index":
            continue
        m = re.search(r"^source:\s*(\S+)\s*$", f.read_text(encoding="utf-8"), re.M)
        if m and m.group(1) == url:
            return f
    return None


def append_thought(note_path: Path, thought: str) -> bool:
    """Add a re-share's quick thought to the existing note's My thoughts section."""
    text = note_path.read_text(encoding="utf-8")
    marker = "## 💭 My thoughts\n"
    idx = text.find(marker)
    if idx == -1:
        return False
    insert_at = idx + len(marker)
    stamp = today()
    addition = f"\n{thought} *({stamp})*\n"
    note_path.write_text(text[:insert_at] + addition + text[insert_at:],
                         encoding="utf-8", newline="\n")
    return True


def strip_add(note_path: Path) -> int:
    """Re-insert an existing note into the homepage strip. Used by the workflow
    to repair the strip after a push race: the only file two writers share is
    content/index.md, so on rebase conflict we take the remote version and
    replay just our card on top of it."""
    fm = note_path.read_text(encoding="utf-8")
    title_m = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M)
    media_m = re.search(r"^media:\s*(\w+)", fm, re.M)
    title = title_m.group(1).replace('\\"', '"') if title_m else note_path.stem
    media = media_m.group(1) if media_m else "article"
    ok = update_recent_strip(note_path.stem, title, media)
    print(f"strip-add: {note_path.stem} ({'ok' if ok else 'markers missing'})")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url")
    ap.add_argument("--thought", default="")
    ap.add_argument("--from-event", action="store_true",
                    help="resolve url/thought from the GitHub Actions event payload")
    ap.add_argument("--strip-add", metavar="NOTE_PATH",
                    help="only re-insert the given note into the homepage strip")
    args = ap.parse_args()

    if args.strip_add:
        return strip_add(Path(args.strip_add))

    url, thought = (params_from_event() if args.from_event else (args.url or "", args.thought))
    if not url or not url.startswith(("http://", "https://")):
        print(f"::error::no valid URL to capture (got: {url!r})")
        return 1

    existing = find_existing_capture(url)
    if existing:
        title_m = re.search(r'^title:\s*"?(.*?)"?\s*$', existing.read_text(encoding="utf-8"), re.M)
        title = title_m.group(1).replace('\\"', '"') if title_m else existing.stem
        print(f"duplicate: already captured as {existing.stem} - skipping re-capture")
        if thought:
            if append_thought(existing, thought):
                print("quick thought appended to the existing note's My thoughts section")
            else:
                print("::warning::could not find My thoughts section to append to")
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a", encoding="utf-8") as f:
                f.write(f"note_slug={existing.stem}\nnote_title={title}\nduplicate=true\n")
        return 0

    media = detect_media(url)
    print(f"capture: {url} (media={media})")

    fetched = FETCHERS[media](url)
    if not fetched.ok:
        print(f"::warning::fetch failed: {fetched.error}")

    llm, llm_error = run_summarize(media, url, fetched)
    if llm is None:
        print(f"::warning::LLM summarize failed: {llm_error}")

    tags, new_tags, canon_err = canonicalize((llm or {}).get("tags", []), existing_tags())
    if canon_err:
        print(f"::warning::{canon_err}")
    for tag, desc in new_tags.items():
        created = ensure_hub(tag, desc)
        if created:
            print(f"new hub: {created.relative_to(REPO_ROOT)}")

    see_also = []
    if llm:
        see_also = find_related("", llm.get("title") or fetched.title or "",
                                llm.get("tldr") or "")

    path, title = build_note(url, media, thought, fetched, llm, llm_error, tags, see_also)
    slug = path.stem
    update_recent_strip(slug, title, media)

    print(f"note: {path.relative_to(REPO_ROOT)} | title: {title} | tags: {tags} | new hubs: {list(new_tags)}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"note_slug={slug}\nnote_title={title}\nduplicate=false\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
