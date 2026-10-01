import os
import unittest
from unittest import mock

import httpx

from radar import common


def resp(status, payload):
    return httpx.Response(status, json=payload, request=httpx.Request("POST", "http://x"))


ANTH_ENV = {
    "GENUI_LLM_PROVIDER": "anthropic",
    "GENUI_LLM_BASE_URL": "https://example.test/",
    "GENUI_LLM_MODEL": "claude-test",
    "GENUI_LLM_API_KEY": "k",
}


class QwenDefaultTest(unittest.TestCase):
    def test_qwen_default_route(self):
        env = {"DASHSCOPE_API_KEY": "d"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(common.httpx, "post") as post:
            post.return_value = resp(200, {"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]})
            self.assertEqual(common.llm("hi"), {"a": 1})
            self.assertEqual(post.call_args.args[0], common.QWEN_URL)
            self.assertEqual(post.call_args.kwargs["json"]["model"], common.STRONG_MODEL)


class AnthropicTest(unittest.TestCase):
    def test_messages_json_and_env_model_overrides(self):
        payload = {"model": "claude-test", "content": [{"type": "text", "text": '{"keep": [0]}'}]}
        with mock.patch.dict(os.environ, ANTH_ENV, clear=True), mock.patch.object(common.httpx, "post") as post:
            post.return_value = resp(200, payload)
            self.assertEqual(common.llm("hi", model=common.STRONG_MODEL), {"keep": [0]})
            self.assertEqual(post.call_args.args[0], "https://example.test/v1/messages")
            body = post.call_args.kwargs["json"]
            self.assertEqual(body["model"], "claude-test")
            self.assertNotIn("temperature", body)  # Opus 5 rejects this parameter.
            self.assertEqual(post.call_args.kwargs["headers"]["x-api-key"], "k")
            self.assertEqual(common.last_response_model(), "claude-test")

    def test_text_mode(self):
        payload = {"model": "claude-test", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
        with mock.patch.dict(os.environ, ANTH_ENV, clear=True), mock.patch.object(common.httpx, "post") as post:
            post.return_value = resp(200, payload)
            self.assertEqual(common.llm("hi", as_json=False), "ab")

    def test_retries_transient_then_succeeds(self):
        ok = resp(200, {"model": "claude-test", "content": [{"type": "text", "text": "{}"}]})
        with mock.patch.dict(os.environ, ANTH_ENV, clear=True), \
                mock.patch.object(common.httpx, "post") as post, mock.patch.object(common.time, "sleep"):
            post.side_effect = [resp(529, {}), resp(503, {}), ok]
            self.assertEqual(common.llm("hi"), {})
            self.assertEqual(post.call_count, 3)

    def test_retries_bounded(self):
        with mock.patch.dict(os.environ, ANTH_ENV, clear=True), \
                mock.patch.object(common.httpx, "post") as post, mock.patch.object(common.time, "sleep"):
            post.return_value = resp(503, {})
            with self.assertRaises(httpx.HTTPStatusError):
                common.llm("hi")
            self.assertEqual(post.call_count, common.MAX_ATTEMPTS)

    def test_non_transient_not_retried(self):
        with mock.patch.dict(os.environ, ANTH_ENV, clear=True), \
                mock.patch.object(common.httpx, "post") as post, mock.patch.object(common.time, "sleep"):
            post.return_value = resp(400, {})
            with self.assertRaises(httpx.HTTPStatusError):
                common.llm("hi")
            self.assertEqual(post.call_count, 1)

    def test_missing_model_no_fallback(self):
        env = {k: v for k, v in ANTH_ENV.items() if k != "GENUI_LLM_MODEL"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(common.httpx, "post") as post:
            with self.assertRaises(RuntimeError):
                common.llm("hi")
            post.assert_not_called()

    def test_response_model_mismatch_raises(self):
        payload = {"model": "other-model", "content": [{"type": "text", "text": "{}"}]}
        with mock.patch.dict(os.environ, ANTH_ENV, clear=True), mock.patch.object(common.httpx, "post") as post:
            post.return_value = resp(200, payload)
            with self.assertRaises(RuntimeError):
                common.llm("hi")


if __name__ == "__main__":
    unittest.main()
