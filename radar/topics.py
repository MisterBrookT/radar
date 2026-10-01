"""Data-only topic presets; no topic-specific logic in the editorial engine."""
import json
import os
import re
from pathlib import Path

PRESETS = Path(__file__).resolve().parent.parent/'topics'


def load_topic(name=None):
    name = name or os.environ.get('RADAR_TOPIC', 'genui')
    path = Path(name) if str(name).endswith('.json') else PRESETS/(str(name)+'.json')
    data = json.loads(path.read_text())
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', data.get('name', '')):
        raise ValueError('Topic needs a safe name')
    if not data.get('title') or not data.get('scope') or not data.get('search_queries'):
        raise ValueError('Topic needs title, scope and source queries')
    return data
