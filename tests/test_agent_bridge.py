from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1] / "skills" / "llm-wiki" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import agent_bridge as bridge  # noqa: E402
import launch_wiki  # noqa: E402


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class RequestRecorder:
    def __init__(self, payload: dict):
        self.payload = payload
        self.request = None
        self.timeout = None

    def __call__(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return FakeResponse(self.payload)

    @property
    def body(self) -> dict:
        return json.loads(self.request.data.decode())


class ProviderTests(unittest.TestCase):
    def call_provider(self, provider: str, response: dict) -> RequestRecorder:
        recorder = RequestRecorder(response)
        env_name = bridge.API_KEY_ENV[provider][0]
        with patch.dict(
            os.environ,
            {
                env_name: "test-secret-value",
                "LLMWIKI_MODEL": f"test-{provider}-model",
            },
            clear=True,
        ):
            answer = bridge.ask_api(provider, "safe prompt", opener=recorder)
        self.assertEqual(answer, "mock answer")
        self.assertNotIn("test-secret-value", recorder.request.full_url)
        return recorder

    def test_openrouter_request_and_response(self):
        call = self.call_provider(
            "openrouter",
            {"choices": [{"message": {"content": "mock answer"}}]},
        )
        self.assertEqual(call.request.full_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(call.request.get_header("Authorization"), "Bearer test-secret-value")
        self.assertEqual(call.body["messages"][0]["role"], "system")
        self.assertEqual(call.body["messages"][1]["content"], "safe prompt")

    def test_openai_request_and_response(self):
        call = self.call_provider("openai", {"output_text": "mock answer"})
        self.assertEqual(call.request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(call.body["input"], "safe prompt")

    def test_gemini_request_and_response(self):
        call = self.call_provider(
            "gemini",
            {"candidates": [{"content": {"parts": [{"text": "mock answer"}]}}]},
        )
        self.assertIn(":generateContent", call.request.full_url)
        self.assertEqual(call.request.get_header("X-goog-api-key"), "test-secret-value")
        self.assertNotIn("key=", call.request.full_url)

    def test_anthropic_request_and_response(self):
        call = self.call_provider(
            "anthropic",
            {"content": [{"type": "text", "text": "mock answer"}]},
        )
        self.assertEqual(call.request.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(call.request.get_header("X-api-key"), "test-secret-value")
        self.assertEqual(call.request.get_header("Anthropic-version"), "2023-06-01")

    def test_health_status_never_contains_key(self):
        with patch.dict(
            os.environ,
            {
                "LLMWIKI_PROVIDER": "openai",
                "LLMWIKI_AI_ENABLED": "1",
                "OPENAI_API_KEY": "never-return-this",
            },
            clear=True,
        ):
            encoded = json.dumps(bridge.provider_status())
        self.assertNotIn("never-return-this", encoded)
        self.assertIn("****", encoded)

    def test_prompt_caps_context_and_marks_documents_untrusted(self):
        pages = [
            {"id": f"{index}.md", "title": f"Page {index}", "body": "x" * 10_000}
            for index in range(20)
        ]
        prompt = bridge.build_prompt("질문", pages)
        context = prompt.split("<wiki-context>\n", 1)[1].split("\n</wiki-context>", 1)[0]
        self.assertLessEqual(len(context.encode()), bridge.MAX_CONTEXT_BYTES)
        self.assertIn("신뢰할 수 없는 데이터", bridge.SYSTEM_INSTRUCTION)
        self.assertLessEqual(prompt.count("<wiki-document "), bridge.TOP_K)


class EnvironmentTests(unittest.TestCase):
    def test_dotenv_parser_is_literal_and_allowlisted(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "OPENAI_API_KEY=$(not-executed)\nUNRELATED=value\nLLMWIKI_AI_ENABLED=1\n",
                "utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                launch_wiki.load_workspace_env(root)
                self.assertEqual(os.environ["OPENAI_API_KEY"], "$(not-executed)")
                self.assertEqual(os.environ["LLMWIKI_AI_ENABLED"], "1")
                self.assertNotIn("UNRELATED", os.environ)


if __name__ == "__main__":
    unittest.main()
