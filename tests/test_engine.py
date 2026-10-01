import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from radar import engine
from radar.common import save
from radar.topics import load_topic


class EngineTests(unittest.TestCase):
    def test_topic_is_data_not_engine_constant(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'topic.json'
            p.write_text(json.dumps({'name': 'databases', 'title': 'Databases',
                                    'scope': 'Database systems research', 'search_queries': ['database']}))
            self.assertEqual(load_topic(str(p))['name'], 'databases')

    def test_agent_exit_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine.subprocess, 'run', return_value=type('Result', (), {'returncode': 9})()):
            with self.assertRaises(RuntimeError):
                engine.agent(Path(tmp), 'research', 'Do research', 'test-model')

    def test_completed_delivery_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'delivered.json', {'status': 'accepted'})
            with patch.object(engine, 'agent') as agent:
                self.assertEqual(engine.run(root, load_topic(), '2026-10-01'), 'already-delivered')
            agent.assert_not_called()

    def test_unresolved_send_cannot_restart_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'send-attempt.json', {'video_sha256': 'submitted'})
            with self.assertRaisesRegex(RuntimeError, 'replay blocked'):
                engine.run(root, load_topic(), '2026-10-01')

    def test_no_eligible_work_does_not_render_or_send_filler(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(engine.os.environ):
            root = Path(tmp)
            def worker(*args):
                save(root/'plan.json', {'no_core_headlines': True, 'stories': []})
            with patch.object(engine.collect, 'run'), patch.object(engine, 'agent', side_effect=worker), patch.object(engine.minimal_video, 'run') as render, patch.object(engine.deliver, 'run') as send:
                result = engine.run(root, load_topic(), '2026-10-01')
            self.assertEqual(result, 'no-eligible-core-work')
            render.assert_not_called()
            send.assert_not_called()

    def test_cli_no_delivery_passes_explicit_send_false(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine, 'run_dir', return_value=Path(tmp)), patch.object(engine, 'run', return_value='ready') as run:
            engine.main(['--run-id', 'local-example', '--week-ending', '2026-10-01', '--no-delivery'])
            self.assertFalse(run.call_args.kwargs['send'])

    def test_review_false_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'video-review.json', {'video_sha256': 'test', 'opening_overview_checked': False})
            self.assertFalse(engine.review_passed(root))
