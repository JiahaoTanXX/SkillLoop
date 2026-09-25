"""Loopback SGLang client and exact local chat-template token preflight."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from skillloop.protocol import decode_json


MODEL_ID = "Qwen/Qwen3.8-27B-FP8"

_TOKENIZER_CODE = """
import json,sys
from transformers import AutoTokenizer
payload=json.load(sys.stdin)
tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=True)
messages=payload['messages']
for message in messages:
    if message.get('tool_calls'):
        for call in message['tool_calls']:
            function=call.get('function',call)
            if isinstance(function.get('arguments'),str):
                function['arguments']=json.loads(function['arguments'])
ids=tokenizer.apply_chat_template(messages,tools=payload['tools'],tokenize=True,add_generation_prompt=True)
print(len(ids['input_ids']) if hasattr(ids,'keys') else len(ids))
"""

_TEXT_TOKENIZER_CODE = """
import sys
from transformers import AutoTokenizer
tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=True)
print(len(tokenizer.encode(sys.stdin.read(),add_special_tokens=False)))
"""


class GatewayError(RuntimeError):
    def __init__(self, code: str, response: dict[str, Any] | None = None):
        super().__init__(code)
        self.response = response


class ExactDockerTokenizer:
    """Gateway-owned tokenizer. Prompts enter docker exec via stdin, never argv."""

    def __init__(self, container: str = "skillloop-m4-sglang"):
        self.container = container

    def count(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> int:
        completed = subprocess.run(
            ["docker", "exec", "-i", self.container, "python3", "-c", _TOKENIZER_CODE],
            input=json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
        )
        if completed.returncode != 0:
            raise GatewayError("tokenizer_unavailable")
        try:
            return int(completed.stdout.strip())
        except ValueError as exc:
            raise GatewayError("tokenizer_invalid_count") from exc

    def count_text(self, text: str) -> int:
        completed = subprocess.run(
            ["docker", "exec", "-i", self.container, "python3", "-c", _TEXT_TOKENIZER_CODE],
            input=text.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, check=False,
        )
        if completed.returncode != 0:
            raise GatewayError("tokenizer_unavailable")
        try:
            return int(completed.stdout.strip())
        except ValueError as exc:
            raise GatewayError("tokenizer_invalid_count") from exc


class SGLangGateway:
    def __init__(self, endpoint: str, tokenizer: ExactDockerTokenizer,
                 *, max_context_tokens: int = 16_384, max_output_tokens: int = 2_048,
                 timeout_seconds: float = 180, backend_template_overhead_tokens: int = 66):
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise GatewayError("loopback_endpoint_required")
        self.endpoint = endpoint.rstrip("/")
        self.tokenizer = tokenizer
        self.max_context_tokens = max_context_tokens
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        # Calibrated against SGLang 0.5.19's returned prompt_tokens for the
        # fixed Qwen image/template and tool parser; mismatch fails closed.
        self.backend_template_overhead_tokens = backend_template_overhead_tokens

    def count_final(self, text: str) -> int:
        return self.tokenizer.count_text(text)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                 *, remaining_seconds: float) -> tuple[dict[str, Any], int, float]:
        prompt_tokens = self.tokenizer.count(messages, tools) + self.backend_template_overhead_tokens
        if prompt_tokens + self.max_output_tokens > self.max_context_tokens:
            raise GatewayError("context_exceeded")
        if remaining_seconds <= 0:
            raise GatewayError("run_deadline")
        body = json.dumps({"model": MODEL_ID, "messages": messages, "tools": tools,
                           "tool_choice": "auto", "temperature": 1.0, "top_p": 0.95,
                           "max_tokens": self.max_output_tokens}, ensure_ascii=False).encode()
        request = urllib.request.Request(self.endpoint + "/v1/chat/completions", data=body,
                                         headers={"Content-Type": "application/json"})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout_seconds, remaining_seconds)) as response:
                parsed = decode_json(response.read(4_194_305))
        except (TimeoutError, urllib.error.URLError) as exc:
            raise GatewayError("provider_timeout") from exc
        if type(parsed) is not dict or parsed.get("model") not in {MODEL_ID, "/model"}:
            raise GatewayError("model_identity_mismatch")
        usage = parsed.get("usage") or {}
        if usage.get("prompt_tokens") != prompt_tokens:
            raise GatewayError("tokenizer_mismatch", response=parsed)
        if type(usage.get("completion_tokens")) is not int or usage["completion_tokens"] > self.max_output_tokens:
            raise GatewayError("output_token_limit", response=parsed)
        return parsed, prompt_tokens, time.monotonic() - started
