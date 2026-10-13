from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SampledPage:
    domain: str
    url: str
    reason: str
    rank: int

    def to_dict(self) -> dict:
        return asdict(self)
