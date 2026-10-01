# Runtime setup

Radar's workers use the Pi CLI. Heavy rendering can run on a Linux server (the first case used Linux ARM64); a detached tmux session survives SSH disconnection, not server reboot.

## Models

Install and authenticate Pi separately. Never commit authentication files or forward an entire local environment. List configured routes with `pi --list-models`, then select the routes available in your installation:

```bash
export RADAR_PI=/path/to/pi
export RADAR_NARRATION_MODEL=provider/sonnet-model
export RADAR_VISUAL_MODEL=provider/opus-model
```

These model-route placeholders must be replaced. The first verified case used Sonnet for research/narration and Opus for visuals/independent review. Other routes are configurable; no provider credentials are bundled.

## Rendering and local voice

```bash
uv sync
uv run playwright install chromium-headless-shell
export RADAR_PIPER_PYTHON=/path/to/piper-environment/bin/python
export RADAR_PIPER_MODEL=/path/to/english-voice.onnx
export RADAR_TTS_WORKERS=1
```

Install Piper in its own environment and verify downloaded model checksums. Piper and voice datasets/models have their own licenses; the engine's code license does not relicense them. Chromium needs suitable fonts, including Simplified Chinese (e.g. Noto Sans CJK SC). `imageio-ffmpeg` supplies ffmpeg on supported platforms; otherwise configure its executable using `IMAGEIO_FFMPEG_EXE`.

## Generate without delivery

```bash
uv run python -m radar run --topic genui --week-ending YYYY-MM-DD --run-id UNIQUE-ID --no-delivery
```

Replace the date/run ID. The output directory contains the full sources, narration, original figures, script, measured timing, encoded video and review. Failed research/review does not become a successful video; no eligible work means no filler.

## Optional WeChat delivery

Pair the standalone bot separately:

```bash
uv run python -m radar.weixin login
uv run python -m radar.weixin finish
# Message the paired bot, then refresh its owner context:
uv run python -m radar.weixin context
export RADAR_WECHAT=1
```

Account/context/send ledgers remain private. The legacy default account directory is retained for compatibility; override it with `RADAR_WEIXIN_HOME`. A recent owner message is required by the upstream reply window. Unknown/partial sends block replay. API acceptance is not proof that a person watched the video.

To run with delivery, omit `--no-delivery`. A separate transport interpreter can be configured with `RADAR_WECHAT_PYTHON`.

## Remote jobs

Use `deploy/run-project.sh` with an immutable per-job snapshot. Its voice/transport interpreter defaults reflect the first tested installation and can be overridden through `RADAR_PYTHON`, `RADAR_PIPER_PYTHON`, `RADAR_PIPER_MODEL` and `RADAR_WECHAT_PYTHON`.

Preview an explicit rsync allowlist before copying code; exclude credentials, `.git`, caches, local dependencies and old runs. Do not overwrite an active job. Persist provenance, command, logs and actual exit status. Do not restore the retired daily/Hermes deployment. Recurring scheduling is not enabled by the first one-off case.
