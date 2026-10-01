"""Stage 7: send today's video and a short source list through standalone Weixin iLink.

Without GENUI_WECHAT=1 (e.g. on the Mac) it just reveals the files.
Each day is sent at most once: a `delivered.json` marker blocks resends.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .common import load

WECHAT_PY = os.environ.get("GENUI_WECHAT_PYTHON", sys.executable)


def message(day_dir) -> str:
    script = load(day_dir / "script.json")
    items = load(day_dir / "selected.json")
    profile = load(day_dir/'briefing.json') if (day_dir/'briefing.json').exists() else {}
    if profile.get('cadence') == 'weekly':
        window = profile['window']
        header = f"{profile.get('topic_title', 'Radar')} Weekly · {window['start']}–{window['end_inclusive']}"
    else:
        header = f"GenUI Daily · {day_dir.name}"
    lines = [header, script["title"], ""]
    for i, it in enumerate(items, 1):
        title = " ".join(re.sub(r"https://t\.co/\w+", "", it["title"]).split())[:70]
        related = '[Related context] ' if it.get('topic_role') == 'adjacent' else ''
        lines.append(f"{i}. {related}{title}\n{it['url']}")
    return "\n".join(lines)


def run(day_dir):
    video = day_dir / "video.mp4"
    marker = day_dir / "delivered.json"
    if os.environ.get("GENUI_WECHAT") != "1":
        print(f"  ready: {video}")
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", video])
        return
    if marker.exists():
        print("  already delivered today; skipping")
        return
    if not video.exists():
        print("  no video yet; skipping")
        return
    text = day_dir / "wechat.txt"
    text.write_text(message(day_dir))
    res = subprocess.run([WECHAT_PY, "-m", "radar.wechat_send", video, text],
                         capture_output=True, text=True, timeout=900,
                         cwd=Path(__file__).resolve().parent.parent,
                         env=os.environ.copy())
    out = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else res.stderr.strip()[-500:]
    print(f"  wechat: {out}")
    if res.returncode != 0:
        raise SystemExit("WeChat delivery failed")
    marker.write_text(json.dumps({"result": json.loads(out)}, ensure_ascii=False))
