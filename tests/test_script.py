import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from radar import script
from radar.common import save, load


def draft(n):
    return {'title': 'test', 'stories': [], 'scenes': [{'kind': 'intro', 'heading': 'test', 'bullets': [], 'sources': [], 'narration': '字' * n}]}


class ScriptLengthTests(unittest.TestCase):
    def test_overlong_draft_is_revised(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            save(p / 'selected.json', [{}])
            with patch.object(script, 'fmt', return_value='source'), patch.object(script, 'llm', side_effect=[draft(4805), draft(2800)]) as llm:
                script.run(p)
                self.assertEqual(llm.call_count, 2)
            self.assertEqual(len(load(p / 'script.json')['scenes'][0]['narration']), 2800)

    def test_bad_length_cannot_reach_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            save(p / 'selected.json', [{}])
            with patch.object(script, 'fmt', return_value='source'), patch.object(script, 'llm', return_value=draft(4805)):
                with self.assertRaises(ValueError):
                    script.run(p)
            self.assertFalse((p / 'script.json').exists())
