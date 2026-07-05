#!/usr/bin/env python3
"""The gardener: keeps the organic taxonomy healthy as the garden scales.

Runs weekly (and on demand) via .github/workflows/gardener.yml:

1. THIN-TAG FOLDING — tags with <2 notes that are past a grace period get
   folded into their best-fit healthy tag (LLM decides), the affected notes
   are rewritten, and the dead hub file is deleted. A hub with `pinned: true`
   in its frontmatter is never folded (owner-curated keepers).
2. ZERO-TAG HEALING — notes that ended up with no tags (LLM hiccup at capture
   time) get retagged from the EXISTING tag set only.

Never mints new tags. Prints a summary; exits 0 even when nothing to do.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import NOTES_DIR, TAGS_DIR, llm_json, slug_tag, today  # noqa: E402

GRACE_DAYS = int(os.environ.get("GARDENER_GRACE_DAYS", "14"))
MIN_NOTES = 2

FOLD_PROMPT = """You maintain the category system of a personal knowledge graph.

All tags with their note counts:
{counts}

These tags are THIN (fewer than {min_notes} notes, older than {grace} days):
{thin}

For each thin tag pick the single existing NON-thin tag that best absorbs it
(a broader neighbor its notes would naturally live under). If genuinely no
listed tag fits, answer "keep".

Return STRICT JSON only: {{"folds": {{"thin-tag": "target-tag-or-keep"}}}}
"""

RETAG_PROMPT = """Pick 1-2 tags for this note, ONLY from this list: {tags}

NOTE TITLE: {title}
TL;DR: {tldr}

Return STRICT JSON only: {{"tags": ["..."]}}
"""


def note_info(f: Path) -> dict:
    text = f.read_text(encoding="utf-8")
    tags_m = re.search(r"^tags:\s*\[([^\]]*)\]", text, re.M)
    return {
        "path": f,
        "text": text,
        "published": not re.search(r"^publish:\s*false", text, re.M),
        "tags": [t.strip() for t in (tags_m.group(1).split(",") if tags_m else []) if t.strip()],
        "date": (re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.M) or [None, "2000-01-01"])[1],
        "title": (re.search(r'^title:\s*"?(.*?)"?\s*$', text, re.M) or [None, f.stem])[1],
        "tldr": (re.search(r"## ⚡ TL;DR\s*\n+([^\n#][^\n]*)", text) or [None, ""])[1].strip(),
    }


def rewrite_tags(info: dict, new_tags: list[str]) -> None:
    text = info["text"]
    text = re.sub(r"^tags:\s*\[[^\]]*\]", f"tags: [{', '.join(new_tags)}]", text, count=1, flags=re.M)
    # Related hub links: swap/dedupe wikilinks that are bare tag references
    related = " · ".join(f"[[{t}]]" for t in new_tags)
    text = re.sub(r"(## Related\s*\n+)(\[\[[^\]|]+\]\]( · \[\[[^\]|]+\]\])*)",
                  lambda m: m.group(1) + related, text, count=1)
    info["path"].write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    notes = [note_info(f) for f in NOTES_DIR.glob("*.md") if f.stem != "index"]
    notes = [n for n in notes if n["published"]]

    counts: dict[str, list[dict]] = {}
    for n in notes:
        for t in n["tags"]:
            counts.setdefault(t, []).append(n)

    pinned = set()
    for f in TAGS_DIR.glob("*.md"):
        if re.search(r"^pinned:\s*true", f.read_text(encoding="utf-8"), re.M):
            pinned.add(f.stem)

    cutoff = (datetime.date.fromisoformat(today()) - datetime.timedelta(days=GRACE_DAYS)).isoformat()
    changed = 0

    # ---- 1. fold thin tags ----------------------------------------------
    thin = []
    for tag, tagged in counts.items():
        if tag in pinned or len(tagged) >= MIN_NOTES:
            continue
        if min(n["date"] for n in tagged) <= cutoff:  # past grace period
            thin.append(tag)

    if thin:
        healthy = {t: len(v) for t, v in counts.items() if t not in thin}
        result, err = llm_json(FOLD_PROMPT.format(
            counts="\n".join(f"{t}: {c}" for t, c in sorted(healthy.items())),
            min_notes=MIN_NOTES, grace=GRACE_DAYS, thin="\n".join(sorted(thin))))
        if result is None:
            print(f"::warning::fold pass skipped: {err}")
        else:
            for old, target in (result.get("folds") or {}).items():
                old, target = slug_tag(old), slug_tag(target)
                if old not in thin or (target != "keep" and target not in healthy):
                    continue
                if target == "keep":
                    print(f"keep: {old}")
                    continue
                for n in counts.get(old, []):
                    new_tags = [t for t in n["tags"] if t != old]
                    if target not in new_tags:
                        new_tags.append(target)
                    rewrite_tags(note_info(n["path"]), new_tags[:3])
                hub = TAGS_DIR / f"{old}.md"
                if hub.exists():
                    hub.unlink()
                print(f"folded: {old} -> {target} ({len(counts.get(old, []))} note(s))")
                changed += 1

    # ---- 2. heal zero-tag notes ------------------------------------------
    all_tags = sorted(t for t in counts if t not in thin) or sorted(counts)
    for n in notes:
        if n["tags"]:
            continue
        result, err = llm_json(RETAG_PROMPT.format(
            tags=", ".join(all_tags), title=n["title"], tldr=n["tldr"] or n["title"]))
        if result is None:
            print(f"::warning::retag skipped for {n['path'].stem}: {err}")
            continue
        new_tags = [slug_tag(t) for t in (result.get("tags") or []) if slug_tag(t) in all_tags][:2]
        if new_tags:
            info = note_info(n["path"])
            text = info["text"].replace("_(untagged — needs attention)_",
                                        " · ".join(f"[[{t}]]" for t in new_tags))
            info["path"].write_text(text, encoding="utf-8", newline="\n")
            rewrite_tags(note_info(n["path"]), new_tags)
            # tags valid now: drop the needs-attention flag if it was tag-related
            info = note_info(n["path"])
            info["path"].write_text(
                re.sub(r"^needs-attention: true\n", "", info["text"], flags=re.M),
                encoding="utf-8", newline="\n")
            print(f"healed: {n['path'].stem} -> {new_tags}")
            changed += 1

    print(f"gardener: {changed} change(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
