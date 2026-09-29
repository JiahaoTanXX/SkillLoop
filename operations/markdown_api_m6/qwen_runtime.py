"""Experimental qwen3.8-flash adapter for the isolated Markdown M6 profile.

Unknown reasoning usage is returned as unknown and remains visible in the raw
response trace. Unknown usage retains the conservative shared-ledger reserve.
This adapter never marks API calibration or M6 admission ready.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from skillloop.protocol import digest_jcs
from skillloop.protection.api_budget import ScopedAPIBudget


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args):
        raise ValueError("api_redirect_denied")


class QwenExperimentalTransport:
    """Send one request, retain raw evidence, and never substitute usage fields."""

    def __init__(self, config: dict, *, response_root: Path, ledger_path: Path):
        if (config.get("base_url") != "https://maas.qianwenaiapi.com/compatible-mode/v1"
                or config.get("model") != "qwen3.8-flash"
                or config.get("enable_thinking") is not False
                or config.get("pricing_verified") is not True):
            raise ValueError("api_identity_or_pricing_not_admitted")
        response_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if response_root.stat().st_mode & 0o077:
            raise ValueError("api_response_directory_permissions")
        key_path = Path(config["credential_file"])
        if key_path.stat().st_mode & 0o077:
            raise ValueError("api_credential_permissions")
        self.key = key_path.read_text().strip()
        self.config = dict(config)
        self.response_root = response_root
        # Reuse the existing shared ledger. Validate its legacy 10 RMB binding,
        # then enforce the joint M6 campaign ceiling with BEGIN IMMEDIATE.
        self.budget = ScopedAPIBudget(
            ledger_path,
            input_rate=config["input_price_per_million_rmb"],
            output_rate=config["output_price_per_million_rmb"],
            limit_rmb="50.00",
            legacy_limit_rmb=config["max_cost_rmb"],
        )
        os.chmod(ledger_path, 0o600)

    def complete(self, *, request_id: str, messages: list[dict], tools: list[dict],
                 max_output_tokens: int = 2048, timeout_seconds: float = 120) -> tuple[dict, dict]:
        if not 1 <= max_output_tokens <= 2048:
            raise ValueError("api_output_cap")
        input_bound = 16384 - max_output_tokens
        reserved = self.budget.reserve(request_id, input_bound, max_output_tokens)
        path = self.response_root / (digest_jcs(request_id)[7:] + ".response.bin")
        if path.exists():
            raise ValueError("api_response_already_exists")
        payload = {
            "model": self.config["model"], "messages": messages,
            "max_tokens": max_output_tokens, "temperature": 1.0, "top_p": 0.95,
            "enable_thinking": False,
        }
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        req = urllib.request.Request(
            self.config["base_url"] + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
        )
        with urllib.request.build_opener(NoRedirect).open(
            req, timeout=min(timeout_seconds, 120)
        ) as response:
            raw = response.read(4_194_305)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if len(raw) > 4_194_304:
            raise ValueError("api_response_limit")
        value = json.loads(raw)
        if value.get("model") != self.config["model"]:
            raise ValueError("api_returned_model_mismatch")
        usage = value.get("usage") or {}
        prompt_tokens, completion_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        reasoning_tokens = usage.get("reasoning_tokens")
        if reasoning_tokens is None:
            reasoning_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        choices = value.get("choices") or []
        if not choices:
            raise ValueError("api_choices_missing")
        if (type(prompt_tokens) is not int or type(completion_tokens) is not int
                or prompt_tokens > input_bound or completion_tokens > max_output_tokens):
            raise ValueError("api_usage_not_admitted")
        if choices[0].get("finish_reason") == "length" or choices[0].get("message", {}).get("reasoning_content"):
            raise ValueError("api_truncation_or_reasoning_content")
        status = "missing" if reasoning_tokens is None else "zero" if reasoning_tokens == 0 else "nonzero"
        charged = None
        if reasoning_tokens is not None:
            charged = self.budget.finish(request_id, prompt_tokens, completion_tokens)
        # When reasoning usage is missing, keep the full reservation. The raw
        # provider response remains unchanged and carries no synthetic zero.
        return value, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
            "reasoning_usage_status": status,
            "charged_micro_rmb": charged,
            "conservative_reserved_micro_rmb": reserved if charged is None else None,
            "response_path": str(path),
        }


class QwenAPIGateway:
    """AgentAdapter-compatible gateway backed by the experimental transport."""

    def __init__(self, transport: QwenExperimentalTransport, tokenizer: Any, *,
                 max_context_tokens: int = 16384, max_output_tokens: int = 2048,
                 timeout_seconds: float = 120):
        from skillloop.runtime.gateway import GatewayError

        self.gateway_error = GatewayError
        self.transport = transport
        self.tokenizer = tokenizer
        self.max_context_tokens = max_context_tokens
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.enable_thinking = False

    def count_final(self, text: str) -> int:
        return self.tokenizer.count_text(text)

    def complete(self, messages: list[dict], tools: list[dict], *,
                 remaining_seconds: float) -> tuple[dict, int, float]:
        started = time.monotonic()
        if remaining_seconds <= 0:
            raise self.gateway_error("run_deadline")
        preflight = self.tokenizer.count(messages, tools, enable_thinking=False)
        if preflight + self.max_output_tokens > self.max_context_tokens:
            raise self.gateway_error("context_exceeded")
        request_id = "m6-joint-api-markdown-" + uuid.uuid4().hex
        try:
            response, usage = self.transport.complete(
                request_id=request_id, messages=messages, tools=tools,
                max_output_tokens=self.max_output_tokens,
                timeout_seconds=min(self.timeout_seconds, remaining_seconds),
            )
        except (TimeoutError, OSError, ValueError) as error:
            raise self.gateway_error("api_runtime_error") from error
        observed_prompt = response.get("usage", {}).get("prompt_tokens")
        if type(observed_prompt) is not int or observed_prompt + self.max_output_tokens > self.max_context_tokens:
            raise self.gateway_error("api_observed_context_exceeded", response=response)
        return response, preflight, time.monotonic() - started


def runtime_executor(output: Path, profile_id: str, skill_bytes: bytes, request: dict,
                     binding: dict, config: dict, mutation: Any, attempt_index: int,
                     deployment_epoch: str) -> dict:
    """Run the existing trusted Proxy/Agent pipeline with the API gateway."""
    from skillloop.runtime.adapter import AgentAdapter
    from skillloop.runtime.client import ProxyClient
    from skillloop.runtime.gateway import ExactDockerTokenizer

    private_root = Path(os.environ["SKILLLOOP_M6_API_PRIVATE"]).resolve()
    api_private = Path(os.environ["SKILLLOOP_API_PRIVATE"]).resolve()
    ledger_path = Path(os.environ["SKILLLOOP_API_LEDGER"]).resolve()
    response_root = private_root / "api-responses"
    api_config = json.loads((api_private / "config.json").read_text(encoding="utf-8"))
    transport = QwenExperimentalTransport(api_config, response_root=response_root, ledger_path=ledger_path)
    tokenizer = ExactDockerTokenizer(os.environ.get(
        "SKILLLOOP_TOKENIZER_CONTAINER", "skillloop-m4-sglang"))
    try:
        result = AgentAdapter(
            proxy=ProxyClient(output / "sockets"),
            gateway=QwenAPIGateway(
                transport, tokenizer,
                max_context_tokens=config.get("max_context_tokens", 16384),
                max_output_tokens=config.get("max_output_tokens", 2048),
                timeout_seconds=config.get("provider_timeout_seconds", 120),
            ),
            private_root=output / "evidence",
        ).run(
            profile_id=profile_id, skill_bytes=skill_bytes, run_request=request,
            task_binding=binding, fence=1, trust_revision=1,
            deployment_epoch=deployment_epoch,
            deadline_seconds=config.get("agent_deadline_seconds", 235),
            rendered_mutation=mutation, attempt_index=attempt_index,
        )
        # Aggregate exact raw usage attestations from the just-finished private
        # trace. Missing reasoning remains null; no zero is synthesized.
        events = [json.loads(line) for line in Path(result["trace_path"]).read_text().splitlines()]
        responses = [event["response"] for event in events if event.get("type") == "model_response"]
        reasoning = []
        for response in responses:
            usage = response.get("usage") or {}
            count = usage.get("reasoning_tokens")
            if count is None:
                count = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            reasoning.append(count)
        result["usage_attestation"] = {
            "model_responses": len(responses),
            "reasoning_tokens": sum(reasoning) if all(type(item) is int for item in reasoning) else None,
            "reasoning_usage_missing": sum(item is None for item in reasoning),
            "reasoning_usage_nonzero": sum(type(item) is int and item != 0 for item in reasoning),
        }
        return result
    finally:
        tokenizer.close()
