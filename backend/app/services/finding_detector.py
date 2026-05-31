from collections import defaultdict

import networkx as nx

from app.models.finding import ValidationFinding
from app.models.pipeline_job import PipelineJob
from app.services.graph_builder import detect_cycles

_EXTERNAL_PREFIXES = ("raw.", "source.", "landing.", "external.")


def detect_findings(jobs: list[PipelineJob], graph: nx.DiGraph) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    findings.extend(_circular_dependencies(graph))
    findings.extend(_duplicate_targets(jobs))
    findings.extend(_unresolved_upstreams(jobs))
    findings.extend(_disabled_dependencies(jobs))
    return findings


def _circular_dependencies(graph: nx.DiGraph) -> list[ValidationFinding]:
    findings = []
    for cycle in detect_cycles(graph):
        loop = " → ".join(cycle + [cycle[0]])
        findings.append(
            ValidationFinding(
                finding_type="circular_dependency",
                severity="error",
                message=f"Circular dependency detected: {loop}",
                affected_table=", ".join(cycle),
                recommendation="Break the cycle by removing or redirecting one of the ETL jobs in this loop.",
            )
        )
    return findings


def _duplicate_targets(jobs: list[PipelineJob]) -> list[ValidationFinding]:
    target_to_keys: dict[str, list[str]] = defaultdict(list)
    for job in jobs:
        target_to_keys[job.target_table].append(job.config_key)

    findings = []
    for table, keys in target_to_keys.items():
        if len(keys) > 1:
            findings.append(
                ValidationFinding(
                    finding_type="duplicate_target",
                    severity="error",
                    message=f"Multiple jobs write to '{table}': {', '.join(keys)}.",
                    affected_table=table,
                    recommendation="Ensure only one ETL job writes to each target table, or merge the jobs.",
                )
            )
    return findings


def _unresolved_upstreams(jobs: list[PipelineJob]) -> list[ValidationFinding]:
    produced = {job.target_table for job in jobs}
    seen: set[str] = set()
    findings = []

    for job in jobs:
        src = job.source_table
        if src in seen:
            continue
        seen.add(src)

        if src in produced or src.startswith(_EXTERNAL_PREFIXES):
            continue

        findings.append(
            ValidationFinding(
                finding_type="unresolved_upstream",
                severity="info",
                message=(
                    f"Source table '{src}' is not produced by any job in the config "
                    "and does not match a known external prefix."
                ),
                affected_job=job.config_key,
                affected_table=src,
                recommendation=(
                    "Verify this table is populated outside this pipeline config, "
                    "or add the missing ETL job."
                ),
            )
        )
    return findings


def _disabled_dependencies(jobs: list[PipelineJob]) -> list[ValidationFinding]:
    producers: dict[str, list[PipelineJob]] = defaultdict(list)
    for job in jobs:
        producers[job.target_table].append(job)

    findings = []
    for job in jobs:
        if not job.enabled:
            continue

        src_producers = producers.get(job.source_table)
        if not src_producers:
            continue

        if all(not p.enabled for p in src_producers):
            disabled_keys = ", ".join(p.config_key for p in src_producers)
            findings.append(
                ValidationFinding(
                    finding_type="disabled_dependency",
                    severity="error",
                    message=(
                        f"Enabled job '{job.config_key}' depends on '{job.source_table}', "
                        f"which is only produced by disabled job(s): {disabled_keys}."
                    ),
                    affected_job=job.config_key,
                    affected_table=job.source_table,
                    recommendation=(
                        f"Enable the upstream job(s) ({disabled_keys}) "
                        f"or provide an alternative source for '{job.source_table}'."
                    ),
                )
            )
    return findings
