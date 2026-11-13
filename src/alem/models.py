"""Provider-neutral model catalog, credentials, and gateway.

The module deliberately uses the Python standard library.  Provider entries
describe what Alem actually knows how to do; unsupported subscription OAuth is
represented explicitly instead of being approximated with private endpoints.
Secrets live only in the workspace-local credential store or the environment
and are never included in status/configuration mappings.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import subprocess
import tempfile
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse

from alem.errors import AlemError
from alem.extensions.api import ExecutionResponse
from alem.workspace import Workspace

MODEL_STATE_VERSION = 1
MODEL_CREDENTIALS_VERSION = 1
MODEL_CAPABILITY = "model_completion"


class ModelError(AlemError):
    """A model configuration, protocol, or transport error."""


class TransientModelError(ModelError):
    """A bounded retry/fallback-worthy provider failure."""


class AuthenticationModelError(ModelError):
    """A credential or permission failure; fallback must not hide it."""


class UnsupportedAuthError(ModelError):
    """The requested provider authentication flow is not supported."""


AuthMethod = Literal["api-key", "oauth", "no-auth", "cloud-credentials"]
SupportState = Literal["supported", "catalogued", "unsupported"]
Protocol = Literal["openai-chat", "anthropic-messages"]


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    provider: str
    context_window: int | None = None
    max_output: int | None = None
    tool_calling: bool | None = None
    vision: bool | None = None
    streaming: bool | None = None
    source: str = "built-in static catalog"

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "context_window": self.context_window,
            "max_output": self.max_output,
            "tool_calling": self.tool_calling,
            "vision": self.vision,
            "streaming": self.streaming,
            "source": self.source,
            "known_in_catalog": True,
        }


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    id: str
    name: str
    support_state: SupportState
    auth_methods: tuple[AuthMethod, ...]
    env_vars: tuple[str, ...] = ()
    default_base_url: str | None = None
    protocol: Protocol = "openai-chat"
    default_models: tuple[ModelSpec, ...] = ()
    notes: str = ""

    @property
    def api_key_required(self) -> bool:
        return "api-key" in self.auth_methods and "no-auth" not in self.auth_methods

    def to_mapping(self, *, base_url: str | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "support_state": self.support_state,
            "auth_methods": list(self.auth_methods),
            "environment_variables": list(self.env_vars),
            "base_url": base_url if base_url is not None else self.default_base_url,
            "protocol": self.protocol,
            "adapter": self.protocol,
            "models": [model.to_mapping() for model in self.default_models],
            "notes": self.notes,
        }


def _model(provider: str, identifier: str) -> ModelSpec:
    return ModelSpec(
        identifier, provider, source="built-in static catalog; verify upstream availability"
    )


def _provider(
    identifier: str,
    name: str,
    *,
    auth_methods: tuple[AuthMethod, ...],
    env_vars: tuple[str, ...] = (),
    base_url: str | None = None,
    protocol: Protocol = "openai-chat",
    models: tuple[str, ...] = (),
    support_state: SupportState = "supported",
    notes: str = "",
) -> ProviderSpec:
    return ProviderSpec(
        identifier,
        name,
        support_state,
        auth_methods,
        env_vars,
        base_url,
        protocol,
        tuple(_model(identifier, item) for item in models),
        notes,
    )


PROVIDERS: tuple[ProviderSpec, ...] = (
    _provider(
        "openai",
        "OpenAI Platform API",
        auth_methods=("api-key",),
        env_vars=("OPENAI_API_KEY",),
        base_url="https://api.openai.com/v1",
        models=("gpt-4o-mini", "gpt-4o"),
        notes="Platform API billing and credentials are separate from ChatGPT subscriptions.",
    ),
    _provider(
        "anthropic",
        "Anthropic API",
        auth_methods=("api-key",),
        env_vars=("ANTHROPIC_API_KEY",),
        base_url="https://api.anthropic.com/v1",
        protocol="anthropic-messages",
        models=("claude-3-5-sonnet-latest",),
    ),
    _provider(
        "openrouter",
        "OpenRouter",
        auth_methods=("api-key",),
        env_vars=("OPENROUTER_API_KEY",),
        base_url="https://openrouter.ai/api/v1",
        models=("openai/gpt-4o-mini",),
        notes="The model ID belongs to OpenRouter's upstream catalog and may change.",
    ),
    _provider(
        "deepseek",
        "DeepSeek",
        auth_methods=("api-key",),
        env_vars=("DEEPSEEK_API_KEY",),
        base_url="https://api.deepseek.com/v1",
        models=("deepseek-chat",),
    ),
    _provider(
        "dashscope",
        "Alibaba DashScope / Qwen",
        auth_methods=("api-key",),
        env_vars=("DASHSCOPE_API_KEY",),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=("qwen-plus",),
    ),
    _provider(
        "zhipu",
        "Zhipu / Z.AI GLM",
        auth_methods=("api-key",),
        env_vars=("ZHIPUAI_API_KEY",),
        base_url="https://open.bigmodel.cn/api/paas/v4",
        models=("glm-4-flash",),
    ),
    _provider(
        "moonshot",
        "Moonshot / Kimi (China endpoint)",
        auth_methods=("api-key",),
        env_vars=("MOONSHOT_API_KEY",),
        base_url="https://api.moonshot.cn/v1",
        models=("moonshot-v1-8k",),
    ),
    _provider(
        "minimax",
        "MiniMax",
        auth_methods=("api-key",),
        env_vars=("MINIMAX_API_KEY",),
        support_state="catalogued",
        models=("MiniMax-Text-01",),
        notes="Catalogued for explicit endpoint configuration; no default endpoint is assumed.",
    ),
    _provider(
        "custom-openai",
        "Custom OpenAI-compatible endpoint",
        auth_methods=("api-key", "no-auth"),
        base_url=None,
        models=("custom-model",),
        notes="Requires `alem model configure custom-openai --base-url ...`.",
    ),
    _provider(
        "ollama",
        "Ollama (local)",
        auth_methods=("no-auth",),
        base_url="http://127.0.0.1:11434/v1",
        models=("llama3.1",),
    ),
    _provider(
        "lm-studio",
        "LM Studio (local)",
        auth_methods=("no-auth",),
        base_url="http://127.0.0.1:1234/v1",
        models=("local-model",),
    ),
    _provider(
        "openai-codex",
        "OpenAI Codex / ChatGPT subscription",
        auth_methods=("oauth",),
        support_state="unsupported",
        notes=(
            "No documented official OAuth runtime is bundled. Use OpenAI Platform API "
            "or an official coding-agent integration."
        ),
    ),
    _provider(
        "anthropic-claude",
        "Claude subscription",
        auth_methods=("oauth",),
        support_state="unsupported",
        notes=(
            "No documented official subscription OAuth runtime is bundled. Use the Anthropic API."
        ),
    ),
    _provider(
        "google-gemini",
        "Google Gemini",
        auth_methods=("api-key", "cloud-credentials"),
        env_vars=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        support_state="catalogued",
        models=("gemini-1.5-flash",),
        notes="Catalogued; the base Alem gateway does not yet ship a Gemini protocol adapter.",
    ),
)

PROVIDER_INDEX = {provider.id: provider for provider in PROVIDERS}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _state_path(workspace: Workspace, name: str) -> Path:
    return workspace.path(".alem", "state", name)


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelError(f"cannot read model state {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ModelError(f"model state {path.name} must contain a JSON object")
    return value


def _restrict_file(path: Path) -> None:
    """Apply the strongest portable user-only mode available to this process."""

    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    if os.name == "nt":
        username = os.environ.get("USERNAME")
        if username:
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )


def _secure_atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        _restrict_file(temporary)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
        _restrict_file(path)
    finally:
        if temporary.exists():
            temporary.unlink()


class CredentialStore:
    """Workspace-local API-key fallback store with atomic, redacted access."""

    def __init__(self, workspace: Workspace | str | Path):
        self.workspace = (
            workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace).resolve())
        )
        self.path = _state_path(self.workspace, "model-credentials.json")

    def _read(self) -> dict[str, Any]:
        value = _load_json(
            self.path, {"schema_version": MODEL_CREDENTIALS_VERSION, "credentials": {}}
        )
        if value.get("schema_version") != MODEL_CREDENTIALS_VERSION:
            raise ModelError("unsupported model credential store schema")
        credentials = value.get("credentials", {})
        if not isinstance(credentials, dict):
            raise ModelError("model credential store credentials must be an object")
        return value

    def set_api_key(self, provider: str, api_key: str) -> None:
        secret = api_key.strip()
        if not secret:
            raise ModelError("API key input was empty")
        value = self._read()
        credentials = value.setdefault("credentials", {})
        credentials[provider] = {"api_key": secret, "updated_at": _utc_now()}
        value["schema_version"] = MODEL_CREDENTIALS_VERSION
        _secure_atomic_write(self.path, json.dumps(value, indent=2, sort_keys=True) + "\n")

    def delete(self, provider: str) -> bool:
        value = self._read()
        credentials = value.get("credentials", {})
        changed = isinstance(credentials, dict) and provider in credentials
        if changed:
            del credentials[provider]
            _secure_atomic_write(self.path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return changed

    def _stored_api_key(self, provider: str) -> str | None:
        value = self._read()
        record = value.get("credentials", {}).get(provider)
        if isinstance(record, dict) and isinstance(record.get("api_key"), str):
            return record["api_key"]
        return None

    def resolve(self, spec: ProviderSpec) -> tuple[str | None, str]:
        for env_var in spec.env_vars:
            value = os.environ.get(env_var)
            if value:
                return value, f"environment:{env_var}"
        stored = self._stored_api_key(spec.id)
        return (stored, "workspace") if stored else (None, "not-configured")

    def configured(self, spec: ProviderSpec) -> tuple[bool, str]:
        _, source = self.resolve(spec)
        return source != "not-configured", source


class ModelConfigStore:
    """Non-secret model selection and endpoint overrides."""

    def __init__(self, workspace: Workspace | str | Path):
        self.workspace = (
            workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace).resolve())
        )
        self.path = _state_path(self.workspace, "model-config.json")

    def read(self) -> dict[str, Any]:
        value = _load_json(
            self.path,
            {
                "schema_version": MODEL_STATE_VERSION,
                "current": None,
                "defaults": {},
                "fallbacks": {},
                "providers": {},
                "updated_at": None,
            },
        )
        if value.get("schema_version") != MODEL_STATE_VERSION:
            raise ModelError("unsupported model configuration schema")
        return value

    def write(self, value: dict[str, Any]) -> None:
        value["schema_version"] = MODEL_STATE_VERSION
        value["updated_at"] = _utc_now()
        self.workspace.ensure_runtime()
        self.workspace.write_json(".alem/state/model-config.json", value)

    def set_current(self, model: str) -> None:
        value = self.read()
        value["current"] = model
        self.write(value)

    def set_provider(
        self, provider: str, *, base_url: str | None = None, model: str | None = None
    ) -> None:
        value = self.read()
        providers = value.setdefault("providers", {})
        record = providers.setdefault(provider, {})
        if base_url is not None:
            record["base_url"] = validate_base_url(base_url)
        if model:
            models = record.setdefault("models", [])
            if model not in models:
                models.append(model)
        self.write(value)

    def set_fallbacks(self, capability: str, models: Iterable[str]) -> None:
        value = self.read()
        value.setdefault("fallbacks", {})[capability] = list(dict.fromkeys(models))
        self.write(value)


def parse_model_catalog(provider: str, raw: Mapping[str, Any] | list[Any]) -> list[ModelSpec]:
    """Normalize common OpenAI-compatible catalog responses without secrets."""

    values: Any = raw.get("data", []) if isinstance(raw, Mapping) else raw
    if isinstance(raw, Mapping) and not values:
        values = raw.get("models", [])
    if not isinstance(values, list):
        raise ModelError("model catalog must contain a list under `data` or `models`")
    result: list[ModelSpec] = []
    for item in values:
        if isinstance(item, str):
            identifier = item
            metadata: Mapping[str, Any] = {}
        elif isinstance(item, Mapping) and isinstance(item.get("id"), str):
            identifier = item["id"]
            metadata = item
        elif isinstance(item, Mapping) and isinstance(item.get("name"), str):
            identifier = item["name"]
            metadata = item
        else:
            continue
        result.append(
            ModelSpec(
                identifier,
                provider,
                context_window=metadata.get("context_window")
                if isinstance(metadata.get("context_window"), int)
                else None,
                max_output=metadata.get("max_output")
                if isinstance(metadata.get("max_output"), int)
                else None,
                tool_calling=metadata.get("tool_calling")
                if isinstance(metadata.get("tool_calling"), bool)
                else None,
                vision=metadata.get("vision") if isinstance(metadata.get("vision"), bool) else None,
                streaming=metadata.get("streaming")
                if isinstance(metadata.get("streaming"), bool)
                else None,
                source="provider catalog response",
            )
        )
    return result


def get_provider(provider: str) -> ProviderSpec:
    try:
        return PROVIDER_INDEX[provider]
    except KeyError as exc:
        raise ModelError(f"unknown model provider: {provider}") from exc


def _provider_config(workspace: Workspace, provider: str) -> dict[str, Any]:
    value = ModelConfigStore(workspace).read().get("providers", {})
    record = value.get(provider, {}) if isinstance(value, dict) else {}
    return record if isinstance(record, dict) else {}


def provider_base_url(workspace: Workspace, spec: ProviderSpec) -> str | None:
    record = _provider_config(workspace, spec.id)
    value = record.get("base_url")
    return str(value) if value else spec.default_base_url


def provider_models(workspace: Workspace, spec: ProviderSpec) -> list[ModelSpec]:
    result = list(spec.default_models)
    record = _provider_config(workspace, spec.id)
    configured = record.get("models", [])
    if isinstance(configured, list):
        for item in configured:
            if isinstance(item, str) and item and all(model.id != item for model in result):
                result.append(ModelSpec(item, spec.id, source="workspace configuration"))
    return result


def parse_model_ref(value: str) -> tuple[str, str]:
    provider, separator, model = value.partition("/")
    if not separator or not provider or not model:
        raise ModelError("model must use the form PROVIDER/MODEL")
    get_provider(provider)
    return provider, model


def validate_base_url(value: str) -> str:
    """Allow HTTPS by default and HTTP only for loopback/local endpoints."""

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ModelError("base URL must be an HTTPS URL or an HTTP loopback URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ModelError("base URL must not contain credentials, query parameters, or fragments")
    if parsed.scheme == "http" and parsed.hostname.lower() not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ModelError("HTTP is allowed only for loopback hosts: localhost, 127.0.0.1, or ::1")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def redact_url(value: str | None) -> str | None:
    if not value:
        return value
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return "<redacted>"
    return urlunparse((parsed.scheme, parsed.hostname or "", parsed.path, "", "", ""))


def model_status(workspace: Workspace | str | Path) -> dict[str, Any]:
    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace).resolve())
    config = ModelConfigStore(ws).read()
    current = config.get("current") or os.environ.get("ALEM_MODEL")
    values: list[dict[str, Any]] = []
    store = CredentialStore(ws)
    for spec in PROVIDERS:
        configured, source = store.configured(spec)
        base_url = provider_base_url(ws, spec)
        if spec.support_state == "unsupported":
            readiness = "unsupported"
        elif not base_url:
            readiness = "needs-configuration"
        elif spec.api_key_required and not configured:
            readiness = "needs-credentials"
        elif "no-auth" in spec.auth_methods:
            readiness = "local"
        else:
            readiness = "configured"
        values.append(
            {
                "id": spec.id,
                "name": spec.name,
                "support_state": spec.support_state,
                "auth_methods": list(spec.auth_methods),
                "credential_source": source,
                "credentials_configured": configured,
                "base_url": redact_url(base_url),
                "readiness": readiness,
                "models": [model.to_mapping() for model in provider_models(ws, spec)],
                "notes": spec.notes,
                "selected": isinstance(current, str) and current.startswith(f"{spec.id}/"),
            }
        )
    return {"current": current, "providers": values, "schema_version": MODEL_STATE_VERSION}


def list_models(
    workspace: Workspace | str | Path, provider: str | None = None
) -> list[dict[str, Any]]:
    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace).resolve())
    specs = [get_provider(provider)] if provider else list(PROVIDERS)
    statuses = {item["id"]: item for item in model_status(ws)["providers"]}
    result: list[dict[str, Any]] = []
    for spec in specs:
        status = statuses[spec.id]
        for model in provider_models(ws, spec):
            result.append({**model.to_mapping(), "readiness": status["readiness"]})
    return result


class ModelGateway:
    """Common completion gateway for the built-in, tested protocols."""

    def __init__(
        self,
        workspace: Workspace | str | Path,
        *,
        opener: Callable[..., Any] | None = None,
    ):
        self.workspace = (
            workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace).resolve())
        )
        self.credentials = CredentialStore(self.workspace)
        self.opener = opener or urllib.request.urlopen

    def _provider_and_model(self, model: str | None) -> tuple[ProviderSpec, str]:
        selected = model or ModelConfigStore(self.workspace).read().get("current")
        selected = selected or os.environ.get("ALEM_MODEL")
        if not isinstance(selected, str) or not selected:
            raise ModelError("no model selected; run `alem model set PROVIDER/MODEL`")
        provider, model_id = parse_model_ref(selected)
        return get_provider(provider), model_id

    def _credentials(self, spec: ProviderSpec) -> str | None:
        value, _ = self.credentials.resolve(spec)
        return value

    def _base_url(self, spec: ProviderSpec) -> str:
        if spec.support_state != "supported":
            raise ModelError(
                spec.notes or f"provider {spec.id} is not supported by the base gateway"
            )
        base_url = provider_base_url(self.workspace, spec)
        if not base_url:
            raise ModelError(
                f"provider {spec.id} needs a base URL; run `alem model configure {spec.id}`"
            )
        return validate_base_url(base_url)

    def _request(self, request: urllib.request.Request, timeout: float) -> Mapping[str, Any]:
        try:
            response = self.opener(request, timeout=timeout)
            body = response.read()
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            value = json.loads(body)
        except urllib.error.HTTPError as exc:
            if exc.code in {408, 429, 500, 502, 503, 504}:
                raise TransientModelError(f"model provider returned HTTP {exc.code}") from exc
            if exc.code in {401, 403}:
                raise AuthenticationModelError(
                    f"model provider rejected credentials (HTTP {exc.code})"
                ) from exc
            raise ModelError(f"model provider returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ModelError("model provider connection failed") from exc
        except json.JSONDecodeError as exc:
            raise ModelError("model provider returned invalid JSON") from exc
        if not isinstance(value, Mapping):
            raise ModelError("model provider response must be a JSON object")
        return value

    def _headers(self, spec: ProviderSpec, api_key: str | None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Alem-Research/1.0",
        }
        if api_key:
            if spec.protocol == "anthropic-messages":
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def complete(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str | None = None,
        tools: list[Mapping[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        spec, model_id = self._provider_and_model(model)
        base_url = self._base_url(spec)
        api_key = self._credentials(spec)
        if spec.api_key_required and not api_key:
            raise ModelError(
                f"provider {spec.id} needs credentials; set {spec.env_vars[0]} or "
                f"run `alem model login {spec.id}`"
            )
        if spec.protocol == "anthropic-messages":
            payload: dict[str, Any] = {
                "model": model_id,
                "messages": messages,
                "max_tokens": max_tokens or 1024,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            if tools:
                payload["tools"] = tools
            endpoint = f"{base_url}/messages"
        else:
            payload = {"model": model_id, "messages": messages}
            if temperature is not None:
                payload["temperature"] = temperature
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if tools:
                payload["tools"] = tools
            endpoint = f"{base_url}/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(spec, api_key),
            method="POST",
        )
        value = self._request(request, timeout)
        if spec.protocol == "anthropic-messages":
            content = value.get("content", [])
            text = (
                "".join(
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, Mapping) and item.get("type") == "text"
                )
                if isinstance(content, list)
                else ""
            )
            tool_calls = (
                [
                    item
                    for item in content
                    if isinstance(item, Mapping) and item.get("type") == "tool_use"
                ]
                if isinstance(content, list)
                else []
            )
            finish_reason = value.get("stop_reason")
        else:
            choices = value.get("choices", [])
            choice = (
                choices[0]
                if isinstance(choices, list) and choices and isinstance(choices[0], Mapping)
                else {}
            )
            message = choice.get("message", {}) if isinstance(choice, Mapping) else {}
            text = message.get("content", "") if isinstance(message, Mapping) else ""
            tool_calls = message.get("tool_calls", []) if isinstance(message, Mapping) else []
            finish_reason = choice.get("finish_reason") if isinstance(choice, Mapping) else None
        return {
            "content": text if isinstance(text, str) else "",
            "model": str(value.get("model", model_id)),
            "provider": spec.id,
            "finish_reason": finish_reason,
            "tool_calls": tool_calls if isinstance(tool_calls, list) else [],
            "usage": value.get("usage", {}) if isinstance(value.get("usage", {}), Mapping) else {},
        }

    def stream(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str | None = None,
        cancel: threading.Event | None = None,
        timeout: float = 60.0,
    ):
        """Yield text deltas from a provider's SSE response, then a final result."""

        spec, model_id = self._provider_and_model(model)
        base_url = self._base_url(spec)
        api_key = self._credentials(spec)
        if spec.api_key_required and not api_key:
            raise ModelError(f"provider {spec.id} needs credentials")
        payload: dict[str, Any] = {"model": model_id, "messages": messages, "stream": True}
        if spec.protocol == "anthropic-messages":
            payload["max_tokens"] = 1024
            endpoint = f"{base_url}/messages"
        else:
            endpoint = f"{base_url}/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={**self._headers(spec, api_key), "Accept": "text/event-stream"},
            method="POST",
        )
        try:
            response = self.opener(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise AuthenticationModelError(
                    f"model provider rejected credentials (HTTP {exc.code})"
                ) from exc
            raise ModelError(f"model provider returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise ModelError("model provider connection failed") from exc
        parts: list[str] = []
        usage: dict[str, Any] = {}
        try:
            for raw in response:
                if cancel is not None and cancel.is_set():
                    break
                line = (
                    raw.decode("utf-8", errors="replace").strip()
                    if isinstance(raw, bytes)
                    else str(raw).strip()
                )
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "error":
                    raise ModelError("provider stream returned an error")
                if spec.protocol == "anthropic-messages":
                    delta = event.get("delta", {})
                    piece = delta.get("text", "") if isinstance(delta, dict) else ""
                else:
                    choices = event.get("choices", [])
                    first = choices[0] if isinstance(choices, list) and choices else {}
                    delta = first.get("delta", {}) if isinstance(first, dict) else {}
                    piece = delta.get("content", "") if isinstance(delta, dict) else ""
                if isinstance(piece, str) and piece:
                    parts.append(piece)
                    yield {"type": "delta", "text": piece}
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
            yield {
                "type": "complete",
                "content": "".join(parts),
                "provider": spec.id,
                "model": model_id,
                "usage": usage,
                "cancelled": bool(cancel and cancel.is_set()),
            }
        finally:
            response.close()

    def test_connection(self, model: str | None = None, *, timeout: float = 5.0) -> dict[str, Any]:
        spec, _ = self._provider_and_model(model)
        base_url = self._base_url(spec)
        api_key = self._credentials(spec)
        if spec.api_key_required and not api_key:
            raise ModelError(f"provider {spec.id} needs credentials before it can be tested")
        request = urllib.request.Request(
            f"{base_url}/models",
            headers=self._headers(spec, api_key),
            method="GET",
        )
        self._request(request, timeout)
        return {"provider": spec.id, "base_url": redact_url(base_url), "reachable": True}

    def available_models(self, provider: str, *, timeout: float = 3.0) -> list[ModelSpec]:
        """Read the provider's advertised IDs without sending a prompt."""

        spec = get_provider(provider)
        base_url = self._base_url(spec)
        api_key = self._credentials(spec)
        if spec.api_key_required and not api_key:
            raise ModelError(f"provider {spec.id} needs credentials")
        request = urllib.request.Request(
            f"{base_url}/models",
            headers=self._headers(spec, api_key),
            method="GET",
        )
        return parse_model_catalog(spec.id, self._request(request, timeout))

    def invoke(self, payload: Mapping[str, Any], *, operation: str = "invoke") -> ExecutionResponse:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ModelError("model_completion requires a non-empty messages array")
        config = ModelConfigStore(self.workspace).read()
        explicit_model = payload.get("model") if isinstance(payload.get("model"), str) else None
        candidates: list[str] = []
        if explicit_model:
            candidates.append(explicit_model)
        else:
            current = config.get("current") or os.environ.get("ALEM_MODEL")
            if isinstance(current, str) and current:
                candidates.append(current)
            fallbacks = config.get("fallbacks", {}).get(MODEL_CAPABILITY, [])
            if isinstance(fallbacks, list):
                candidates.extend(item for item in fallbacks if isinstance(item, str))
        candidates = list(dict.fromkeys(candidates))
        if not candidates:
            raise ModelError("no model selected; run `alem model set PROVIDER/MODEL`")

        failures: list[dict[str, str]] = []
        for index, candidate in enumerate(candidates):
            try:
                result = self.complete(
                    [item for item in messages if isinstance(item, Mapping)],
                    model=candidate,
                    tools=payload.get("tools") if isinstance(payload.get("tools"), list) else None,
                    temperature=payload.get("temperature")
                    if isinstance(payload.get("temperature"), (int, float))
                    else None,
                    max_tokens=payload.get("max_tokens")
                    if isinstance(payload.get("max_tokens"), int)
                    else None,
                    timeout=float(payload.get("timeout", 60.0)),
                )
            except TransientModelError as exc:
                failures.append(
                    {
                        "model": candidate,
                        "classification": "transient",
                        "error_type": type(exc).__name__,
                    }
                )
                continue
            metadata: dict[str, Any] = {"provider": result["provider"], "operation": operation}
            if index:
                metadata["fallback_used"] = candidate
            if failures:
                metadata["fallback_failures"] = failures
            return ExecutionResponse(result, metadata)
        summary = ", ".join(item["model"] for item in failures)
        raise TransientModelError(f"all configured model fallbacks failed: {summary}")


def model_completion(workspace: Workspace, payload: Mapping[str, Any]) -> ExecutionResponse:
    """Invoke the built-in gateway through Alem's capability contract path."""

    return ModelGateway(workspace).invoke(payload)


def remove_local_credential(workspace: Workspace, provider: str) -> bool:
    get_provider(provider)
    return CredentialStore(workspace).delete(provider)


def save_api_key(workspace: Workspace, provider: str, api_key: str) -> None:
    spec = get_provider(provider)
    if "api-key" not in spec.auth_methods:
        raise UnsupportedAuthError(
            f"{spec.name} does not accept API-key login; supported auth: "
            f"{', '.join(spec.auth_methods)}"
        )
    CredentialStore(workspace).set_api_key(provider, api_key)


def validate_login_method(provider: str, method: str) -> ProviderSpec:
    spec = get_provider(provider)
    if method not in spec.auth_methods:
        if method == "oauth":
            raise UnsupportedAuthError(
                f"OAuth is not supported for {spec.name}. Alem does not use private "
                "subscription token flows; "
                "use a documented API key or an official upstream coding-agent integration."
            )
        raise UnsupportedAuthError(
            f"authentication method {method!r} is not supported for {spec.name}; "
            f"available: {', '.join(spec.auth_methods)}"
        )
    if spec.support_state == "unsupported":
        raise UnsupportedAuthError(spec.notes)
    return spec


def configure_provider(
    workspace: Workspace,
    provider: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
) -> None:
    spec = get_provider(provider)
    if spec.support_state == "unsupported":
        raise ModelError(spec.notes)
    ModelConfigStore(workspace).set_provider(provider, base_url=base_url, model=model)


def set_default_model(workspace: Workspace, model: str) -> None:
    provider, _ = parse_model_ref(model)
    spec = get_provider(provider)
    if spec.support_state == "unsupported":
        raise ModelError(spec.notes)
    ModelConfigStore(workspace).set_current(model)


def set_model_fallbacks(workspace: Workspace, capability: str, models: Iterable[str]) -> None:
    validated: list[str] = []
    for model in models:
        provider, _ = parse_model_ref(model)
        spec = get_provider(provider)
        if spec.support_state == "unsupported":
            raise ModelError(spec.notes)
        validated.append(model)
    ModelConfigStore(workspace).set_fallbacks(capability, validated)


def model_doctor(workspace: Workspace | str | Path) -> dict[str, Any]:
    status = model_status(workspace)
    checks = []
    for item in status["providers"]:
        readiness = item["readiness"]
        checks.append(
            {
                "provider": item["id"],
                "status": "pass" if readiness in {"configured", "local"} else "info",
                "message": {
                    "configured": "API credential is available; connection test is opt-in",
                    "local": (
                        "local endpoint configured; run `alem model test` to check the service"
                    ),
                    "needs-credentials": (
                        "set the documented environment variable or run `alem model login`"
                    ),
                    "needs-configuration": "configure an explicit endpoint before use",
                    "unsupported": item["notes"],
                }.get(readiness, readiness),
            }
        )
    return {"ok": True, "current": status["current"], "checks": checks}
