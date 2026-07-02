# CAPTURE.md — how to send URLs to the garden

URL in → published note out, ~2 minutes, zero manual steps. Backend:
`.github/workflows/capture.yml` → `scripts/capture.py`.

## API contract

All clients POST a `repository_dispatch` event:

```
POST https://api.github.com/repos/Kyle-Briggs8/Kyle-Briggs8.github.io/dispatches
Authorization: Bearer <FINE_GRAINED_TOKEN>
Accept: application/vnd.github+json
Content-Type: application/json

{"event_type": "capture-url",
 "client_payload": {"url": "https://…", "quick_thought": "optional"}}
```

A `204 No Content` response means it worked.

### Token setup (once)

GitHub → Settings → Developer settings → Fine-grained personal access tokens →
Generate new token. Scope it to **only this repository** with **Contents:
Read and write** permission (that's what `repository_dispatch` requires).
Set a long expiry. This token can push to this repo — treat it accordingly.

## Client 1 — GitHub Issue form (zero setup, also the test harness)

Open a [📥 Capture URL issue](https://github.com/Kyle-Briggs8/Kyle-Briggs8.github.io/issues/new?template=capture.yml),
paste the URL, submit. The Action processes it, comments the note link, and
closes the issue. Works from any device that can open GitHub.

## Client 2 — iOS Shortcut (share sheet)

Build once in the Shortcuts app:

1. New Shortcut → rename it "Save to garden" → Shortcut details →
   enable **Show in Share Sheet**, accept types: **URLs, Safari web pages**.
2. Add action **Get URLs from Input** (input: Shortcut Input).
3. Add action **Ask for Input** → Text, prompt "Quick thought?" →
   turn OFF "Require input" (so you can skip it).
4. Add action **Get Contents of URL**:
   - URL: `https://api.github.com/repos/Kyle-Briggs8/Kyle-Briggs8.github.io/dispatches`
   - Method: POST
   - Headers: `Authorization` = `Bearer <token>`, `Accept` = `application/vnd.github+json`
   - Request Body: JSON →
     `event_type` = `capture-url` (Text), and a `client_payload` dictionary with
     `url` = *URLs* variable, `quick_thought` = *Provided Input* variable.
5. Add action **Show Notification** → "Sent to garden 🌱".

Then: any app → Share → "Save to garden".

## Client 3 — Windows bookmarklet (one-click from the browser)

Create a bookmark whose URL is the following (replace `PASTE_TOKEN_HERE`):

```javascript
javascript:(()=>{const t='PASTE_TOKEN_HERE';fetch('https://api.github.com/repos/Kyle-Briggs8/Kyle-Briggs8.github.io/dispatches',{method:'POST',headers:{'Authorization':'Bearer '+t,'Accept':'application/vnd.github+json','Content-Type':'application/json'},body:JSON.stringify({event_type:'capture-url',client_payload:{url:location.href}})}).then(r=>alert(r.ok||r.status===204?'Sent to garden 🌱':'Capture failed: HTTP '+r.status)).catch(e=>alert('Capture failed: '+e))})();
```

Click it on any page to capture that page. Note: some sites' Content-Security-Policy
blocks bookmarklet fetches; if a site refuses, fall back to the issue form.

## Manual trigger / debugging

- Run it by hand: Actions → "Capture URL to garden note" → Run workflow → paste URL.
  Or: `gh workflow run capture.yml -f url=https://…`
- Notes from failed fetches/summaries carry `needs-attention: true` in
  frontmatter — search the repo for that string periodically.
- Tags are organic: the LLM proposes them, a second pass canonicalizes against
  existing tags, and hub pages auto-create on first use.

## Secrets the workflow needs

| Secret | Purpose |
|---|---|
| `GEMINI_API_KEY` | primary summarizer (free tier, aistudio.google.com/apikey) |
| `GROQ_API_KEY` | optional fallback (console.groq.com) |

Set with: `gh secret set GEMINI_API_KEY` (paste key when prompted).
Without either key, captures still work but notes arrive `needs-attention`
with no summary.
