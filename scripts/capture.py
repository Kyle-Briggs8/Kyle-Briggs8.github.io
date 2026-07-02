#!/usr/bin/env python3
"""BrainSite capture pipeline: URL in, templated garden note out.

Usage (local):
    python scripts/capture.py --url https://... [--thought "..."]

In GitHub Actions the script can instead resolve its inputs from the event
payload (repository_dispatch, workflow_dispatch handled by the workflow,
issues parsed from the issue body):
    python scripts/capture.py --from-event

Design rules (from CLAUDE.md):
- Tags come ONLY from the 17-tag controlled vocabulary; never invented.
- If nothing fits, tag the closest match AND append a suggestion to
  tag-suggestions.md for human review. No `misc` tag.
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

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = REPO_ROOT / "content" / "notes"
INDEX_MD = REPO_ROOT / "content" / "index.md"
TAG_SUGGESTIONS = REPO_ROOT / "tag-suggestions.md"

VOCABULARY = [
    "agentic-systems", "llm-evals", "rag-and-retrieval", "ai-security",
    "ml-infrastructure", "geoint", "cybersecurity",
    "gov-tech", "startups", "venture-capital", "big-tech",
    "personal-finance", "markets-and-investing",
    "career-strategy", "fitness", "math-and-puzzles", "ideas-worth-stealing",
]

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


FETCHERS = {"video": fetch_video, "tweet": fetch_tweet, "article": fetch_article, "podcast": fetch_article}


# ----------------------------------------------------------------------- LLM

PROMPT_TEMPLATE = """You are the summarizer for a personal "digital garden" of saved media.
Given the content below, return STRICT JSON only — no preamble, no markdown fences.

{{
  "title": "descriptive human-readable note title",
  "slug": "kebab-case-filename-slug (short, descriptive, no dates)",
  "author": "creator of the source content, or null",
  "tldr": "1-2 sentence TL;DR",
  "summary_md": "short paragraph OR up to 5 markdown bullets",
  "tags": ["1 to 3 tags, ONLY from the allowed list below"],
  "suggested_tag": "kebab-case suggestion if the allowed list fits poorly, else null"
}}

RULES:
- tags MUST come from this exact list (pick the closest matches, 1-3 of them,
  never invent new ones, never zero): {vocab}
- If nothing fits well, still pick the single closest tag AND set suggested_tag.

MEDIA TYPE: {media}
SOURCE URL: {url}
KNOWN TITLE: {title}
KNOWN AUTHOR: {author}

CONTENT:
{content}
"""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in LLM response")
    return json.loads(raw[start : end + 1])


def call_gemini(prompt: str) -> dict:
    key = os.environ["GEMINI_API_KEY"]
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
    key = os.environ["GROQ_API_KEY"]
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


def run_llm(media: str, url: str, fetched: FetchResult) -> tuple[dict | None, str]:
    """Gemini first, Groq fallback. Returns (result, error_string)."""
    prompt = PROMPT_TEMPLATE.format(
        vocab=", ".join(VOCABULARY), media=media, url=url,
        title=fetched.title or "(unknown)", author=fetched.author or "(unknown)",
        content=(fetched.text or "(fetch failed — summarize from title/URL only)")[:MAX_CONTENT_CHARS],
    )
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
    icon = "🎧" if media == "podcast" else "🔗"
    label = title or url
    return f"{icon} [{label}]({url})"


def build_note(url, media, thought, fetched, llm, llm_error) -> tuple[Path, str, list[str], str | None]:
    today = datetime.date.today().isoformat()
    needs_attention = (not fetched.ok) or (llm is None)

    title = (llm or {}).get("title") or fetched.title or url
    author = (llm or {}).get("author") or fetched.author or ""
    slug = slugify((llm or {}).get("slug") or title)

    tags = [t for t in (llm or {}).get("tags", []) if t in VOCABULARY][:3]
    suggested = (llm or {}).get("suggested_tag") or None
    if suggested in VOCABULARY:
        suggested = None
    if not tags:  # rule 4: never force a bogus tag; flag instead
        needs_attention = True

    tldr = (llm or {}).get("tldr") or "_(summary pending — automatic capture could not summarize this source)_"
    summary = (llm or {}).get("summary_md") or f"_(no summary generated: {llm_error or fetched.error or 'unknown'})_"

    fm = ["---", f"title: {yaml_escape(title)}", f"source: {url}"]
    if author:
        fm.append(f"author: {yaml_escape(author)}")
    fm += [f"media: {media}", f"date: {today}", f"tags: [{', '.join(tags)}]", "publish: true"]
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

    path = unique_note_path(slug)
    path.write_text("\n".join(fm) + "\n\n" + "\n".join(body), encoding="utf-8", newline="\n")
    return path, title, tags, suggested


RECENT_START = "<!-- RECENT-NOTES:START -->"
RECENT_END = "<!-- RECENT-NOTES:END -->"


def update_recent_strip(slug: str, title: str) -> bool:
    """Prepend the new note to the homepage strip (between markers), keep 5."""
    if not INDEX_MD.exists():
        return False
    text = INDEX_MD.read_text(encoding="utf-8")
    if RECENT_START not in text or RECENT_END not in text:
        return False
    before, rest = text.split(RECENT_START, 1)
    inside, after = rest.split(RECENT_END, 1)
    items = [ln for ln in inside.splitlines() if ln.strip().startswith("- ")]
    items.insert(0, f"- [[notes/{slug}|{title}]]")
    new_inside = "\n" + "\n".join(items[:5]) + "\n"
    INDEX_MD.write_text(before + RECENT_START + new_inside + RECENT_END + after,
                        encoding="utf-8", newline="\n")
    return True


def append_tag_suggestion(suggestion: str, url: str, title: str) -> None:
    line = f"- `{suggestion}` — suggested for [{title}]({url}) on {datetime.date.today().isoformat()}\n"
    header = "# Tag suggestions\n\nAppended by the capture pipeline when the vocabulary fits poorly.\nPromote to CLAUDE.md vocabulary manually when ~5+ notes would use one.\n\n"
    if TAG_SUGGESTIONS.exists():
        TAG_SUGGESTIONS.write_text(TAG_SUGGESTIONS.read_text(encoding="utf-8") + line, encoding="utf-8", newline="\n")
    else:
        TAG_SUGGESTIONS.write_text(header + line, encoding="utf-8", newline="\n")


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

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url")
    ap.add_argument("--thought", default="")
    ap.add_argument("--from-event", action="store_true",
                    help="resolve url/thought from the GitHub Actions event payload")
    args = ap.parse_args()

    url, thought = (params_from_event() if args.from_event else (args.url or "", args.thought))
    if not url or not url.startswith(("http://", "https://")):
        print(f"::error::no valid URL to capture (got: {url!r})")
        return 1

    media = detect_media(url)
    print(f"capture: {url} (media={media})")

    fetched = FETCHERS[media](url)
    if not fetched.ok:
        print(f"::warning::fetch failed: {fetched.error}")

    llm, llm_error = run_llm(media, url, fetched)
    if llm is None:
        print(f"::warning::LLM step failed: {llm_error}")

    path, title, tags, suggested = build_note(url, media, thought, fetched, llm, llm_error)
    slug = path.stem
    update_recent_strip(slug, title)
    if suggested:
        append_tag_suggestion(suggested, url, title)

    print(f"note: {path.relative_to(REPO_ROOT)} | title: {title} | tags: {tags} | suggested: {suggested}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"note_slug={slug}\nnote_title={title}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
