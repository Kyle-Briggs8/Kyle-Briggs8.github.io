---
title: "Prompt injection: What's the worst that can happen? (Simon Willison)"
source: https://simonwillison.net/2023/Apr/14/worst-that-can-happen/
author: Simon Willison
media: article
date: 2026-06-08
tags: [ai-security, agentic-systems]
publish: true
---

🔗 [Read on simonwillison.net](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/)

## ⚡ TL;DR

Prompt injection isn't a quirky jailbreak — it's a structural vulnerability, and it gets catastrophic exactly when you wire LLMs to tools, email, and private data.

## Summary

*Summary is AI-drafted — machine voice, not mine.*

- The core problem: LLMs can't reliably distinguish instructions from data, so any untrusted content an assistant reads is a potential command channel.
- Walks the escalation: from search-result manipulation to full data exfiltration once an "AI assistant" can read your email and act on your behalf.
- Key uncomfortable claim that has aged well: you can't fix this with more prompting; mitigations are architectural (privilege separation, human confirmation on consequential actions).

## 💭 My thoughts

## Related

[[ai-security]] · [[agentic-systems]] · [[cybersecurity]]
