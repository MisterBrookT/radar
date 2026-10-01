<div align="center">

<h1>Radar</h1>
<p>Weekly research briefings, from sources to reviewed bilingual video.</p>

</div>

Radar researches a topic, selects a few important developments, and produces a video with original-source figures, English narration and English/Chinese captions. It starts with the whole picture, then explains the necessary detail, evidence and limits. No fixed video length or filler.

## First case

[Generative UI](cases/genui/README.md): a 2:37 briefing on AUV-Bench and native Angular A2UI rendering. The autonomous run passed review and delivery; the recipient watched and approved it. This repo keeps the case definition and result summary, not generated media.

## Run

Configure [models and local voice](docs/pi-dgx.md), then:

```bash
uv sync
uv run playwright install chromium-headless-shell
uv run python -m radar run --topic genui --run-id my-first-run --no-delivery
```

Topics are data presets in [`topics/`](topics/). Copy one and pass its name or JSON path with `--topic`.

Review failures block delivery; uncertain sends block replay. Recurring weekly scheduling is not enabled.

[Briefing approach](docs/briefing-playbook.md) | [Architecture](docs/architecture.md) | [Renderer](docs/minimal-video.md)

[MIT](LICENSE). Third-party sources and voice models retain their own licenses.
