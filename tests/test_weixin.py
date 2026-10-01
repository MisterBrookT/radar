import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from radar.weixin import Weixin, encrypt_media, make_client, save_private, validate_url


class WeixinTests(unittest.TestCase):
    def test_transport_forces_ipv4_without_send_retries(self):
        with patch('radar.weixin.httpx.HTTPTransport') as transport, patch('radar.weixin.httpx.Client') as client:
            make_client(120)
            transport.assert_called_once_with(local_address='0.0.0.0', trust_env=False, retries=0)
            self.assertFalse(client.call_args.kwargs['follow_redirects'])
            self.assertEqual(client.call_args.kwargs['timeout'].connect, 10)

    def test_hosts_are_restricted(self):
        validate_url('https://ilinkai.weixin.qq.com')
        validate_url('https://novac2c.cdn.weixin.qq.com/c2c/upload', cdn=True)
        for url in ('http://ilinkai.weixin.qq.com', 'https://evil.example',
                    'https://ilinkai.weixin.qq.com.evil.example',
                    'https://user@ilinkai.weixin.qq.com', 'https://ilinkai.weixin.qq.com:8443'):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_encryption_padding_and_key_encoding(self):
        key = bytes(range(16))
        ciphertext, encoded = encrypt_media(b'x' * 16, key)
        self.assertEqual(len(ciphertext), 32)
        self.assertEqual(base64.b64decode(encoded), key.hex().encode())
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        decrypt = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
        self.assertEqual(decrypt.update(ciphertext) + decrypt.finalize(), b'x' * 16 + b'\x10' * 16)

    def test_private_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'account.json'
            save_private(path, {'token': 'test'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), {'token': 'test'})

    def test_missing_context_prevents_any_network_call(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Weixin(Path(directory))
            save_private(client.account_path, {'token': 'test', 'userId': 'owner',
                                             'baseUrl': 'https://ilinkai.weixin.qq.com'})
            with patch.object(client, 'call') as call:
                with self.assertRaisesRegex(RuntimeError, 'fresh message'):
                    client.send('', 'hello')
                call.assert_not_called()

    def test_unknown_outcome_is_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Weixin(Path(directory))
            save_private(client.account_path, {'token': 'test', 'userId': 'owner',
                                             'baseUrl': 'https://ilinkai.weixin.qq.com'})
            save_private(client.state_path, {'context': 'test', 'context_at': time.time()})
            with patch.object(client, 'call', side_effect=TimeoutError) as call:
                first = client.send('', 'hello')
                second = client.send('', 'hello')
                self.assertEqual(first['status'], 'unknown')
                self.assertEqual(second['status'], 'unknown')
                self.assertEqual(call.call_count, 1)

    def test_only_owner_direct_messages_refresh_context(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Weixin(Path(directory))
            save_private(client.account_path, {'userId': 'owner'})
            messages = [{'from_user_id': 'stranger', 'message_type': 1, 'context_token': 'bad'},
                        {'from_user_id': 'owner', 'message_type': 1, 'group_id': 'group', 'context_token': 'bad'}]
            with patch.object(client, 'call', return_value={'msgs': messages}):
                self.assertFalse(client.receive_context()['context_ready'])
            messages.append({'from_user_id': 'owner', 'message_type': 1, 'context_token': 'good'})
            with patch.object(client, 'call', return_value={'msgs': messages}):
                self.assertTrue(client.receive_context()['context_ready'])

    def test_accepted_delivery_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Weixin(Path(directory))
            save_private(client.account_path, {'token': 'test', 'userId': 'owner'})
            save_private(client.state_path, {'context': 'test', 'context_at': time.time()})
            with patch.object(client, 'call', return_value={'ret': 0}) as call:
                self.assertTrue(client.send('', 'hello')['success'])
                self.assertTrue(client.send('', 'hello')['success'])
                self.assertEqual(call.call_count, 1)

    def test_empty_http_success_acknowledgement_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Weixin(Path(directory))
            save_private(client.account_path, {'token': 'test', 'userId': 'owner',
                                             'baseUrl': 'https://ilinkai.weixin.qq.com'})
            save_private(client.state_path, {'context': 'test', 'context_at': time.time()})
            with patch.object(client, 'call', return_value={}):
                self.assertTrue(client.send('', 'hello')['success'])
