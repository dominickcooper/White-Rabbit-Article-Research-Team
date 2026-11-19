"""Read-only extension boundary for future connection-discovery engines.

Discovery providers return candidates, never facts. A candidate becomes a stored claim or
relationship only through an explicit reviewed write using :class:`VaultDB`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .database import VaultDB
from .temporal import HistoricalDate, ranges_overlap


@dataclass(frozen=True)
class ConnectionCandidate:
    entity_a_id: str
    entity_b_id: str
    basis_entity_id: str
    candidate_type: str
    explanation: str
    significance_score: float | None = None


class DiscoveryProvider(Protocol):
    name: str

    def discover(self, db: VaultDB) -> list[ConnectionCandidate]: ...


class SharedAffiliationProvider:
    """Find overlapping affiliations without asserting personal contact."""

    name = "shared-affiliation-overlap"

    def discover(self, db: VaultDB) -> list[ConnectionCandidate]:
        rows = db.conn.execute(
            """SELECT a.subject_entity_id a_id, b.subject_entity_id b_id,
                      a.object_entity_id basis_id, a.historical_start a_start,
                      a.historical_start_precision a_start_precision, a.historical_end a_end,
                      a.historical_end_precision a_end_precision, b.historical_start b_start,
                      b.historical_start_precision b_start_precision, b.historical_end b_end,
                      b.historical_end_precision b_end_precision, o.canonical_name basis_name
               FROM relationships a JOIN relationships b
                 ON a.object_entity_id=b.object_entity_id AND a.subject_entity_id < b.subject_entity_id
                AND a.relationship_type=b.relationship_type
               JOIN entities o ON o.id=a.object_entity_id
               WHERE a.relationship_type IN ('member_of','served_in','employed_by','director_of')"""
        ).fetchall()
        candidates = []
        for row in rows:
            overlap = ranges_overlap(
                HistoricalDate(row["a_start"], row["a_start_precision"]), HistoricalDate(row["a_end"], row["a_end_precision"]),
                HistoricalDate(row["b_start"], row["b_start_precision"]), HistoricalDate(row["b_end"], row["b_end_precision"]),
            )
            if overlap:
                candidates.append(ConnectionCandidate(
                    row["a_id"], row["b_id"], row["basis_id"], "institutional_overlap",
                    f"Overlapping {row['basis_name']} affiliation; this does not establish personal contact.",
                ))
        return candidates
