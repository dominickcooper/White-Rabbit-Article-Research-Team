from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
import re


class OverlapResult(str, Enum):
    DEFINITE_OVERLAP = "definite_overlap"
    POSSIBLE_OVERLAP = "possible_overlap"
    NO_OVERLAP = "no_overlap"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class HistoricalDate:
    """A date value whose precision and evidentiary certainty remain explicit."""

    value: str | None = None
    precision: str = "unknown"
    certainty: str = "unknown"

    def bounds(self) -> tuple[date | None, date | None]:
        """Return the earliest and latest date represented by this value."""
        if not self.value or self.precision == "unknown":
            return None, None
        value = self.value.strip()
        if self.precision == "approximate":
            if re.fullmatch(r"\d{4}", value):
                year = int(value)
                return date(max(1, year - 1), 1, 1), date(min(9999, year + 1), 12, 31)
            if re.fullmatch(r"\d{4}-\d{2}", value):
                year, month = map(int, value.split("-"))
                center_start = date(year, month, 1)
                center_end = date(year, month, monthrange(year, month)[1])
                return center_start - timedelta(days=31), center_end + timedelta(days=31)
            center = date.fromisoformat(value)
            return center - timedelta(days=31), center + timedelta(days=31)
        if self.precision == "year":
            if not re.fullmatch(r"\d{4}", value):
                raise ValueError(f"year precision requires YYYY: {value}")
            year = int(value)
            return date(year, 1, 1), date(year, 12, 31)
        if self.precision == "month":
            if not re.fullmatch(r"\d{4}-\d{2}", value):
                raise ValueError(f"month precision requires YYYY-MM: {value}")
            year, month = map(int, value.split("-"))
            return date(year, month, 1), date(year, month, monthrange(year, month)[1])
        if self.precision == "exact":
            parsed = date.fromisoformat(value)
            return parsed, parsed
        raise ValueError(f"unsupported historical date precision: {self.precision}")

    @property
    def uncertain(self) -> bool:
        return self.precision == "approximate" or self.certainty in {"probable", "possible", "uncertain", "unknown"}


def ranges_overlap(
    start_a: HistoricalDate,
    end_a: HistoricalDate,
    start_b: HistoricalDate,
    end_b: HistoricalDate,
) -> OverlapResult:
    """Classify overlap without collapsing uncertain or missing chronology to a Boolean."""
    a_start_early, a_start_late = start_a.bounds()
    b_start_early, b_start_late = start_b.bounds()
    if a_start_early is None or b_start_early is None:
        return OverlapResult.INSUFFICIENT_EVIDENCE

    a_end_early, a_end_late = end_a.bounds()
    b_end_early, b_end_late = end_b.bounds()
    a_open, b_open = a_end_early is None, b_end_early is None
    if a_open:
        a_end_early = a_end_late = date.max
    if b_open:
        b_end_early = b_end_late = date.max

    if a_end_late < a_start_early or b_end_late < b_start_early:
        return OverlapResult.INSUFFICIENT_EVIDENCE
    if a_end_late < b_start_early or b_end_late < a_start_early:
        return OverlapResult.NO_OVERLAP

    definite = a_start_late <= b_end_early and b_start_late <= a_end_early
    uncertain = start_a.uncertain or start_b.uncertain
    if not a_open:
        uncertain = uncertain or end_a.uncertain
    if not b_open:
        uncertain = uncertain or end_b.uncertain
    if definite and not uncertain:
        return OverlapResult.DEFINITE_OVERLAP
    return OverlapResult.POSSIBLE_OVERLAP
