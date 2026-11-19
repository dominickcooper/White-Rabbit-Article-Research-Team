"""Bounded, read-only exploration services for the Phase 3 interface.

Only accepted Vault tables are used for graph, timeline, path, and profile results.
Deterministic discovery candidates are returned as a separately labelled overlay and are
never inserted into accepted knowledge by this module.
"""
from __future__ import annotations

from collections import deque
from datetime import date
import base64
import csv
from io import StringIO
import json
from typing import Any, Iterable

from .database import VaultDB
from .discovery import SharedAffiliationProvider
from .temporal import HistoricalDate, OverlapResult, ranges_overlap


MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 2000
MAX_TIMELINE_ITEMS = 500
MAX_PATH_DEPTH = 6
MAX_PATHS = 10
CLASSIFICATIONS = {
    "ACCEPTED TESTIMONY": "accepted_testimony",
    "CORROBORATED INFERENCE": "corroborated_inference",
}


def _bounded(value: int, *, default: int, maximum: int) -> int:
    return min(max(int(value or default), 1), maximum)


def _cursor_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        raw = base64.urlsafe_b64decode(cursor.encode() + b"===").decode()
        value = json.loads(raw)
        offset = int(value["offset"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid pagination cursor") from exc
    if offset < 0:
        raise ValueError("invalid pagination cursor")
    return offset


def _next_cursor(offset: int, count: int, has_more: bool) -> str | None:
    if not has_more:
        return None
    raw = json.dumps({"offset": offset + count}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _evidence(db: VaultDB, relationship_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.conn.execute(
        """SELECT re.revision_id, re.claim_id, re.locator, re.original_wording,
                  d.id document_id, d.title document_title, d.author, d.document_date,
                  d.source_classification, d.authority_level, d.original_file, d.original_url,
                  dr.file_hash
           FROM relationship_evidence re
           JOIN document_revisions dr ON dr.id=re.revision_id
           JOIN documents d ON d.id=dr.document_id
           WHERE re.relationship_id=?
           ORDER BY d.title, re.locator, re.revision_id""",
        (relationship_id,),
    )]


def _claim_evidence(db: VaultDB, claim_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.conn.execute(
        """SELECT ce.revision_id, ce.locator, ce.original_wording, ce.independent,
                  ce.dependency_group, ce.attribution, d.id document_id,
                  d.title document_title, d.original_file, d.original_url, dr.file_hash
           FROM claim_evidence ce
           JOIN document_revisions dr ON dr.id=ce.revision_id
           JOIN documents d ON d.id=dr.document_id
           WHERE ce.claim_id=? ORDER BY d.title, ce.locator""",
        (claim_id,),
    )]


def _entity_evidence(db: VaultDB, entity_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in db.conn.execute(
        """SELECT c.id claim_id, c.statement, ce.revision_id, ce.locator,
                  ce.original_wording, ce.attribution, d.id document_id,
                  d.title document_title, d.original_file, d.original_url, dr.file_hash
           FROM claim_entities link JOIN claims c ON c.id=link.claim_id
           JOIN claim_evidence ce ON ce.claim_id=c.id
           JOIN document_revisions dr ON dr.id=ce.revision_id
           JOIN documents d ON d.id=dr.document_id
           WHERE link.entity_id=? ORDER BY c.id, d.title, ce.locator""",
        (entity_id,),
    )]


def _relationship_row(db: VaultDB, relationship_id: str) -> dict[str, Any] | None:
    row = db.conn.execute(
        """SELECT r.*, s.canonical_name subject_name, s.entity_type subject_type,
                  o.canonical_name object_name, o.entity_type object_type
           FROM relationships r
           JOIN entities s ON s.id=r.subject_entity_id
           JOIN entities o ON o.id=r.object_entity_id
           WHERE r.id=?""",
        (relationship_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["evidence"] = _evidence(db, relationship_id)
    result["edge_kind"] = "accepted"
    result["classification_kind"] = CLASSIFICATIONS.get(
        str(result["classification"]).upper(), "accepted_source_backed"
    )
    result["interaction_warning"] = (
        "A stored graph relationship is not, by itself, proof of personal acquaintance or coordination."
    )
    return result


def _historical(value: Any, precision: Any, certainty: Any) -> HistoricalDate:
    return HistoricalDate(value, precision or "unknown", certainty or "unknown")


def _query_date(value: str, *, end: bool = False) -> HistoricalDate:
    value = value.strip()
    if len(value) == 4:
        precision = "year"
    elif len(value) == 7:
        precision = "month"
    else:
        precision = "exact"
    return HistoricalDate(value, precision, "certain")


def temporal_state(row: dict[str, Any], start: str | None, end: str | None) -> str:
    """Return the existing four-state overlap classification for a query window."""
    if not start or not end:
        return OverlapResult.INSUFFICIENT_EVIDENCE.value
    return ranges_overlap(
        _historical(row.get("historical_start"), row.get("historical_start_precision"),
                    row.get("historical_start_certainty")),
        _historical(row.get("historical_end"), row.get("historical_end_precision"),
                    row.get("historical_end_certainty")),
        _query_date(start), _query_date(end, end=True),
    ).value


def _temporal_allowed(state: str, mode: str, has_window: bool) -> bool:
    if mode == "all" or not has_window:
        return True
    if mode == "confirmed":
        return state == OverlapResult.DEFINITE_OVERLAP.value
    if mode == "possible":
        return state == OverlapResult.POSSIBLE_OVERLAP.value
    if mode == "undated":
        return state == OverlapResult.INSUFFICIENT_EVIDENCE.value
    raise ValueError("temporal mode must be confirmed, possible, undated, or all")


def _investigation_map(db: VaultDB, entity_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    ids = sorted(set(entity_ids))
    result = {entity_id: [] for entity_id in ids}
    if not ids:
        return result
    marks = ",".join("?" for _ in ids)
    for row in db.conn.execute(
        f"""SELECT ei.entity_id, i.id, i.name, ei.notes
             FROM entity_investigations ei JOIN investigations i ON i.id=ei.investigation_id
             WHERE ei.entity_id IN ({marks}) ORDER BY i.name""", ids
    ):
        result[str(row["entity_id"])].append({
            "id": row["id"], "name": row["name"], "notes": row["notes"]
        })
    return result


def graph_data(
    db: VaultDB, *, focus_id: str | None = None, depth: int = 1,
    query: str = "", entity_types: set[str] | None = None,
    relationship_types: set[str] | None = None, investigation_ids: set[str] | None = None,
    start: str | None = None, end: str | None = None, temporal_mode: str = "all",
    include_candidates: bool = False, include_documents: bool = False,
    limit: int = 200, cursor: str | None = None,
) -> dict[str, Any]:
    """Return a bounded accepted graph, optionally focused to one-to-three hops."""
    depth = min(max(int(depth), 0), 3)
    limit = _bounded(limit, default=200, maximum=MAX_GRAPH_NODES)
    offset = _cursor_offset(cursor)
    if len(query) > 500:
        raise ValueError("graph search query is too long")
    if relationship_types and len(relationship_types) > 100:
        raise ValueError("too many relationship-type filters")
    if investigation_ids and len(investigation_ids) > 100:
        raise ValueError("too many investigation filters")
    has_window = bool(start and end)
    if bool(start) != bool(end):
        raise ValueError("both start and end are required for temporal filtering")
    if has_window:
        _query_date(start or "")
        _query_date(end or "")
    if temporal_mode not in {"confirmed", "possible", "undated", "all"}:
        raise ValueError("temporal mode must be confirmed, possible, undated, or all")

    membership: set[str] | None = None
    if investigation_ids:
        marks = ",".join("?" for _ in investigation_ids)
        membership = {str(row[0]) for row in db.conn.execute(
            f"SELECT DISTINCT entity_id FROM entity_investigations WHERE investigation_id IN ({marks})",
            sorted(investigation_ids),
        )}

    where: list[str] = []
    params: list[Any] = []
    if relationship_types:
        where.append(f"r.relationship_type IN ({','.join('?' for _ in relationship_types)})")
        params.extend(sorted(relationship_types))
    if membership is not None:
        if not membership:
            return {"nodes": [], "edges": [], "candidates": [],
                    "page": {"limit": limit, "returned": 0, "total": 0, "next_cursor": None},
                    "filters": {"start": start, "end": end, "temporal_mode": temporal_mode,
                                "depth": depth, "include_candidates": include_candidates,
                                "include_documents": include_documents},
                    "notice": "No entities have an explicit membership in the selected investigation(s)."}
        selected_investigations = sorted(investigation_ids or set())
        inv_marks = ",".join("?" for _ in selected_investigations)
        where.append(
            f"EXISTS (SELECT 1 FROM entity_investigations esi "
            f"WHERE esi.entity_id=r.subject_entity_id AND esi.investigation_id IN ({inv_marks}))"
        )
        where.append(
            f"EXISTS (SELECT 1 FROM entity_investigations eoi "
            f"WHERE eoi.entity_id=r.object_entity_id AND eoi.investigation_id IN ({inv_marks}))"
        )
        params.extend(selected_investigations)
        params.extend(selected_investigations)
    sql = """SELECT r.*, s.canonical_name subject_name, s.entity_type subject_type,
                    o.canonical_name object_name, o.entity_type object_type
             FROM relationships r JOIN entities s ON s.id=r.subject_entity_id
             JOIN entities o ON o.id=r.object_entity_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.id"
    all_rows = [dict(row) for row in db.conn.execute(sql, params)]
    filtered: list[dict[str, Any]] = []
    for row in all_rows:
        state = temporal_state(row, start, end)
        if not _temporal_allowed(state, temporal_mode, has_window):
            continue
        row["temporal_overlap"] = state
        filtered.append(row)

    selected_edges: list[dict[str, Any]]
    if focus_id:
        exists = db.conn.execute("SELECT 1 FROM entities WHERE id=?", (focus_id,)).fetchone()
        if not exists:
            raise KeyError(focus_id)
        visited = {focus_id}
        frontier = {focus_id}
        edge_ids: set[str] = set()
        for _ in range(depth):
            next_frontier: set[str] = set()
            for row in filtered:
                left, right = row["subject_entity_id"], row["object_entity_id"]
                if left in frontier or right in frontier:
                    edge_ids.add(row["id"])
                    if left not in visited:
                        next_frontier.add(left)
                    if right not in visited:
                        next_frontier.add(right)
            visited.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break
        selected_edges = [row for row in filtered if row["id"] in edge_ids][:MAX_GRAPH_EDGES]
        entity_ids = visited
    else:
        term = query.casefold().strip()
        entity_rows = db.conn.execute(
            "SELECT id, canonical_name, description FROM entities ORDER BY id"
        ).fetchall()
        entity_ids = {
            str(row["id"]) for row in entity_rows
            if not term or term in str(row["canonical_name"]).casefold()
            or term in str(row["description"]).casefold()
        }
        selected_edges = [
            row for row in filtered
            if row["subject_entity_id"] in entity_ids or row["object_entity_id"] in entity_ids
        ][:MAX_GRAPH_EDGES]
        if not term:
            entity_ids = {eid for row in selected_edges for eid in (row["subject_entity_id"], row["object_entity_id"])}

    ordered_ids = sorted(entity_ids)
    if entity_types and ordered_ids:
        typed = {str(row["id"]) for row in db.conn.execute(
            f"SELECT id FROM entities WHERE entity_type IN ({','.join('?' for _ in entity_types)})",
            sorted(entity_types),
        )}
        ordered_ids = [item for item in ordered_ids if item in typed]
    page_ids = ordered_ids[offset:offset + limit + 1]
    has_more = len(page_ids) > limit
    page_ids = page_ids[:limit]
    page_set = set(page_ids)

    inv_map = _investigation_map(db, page_ids)
    nodes: list[dict[str, Any]] = []
    if page_ids:
        marks = ",".join("?" for _ in page_ids)
        for row in db.conn.execute(
            f"SELECT * FROM entities WHERE id IN ({marks}) ORDER BY canonical_name, id", page_ids
        ):
            node = dict(row)
            node["investigations"] = inv_map.get(str(row["id"]), [])
            node["shared_investigation"] = len(node["investigations"]) > 1
            nodes.append(node)

    edges: list[dict[str, Any]] = []
    document_nodes: dict[str, dict[str, Any]] = {}
    for row in selected_edges:
        if row["subject_entity_id"] not in page_set or row["object_entity_id"] not in page_set:
            continue
        edge = dict(row)
        edge["edge_kind"] = "accepted"
        edge["classification_kind"] = CLASSIFICATIONS.get(
            str(row["classification"]).upper(), "accepted_source_backed"
        )
        edge["evidence"] = _evidence(db, str(row["id"]))
        edge["interaction_warning"] = (
            "This accepted graph edge does not alone establish personal acquaintance or coordination."
        )
        edges.append(edge)
        if include_documents:
            for evidence_index, evidence in enumerate(edge["evidence"]):
                doc_id = str(evidence["document_id"])
                if doc_id not in document_nodes and len(page_ids) + len(document_nodes) >= MAX_GRAPH_NODES:
                    continue
                document_nodes[doc_id] = {
                    "id": doc_id, "canonical_name": evidence["document_title"],
                    "entity_type": "document", "description": "Evidence source",
                    "investigations": [], "shared_investigation": False,
                }
                edges.append({
                    "id": f"EVIDENCE-{row['id']}-{doc_id}-{evidence['revision_id']}-{evidence_index}",
                    "subject_entity_id": row["subject_entity_id"], "object_entity_id": doc_id,
                    "subject_name": row["subject_name"], "object_name": evidence["document_title"],
                    "relationship_type": "supported_by", "directed": 1,
                    "classification": row["classification"], "classification_kind": "source_reference",
                    "edge_kind": "evidence_link", "evidence": [evidence],
                    "historical_start": None, "historical_end": None,
                    "historical_start_precision": "unknown", "historical_end_precision": "unknown",
                    "historical_start_certainty": "unknown", "historical_end_certainty": "unknown",
                    "temporal_overlap": OverlapResult.INSUFFICIENT_EVIDENCE.value,
                })

    candidates: list[dict[str, Any]] = []
    if include_candidates:
        for index, candidate in enumerate(
            SharedAffiliationProvider().discover(db, entity_ids=page_set, limit=MAX_GRAPH_NODES)
        ):
            if candidate.entity_a_id in page_set and candidate.entity_b_id in page_set:
                candidates.append({
                    "id": f"CANDIDATE-{index}-{candidate.entity_a_id}-{candidate.entity_b_id}",
                    "subject_entity_id": candidate.entity_a_id,
                    "object_entity_id": candidate.entity_b_id,
                    "relationship_type": candidate.candidate_type,
                    "basis_entity_id": candidate.basis_entity_id,
                    "classification": "PLAUSIBLE CONNECTION",
                    "classification_kind": "exploratory_candidate",
                    "edge_kind": "candidate",
                    "explanation": candidate.explanation,
                    "interaction_warning": "Institutional overlap is not evidence of personal acquaintance.",
                    "evidence": [],
                })

    nodes.extend(document_nodes.values())
    return {
        "nodes": nodes, "edges": edges, "candidates": candidates,
        "page": {"limit": limit, "returned": len(page_ids), "total": len(ordered_ids),
                 "next_cursor": _next_cursor(offset, len(page_ids), has_more)},
        "filters": {"start": start, "end": end, "temporal_mode": temporal_mode,
                    "depth": depth, "include_candidates": include_candidates,
                    "include_documents": include_documents},
        "notice": "Paths and shared institutions describe graph connectedness, not coordination or acquaintance.",
    }


def relationship_detail(db: VaultDB, relationship_id: str) -> dict[str, Any] | None:
    return _relationship_row(db, relationship_id)


def _event_investigations(db: VaultDB, entity_id: str) -> list[dict[str, Any]]:
    return _investigation_map(db, [entity_id]).get(entity_id, [])


def timeline_data(
    db: VaultDB, *, start: str = "0001", end: str = "9999", entity_id: str | None = None,
    event_type: str | None = None, country: str | None = None,
    investigation_ids: set[str] | None = None, source_id: str | None = None,
    limit: int = 200, cursor: str | None = None,
) -> dict[str, Any]:
    limit = _bounded(limit, default=200, maximum=MAX_TIMELINE_ITEMS)
    offset = _cursor_offset(cursor)
    query_start, query_end = _query_date(start), _query_date(end, end=True)
    membership: set[str] | None = None
    if investigation_ids:
        marks = ",".join("?" for _ in investigation_ids)
        membership = {str(row[0]) for row in db.conn.execute(
            f"SELECT DISTINCT entity_id FROM entity_investigations WHERE investigation_id IN ({marks})",
            sorted(investigation_ids),
        )}

    items: list[dict[str, Any]] = []
    for row in db.conn.execute(
        """SELECT e.id, e.canonical_name label, e.description, d.event_kind,
                  d.start_value historical_start, d.start_precision historical_start_precision,
                  d.start_certainty historical_start_certainty, d.end_value historical_end,
                  d.end_precision historical_end_precision, d.end_certainty historical_end_certainty
           FROM entities e JOIN event_details d ON d.entity_id=e.id ORDER BY d.start_value, e.id"""
    ):
        item = dict(row)
        if entity_id and item["id"] != entity_id:
            continue
        if event_type and item["event_kind"] != event_type:
            continue
        if membership is not None and item["id"] not in membership:
            continue
        state = ranges_overlap(
            _historical(item["historical_start"], item["historical_start_precision"], item["historical_start_certainty"]),
            _historical(item["historical_end"], item["historical_end_precision"], item["historical_end_certainty"]),
            query_start, query_end,
        ).value
        if state == OverlapResult.NO_OVERLAP.value:
            continue
        evidence = _entity_evidence(db, item["id"])
        if source_id and not any(record["document_id"] == source_id for record in evidence):
            continue
        item.update({"kind": "event", "temporal_overlap": state,
                     "investigations": _event_investigations(db, item["id"]), "evidence": evidence})
        items.append(item)

    for raw in db.conn.execute(
        """SELECT r.*, s.canonical_name subject_name, o.canonical_name object_name
           FROM relationships r JOIN entities s ON s.id=r.subject_entity_id
           JOIN entities o ON o.id=r.object_entity_id ORDER BY r.historical_start, r.id"""
    ):
        row = dict(raw)
        if entity_id and entity_id not in {row["subject_entity_id"], row["object_entity_id"]}:
            continue
        if membership is not None and not ({row["subject_entity_id"], row["object_entity_id"]} <= membership):
            continue
        evidence = _evidence(db, row["id"])
        if source_id and not any(item["document_id"] == source_id for item in evidence):
            continue
        state = ranges_overlap(
            _historical(row["historical_start"], row["historical_start_precision"], row["historical_start_certainty"]),
            _historical(row["historical_end"], row["historical_end_precision"], row["historical_end_certainty"]),
            query_start, query_end,
        ).value
        if state == OverlapResult.NO_OVERLAP.value:
            continue
        row.update({
            "label": f"{row['subject_name']} — {row['relationship_type'].replace('_', ' ')} — {row['object_name']}",
            "kind": "relationship", "temporal_overlap": state, "evidence": evidence,
        })
        items.append(row)

    if country:
        country_ids = {str(row["id"]) for row in db.conn.execute(
            "SELECT id FROM entities WHERE entity_type='place' AND lower(canonical_name) LIKE ?",
            (f"%{country.casefold()}%",),
        )}
        connected = set(country_ids)
        for row in db.conn.execute("SELECT subject_entity_id,object_entity_id FROM relationships"):
            if row["subject_entity_id"] in country_ids:
                connected.add(str(row["object_entity_id"]))
            if row["object_entity_id"] in country_ids:
                connected.add(str(row["subject_entity_id"]))
        items = [item for item in items if item.get("id") in connected
                 or item.get("subject_entity_id") in connected or item.get("object_entity_id") in connected]

    items.sort(key=lambda item: (item.get("historical_start") or "9999-12-31", item["kind"], item["id"]))
    page = items[offset:offset + limit + 1]
    has_more = len(page) > limit
    page = page[:limit]
    return {
        "items": page,
        "page": {"limit": limit, "returned": len(page), "total": len(items),
                 "next_cursor": _next_cursor(offset, len(page), has_more)},
        "window": {"start": start, "end": end},
    }


def _path_temporal(edges: list[dict[str, Any]]) -> dict[str, str]:
    known = [edge for edge in edges if edge.get("historical_start")]
    if not known:
        return {"state": "undated", "explanation": "No edge in this path has a known start date."}
    if len(known) != len(edges):
        return {"state": "insufficient_evidence", "explanation": "At least one edge is undated."}
    lower: date | None = None
    upper: date | None = None
    uncertain = False
    for edge in known:
        start = _historical(edge["historical_start"], edge["historical_start_precision"], edge["historical_start_certainty"])
        end = _historical(edge["historical_end"], edge["historical_end_precision"], edge["historical_end_certainty"])
        start_bounds, end_bounds = start.bounds(), end.bounds()
        edge_low = start_bounds[0]
        edge_high = end_bounds[1] if end_bounds[1] else date.max
        if edge_low is None:
            return {"state": "insufficient_evidence", "explanation": "At least one edge is undated."}
        lower = max(lower, edge_low) if lower else edge_low
        upper = min(upper, edge_high) if upper else edge_high
        uncertain = uncertain or start.uncertain or (end.value is not None and end.uncertain)
    if lower and upper and lower > upper:
        return {"state": "temporally_incompatible",
                "explanation": "The stored relationship ranges do not share a common historical period."}
    return {"state": "possible" if uncertain else "chronologically_coherent",
            "explanation": "The stored relationship ranges have a common possible period; this does not prove interaction."}


def connection_paths(
    db: VaultDB, source_id: str, target_id: str, *, max_depth: int = 4,
    relationship_types: set[str] | None = None, respect_direction: bool = False,
    max_paths: int = 5,
) -> dict[str, Any]:
    if source_id == target_id:
        raise ValueError("source and target must be different entities")
    max_depth = min(max(int(max_depth), 1), MAX_PATH_DEPTH)
    max_paths = min(max(int(max_paths), 1), MAX_PATHS)
    if relationship_types and len(relationship_types) > 100:
        raise ValueError("too many relationship-type filters")
    entities = {str(row["id"]): dict(row) for row in db.conn.execute("SELECT * FROM entities")}
    if source_id not in entities:
        raise KeyError(source_id)
    if target_id not in entities:
        raise KeyError(target_id)
    edges: dict[str, dict[str, Any]] = {}
    adjacency_cache: dict[str, list[tuple[str, str]]] = {}

    def adjacent(entity: str) -> list[tuple[str, str]]:
        if entity in adjacency_cache:
            return adjacency_cache[entity]
        params: list[Any] = [entity, entity]
        type_sql = ""
        if relationship_types:
            marks = ",".join("?" for _ in relationship_types)
            type_sql = f" AND relationship_type IN ({marks})"
            params.extend(sorted(relationship_types))
        rows = db.conn.execute(
            "SELECT * FROM relationships WHERE (subject_entity_id=? OR object_entity_id=?)"
            + type_sql + " ORDER BY id", params
        ).fetchall()
        result: list[tuple[str, str]] = []
        for raw in rows:
            edge = dict(raw)
            edges[edge["id"]] = edge
            if edge["subject_entity_id"] == entity:
                result.append((edge["object_entity_id"], edge["id"]))
            elif not respect_direction or not edge["directed"]:
                result.append((edge["subject_entity_id"], edge["id"]))
        adjacency_cache[entity] = result
        return result

    queue = deque([(source_id, [source_id], [])])
    found: list[tuple[list[str], list[str]]] = []
    shortest: int | None = None
    while queue and len(found) < max_paths:
        current, node_path, edge_path = queue.popleft()
        if shortest is not None and len(edge_path) >= shortest:
            continue
        if len(edge_path) >= max_depth:
            continue
        for neighbor, edge_id in adjacent(current):
            if neighbor in node_path:
                continue
            next_nodes, next_edges = [*node_path, neighbor], [*edge_path, edge_id]
            if neighbor == target_id:
                shortest = len(next_edges)
                found.append((next_nodes, next_edges))
            else:
                queue.append((neighbor, next_nodes, next_edges))

    paths = []
    for node_ids, edge_ids in found[:max_paths]:
        path_edges = []
        for item in edge_ids:
            edge = dict(edges[item])
            edge["evidence"] = _evidence(db, item)
            path_edges.append(edge)
        paths.append({
            "nodes": [entities[item] for item in node_ids],
            "edges": path_edges,
            "hop_count": len(edge_ids),
            "temporal_compatibility": _path_temporal(path_edges),
            "meaning_boundary": "This is an existing accepted graph path, not proof of a demonstrated historical interaction or coordination.",
        })
    return {
        "source": entities[source_id], "target": entities[target_id], "paths": paths,
        "max_depth": max_depth, "respect_direction": respect_direction,
        "notice": "Connectedness alone does not establish acquaintance, coordination, or common command.",
    }


def entity_profile(db: VaultDB, entity_id: str) -> dict[str, Any] | None:
    profile = db.get_entity(entity_id)
    if profile is None:
        return None
    profile["investigations"] = _investigation_map(db, [entity_id]).get(entity_id, [])
    profile["documents"] = []
    documents: dict[str, dict[str, Any]] = {}
    for claim in profile["claims"]:
        claim["evidence"] = _claim_evidence(db, claim["id"])
        for evidence in claim["evidence"]:
            documents[evidence["document_id"]] = {
                "id": evidence["document_id"], "title": evidence["document_title"],
                "original_file": evidence["original_file"], "original_url": evidence["original_url"],
            }
    for relationship in profile["relationships"]:
        relationship["evidence"] = _evidence(db, relationship["id"])
        relationship["classification_kind"] = CLASSIFICATIONS.get(
            str(relationship["classification"]).upper(), "accepted_source_backed"
        )
        for evidence in relationship["evidence"]:
            documents[evidence["document_id"]] = {
                "id": evidence["document_id"], "title": evidence["document_title"],
                "original_file": evidence["original_file"], "original_url": evidence["original_url"],
            }
    profile["documents"] = sorted(documents.values(), key=lambda item: (item["title"], item["id"]))
    profile["identity_matches"] = [dict(row) for row in db.conn.execute(
        """SELECT * FROM merge_suggestions
           WHERE status='open' AND (entity_a_id=? OR entity_b_id=?) ORDER BY created_at""",
        (entity_id, entity_id),
    )]
    claim_ids = [claim["id"] for claim in profile["claims"]]
    profile["conflicts"] = []
    if claim_ids:
        marks = ",".join("?" for _ in claim_ids)
        profile["conflicts"] = [dict(row) for row in db.conn.execute(
            f"SELECT * FROM conflicts WHERE claim_a_id IN ({marks}) OR claim_b_id IN ({marks}) ORDER BY created_at",
            (*claim_ids, *claim_ids),
        )]
    profile["timeline"] = timeline_data(db, start="0001", end="9999", entity_id=entity_id,
                                        limit=MAX_TIMELINE_ITEMS)["items"]
    return profile


def investigations_data(db: VaultDB, selected_ids: set[str] | None = None) -> dict[str, Any]:
    investigations = [dict(row) for row in db.conn.execute(
        "SELECT * FROM investigations ORDER BY name, id"
    )]
    memberships = [dict(row) for row in db.conn.execute(
        """SELECT ei.entity_id, ei.investigation_id, ei.notes, e.canonical_name, e.entity_type
           FROM entity_investigations ei JOIN entities e ON e.id=ei.entity_id
           ORDER BY e.canonical_name, ei.investigation_id"""
    )]
    document_memberships = [dict(row) for row in db.conn.execute(
        """SELECT di.document_id, di.investigation_id, di.notes, d.title,
                  d.source_classification, d.authority_level
           FROM document_investigations di JOIN documents d ON d.id=di.document_id
           ORDER BY d.title, di.investigation_id"""
    )]
    counts: dict[str, int] = {}
    for item in memberships:
        counts[item["investigation_id"]] = counts.get(item["investigation_id"], 0) + 1
    for item in investigations:
        item["entity_count"] = counts.get(item["id"], 0)
    selected = selected_ids or set()
    by_entity: dict[str, set[str]] = {}
    entity_records: dict[str, dict[str, Any]] = {}
    for item in memberships:
        by_entity.setdefault(item["entity_id"], set()).add(item["investigation_id"])
        entity_records[item["entity_id"]] = {
            "id": item["entity_id"], "canonical_name": item["canonical_name"],
            "entity_type": item["entity_type"],
        }
    shared = []
    shared_documents = []
    if len(selected) >= 2:
        for entity_id, invs in by_entity.items():
            overlap = invs & selected
            if len(overlap) >= 2:
                record = dict(entity_records[entity_id])
                record["investigation_ids"] = sorted(overlap)
                shared.append(record)
        document_map: dict[str, set[str]] = {}
        document_records: dict[str, dict[str, Any]] = {}
        for item in document_memberships:
            document_map.setdefault(item["document_id"], set()).add(item["investigation_id"])
            document_records[item["document_id"]] = {
                "id": item["document_id"], "title": item["title"],
                "source_classification": item["source_classification"],
                "authority_level": item["authority_level"],
            }
        for document_id, invs in document_map.items():
            overlap = invs & selected
            if len(overlap) >= 2:
                record = dict(document_records[document_id])
                record["investigation_ids"] = sorted(overlap)
                shared_documents.append(record)
    return {"investigations": investigations, "memberships": memberships,
            "document_memberships": document_memberships, "selected_ids": sorted(selected),
            "shared_entities": shared, "shared_documents": shared_documents}


def timeline_csv(payload: dict[str, Any]) -> str:
    output = StringIO()
    fields = ["id", "kind", "label", "historical_start", "historical_start_precision",
              "historical_start_certainty", "historical_end", "historical_end_precision",
              "historical_end_certainty", "temporal_overlap"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(payload["items"])
    return output.getvalue()
