"""Patch only the private refunds API source snapshot with the profile gateway."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text()
    if source.count(old) != 1:
        raise ValueError(f"expected_one_patch_anchor:{path.name}")
    path.write_text(source.replace(old, new, 1))


def install(root: Path) -> None:
    tokenizer = root / "skillloop/runtime/gateway.py"
    tokenizer_source = tokenizer.read_text()
    if 'def __init__(self, container: str | None = None):' not in tokenizer_source:
        replace_once(tokenizer, 'def __init__(self, container: str = "skillloop-m4-sglang"):',
            'def __init__(self, container: str | None = None):')
    if 'self.container = container or os.environ.get("SKILLLOOP_TOKENIZER_CONTAINER"' not in tokenizer.read_text():
        replace_once(tokenizer, "self.container = container\n",
            'self.container = container or os.environ.get("SKILLLOOP_TOKENIZER_CONTAINER", "skillloop-m4-sglang")\n')

    runner = root / "scripts/dgx_m5_development.py"
    import_anchor = "from skillloop.runtime.gateway import ExactDockerTokenizer, SGLangGateway\n"
    api_import = "from skillloop.runtime.qwen_gateway import QwenAPIGateway\n"
    if api_import not in runner.read_text():
        replace_once(runner, import_anchor, import_anchor + api_import)

    gateway_anchor = """gateway=SGLangGateway("http://127.0.0.1:30000", tokenizer,
                    enable_thinking=config.get("thinking", True),
                    max_context_tokens=config.get("max_context_tokens", 16384),
                    max_output_tokens=config.get("max_output_tokens", 2048),
                    timeout_seconds=config.get("provider_timeout_seconds", 180)),"""
    gateway_api = """gateway=(QwenAPIGateway(tokenizer=tokenizer,
                        config=json.loads(Path(config["api_config_file"]).read_text()),
                        response_root=output / "api-responses",
                        shared_budget_path=Path(config["api_shared_budget_path"]),
                        purpose=config.get("api_purpose", "calibration"),
                        max_context_tokens=config.get("max_context_tokens", 16384),
                        max_output_tokens=config.get("max_output_tokens", 2048))
                        if config.get("provider") == "qwen_api" else
                        SGLangGateway(gateway_url, tokenizer,
                            enable_thinking=config.get("thinking", True),
                            max_context_tokens=config.get("max_context_tokens", 16384),
                            max_output_tokens=config.get("max_output_tokens", 2048),
                            timeout_seconds=config.get("provider_timeout_seconds", 180))),"""
    if "gateway=(QwenAPIGateway(" not in runner.read_text():
        replace_once(runner, gateway_anchor, gateway_api)

    # Publishing moves a run to `finalizing` in the proxy. Do not ask the model
    # for another turn after a successful publish: any subsequent tool batch
    # would be rejected as skipped_after_failure even though publication worked.
    adapter = root / "skillloop/runtime/adapter.py"
    adapter_source = adapter.read_text()
    terminal_anchor = "                    messages.append({\"role\": \"tool\", \"tool_call_id\": native_calls[index][\"id\"],\n                                     \"content\": json.dumps(model_body, ensure_ascii=False)})\n        except GatewayError as exc:\n"
    terminal_patch = "                    messages.append({\"role\": \"tool\", \"tool_call_id\": native_calls[index][\"id\"],\n                                     \"content\": json.dumps(model_body, ensure_ascii=False)})\n                if published:\n                    terminal_reason = \"completed\"\n                    break\n        except GatewayError as exc:\n"
    if 'if published:\n                    terminal_reason = "completed"' not in adapter_source:
        replace_once(adapter, terminal_anchor, terminal_patch)
    os.chmod(adapter, 0o600)
    os.chmod(runner, 0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    install(parser.parse_args().repo.resolve())
