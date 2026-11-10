from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from alem.cli import main
from alem.errors import AlemError
from alem.extensions import PluginManager
from alem.extensions.manager import plugin_tree_digest
from alem.integrations import load_integrations
from alem.reconciliation import reconcile_accepted_integrations
from alem.setup_workspace import initialize_workspace
from alem.tool_status import list_tool_statuses
from alem.workspace import Workspace
from scripts import bootstrap_runtime

CONFIG = """\
[alem]
workspace_version = 1
name = "Accepted integration tests"

[runtime]
state_directory = ".alem/state"

[plugins]
api_version = "1.0"
catalogues = ["catalogue/index.toml"]
require_install_approval = true
require_execution_approval = true

[context]
mode = "lazy"
"""


def _toml_list(items: list[str]) -> str:
    return json.dumps(items)


def _write_plugin(workspace: Workspace, spec: dict[str, object]) -> Path:
    plugin_id = str(spec["plugin_id"])
    folder = str(spec["folder"])
    path = workspace.path("plugins", folder)
    path.mkdir(parents=True, exist_ok=True)
    version = str(spec.get("version", "1.0.0"))
    required = list(spec.get("required_credentials", []))
    (path / "SKILL.md").write_text(
        "---\nname: readiness-fixture\ndescription: Test accepted tool status.\n---\n"
        f"# {plugin_id} {version}\n",
        encoding="utf-8",
    )
    (path / "plugin.toml").write_text(
        f'''schema_version = 1
capabilities = []

[plugin]
id = {json.dumps(plugin_id)}
name = {json.dumps(plugin_id)}
version = {json.dumps(version)}
api = ">=1.0,<2.0"
description = "Accepted fixture for provisioning and readiness tests."
author = "Alem test fixture"
repository = "local://{plugin_id}"
license = "MIT"
types = ["skill"]

[compatibility]
python = ">=3.11,<4.0"
operating_systems = ["windows", "linux", "macos"]
coding_agents = ["codex", "claude-code"]

[dependencies]
plugins = []
python = []

[permissions]
network = []
filesystem_read = []
filesystem_write = []
subprocess = false
native_code = false

[credentials]
required = {_toml_list([str(item) for item in required])}
optional = []

[documentation]
installation = "Managed by Alem after maintainer acceptance."
usage = "Readiness fixture."

[assets]
skills = ["SKILL.md"]
agents = []
workflows = []
''',
        encoding="utf-8",
    )
    return path


def _spec(
    integration_id: str,
    plugin_id: str,
    folder: str,
    *,
    acceptance: str = "accepted",
    authorship: str = "alem-official",
    contributor: str | None = None,
    required_credentials: list[str] | None = None,
    required_hardware: list[str] | None = None,
    required_runtimes: list[str] | None = None,
    service_checks: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": integration_id,
        "plugin_id": plugin_id,
        "folder": folder,
        "version": "1.0.0",
        "acceptance": acceptance,
        "authorship": authorship,
        "contributor": contributor,
        "required_credentials": required_credentials or [],
        "required_hardware": required_hardware or [],
        "required_runtimes": required_runtimes or [],
        "service_checks": service_checks or [],
    }


def _write_release_indexes(workspace: Workspace, specs: list[dict[str, object]]) -> None:
    catalogue = ["schema_version = 1", ""]
    registry = ["schema_version = 3", ""]
    for spec in specs:
        source = workspace.path("plugins", str(spec["folder"]))
        digest = plugin_tree_digest(source)
        community = str(spec["plugin_id"]).startswith("community.")
        channel = "community" if community else "official"
        verification = "verified" if community else "official"
        required_hardware = [str(item) for item in spec["required_hardware"]]
        required_runtimes = [str(item) for item in spec.get("required_runtimes", [])]
        service_checks = [str(item) for item in spec["service_checks"]]
        catalogue.extend(
            [
                "[[plugins]]",
                f'id = {json.dumps(str(spec["plugin_id"]))}',
                f'version = {json.dumps(str(spec["version"]))}',
                f'channel = "{channel}"',
                f'verification = "{verification}"',
                f'source = "../plugins/{spec["folder"]}"',
                f'summary = "Fixture for {spec["id"]}."',
                'author = "Alem test fixture"',
                f'repository = "local://{spec["plugin_id"]}"',
                'license = "MIT"',
                'extension_types = ["skill"]',
                "capabilities = []",
                "",
            ]
        )
        integration = [
                "[[integrations]]",
                f'id = {json.dumps(str(spec["id"]))}',
                f'name = {json.dumps(str(spec["id"]).replace("-", " ").title())}',
                'kind = "provider"',
                'status = "contract-tested"',
                'trust = "verified"',
                'capabilities = []',
                'cost = "local-test"',
                'authentication = "none"',
                'privacy = "local fixture"',
                'notes = "Accepted integration test fixture."',
                f'plugin_id = {json.dumps(str(spec["plugin_id"]))}',
                f'acceptance = {json.dumps(str(spec["acceptance"]))}',
                f'authorship = {json.dumps(str(spec["authorship"]))}',
                f"required_hardware = {_toml_list(required_hardware)}",
                f"required_runtimes = {_toml_list(required_runtimes)}",
                f"service_checks = {_toml_list(service_checks)}",
                "configuration_instructions = "
                + json.dumps("Set required variables through a secure environment."),
                "",
            ]
        if spec["acceptance"] == "accepted":
            integration.extend(
                [
                    f'release_version = {json.dumps(str(spec["version"]))}',
                    f'release_digest = "{digest}"',
                ]
            )
        if spec.get("contributor"):
            integration.append(f'contributor = {json.dumps(str(spec["contributor"]))}')
        registry.extend(integration)
    workspace.path("catalogue/index.toml").parent.mkdir(parents=True, exist_ok=True)
    workspace.path("catalogue/index.toml").write_text("\n".join(catalogue), encoding="utf-8")
    workspace.path("integrations/registry.toml").write_text("\n".join(registry), encoding="utf-8")


def _workspace(root: Path, specs: list[dict[str, object]]) -> Workspace:
    root.mkdir(parents=True, exist_ok=True)
    (root / "alem.toml").write_text(CONFIG, encoding="utf-8")
    (root / "skills" / "router").mkdir(parents=True)
    (root / "skills" / "router" / "SKILL.md").write_text(
        "---\nname: router\ndescription: Test router.\n---\n# Router\n", encoding="utf-8"
    )
    (root / "integrations").mkdir()
    for spec in specs:
        _write_plugin(Workspace(root.resolve()), spec)
    workspace = Workspace(root.resolve())
    _write_release_indexes(workspace, specs)
    return workspace


def _accepted_fixture() -> list[dict[str, object]]:
    return [
        _spec("official", "org.test.official", "official/test", authorship="alem-official"),
        _spec(
            "community",
            "community.test.community",
            "community/test",
            authorship="community-contributor",
            contributor="Alem Community Contributor",
        ),
        _spec(
            "candidate",
            "community.test.candidate",
            "community/candidate",
            acceptance="candidate",
            authorship="community-contributor",
            contributor="Candidate Author",
        ),
    ]


def test_setup_provisions_accepted_authorships_but_not_candidate_and_is_idempotent(
    tmp_path: Path,
) -> None:
    specs = _accepted_fixture()
    workspace = _workspace(tmp_path / "workspace", specs)

    first = initialize_workspace(workspace)
    second = initialize_workspace(workspace)

    state = workspace.read_json(".alem/state/plugins.json")["plugins"]
    assert set(state) == {"org.test.official", "community.test.community"}
    assert state["org.test.official"]["authorship"] == "alem-official"
    assert state["org.test.official"]["release_version"] == "1.0.0"
    assert state["org.test.official"]["release_digest"] == plugin_tree_digest(
        workspace.path("plugins/official/test")
    )
    assert state["community.test.community"]["authorship"] == "community-contributor"
    assert state["community.test.community"]["contributor"] == "Alem Community Contributor"
    assert first["plugins"]["reconciliation"]["installed"] == [
        "org.test.official",
        "community.test.community",
    ]
    assert second["plugins"]["reconciliation"]["already_current"] == [
        "org.test.official",
        "community.test.community",
    ]
    assert second["plugins"]["reconciliation"]["candidates_untouched"] == 1
    context_entries = workspace.read_json(".alem/cache/context-index.json")["entries"]
    context_by_id = {item["id"]: item for item in context_entries}
    assert context_by_id["community.test.community:readiness-fixture"]["acceptance"] == "accepted"
    assert (
        context_by_id["community.test.community:readiness-fixture"]["authorship"]
        == "community-contributor"
    )
    assert context_by_id["community.test.candidate"]["acceptance"] == "candidate"


def test_failed_accepted_update_is_reported_without_replacing_working_release(
    tmp_path: Path,
) -> None:
    specs = _accepted_fixture()[:2]
    workspace = _workspace(tmp_path / "workspace", specs)
    initialize_workspace(workspace)
    state_before = workspace.read_json(".alem/state/plugins.json")["plugins"]
    working_path = state_before["org.test.official"]["path"]

    source_skill = workspace.path("plugins/official/test/SKILL.md")
    source_skill.write_text("# Tampered without maintainer registry change\n", encoding="utf-8")
    result = reconcile_accepted_integrations(workspace)

    state_after = workspace.read_json(".alem/state/plugins.json")["plugins"]
    assert any(item["id"] == "official" for item in result["failed"])
    assert state_after["org.test.official"]["path"] == working_path
    assert state_after["org.test.official"]["digest"] == state_before["org.test.official"]["digest"]
    assert "community.test.community" in result["already_current"]


def test_update_reconciles_new_and_changed_accepted_release_and_supports_rollback(
    tmp_path: Path,
) -> None:
    specs = _accepted_fixture()[:2]
    workspace = _workspace(tmp_path / "workspace", specs)
    initialize_workspace(workspace)

    added = _spec(
        "new-community",
        "community.test.new-tool",
        "community/new-tool",
        authorship="community-contributor",
        contributor="New Contributor",
    )
    specs.append(added)
    _write_plugin(workspace, added)
    _write_release_indexes(workspace, specs)
    first_update = reconcile_accepted_integrations(workspace)
    repeat_update = reconcile_accepted_integrations(workspace)
    assert first_update["installed"] == ["community.test.new-tool"]
    assert "community.test.new-tool" in repeat_update["already_current"]

    new_tool = workspace.path("plugins/community/new-tool")
    manifest_path = new_tool / "plugin.toml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace('version = "1.0.0"', 'version = "1.1.0"'),
        encoding="utf-8",
    )
    (new_tool / "SKILL.md").write_text("# Updated release\n", encoding="utf-8")
    added["version"] = "1.1.0"
    _write_release_indexes(workspace, specs)
    updated = reconcile_accepted_integrations(workspace)
    assert updated["updated"] == ["community.test.new-tool"]

    manager = PluginManager(workspace.root, catalogue=workspace.path("catalogue/index.toml"))
    rollback = manager.rollback("community.test.new-tool")
    assert rollback["version"] == "1.0.0"
    pinned = reconcile_accepted_integrations(workspace)
    assert pinned["pinned"] == ["community.test.new-tool"]
    manager.unpin("community.test.new-tool")
    after_unpin = reconcile_accepted_integrations(workspace)
    assert after_unpin["updated"] == ["community.test.new-tool"]


def test_readiness_keeps_blocked_tools_available_without_disclosing_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    specs = [
        _spec(
            "api",
            "community.test.api",
            "community/api",
            authorship="community-contributor",
            contributor="API Adapter Author",
            required_credentials=["ALEM_TEST_SECRET"],
            service_checks=["https://api.example.test/health"],
        ),
        _spec(
            "gpu",
            "community.test.gpu",
            "community/gpu",
            authorship="community-contributor",
            contributor="GPU Adapter Author",
            required_hardware=["gpu"],
        ),
        _spec(
            "offline",
            "community.test.offline",
            "community/offline",
            authorship="community-contributor",
            contributor="Service Adapter Author",
            service_checks=["https://service.example.test/health"],
        ),
        _spec(
            "runtime",
            "community.test.runtime",
            "community/runtime",
            authorship="community-contributor",
            contributor="Runtime Adapter Author",
            required_runtimes=[".alem/tools/test-runtime"],
        ),
        _spec("ready", "org.test.ready", "official/ready"),
    ]
    workspace = _workspace(tmp_path / "workspace", specs)
    initialize_workspace(workspace)
    monkeypatch.delenv("ALEM_TEST_SECRET", raising=False)

    with (
        patch("alem.tool_status._hardware_check", return_value=(False, "GPU not found")),
        patch("alem.tool_status._service_check", return_value=(False, "service unavailable")),
    ):
        statuses = {item["id"]: item for item in list_tool_statuses(workspace)}

    assert statuses["api"]["available"] is True
    assert statuses["api"]["readiness"] == "needs-configuration"
    assert "ALEM_TEST_SECRET" in " ".join(statuses["api"]["blockers"])
    assert statuses["gpu"]["available"] is True
    assert statuses["gpu"]["readiness"] == "missing-hardware"
    assert statuses["offline"]["available"] is True
    assert statuses["offline"]["readiness"] == "service-unavailable"
    assert statuses["runtime"]["available"] is True
    assert statuses["runtime"]["readiness"] == "missing-runtime"
    assert statuses["ready"]["readiness"] == "ready"

    secret = "SENSITIVE_SENTINEL_924817"
    monkeypatch.setenv("ALEM_TEST_SECRET", secret)
    with patch("alem.tool_status._hardware_check", return_value=(True, "GPU present")), patch(
        "alem.tool_status._service_check", return_value=(True, "service reachable")
    ):
        readiness = {item["id"]: item for item in list_tool_statuses(workspace)}
        assert readiness["api"]["readiness"] == "ready"
    result = main(["--workspace", str(workspace.root), "tools", "configure", "api"])
    output = capsys.readouterr().out
    assert result == 0
    assert "ALEM_TEST_SECRET" not in output  # key is configured, so no prompt is required
    assert secret not in output

    monkeypatch.delenv("ALEM_TEST_SECRET")
    main(["--workspace", str(workspace.root), "tools", "configure", "api"])
    output = capsys.readouterr().out
    assert "ALEM_TEST_SECRET" in output
    assert secret not in output

    plugin_state = workspace.read_json(".alem/state/plugins.json")
    plugin_state["plugins"]["org.test.ready"]["path"] = "../escaped-plugin"
    workspace.write_json(".alem/state/plugins.json", plugin_state)
    broken = list_tool_statuses(workspace, identifier="ready", check_services=False)[0]
    assert broken["readiness"] == "error"
    assert broken["available"] is False


def test_legacy_registry_migrates_as_candidates(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "alem.toml").write_text(CONFIG, encoding="utf-8")
    (root / "integrations").mkdir()
    (root / "integrations" / "registry.toml").write_text(
        'schema_version = 1\n[[integrations]]\nid = "openalex"\n'
        'status = "bundled-plugin"\ncapability = "academic_search"\n',
        encoding="utf-8",
    )

    records = load_integrations(Workspace(root.resolve()))
    assert records[0].acceptance == "candidate"
    assert records[0].authorship == "unknown"


def test_registry_rejects_unknown_fields_and_secret_bearing_readiness_urls(
    tmp_path: Path,
) -> None:
    specs = [
        _spec(
            "api",
            "community.test.api",
            "community/api",
            authorship="community-contributor",
            contributor="API Adapter Author",
            service_checks=["https://api.example.test/health"],
        )
    ]
    workspace = _workspace(tmp_path / "workspace", specs)
    registry = workspace.path("integrations/registry.toml")
    original = registry.read_text(encoding="utf-8")
    registry.write_text(
        original.replace(
            'notes = "Accepted integration test fixture."',
            'notes = "Accepted integration test fixture."\nunknown = true',
        ),
        encoding="utf-8",
    )
    with pytest.raises(AlemError, match="unknown fields"):
        load_integrations(workspace)

    registry.write_text(
        original.replace(
            'service_checks = ["https://api.example.test/health"]',
            'service_checks = ["https://api.example.test/health?api_key=not-a-secret"]',
        ),
        encoding="utf-8",
    )
    with pytest.raises(AlemError, match="credential-free HTTP URLs"):
        load_integrations(workspace)


def test_bootstrap_installs_dependencies_into_the_actual_workspace_interpreter(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\ndependencies = ["jsonschema>=4.23,<5", "PyYAML>=6.0.2,<7"]\n',
        encoding="utf-8",
    )
    expected_python = root / ".alem" / "venv" / "Scripts" / "python.exe"
    calls: list[list[str]] = []

    class Builder:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def create(self, target: Path) -> None:
            interpreter = target / "Scripts" / "python.exe"
            interpreter.parent.mkdir(parents=True)
            interpreter.write_bytes(b"test interpreter")

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(bootstrap_runtime.sys, "platform", "win32"), patch.object(
        bootstrap_runtime.venv, "EnvBuilder", Builder
    ), patch.object(bootstrap_runtime.subprocess, "run", side_effect=run):
        assert bootstrap_runtime.bootstrap(root) == 0

    pip_call = next(command for command in calls if command[1:3] == ["-m", "pip"])
    assert Path(pip_call[0]) == expected_python
    assert "PyYAML>=6.0.2,<7" in pip_call
    assert "jsonschema>=4.23,<5" in pip_call
    assert json.loads((root / ".alem/state/runtime-dependencies.json").read_text())[
        "python"
    ] == str(expected_python.resolve())

    calls.clear()
    with patch.object(bootstrap_runtime.subprocess, "run", side_effect=run):
        assert bootstrap_runtime.bootstrap(root) == 0
    assert len(calls) == 1
    assert calls[0] == [str(expected_python), "-c", bootstrap_runtime.IMPORT_CHECK]
