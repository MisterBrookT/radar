"""Minimal, deterministic SVG animation scheduled from measured semantic speech.

Scenes contain events with say/subtitle, reveal/focus node IDs, and optional
short label. Visuals are constrained graphs or zero-baseline count bars; no
model-authored HTML or code is executed. Later claims remain invisible.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import subprocess
import struct
import textwrap
import wave
from pathlib import Path

from playwright.sync_api import sync_playwright

from .video import FFMPEG, caption_lines, duration, tts

W, H = 1920, 1080
CSS = """
*{box-sizing:border-box;margin:0}body{width:1920px;height:1080px;background:#fafaf7;color:#20231f;
font-family:Arial,'Noto Sans CJK SC','DejaVu Sans',sans-serif;padding:82px 170px;position:relative}
h1{font-size:62px;font-weight:500;letter-spacing:-1.5px;line-height:1.15}
svg{position:absolute;left:180px;top:215px;width:1560px;height:650px;overflow:visible}
.claim{position:absolute;top:380px;left:200px;right:200px;font-size:86px;font-weight:500;line-height:1.2;text-align:center}
.caption{position:absolute;bottom:64px;left:235px;right:235px;text-align:center;font-size:34px;line-height:1.35}
.source{position:absolute;bottom:170px;left:180px;font-size:20px;color:#777d74}
.bilingual svg{top:190px;height:620px}
.bilingual .source{bottom:240px}
.bilingual .caption{bottom:32px;left:230px;right:230px}
.caption-en{font-size:30px;line-height:1.3}
.caption-zh{font-size:34px;line-height:1.35;margin-top:10px}
"""


def validate_script(script):
    if not script.get('scenes'):
        raise ValueError('No scenes')
    ids = set()
    for scene in script['scenes']:
        if scene.get('visual_type') not in {'graph', 'bars', 'statement', 'figure'}:
            raise ValueError('Unknown visual type')
        nodes = scene.get('nodes', []) if scene['visual_type'] == 'graph' else scene.get('bars', [])
        allowed = {node['id'] for node in nodes}
        if not set(scene.get('initial', [])) <= allowed:
            raise ValueError('Unknown initial visual reference')
        if len(allowed) != len(nodes):
            raise ValueError('Duplicate visual IDs')
        if not scene.get('events'):
            raise ValueError('Empty scene')
        if scene['visual_type'] == 'figure':
            width, height = scene['image_size']
            for event in scene['events']:
                x, y, w, h = event['crop']
                if min(x, y) < 0 or min(w, h) <= 0 or x+w > width or y+h > height:
                    raise ValueError('Figure crop outside original image')
        for node in nodes:
            if scene['visual_type'] == 'graph':
                if not 0 <= float(node['x']) <= 1440 or not 0 <= float(node['y']) <= 600:
                    raise ValueError('Node outside canvas')
            elif not 0 <= float(node['value']) <= float(scene.get('maximum', 20)):
                raise ValueError('Bar outside zero-baseline scale')
        for edge in scene.get('edges', []):
            if edge['from'] not in allowed or edge['to'] not in allowed:
                raise ValueError('Unknown edge endpoint')
        for event in scene['events']:
            if event['id'] in ids:
                raise ValueError('Duplicate semantic event ID')
            ids.add(event['id'])
            if not event.get('say') or event.get('subtitle') != event['say']:
                raise ValueError('Speech and subtitle must have one source')
            if 'segments' in event:
                segments = event['segments']
                if not segments or any(not p.get('en') or not p.get('zh') for p in segments):
                    raise ValueError('Bilingual captions need aligned English/Chinese units')
                if ' '.join(p['en'] for p in segments) != event['say']:
                    raise ValueError('Bilingual units must preserve the spoken text')
            if not set(event.get('node_labels', {})) <= allowed:
                raise ValueError('Unknown label reference')
            if not set(event.get('reveal', []) + event.get('focus', [])) <= allowed:
                raise ValueError('Unknown visual reference')


def visual_state(scene, event_index):
    revealed = set(scene.get('initial', []))
    for event in scene['events'][:event_index + 1]:
        revealed.update(event.get('reveal', []))
    return revealed, set(scene['events'][event_index].get('focus', []))


def semantic_phrases(scenes):
    output = []
    for si, scene in enumerate(scenes):
        for ei, event in enumerate(scene['events']):
            units = event.get('segments') or [{'en': p} for p in caption_lines(event['say'])]
            for pi, unit in enumerate(units):
                output.append({'scene': si, 'event': ei, 'phrase': pi,
                               'id': f"{event['id']}-{pi}", 'text': unit['en'],
                               'subtitle_zh': unit.get('zh', ''), 'animate': pi == 0})
    return output


def label_svg(label, x, y, size=30, color='#20231f', width=20):
    lines = textwrap.wrap(str(label), width=width, break_long_words=False)[:3]
    top = y - (len(lines) - 1) * size * .6
    return '<text text-anchor="middle" font-family="Arial,DejaVu Sans" font-size="%s" fill="%s">%s</text>' % (
        size, color, ''.join(f'<tspan x="{x}" y="{top + i * size * 1.2}">{html.escape(line)}</tspan>'
                            for i, line in enumerate(lines)))


def scene_html(scene, event_index, subtitle, phase=1, subtitle_zh=''):
    e = html.escape
    body = '<body class="bilingual">' if subtitle_zh else '<body>'
    captions = (f'<div class="caption"><div class="caption-en" lang="en">{e(subtitle)}</div>'
                f'<div class="caption-zh" lang="zh-CN">{e(subtitle_zh)}</div></div>'
                if subtitle_zh else f'<div class="caption">{e(subtitle)}</div>')
    phase = max(0, min(1, float(phase)))
    eased = 1 - (1 - phase) ** 3
    revealed, focus = visual_state(scene, event_index)
    previous, _ = visual_state(scene, event_index - 1) if event_index else (set(scene.get('initial', [])), set())
    new = revealed - previous
    parts = []
    if scene['visual_type'] == 'graph':
        nodes = {n['id']: dict(n) for n in scene.get('nodes', [])}
        for event in scene['events'][:event_index + 1]:
            for nid, label in event.get('node_labels', {}).items():
                nodes[nid]['label'] = label
        for edge in scene.get('edges', []):
            if event_index > edge.get('visible_until', len(scene['events'])):
                continue
            a, b = edge['from'], edge['to']
            if a not in revealed or b not in revealed:
                continue
            left, right = nodes[a], nodes[b]
            x1, y1, x2, y2 = left['x'], left['y'], right['x'], right['y']
            dx, dy = x2 - x1, y2 - y1
            scale = min(150 / abs(dx) if dx else float('inf'),
                        48 / abs(dy) if dy else float('inf'))
            if dx == 0 and dy == 0:
                continue
            x1, y1 = x1 + dx * scale, y1 + dy * scale
            x2, y2 = x2 - dx * scale, y2 - dy * scale
            opacity = eased if a in new or b in new else .65
            dash = 'stroke-dasharray="8 8"' if edge.get('dashed') else ''
            path = f'M{x1},{y1} L{x2},{y2}'
            if edge.get('dashed'):
                path = f'M{x1},{y1} Q{(x1+x2)/2+95},{(y1+y2)/2+70} {x2},{y2}'
            parts.append(f'<path d="{path}" fill="none" stroke="#7c887a" stroke-width="3" '
                         f'opacity="{opacity}" {dash} marker-end="url(#arrow)"/>')
            if b in new and a in previous and 0 < phase < 1 and not edge.get('dashed'):
                parts.append(f'<circle cx="{x1+(x2-x1)*eased}" cy="{y1+(y2-y1)*eased}" r="6" fill="#315dcc"/>')
        for nid, node in nodes.items():
            if nid not in revealed:
                continue
            active = nid in focus
            opacity = eased if nid in new else (1 if active else .65)
            shift = 18 * (1 - eased) if nid in new else 0
            x, y = float(node['x']), float(node['y'])
            color = '#315dcc' if active else '#9aa297'
            fill = '#edf1fc' if active else '#f4f5ef'
            parts.append(f'<g opacity="{opacity}" transform="translate(0,{shift})"><rect x="{x-150}" y="{y-48}" '
                         f'width="300" height="96" rx="13" fill="{fill}" stroke="{color}" stroke-width="2.5"/>'
                         + label_svg(node['label'], x, y + 9) + '</g>')
    elif scene['visual_type'] == 'bars':
        maximum = float(scene.get('maximum', 20))
        count = len(scene.get('bars', []))
        axis_y = 270 + max(0, count-1)*130
        parts.append(f'<path d="M380,{axis_y} H1280" stroke="#c6cbc1" stroke-width="2"/>')
        for value in (0, maximum / 2, maximum):
            x = 380 + value / maximum * 900
            parts.append(label_svg(f'{value:g}', x, axis_y+35, 23, '#777d74'))
        for index, bar in enumerate(scene.get('bars', [])):
            if bar['id'] not in revealed:
                continue
            y = 130 + index * 130
            width = float(bar['value']) / maximum * 900
            width *= eased if bar['id'] in new else 1
            color = '#315dcc' if bar['id'] in focus else '#a9b29f'
            parts.append(label_svg(bar['label'], 170, y + 34, 29))
            parts.append(f'<rect x="380" y="{y}" width="{width}" height="62" rx="5" fill="{color}"/>')
            value_label = bar.get('display_label')
            if value_label is None:
                value_label = f"{float(bar['value']):g}"
                if scene.get('denominator') is not None:
                    value_label += f"/{float(scene['denominator']):g}"
            parts.append(label_svg(value_label, 420 + width, y + 40, 30))
    elif scene['visual_type'] == 'figure':
        target = scene['events'][event_index]['crop']
        origin = scene['events'][event_index-1]['crop'] if event_index else scene.get('overview', target)
        crop = [a+(b-a)*eased for a,b in zip(origin,target)]
        width,height = scene['image_size']
        image = e(scene['image_data'], quote=True)
        parts.append(f'<image href="{image}" x="0" y="0" width="{width}" height="{height}"/>')
        event = scene['events'][event_index]
        highlights = event.get('highlights', []) or ([event['highlight']] if event.get('highlight') else [])
        for highlight in highlights:
            x,y,w,h = highlight
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
                         f'stroke="#315dcc" stroke-width="{max(.7,crop[2]/1560*3)}" opacity="{eased}"/>')
        clip = f'<defs><clipPath id="figure-crop"><rect x="{crop[0]}" y="{crop[1]}" width="{crop[2]}" height="{crop[3]}"/></clipPath></defs>'
        svg = '<svg style="overflow:hidden" viewBox="%s" preserveAspectRatio="xMidYMid meet">%s<g clip-path="url(#figure-crop)">%s</g></svg>' % (' '.join(map(str,crop)), clip, ''.join(parts))
        return f'<style>{CSS}</style>{body}<h1>{e(scene["heading"])}</h1>{svg}<div class="source">{e(scene.get("citation", ""))}</div>{captions}</body>'
    else:
        claim = scene['events'][event_index].get('label', scene['heading'])
        parts.append(f'<foreignObject x="100" y="120" width="1240" height="380"><div xmlns="http://www.w3.org/1999/xhtml" '
                     f'style="font-size:82px;text-align:center;line-height:1.3;opacity:{eased}">{e(claim)}</div></foreignObject>')
    svg = ('<svg viewBox="0 0 1440 600"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" '
           'orient="auto"><path d="M0,0 L8,4 L0,8" fill="#7c887a"/></marker></defs>' + ''.join(parts) + '</svg>')
    return f'<style>{CSS}</style>{body}<h1>{e(scene["heading"])}</h1>{svg}<div class="source">{e(scene.get("citation", ""))}</div>{captions}</body>'


def measured_duration(path):
    try:
        with wave.open(str(path)) as audio:
            return audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError):
        return duration(path)


def run(day_dir, preview_events=None, preview_scene=None, target_seconds=None):
    day_dir = Path(day_dir).resolve()
    script = json.loads((day_dir / 'script.json').read_text())
    validate_script(script)
    scenes = script['scenes']
    for scene in scenes:
        if scene['visual_type'] == 'figure':
            asset = (day_dir/scene['asset']).resolve()
            if not asset.is_relative_to(day_dir/'assets'):
                raise ValueError('Figure asset must stay inside run assets')
            data = asset.read_bytes()
            if len(data)>25*1024*1024 or data[:8]!=b'\x89PNG\r\n\x1a\n' or data[12:16]!=b'IHDR':
                raise ValueError('Only bounded original PNG figures allowed')
            if tuple(scene['image_size'])!=struct.unpack('>II',data[16:24]):
                raise ValueError('Figure size does not match original')
            scene['image_data']='data:image/png;base64,'+base64.b64encode(data).decode()
    phrases = semantic_phrases(scenes)
    if preview_scene:
        phrases = [p for p in phrases if scenes[p['scene']]['id'] == preview_scene]
        if not phrases:
            raise ValueError('Unknown preview scene')
    if preview_events:
        phrases = phrases[:preview_events]
    build = day_dir / 'minimal-build'
    build.mkdir(exist_ok=True)
    frames, audio_files, timeline = [], [], []
    elapsed = 0.0
    # Cache only local provider/voice/text combinations; reused clips are measured.
    for index, phrase in enumerate(phrases):
        key = hashlib.sha256((os.environ.get('GENUI_TTS_PROVIDER', 'piper') +
                              os.environ.get('GENUI_PIPER_MODEL', '') + phrase['text']).encode()).hexdigest()[:16]
        audio = build / f'{key}.wav'
        if not audio.exists():
            tts(phrase['text'], audio)
        phrase['duration'] = measured_duration(audio)
        phrase['audio'] = audio
        print(f'Speech {index+1}/{len(phrases)}', flush=True)
    total_speech = sum(p['duration'] for p in phrases)
    print(f'Measured speech: {total_speech:.2f}s', flush=True)
    if target_seconds and not preview_events:
        rate = total_speech / target_seconds
        if not .85 <= rate <= 1.15:
            raise ValueError(f'Narration needs editorial revision: {total_speech:.2f}s; refusing excessive speed change')
        for phrase in phrases:
            normalized = build/f'{phrase["audio"].stem}-rate-{rate:.6f}.wav'
            if not normalized.exists():
                subprocess.run([FFMPEG,'-y','-loglevel','error','-i',str(phrase['audio']),
                                '-af',f'atempo={rate:.8f}','-c:a','pcm_s16le',str(normalized)],check=True)
            phrase['audio']=normalized
            phrase['duration']=measured_duration(normalized)
        print(f'Uniform voice rate {rate:.4f}; remeasured {sum(p["duration"] for p in phrases):.2f}s',flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        for index, phrase in enumerate(phrases):
            si, ei = phrase['scene'], phrase['event']
            length = phrase['duration']
            animate = min(.65, length * .35) if phrase['animate'] else 0
            steps = 8 if animate else 0
            for frame in range(steps + 1):
                phase = frame / steps if steps else 1
                page.set_content(scene_html(scenes[si], ei, phrase['text'], phase, phrase['subtitle_zh']))
                png = build / f'frame-{index:03d}-{frame:02d}.png'
                page.screenshot(path=png)
                hold = animate / steps if frame < steps else length - animate
                frames.append((png, hold))
            audio_files.append(phrase['audio'])
            timeline.append({'id': phrase['id'], 'scene': si, 'event': ei, 'start': elapsed,
                             'duration': length, 'subtitle': phrase['text'], 'subtitle_zh': phrase['subtitle_zh'],
                             'reveal': scenes[si]['events'][ei].get('reveal', []),
                             'focus': scenes[si]['events'][ei].get('focus', []),
                             'animation_seconds': animate, 'audio': str(phrase['audio'].relative_to(day_dir))})
            elapsed += length
            print(f'Visual {index+1}/{len(phrases)}', flush=True)
        browser.close()
    (day_dir / ('preview-timing.json' if preview_events else 'timing.json')).write_text(
        json.dumps({'duration': elapsed, 'events': timeline}, indent=2))
    video_list, audio_list = build / 'frames.txt', build / 'audio.txt'
    video_list.write_text(''.join(f"file '{path}'\noption framerate 1000\nduration {hold:.8f}\n" for path, hold in frames)
                          + f"file '{frames[-1][0]}'\noption framerate 1000\n")
    audio_list.write_text(''.join(f"file '{path}'\n" for path in audio_files))
    output = day_dir / ('preview.mp4' if preview_events else 'video.mp4')
    subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(video_list),
                    '-f', 'concat', '-safe', '0', '-i', str(audio_list), '-t', f'{elapsed:.8f}',
                    '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                    '-threads', '4', '-c:a', 'aac', '-ar', '48000', '-movflags', '+faststart', str(output)], check=True)
    print(f'Wrote {output} ({elapsed:.2f}s)', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir')
    parser.add_argument('--preview-events', type=int)
    parser.add_argument('--preview-scene')
    parser.add_argument('--target-seconds', type=float)
    args = parser.parse_args()
    run(args.run_dir, args.preview_events, args.preview_scene, args.target_seconds)
