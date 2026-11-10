"""Task-scoped discovery and activation for Alem skills and capabilities."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alem.config import AlemConfig, load_config
from alem.errors import AlemError
from alem.workspace import Workspace

INDEX_SCHEMA_VERSION = 1
PLAN_SCHEMA_VERSION = 1
TOKEN = re.compile(r"[a-z0-9]+")

STAGE_HINTS: dict[str, tuple[str, ...]] = {
    "orient": ("orient", "resume", "project", "status", "workspace"),
    "ideation": ("idea", "ideation", "brainstorm", "topic", "novel"),
    "scoping": ("scope", "question", "eligibility", "boundary", "gap"),
    "literature-search": ("search", "paper", "article", "literature", "scholar", "doi"),
    "evidence-synthesis": ("review", "synthesize", "evidence", "screen", "extract"),
    "research-design": ("method", "protocol", "design", "hypothesis", "power"),
    "dataset-discovery": ("dataset", "data source", "acquire data", "repository"),
    "analysis": ("analyze", "analysis", "statistics", "model", "csv", "experiment"),
    "writing": ("write", "manuscript", "paper", "abstract", "draft"),
    "citation-verification": ("citation", "cite", "reference", "claim", "verify source"),
    "review": ("peer review", "critique", "review manuscript", "reproducibility"),
    "knowledge-update": ("knowledge", "wiki", "obsidian", "promote finding"),
    "integration-development": ("integrate", "plugin", "adapter", "github repo", "tool"),
}

SKILL_STAGES: dict[str, tuple[str, ...]] = {
    "research-ideation": ("ideation",),
    "research-scoping": ("scoping",),
    "literature-search": ("literature-search",),
    "systematic-review": ("scoping", "literature-search", "evidence-synthesis"),
    "literature-review": ("evidence-synthesis",),
    "critical-reading": ("evidence-synthesis", "citation-verification"),
    "research-design": ("research-design",),
    "dataset-discovery": ("dataset-discovery",),
    "experiment-design": ("research-design", "analysis"),
    "data-analysis": ("analysis",),
    "academic-writing": ("writing",),
    "citation-management": ("literature-search", "writing", "citation-verification"),
    "citation-verification": ("citation-verification",),
    "peer-review": ("review",),
    "reproducibility-audit": ("review",),
    "knowledge-management": ("knowledge-update",),
}

CAPABILITY_HINTS: dict[str, tuple[str, ...]] = {
    "academic_search": ("search papers", "find papers", "literature", "scholarly search"),
    "paper_metadata": ("paper metadata", "doi", "bibliographic", "authors"),
    "pdf_extract": ("pdf", "extract text", "document"),
    "citation_verify": ("verify citation", "supports claim", "citation"),
    "reference_management": ("zotero", "bibtex", "references", "library"),
    "dataset_search": ("find dataset", "dataset discovery", "data source"),
    "statistical_analysis": ("statistics", "analyze data", "statistical analysis"),
    "research_agent": ("deep research", "research agent", "feynman"),
    "research_skill_catalog": ("find research skill", "skill catalog"),
    "research_tool_catalog": ("find research tool", "tool catalog"),
}

CAPABILITY_STAGES: dict[str, tuple[str, ...]] = {
    "academic_search": ("literature-search",),
    "paper_metadata": ("literature-search", "citation-verification"),
    "pdf_extract": ("evidence-synthesis", "citation-verification"),
    "citation_verify": ("citation-verification",),
    "reference_management": ("literature-search", "writing", "citation-verification"),
    "dataset_search": ("dataset-discovery",),
    "statistical_analysis": ("analysis",),
    "research_skill_catalog": ("integration-development",),
    "research_tool_catalog": ("integration-development",),
}


@dataclass(frozen=True, slots=True)
class ContextEntry:
    id: str
    kind: str
    description: str
    state: str
    trust: str
    path: str | None = None
    plugin_id: str | None = None
    capability: str | None = None
    capability_version: str | None = None
    providers: tuple[str, ...] = ()
    workflow_stages: tuple[str, ...] = ()
    use_when: tuple[str, ...] = ()
    avoid_when: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    mutation: str = "read-only"
    network: bool = False
    estimated_tokens: int = 0
    acceptance: str | None = None
    authorship: str | None = None


@dataclass(frozen=True, slots=True)
class ContextPlan:
    schema_version: int
    id: str
    created_at: str
    task: str
    stages: tuple[str, ...]
    skills: tuple[ContextEntry, ...]
    capabilities: tuple[ContextEntry, ...]
    suggestions: tuple[ContextEntry, ...]
    excluded: tuple[str, ...]
    estimated_context_tokens: int
    index_digest: str
    rationale: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def _tokens(value: str) -> set[str]:
    return set(TOKEN.findall(value.lower()))


def _metadata_text(value: str, *, limit: int = 500) -> str:
    """Keep untrusted discovery metadata compact and single-purpose."""

    cleaned = " ".join(value.replace("\x00", " ").split())
    return cleaned[:limit]


def _source_digest(workspace: Workspace) -> str:
    """Fingerprint routing sources so stale indexes rebuild automatically."""

    paths = [workspace.path("alem.toml")]
    for relative, patterns in (
        ("skills", ("*/SKILL.md", "*/routing.toml")),
        ("catalogue", ("*.toml",)),
        ("integrations", ("registry.toml",)),
        (".alem/state", ("plugins.json",)),
        (".alem/plugins", ("*/plugin.toml", "*/**/SKILL.md", "*/**/routing.toml")),
    ):
        root = workspace.path(relative)
        if not root.exists():
            continue
        for pattern in patterns:
            paths.extend(sorted(path for path in root.glob(pattern) if path.is_file()))
    hasher = hashlib.sha256()
    for path in sorted(set(paths), key=lambda item: item.as_posix()):
        hasher.update(path.relative_to(workspace.root).as_posix().encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _frontmatter_value(text: str, key: str) -> str | None:
    """Read a scalar or block-scalar value from a skill's YAML frontmatter.

    Skill metadata is intentionally kept dependency-free, but descriptions in
    the Agent Skills format commonly use ``|`` or ``>`` block scalars. Treat
    their indented continuation lines as the value instead of indexing the
    scalar marker itself.
    """

    lines = text[:5000].splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            break
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value in {"|", "|-", "|+", ">", ">-", ">+", ""}:
            continuation: list[str] = []
            for child in lines[index + 1 :]:
                if child.strip() == "---" or (
                    child and not child[0].isspace()
                ):
                    break
                if child.strip():
                    continuation.append(child.strip())
            return " ".join(continuation)
        return value.strip("\"'")
    return None


def _skill_header(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    name = _frontmatter_value(text, "name") or path.parent.name
    description = _metadata_text(
        _frontmatter_value(text, "description")
        or f"Use the {name} research skill."
    )
    return name, description


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _routing_sidecar(path: Path) -> dict[str, Any]:
    candidate = path.parent / "routing.toml"
    if not candidate.is_file():
        return {}
    try:
        with candidate.open("rb") as stream:
            raw = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise AlemError(f"Cannot read routing metadata {candidate}: {exc}") from exc
    if raw.get("schema_version") != 1:
        raise AlemError(f"Unsupported routing metadata schema in {candidate}")
    route = raw.get("routing", {})
    if not isinstance(route, dict):
        raise AlemError(f"[routing] must be a table in {candidate}")
    return route


def _skill_entry(
    workspace: Workspace,
    path: Path,
    *,
    plugin_id: str | None = None,
    state: str = "enabled",
    trust: str = "official",
    acceptance: str | None = None,
    authorship: str | None = None,
) -> ContextEntry:
    name, description = _skill_header(path)
    route = _routing_sidecar(path)
    stages = _strings(route.get("workflow_stages")) or SKILL_STAGES.get(name, ())
    use_when = _strings(route.get("use_when"))
    avoid_when = _strings(route.get("avoid_when"))
    estimated = route.get("estimated_tokens")
    if not isinstance(estimated, int) or estimated < 1:
        estimated = max(64, len(path.read_text(encoding="utf-8")) // 4)
    relative = path.relative_to(workspace.root).as_posix()
    return ContextEntry(
        id=(f"{plugin_id}:{name}" if plugin_id else name),
        kind="skill",
        description=description,
        state=state,
        trust=trust,
        path=relative,
        plugin_id=plugin_id,
        workflow_stages=stages,
        use_when=use_when,
        avoid_when=avoid_when,
        inputs=_strings(route.get("inputs")),
        outputs=_strings(route.get("outputs")),
        domains=_strings(route.get("domains")),
        mutation=str(route.get("mutation", "local-reversible")),
        network=bool(route.get("network", False)),
        estimated_tokens=estimated,
        acceptance=acceptance,
        authorship=authorship,
    )


def _catalogue_path(config: AlemConfig) -> Path | None:
    values = config.raw.get("plugins", {}).get("catalogues", [])
    if isinstance(values, list) and values and isinstance(values[0], str):
        candidate = config.workspace.path(values[0])
        return candidate if candidate.is_file() else None
    return None


def collect_context_entries(workspace: Workspace) -> list[ContextEntry]:
    """Collect compact metadata without importing or executing plugin code."""

    from alem.extensions import PluginCatalogue, PluginManager
    from alem.integrations import load_integrations

    config = load_config(workspace)
    entries: list[ContextEntry] = []
    for skill_file in sorted(workspace.path("skills").glob("*/SKILL.md")):
        if skill_file.parent.name != "alem-router":
            entries.append(_skill_entry(workspace, skill_file))

    catalogue_path = _catalogue_path(config)
    manager = PluginManager(workspace.root, catalogue=catalogue_path)
    installed = {item.id: item for item in manager.list_installed()}
    trust_by_id: dict[str, str] = {}
    registry_path = workspace.path("integrations/registry.toml")
    integrations = load_integrations(workspace) if registry_path.is_file() else []
    releases_by_plugin = {
        item.plugin_id: item for item in integrations if item.plugin_id
    }
    catalogue = PluginCatalogue(catalogue_path) if catalogue_path else None
    if catalogue:
        for item in catalogue.search():
            trust_by_id[item.id] = item.verification
            if item.id not in installed:
                release = releases_by_plugin.get(item.id)
                acceptance = release.acceptance if release else "candidate"
                availability_state = "accepted" if acceptance == "accepted" else "candidate"
                entries.append(
                    ContextEntry(
                        id=item.id,
                        kind="integration",
                        description=_metadata_text(
                            ("Accepted release. " if acceptance == "accepted" else "Candidate. ")
                            + item.summary
                        ),
                        state=availability_state,
                        trust=item.verification,
                        plugin_id=item.id,
                        providers=tuple(item.capabilities),
                        estimated_tokens=max(32, len(item.summary) // 4),
                        acceptance=acceptance,
                        authorship=release.authorship if release else None,
                    )
                )

    for asset in manager.discover_assets("skill", enabled_only=False):
        record = installed.get(asset.plugin_id)
        if record is None:
            continue
        state = "enabled" if record.enabled and record.execution_approved else "installed"
        release = releases_by_plugin.get(asset.plugin_id)
        skill_file = asset.path / "SKILL.md" if asset.path.is_dir() else asset.path
        if skill_file.is_file():
            entries.append(
                _skill_entry(
                    workspace,
                    skill_file,
                    plugin_id=asset.plugin_id,
                    state=state,
                    trust=trust_by_id.get(asset.plugin_id, "unverified"),
                    acceptance=release.acceptance if release else "candidate",
                    authorship=release.authorship if release else "unknown",
                )
            )

    registry = manager.registry(enabled_only=False)
    for capability in registry.capabilities():
        providers = registry.providers(capability)
        enabled_ids = {
            item.plugin_id
            for item in manager.registry(enabled_only=True).providers(capability)
        }
        enabled = [item for item in providers if item.plugin_id in enabled_ids]
        selected = enabled or providers
        descriptions: list[str] = []
        network = False
        for provider in selected:
            manifest = manager._installed_manifest(  # noqa: SLF001 - read-only internal view
                provider.plugin_id,
                manager._load_state()["plugins"][provider.plugin_id],  # noqa: SLF001
            )
            network = network or bool(manifest.permissions.network)
            for declared in manifest.capabilities:
                if declared.name == capability and declared.description:
                    descriptions.append(declared.description)
        description = _metadata_text(
            descriptions[0] if descriptions else f"Invoke {capability}."
        )
        hints = CAPABILITY_HINTS.get(capability, ())
        entries.append(
            ContextEntry(
                id=f"capability:{capability}",
                kind="capability",
                description=description,
                state="enabled" if enabled else "installed",
                trust=(
                    "official"
                    if all(p.plugin_id.startswith("org.alem.") for p in selected)
                    else "mixed"
                ),
                capability=capability,
                capability_version=selected[0].capability_version,
                providers=tuple(item.plugin_id for item in selected),
                workflow_stages=CAPABILITY_STAGES.get(capability, ()),
                use_when=hints,
                network=network,
                estimated_tokens=max(48, (len(description) + len(capability)) // 4),
                acceptance=(
                    "accepted"
                    if selected
                    and all(
                        releases_by_plugin.get(item.plugin_id)
                        and releases_by_plugin[item.plugin_id].acceptance == "accepted"
                        for item in selected
                    )
                    else "candidate"
                ),
                authorship=(
                    next(
                        iter(
                            {
                                releases_by_plugin[item.plugin_id].authorship
                                for item in selected
                                if releases_by_plugin.get(item.plugin_id)
                            }
                        )
                    )
                    if len(
                        {
                            releases_by_plugin[item.plugin_id].authorship
                            for item in selected
                            if releases_by_plugin.get(item.plugin_id)
                        }
                    ) == 1
                    else "mixed"
                ),
            )
        )
    return sorted(entries, key=lambda item: (item.kind, item.id))


def build_context_index(workspace: Workspace) -> dict[str, Any]:
    entries = collect_context_entries(workspace)
    body = [asdict(item) for item in entries]
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    value = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "digest": digest,
        "source_digest": _source_digest(workspace),
        "entries": body,
    }
    workspace.write_json(".alem/cache/context-index.json", value)
    return value


def load_context_index(workspace: Workspace, *, rebuild: bool = False) -> dict[str, Any]:
    value = None if rebuild else workspace.read_json(".alem/cache/context-index.json")
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != INDEX_SCHEMA_VERSION
        or value.get("source_digest") != _source_digest(workspace)
    ):
        return build_context_index(workspace)
    return value


def _entry(value: dict[str, Any]) -> ContextEntry:
    tuple_fields = {
        "providers",
        "workflow_stages",
        "use_when",
        "avoid_when",
        "inputs",
        "outputs",
        "domains",
    }
    converted = dict(value)
    for key in tuple_fields:
        converted[key] = tuple(converted.get(key, ()))
    return ContextEntry(**converted)


def infer_stages(task: str) -> tuple[str, ...]:
    lowered = task.lower()
    scored: list[tuple[int, str]] = []
    for stage, hints in STAGE_HINTS.items():
        score = sum(3 if hint in lowered else len(_tokens(hint) & _tokens(task)) for hint in hints)
        if score:
            scored.append((score, stage))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(stage for _, stage in scored[:3])


def _score(entry: ContextEntry, task: str, stages: tuple[str, ...]) -> int:
    task_tokens = _tokens(task)
    haystack = " ".join(
        (
            entry.id,
            entry.description,
            *entry.use_when,
            *entry.inputs,
            *entry.outputs,
            *entry.domains,
        )
    ).lower()
    score = len(task_tokens & _tokens(haystack)) * 3
    score += len(set(stages) & set(entry.workflow_stages)) * 8
    if entry.kind == "skill" and entry.id in stages:
        score += 12
    score += sum(10 for phrase in entry.use_when if phrase.lower() in task.lower())
    score -= sum(20 for phrase in entry.avoid_when if phrase.lower() in task.lower())
    if entry.capability:
        score += sum(
            8 for hint in CAPABILITY_HINTS.get(entry.capability, ()) if hint in task.lower()
        )
    if entry.id.lower() in task.lower():
        score += 25
    return score


def plan_context(
    workspace: Workspace,
    task: str,
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    rebuild_index: bool = False,
) -> ContextPlan:
    task = task.strip()
    if not task:
        raise AlemError("context task must be non-empty")
    config = load_config(workspace)
    index = load_context_index(workspace, rebuild=rebuild_index)
    entries = [_entry(item) for item in index.get("entries", []) if isinstance(item, dict)]
    stages = infer_stages(task)
    excluded = set(exclude)
    ranked = sorted(
        ((_score(item, task, stages), item) for item in entries if item.id not in excluded),
        key=lambda pair: (-pair[0], pair[1].id),
    )
    include_set = set(include)

    def choose(kind: str, limit: int) -> list[ContextEntry]:
        minimum_score = 7 if kind == "capability" else 1
        available = [
            item
            for score, item in ranked
            if item.kind == kind
            and item.state == "enabled"
            and (
                score >= minimum_score
                or item.id in include_set
                or (item.capability or "") in include_set
            )
        ]
        forced = [
            item
            for item in entries
            if item.kind == kind
            and item.state == "enabled"
            and (item.id in include_set or (item.capability or "") in include_set)
            and item.id not in excluded
        ]
        ordered: list[ContextEntry] = []
        for item in (*forced, *available):
            if item.id not in {value.id for value in ordered}:
                ordered.append(item)
        return ordered[:limit]

    skills = choose("skill", config.context.max_skills)
    capabilities = choose("capability", config.context.max_capabilities)
    suggestions = tuple(
        item
        for score, item in ranked
        if score >= 6 and item.state in {"available", "installed"}
    )[:5]

    estimated = 450 + sum(item.estimated_tokens for item in (*skills, *capabilities))
    while estimated > config.context.max_context_tokens and skills:
        removed = skills.pop()
        estimated -= removed.estimated_tokens
    while estimated > config.context.max_context_tokens and capabilities:
        removed = capabilities.pop()
        estimated -= removed.estimated_tokens

    created_at = datetime.now(UTC).isoformat()
    plan_id = created_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
    plan_id += "-" + hashlib.sha256(
        f"{task}\0{index.get('digest', '')}".encode()
    ).hexdigest()[:10]
    rationale = tuple(
        [f"Detected workflow stages: {', '.join(stages) or 'general'}."]
        + [f"Selected skill {item.id}: {item.description}" for item in skills]
        + [
            f"Selected {item.id} with providers {', '.join(item.providers)}."
            for item in capabilities
        ]
    )
    plan = ContextPlan(
        schema_version=PLAN_SCHEMA_VERSION,
        id=plan_id,
        created_at=created_at,
        task=task,
        stages=stages,
        skills=tuple(skills),
        capabilities=tuple(capabilities),
        suggestions=suggestions,
        excluded=tuple(sorted(excluded)),
        estimated_context_tokens=estimated,
        index_digest=str(index.get("digest", "")),
        rationale=rationale,
    )
    workspace.write_json(f".alem/state/context/plans/{plan.id}.json", plan.to_mapping())
    return plan


def load_plan(workspace: Workspace, plan_id: str | None = None) -> dict[str, Any]:
    if plan_id is None:
        active = workspace.read_json(".alem/state/context/active.json")
        if not isinstance(active, dict) or not isinstance(active.get("plan_id"), str):
            raise AlemError("no active context plan")
        plan_id = active["plan_id"]
    plan = workspace.read_json(f".alem/state/context/plans/{plan_id}.json")
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise AlemError(f"unknown or invalid context plan: {plan_id}")
    return plan


def activate_plan(workspace: Workspace, plan_id: str) -> dict[str, Any]:
    plan = load_plan(workspace, plan_id)
    for skill in plan.get("skills", []):
        path = skill.get("path") if isinstance(skill, dict) else None
        if not isinstance(path, str) or not workspace.path(path).is_file():
            raise AlemError(f"selected skill is unavailable: {path!r}")
    active = {
        "schema_version": 1,
        "plan_id": plan_id,
        "activated_at": datetime.now(UTC).isoformat(),
        "task": plan.get("task"),
        "skills": [item.get("id") for item in plan.get("skills", [])],
        "capabilities": [item.get("capability") for item in plan.get("capabilities", [])],
    }
    workspace.write_json(".alem/state/context/active.json", active)
    return active


def deactivate_context(workspace: Workspace) -> bool:
    target = workspace.path(".alem/state/context/active.json")
    if not target.exists():
        return False
    target.unlink()
    return True


def search_context(
    workspace: Workspace, query: str, *, all_states: bool = False
) -> list[dict[str, Any]]:
    index = load_context_index(workspace)
    terms = _tokens(query)
    values: list[tuple[int, dict[str, Any]]] = []
    for raw in index.get("entries", []):
        if not isinstance(raw, dict) or (not all_states and raw.get("state") != "enabled"):
            continue
        text = json.dumps(raw, sort_keys=True).lower()
        score = len(terms & _tokens(text))
        if not terms or score:
            values.append((score, raw))
    values.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
    return [item for _, item in values]
