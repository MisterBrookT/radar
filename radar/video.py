"""Stage 6: narration (Qwen TTS) + slides (HTML -> PNG via Playwright) -> MP4 with subtitles (ffmpeg)."""
import hashlib
import html
import os
import re
import subprocess

import imageio_ffmpeg

import httpx
from playwright.sync_api import sync_playwright

from .common import load, save

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TTS_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
VOICE = "Ethan"
W, H = 1920, 1080

CSS = """
*{margin:0;box-sizing:border-box}
body{width:1920px;height:1080px;background:#fafaf7;color:#1a1a1a;
 font-family:'PingFang SC','Hiragino Sans GB',sans-serif;padding:150px 200px 0;position:relative}
.meta{position:absolute;top:72px;left:200px;right:200px;display:flex;justify-content:space-between;
 font-size:24px;color:#9a9a94;letter-spacing:1px}
h1{font-size:68px;line-height:1.25;font-weight:600;max-width:1400px;margin-bottom:64px}
.row{display:flex;gap:96px}
ul{list-style:none;flex:1}
li{font-size:42px;line-height:1.4;margin-bottom:30px;color:#c4c4bd}
li.seen{color:#6b6b66}li.on{color:#1a1a1a}
.fig{width:520px;height:460px;display:flex;align-items:flex-start;justify-content:center}
.fig img{max-width:100%;max-height:100%;border-radius:8px}
.diagram{width:520px;display:flex;flex-direction:column;gap:18px}
.diagram .node{padding:22px 28px;border:2px solid #d8d8d0;border-radius:12px;font-size:34px;background:#f0f0e9}
.diagram .arrow{font-size:32px;color:#6b6b66;text-align:center}
.diagram.comparison .node{border-left:6px solid #6b6b66}
.src{position:absolute;left:200px;bottom:168px;font-size:24px;color:#9a9a94;line-height:1.6}
.cap{position:absolute;left:200px;right:200px;bottom:72px;font-size:36px;color:#3a3a36;text-align:center}
.center{display:flex;flex-direction:column;justify-content:center;padding-top:0}
.center h1{font-size:88px;margin-bottom:28px}.center .sub{font-size:34px;color:#9a9a94}
"""


def tts(text: str, path) -> None:
    if os.environ.get("GENUI_TTS_PROVIDER", "qwen") == "piper":
        from pathlib import Path
        model = Path(os.environ["GENUI_PIPER_MODEL"]).expanduser()
        if not model.is_file():
            raise FileNotFoundError(f"Piper voice model missing: {model}")
        subprocess.run([os.environ["GENUI_PIPER_PYTHON"], "-m", "piper", "-m", str(model),
                        "-f", str(path)], input=text, text=True, capture_output=True,
                       check=True, timeout=60)
        return
    import time
    # DGX IPv6 routes can blackhole these hosts; pin only voice traffic to IPv4.
    with httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                      timeout=httpx.Timeout(120, connect=10)) as client:
        for attempt in range(8):
            r = client.post(TTS_URL, headers={"Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}"},
                            json={"model": "qwen3-tts-flash",
                                  "input": {"text": text, "voice": VOICE, "language_type": "English" if os.environ.get("GENUI_LANGUAGE", "en") == "en" else "Chinese"}})
            if r.status_code != 429:
                break
            time.sleep(2 ** attempt)
        r.raise_for_status()
        audio = client.get(r.json()["output"]["audio"]["url"])
        audio.raise_for_status()
        path.write_bytes(audio.content)


def duration(path) -> float:
    """Decode to count samples; TTS WAV headers can carry a bogus length."""
    out = subprocess.run([FFMPEG, "-i", str(path), "-f", "null", "-"], capture_output=True, text=True).stderr
    h, m, sec = re.findall(r"time=(\d+):(\d+):([\d.]+)", out)[-1]
    return int(h) * 3600 + int(m) * 60 + float(sec)


def signal_text(it: dict) -> str:
    s = it["signals"]
    if it["kind"] == "paper":
        return f"{s['visits']} visits · {s['votes']} votes on alphaXiv"
    if it["kind"] == "hn":
        return f"{s['points']} points · {s['comments']} comments on Hacker News"
    return f"{s['likes']} likes · {s['reposts']} reposts"


def source_line(it: dict) -> str:
    who = it["authors"][0] + (" et al." if it["kind"] == "paper" and len(it["authors"]) > 1 else "")
    where = {"paper": f"arXiv {it['id']}", "hn": "HN"}.get(it["kind"], "X")
    return f"{who} · {where} · {signal_text(it)}"


def diagram(plan) -> str:
    """Render a constrained model-authored diagram; never execute generated code."""
    if not isinstance(plan, dict) or plan.get("type") not in {"flow", "comparison", "cards"}:
        return ""
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or len(nodes) < 2:
        return ""
    parts = [f"<div class='node'>{html.escape(str(n)[:40])}</div>" for n in nodes[:4]]
    sep = "<div class='arrow'>→</div>" if plan["type"] == "flow" else ""
    return f"<div class='diagram {plan['type']}'>{sep.join(parts)}</div>"


def slide(scene, items, idx, total, title, day, cap="", step=0) -> str:
    """One message per frame: heading, bullets revealed in step with narration, quiet source line."""
    e = html.escape
    capdiv = f"<div class='cap'>{e(cap)}</div>" if cap else ""
    meta = f"<div class='meta'><span>GenUI Daily</span><span>{day} · {idx + 1}/{total}</span></div>"
    if scene["kind"] in ("intro", "outro"):
        sub = e(title) if scene["kind"] == "intro" else ""
        return (f"<style>{CSS}</style><body class='center'>{meta}<h1>{e(scene['heading'])}</h1>"
                f"<div class='sub'>{sub}</div>{capdiv}</body>")
    bullets = scene.get("bullets", [])
    lis = "".join(f"<li class='{'on' if i == step else 'seen' if i < step else ''}'>{e(b)}</li>"
                  for i, b in enumerate(bullets))
    srcs = [items[i] for i in scene.get("sources", []) if i < len(items)]
    media = next((s["image"] for s in srcs if s["kind"] == "tweet" and s.get("image")), None)
    fig = diagram(scene.get("visual")) or (f"<div class='fig'><img src='{e(media)}'></div>" if media else "")
    src = "<br>".join(e(source_line(s)) for s in srcs[:2])
    return (f"<style>{CSS}</style><body>{meta}<h1>{e(scene['heading'])}</h1>"
            f"<div class='row'><ul>{lis}</ul>{fig}</div><div class='src'>{src}</div>{capdiv}</body>")


def caption_lines(text: str) -> list[str]:
    if not re.search(r"[\u4e00-\u9fff]", text):
        import textwrap
        return textwrap.wrap(text, width=64, break_long_words=False, break_on_hyphens=False)
    merged, cur = [], ""
    for x in (x for x in re.split(r"(?<=[，。！？；：])", text) if x.strip()):
        if len(cur) + len(x) > 30 and cur:
            merged.append(cur.strip())
            cur = ""
        cur += x
    if cur.strip():
        merged.append(cur.strip())
    out = []  # hard cap so a caption never wraps
    for m in merged:
        while len(m) > 36:
            out.append(m[:30])
            m = m[30:]
        out.append(m)
    return out


def run(day_dir):
    """Narration is the clock: one TTS clip per caption phrase; each frame lasts exactly its clip."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    day = day_dir.name
    script = load(day_dir / "script.json")
    items = load(day_dir / "selected.json")
    scenes = script["scenes"]
    tmp = day_dir / "build"
    tmp.mkdir(exist_ok=True)

    events = []  # (scene_idx, phrase_idx, text, wav)
    for k, sc in enumerate(scenes):
        for j, cap in enumerate(caption_lines(sc["narration"])):
            events.append((k, j, cap, tmp / f"tts_{hashlib.md5((os.environ.get('GENUI_TTS_PROVIDER', 'qwen') + os.environ.get('GENUI_PIPER_MODEL', VOICE) + cap).encode()).hexdigest()[:12]}.wav"))

    def synth(ev):
        if not ev[3].exists():
            tts(ev[2], ev[3])
    pool = ThreadPoolExecutor(max_workers=int(os.environ.get("GENUI_TTS_WORKERS", "3")))
    futures = [pool.submit(synth, ev) for ev in events]
    try:
        for count, future in enumerate(as_completed(futures), 1):
            future.result()
            if count % 10 == 0 or count == len(events):
                print(f"  TTS {count}/{len(events)} phrases", flush=True)
    finally:
        # A failed request must not leave every queued paid request running.
        pool.shutdown(wait=True, cancel_futures=True)
    durs = [duration(ev[3]) for ev in events]
    print(f"  {len(events)} phrases, narration {sum(durs) / 60:.1f} min")

    timeline, elapsed = [], 0.0
    for k, sc in enumerate(scenes):
        scene_events = [(ev, d) for ev, d in zip(events, durs) if ev[0] == k]
        nb = max(1, len(sc.get("bullets", [])))
        for n, (ev, d) in enumerate(scene_events):
            timeline.append({"scene": k, "start": round(elapsed, 3), "duration": d,
                             "subtitle": ev[2], "step": min(nb - 1, n * nb // len(scene_events)),
                             "audio": str(ev[3].relative_to(day_dir))})
            elapsed += d
        elapsed += 0.5
    save(day_dir / "timing.json", {"events": timeline, "duration": round(elapsed, 3)})

    clips = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H})
        for k, sc in enumerate(scenes):
            evs = [(ev, d) for ev, d in zip(events, durs) if ev[0] == k]
            nb = max(1, len(sc.get("bullets", [])))
            frames = []
            for n, (ev, d) in enumerate(evs):
                step = min(nb - 1, n * nb // len(evs))
                png = tmp / f"f{k:02}_{n:02}.png"
                page.set_content(slide(sc, items, k, len(scenes), script["title"], day, ev[2], step))
                page.wait_for_load_state("networkidle", timeout=20000)
                page.screenshot(path=png)
                frames.append((png, ev[3], d))
            pause = 0.5  # breathing room at scene end
            vlist = tmp / f"s{k:02}_v.txt"
            vlist.write_text("".join(f"file '{f}'\nduration {d + (pause if i == len(frames) - 1 else 0):.3f}\n"
                                     for i, (f, _, d) in enumerate(frames)) + f"file '{frames[-1][0]}'\n")
            alist = tmp / f"s{k:02}_a.txt"
            alist.write_text("".join(f"file '{a}'\n" for _, a, _ in frames))
            total = sum(d for *_, d in frames) + pause
            clip = tmp / f"scene{k:02}.mp4"
            subprocess.run([FFMPEG, "-y", "-loglevel", "error",
                            "-f", "concat", "-safe", "0", "-i", vlist,
                            "-f", "concat", "-safe", "0", "-i", alist,
                            "-af", "apad", "-t", f"{total:.3f}", "-vf", "fps=30,format=yuv420p",
                            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-ar", "48000", clip],
                           check=True)
            clips.append(clip)
        b.close()
    (tmp / "clips.txt").write_text("".join(f"file '{c}'\n" for c in clips))
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", tmp / "clips.txt", "-c", "copy", day_dir / "video.mp4"], check=True)

    src_md = [f"# {script['title']} ({day})\n"]
    for i, it in enumerate(items):
        title = " ".join(re.sub(r"https://t\.co/\w+", "", it["title"]).split())
        src_md.append(f"{i + 1}. [{title}]({it['url']}) — {', '.join(it['authors'])} · {signal_text(it)}")
    (day_dir / "sources.md").write_text("\n".join(src_md) + "\n")
    print(f"  wrote {day_dir / 'video.mp4'}")
