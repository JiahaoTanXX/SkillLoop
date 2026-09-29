"""Profile-local gateway that routes M6 refund calls through the private Qwen API."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from skillloop.runtime.gateway import GatewayError, ExactDockerTokenizer
from skillloop.runtime.qwen_api import QwenAPITransport


class QwenAPIGateway:
    def __init__(self, *, tokenizer: ExactDockerTokenizer, config: dict[str, Any],
                 response_root: Path, shared_budget_path: Path,
                 purpose: str = "calibration", max_context_tokens: int = 16_384,
                 max_output_tokens: int = 2_048):
        self.tokenizer = tokenizer
        self.max_context_tokens = max_context_tokens
        self.max_output_tokens = max_output_tokens
        self.purpose = purpose
        self.transport = QwenAPITransport(config, Path(response_root), shared_budget_path=shared_budget_path)

    def count_final(self, text: str) -> int:
        return self.tokenizer.count_text(text)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                 *, remaining_seconds: float) -> tuple[dict[str, Any], int, float]:
        started = time.monotonic()
        prompt_tokens = self.tokenizer.count(messages, tools, enable_thinking=False) + 66
        if prompt_tokens + self.max_output_tokens > self.max_context_tokens:
            raise GatewayError("context_exceeded")
        remaining = remaining_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise GatewayError("run_deadline")
        request_id = "m6-joint-api-refunds-" + uuid.uuid4().hex
        try:
            response, usage = self.transport.complete(request_id=request_id, messages=messages,
                tools=tools, max_output_tokens=self.max_output_tokens, purpose=self.purpose,
                timeout_seconds=remaining)
        except (TimeoutError, OSError, ValueError) as error:
            raise GatewayError("api_provider_or_protocol_error") from error
        response["_skillloop_private_transport_audit"] = {
            "request_id": request_id,
            "preflight_prompt_tokens": prompt_tokens,
            "reasoning_tokens": usage["reasoning_tokens"],
            "reasoning_usage_status": usage["reasoning_usage_status"],
            "raw_response_digest": usage["raw_response_digest"],
            "reserved_micro_rmb": usage["reserved_micro_rmb"],
            "charged_micro_rmb": usage["charged_micro_rmb"],
            "known_usage_cost_micro_rmb": usage["known_usage_cost_micro_rmb"],
            "reservation_retained": usage["reservation_retained"],
        }
        return response, prompt_tokens, time.monotonic() - started
