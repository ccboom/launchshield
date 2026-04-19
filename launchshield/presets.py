"""Preset tier definitions — fixed invocation counts per mode."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .models import RunMode


@dataclass(frozen=True)
class TierConfig:
    mode: RunMode
    file_scan: int
    dep_lookup: int
    site_probe: int
    deep_analysis: int
    aisa_verify: int
    fix_suggestion: int

    def total(self) -> int:
        return (
            self.file_scan
            + self.dep_lookup
            + self.site_probe
            + self.deep_analysis
            + self.aisa_verify
            + self.fix_suggestion
        )

    def as_dict(self) -> Dict[str, int]:
        return {
            "file_scan": self.file_scan,
            "dep_lookup": self.dep_lookup,
            "site_probe": self.site_probe,
            "deep_analysis": self.deep_analysis,
            "aisa_verify": self.aisa_verify,
            "fix_suggestion": self.fix_suggestion,
        }


PRESET_STRESS = TierConfig(
    mode=RunMode.PRESET_STRESS,
    file_scan=25,
    dep_lookup=15,
    site_probe=12,
    deep_analysis=6,
    aisa_verify=3,
    fix_suggestion=2,
)

CUSTOM_STANDARD = TierConfig(
    mode=RunMode.CUSTOM_STANDARD,
    file_scan=12,
    dep_lookup=6,
    site_probe=8,
    deep_analysis=4,
    aisa_verify=2,
    fix_suggestion=2,
)

TIERS: Dict[RunMode, TierConfig] = {
    RunMode.PRESET_STRESS: PRESET_STRESS,
    RunMode.CUSTOM_STANDARD: CUSTOM_STANDARD,
}

assert PRESET_STRESS.total() == 63, "preset-stress must total 63 invocations"
assert CUSTOM_STANDARD.total() == 34, "custom-standard must total 34 invocations"


def tier_for(mode: RunMode) -> TierConfig:
    return TIERS[mode]
