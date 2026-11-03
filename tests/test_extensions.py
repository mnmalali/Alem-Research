from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from alem.extensions import (
    ApprovalRequired,
    DependencyError,
    ExecutionRequest,
    ExecutionResponse,
    ManifestError,
    PluginCatalogue,
    PluginExecutionError,
    PluginManager,
    PluginNotFoundError,
    RoutingError,
    load_manifest,
    validate_manifest,
)
from alem.extensions.runtime import SubprocessRuntime
from alem.setup_workspace import sync_all_skill_adapters
from alem.workspace import Workspace

REPOSITORY = Path(__file__).resolve().parents[1]
CATALOGUE = REPOSITORY / "catalogue" / "index.toml"
DEMO = REPOSITORY / "examples" / "plugins" / "community-static-search"


class _JsonResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.value).encode()


def _load_provider_module(relative_path: str, module_name: str):
    source = REPOSITORY / relative_path / "plugin.py"
    spec = importlib.util.spec_from_file_location(module_name, source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manager(tmp_path: Path, *, runtime=None) -> PluginManager:
    return PluginManager(tmp_path, catalogue=CATALOGUE, runtime=runtime)


def _write_data_plugin(root: Path, plugin_id: str, dependencies=()) -> Path:
    destination = root / "plugins" / plugin_id
    destination.mkdir(parents=True)
    dependency_text = ",\n  ".join(
        f'{{ id = "{dependency_id}", version = "{version}", '
        f"optional = {str(optional).lower()} }}"
        for dependency_id, version, optional in dependencies
    )
    (destination / "plugin.toml").write_text(
        f"""schema_version = 1
capabilities = []

[plugin]
id = "{plugin_id}"
name = "{plugin_id}"
version = "1.0.0"
api = ">=1.0,<2.0"
description = "Dependency graph test fixture."
author = "Test contributor"
repository = "local://{plugin_id}"
license = "MIT"
types = ["skill"]

[compatibility]
python = ">=3.11,<4.0"
operating_systems = ["windows", "linux", "macos"]
coding_agents = ["codex", "claude-code"]

[dependencies]
plugins = [{dependency_text}]
python = []

[permissions]
network = []
filesystem_read = []
filesystem_write = []
subprocess = false
native_code = false

[credentials]
required = []
optional = []

[documentation]
installation = "Install for dependency tests."
usage = "Data-only fixture."

[assets]
skills = []
agents = []
workflows = []
""",
        encoding="utf-8",
    )
    return destination


def _write_catalogue(root: Path, plugin_ids: list[str]) -> Path:
    catalogue = root / "catalogue"
    catalogue.mkdir()
    entries = []
    for plugin_id in plugin_ids:
        entries.append(
            f"""[[plugins]]
id = "{plugin_id}"
version = "1.0.0"
channel = "community"
verification = "unverified"
source = "../plugins/{plugin_id}"
summary = "Dependency fixture."
author = "Test contributor"
repository = "local://{plugin_id}"
license = "MIT"
extension_types = ["skill"]
capabilities = []
"""
        )
    index = catalogue / "index.toml"
    index.write_text("schema_version = 1\n\n" + "\n".join(entries), encoding="utf-8")
    return index


def test_all_catalogue_manifests_are_strictly_valid() -> None:
    catalogue = PluginCatalogue(CATALOGUE)
    assert [entry.id for entry in catalogue.search("academic_search")] == [
        "org.alem.openalex",
        "org.alem.semantic-scholar",
        "dev.community.static-search",
    ]
    for entry in catalogue.search():
        source = catalogue.resolve_source(entry)
        warnings = validate_manifest(source)
        if entry.id == "community.feynman-bridge":
            assert warnings == [
                "plugin requests subprocess execution",
                "plugin requests unrestricted network access",
            ]
        else:
            assert warnings == []
        manifest = load_manifest(source)
        assert manifest.id == entry.id
        assert manifest.api == ">=1.0,<2.0"


def test_openalex_provider_normalizes_offline_response_and_mailto(monkeypatch) -> None:
    module = _load_provider_module("plugins/official/openalex", "_test_openalex_plugin")
    requests = []
    payload = {
        "meta": {"count": 2},
        "results": [
            {
                "id": "https://openalex.org/W1",
                "display_name": "Verified metadata title",
                "publication_year": 2024,
                "doi": "https://doi.org/10.1000/example",
                "authorships": [
                    {"author": {"display_name": "Ada Researcher"}},
                    {"author": {}},
                ],
                "primary_location": {"landing_page_url": "https://example.org/paper"},
                "abstract_inverted_index": {"Evidence": [0], "first": [1]},
                "cited_by_count": 7,
            },
            {"id": "https://openalex.org/W2", "display_name": "Sparse record"},
        ],
    }

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _JsonResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    response = module.plugin.invoke(
        ExecutionRequest(
            "academic_search",
            input={"query": "evidence synthesis", "limit": 2},
            context={"credentials": {"OPENALEX_MAILTO": "researcher@example.org"}},
        )
    )
    first, sparse = response.output["items"]
    assert first == {
        "title": "Verified metadata title",
        "authors": ["Ada Researcher"],
        "year": 2024,
        "doi": "10.1000/example",
        "url": "https://example.org/paper",
        "external_id": "https://openalex.org/W1",
        "abstract": "Evidence first",
        "citation_count": 7,
        "source": "OpenAlex",
        "verification_status": "retrieved_metadata",
    }
    assert sparse["doi"] is None
    assert sparse["authors"] == []
    assert sparse["year"] is None
    assert sparse["abstract"] is None
    assert sparse["url"] == "https://openalex.org/W2"
    request, timeout = requests[0]
    query = parse_qs(urlparse(request.full_url).query)
    assert query["mailto"] == ["researcher@example.org"]
    assert query["per-page"] == ["2"]
    assert request.get_header("User-agent") == "AlemResearch/1.0"
    assert timeout == 20


def test_semantic_scholar_provider_normalizes_offline_response_and_key(monkeypatch) -> None:
    module = _load_provider_module(
        "plugins/official/semantic-scholar", "_test_semantic_scholar_plugin"
    )
    requests = []
    payload = {
        "total": 2,
        "data": [
            {
                "paperId": "S2-1",
                "title": "Semantic record",
                "authors": [{"name": "Grace Scholar"}, {}],
                "year": 2023,
                "externalIds": {"DOI": "10.2000/semantic"},
                "url": "https://www.semanticscholar.org/paper/S2-1",
                "abstract": "Reported abstract.",
                "citationCount": 4,
            },
            {"paperId": "S2-2", "title": "Sparse semantic record"},
        ],
    }

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _JsonResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    response = module.plugin.invoke(
        ExecutionRequest(
            "academic_search",
            input={"query": "research provenance", "limit": 2},
            context={"credentials": {"SEMANTIC_SCHOLAR_API_KEY": "test-key"}},
        )
    )
    first, sparse = response.output["items"]
    assert first["doi"] == "10.2000/semantic"
    assert first["authors"] == ["Grace Scholar"]
    assert first["external_id"] == "S2-1"
    assert first["verification_status"] == "retrieved_metadata"
    assert sparse["doi"] is None
    assert sparse["authors"] == []
    assert sparse["year"] is None
    assert sparse["abstract"] is None
    request, timeout = requests[0]
    query = parse_qs(urlparse(request.full_url).query)
    assert query["query"] == ["research provenance"]
    assert query["limit"] == ["2"]
    assert request.get_header("X-api-key") == "test-key"
    assert timeout == 20


def test_manifest_rejects_unknown_fields(tmp_path: Path) -> None:
    source = (DEMO / "plugin.toml").read_text(encoding="utf-8")
    plugin = tmp_path / "bad"
    plugin.mkdir()
    (plugin / "plugin.py").write_text("plugin = object()\n", encoding="utf-8")
    (plugin / "plugin.toml").write_text(source + "\nunknown = true\n", encoding="utf-8")
    # The appended key lands in [assets], where strict validation rejects it.
    with pytest.raises(ManifestError, match="unknown keys"):
        load_manifest(plugin)


@pytest.mark.parametrize(
    "requirement",
    ["--target=outside", "https://example.org/package.whl", "../package", "package>=1.0"],
)
def test_manifest_rejects_python_dependency_options_and_non_pins(
    tmp_path: Path, requirement: str
) -> None:
    source = (DEMO / "plugin.toml").read_text(encoding="utf-8")
    plugin = tmp_path / "unsafe-dependency"
    plugin.mkdir()
    (plugin / "plugin.py").write_text("plugin = object()\n", encoding="utf-8")
    source = source.replace("python = []", f'python = ["{requirement}"]', 1)
    (plugin / "plugin.toml").write_text(source, encoding="utf-8")
    with pytest.raises(ManifestError, match="exact index requirements"):
        load_manifest(plugin)


def test_third_party_plugin_complete_local_lifecycle(tmp_path: Path) -> None:
    plugins = manager(tmp_path)
    with pytest.raises(ApprovalRequired, match="installation"):
        plugins.install(DEMO)

    plan = plugins.install(DEMO, approved=True)
    assert [item.id for item in plan.plugins] == ["dev.community.static-search"]
    installed = plugins.list_installed()
    assert len(installed) == 1
    assert installed[0].enabled is False
    assert installed[0].execution_approved is False

    plugins.enable("dev.community.static-search")
    with pytest.raises(RoutingError, match="ApprovalRequired"):
        plugins.invoke("academic_search", {"query": "local-first research"})

    plugins.approve_execution("dev.community.static-search", approved=True)
    response = plugins.invoke("academic_search", {"query": "local-first research"})
    assert response.metadata["provider"] == "dev.community.static-search"
    assert response.output["items"][0]["verification_status"] == "synthetic_example_do_not_cite"

    plugins.disable("dev.community.static-search")
    with pytest.raises(RoutingError, match="no enabled plugin"):
        plugins.invoke("academic_search", {"query": "test"})
    plugins.enable("dev.community.static-search")
    plugins.remove("dev.community.static-search")
    assert plugins.list_installed() == []
    assert not (tmp_path / ".alem" / "plugins" / "dev.community.static-search").exists()


def test_execution_approval_is_invalidated_by_file_change(tmp_path: Path) -> None:
    plugins = manager(tmp_path)
    plugins.install(DEMO, approved=True)
    plugins.enable("dev.community.static-search", approve_execution=True)
    installed_code = tmp_path / ".alem" / "plugins" / "dev.community.static-search" / "plugin.py"
    installed_code.write_text(
        installed_code.read_text(encoding="utf-8") + "\n# modified\n", encoding="utf-8"
    )
    with pytest.raises(RoutingError, match="PluginIntegrityError"):
        plugins.invoke("academic_search", {"query": "test"})


class _FallbackRuntime:
    def __init__(self) -> None:
        self.called: list[str] = []

    def invoke(self, manifest, request, *, dependency_root=None):
        self.called.append(manifest.id)
        if manifest.id == "org.alem.openalex":
            raise PluginExecutionError("simulated provider outage")
        return ExecutionResponse({"items": [], "query": request.input["query"]})


def test_configured_default_and_fallback_provider(tmp_path: Path) -> None:
    runtime = _FallbackRuntime()
    plugins = manager(tmp_path, runtime=runtime)
    plugins.install("org.alem.openalex", approved=True)
    plugins.install("org.alem.semantic-scholar", approved=True)
    plugins.enable("org.alem.openalex", approve_execution=True)
    plugins.enable("org.alem.semantic-scholar", approve_execution=True)

    registry = plugins.registry()
    assert [item.plugin_id for item in registry.providers("academic_search")] == [
        "org.alem.openalex",
        "org.alem.semantic-scholar",
    ]
    plugins.set_route(
        "academic_search",
        default="org.alem.openalex",
        fallbacks=["org.alem.semantic-scholar"],
    )
    response = plugins.invoke("academic_search", {"query": "evidence provenance"})
    assert runtime.called == ["org.alem.openalex", "org.alem.semantic-scholar"]
    assert response.metadata["provider"] == "org.alem.semantic-scholar"
    assert response.metadata["provider_failures"] == [
        {"provider": "org.alem.openalex", "error_type": "PluginExecutionError"}
    ]


def test_routing_never_crosses_capability_contract_versions(tmp_path: Path) -> None:
    version_two = tmp_path / "version-two"
    shutil.copytree(DEMO, version_two)
    manifest_text = (version_two / "plugin.toml").read_text(encoding="utf-8")
    manifest_text = manifest_text.replace(
        'id = "dev.community.static-search"', 'id = "dev.community.static-search-v2"', 1
    )
    manifest_text = manifest_text.replace(
        'name = "academic_search"\nversion = "1.0"',
        'name = "academic_search"\nversion = "2.0"',
        1,
    ).replace("priority = 10", "priority = 1000", 1)
    (version_two / "plugin.toml").write_text(manifest_text, encoding="utf-8")

    plugins = manager(tmp_path / "workspace")
    plugins.install(DEMO, approved=True)
    plugins.install(version_two, approved=True)
    plugins.enable("dev.community.static-search", approve_execution=True)
    plugins.enable("dev.community.static-search-v2", approve_execution=True)
    registry = plugins.registry()

    assert [
        provider.plugin_id
        for provider in registry.resolve("academic_search", capability_version="1.0")
    ] == ["dev.community.static-search"]
    assert [
        provider.plugin_id
        for provider in registry.resolve("academic_search", capability_version="2.0")
    ] == ["dev.community.static-search-v2"]
    with pytest.raises(PluginNotFoundError, match="version '1.0'"):
        registry.resolve(
            "academic_search",
            provider="dev.community.static-search-v2",
            capability_version="1.0",
        )


def test_update_requires_fresh_install_approval_and_clears_execution_approval(
    tmp_path: Path,
) -> None:
    plugins = manager(tmp_path)
    plugins.install("dev.community.static-search", approved=True)
    plugins.enable("dev.community.static-search", approve_execution=True)
    with pytest.raises(ApprovalRequired, match="update installation"):
        plugins.update("dev.community.static-search")
    plugins.update("dev.community.static-search", approved=True)
    record = plugins.list_installed()[0]
    assert record.enabled is False
    assert record.execution_approved is False


def test_data_only_skill_asset_is_installed_and_discovered(tmp_path: Path) -> None:
    source = tmp_path / "source-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("# Community skill\n", encoding="utf-8")
    (source / "plugin.toml").write_text(
        """schema_version = 1
capabilities = []

[plugin]
id = "dev.community.sample-skill"
name = "Sample skill"
version = "0.1.0"
api = ">=1.0,<2.0"
description = "Data-only discovery fixture."
author = "Test contributor"
repository = "local://sample-skill"
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
required = []
optional = []

[documentation]
installation = "Install after review."
usage = "Enable to expose the skill asset."

[assets]
skills = ["SKILL.md"]
agents = []
workflows = []
""",
        encoding="utf-8",
    )
    plugins = manager(tmp_path / "workspace")
    plugins.install(source, approved=True)
    assert plugins.discover_assets("skill") == []
    plugins.enable("dev.community.sample-skill", approve_execution=True)
    assets = plugins.discover_assets("skill")
    assert len(assets) == 1
    assert assets[0].plugin_id == "dev.community.sample-skill"
    assert assets[0].path.read_text(encoding="utf-8") == "# Community skill\n"

    workspace_root = tmp_path / "workspace"
    (workspace_root / "alem.toml").write_text(
        """[alem]
workspace_version = 1
[plugins]
api_version = "1.0"
catalogues = []
""",
        encoding="utf-8",
    )
    core_skill = workspace_root / "skills" / "core-skill" / "SKILL.md"
    core_skill.parent.mkdir(parents=True)
    core_skill.write_text("# Core skill\n", encoding="utf-8")
    workspace = Workspace(workspace_root)
    sync_all_skill_adapters(workspace)
    adapter = (
        workspace_root
        / ".agents"
        / "skills"
        / "plugin--dev-community-sample-skill"
        / "SKILL.md"
    )
    assert adapter.is_file()
    assert ".alem/plugins/dev.community.sample-skill/SKILL.md" in adapter.read_text(
        encoding="utf-8"
    )

    plugins.disable("dev.community.sample-skill")
    sync_all_skill_adapters(workspace)
    assert not adapter.exists()


def test_dependency_tree_tamper_invalidates_execution_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    shutil.copytree(DEMO, source)
    manifest_text = (source / "plugin.toml").read_text(encoding="utf-8")
    (source / "plugin.toml").write_text(
        manifest_text.replace("python = []", 'python = ["fakepkg==1.0"]', 1),
        encoding="utf-8",
    )

    workspace_root = tmp_path / "workspace"

    def fake_pip(command, **kwargs):
        for option in (
            "--isolated",
            "--no-cache-dir",
            "--no-input",
            "--no-deps",
            "--only-binary=:all:",
        ):
            assert option in command
        for key in ("HOME", "TEMP", "PIP_CONFIG_FILE", "PIP_CACHE_DIR"):
            assert (
                Path(kwargs["env"][key])
                .resolve()
                .is_relative_to((workspace_root / ".alem").resolve())
            )
        target = Path(command[command.index("--target") + 1])
        assert target.resolve().is_relative_to((workspace_root / ".alem").resolve())
        (target / "fakepkg.py").write_text("VALUE = 1\n", encoding="utf-8")
        metadata = target / "fakepkg-1.0.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: fakepkg\nVersion: 1.0\n",
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    plugins = manager(workspace_root)
    with monkeypatch.context() as patch:
        patch.setattr("alem.extensions.manager.subprocess.run", fake_pip)
        plugins.install(source, approved=True, install_python_dependencies=True)
    state = json.loads(plugins.state_path.read_text(encoding="utf-8"))
    record = state["plugins"]["dev.community.static-search"]
    assert record["dependency_lock"] == ["fakepkg==1.0"]
    plugins.enable("dev.community.static-search", approve_execution=True)
    dependency_file = (
        tmp_path
        / "workspace"
        / ".alem"
        / "plugin-dependencies"
        / "dev.community.static-search"
        / "fakepkg.py"
    )
    dependency_file.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(RoutingError, match="PluginIntegrityError"):
        plugins.invoke("academic_search", {"query": "tamper proof"})


def test_dependency_cannot_shadow_alem_public_api(tmp_path: Path) -> None:
    dependency_root = tmp_path / "dependencies"
    fake_alem = dependency_root / "alem"
    fake_alem.mkdir(parents=True)
    (fake_alem / "__init__.py").write_text(
        "raise RuntimeError('dependency shadowed trusted core')\n", encoding="utf-8"
    )
    response = SubprocessRuntime().invoke(
        load_manifest(DEMO),
        ExecutionRequest("academic_search", input={"query": "path precedence"}),
        dependency_root=dependency_root,
    )
    assert response.metadata["provider"] == "dev.community.static-search"


def test_dependency_graph_order_and_reverse_dependency_guards(tmp_path: Path) -> None:
    ecosystem = tmp_path / "ecosystem"
    _write_data_plugin(ecosystem, "dev.graph.c")
    _write_data_plugin(ecosystem, "dev.graph.b", [("dev.graph.c", ">=1.0,<2.0", False)])
    _write_data_plugin(ecosystem, "dev.graph.a", [("dev.graph.b", ">=1.0,<2.0", False)])
    index = _write_catalogue(ecosystem, ["dev.graph.a", "dev.graph.b", "dev.graph.c"])
    plugins = PluginManager(tmp_path / "workspace", catalogue=index)
    plan = plugins.install("dev.graph.a", approved=True)
    assert [manifest.id for manifest in plan.plugins] == [
        "dev.graph.c",
        "dev.graph.b",
        "dev.graph.a",
    ]
    with pytest.raises(DependencyError, match="enable required dependencies.*dev.graph.b"):
        plugins.enable("dev.graph.a", approve_execution=True)
    plugins.enable("dev.graph.c", approve_execution=True)
    plugins.enable("dev.graph.b", approve_execution=True)
    plugins.enable("dev.graph.a", approve_execution=True)
    with pytest.raises(DependencyError, match="required by enabled plugins: dev.graph.b"):
        plugins.disable("dev.graph.c")
    with pytest.raises(DependencyError, match="required by enabled plugins: dev.graph.a"):
        plugins.remove("dev.graph.b")
    plugins.disable("dev.graph.a")
    plugins.remove("dev.graph.b")
    plugins.disable("dev.graph.c")


def test_optional_dependency_does_not_block_lifecycle(tmp_path: Path) -> None:
    ecosystem = tmp_path / "ecosystem"
    _write_data_plugin(ecosystem, "dev.optional.helper")
    _write_data_plugin(
        ecosystem,
        "dev.optional.consumer",
        [("dev.optional.helper", ">=1.0,<2.0", True)],
    )
    index = _write_catalogue(ecosystem, ["dev.optional.consumer", "dev.optional.helper"])
    plugins = PluginManager(tmp_path / "workspace", catalogue=index)
    plugins.install("dev.optional.consumer", approved=True)
    plugins.enable("dev.optional.consumer", approve_execution=True)
    plugins.remove("dev.optional.helper")
    assert [item.id for item in plugins.list_installed()] == ["dev.optional.consumer"]


def test_dependency_cycle_is_rejected(tmp_path: Path) -> None:
    ecosystem = tmp_path / "ecosystem"
    _write_data_plugin(ecosystem, "dev.cycle.a", [("dev.cycle.b", ">=1.0,<2.0", False)])
    _write_data_plugin(ecosystem, "dev.cycle.b", [("dev.cycle.a", ">=1.0,<2.0", False)])
    index = _write_catalogue(ecosystem, ["dev.cycle.a", "dev.cycle.b"])
    plugins = PluginManager(tmp_path / "workspace", catalogue=index)
    with pytest.raises(DependencyError, match="dependency cycle"):
        plugins.plan_install("dev.cycle.a")


def test_dependency_version_conflict_is_rejected(tmp_path: Path) -> None:
    ecosystem = tmp_path / "ecosystem"
    _write_data_plugin(ecosystem, "dev.conflict.b")
    _write_data_plugin(ecosystem, "dev.conflict.c", [("dev.conflict.b", ">=2.0,<3.0", False)])
    _write_data_plugin(
        ecosystem,
        "dev.conflict.a",
        [
            ("dev.conflict.b", ">=1.0,<2.0", False),
            ("dev.conflict.c", ">=1.0,<2.0", False),
        ],
    )
    index = _write_catalogue(ecosystem, ["dev.conflict.a", "dev.conflict.b", "dev.conflict.c"])
    plugins = PluginManager(tmp_path / "workspace", catalogue=index)
    with pytest.raises(DependencyError, match="does not satisfy"):
        plugins.plan_install("dev.conflict.a")


def test_failed_dependency_update_rolls_back_existing_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugins = manager(tmp_path / "workspace")
    plugins.install(DEMO, approved=True)
    plugins.enable("dev.community.static-search", approve_execution=True)

    update_source = tmp_path / "update-source"
    shutil.copytree(DEMO, update_source)
    manifest_text = (update_source / "plugin.toml").read_text(encoding="utf-8")
    (update_source / "plugin.toml").write_text(
        manifest_text.replace("python = []", 'python = ["missing-wheel==1.0"]', 1),
        encoding="utf-8",
    )

    def failed_pip(_command, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="no matching wheel")

    with monkeypatch.context() as patch:
        patch.setattr("alem.extensions.manager.subprocess.run", failed_pip)
        with pytest.raises(DependencyError, match="no matching wheel"):
            plugins.update(
                "dev.community.static-search",
                source=update_source,
                approved=True,
                install_python_dependencies=True,
            )

    installed = plugins.list_installed()[0]
    assert installed.enabled is True
    assert installed.execution_approved is True
    response = plugins.invoke("academic_search", {"query": "rollback"})
    assert response.metadata["provider"] == "dev.community.static-search"
