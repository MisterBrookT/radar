# Radar — topic-adaptive research briefing workflow

For any briefing/video work in this repository, read `docs/briefing-playbook.md` first.

- Radar is the general engine. Generative UI is one case/preset; keep topic scope and source queries in `topics/*.json`, not hardcoded in the engine.
- Default cadence: weekly, the past seven days, not a daily roundup.
- Preserve brook's approved rhythm: **title → whole-picture core idea → only necessary detail → evidence, boundaries and takeaway**.
- Minimal means concise but necessary, not skipping orientation or racing into features.
- No fixed runtime, word quota or scene quota. Ten or twenty minutes is fine if the selected work warrants it. Never pad a quiet week.
- Select a few important works/main lines, not one item per platform or merely the most-liked posts.
- Enforce the active preset's direct/adjacent boundary. For the GenUI case, a fixed canvas using an LLM to generate charts (VisCanvas) is adjacent, not a core GenUI headline.
- Use the original source figures with restrained narration-timed guidance. English narration; aligned English/Chinese captions in complete semantic units.
- Review primary sources and claim boundaries before scripting; inspect the actual rendered opening and longest bilingual caption before delivery.
- Use `python -m radar run` for full project-owned production. `radar.engine` launches its research/narration/visual-review workers; `radar.minimal_video` renders deterministically. The supervising assistant launches/checks the project, not handwrites the issue. The old daily/script/slide renderer is explicit `--legacy` compatibility only.
- Preserve uncommitted work, prior cases and private credentials. No model-authored executable visuals, uncertain send retries or Hermes reinstalls.
- Old DGX daily/retry timers were disabled when switching to weekly. Do not reactivate them. Weekly automation is not yet deployed; source review remains agent-operated.
