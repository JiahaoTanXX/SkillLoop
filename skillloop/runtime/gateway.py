"""Loopback SGLang client and exact local chat-template token preflight."""

from __future__ import annotations

import json
import os
import select
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from skillloop.protocol import decode_json


MODEL_ID = "Qwen/Qwen3.8-27B-FP8"

_TOKENIZER_WORKER_CODE = """
import json,sys
from transformers import AutoTokenizer
tokenizer=AutoTokenizer.from_pretrained('/model',local_files_only=True,trust_remote_code=True)
for line in sys.stdin:
    payload=json.loads(line)
    try:
        if payload['operation']=='text':
            count=len(tokenizer.encode(payload['text'],add_special_tokens=False))
        else:
            messages=payload['messages']
            for message in messages:
                for call in message.get('tool_calls') or []:
                    function=call.get('function',call)
                    if isinstance(function.get('arguments'),str):
                        function['arguments']=json.loads(function['arguments'])
            ids=tokenizer.apply_chat_template(messages,tools=payload['tools'],tokenize=True,
                add_generation_prompt=True,enable_thinking=payload['enable_thinking'])
            count=len(ids['input_ids']) if hasattr(ids,'keys') else len(ids)
        result={'id':payload['id'],'count':count}
    except Exception:
        result={'id':payload['id'],'error':'tokenizer_invalid_input'}
    print(json.dumps(result),flush=True)
"""


class GatewayError(RuntimeError):
    def __init__(self, code: str, response: dict[str, Any] | None = None):
        super().__init__(code)
        self.response = response


class ExactDockerTokenizer:
    """Gateway-owned tokenizer. Prompts enter docker exec via stdin, never argv."""

    def __init__(self, container: str = "skillloop-m4-sglang"):
        self.container = container
        self._text_counts: dict[str, int] = {}
        self._process = None
        self._sequence = 0
        self._lock = threading.Lock()

    def _request(self, payload: dict[str, Any]) -> int:
        # One tokenizer process per owner. It holds no model KV cache and is
        # never reused by a different Runtime, scanner or evaluation role.
        with self._lock:
            if self._process is None:
                self._process = subprocess.Popen(
                    ["docker", "exec", "-i", self.container, "python3", "-u", "-c", _TOKENIZER_WORKER_CODE],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
                os.set_blocking(self._process.stdin.fileno(), False)
            self._sequence += 1
            payload = {**payload, "id": self._sequence}
            try:
                deadline = time.monotonic() + 30
                encoded = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
                if len(encoded) > 8 * 1024 * 1024:
                    raise GatewayError("tokenizer_input_limit")
                offset = 0
                while offset < len(encoded):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not select.select([], [self._process.stdin], [], remaining)[1]:
                        raise GatewayError("tokenizer_unavailable")
                    offset += os.write(self._process.stdin.fileno(), encoded[offset:])
                response = bytearray()
                while b"\n" not in response:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not select.select([self._process.stdout], [], [], remaining)[0]:
                        raise GatewayError("tokenizer_unavailable")
                    chunk = os.read(self._process.stdout.fileno(), 4096)
                    if not chunk or len(response) + len(chunk) > 4096:
                        raise GatewayError("tokenizer_invalid_count")
                    response.extend(chunk)
                parsed = decode_json(bytes(response).strip())
                if (type(parsed) is not dict or parsed.get("id") != self._sequence or
                        type(parsed.get("count")) is not int or parsed["count"] < 0):
                    raise GatewayError("tokenizer_invalid_count")
                return parsed["count"]
            except (OSError, ValueError, GatewayError) as error:
                self.close()
                if isinstance(error, GatewayError):
                    raise
                raise GatewayError("tokenizer_unavailable") from error

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        if process.stdout:
            process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def __del__(self):
        if getattr(self, "_process", None) is not None:
            self.close()

    def count(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
              *, enable_thinking: bool = True) -> int:
        return self._request({"operation": "chat", "messages": messages, "tools": tools,
                              "enable_thinking": enable_thinking})

    def count_text(self, text: str) -> int:
        # Process-local exact-string memoization; never shared between roles.
        # The deployment fixes tokenizer bytes for the lifetime of this object.
        if text in self._text_counts:
            return self._text_counts[text]
        count = self._request({"operation": "text", "text": text})
        self._text_counts[text] = count
        return count


class SGLangGateway:
    def __init__(self, endpoint: str, tokenizer: ExactDockerTokenizer,
                 *, max_context_tokens: int = 16_384, max_output_tokens: int = 2_048,
                 timeout_seconds: float = 180, backend_template_overhead_tokens: int = 66,
                 enable_thinking: bool = True):
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
        self.enable_thinking = enable_thinking

    def count_final(self, text: str) -> int:
        return self.tokenizer.count_text(text)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                 *, remaining_seconds: float) -> tuple[dict[str, Any], int, float]:
        preflight_started = time.monotonic()
        prompt_tokens = self.tokenizer.count(messages, tools,
            enable_thinking=self.enable_thinking) + self.backend_template_overhead_tokens
        remaining_seconds -= time.monotonic() - preflight_started
        if prompt_tokens + self.max_output_tokens > self.max_context_tokens:
            raise GatewayError("context_exceeded")
        if remaining_seconds <= 0:
            raise GatewayError("run_deadline")
        payload = {"model": MODEL_ID, "messages": messages, "tools": tools,
                   "tool_choice": "auto", "temperature": 1.0, "top_p": 0.95,
                   "max_tokens": self.max_output_tokens}
        if not self.enable_thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        body = json.dumps(payload, ensure_ascii=False).encode()
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
        if any(choice.get("finish_reason") == "length" for choice in parsed.get("choices", [])):
            raise GatewayError("output_token_limit", response=parsed)
        return parsed, prompt_tokens, time.monotonic() - started
