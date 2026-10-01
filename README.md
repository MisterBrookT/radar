<div align="center">

<h1>Radar</h1>
<p>Topic-adaptive, source-grounded research briefings—from a weekly topic to a reviewed bilingual video.</p>

</div>

## About

Radar runs research, narration, visual planning, rendering, review and optional delivery as one project-owned workflow. Generative UI is its first case, not the engine boundary. Topic scope and source queries live in `topics/*.json`; the production rhythm stays reusable.

The [first GenUI case](cases/genui/README.md) completed the autonomous path and was watched and approved by its recipient. This repository contains source, presets and a non-secret result summary—not generated videos or private runtime data.

**Title → whole-picture core idea → only necessary detail → evidence, boundaries and takeaway.** English narration, semantic English/Chinese captions, original figures and content-driven duration.

## Run the project

```bash
uv sync
uv run playwright install chromium-headless-shell
# Configure model routes, Piper and optional delivery first (docs/pi-dgx.md).
uv run python -m radar run --topic genui --week-ending YYYY-MM-DD --run-id UNIQUE-ID --no-delivery
```

The project launches its own workers: Sonnet for primary-source research and narration; Opus for source-figure visual planning and independent final-frame review. It renders with local English Piper, fully decodes the video, verifies input/artifact hashes, and delivers once through the existing standalone WeChat account. The supervising assistant starts/checks the project—not manually writes each digest.

Runtime requirements: configured Pi model routes, existing Piper interpreter/model and Playwright/ffmpeg. To send, pair a recent-context WeChat account, set `RADAR_WECHAT=1` and omit `--no-delivery`. Public settings use `RADAR_*`; legacy `GENUI_*` aliases and already-installed voice/account resources remain compatible during migration. Credentials are never part of source snapshots.

`deploy/run-project.sh` is the DGX job entry. Use an immutable snapshot and detached tmux session with unique ID, logs, provenance and real exit status. Automatic weekly scheduling is separate and must not be claimed from a successful one-off launch.

## Change topics

Copy a preset, change its name/title, relevance scope, paper terms/categories, search queries and official repositories; pass its name or JSON path via `--topic`. No renderer changes are required. Choose a few important developments in the past seven days, with no popularity/platform quota or forced video length. Adjacent work is clearly labelled, never substituted for the requested topic.

## Inspect or run individual stages

```bash
uv run python -m radar --topic genui --week-ending YYYY-MM-DD --through plan
```

This safer partial route stops at planning. Full project runs use `radar run`. Logs, sources, scripts, measured timing, review frames and delivery markers remain in the run directory. Failed review blocks delivery; unknown send outcomes block replay. A no-eligible-work result is not a fabricated filler video or a delivery success.

- [First case: Generative UI](cases/genui/README.md)
- [Briefing playbook](docs/briefing-playbook.md)
- [Minimal video engine](docs/minimal-video.md)
- [Architecture/history](docs/architecture.md)
- [DGX Pi runtime](docs/pi-dgx.md)

Code is [MIT licensed](LICENSE). Third-party sources and voice engines/models retain their own licenses.

Old daily jobs and Hermes are retired. Historical rendering is explicit `--legacy` compatibility only. Preserve active jobs, accepted-send markers, private credentials and uncommitted work.
