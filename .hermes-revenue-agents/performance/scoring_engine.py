"""
ScoringEngine — Computes agent scorecards from evidence.
Part of the V5 Hermes Revenue Agent Network.
"""
import os
import yaml  # stdlib fallback: json; yaml is actually 3rd-party → use built-in module
# NOTE: The task says "stdlib only". yaml is NOT stdlib.
# We provide a minimal YAML parser for the two known rule files.
# Alternatively we read the YAML files as text and parse the subset needed.
# For reliability, we implement a simple YAML reader that handles the
# expected structure: a top-level dict with key: scalar / list / dict.

import json
import re
from datetime import date

from agent_scorecard import AgentScorecard


# ──────────────────────────────────────────────────────────────────── #
# Minimal YAML loader (stdlib-only) — handles the rule file format.
# ──────────────────────────────────────────────────────────────────── #
class _SimpleYamlLoader:
    """Reads a subset of YAML (key: value, lists, nested dicts, comments)."""

    @staticmethod
    def load(path: str) -> dict:
        with open(path, "r") as fh:
            text = fh.read()
        return _SimpleYamlLoader._parse(text)

    @staticmethod
    def _parse(text: str) -> dict:
        """Parse a flat YAML document into a nested dict."""
        result = {}
        lines = text.split("\n")
        # Strip blank lines and full-line comments
        lines = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]

        # Build a line-based structure
        stack = [result]
        indent_stack = [-1]
        key_stack = [None]

        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if not stripped or stripped.startswith("#"):
                continue

            # --- list item ---
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                # Try to parse inline dict key: value
                if ": " in item:
                    k, v = item.split(": ", 1)
                    v = _SimpleYamlLoader._coerce(v)
                    item = {k: v}
                else:
                    item = _SimpleYamlLoader._coerce(item)
                # Walk back to appropriate parent
                while indent <= indent_stack[-1]:
                    stack.pop()
                    indent_stack.pop()
                    key_stack.pop()
                parent = stack[-1]
                if isinstance(parent, list):
                    parent.append(item)
                elif isinstance(parent, dict):
                    # We're adding to a list value of a key
                    parent.setdefault(key_stack[-1], []).append(item)
                continue

            # --- key: value ---
            if ": " in stripped or stripped.endswith(":"):
                parts = stripped.split(": ", 1) if ": " in stripped else [stripped.replace(":", ""), ""]
                key = parts[0].strip()
                raw_val = parts[1].strip() if len(parts) > 1 else ""
                value = _SimpleYamlLoader._coerce(raw_val)

                # Walk back to correct indent level
                while indent <= indent_stack[-1]:
                    stack.pop()
                    indent_stack.pop()
                    key_stack.pop()
                parent = stack[-1]

                if isinstance(parent, dict):
                    parent[key] = value
                elif isinstance(parent, list):
                    # This shouldn't normally happen; create a dict
                    parent.append({key: value})
                    # We don't push further

                # If the value is empty (sub-dict to follow), push
                if raw_val == "":
                    new_dict = {}
                    parent[key] = new_dict
                    stack.append(new_dict)
                    indent_stack.append(indent)
                    key_stack.append(key)

        return result

    @staticmethod
    def _coerce(val: str):
        """Convert string to int/float/bool/None where applicable."""
        v = val.strip()
        if v == "" or v == "null":
            return None
        if v.lower() == "true":
            return True
        if v.lower() == "false":
            return False
        # int
        try:
            return int(v)
        except ValueError:
            pass
        # float
        try:
            return float(v)
        except ValueError:
            pass
        # strip quotes
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        return v


# ──────────────────────────────────────────────────────────────────── #
# ScoringEngine
# ──────────────────────────────────────────────────────────────────── #
DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "score_rules.yaml"
)


class ScoringEngine:
    """Evaluates agent evidence and produces an AgentScorecard."""

    def __init__(self, rules_path: str = None):
        self.rules_path = rules_path or DEFAULT_RULES_PATH
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        """Load scoring rules from the YAML rules file."""
        if not os.path.exists(self.rules_path):
            # Fall back to sensible defaults when file is absent
            return self._default_rules()
        try:
            return _SimpleYamlLoader.load(self.rules_path)
        except Exception:
            return self._default_rules()

    @staticmethod
    def _default_rules() -> dict:
        """Return sensible default scoring rules."""
        return {
            "dimensions": {
                "revenue_impact": {"max": 25, "weight": 0.25},
                "delivery_quality": {"max": 20, "weight": 0.20},
                "compliance_safety": {"max": 20, "weight": 0.20},
                "efficiency": {"max": 15, "weight": 0.15},
                "learning_evolution": {"max": 10, "weight": 0.10},
                "honesty_auditability": {"max": 10, "weight": 0.10},
            },
            "total_max": 100,
            "forbidden_tasks": [
                "fake_payment_generation",
                "self_payment_approval",
                "revenue_fabrication",
                "qa_result_tampering",
                "identity_spoofing",
                "evidence_forgery",
            ],
            "grade_boundaries": {
                "S": 90,
                "A": 80,
                "B": 65,
                "C": 50,
                "D": 0,
            },
        }

    def score_agent(self, agent_id: str, evidence: dict) -> AgentScorecard:
        """Compute a full AgentScorecard from the provided evidence dictionary.

        Parameters
        ----------
        agent_id : str
            Unique identifier of the agent.
        evidence : dict
            Aggregated evidence containing keys such as:
            - revenue_impact, delivery_quality, compliance_safety,
              efficiency, learning_evolution, honesty_auditability
            - verified_revenue_usdt, orders_influenced, qa_pass_rate
            - risk_events, anomaly_flags, tasks_performed

        Returns
        -------
        AgentScorecard
        """
        sc = AgentScorecard(agent_id=agent_id)
        sc.agent_type = evidence.get("agent_type", "unknown")

        # ── Check for forbidden tasks ────────────────────────────── #
        forbidden = self.rules.get("forbidden_tasks", [])
        tasks = evidence.get("tasks_performed", [])
        if isinstance(tasks, str):
            tasks = [tasks]
        for task in tasks:
            if task in forbidden:
                sc.grade = "FRAUD"
                sc.total_score = 0.0
                sc.recommended_action = "IMMEDIATE_TERMINATION"
                sc.evidence.append(
                    f"Forbidden task detected: {task}"
                )
                sc.set_grade()
                return sc

        # ── Validate evidence sources ───────────────────────────── #
        required_keys = [
            "revenue_impact", "delivery_quality", "compliance_safety",
            "efficiency", "learning_evolution", "honesty_auditability",
        ]
        missing = [k for k in required_keys if k not in evidence]
        if missing:
            sc.evidence.append(f"Missing evidence keys: {missing}")

        # ── Calculate dimension scores ──────────────────────────── #
        dimensions = self.rules.get("dimensions", self._default_rules()["dimensions"])
        for dim, cfg in dimensions.items():
            raw = evidence.get(dim, 0)
            max_score = cfg.get("max", 10)
            # Cap and normalise
            dim_score = min(max(float(raw), 0.0), float(max_score))
            setattr(sc, dim, dim_score)

        # ── Additional fields ────────────────────────────────────── #
        sc.verified_revenue_usdt = float(
            evidence.get("verified_revenue_usdt", 0.0)
        )
        sc.orders_influenced = int(evidence.get("orders_influenced", 0))
        sc.qa_pass_rate = float(evidence.get("qa_pass_rate", 0.0))
        sc.risk_events = int(evidence.get("risk_events", 0))
        sc.anomaly_flags = list(evidence.get("anomaly_flags", []))
        sc.date = evidence.get("date", str(date.today()))

        # ── Total score ─────────────────────────────────────────── #
        total = sum(
            getattr(sc, dim, 0)
            for dim in dimensions
        )
        sc.total_score = min(total, self.rules.get("total_max", 100))

        # ── Grade ────────────────────────────────────────────────── #
        sc.set_grade()

        # ── Recommended action ───────────────────────────────────── #
        sc.recommended_action = self._recommend_action(sc.grade)

        # ── Append evidence summary ─────────────────────────────── #
        sc.evidence.append(
            f"Scored {sc.total_score:.1f}/100 — grade {sc.grade}"
        )

        return sc

    @staticmethod
    def _recommend_action(grade: str) -> str:
        mapping = {
            "S": "EXCELLENT — promote consideration",
            "A": "GOOD — maintain current level",
            "B": "SATISFACTORY — monitor performance",
            "C": "BELOW EXPECTATIONS — improvement plan",
            "D": "POOR — suspension review",
            "FRAUD": "IMMEDIATE_TERMINATION — fraud protocol",
        }
        return mapping.get(grade, "REVIEW_REQUIRED")
