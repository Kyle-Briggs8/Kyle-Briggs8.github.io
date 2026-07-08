---
title: Kyle Briggs
date: 2026-07-01
publish: true
socialImage: og-card.png
---
Hey, my name is Kyle. I am studying Computer Science & Economics at the University of Virginia ('28), and I'm currently a cleared software engineering intern on Microsoft's Federal Cloud & AI team. I care about AI and agentic systems, gov-tech, and the places where startups meet government.

This site is two things: a [[blog/index|blog]] of writings, and a [[notes/index|digital garden]] of notes on what I'm reading, watching, and listening to.

<a class="brain-cta" href="/static/brain/" data-router-ignore>🧠 Open the brain<span>the whole garden as one interactive graph — click a node to preview, dive in from there</span></a>

<p class="brain-pulse">● <span id="pulse-text">the brain is alive and growing</span></p>

<script>
(() => {
  const rel = (d) => {
    const s = (Date.now() - d.getTime()) / 1000;
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + " minutes ago";
    if (s < 86400) { const h = Math.round(s / 3600); return h + (h === 1 ? " hour ago" : " hours ago"); }
    const days = Math.round(s / 86400); return days + (days === 1 ? " day ago" : " days ago");
  };
  const repo = "Kyle-Briggs8/Kyle-Briggs8.github.io";
  Promise.all([
    fetch("https://api.github.com/repos/" + repo + "/commits?path=content/notes&per_page=1").then((r) => r.json()),
    fetch("https://api.github.com/repos/" + repo + "/commits?path=content/notes&per_page=100&since=" + new Date(Date.now() - 7 * 864e5).toISOString()).then((r) => r.json()),
    fetch("/static/contentIndex.json").then((r) => r.json()),
  ]).then(([last, week, idx]) => {
    const fed = new Date(last[0].commit.author.date);
    const notes = week.filter((c) => c.commit.message.startsWith("capture:")).length;
    const clusters = Object.keys(idx).filter((s) => s.startsWith("tags/") && s !== "tags/index").length;
    const el = document.getElementById("pulse-text");
    if (el) el.textContent = "last fed " + rel(fed) + " · " + notes + (notes === 1 ? " note" : " notes") + " this week · " + clusters + " clusters";
  }).catch(() => {});
})();
</script>

📫 [kyl3.briggs@gmail.com](mailto:kyl3.briggs@gmail.com) · [GitHub](https://github.com/Kyle-Briggs8) · [LinkedIn](https://www.linkedin.com/in/kyle-briggs-/) · [[timeline|Timeline]] · [[now|Now]]

<!-- TODO: headshot — drop an image into content/static/ and embed here -->

## Work

<div class="xp">
<div class="xp-item"><span class="xp-role">Cleared Software Engineering Intern</span><span class="xp-org">Microsoft — Federal Cloud & AI, Machine Learning Engine team · Redmond, WA</span><span class="xp-dates">May 2026 – Present</span><span class="xp-desc">Building an AI-powered session monitoring product for classified government cloud environments — an ML-driven oversight layer that flags anomalous behavior and policy violations in real time.</span></div>
<div class="xp-item"><span class="xp-role">Venture Capital Intern — Galant Challenge</span><span class="xp-org">Galant Center for Innovation & Entrepreneurship · Charlottesville, VA</span><span class="xp-dates">Jan 2026 – May 2026</span><span class="xp-desc">1 of 6 VC interns working with partner firms on early-stage diligence — narrowing ~100 startup submissions to the finalists pitching for up to $6M each.</span></div>
<div class="xp-item"><span class="xp-role">Student AI Researcher</span><span class="xp-org">UVA R.A.I.S.E. Lab · Charlottesville, VA</span><span class="xp-dates">Aug 2025 – Present</span><span class="xp-desc">Bayesian network structure learning (Hill Climbing/BIC, exact ILP DAG optimization, IAMB) on a 706K-record hospital dataset to find minimal predictive feature sets for data minimization.</span></div>
<div class="xp-item"><span class="xp-role">AI4ALL Ignite Fellow</span><span class="xp-org">AI4ALL · Charlottesville, VA</span><span class="xp-dates">Aug 2025 – Mar 2026</span><span class="xp-desc">Built a resume–job matching pipeline using LLM skill extraction and embeddings.</span></div>
<div class="xp-item"><span class="xp-role">Software Engineer Intern</span><span class="xp-org">Spectric Labs · Chantilly, VA</span><span class="xp-dates">May 2025 – Aug 2025</span><span class="xp-desc">Built a Python test harness validating RabbitMQ → Logstash → Elasticsearch data integrity (plus Playwright UI tests), wired into GitLab CI/CD; led rollout of a secure company-wide LLM platform with LDAP SSO.</span></div>
<div class="xp-item"><span class="xp-role">Research Intern</span><span class="xp-org">National Geospatial-Intelligence Agency · Springfield, VA</span><span class="xp-dates">Jun 2024 – Aug 2024</span><span class="xp-desc">Client-facing GEOINT research on the 2024 Panamanian election, delivered as an ArcGIS Pro product.</span></div>
<div class="xp-item"><span class="xp-role">Cyber Security Engineer Intern</span><span class="xp-org">National Geospatial-Intelligence Agency · Springfield, VA</span><span class="xp-dates">Jun 2023 – Sep 2023</span><span class="xp-desc">Zero Trust visualizations for agency-wide use; Python tooling on the Carbon Black Response API to surface processes matching behavioral indicators of compromise.</span></div>
<div class="xp-item"><span class="xp-role">Intern</span><span class="xp-org">Research Innovations Inc. (RII) · Franconia, VA</span><span class="xp-dates">May 2024</span><span class="xp-desc">Supported the Dragonfly team's four-antenna sensor system for 360° signal detection, position pinpointing, and heat-map visualization testing.</span></div>
</div>

**Education:** University of Virginia, B.S. Computer Science & Economics, Class of 2028 · GPA 3.96/4.00

**Honors:** Y Combinator Startup School 2026 (invite-only in-person program) · UVA VentureForward — $1,000 in funding (1 of 20 teams)

## Recent writing

<div class="card-stack">
<a class="card" href="/blog/self-organizing-second-brain"><span class="card-kind">essay</span><span class="card-title">I built a second brain that organizes itself</span><span class="card-sub">Share a link from my phone; two minutes later it's a node in the graph. The architecture, the war stories, the $0 bill.</span></a>
<a class="card" href="/blog/geowatch"><span class="card-kind">essay</span><span class="card-title">GeoWatch: open-source GEOINT from live news</span><span class="card-sub">Turning a location name into a mapped, severity-scored intel dashboard — on free tiers.</span></a>
</div>

[[blog/index|All posts →]]

## Recently in the garden

<!-- Updated automatically by scripts/capture.py; keep the markers and the card format. -->
<div class="card-grid">
<!-- RECENT-NOTES:START -->
<a class="card" href="/notes/ken-griffin-miami-condo-demolition-citadel-campus"><span class="card-kind">article</span><span class="card-title">Ken Griffin Secretly Buys and Demolishes Miami Condo Building for Citadel Campus</span></a>
<a class="card" href="/notes/vanguard-history-mutual-ownership"><span class="card-kind">podcast</span><span class="card-title">Vanguard: The Paradox of Client Ownership and Market Dominance</span></a>
<a class="card" href="/notes/spacex-transporter-17-rideshare-concerns"><span class="card-kind">article</span><span class="card-title">SpaceX Transporter-17 Launch Amidst Industry Concerns Over Rideshare Program's Future</span></a>
<a class="card" href="/notes/global-workspace-language-models"><span class="card-kind">article</span><span class="card-title">A global workspace in language models</span></a>
<a class="card" href="/notes/startups-13-sentences"><span class="card-kind">article</span><span class="card-title">Startups in 13 Sentences</span></a>
<a class="card" href="/notes/100-john-does-insider-trading-retail-options-ai-security"><span class="card-kind">podcast</span><span class="card-title">100 John Does: Insider Trading, Retail Options, and AI Security</span></a>
<!-- RECENT-NOTES:END -->
</div>

[[notes/index|The whole garden →]]
