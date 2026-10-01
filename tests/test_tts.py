import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from radar import video


class TTSTransportTests(unittest.TestCase):
    def test_tts_and_audio_download_use_ipv4(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(video.os.environ, {'DASHSCOPE_API_KEY':'test'}), patch.object(video.httpx, 'HTTPTransport') as transport, patch.object(video.httpx, 'Client') as client:
            api = client.return_value.__enter__.return_value
            api.post.return_value.status_code = 200
            api.post.return_value.json.return_value = {'output': {'audio': {'url':'https://audio.test/clip.wav'}}}
            api.get.return_value.content = b'wave'
            path = Path(tmp)/'clip.wav'
            video.tts('test', path)
            transport.assert_called_once_with(local_address='0.0.0.0')
            api.post.assert_called_once()
            api.get.assert_called_once()
            api.get.return_value.raise_for_status.assert_called_once()
            self.assertEqual(path.read_bytes(), b'wave')
