from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True)
class HistoricalDate:
    """A sortable historical date with explicit precision and certainty."""

    value: str | None = None
    precision: str = "unknown"
    certainty: str = "unknown"

    def bounds(self) -> tuple[date | None, date | None]:
        if not self.value:
            return None, None
        if self.precision == "year" or re.fullmatch(r"\d{4}", self.value):
            year = int(self.value[:4])
            return date(year, 1, 1), date(year, 12, 31)
        if self.precision == "month" or re.fullmatch(r"\d{4}-\d{2}", self.value):
            year, month = map(int, self.value.split("-")[:2])
            if month == 12:
                last = date(year, 12, 31)
            else:
                last = date(year, month + 1, 1).fromordinal(date(year, month + 1, 1).toordinal() - 1)
            return date(year, month, 1), last
        parsed = date.fromisoformat(self.value[:10])
        return parsed, parsed


def ranges_overlap(
    start_a: HistoricalDate,
    end_a: HistoricalDate,
    start_b: HistoricalDate,
    end_b: HistoricalDate,
) -> bool | None:
    """Return overlap, treating missing ends as open and missing starts as unknown."""
    a_start, _ = start_a.bounds()
    b_start, _ = start_b.bounds()
    if a_start is None or b_start is None:
        return None
    _, a_end = end_a.bounds()
    _, b_end = end_b.bounds()
    return (a_end is None or b_start <= a_end) and (b_end is None or a_start <= b_end)
