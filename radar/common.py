import json
import os
import re
import sys
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
QWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
FAST_MODEL = "qwen-flash"
STRONG_MODEL = "qwen3-max"
MAX_ATTEMPTS = 3
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504, 529}
_last_response_model = None


def run_dir(day: str) -> Path:
    d = Path(os.environ.get("GENUI_RUNS", ROOT / "runs")) / day
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2))


def load(path: Path):
    return json.loads(path.read_text())


def last_response_model():
    """Model name reported by the most recent Anthropic-route response (None on Qwen route)."""
    return _last_response_model


def _post_with_retry(url: str, headers: dict, body: dict) -> httpx.Response:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=300)
        except httpx.TransportError:
            if attempt == MAX_ATTEMPTS:
                raise
        else:
            if r.status_code not in TRANSIENT_STATUS or attempt == MAX_ATTEMPTS:
                r.raise_for_status()
                return r
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def _anthropic(prompt: str, as_json: bool) -> str:
    global _last_response_model
    base = os.environ.get("GENUI_LLM_BASE_URL")
    model = os.environ.get("GENUI_LLM_MODEL")
    key = os.environ.get("GENUI_LLM_API_KEY")
    if not (base and model and key):
        raise RuntimeError("anthropic provider requires GENUI_LLM_BASE_URL, GENUI_LLM_MODEL, GENUI_LLM_API_KEY")
    if as_json:
        prompt += "\n\nRespond with a single JSON object only, no prose."
    body = {"model": model, "max_tokens": 16000,
            "messages": [{"role": "user", "content": prompt}]}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    data = _post_with_retry(base.rstrip("/") + "/v1/messages", headers, body).json()
    got = data.get("model")
    if got and not got.startswith(model):
        raise RuntimeError(f"requested model {model!r} but response came from {got!r}")
    _last_response_model = got or model
    print(f"[llm] anthropic model={_last_response_model}", file=sys.stderr)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def llm(prompt: str, model: str = STRONG_MODEL, as_json: bool = True):
    if os.environ.get('RADAR_LLM_PROVIDER') == 'pi':
        command = [os.environ.get('RADAR_PI', str(Path.home()/'.local/bin/pi')),
                   '--model', os.environ.get('RADAR_NARRATION_MODEL', 'pix-anthropic/claude-sonnet-5'),
                   '--print', '--no-session', '--no-tools', '--no-skills', '--no-context-files']
        if as_json:
            prompt += '\nReturn a single JSON object, no prose or Markdown fences.'
        result = subprocess.run(command+[prompt], capture_output=True, text=True, check=True, timeout=1800)
        text = re.sub(r'^```(json)?|```$', '', result.stdout.strip()).strip()
        return json.loads(text) if as_json else text
    if os.environ.get("GENUI_LLM_PROVIDER", "qwen") == "anthropic":
        text = _anthropic(prompt, as_json)
        if not as_json:
            return text
        text = re.sub(r"^```(json)?|```$", "", text.strip()).strip()
        return json.loads(text)
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4}
    if as_json:
        body["response_format"] = {"type": "json_object"}
    r = httpx.post(
        QWEN_URL,
        headers={"Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}"},
        json=body,
        timeout=300,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    if not as_json:
        return text
    text = re.sub(r"^```(json)?|```$", "", text.strip()).strip()
    return json.loads(text)
