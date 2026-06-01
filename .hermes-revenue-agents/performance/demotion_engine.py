"""
DemotionEngine — Evaluates and triggers grade demotions.
Part of the V5 Hermes Revenue Agent Network.
"""
from datetime import datetime, timedelta
from agent_scorecard import AgentScorecard


GRADE_ORDER = ["FRAUD", "D", "C", "B", "A", "S"]
LOW_SCORE_THRESHOLD = 50.0  # scores below this are "low"


class DemotionEngine:
    """Determines whether an agent qualifies for a grade demotion.

    Rules (hardcoded per specification):
      - C  after 3 days of low score (total_score < LOW_SCORE_THRESHOLD).
      - D  after 5 days of low score.
      - FRAUD triggered immediately by any hard gaming violation.
    """

    def __init__(self, custom_rules: dict = None):
        """Optionally inject custom demotion rules.

        Expected structure:
            {
                "grade_order": ["FRAUD", "D", "C", "B", "A", "S"],
                "low_score_threshold": 50.0,
                "demotion_rules": [
                    {"from": "B", "to": "C", "low_score_days": 3},
                    {"from": "C", "to": "D", "low_score_days": 5},
                ],
                "fraud_rules": ["HG-001", "HG-002", "HG-003", "HG-004", "HG-005"],
            }
        """
        self._rules = custom_rules or {}
        self.grade_order = self._rules.get("grade_order", GRADE_ORDER)
        self.low_score_threshold = self._rules.get(
            "low_score_threshold", LOW_SCORE_THRESHOLD
        )
        self._demotion_rules = self._rules.get("demotion_rules", [
            {"from": "B", "to": "C", "low_score_days": 3},
            {"from": "C", "to": "D", "low_score_days": 5},
        ])
        self._fraud_rules = self._rules.get("fraud_rules", [
            "HG-001", "HG-002", "HG-003", "HG-004", "HG-005",
        ])

    def check_demotion(
        self, agent_id: str, current_grade: str, violations: list
    ) -> tuple:
        """Evaluate whether the agent should be demoted.

        Parameters
        ----------
        agent_id : str
        current_grade : str
        violations : list of dict or str
            Each violation should be a dict with keys ``type``, ``date``,
            ``rule_id``, ``severity``, or a plain str rule_id.

        Returns
        -------
        (demoted: bool, new_grade: str, reason: str)
        """
        current = current_grade.upper()

        # ── 1. Check for hard gaming — immediate FRAUD ──────────── #
        hard_trigger = self._check_hard_gaming(violations)
        if hard_trigger is not None:
            return (
                True,
                "FRAUD",
                f"Hard gaming violation detected ({hard_trigger}). "
                f"Agent {agent_id} marked as FRAUD — immediate termination.",
            )

        # ── 2. FRAUD cannot be demoted further ──────────────────── #
        if current == "FRAUD":
            return (False, current, "Agent is already FRAUD — no further demotion.")

        # ── 3. Check low-score duration demotions ───────────────── #
        low_score_days = self._count_low_score_days(violations)

        # Current grade index
        try:
            cur_idx = self.grade_order.index(current)
        except ValueError:
            return (False, current, f"Unknown grade {current}.")

        # Try demotion rules in order (B→C, C→D)
        for rule in self._demotion_rules:
            if rule["from"] != current:
                continue
            required_days = rule["low_score_days"]
            if low_score_days >= required_days:
                new_grade = rule["to"]
                return (
                    True,
                    new_grade,
                    f"Demoted from {current} to {new_grade}: "
                    f"{low_score_days} consecutive low-score days "
                    f"(threshold {required_days}).",
                )
            else:
                # Not enough days yet
                remaining = required_days - low_score_days
                return (
                    False,
                    current,
                    f"Low-score days: {low_score_days}/{required_days} "
                    f"needed for demotion to {rule['to']}. "
                    f"{remaining} more day(s) required.",
                )

        # No matching rule — no demotion
        return (
            False,
            current,
            f"Current grade {current} has no active demotion rule.",
        )

    # ═══════════════════════════════════════════════════════════════ #
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════ #

    def _check_hard_gaming(self, violations: list) -> str | None:
        """Return the rule_id of the first hard gaming violation, or None."""
        for v in violations:
            rule_id = self._extract_rule_id(v)
            if rule_id in self._fraud_rules:
                return rule_id
        return None

    def _count_low_score_days(self, violations: list) -> int:
        """Count how many distinct days had a low score.

        Violations relevant to low scores are expected to have a ``type``
        of ``low_score``, ``score_too_low``, or similar.
        """
        seen_dates = set()
        for v in violations:
            vtype = self._extract_type(v)
            if vtype in ("low_score", "score_too_low", "below_threshold"):
                dt = self._extract_date(v)
                if dt:
                    seen_dates.add(dt)
        return len(seen_dates)

    # ── Normalisation helpers ───────────────────────────────────── #

    @staticmethod
    def _extract_rule_id(violation) -> str:
        if isinstance(violation, str):
            return violation
        if isinstance(violation, dict):
            return violation.get("rule_id", violation.get("id", ""))
        return str(violation)

    @staticmethod
    def _extract_type(violation) -> str:
        if isinstance(violation, dict):
            return violation.get("type", violation.get("event", ""))
        return str(violation)

    @staticmethod
    def _extract_date(violation) -> str | None:
        if isinstance(violation, dict):
            dt = violation.get("date", violation.get("timestamp", None))
            if dt:
                return str(dt)[:10]  # normalise to YYYY-MM-DD
        return None
