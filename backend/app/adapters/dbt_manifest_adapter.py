"""dbt manifest adapter — maps dbt models into Open Steward pipeline jobs.

Reads a dbt ``manifest.json`` artifact (``target/manifest.json`` after a
``dbt compile`` / ``dbt build``) and converts each materialized model into a
:class:`PipelineJob`:

- ``config_key``      → the model name (package-qualified on collision)
- ``pipeline_name``   → the model description's first line, or the name
- ``target_table``    → ``schema.alias`` of the model's relation
- ``source_table``    → the first resolved upstream relation
- ``depends_on``      → all resolved upstream relations (multi-parent lineage)
- ``sql_query``       → compiled SQL when available, raw SQL otherwise
- ``load_type``       → ``table`` → ``full``, ``incremental`` → ``incremental``,
                        ``view`` → ``view``
- ``primary_key``     → derived from the model's dbt ``unique`` test, if any

Ephemeral models are not materialized, so they are not emitted as jobs;
dependencies that point at an ephemeral model are resolved *through* it to its
own parents, preserving lineage. Models with no resolvable upstream (rare —
e.g. pure literal SELECTs) are skipped.

Parsing is tolerant of manifest schema differences across dbt versions
(v10–v12 field names are all handled) and only consumes a small, documented
subset of the artifact. Prefer a *compiled* manifest: raw model SQL still
contains Jinja (``{{ ref(...) }}``), which the SQL analyzer will report as
unparseable.
"""

import json
from pathlib import Path

from app.models.pipeline_job import PipelineJob


class DbtManifestAdapter:
    def __init__(self, manifest_path: str) -> None:
        self._path = Path(manifest_path)

    def load(self) -> list[PipelineJob]:
        if not self._path.exists():
            raise FileNotFoundError(f"Manifest file not found: {self._path}")

        with self._path.open(encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Manifest is not valid JSON: {exc}") from None

        nodes = data.get("nodes")
        if not isinstance(nodes, dict):
            raise ValueError("Not a dbt manifest: missing the 'nodes' mapping.")
        sources = data.get("sources") or {}

        self._nodes = nodes
        self._sources = sources
        pk_by_model = self._primary_keys_from_tests(nodes)

        jobs: list[PipelineJob] = []
        seen_names: dict[str, int] = {}
        for unique_id, node in nodes.items():
            if node.get("resource_type") != "model":
                continue
            if self._materialization(node) == "ephemeral":
                continue  # not materialized; resolved through, not emitted

            parents = self._resolve_parents(unique_id, visited=set())
            if not parents:
                continue  # no resolvable upstream — nothing to reconcile against

            name = node.get("name") or unique_id
            seen_names[name] = seen_names.get(name, 0) + 1
            config_key = (
                f"{node.get('package_name')}.{name}"
                if seen_names[name] > 1 and node.get("package_name")
                else name
            )

            description = (node.get("description") or "").strip()
            jobs.append(PipelineJob(
                config_key=config_key,
                pipeline_name=description.splitlines()[0] if description else name,
                enabled=self._enabled(node),
                source_table=parents[0],
                target_table=self._relation(node),
                sql_query=self._sql(node),
                execution_order=None,  # the graph computes topological order
                primary_key=pk_by_model.get(unique_id),
                load_type=self._load_type(node),
                depends_on=parents,
            ))
        return jobs

    # ── node helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _materialization(node: dict) -> str:
        return ((node.get("config") or {}).get("materialized") or "view").lower()

    @staticmethod
    def _enabled(node: dict) -> bool:
        return (node.get("config") or {}).get("enabled", True) is not False

    @staticmethod
    def _relation(node: dict) -> str:
        """The `schema.table` relation a model or source materializes to."""
        schema = node.get("schema") or ""
        table = node.get("alias") or node.get("identifier") or node.get("name") or ""
        return f"{schema}.{table}" if schema else table

    @staticmethod
    def _sql(node: dict) -> str | None:
        # compiled_code (v6+) / compiled_sql (older); fall back to raw Jinja SQL.
        return (
            node.get("compiled_code")
            or node.get("compiled_sql")
            or node.get("raw_code")
            or node.get("raw_sql")
            or None
        )

    @staticmethod
    def _load_type(node: dict) -> str:
        materialized = DbtManifestAdapter._materialization(node)
        return {"table": "full", "incremental": "incremental"}.get(materialized, materialized)

    def _resolve_parents(self, unique_id: str, visited: set[str]) -> list[str]:
        """Resolve a node's upstream dependencies to relations, looking through
        ephemeral models to their own parents. Order-preserving, de-duplicated."""
        node = self._nodes.get(unique_id)
        if node is None:
            return []
        parents: list[str] = []
        for dep_id in (node.get("depends_on") or {}).get("nodes") or []:
            if dep_id in visited:
                continue  # guard against dependency cycles in the manifest
            visited.add(dep_id)
            resolved = self._resolve_dep(dep_id, visited)
            for relation in resolved:
                if relation and relation not in parents:
                    parents.append(relation)
        return parents

    def _resolve_dep(self, dep_id: str, visited: set[str]) -> list[str]:
        source = self._sources.get(dep_id)
        if source is not None:
            return [self._relation(source)]
        node = self._nodes.get(dep_id)
        if node is None:
            return []
        resource_type = node.get("resource_type")
        if resource_type == "model" and self._materialization(node) == "ephemeral":
            return self._resolve_parents(dep_id, visited)  # look through
        if resource_type in ("model", "seed", "snapshot"):
            return [self._relation(node)]
        return []  # tests, macros, exposures, …

    @staticmethod
    def _primary_keys_from_tests(nodes: dict) -> dict[str, str]:
        """Model unique_id → column covered by a dbt `unique` test. dbt's own
        uniqueness contract is exactly what reconciliation checks as a PK."""
        pks: dict[str, str] = {}
        for node in nodes.values():
            if node.get("resource_type") != "test":
                continue
            if ((node.get("test_metadata") or {}).get("name") or "").lower() != "unique":
                continue
            column = node.get("column_name") or (
                (node.get("test_metadata") or {}).get("kwargs") or {}
            ).get("column_name")
            if not column:
                continue
            for dep_id in (node.get("depends_on") or {}).get("nodes") or []:
                if dep_id.startswith("model.") and dep_id not in pks:
                    pks[dep_id] = column
        return pks
