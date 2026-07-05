#!/usr/bin/env python3
"""Emit public/static/brain-meta.json: {slug: YYYY-MM-DD} for the Brain's
time-lapse scrubber. Notes/blog use their frontmatter date; a tag hub's birth
date is the earliest date among notes carrying that tag. Run after
`npx quartz build` (the deploy workflow does this)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
OUT = ROOT / "public" / "static" / "brain-meta.json"

dates: dict[str, str] = {}
tag_first: dict[str, str] = {}

for folder, prefix in (("notes", "notes/"), ("blog", "blog/")):
    for f in (CONTENT / folder).glob("*.md"):
        if f.stem == "index":
            continue
        text = f.read_text(encoding="utf-8")
        if re.search(r"^publish:\s*false", text, re.M):
            continue
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
        if not m:
            continue
        date = m.group(1)
        dates[prefix + f.stem] = date
        tags = re.search(r"^tags:\s*\[([^\]]*)\]", text, re.M)
        for tag in (tags.group(1).split(",") if tags else []):
            tag = tag.strip()
            if tag and (tag not in tag_first or date < tag_first[tag]):
                tag_first[tag] = date

for tag, date in tag_first.items():
    dates["tags/" + tag] = date

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"dates": dates}, indent=0), encoding="utf-8")
print(f"brain-meta.json: {len(dates)} dated nodes")
