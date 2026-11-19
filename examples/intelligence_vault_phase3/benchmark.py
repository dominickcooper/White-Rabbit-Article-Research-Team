"""Reproducible local read benchmark for Phase 3 exploration services."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from white_rabbit.intelligence_vault.database import VaultDB
from white_rabbit.intelligence_vault.exploration import graph_data, timeline_data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relationships", type=int, default=2500)
    args = parser.parse_args()
    count = min(max(args.relationships, 1), 20_000)
    with TemporaryDirectory(prefix="white-rabbit-phase3-") as directory:
        with VaultDB(Path(directory) / "benchmark.db") as db:
            hub = db.add_entity("organization", "Benchmark Hub")
            for index in range(count):
                person = db.add_entity("person", f"Benchmark Person {index:05d}")
                year = 1900 + index % 120
                db.add_relationship(
                    person, hub, "member_of",
                    historical_start={"value": str(year), "precision": "year", "certainty": "certain"},
                    historical_end={"value": str(min(year + 5, 9999)), "precision": "year", "certainty": "certain"},
                )
            started = perf_counter()
            graph = graph_data(db, focus_id=hub, depth=1, limit=500)
            graph_ms = (perf_counter() - started) * 1000
            started = perf_counter()
            timeline = timeline_data(db, start="1900", end="2025", limit=500)
            timeline_ms = (perf_counter() - started) * 1000
            print(f"relationships={count}")
            print(f"graph_ms={graph_ms:.1f} returned_nodes={len(graph['nodes'])} bounded_total={graph['page']['total']}")
            print(f"timeline_ms={timeline_ms:.1f} returned_items={len(timeline['items'])} total={timeline['page']['total']}")


if __name__ == "__main__":
    main()
