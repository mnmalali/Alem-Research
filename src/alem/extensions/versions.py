"""Small, deliberately conservative version constraint helper.

This is not a general dependency solver.  API v1 accepts comma-separated
comparators (``>=``, ``>``, ``<=``, ``<``, ``==``) over numeric dotted
versions, which is enough for deterministic foundation-phase resolution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ManifestError

_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_API_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?$")
_COMPARATOR = re.compile(r"^(>=|<=|==|>|<)\s*(\d+\.\d+(?:\.\d+)?)$")


@dataclass(frozen=True, order=True, slots=True)
class Version:
    major: int
    minor: int
    patch: int = 0

    @classmethod
    def parse(cls, text: str, *, api: bool = False) -> Version:
        match = (_API_VERSION if api else _VERSION).fullmatch(text)
        if not match:
            kind = "API version" if api else "semantic version"
            raise ManifestError(f"invalid {kind}: {text!r}")
        return cls(int(match[1]), int(match[2]), int(match[3] or 0))


def satisfies(version: str, constraint: str, *, api: bool = False) -> bool:
    candidate = Version.parse(version, api=api)
    if not constraint.strip():
        raise ManifestError("version constraint may not be empty")
    for raw in constraint.split(","):
        match = _COMPARATOR.fullmatch(raw.strip())
        if not match:
            raise ManifestError(f"invalid version constraint component: {raw!r}")
        expected = Version.parse(match[2], api=True)
        operator = match[1]
        checks = {
            ">=": candidate >= expected,
            "<=": candidate <= expected,
            ">": candidate > expected,
            "<": candidate < expected,
            "==": candidate == expected,
        }
        if not checks[operator]:
            return False
    return True
