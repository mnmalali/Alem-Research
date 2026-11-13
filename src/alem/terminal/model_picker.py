"""Keyboard-driven model chooser over Alem's configured provider gateway."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from alem.models import ModelGateway, list_models, model_status
from alem.workspace import Workspace


class ModelPicker(ModalScreen[str | None]):
    """Choose a model by provider, then return its full provider/model reference."""

    BINDINGS = [
        ("escape", "dismiss_picker", "Close"),
        ("left", "previous_provider", "Previous provider"),
        ("right", "next_provider", "Next provider"),
    ]
    CSS = """
    ModelPicker { align: center middle; background: #1a1033 75%; }
    #model-dialog { width: 64; max-width: 96%; height: 19; max-height: 90%;
                    background: #25282d; border: round #8b5cf6; padding: 1 2; }
    #model-heading { height: 2; color: #fbbf24; text-style: bold; }
    #model-provider { height: 2; color: #ddd6fe; }
    #model-options { height: 1fr; background: #36323f; border: none; }
    #model-options > .option-list--option-highlighted { background: #5b21b6; color: white; }
    #model-hint { height: 3; color: #ddd6fe; }
    """

    def __init__(self, workspace: Workspace):
        super().__init__()
        self.workspace = workspace
        status = model_status(workspace)
        self.current = status["current"]
        self.providers = [
            item for item in status["providers"] if item["support_state"] == "supported"
        ]
        current_provider = self.current.partition("/")[0] if self.current else ""
        configured = next(
            (item["id"] for item in self.providers if item["readiness"] == "configured"),
            "",
        )
        initial = current_provider or configured or "openai"
        self.provider_index = next(
            (i for i, item in enumerate(self.providers) if item["id"] == initial), 0
        )
        self.local_models: dict[str, list[str] | None] = {}
        self.local_errors: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="model-dialog"):
            yield Static("SELECT MODEL", id="model-heading")
            yield Static(id="model-provider")
            yield OptionList(id="model-options")
            yield Static(id="model-hint")

    def on_mount(self) -> None:
        for provider in self.providers:
            if provider["readiness"] == "local":
                self.local_models[provider["id"]] = None
                self._load_local_models(provider["id"])
        self._refresh()
        self.query_one("#model-options", OptionList).focus()

    @work(thread=True)
    def _load_local_models(self, provider: str) -> None:
        try:
            models = ModelGateway(self.workspace).available_models(provider)
            identifiers = list(dict.fromkeys(model.id for model in models))
            error = "" if identifiers else "The endpoint returned no models."
        except Exception:
            identifiers = []
            error = "Endpoint unavailable. Start the local model server and reopen /model."
        self.app.call_from_thread(self._show_local_models, provider, identifiers, error)

    def _show_local_models(self, provider: str, identifiers: list[str], error: str) -> None:
        self.local_models[provider] = identifiers
        self.local_errors[provider] = error
        if self.is_mounted and self.providers[self.provider_index]["id"] == provider:
            self._refresh()

    def _refresh(self) -> None:
        provider = self.providers[self.provider_index]
        identifier = provider["id"]
        self.query_one("#model-provider", Static).update(
            f"◀  {provider['name']}  ({self.provider_index + 1}/{len(self.providers)})  ▶"
            f"   ·   {provider['readiness']}"
        )
        options = self.query_one("#model-options", OptionList)
        options.clear_options()
        readiness = provider["readiness"]
        if readiness == "local":
            models = self.local_models.get(identifier)
            if models is None:
                hint = "Checking installed models at the local endpoint…"
                models = []
            elif not models:
                hint = self.local_errors.get(identifier, "No installed models found.")
            else:
                hint = "↑↓ choose · Enter select · ←→ provider · Esc close"
        elif readiness == "configured":
            models = [item["id"] for item in list_models(self.workspace, identifier)]
            hint = "↑↓ choose · Enter select · ←→ provider · Esc close"
        elif readiness == "needs-credentials":
            models = []
            options.add_option(Option("Set up API key →", id=f"login:{identifier}"))
            options.highlighted = 0
            hint = f"Enter to set up {identifier} · ←→ provider · Esc close"
        else:
            models = []
            hint = f"Configure an endpoint with alem model configure {identifier}."
        for model in models:
            reference = f"{identifier}/{model}"
            label = f"● {model}" if reference == self.current else f"  {model}"
            options.add_option(Option(label, id=reference))
        if models:
            selected = next(
                (i for i, model in enumerate(models) if f"{identifier}/{model}" == self.current),
                0,
            )
            options.highlighted = selected
        self.query_one("#model-hint", Static).update(hint)

    def action_previous_provider(self) -> None:
        self.provider_index = (self.provider_index - 1) % len(self.providers)
        self._refresh()

    def action_next_provider(self) -> None:
        self.provider_index = (self.provider_index + 1) % len(self.providers)
        self._refresh()

    def action_dismiss_picker(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(event.option.id)
