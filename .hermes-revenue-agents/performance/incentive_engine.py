"""
IncentiveEngine — Determines agent incentives based on grade.
Part of the V5 Hermes Revenue Agent Network.
"""


class IncentiveEngine:
    """Translates a grade into quota adjustments, task priority, and agent level.

    Mapping (hardcoded per specification):
        S     →  1.5x quota  +  high priority
        A     →  1.0x quota  +  normal priority
        B     →  0.5x quota  +  low priority
        C     →  0.25x quota +  restricted priority
        D     →  suspended   +  suspended
        FRAUD →  killed      +  killed
    """

    # ── Grade → multiplier mapping ──────────────────────────────── #
    QUOTA_MAP = {
        "S": 1.5,
        "A": 1.0,
        "B": 0.5,
        "C": 0.25,
        "D": 0.0,
        "FRAUD": 0.0,
    }

    # ── Grade → task priority ───────────────────────────────────── #
    PRIORITY_MAP = {
        "S": "high",
        "A": "normal",
        "B": "low",
        "C": "restricted",
        "D": "suspended",
        "FRAUD": "killed",
    }

    # ── Grade → agent level ─────────────────────────────────────── #
    LEVEL_MAP = {
        "S": "S",
        "A": "A",
        "B": "B",
        "C": "C",
        "D": "D",
        "FRAUD": "FRAUD",
    }

    def __init__(self, incentive_rules: dict = None):
        """Optionally accept custom incentive rules dict.

        Expected structure (same as defaults, can be partial):
            {
                "quota_multipliers": {"S": 1.5, ...},
                "priority_map": {"S": "high", ...},
                "level_map": {"S": "S", ...},
            }
        """
        self._rules = incentive_rules or {}
        # Merge custom overrides on top of defaults
        self._quota = {**self.QUOTA_MAP, **self._rules.get("quota_multipliers", {})}
        self._priority = {**self.PRIORITY_MAP, **self._rules.get("priority_map", {})}
        self._level = {**self.LEVEL_MAP, **self._rules.get("level_map", {})}

    def calculate_quota_adjustment(self, grade: str) -> float:
        """Return a multiplier applied to base quota.

        S=1.5, A=1.0, B=0.5, C=0.25, D=0.0, FRAUD=0.0.
        Unknown grades return 0.0.
        """
        return self._quota.get(grade.upper(), 0.0)

    def get_task_priority(self, grade: str) -> str:
        """Return task priority string for the given grade.

        S=high, A=normal, B=low, C=restricted, D=suspended, FRAUD=killed.
        """
        return self._priority.get(grade.upper(), "unknown")

    def get_agent_level(self, grade: str) -> str:
        """Return agent level label.

        S/A/B/C/D/FRAUD → same string.
        """
        return self._level.get(grade.upper(), "UNKNOWN")

    def is_active(self, grade: str) -> bool:
        """Return True if the agent may still receive tasks."""
        return grade.upper() not in ("D", "FRAUD")
