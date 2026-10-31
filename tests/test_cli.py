from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from alem.cli import main

ALEM_TOML = """\
[alem]
workspace_version = 1
name = "CLI workspace"

[plugins]
api_version = "1.0"
catalogues = ["catalogue/index.toml"]
require_install_approval = true
require_execution_approval = true

[capabilities.academic_search]
default = "org.test.primary"
fallbacks = ["org.test.fallback"]
"""


def make_workspace(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "alem.toml").write_text(ALEM_TOML, encoding="utf-8")
    (root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    skill = root / "skills" / "literature-search" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: literature-search\ndescription: Search reproducibly.\n---\n# Search\n",
        encoding="utf-8",
    )
    template = root / "templates" / "project"
    (template / "03_data" / "raw").mkdir(parents=True)
    (template / "PROJECT.md").write_text("# {{project_name}}\nslug: {{project_slug}}\n")
    (template / "public.md").write_text("public\n")
    (template / ".env").write_text("TOKEN=secret\n")
    (template / "03_data" / "raw" / "private.csv").write_text("private\n")
    knowledge = root / "knowledge"
    knowledge.mkdir()
    (knowledge / "concept.md").write_text(
        "---\ntitle: CLI Concept\ntype: concept\nstatus: established\n---\n# CLI Concept\n"
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
"""
    )
    workflows = root / "workflows"
    workflows.mkdir()
    (workflows / "literature-review.md").write_text("# Literature review\n")
    return root.resolve()


def invoke(root: Path, *arguments: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = main(["--workspace", str(root), *arguments])
    return result, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_setup_health_and_config_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_workspace(Path(temporary) / "workspace")

            setup_code, setup_out, setup_err = invoke(root, "setup", "--json")
            health_code, health_out, health_err = invoke(root, "health", "--strict", "--json")
            config_code, config_out, config_err = invoke(root, "config", "validate", "--json")

            self.assertEqual((setup_code, setup_err), (0, ""))
            self.assertEqual((health_code, health_err), (0, ""))
            self.assertEqual((config_code, config_err), (0, ""))
            self.assertEqual(json.loads(setup_out)["workspace_version"], 1)
            self.assertTrue(json.loads(health_out)["ok"])
            config = json.loads(config_out)
            self.assertTrue(config["valid"])
            route = config["capabilities"]["academic_search"]
            self.assertEqual(route["default"], "org.test.primary")

    def test_project_create_list_and_privacy_preserving_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_workspace(Path(temporary) / "workspace")
            invoke(root, "setup")

            create_code, create_out, create_err = invoke(root, "project", "create", "CLI Study")
            list_code, list_out, list_err = invoke(root, "project", "list", "--json")
            export_code, export_out, export_err = invoke(root, "project", "export", "cli-study")

            self.assertEqual((create_code, create_err), (0, ""))
            expected_project = "projects\\cli-study" if "\\" in create_out else "projects/cli-study"
            self.assertIn(expected_project, create_out)
            self.assertEqual((list_code, list_err), (0, ""))
            self.assertEqual(json.loads(list_out)["projects"], ["cli-study"])
            self.assertEqual((export_code, export_err), (0, ""))
            self.assertIn("exports", export_out)
            self.assertEqual(len(list((root / "exports").glob("cli-study-*.zip"))), 1)

    def test_relative_cli_export_output_is_workspace_relative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_workspace(Path(temporary) / "workspace")
            invoke(root, "setup")
            invoke(root, "project", "create", "CLI Study")

            code, output, error = invoke(
                root, "project", "export", "cli-study", "--output", "exports/named.zip"
            )

            self.assertEqual((code, error), (0, ""))
            self.assertIn("exports", output)
            self.assertTrue((root / "exports" / "named.zip").is_file())

    def test_plugin_create_generates_a_valid_escaped_starter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_workspace(Path(temporary) / "workspace")

            create_code, create_out, create_err = invoke(
                root,
                "plugin",
                "create",
                'Quoted " Provider',
                "--id",
                "community.quoted-provider",
            )
            plugin = root / "plugins" / "community" / "quoted-provider"
            validate_code, _, validate_err = invoke(
                root, "plugin", "validate", str(plugin)
            )

            self.assertEqual((create_code, create_err), (0, ""))
            self.assertIn("Created validated plugin starter", create_out)
            self.assertEqual((validate_code, validate_err), (0, ""))
            self.assertIn('name = "Quoted \\" Provider"', (plugin / "plugin.toml").read_text())
            self.assertIn("from alem.extensions.api import", (plugin / "plugin.py").read_text())

    def test_skill_integration_workflow_and_knowledge_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = make_workspace(Path(temporary) / "workspace")

            skill_code, skill_out, _ = invoke(root, "skill", "list", "--json")
            sync_code, sync_out, _ = invoke(root, "skill", "sync", "--json")
            integration_code, integration_out, _ = invoke(
                root, "integration", "list", "--status", "planned", "--json"
            )
            workflow_code, workflow_out, _ = invoke(root, "workflow", "list", "--json")
            knowledge_code, knowledge_out, _ = invoke(root, "knowledge", "index")

            self.assertEqual(skill_code, 0)
            self.assertEqual(json.loads(skill_out)["skills"], ["literature-search"])
            self.assertEqual(sync_code, 0)
            self.assertEqual(json.loads(sync_out)["written"], 2)
            self.assertEqual(integration_code, 0)
            self.assertEqual(
                [item["id"] for item in json.loads(integration_out)["integrations"]], ["crossref"]
            )
            self.assertEqual(workflow_code, 0)
            self.assertEqual(json.loads(workflow_out)["workflows"], ["literature-review"])
            self.assertEqual(knowledge_code, 0)
            self.assertIn("Indexed 1 knowledge pages", knowledge_out)
            self.assertIn("[[concept|CLI Concept]]", (root / "knowledge" / "index.md").read_text())

    def test_invalid_workspace_returns_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            code, output, error = invoke(root, "health")

            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("No alem.toml found", error)


if __name__ == "__main__":
    unittest.main()
