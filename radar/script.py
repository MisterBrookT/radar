"""Stages 4-5: group sources into stories and write the narrated script (strong LLM)."""
from .common import llm, load, save

PROMPT = """你是一档每日「生成式界面 (Generative UI)」视频简报的编剧。观众是一位 HCI × 可视化 × AI agent 方向的研究者，也关注创业机会。他时间很少，不需要论文细节，只想知道：人们在做什么、为什么值得关注、能带来什么想法。

下面是今天按平台热度挑出的来源（论文、X 帖子、Hacker News 讨论），编号 S0..Sn：

{sources}

要求：
1. 把来源归为 2–3 个「故事」（同一趋势/主题的放在一起），不要逐条罗列。每个来源至少出现在一个故事里。
2. 结构：开场（今天的主线，一句话）→ 各个故事 → 收尾（一个值得带走的想法或可以动手做的方向）。
0. 事实只能来自上面的来源文字。来源没说的细节（产品是什么类型、技术实现、数字、公司、时间）不要编造；帖子信息很少时就如实说“帖子没有细讲”。背景知识必须明确说是背景。
3. 每个故事讲清楚：谁做了什么、为什么有意思、还没被证明的是什么。区分「来源里说的」和「我们的推测」（推测时明确说“我的猜测是”）。
4. 中文口语化旁白，技术名词保留英文。视频约 9–10 分钟：旁白总计 2600–2900 字，不要超过 3000 字。
5. 输出 11–14 个「场景」：开场 1 个（约 150 字）、每个故事 3–4 个场景（每个 220–300 字：背景、做了什么、为什么有意思、存疑之处）、收尾 1–2 个。每个场景，并给出屏幕上显示的标题与 2–4 个要点（每条不超过 18 个字）。

6. 每个 story 场景提供一个 visual：type 为 flow（流程）、comparison（对比）或 cards（并列概念），nodes 为 2–4 个短标签（每个不超过 12 字）。图示必须来自来源，或明确标为推测，不编造架构。图示用来解释，不重复标题。

输出 JSON：
{{"title": "今天的视频标题",
  "stories": [{{"name": "故事名", "sources": [0,2]}}],
  "scenes": [{{"kind": "intro|story|outro", "story": 故事序号或null, "heading": "屏幕标题",
              "bullets": ["要点"], "sources": [相关来源编号], "visual": {{"type": "flow|comparison|cards", "nodes": ["概念"]}}, "narration": "旁白"}}]}}"""


def fmt(i: int, it: dict) -> str:
    sig = ", ".join(f"{k}={v}" for k, v in it["signals"].items())
    return (f"S{i} [{it['kind']}] {it['title']}\n  by {', '.join(it['authors'])} · {it['date']} · {sig}\n"
            f"  {it['text'][:1500]}")


def run(day_dir, target_chars=(2600, 3000)):
    items = load(day_dir / "selected.json")
    if not items:
        raise ValueError("no selected sources; cannot generate a grounded briefing")
    minimum, maximum = target_chars
    prompt = PROMPT.format(sources="\n\n".join(fmt(i, it) for i, it in enumerate(items)))
    import os
    if os.environ.get("GENUI_LANGUAGE", "en") == "en":
        prompt += ("\nOverride language: write ALL narration, headings, bullets, diagram labels and title in natural English. "
                   "Keep facts grounded in the sources. Character limits still apply. Use an English test title.")
    if target_chars != (2600, 3000):
        prompt += (f"\n优先覆盖上面的时长要求：这是端到端测试短片，全部旁白总计 {minimum}–{maximum} 字，"
                   "只生成 4 个场景（开场、两个故事、收尾），约 1–2 分钟。标题标明这是流程测试（按指定语言书写）。")
    script = llm(prompt)
    import json
    for attempt in range(3):
        chars = sum(len(s["narration"]) for s in script["scenes"])
        if minimum <= chars <= maximum:
            break
        if attempt == 2:
            raise ValueError(f"script narration {chars} chars outside {minimum}–{maximum}; refusing TTS")
        print(f"  revising script length: {chars} chars")
        script = llm(f"修改下面的 JSON 视频脚本。旁白 narration 总长度必须在 {minimum}–{maximum} 个字符之间，"
                     f"目前实际 {chars} 字。严格控制长度，不重复信息。保留故事、来源、场景和 visual 图示，"
                     "不新增事实，只输出完整 JSON。\n" + json.dumps(script, ensure_ascii=False))
    save(day_dir / "script.json", script)
    print(f"  script: {len(script['scenes'])} scenes, {chars} chars")
