from __future__ import annotations

import io
import json
import os
import stat
from pathlib import Path

import pytest

from alem.cli import main
from alem.extensions.api import ExecutionResponse
from alem.extensions.manager import PluginManager
from alem.models import (
    CredentialStore,
    ModelConfigStore,
    ModelError,
    ModelGateway,
    TransientModelError,
    UnsupportedAuthError,
    model_status,
    parse_model_catalog,
    set_model_fallbacks,
    validate_base_url,
    validate_login_method,
)
from alem.terminal.mascot import print_owl, render_ansi
from alem.workspace import Workspace


def make_workspace(root: Path) -> Workspace:
    root.mkdir(parents=True, exist_ok=True)
    (root / "alem.toml").write_text(
        """[alem]\nworkspace_version = 1\n[plugins]\napi_version = '1.0'\n""",
        encoding="utf-8",
    )
    return Workspace(root)


def test_mascot_color_and_redirect_fallback() -> None:
    assert "\x1b[" in render_ansi(True)
    assert "\x1b[" not in render_ansi(False)

    output = io.StringIO()
    print_owl("Research deeper.", file=output)
    value = output.getvalue()
    assert "\x1b[" not in value
    assert "Research deeper." in value


def test_mascot_handles_file_like_object_without_isatty() -> None:
    class Sink:
        encoding = "ascii"

        def __init__(self) -> None:
            self.value = ""

        def write(self, value: str) -> int:
            self.value += value
            return len(value)

        def flush(self) -> None:
            return None

    sink = Sink()
    print_owl(file=sink)  # type: ignore[arg-type]
    assert "\x1b[" not in sink.value
    assert "#" in sink.value


def test_credential_precedence_and_redacted_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    store = CredentialStore(workspace)
    store.set_api_key("openai", "local-secret")
    assert store.path.is_file()
    if os.name != "nt":
        assert stat.S_IMODE(store.path.stat().st_mode) & 0o077 == 0

    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    spec_status = model_status(workspace)
    openai = next(item for item in spec_status["providers"] if item["id"] == "openai")
    assert openai["credential_source"] == "environment:OPENAI_API_KEY"
    assert "secret" not in json.dumps(spec_status)


def test_auth_states_and_url_validation(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    with pytest.raises(UnsupportedAuthError, match="private subscription token flows"):
        validate_login_method("openai", "oauth")
    with pytest.raises(UnsupportedAuthError):
        validate_login_method("openai-codex", "oauth")
    assert validate_base_url("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1"
    with pytest.raises(ModelError, match="loopback"):
        validate_base_url("http://remote.example/v1")
    assert (
        next(item for item in model_status(workspace)["providers"] if item["id"] == "openai-codex")[
            "readiness"
        ]
        == "unsupported"
    )


def test_supported_provider_matrix_is_explicit() -> None:
    status = model_status(Workspace(Path.cwd()))
    providers = {item["id"]: item for item in status["providers"]}
    for provider in (
        "openai",
        "anthropic",
        "openrouter",
        "deepseek",
        "dashscope",
        "zhipu",
        "moonshot",
    ):
        assert providers[provider]["support_state"] == "supported"
        assert providers[provider]["base_url"].startswith("https://")
    assert providers["openai-codex"]["support_state"] == "unsupported"
    assert providers["google-gemini"]["support_state"] == "catalogued"


def test_model_catalog_parsing_and_gateway_protocol(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    CredentialStore(workspace).set_api_key("openai", "test-secret")
    ModelConfigStore(workspace).set_current("openai/test-model")
    captured: list[object] = []

    class Response:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "test-model",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "hello"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"total_tokens": 3},
                }
            ).encode()

    def opener(request: object, timeout: float) -> Response:
        captured.append(request)
        return Response()

    parsed = parse_model_catalog("openai", {"data": [{"id": "new-model"}, "other-model"]})
    assert [item.id for item in parsed] == ["new-model", "other-model"]
    result = ModelGateway(workspace, opener=opener).complete([{"role": "user", "content": "hi"}])
    assert result["content"] == "hello"
    assert result["usage"] == {"total_tokens": 3}
    assert len(captured) == 1


def test_available_models_reads_local_catalog_without_a_prompt(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    requests = []

    class Response:
        def read(self) -> bytes:
            return b'{"data":[{"id":"installed-owl"},{"id":"other-model"}]}'

    def opener(request, timeout):
        requests.append((request, timeout))
        return Response()

    models = ModelGateway(workspace, opener=opener).available_models("ollama")
    assert [model.id for model in models] == ["installed-owl", "other-model"]
    request, timeout = requests[0]
    assert request.get_method() == "GET"
    assert request.full_url == "http://127.0.0.1:11434/v1/models"
    assert request.data is None
    assert timeout == 3.0


def test_anthropic_messages_protocol_is_normalized(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    CredentialStore(workspace).set_api_key("anthropic", "test-secret")
    ModelConfigStore(workspace).set_current("anthropic/claude-test")

    class Response:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "claude-test",
                    "content": [{"type": "text", "text": "hello"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            ).encode()

    result = ModelGateway(workspace, opener=lambda request, timeout: Response()).complete(
        [{"role": "user", "content": "hi"}]
    )
    assert result["provider"] == "anthropic"
    assert result["content"] == "hello"
    assert result["finish_reason"] == "end_turn"


def test_transient_model_failures_follow_ordered_fallbacks(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    ModelConfigStore(workspace).set_current("openai/primary")
    set_model_fallbacks(
        workspace,
        "model_completion",
        ["openrouter/fallback-model"],
    )
    gateway = ModelGateway(workspace)
    attempted: list[str] = []

    def complete(
        messages: list[object], *, model: str | None = None, **kwargs: object
    ) -> dict[str, object]:
        assert model is not None
        attempted.append(model)
        if model == "openai/primary":
            raise TransientModelError("temporary outage")
        return {
            "content": "fallback",
            "model": model,
            "provider": "openrouter",
            "finish_reason": "stop",
            "tool_calls": [],
            "usage": {},
        }

    gateway.complete = complete  # type: ignore[method-assign]
    response = gateway.invoke({"messages": [{"role": "user", "content": "hi"}]})
    assert attempted == ["openai/primary", "openrouter/fallback-model"]
    assert response.metadata["fallback_used"] == "openrouter/fallback-model"
    assert response.metadata["fallback_failures"][0]["classification"] == "transient"


def test_model_gateway_enters_contract_validated_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    output = {
        "content": "ok",
        "model": "test-model",
        "provider": "openai",
        "finish_reason": "stop",
        "tool_calls": [],
        "usage": {},
    }

    def fake_invoke(
        self: ModelGateway, payload: object, *, operation: str = "invoke"
    ) -> ExecutionResponse:
        return ExecutionResponse(output, {"provider": "openai", "operation": operation})

    monkeypatch.setattr(ModelGateway, "invoke", fake_invoke)
    response = PluginManager(workspace.root).invoke(
        "model_completion",
        {"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.output["content"] == "ok"
    assert response.metadata["provider"] == "org.alem.model-gateway"


def test_model_cli_json_and_no_ansi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = make_workspace(tmp_path / "workspace")
    output = io.StringIO()
    with monkeypatch.context() as context:
        context.setattr("sys.stdout", output)
        assert main(["--workspace", str(workspace.root), "model", "providers", "--json"]) == 0
    parsed = json.loads(output.getvalue())
    assert any(item["id"] == "openai" for item in parsed["providers"])
    assert "\x1b[" not in output.getvalue()
