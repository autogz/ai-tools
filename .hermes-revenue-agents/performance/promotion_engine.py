"""
PromotionEngine — Evaluates eligibility for grade promotion.
Part of the V5 Hermes Revenue Agent Network.
"""
from datetime import datetime
from agent_scorecard import AgentScorecard


# Grade ordering for comparison
GRADE_ORDER = ["D", "C", "B", "A", "S"]


class PromotionEngine:
    """Determines whether an agent qualifies for a grade promotion.

    Promotion rules (hardcoded per specification):
      - B is the default starting grade for new agents.
      - S requires 3+ consecutive A grades in history.
      - A requires 5+ consecutive B grades followed by 2 A grades.
      - Otherwise no promotion.

    A "promotion_record" dict is generated for every check, regardless
    of outcome.
    """

    def __init__(self, custom_rules: dict = None):
        """Optionally inject custom promotion rules.

        Expected structure:
            {
                "default_grade": "B",
                "grade_order": ["D", "C", "B", "A", "S"],
                "promotion_rules": [
                    {"target": "S", "required_grade": "A", "consecutive": 3},
                    {"target": "A", "required_grade": "B", "consecutive": 5,
                     "then_grade": "A", "then_count": 2},
                ],
            }
        """
        self._rules = custom_rules or {}
        self.default_grade = self._rules.get("default_grade", "B")
        self.grade_order = self._rules.get("grade_order", GRADE_ORDER)
        self._promotion_rules = self._rules.get("promotion_rules", [
            {"target": "S", "required_grade": "A", "consecutive": 3},
            {"target": "A", "required_grade": "B", "consecutive": 5,
             "then_grade": "A", "then_count": 2},
        ])

    def check_promotion(
        self, agent_id: str, current_grade: str, history: list
    ) -> tuple:
        """Evaluate promotion eligibility.

        Parameters
        ----------
        agent_id : str
        current_grade : str
            The agent's current grade (e.g. "B").
        history : list of dict or list of str
            Each entry should be a dict with at least a ``grade`` key,
            or a plain grade string.  Ordered most-recent-first.

        Returns
        -------
        (promoted: bool, new_grade: str, reason: str)
        """
        current = current_grade.upper()

        # Normalise history to list of grade strings (most recent first)
        grades = self._normalise_history(history)

        # Build promotion record regardless of outcome
        record = self._build_record(agent_id, current, grades)

        # ── FRAUD / D cannot be promoted ────────────────────────── #
        if current in ("FRAUD", "D"):
            return (
                False,
                current,
                "Agents with FRAUD or D grade are not eligible for promotion.",
            )

        # ── Check each rule in order (highest target first) ─────── #
        for rule in sorted(
            self._promotion_rules,
            key=lambda r: self.grade_order.index(r["target"]),
            reverse=True,
        ):
            target = rule["target"]
            if self.grade_order.index(target) <= self.grade_order.index(current):
                continue  # already at or above target

            required_grade = rule["required_grade"]
            consecutive = rule["consecutive"]

            # Check the first N entries are all required_grade
            if len(grades) < consecutive:
                continue
            if not all(g == required_grade for g in grades[:consecutive]):
                continue

            # S promotion: simple consecutive check
            if target == "S":
                record["promoted"] = True
                record["new_grade"] = "S"
                record["reason"] = (
                    f"Achieved {consecutive}+ consecutive {required_grade} grades."
                )
                return (True, "S", record["reason"])

            # A promotion: 5+ consecutive B then 2 A
            then_grade = rule.get("then_grade")
            then_count = rule.get("then_count", 0)
            if then_grade:
                # After the consecutive Bs, we need `then_count` of `then_grade`
                remaining = grades[consecutive:]
                if len(remaining) < then_count:
                    continue
                if not all(g == then_grade for g in remaining[:then_count]):
                    continue
                record["promoted"] = True
                record["new_grade"] = "A"
                record["reason"] = (
                    f"Achieved {consecutive}+ consecutive {required_grade} grades "
                    f"followed by {then_count} {then_grade} grades."
                )
                return (True, "A", record["reason"])

        # No rule matched
        rank = self.grade_order.index(current) if current in self.grade_order else -1
        record["reason"] = (
            f"Current grade {current} does not meet any promotion criteria. "
            f"Next possible target: {self._next_grade(current)}."
        )
        return (False, current, record["reason"])

    # ═══════════════════════════════════════════════════════════════ #
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════ #

    @staticmethod
    def _normalise_history(history: list) -> list:
        """Convert a heterogeneous history list into a list of grade strings
        ordered most-recent-first (already presumed)."""
        grades = []
        for entry in history:
            if isinstance(entry, str):
                grades.append(entry.upper())
            elif isinstance(entry, dict):
                grades.append(entry.get("grade", "").upper())
            elif isinstance(entry, AgentScorecard):
                grades.append(entry.grade.upper())
        return grades

    def _next_grade(self, current: str) -> str:
        """Return the next grade above current, or 'S (max)' if top."""
        try:
            idx = self.grade_order.index(current)
        except ValueError:
            return "unknown"
        if idx >= len(self.grade_order) - 1:
            return "S (max)"
        return self.grade_order[idx + 1]

    def _build_record(
        self, agent_id: str, current_grade: str, grades: list
    ) -> dict:
        """Generate a promotion record dict (always captured)."""
        return {
            "agent_id": agent_id,
            "current_grade": current_grade,
            "grades_history": grades,
            "promoted": False,
            "new_grade": current_grade,
            "reason": "",
            "timestamp": datetime.utcnow().isoformat(),
        }
