"""Send through the standalone iLink bot account; never imports Hermes.

Usage: python -m genui.wechat_send VIDEO TEXT_FILE
Use '-' for text-only delivery. Pair first with python -m genui.weixin login.
"""
import json
import sys
from pathlib import Path

from .weixin import Weixin


def main(video: str, text: str) -> dict:
    return Weixin().send(video if video != '-' else '', text)


if __name__ == '__main__':
    result = main(sys.argv[1], Path(sys.argv[2]).read_text())
    print(json.dumps(result))
    sys.exit(0 if result.get('success') else 1)
