"""Deterministic contracts for source thesis, handoff, convergence, and quality gates.

The functions in this module do not decide historical truth or literary quality. They
make required workflow state explicit so missing reviews cannot masquerade as approval.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
import re


GATE_STATUSES = {
    "PASS", "FAIL", "NEEDS REVIEW", "BLOCKED", "NOT RUN",
    "AUTHOR APPROVAL REQUIRED",
}
RABBIT_HOLE_DISPOSITIONS = {
    "DEVELOPED", "CONTRADICTED", "EXHAUSTED", "DEFERRED", "BLOCKED",
}
_STOPWORDS = {
    "about", "after", "against", "also", "and", "are", "article", "author",
    "because", "been", "before", "being", "between", "could", "does", "from",
    "have", "into", "investigation", "more", "must", "that", "the", "their",
    "then", "there", "these", "they", "this", "those", "through", "was", "were",
    "what", "when", "where", "which", "while", "with", "would",
}


@dataclass(frozen=True)
class GateResult:
    status: str
    evidence: str


def markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ims)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)", text
    )
    return match.group(1).strip() if match else ""


def _terms(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9][a-z0-9'/-]{2,}", text.casefold())
        if word not in _STOPWORDS and not word.isdigit()
    }


def thesis_fidelity(source_thesis: str, story_decision: str) -> dict:
    """Diagnose silent thesis replacement without pretending semantic certainty.

    Explicit workflow state controls the result. Token overlap is only a backstop that
    can produce NEEDS REVIEW; it can never approve a thesis change.
    """
    locked = markdown_section(source_thesis, "Principal source-derived thesis")
    selected = (
        markdown_section(story_decision, "Selected central investigation")
        or markdown_section(story_decision, "Revised thesis or central question")
    )
    status_match = re.search(
        r"(?im)^Thesis fidelity outcome:\s*(ALIGNED|REFINED|FUNDAMENTAL CHANGE PROPOSED)\s*$",
        story_decision,
    )
    decision_match = re.search(
        r"(?im)^Author thesis decision:\s*(NOT REQUIRED|REQUIRED|APPROVED)\s*$",
        story_decision,
    )
    outcome = status_match.group(1) if status_match else "MISSING"
    author_decision = decision_match.group(1) if decision_match else "MISSING"
    locked_terms, selected_terms = _terms(locked), _terms(selected)
    overlap = (
        len(locked_terms & selected_terms) / max(1, len(locked_terms | selected_terms))
        if locked_terms and selected_terms else 0.0
    )
    lexical_drift = bool(len(locked_terms) >= 5 and len(selected_terms) >= 5 and overlap < 0.16)
    major_change = outcome == "FUNDAMENTAL CHANGE PROPOSED" or lexical_drift
    approved = author_decision == "APPROVED"
    if not locked or not selected or outcome == "MISSING" or author_decision == "MISSING":
        status = "NOT RUN"
        reason = "Source Thesis or explicit fidelity fields are incomplete."
    elif major_change and not approved:
        status = "NEEDS REVIEW"
        reason = "AUTHOR THESIS DECISION REQUIRED before the investigation can change direction."
    elif major_change and approved:
        status = "PASS"
        reason = "The fundamental change is explicit and the author decision is recorded as APPROVED."
    elif outcome in {"ALIGNED", "REFINED"} and not lexical_drift:
        status = "PASS"
        reason = "The Story Decision explicitly retains or refines the locked investigation."
    else:
        status = "NEEDS REVIEW"
        reason = "The recorded outcome and the selected investigation require human review."
    return {
        "status": status,
        "reason": reason,
        "outcome": outcome,
        "author_decision": author_decision,
        "term_overlap": round(overlap, 3),
        "lexical_drift_signal": lexical_drift,
    }


def network_convergences(paths: list[dict]) -> list[dict]:
    """Return shared nodes while retaining path and source-dependency identities."""
    by_node: dict[str, list[dict]] = defaultdict(list)
    for path in paths:
        path_id = str(path.get("path_id", "")).strip()
        dependency = str(path.get("dependency_group", "")).strip() or path_id
        for node in dict.fromkeys(str(n).strip() for n in path.get("nodes", []) if str(n).strip()):
            by_node[node.casefold()].append({
                "node": node,
                "path_id": path_id,
                "dependency_group": dependency,
                "chronology": path.get("chronology", ""),
                "provenance": path.get("provenance", ""),
            })
    results = []
    for rows in by_node.values():
        path_ids = sorted({row["path_id"] for row in rows if row["path_id"]})
        if len(path_ids) < 2:
            continue
        dependencies = sorted({row["dependency_group"] for row in rows})
        results.append({
            "node": rows[0]["node"],
            "path_ids": path_ids,
            "dependency_groups": dependencies,
            "independent_streams": len(dependencies),
            "requires_investigation": True,
            "unified_command_established": False,
            "rows": rows,
        })
    return sorted(results, key=lambda row: (-len(row["path_ids"]), row["node"].casefold()))


def rabbit_hole_completion(record: dict) -> dict:
    """Validate that a terminal rabbit-hole disposition records actual pursuit."""
    disposition = str(record.get("disposition", "")).upper().strip()
    searches = [x for x in record.get("searches", []) if str(x).strip()]
    readings = [x for x in record.get("records_read", []) if str(x).strip()]
    connections = [x for x in record.get("connections", []) if str(x).strip()]
    reason = str(record.get("stopping_reason", "")).strip()
    contrary = [x for x in record.get("contrary_evidence", []) if str(x).strip()]
    blocker = str(record.get("blocker", "")).strip()
    errors: list[str] = []
    if disposition not in RABBIT_HOLE_DISPOSITIONS:
        errors.append("Use DEVELOPED, CONTRADICTED, EXHAUSTED, DEFERRED, or BLOCKED.")
    if disposition in {"DEVELOPED", "CONTRADICTED", "EXHAUSTED"}:
        if not searches or not readings:
            errors.append("Terminal disposition requires searches and records actually read.")
        if not reason:
            errors.append("Terminal disposition requires a stopping reason.")
    if disposition == "DEVELOPED" and not connections:
        errors.append("DEVELOPED requires consequential connections or findings.")
    if disposition == "CONTRADICTED" and not contrary:
        errors.append("CONTRADICTED requires substantive contrary evidence.")
    if disposition == "EXHAUSTED" and len(searches) < 2:
        errors.append("EXHAUSTED requires more than one identifiable avenue; one failed search is insufficient.")
    if disposition == "DEFERRED" and not reason:
        errors.append("DEFERRED requires a priority or feasibility reason.")
    if disposition == "BLOCKED" and not blocker:
        errors.append("BLOCKED requires the inaccessible record, identifier, or access limitation.")
    return {"valid": not errors, "disposition": disposition, "errors": errors}


def writer_context_manifest(project: Path) -> dict:
    """Declare the controlled writing context and the auditor-only context."""
    primary = (
        "research/SOURCE_THESIS.md", "research/WRITER_PACKET.md",
        "research/STORY_SPINE.md", "research/STYLE_PROFILE.md",
        "ARTICLE_BRIEF.md",
    )
    lookup_only = (
        "output/research_dossier.md", "research/EXTREME_THESIS_LEDGER.md",
        "research/ZEBRA_ANALYSIS.md", "research/THESIS_REDUCTION.md",
        "research/CONNECTION_CHAINS.md", "research/RABBIT_HOLE_QUEUE.md",
    )
    return {
        "writer_primary": [name for name in primary if (project / name).is_file()],
        "writer_lookup_only": [name for name in lookup_only if (project / name).is_file()],
        "auditor_full_research": [
            path.relative_to(project).as_posix()
            for path in sorted((project / "research").rglob("*")) if path.is_file()
        ],
        "rule": "Writer receives the controlled handoff; auditor independently receives the complete research record.",
    }


def _quality_gate_rows(text: str) -> dict[str, GateResult]:
    rows: dict[str, GateResult] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"[A-G]", cells[0]):
            continue
        status = cells[1].upper()
        if status in GATE_STATUSES:
            rows[cells[0]] = GateResult(status, cells[2])
    return rows


def quality_gate_report(project: Path, *, technical_pass: bool) -> dict:
    """Return independent gates; never convert software output into publication approval."""
    gate_file = project / "research/QUALITY_GATES.md"
    rows = _quality_gate_rows(gate_file.read_text(encoding="utf-8-sig")) if gate_file.is_file() else {}
    source_path = project / "research/SOURCE_THESIS.md"
    story_path = project / "research/STORY_DECISION.md"
    fidelity = thesis_fidelity(
        source_path.read_text(encoding="utf-8-sig") if source_path.is_file() else "",
        story_path.read_text(encoding="utf-8-sig") if story_path.is_file() else "",
    )
    gates: dict[str, GateResult] = {
        "A": GateResult("PASS" if technical_pass else "FAIL", "Computed by the mechanical validator."),
        "B": rows.get("B", GateResult("NOT RUN", "Research-completeness review has not been recorded.")),
        "C": rows.get("C", GateResult(fidelity["status"], fidelity["reason"])),
        "D": rows.get("D", GateResult("NOT RUN", "Narrative review has not been recorded.")),
        "E": rows.get("E", GateResult("NOT RUN", "Gold comparison and semantic voice review have not been recorded.")),
        "F": rows.get("F", GateResult("NOT RUN", "Independent evidence-integrity review has not been recorded.")),
        "G": GateResult("AUTHOR APPROVAL REQUIRED", "Software cannot approve publication."),
    }
    if fidelity["status"] in {"FAIL", "NEEDS REVIEW", "BLOCKED"}:
        gates["C"] = GateResult(fidelity["status"], fidelity["reason"])
    return {
        "gates": {key: asdict(value) for key, value in gates.items()},
        "thesis_fidelity": fidelity,
        "publication_status": "AUTHOR APPROVAL REQUIRED",
    }
