from __future__ import annotations

import asyncio
import io
import json
import threading
from pathlib import Path

from rich.console import Console
from textual.widgets import Input, OptionList, RichLog

from alem.extensions import PluginManager
from alem.models import CredentialStore, ModelConfigStore, ModelGateway, get_provider
from alem.terminal.model_picker import ModelPicker
from alem.terminal.tui import AlemApp, owl_text
from alem.workspace import Workspace


def test_colored_owl_retains_all_brand_colors() -> None:
    art = owl_text()
    style_text = " ".join(str(span.style) for span in art.spans)
    for color in ("139,92,246", "91,33,182", "221,214,254", "26,16,51", "251,191,36"):
        assert color in style_text


def test_owl_reduces_to_256_colors_and_plain_blocks(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    output = io.StringIO()
    Console(file=output, force_terminal=True, color_system="256", width=30).print(owl_text())
    assert "38;5;" in output.getvalue() or "48;5;" in output.getvalue()
    assert "38;2;" not in output.getvalue()
    assert not owl_text(color=False).spans


def test_tui_stays_open_and_commands_work(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text("[alem]\nworkspace_version=1\n[plugins]\napi_version='1.0'\n")

    async def run() -> None:
        app = AlemApp(Workspace(root))
        async with app.run_test(size=(80, 30)) as pilot:
            assert app.is_running
            prompt = app.query_one("#prompt", Input)
            prompt.value = "/provider"
            await pilot.press("enter")
            await pilot.pause()
            assert app.query_one("#activity", RichLog).lines
            prompt.value = "/lit missing-project"
            await pilot.press("enter")
            await pilot.pause()
            prompt.value = "/exit"
            await pilot.press("enter")

    asyncio.run(run())


def test_guided_api_key_setup_hides_secret(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text("[alem]\nworkspace_version=1\n[plugins]\napi_version='1.0'\n")

    async def run() -> None:
        app = AlemApp(Workspace(root))
        async with app.run_test(size=(100, 30)) as pilot:
            prompt = app.query_one("#prompt", Input)
            prompt.value = "/model login openai"
            await pilot.press("enter")
            assert prompt.password
            prompt.value = "test-private-value"
            await pilot.press("enter")
            assert not prompt.password
            stored, _ = CredentialStore(Workspace(root)).resolve(get_provider("openai"))
            assert stored == "test-private-value"
            assert "test-private-value" not in str(app.query_one("#activity", RichLog).lines)
            assert isinstance(app.screen, ModelPicker)
            await pilot.press("escape")
            prompt.value = "/exit"
            await pilot.press("enter")

    asyncio.run(run())


def test_model_picker_selects_and_persists_configured_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "example-test-key")
    workspace = Workspace(tmp_path)

    async def run() -> None:
        app = AlemApp(workspace)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.press("ctrl+m")
            await pilot.pause()
            assert isinstance(app.screen, ModelPicker)
            options = app.screen.query_one("#model-options", OptionList)
            assert options.option_count == 2
            await pilot.press("down", "enter")
            await pilot.pause()
            assert ModelConfigStore(workspace).read()["current"] == "openai/gpt-4o"
            assert "openai/gpt-4o" in str(app.query_one("#status").render())
            app.query_one("#prompt", Input).value = "/model"
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ModelPicker)
            assert app.screen.query_one("#model-options", OptionList).highlighted == 1
            await pilot.press("escape")
            await pilot.pause()
            assert ModelConfigStore(workspace).read()["current"] == "openai/gpt-4o"

    asyncio.run(run())


def test_picker_guides_unconfigured_provider_and_uses_local_catalog(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = Workspace(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def local_models(self, provider, *, timeout=3.0):
        from alem.models import ModelSpec

        return [ModelSpec("installed-owl", provider)] if provider == "ollama" else []

    monkeypatch.setattr(ModelGateway, "available_models", local_models)

    async def run() -> None:
        app = AlemApp(workspace)
        async with app.run_test(size=(100, 30)) as pilot:
            prompt = app.query_one("#prompt", Input)
            prompt.value = "/model"
            await pilot.press("enter")
            await pilot.pause(delay=0.1)
            assert isinstance(app.screen, ModelPicker)
            assert "set up openai" in str(app.screen.query_one("#model-hint").render())
            assert app.screen.query_one("#model-options", OptionList).option_count == 1
            await pilot.press("enter")
            await pilot.pause()
            assert prompt.password
            await pilot.press("escape")
            assert not prompt.password
            prompt.value = "/model"
            await pilot.press("enter")
            await pilot.pause()
            for _ in range(8):
                await pilot.press("right")
            await pilot.pause()
            assert "Ollama" in str(app.screen.query_one("#model-provider").render())
            assert app.screen.query_one("#model-options", OptionList).option_count == 1
            await pilot.press("enter")
            await pilot.pause()
            assert ModelConfigStore(workspace).read()["current"] == "ollama/installed-owl"

    asyncio.run(run())


def test_no_model_and_provider_failure_are_visible(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text("[alem]\nworkspace_version=1\n[plugins]\napi_version='1.0'\n")

    def failed_stream(self, payload, *, cancel=None):
        raise RuntimeError("provider unavailable")
        yield  # pragma: no cover

    monkeypatch.setattr(PluginManager, "invoke_model_stream", failed_stream)

    async def run() -> None:
        app = AlemApp(Workspace(root))
        async with app.run_test(size=(80, 30)) as pilot:
            prompt = app.query_one("#prompt", Input)
            prompt.value = "question"
            await pilot.press("enter")
            await pilot.pause()
            assert app.history == []
            assert "Choose a model" in str(app.query_one("#activity", RichLog).lines)
            ModelConfigStore(Workspace(root)).set_current("ollama/test-model")
            prompt.value = "question"
            await pilot.press("enter")
            await pilot.pause(delay=0.1)
            assert app.cancel_event is None
            assert "provider unavailable" in str(app.query_one("#activity", RichLog).lines)
            prompt.value = "/exit"
            await pilot.press("enter")

    asyncio.run(run())


def test_tui_layout_at_common_terminal_widths(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text("[alem]\nworkspace_version=1\n[plugins]\napi_version='1.0'\n")

    async def run() -> None:
        for width in (80, 100, 120):
            app = AlemApp(Workspace(root))
            async with app.run_test(size=(width, 30)) as pilot:
                await pilot.pause()
                assert app.query_one("#prompt", Input).visible
                assert app.query_one("#conversation").size.width > width // 2
                await pilot.resize_terminal(55, 25)
                await pilot.pause()
                assert not app.query_one("#owl").display
                assert app.query_one("#prompt", Input).visible
                app.exit()

    asyncio.run(run())


def test_real_stream_parser_and_cancel(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    workspace = Workspace(root)
    ModelConfigStore(workspace).set_current("ollama/test-model")

    class Response:
        def __init__(self) -> None:
            self.closed = False

        def __iter__(self):
            chunks = ["first", " second"]
            for piece in chunks:
                yield (
                    "data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}) + "\n"
                ).encode()
            yield b"data: [DONE]\n"

        def close(self) -> None:
            self.closed = True

    response = Response()
    gateway = ModelGateway(workspace, opener=lambda request, timeout: response)
    events = list(gateway.stream([{"role": "user", "content": "hi"}]))
    assert [event["type"] for event in events] == ["delta", "delta", "complete"]
    assert events[-1]["content"] == "first second"
    assert response.closed

    cancelled = threading.Event()
    cancelled.set()
    response = Response()
    result = list(gateway.stream([{"role": "user", "content": "hi"}], cancel=cancelled))
    assert result[-1]["cancelled"] is True
    assert response.closed


def test_composer_displays_gateway_stream(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text("[alem]\nworkspace_version=1\n[plugins]\napi_version='1.0'\n")
    ModelConfigStore(Workspace(root)).set_current("ollama/test-model")

    def fake_stream(self, payload, *, cancel=None):
        assert payload["messages"][-1]["content"] == "hello"
        yield {"type": "delta", "text": "real "}
        yield {"type": "delta", "text": "output"}
        yield {"type": "complete", "provider": "ollama", "model": "test-model"}

    monkeypatch.setattr(PluginManager, "invoke_model_stream", fake_stream)

    async def run() -> None:
        app = AlemApp(Workspace(root))
        async with app.run_test(size=(100, 34)) as pilot:
            prompt = app.query_one("#prompt", Input)
            prompt.value = "hello"
            await pilot.press("enter")
            await pilot.pause(delay=0.1)
            assert app.history[-1] == {"role": "assistant", "content": "real output"}
            assert app.cancel_event is None
            prompt.value = "/exit"
            await pilot.press("enter")

    asyncio.run(run())
