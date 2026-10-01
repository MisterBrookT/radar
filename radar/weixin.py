"""Standalone Weixin iLink bot transport. No Hermes runtime or account imports.

Private state defaults to ~/.config/genui-weixin. Send outcomes are recorded
before transmission; uncertain outcomes are never automatically replayed.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx

API = 'https://ilinkai.weixin.qq.com'
CDN = 'https://novac2c.cdn.weixin.qq.com/c2c'
HEADERS = {'iLink-App-Id': 'bot', 'iLink-App-ClientVersion': str((2 << 16) | (4 << 8) | 8)}


def make_client(timeout):
    # DGX has broken IPv6 egress to the media CDN. Bind IPv4 locally rather
    # than changing global DNS, and never transport-retry a message submission.
    transport = httpx.HTTPTransport(local_address='0.0.0.0', trust_env=False, retries=0)
    return httpx.Client(transport=transport, trust_env=False,
                        timeout=httpx.Timeout(timeout, connect=10), follow_redirects=False)


def validate_url(url, cdn=False):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    allowed = host.endswith('.cdn.weixin.qq.com') if cdn else host == 'ilinkai.weixin.qq.com'
    if (parsed.scheme != 'https' or not allowed or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError('Unexpected Weixin host; refusing to send credentials or media')


def save_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_private(path):
    return json.loads(path.read_text()) if path.exists() else {}


def encrypt_media(plaintext, key):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    padding = 16 - len(plaintext) % 16
    encryptor = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
    encrypted = encryptor.update(plaintext + bytes([padding]) * padding) + encryptor.finalize()
    return encrypted, base64.b64encode(key.hex().encode('ascii')).decode('ascii')


class Weixin:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get('GENUI_WEIXIN_HOME', Path.home() / '.config/genui-weixin'))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.account_path = self.directory / 'account.json'
        self.state_path = self.directory / 'state.json'

    def call(self, method, payload=None, authenticated=True):
        account = load_private(self.account_path) if authenticated else {}
        base = account.get('baseUrl', API).rstrip('/')
        validate_url(base)
        headers = dict(HEADERS)
        if authenticated:
            headers.update({'AuthorizationType': 'ilink_bot_token',
                            'Authorization': 'Bearer ' + account['token'],
                            'X-WECHAT-UIN': base64.b64encode(str(secrets.randbits(32)).encode()).decode()})
        with make_client(45) as client:
            url = base + '/ilink/bot/' + method
            if payload is None:
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, headers=headers, json={**payload,
                    'base_info': {'channel_version': '2.4.8', 'bot_agent': 'Radar/0.1'}})
            if response.status_code != 200:
                raise RuntimeError(f'Weixin HTTP {response.status_code}')
            result = response.json()
            if not isinstance(result, dict):
                raise RuntimeError('Malformed Weixin acknowledgement')
            if result.get('ret', 0) or result.get('errcode', 0):
                raise RuntimeError(f'Weixin rejected request: {result.get("errcode", result.get("ret"))}')
            return result

    def begin_login(self):
        result = self.call('get_bot_qrcode?bot_type=3', authenticated=False)
        if not result.get('qrcode') or not result.get('qrcode_img_content'):
            raise RuntimeError('Weixin did not issue a QR code')
        save_private(self.directory / 'login.json', result)
        return result['qrcode_img_content']

    def finish_login(self):
        pending = self.directory / 'login.json'
        result = self.call('get_qrcode_status?' + urlencode({'qrcode': load_private(pending)['qrcode']}),
                           authenticated=False)
        if result.get('status') != 'confirmed':
            return {'status': result.get('status', 'unknown')}
        old = load_private(self.account_path)
        owner = result.get('ilink_user_id')
        if not owner or not result.get('bot_token') or not result.get('ilink_bot_id'):
            raise RuntimeError('Incomplete login response')
        if old.get('userId') and old['userId'] != owner:
            raise RuntimeError('Different WeChat owner; refusing to replace account')
        base = result.get('baseurl') or API
        validate_url(base)
        save_private(self.account_path, {'token': result['bot_token'], 'userId': owner,
                     'accountId': result['ilink_bot_id'], 'baseUrl': base})
        save_private(self.state_path, {})
        pending.unlink()
        return {'status': 'confirmed', 'next': 'Send a fresh message to the linked bot'}

    def receive_context(self):
        state = load_private(self.state_path)
        account = load_private(self.account_path)
        result = self.call('getupdates', {'get_updates_buf': state.get('cursor', '')})
        state['cursor'] = result.get('get_updates_buf', state.get('cursor', ''))
        for message in result.get('msgs', []):
            if (message.get('from_user_id') == account['userId'] and message.get('message_type') == 1
                    and not message.get('group_id') and message.get('context_token')):
                state['context'] = message['context_token']
                state['context_at'] = time.time()
        save_private(self.state_path, state)
        return {'context_ready': bool(state.get('context')) and time.time() - state.get('context_at', 0) < 86400}

    def upload_video(self, video, owner):
        plaintext = Path(video).read_bytes()
        if not plaintext or len(plaintext) > 100 * 1024 * 1024:
            raise ValueError('Video must be nonempty and at most 100 MiB')
        key, filekey = secrets.token_bytes(16), secrets.token_hex(16)
        encrypted, encoded_key = encrypt_media(plaintext, key)
        digest = hashlib.md5(plaintext).hexdigest()  # iLink wire protocol, not a security checksum
        upload = self.call('getuploadurl', {'filekey': filekey, 'media_type': 2, 'to_user_id': owner,
            'rawsize': len(plaintext), 'rawfilemd5': digest, 'filesize': len(encrypted),
            'no_need_thumb': True, 'aeskey': key.hex()})
        url = upload.get('upload_full_url')
        if not url and upload.get('upload_param'):
            url = CDN + '/upload?' + urlencode({'encrypted_query_param': upload['upload_param'], 'filekey': filekey})
        if not url:
            raise RuntimeError('Weixin returned no media upload URL')
        validate_url(url, cdn=True)
        with make_client(120) as client:
            response = client.post(url, content=encrypted, headers={'Content-Type': 'application/octet-stream'})
        parameter = response.headers.get('x-encrypted-param')
        if response.status_code != 200 or not parameter:
            raise RuntimeError('Encrypted video upload failed')
        return {'type': 5, 'video_item': {'media': {'encrypt_query_param': parameter,
                'aes_key': encoded_key, 'encrypt_type': 1}, 'video_size': len(encrypted),
                'play_length': 0, 'video_md5': digest}}

    def send(self, video, text):
        lock = self.directory / 'delivery.lock'
        with os.fdopen(os.open(lock, os.O_CREAT | os.O_RDWR, 0o600), 'w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            return self._send_locked(video, text)

    def _send_locked(self, video, text):
        account, state = load_private(self.account_path), load_private(self.state_path)
        if not state.get('context') or time.time() - state.get('context_at', 0) >= 86400:
            raise RuntimeError('Send a fresh message to the linked bot before delivery')
        digest = hashlib.sha256(text.encode())
        if video:
            digest.update(Path(video).read_bytes())
        ledger = self.directory / ('delivery-' + digest.hexdigest() + '.json')
        previous = load_private(ledger)
        if previous:
            return previous
        items = [{'type': 1, 'text_item': {'text': text}}] if text else []
        if video:
            items.append(self.upload_video(video, account['userId']))
        if not items:
            raise ValueError('Empty delivery')
        client_id = 'radar-' + secrets.token_hex(16)
        result = {'success': False, 'status': 'unknown', 'client_id': client_id}
        save_private(ledger, result)  # Crash or timeout after this point cannot trigger replay.
        try:
            for index, item in enumerate(items):
                response = self.call('sendmessage', {'msg': {'from_user_id': '', 'to_user_id': account['userId'],
                    'client_id': client_id + '-' + str(index), 'message_type': 2, 'message_state': 2,
                    'context_token': state['context'], 'item_list': [item]}})
                # Successful iLink sends can return HTTP 200 with {}: zero
                # status fields are omitted. call() already checked HTTP/JSON.
                if response.get('ret', 0) != 0 or response.get('errcode', 0) != 0:
                    break
                result['accepted_parts'] = index + 1
                save_private(ledger, result)
            else:
                result.update(success=True, status='accepted')
        except Exception:
            pass  # The network may fail after acceptance; never infer a safe retry.
        save_private(ledger, result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['login', 'finish', 'context', 'status'])
    args = parser.parse_args()
    client = Weixin()
    if args.command == 'login':
        print(client.begin_login())
    elif args.command == 'finish':
        print(json.dumps(client.finish_login()))
    elif args.command == 'context':
        print(json.dumps(client.receive_context()))
    else:
        state = load_private(client.state_path)
        print(json.dumps({'linked': client.account_path.exists(),
                          'context_ready': bool(state.get('context')) and time.time() - state.get('context_at', 0) < 86400}))


if __name__ == '__main__':
    main()
