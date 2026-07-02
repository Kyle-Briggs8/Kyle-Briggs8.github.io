---
title: "Building Effective Agents (Anthropic)"
source: https://www.anthropic.com/engineering/building-effective-agents
author: Erik Schluntz & Barry Zhang (Anthropic)
media: article
date: 2026-06-02
tags: [agentic-systems, ideas-worth-stealing]
publish: true
---

🔗 [Read on anthropic.com](https://www.anthropic.com/engineering/building-effective-agents)

## ⚡ TL;DR

Most successful "agents" in production aren't agents at all — they're simple, composable workflow patterns. Only reach for autonomous loops when the task genuinely needs them.

## Summary

*Summary is AI-drafted — machine voice, not mine.*

- Distinguishes **workflows** (predefined code paths orchestrating LLM calls) from **agents** (models dynamically directing their own tool use).
- Catalogs the workflow patterns that actually ship: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer.
- Core advice: start with a single LLM call plus retrieval; add complexity only when simpler solutions demonstrably fall short. Agents trade latency and cost for capability — make that trade knowingly.
- Tool design deserves as much care as prompt design ("agent-computer interface" as a first-class concern).

## 💭 My thoughts

## Related

[[agentic-systems]] · [[ideas-worth-stealing]] · [[lilian-weng-llm-agents]]
