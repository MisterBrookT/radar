import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from radar import __main__ as cli, script
from radar.common import save, load


class SmokeTests(unittest.TestCase):
    def test_default_uses_weekly_without_legacy_renderer(self):
        with patch.object(sys, 'argv', ['radar']), patch.object(cli.weekly, 'main') as weekly:
            cli.main()
            weekly.assert_called_once_with([])

    def test_smoke_runs_every_stage_with_small_limits(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sys, 'argv', ['radar', '--legacy', '--smoke']), patch.object(cli, 'run_dir', return_value=Path(tmp)), patch.object(cli.collect, 'run') as collect, patch.object(cli.rank, 'run') as rank, patch.object(cli.script, 'run') as script_run, patch.object(cli.video, 'run') as video, patch.object(cli.deliver, 'run') as deliver:
            cli.main()
            collect.assert_called_once_with(Path(tmp), paper_days=14, max_pages=8)
            rank.assert_called_once_with(Path(tmp), top=3)
            script_run.assert_called_once_with(Path(tmp), target_chars=(450, 650))
            video.assert_called_once_with(Path(tmp))
            deliver.assert_called_once_with(Path(tmp))

    def test_short_script_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); save(p/'selected.json', [{}])
            draft = {'title':'test','scenes':[{'narration':'字'*550}]}
            with patch.object(script, 'fmt', return_value='source'), patch.object(script, 'llm', return_value=draft) as llm:
                script.run(p, target_chars=(450, 650))
                self.assertIn('450', llm.call_args.args[0])
            self.assertEqual(load(p/'script.json'), draft)
