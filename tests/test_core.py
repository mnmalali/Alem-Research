from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from alem.adapters import (
    GENERATED_MARKER,
    PLUGIN_GENERATED_MARKER,
    sync_skill_adapters,
)
from alem.config import load_config
from alem.errors import AlemError, ConfigurationError, UnsafePathError
from alem.health import run_health_checks
from alem.integrations import load_integrations
from alem.knowledge import END, START, scan_knowledge, update_index
from alem.projects import create_project, export_project, slugify
from alem.setup_workspace import initialize_workspace
from alem.workspace import Workspace

ALEM_TOML = """\
[alem]
workspace_version = 1
name = "Test workspace"

[runtime]
state_directory = ".alem/state"

[plugins]
api_version = "1.0"
catalogues = ["catalogue/index.toml"]
require_install_approval = true
require_execution_approval = true

[capabilities.academic_search]
default = "org.test.primary"
fallbacks = ["org.test.primary", "org.test.fallback"]
"""


def make_workspace(root: Path) -> Workspace:
    root.mkdir(parents=True, exist_ok=True)
    (root / "alem.toml").write_text(ALEM_TOML, encoding="utf-8")
    (root / "AGENTS.md").write_text("# Test agent instructions\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Test Claude instructions\n", encoding="utf-8")
    skill = root / "skills" / "literature-search" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: literature-search\ndescription: Reproducible search.\n---\n# Search\n",
        encoding="utf-8",
    )
    template = root / "templates" / "project"
    (template / "03_data" / "raw").mkdir(parents=True)
    (template / "notes").mkdir(parents=True)
    (template / "PROJECT.md").write_text(
        "# {{project_name}}\nslug: {{project_slug}}\ncreated: {{created_date}}\n",
        encoding="utf-8",
    )
    (template / "notes" / "public.md").write_text("safe\n", encoding="utf-8")
    (template / "03_data" / "raw" / "participants.csv").write_text(
        "private\n", encoding="utf-8"
    )
    (template / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (template / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
    (template / "credentials.json").write_text('{"token":"secret"}\n', encoding="utf-8")
    (template / "secrets.toml").write_text('token = "secret"\n', encoding="utf-8")
    (template / "paper.pdf").write_bytes(b"not a real PDF")
    knowledge = root / "knowledge"
    knowledge.mkdir()
    (knowledge / "paper-one.md").write_text(
        "---\ntitle: Paper One\ntype: paper\nstatus: verified\n---\n# Ignored heading\n",
        encoding="utf-8",
    )
    (knowledge / "concept.md").write_text("# Useful Concept\n", encoding="utf-8")
    (knowledge / "_template.md").write_text("# Template\n", encoding="utf-8")
    (knowledge / "index.md").write_text(
        f"# Curated preface\n\n{START}\nold generated data\n{END}\n\nCurated tail.\n",
        encoding="utf-8",
    )
    integrations = root / "integrations"
    integrations.mkdir()
    (integrations / "registry.toml").write_text(
        """schema_version = 1
[[integrations]]
id = "openalex"
status = "bundled-plugin"
capability = "academic_search"
[[integrations]]
id = "crossref"
status = "planned"
capability = "paper_metadata"
""",
        encoding="utf-8",
    )
    workflows = root / "workflows"
    workflows.mkdir()
    (workflows / "literature-review.md").write_text("# Workflow\n", encoding="utf-8")
    return Workspace(root.resolve())


class WorkspaceAndConfigTests(unittest.TestCase):
    def test_discovers_workspace_from_nested_path_and_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            workspace = make_workspace(root)
            nested = root / "projects" / "nested"
            nested.mkdir(parents=True)

            self.assertEqual(Workspace.discover(nested).root, workspace.root)
            with self.assertRaises(UnsafePathError):
                workspace.path("..", "escaped.txt")
            with self.assertRaises(UnsafePathError):
                workspace.assert_local(root.parent / "outside.txt")

    def test_atomic_json_io_never_leaves_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            target = workspace.write_json(".alem/state/value.json", {"answer": 42})

            self.assertEqual(workspace.read_json(".alem/state/value.json"), {"answer": 42})
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_config_parses_routes_and_removes_default_from_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")

            config = load_config(workspace)

            self.assertEqual(config.workspace_version, 1)
            self.assertEqual(config.plugin_api_version, "1.0")
            route = config.route_for("academic_search")
            self.assertEqual(route.default, "org.test.primary")
            self.assertEqual(route.fallbacks, ("org.test.fallback",))
            self.assertEqual(config.route_for("unknown").providers, ())

    def test_config_rejects_unsupported_workspace_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            config_path = workspace.path("alem.toml")
            invalid = ALEM_TOML.replace("workspace_version = 1", "workspace_version = 9")
            config_path.write_text(invalid, encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                load_config(workspace)


class SetupAdapterAndHealthTests(unittest.TestCase):
    def test_setup_does_not_promote_legacy_or_catalogue_entries_to_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            official = workspace.path("plugins/official/test-official")
            official.mkdir(parents=True)
            (official / "SKILL.md").write_text("# Official skill\n", encoding="utf-8")
            (official / "plugin.toml").write_text(
                """schema_version = 1
capabilities = []

[plugin]
id = "org.test.official"
name = "Test official plugin"
version = "1.0.0"
api = ">=1.0,<2.0"
description = "Test official plugin."
author = "Alem maintainers"
repository = "local://official"
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
installation = "Install automatically during setup."
usage = "Test fixture."

[assets]
skills = ["SKILL.md"]
agents = []
workflows = []
""",
                encoding="utf-8",
            )
            community = workspace.path("plugins/community/test-community")
            community.mkdir(parents=True)
            (community / "SKILL.md").write_text("# Community skill\n", encoding="utf-8")
            (community / "plugin.toml").write_text((official / "plugin.toml").read_text().replace(
                "org.test.official", "dev.test.community"
            ).replace("Test official plugin", "Test community plugin"), encoding="utf-8")
            catalogue = workspace.path("catalogue/index.toml")
            catalogue.parent.mkdir()
            catalogue.write_text(
                """schema_version = 1

[[plugins]]
id = "org.test.official"
version = "1.0.0"
channel = "official"
verification = "official"
source = "../plugins/official/test-official"
summary = "Official fixture."
author = "Alem maintainers"
repository = "local://official"
license = "MIT"
extension_types = ["skill"]
capabilities = []

[[plugins]]
id = "dev.test.community"
version = "1.0.0"
channel = "community"
verification = "unverified"
source = "../plugins/community/test-community"
summary = "Community fixture."
author = "Test contributor"
repository = "local://community"
license = "MIT"
extension_types = ["skill"]
capabilities = []
""",
                encoding="utf-8",
            )

            result = initialize_workspace(workspace)
            self.assertEqual(result["plugins"]["official"]["installed"], [])
            self.assertEqual(
                result["plugins"]["community_available"],
                {"verified": [], "unverified": ["dev.test.community"]},
            )
            state = workspace.read_json(".alem/state/plugins.json", default={})
            self.assertEqual(state.get("plugins", {}), {})
            self.assertEqual(
                result["plugins"]["reconciliation"]["candidates_untouched"], 2
            )
            self.assertEqual(
                [item.acceptance for item in load_integrations(workspace)],
                ["candidate", "candidate"],
            )
            self.assertNotIn("dev.test.community", state.get("plugins", {}))

    def test_setup_records_only_workspace_local_paths_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")

            first = initialize_workspace(workspace)
            second = initialize_workspace(workspace)

            self.assertTrue(workspace.path(".alem/state/workspace.json").is_file())
            self.assertEqual(first["root"], str(workspace.root))
            self.assertTrue(first["created_paths"])
            self.assertEqual(second["created_paths"], [])
            for relative in first["created_paths"]:
                created = (workspace.root / relative).resolve()
                self.assertTrue(created.is_relative_to(workspace.root.resolve()))
            for agent_root in (".agents/skills", ".claude/skills"):
                adapter = workspace.path(agent_root, "literature-search", "SKILL.md")
                self.assertIn(GENERATED_MARKER, adapter.read_text(encoding="utf-8"))
                self.assertIn("../../../skills/literature-search/SKILL.md", adapter.read_text())

    def test_adapter_sync_preserves_custom_files_and_refreshes_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            first = sync_skill_adapters(workspace)
            custom = workspace.path(".agents/skills/literature-search/SKILL.md")
            generated = workspace.path(".claude/skills/literature-search/SKILL.md")
            custom.write_text("# Maintainer-owned adapter\n", encoding="utf-8")
            canonical = workspace.path("skills/literature-search/SKILL.md")
            canonical.write_text(canonical.read_text().replace("Reproducible", "Auditable"))

            second = sync_skill_adapters(workspace)

            self.assertEqual(
                first,
                {
                    "skills": 1,
                    "plugin_skills": 0,
                    "written": 2,
                    "preserved": 0,
                    "removed": 0,
                },
            )
            self.assertEqual(second["preserved"], 1)
            self.assertEqual(custom.read_text(), "# Maintainer-owned adapter\n")
            self.assertIn("Auditable search", generated.read_text())

    def test_enabled_plugin_skill_adapter_is_namespaced_and_removable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            plugin_skill = workspace.path(
                ".alem/plugins/dev.community.sample-skill/SKILL.md"
            )
            plugin_skill.parent.mkdir(parents=True)
            plugin_skill.write_text(
                "---\nname: sample-skill\ndescription: Approved plugin skill.\n---\n# Skill\n",
                encoding="utf-8",
            )

            counts = sync_skill_adapters(
                workspace,
                plugin_skills=[("dev.community.sample-skill", plugin_skill)],
            )
            adapter = workspace.path(
                ".agents/skills/plugin--dev-community-sample-skill/SKILL.md"
            )
            self.assertEqual(counts["plugin_skills"], 1)
            text = adapter.read_text(encoding="utf-8")
            self.assertIn(PLUGIN_GENERATED_MARKER, text)
            self.assertIn(".alem/plugins/dev.community.sample-skill/SKILL.md", text)

            removed = sync_skill_adapters(workspace)
            self.assertFalse(adapter.exists())
            self.assertEqual(removed["removed"], 2)

    def test_health_reports_warning_before_setup_and_passes_after_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")

            before = run_health_checks(workspace)
            initialize_workspace(workspace)
            after = run_health_checks(workspace)

            before_status = {check.name: check.status for check in before.checks}
            after_status = {check.name: check.status for check in after.checks}
            self.assertEqual(before_status["runtime"], "warn")
            self.assertEqual(before_status["Codex adapters"], "warn")
            self.assertTrue(after.ok)
            self.assertEqual(after_status["runtime"], "pass")
            self.assertEqual(after_status["Codex adapters"], "pass")
            self.assertEqual(after_status["Claude Code adapters"], "pass")


class ProjectTests(unittest.TestCase):
    def test_slugify_and_project_creation_replace_template_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")

            project = create_project(workspace, "Causal AI: A Replication")

            self.assertEqual(slugify("Causal AI: A Replication"), "causal-ai-a-replication")
            self.assertEqual(project.name, "causal-ai-a-replication")
            project_file = (project / "PROJECT.md").read_text(encoding="utf-8")
            self.assertIn("# Causal AI: A Replication", project_file)
            self.assertIn("slug: causal-ai-a-replication", project_file)
            self.assertNotIn("{{", project_file)
            with self.assertRaises(AlemError):
                create_project(workspace, "Causal AI: A Replication")

    def test_default_export_excludes_secrets_raw_data_and_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            create_project(workspace, "Private Study")

            archive = export_project(workspace, "private-study")

            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
            self.assertIn("private-study/PROJECT.md", names)
            self.assertIn("private-study/notes/public.md", names)
            self.assertNotIn("private-study/.env", names)
            self.assertNotIn("private-study/.env.local", names)
            self.assertNotIn("private-study/credentials.json", names)
            self.assertNotIn("private-study/secrets.toml", names)
            self.assertNotIn("private-study/paper.pdf", names)
            self.assertNotIn("private-study/03_data/raw/participants.csv", names)

    def test_explicit_sensitive_export_includes_excluded_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            create_project(workspace, "Private Study")

            archive = export_project(workspace, "private-study", include_sensitive=True)

            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
            self.assertIn("private-study/.env", names)
            self.assertIn("private-study/.env.local", names)
            self.assertIn("private-study/credentials.json", names)
            self.assertIn("private-study/secrets.toml", names)
            self.assertIn("private-study/paper.pdf", names)
            self.assertIn("private-study/03_data/raw/participants.csv", names)

    def test_export_output_must_remain_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            workspace = make_workspace(root)
            create_project(workspace, "Private Study")

            with self.assertRaises(UnsafePathError):
                export_project(workspace, "private-study", root.parent / "leak.zip")

    def test_relative_export_output_is_resolved_from_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            create_project(workspace, "Portable Study")

            archive = export_project(workspace, "portable-study", Path("exports/custom.zip"))

            self.assertEqual(archive, workspace.path("exports/custom.zip"))
            self.assertTrue(archive.is_file())

    def test_export_rejects_symbolic_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")
            project = create_project(workspace, "Linked Study")
            external = Path(temporary) / "outside.txt"
            external.write_text("must not be exported\n", encoding="utf-8")
            try:
                (project / "outside-link.txt").symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable on this host: {exc}")

            with self.assertRaisesRegex(AlemError, "linked path"):
                export_project(workspace, "linked-study", include_sensitive=True)


class KnowledgeTests(unittest.TestCase):
    def test_scan_and_controlled_index_preserve_curated_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = make_workspace(Path(temporary) / "workspace")

            pages = scan_knowledge(workspace)
            index, count = update_index(workspace)
            first = index.read_text(encoding="utf-8")
            update_index(workspace)
            second = index.read_text(encoding="utf-8")

            self.assertEqual(count, 2)
            self.assertEqual([page.title for page in pages], ["Useful Concept", "Paper One"])
            self.assertEqual(first, second)
            self.assertIn("# Curated preface", first)
            self.assertIn("Curated tail.", first)
            self.assertNotIn("old generated data", first)
            self.assertIn("[[paper-one|Paper One]] — `verified`", first)
            self.assertIn("[[concept|Useful Concept]] — `unknown`", first)
            self.assertNotIn("Template", first)
            self.assertEqual(first.count(START), 1)
            self.assertEqual(first.count(END), 1)


if __name__ == "__main__":
    unittest.main()
