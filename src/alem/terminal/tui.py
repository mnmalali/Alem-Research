"""Persistent terminal interface over Alem's existing model and research capabilities."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import Input, RichLog, Static

from alem.extensions import PluginManager
from alem.models import get_provider, model_status, save_api_key, set_default_model
from alem.workflows import start_workflow
from alem.workspace import Workspace

from .mascot import OWL, PALETTE
from .model_picker import ModelPicker


def owl_text(*, color: bool = True) -> Text:
    """Render paired pixels with Rich styles; Textual owns terminal color negotiation."""

    art = Text()
    for y in range(0, len(OWL), 2):
        for x in range(len(OWL[0])):
            top = PALETTE.get(OWL[y][x])
            bottom = PALETTE.get(OWL[y + 1][x])
            if color and (top or bottom):
                foreground = top or bottom
                background = bottom if top and bottom else None
                style = Style(
                    color=f"rgb({foreground[0]},{foreground[1]},{foreground[2]})",
                    bgcolor=(
                        f"rgb({background[0]},{background[1]},{background[2]})"
                        if background
                        else None
                    ),
                )
                art.append("▀" if top else "▄", style)
            elif top and bottom:
                art.append("█")
            elif top or bottom:
                art.append("▀" if top else "▄")
            else:
                art.append(" ")
        if y < len(OWL) - 2:
            art.append("\n")
    return art


class AlemApp(App[None]):
    """A research composer that remains active until /exit or Ctrl+Q."""

    TITLE = "Alem Research"
    BINDINGS = [
        ("ctrl+q", "quit", "Exit"),
        ("ctrl+c", "cancel_operation", "Cancel operation"),
        ("ctrl+m", "select_model", "Select model"),
        ("f1", "show_help", "Help"),
        ("pageup", "scroll_up", "Scroll up"),
        ("pagedown", "scroll_down", "Scroll down"),
    ]
    CSS = """
    Screen { background: #25282d; color: #f5f1ff; }
    #main { width: 100%; height: 100%; padding: 0 1; }
    #brand { height: 9; width: 100%; }
    #owl { width: 20; height: 9; }
    #wordmark { width: 1fr; height: 9; content-align: left middle;
                color: #8b5cf6; text-style: bold; }
    #overview { height: 8; width: 100%; border: round #5b21b6; padding: 0 1; }
    #overview-title { color: #fbbf24; text-style: bold; height: 1; }
    #overview-details { height: 5; width: 100%; }
    #conversation { height: 1fr; width: 100%; border: round #5b21b6; margin-top: 1; }
    #activity { height: 1fr; width: 100%; }
    #live { height: auto; max-height: 8; width: 100%; color: #ddd6fe; }
    #composer { height: 3; width: 100%; border: round #8b5cf6; margin-top: 1; }
    #status { height: 1; width: 100%; color: #ddd6fe; }
    Input { background: #36323f; color: white; border: none; height: 1; }
    Input:focus { border: none; }
    #composer Input { width: 100%; }
    """

    def __init__(self, workspace: Workspace, *, no_color: bool = False):
        super().__init__()
        self.workspace = workspace
        self.no_color = (
            no_color or "NO_COLOR" in os.environ or os.environ.get("TERM", "").lower() == "dumb"
        )
        self.history: list[dict[str, str]] = []
        self.cancel_event: threading.Event | None = None
        self.pending_login: str | None = None
        self.operation = "idle"

    def compose(self) -> ComposeResult:
        with Vertical(id="main"):
            with Horizontal(id="brand"):
                yield Static(owl_text(color=not self.no_color), id="owl")
                yield Static("ALEM RESEARCH\nResearch deeper.", id="wordmark")
            with Vertical(id="overview"):
                yield Static("WORKSPACE  /  RESEARCH WORKFLOWS", id="overview-title")
                yield Static(id="overview-details")
            with Vertical(id="conversation"):
                yield RichLog(id="activity", wrap=True, markup=False, highlight=False)
                yield Static("", id="live")
            with Vertical(id="composer"):
                yield Input(placeholder="Ask a research question or type /help …", id="prompt")
            yield Static(id="status")

    def on_mount(self) -> None:
        self.refresh_context()
        self._line("Welcome to Alem Research. Ask a question, or type /help.")
        if not model_status(self.workspace)["current"]:
            self._line("No model selected. Type /model for setup guidance.")
        self.query_one("#prompt", Input).focus()

    def on_resize(self, event: Resize) -> None:
        compact = event.size.width < 62 or event.size.height < 27
        self.query_one("#owl", Static).display = not compact
        self.query_one("#brand", Horizontal).styles.height = 3 if compact else 9
        self.query_one("#wordmark", Static).styles.height = 3 if compact else 9
        self.query_one("#overview", Vertical).styles.height = 6 if compact else 8

    def refresh_context(self) -> None:
        current = model_status(self.workspace)
        selected = current["current"] or "none"
        provider = selected.partition("/")[0] if selected != "none" else "none"
        root = self.workspace.root
        project_count = len(list((root / "projects").glob("*/PROJECT.md")))
        details = (
            f"Workspace: {root.name}   Projects: {project_count}   Model: {selected}\n"
            f"Provider: {provider}   Agents: researcher · reviewer · verifier · writer\n"
            "Workflows: /deepresearch  /lit  /review  /audit  /replicate  /recipe\n"
            "                 /compare  /draft  /autoresearch  /summarize"
        )
        self.query_one("#overview-details", Static).update(details)
        self.query_one("#status", Static).update(
            f" {root.name}  │  {selected}  │  {provider}  │  {self.operation}"
            "  │  Ctrl+C cancel · F1 help · Ctrl+Q exit"
        )

    def _line(self, value: str) -> None:
        self.query_one("#activity", RichLog).write(value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        event.input.value = ""
        if value:
            self.submit(value)

    def submit(self, value: str) -> None:
        if self.pending_login is not None:
            provider = self.pending_login
            self.pending_login = None
            prompt = self.query_one("#prompt", Input)
            prompt.password = False
            prompt.placeholder = "Ask a research question or type /help …"
            try:
                save_api_key(self.workspace, provider, value)
                self._line(f"Credential stored for {provider}. Choose a model.")
                self.refresh_context()
                self.action_select_model()
            except Exception as exc:
                self._line(f"Credential setup failed: {exc}")
            return
        if value.startswith("/"):
            self._command(value)
            return
        if self.cancel_event is not None:
            self._line("An operation is active. Press Ctrl+C to cancel it.")
            return
        if not model_status(self.workspace)["current"]:
            self._line("Choose a model first: /model, then /model PROVIDER/MODEL.")
            return
        self._line(f"You: {value}")
        self.history.append({"role": "user", "content": value})
        self.cancel_event = threading.Event()
        self.operation = "requesting model response"
        self.refresh_context()
        self.query_one("#live", Static).update("Alem: connecting…")
        self._run_question(list(self.history), self.cancel_event)

    @work(thread=True, exclusive=True)
    def _run_question(self, messages: list[dict[str, str]], cancel: threading.Event) -> None:
        pieces: list[str] = []
        try:
            manager = PluginManager(self.workspace.root)
            for event in manager.invoke_model_stream({"messages": messages}, cancel=cancel):
                if cancel.is_set():
                    break
                if event["type"] == "delta":
                    pieces.append(event["text"])
                    self.call_from_thread(self._show_partial, "".join(pieces))
                elif event["type"] == "complete":
                    self.call_from_thread(self._finish_response, "".join(pieces), event)
                    return
            self.call_from_thread(self._finish_response, "".join(pieces), {"cancelled": True})
        except Exception as exc:
            self.call_from_thread(self._finish_response, "".join(pieces), {"error": str(exc)})

    def _show_partial(self, value: str) -> None:
        self.query_one("#live", Static).update("Alem: " + value)

    def _finish_response(self, value: str, result: dict) -> None:
        self.query_one("#live", Static).update("")
        if value and not result.get("cancelled"):
            self.history.append({"role": "assistant", "content": value})
            self._line("Alem: " + value)
        if result.get("error"):
            self._line(f"Provider error: {result['error']}")
        elif result.get("cancelled"):
            self._line("Operation cancelled.")
        else:
            self._line(f"Completed · {result.get('provider', 'model')} / {result.get('model', '')}")
        self.cancel_event = None
        self.operation = "idle"
        self.refresh_context()

    def action_cancel_operation(self) -> None:
        if self.cancel_event is not None:
            self.cancel_event.set()
            self._line("Cancellation requested…")

    def action_show_help(self) -> None:
        self._command("/help")

    def action_select_model(self) -> None:
        if self.cancel_event is not None:
            self._line("Finish or cancel the active operation before changing models.")
            return
        self.push_screen(ModelPicker(self.workspace), self._model_chosen)

    def _model_chosen(self, model: str | None) -> None:
        if not model:
            return
        if model.startswith("login:"):
            self._begin_model_login(model.removeprefix("login:"))
            return
        try:
            set_default_model(self.workspace, model)
        except Exception as exc:
            self._line(f"Model error: {exc}")
            return
        self._line(f"Selected model: {model}")
        self.refresh_context()
        self.query_one("#prompt", Input).focus()

    def _begin_model_login(self, provider: str) -> None:
        try:
            spec = get_provider(provider)
            if spec.support_state != "supported" or "api-key" not in spec.auth_methods:
                self._line(f"API-key setup unavailable for {provider}: {spec.notes}")
                return
            self.pending_login = provider
            prompt = self.query_one("#prompt", Input)
            prompt.password = True
            prompt.placeholder = f"Paste {provider} API key; Enter stores it, Esc cancels"
            self._line(f"Enter the {provider} API key in the hidden composer. Esc cancels.")
            prompt.focus()
        except Exception as exc:
            self._line(f"Provider setup unavailable: {exc}")

    def action_scroll_up(self) -> None:
        self.query_one("#activity", RichLog).scroll_page_up()

    def action_scroll_down(self) -> None:
        self.query_one("#activity", RichLog).scroll_page_down()

    def _command(self, value: str) -> None:
        name, _, argument = value.partition(" ")
        argument = argument.strip()
        if name == "/exit":
            self.exit()
        elif name == "/help":
            self._line(
                "Commands: /deepresearch /lit /review /audit /replicate /recipe "
                "/compare /draft /autoresearch /summarize /model /provider /help /exit"
            )
            self._line("Use /model or Ctrl+M to choose a model; ←→ changes provider.")
            self._line(
                "Research workflows require an active project and a configured capability. "
                "Use `alem workflow list` for available specifications."
            )
        elif name == "/provider":
            status = model_status(self.workspace)
            for item in status["providers"]:
                self._line(
                    f"{item['id']}: {item['readiness']} · {item['support_state']} · "
                    f"auth {', '.join(item['auth_methods'])}"
                )
        elif name == "/model":
            if not argument:
                self.action_select_model()
            elif argument.startswith("login "):
                self._begin_model_login(argument[6:].strip())
            else:
                try:
                    if self.cancel_event is not None:
                        self._line("Finish or cancel the active operation before changing models.")
                        return
                    provider_id = argument.partition("/")[0]
                    readiness = next(
                        item["readiness"]
                        for item in model_status(self.workspace)["providers"]
                        if item["id"] == provider_id
                    )
                    if readiness not in {"configured", "local"}:
                        self._line(
                            f"{provider_id} is {readiness}. Use /model login {provider_id} "
                            "or /provider for setup status."
                        )
                        return
                    set_default_model(self.workspace, argument)
                    self._line(f"Selected model: {argument}")
                    self.refresh_context()
                except Exception as exc:
                    self._line(f"Model error: {exc}")
        elif name == "/summarize":
            if not argument:
                self._line(
                    "Usage: /summarize TEXT. Summaries use the configured model; "
                    "verify source claims independently."
                )
            else:
                self.submit(
                    "Summarize the following supplied text, preserving uncertainty and "
                    "identifying claims that need verification:\n" + argument
                )
        elif name in {"/lit", "/deepresearch"}:
            workflow = {
                "/lit": "literature-review",
                "/deepresearch": "full-research-lifecycle",
            }[name]
            if not argument:
                self._line(f"Usage: {name} PROJECT. Starts the existing {workflow} workflow.")
            else:
                try:
                    run = start_workflow(self.workspace, workflow, argument)
                    self._line(
                        f"Started {workflow}: {run['id']} · {run['state']} · "
                        f"next step {run['current_step']}."
                    )
                    self._line("Use `alem workflow status RUN --project PROJECT` to inspect gates.")
                except Exception as exc:
                    self._line(f"Workflow unavailable: {exc}")
        elif name in {
            "/review",
            "/audit",
            "/replicate",
            "/recipe",
            "/compare",
            "/draft",
            "/autoresearch",
        }:
            self._line(
                f"{name}: no direct interactive workflow is configured. Inspect "
                "`alem workflow list` and start a project run with "
                "`alem workflow start WORKFLOW --project PROJECT`. "
                "Human approval gates remain in the workflow engine."
            )
        else:
            self._line(f"Unknown command: {name}. Type /help.")

    def on_key(self, event) -> None:
        if event.key == "escape" and self.pending_login is not None:
            self.pending_login = None
            prompt = self.query_one("#prompt", Input)
            prompt.value = ""
            prompt.password = False
            prompt.placeholder = "Ask a research question or type /help …"
            self._line("Credential setup cancelled.")
            event.stop()


def run_tui(workspace: Workspace | Path, *, no_color: bool = False) -> None:
    ws = workspace if isinstance(workspace, Workspace) else Workspace(workspace)
    AlemApp(ws, no_color=no_color).run()
