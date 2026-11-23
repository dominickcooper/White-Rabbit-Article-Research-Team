"""Create a separate fictional Phase 3 demonstration Vault.

This script refuses to replace a database. It imports only the adjacent fictional report.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from white_rabbit.intelligence_vault.database import VaultDB
from white_rabbit.intelligence_vault.ingestion import ingest_document


def date(value: str, precision: str = "year", certainty: str = "certain") -> dict[str, str]:
    return {"value": value, "precision": precision, "certainty": certainty}


def build_demo(destination: Path) -> dict[str, str]:
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"refusing to replace existing database: {destination}")
    source = Path(__file__).with_name("lantern_field_report.md").resolve()
    with VaultDB(destination) as db:
        person_a = db.add_entity("person", "Avery North", aliases=["A. North"],
                                 details={"birth_value": "1925", "birth_precision": "year", "biography": "Signals officer."})
        person_b = db.add_entity("person", "Blake Rowan", details={"biography": "Logistics specialist."})
        director = db.add_entity("person", "Casey Vale", details={"biography": "Bank director."})
        witness = db.add_entity("person", "Mara Quill", details={"biography": "Witness named in the fictional report."})
        unit = db.add_entity("organization", "47th Analysis Unit", details={"organization_kind": "military_unit"})
        bank = db.add_entity("organization", "Northstar Bank", details={"organization_kind": "bank"})
        foundation = db.add_entity("organization", "Lantern Relief Foundation", details={"organization_kind": "foundation"})
        event = db.add_entity("event", "Operation Lantern", details={
            "event_kind": "operation", "start_value": "1962-03", "start_precision": "month",
            "start_certainty": "probable", "end_value": "1962-08", "end_precision": "month",
            "end_certainty": "uncertain",
        })
        place = db.add_entity("place", "West Germany", details={"place_kind": "country"})
        document, revision, _ = ingest_document(db, source)

        service_claim = db.add_claim(
            "Avery North served in the 47th Analysis Unit from 1960 through 1962.",
            original_wording="Avery North served in the 47th Analysis Unit from 1960 through 1962.",
            entity_ids=[person_a, unit], historical_start=date("1960"), historical_end=date("1962"),
        )
        db.add_claim_evidence(service_claim, revision, locator="paragraph 2",
                              original_wording="Avery North served in the 47th Analysis Unit from 1960 through 1962.")
        db.add_relationship(person_a, unit, "served_in", revision_id=revision, claim_id=service_claim,
                            locator="paragraph 2", original_wording="Avery North served in the 47th Analysis Unit from 1960 through 1962.",
                            historical_start=date("1960"), historical_end=date("1962"))
        db.add_relationship(person_b, unit, "served_in", historical_start=date("1961", "approximate", "possible"),
                            historical_end=date("1963", "approximate", "uncertain"))

        testimony = db.add_claim(
            "The 47th Analysis Unit retained Northstar Bank during Operation Lantern.",
            claim_type="testimony", status="ACCEPTED TESTIMONY", entity_ids=[witness, unit, bank, event],
            historical_start=date("1962", "approximate", "probable"),
            historical_end=date("1962", "approximate", "probable"),
        )
        passage = "According to witness Mara Quill, the 47th Analysis Unit retained Northstar Bank during Operation Lantern."
        db.add_claim_evidence(testimony, revision, locator="paragraph 4", original_wording=passage,
                              attribution="Mara Quill")
        db.add_relationship(unit, bank, "financial_relationship", classification="ACCEPTED TESTIMONY",
                            revision_id=revision, claim_id=testimony, locator="paragraph 4", original_wording=passage,
                            historical_start=date("1962", "approximate", "probable"), historical_end=date("1962"))
        db.add_relationship(event, place, "occurred_in", revision_id=revision, claim_id=testimony,
                            locator="paragraph 6", original_wording="Operation Lantern took place in West Germany between March and August 1962.",
                            historical_start=date("1962-03", "month", "probable"), historical_end=date("1962-08", "month", "uncertain"))
        db.add_relationship(director, bank, "director_of", historical_start=date("1959"), historical_end=date("1966"))
        db.add_relationship(bank, foundation, "financed", classification="CORROBORATED INFERENCE",
                            historical_start=date("1962", "approximate", "possible"), historical_end=date("1964"))
        db.add_relationship(foundation, event, "supported_program", historical_start=date("1962"), historical_end=date("1962"))

        lantern = db.add_investigation("Lantern Files", "Operation and personnel chronology")
        ledger = db.add_investigation("Northstar Ledger", "Financial and institutional relationships")
        for entity_id in (person_a, person_b, unit, event, place):
            db.attach_investigation(entity_id, lantern)
        for entity_id in (person_a, director, bank, foundation):
            db.attach_investigation(entity_id, ledger)
        db.attach_document_investigation(document, lantern, "operation chronology")
        db.attach_document_investigation(document, ledger, "shared financial testimony")
        return {"database": str(destination), "focus_entity": unit, "path_start": person_a,
                "path_end": director, "document": document, "investigation_a": lantern,
                "investigation_b": ledger}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="A new database path")
    args = parser.parse_args()
    for key, value in build_demo(args.db).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
