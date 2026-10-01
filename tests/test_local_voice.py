import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from radar import video


class LocalVoiceTests(unittest.TestCase):
    def test_piper_uses_local_process_not_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            model=Path(tmp)/'voice.onnx'; model.touch()
            out=Path(tmp)/'voice.wav'
            env={'GENUI_TTS_PROVIDER':'piper','GENUI_PIPER_MODEL':str(model),'GENUI_PIPER_PYTHON':'/local/python'}
            with patch.dict(video.os.environ,env), patch.object(video.subprocess,'run') as run, patch.object(video.httpx,'Client') as cloud:
                video.tts('Hello brook.',out)
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs['input'],'Hello brook.')
                self.assertIn('piper',run.call_args.args[0])
                cloud.assert_not_called()

    def test_english_captions_keep_words(self):
        text=' '.join(['Generative interfaces adapt to what people need.']*5)
        caps=video.caption_lines(text)
        self.assertEqual(' '.join(caps),text)
        self.assertTrue(all(len(c)<=64 for c in caps))
