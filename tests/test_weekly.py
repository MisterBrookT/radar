import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from radar import weekly
from radar.common import load, save
from radar.briefing_policy import validate_weekly_script


class WeeklyTests(unittest.TestCase):
    def test_adjacent_paper_cannot_fill_a_quiet_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'candidates.json', [{'title': 'VisCanvas', 'date': '2026-10-01', 'text': 'A fixed canvas generating charts'}])
            save(root/'collection-status.json', {'window': {'start': '2026-09-25', 'end_inclusive': '2026-10-01'}})
            with patch.object(weekly, 'llm', return_value={'items': [{'index': 0, 'role': 'adjacent', 'reason': 'Generates charts, not UI'}]}) as model:
                weekly.plan(root)
            self.assertEqual(model.call_count, 1)
            self.assertEqual(load(root/'plan.json')['stories'], [])
            self.assertEqual(load(root/'selected.json'), [])

    def test_plan_rejects_adjacent_main_source(self):
        with self.assertRaisesRegex(ValueError, 'core'):
            weekly.validate_plan({'title': 'Week', 'overview': 'Line', 'stories': [
                {'name': 'Charts', 'sources': [0], 'core_insight': 'Insight', 'why_it_matters': 'Reason'}]},
                [{'role': 'adjacent'}], 4)

    def test_plan_has_no_platform_quota_or_story_floor(self):
        p = {'title': 'One important release', 'overview': 'One main line', 'stories': [
            {'name': 'UI generation', 'sources': [0, 1], 'core_insight': 'Insight', 'why_it_matters': 'Reason'}]}
        weekly.validate_plan(p, [{'role': 'direct'}, {'role': 'direct'}], 4)
        p['stories'][0]['sources'] = [-1]
        with self.assertRaises(ValueError):
            weekly.validate_plan(p, [{'role': 'direct'}], 4)

    def test_weekly_script_requires_overview_before_details(self):
        def scene(role, eid):
            return {'id': eid, 'heading': 'Idea', 'visual_type': 'statement', 'role': role, 'story': 0,
                    'purpose': 'Explain the core idea', 'contains_boundary': role == 'evidence',
                    'events': [{'id': eid, 'say': 'An idea.', 'subtitle': 'An idea.',
                                'segments': [{'en': 'An idea.', 'zh': '一个想法。'}]}]}
        script = {'briefing': {'cadence': 'weekly', 'policy_version': 1}, 'language': 'en',
                  'caption_languages': ['en', 'zh-CN'], 'stories': [{'sources': [0]}],
                  'scenes': [scene('overview', 'one'), scene('evidence', 'two')]}
        validate_weekly_script(script, [{'topic_role': 'direct'}])
        broken = copy.deepcopy(script)
        broken['scenes'][0]['role'] = 'example'
        with self.assertRaises(ValueError):
            validate_weekly_script(broken, [{'topic_role': 'direct'}])
        with self.assertRaises(ValueError):
            validate_weekly_script(script, [{'topic_role': 'adjacent'}])

    def test_input_provenance_changes_when_selection_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'script.json', {'scenes': []})
            save(root/'evidence.json', {'sources': []})
            save(root/'selected.json', [{'title': 'First release'}])
            original = weekly.input_hashes(root)
            save(root/'selected.json', [{'title': 'Different release'}])
            self.assertNotEqual(original, weekly.input_hashes(root))

    def test_delivery_rejects_stale_video_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'video.mp4').write_bytes(b'new video')
            (root/'script.json').write_text('{}')
            digest = hashlib.sha256(b'new video').hexdigest()
            save(root/'verification.json', {'full_decode': 'passed', 'video_sha256': digest,
                 'script_sha256': hashlib.sha256(b'{}').hexdigest()})
            save(root/'video-review.json', {'video_sha256': 'old video'})
            with patch.object(weekly, 'reviewed'):
                with self.assertRaisesRegex(ValueError, 'stale'):
                    weekly.delivery_ready(root)

    def test_empty_collection_does_not_invoke_a_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'candidates.json', [])
            save(root/'collection-status.json', {'window': {}})
            with patch.object(weekly, 'llm') as model:
                weekly.plan(root)
            model.assert_not_called()
            self.assertTrue(load(root/'plan.json')['no_core_headlines'])
