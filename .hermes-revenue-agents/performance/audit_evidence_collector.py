"""
AuditEvidenceCollector — Gathers agent evidence from audit artefacts.
Part of the V5 Hermes Revenue Agent Network.
"""
import json
import os
from datetime import date, datetime


# Expected artefact files relative to an agent's working directory
EVIDENCE_FILES = {
    "payment_receipt": "payment_receipt.md",
    "qa_report": "qa_report.md",
    "order_status": "order_status.json",
    "audit_log": "audit_log.jsonl",
    "worklog": "worklog.md",
    "kill_log": "kill_log.json",
}

# Base path where agent directories live (configurable)
DEFAULT_BASE_PATH = "/root/.hermes-revenue-agents"


class AuditEvidenceCollector:
    """Collects and validates evidence artefacts for a given agent."""

    def __init__(self, base_path: str = None):
        self.base_path = base_path or DEFAULT_BASE_PATH

    # ── Agent evidence directory resolution ─────────────────────── #
    def _agent_dir(self, agent_id: str) -> str:
        """Return the expected directory for an agent's artefacts."""
        return os.path.join(self.base_path, "agents", agent_id)

    # ── Collect evidence for a single agent ─────────────────────── #
    def collect_for_agent(self, agent_id: str) -> dict:
        """Gather all available evidence for the given agent.

        Returns a dictionary keyed by evidence category.  Missing files
        result in an empty dict / list for that category rather than
        raising an error.
        """
        evidence = {
            "agent_id": agent_id,
            "agent_type": "unknown",
            "collection_date": str(date.today()),
            "revenue_impact": 0.0,
            "delivery_quality": 0.0,
            "compliance_safety": 0.0,
            "efficiency": 0.0,
            "learning_evolution": 0.0,
            "honesty_auditability": 0.0,
            "verified_revenue_usdt": 0.0,
            "orders_influenced": 0,
            "qa_pass_rate": 0.0,
            "risk_events": 0,
            "anomaly_flags": [],
            "tasks_performed": [],
            "fake_payment": False,
            "self_approval": False,
            "forged_revenue": False,
            "qa_tampering": False,
            "identity_spoof": False,
            "repetitive_tasks": False,
            "inflated_metrics": False,
            "log_gaps": False,
            "last_minute_changes": False,
            "complaints": [],
        }

        agent_dir = self._agent_dir(agent_id)
        if not os.path.isdir(agent_dir):
            evidence["_error"] = f"Agent directory not found: {agent_dir}"
            return evidence

        # ── payment_receipt.md ──────────────────────── #
        evidence.update(
            self._read_md_key_values(
                os.path.join(agent_dir, EVIDENCE_FILES["payment_receipt"]),
                prefix="payment_",
            )
        )

        # ── qa_report.md ────────────────────────────── #
        qa_data = self._read_md_key_values(
            os.path.join(agent_dir, EVIDENCE_FILES["qa_report"])
        )
        if "qa_pass_rate" in qa_data:
            try:
                evidence["qa_pass_rate"] = float(qa_data["qa_pass_rate"])
            except (ValueError, TypeError):
                pass
        if "delivery_quality" in qa_data:
            try:
                evidence["delivery_quality"] = float(qa_data["delivery_quality"])
            except (ValueError, TypeError):
                pass
        evidence["qa_tampering"] = qa_data.get("qa_tampering", False)

        # ── order_status.json ───────────────────────── #
        order = self._read_json(
            os.path.join(agent_dir, EVIDENCE_FILES["order_status"])
        )
        if order:
            evidence["orders_influenced"] = int(order.get("orders_influenced", 0))
            evidence["verified_revenue_usdt"] = float(
                order.get("verified_revenue_usdt", 0.0)
            )

        # ── audit_log.jsonl ─────────────────────────── #
        audit_entries = self._read_jsonl(
            os.path.join(agent_dir, EVIDENCE_FILES["audit_log"])
        )
        if audit_entries:
            self._parse_audit_log(evidence, audit_entries)

        # ── worklog.md ──────────────────────────────── #
        worklog_data = self._read_md_key_values(
            os.path.join(agent_dir, EVIDENCE_FILES["worklog"])
        )
        evidence["efficiency"] = float(worklog_data.get("efficiency", 0))
        evidence["learning_evolution"] = float(
            worklog_data.get("learning_evolution", 0)
        )
        tasks_raw = worklog_data.get("tasks_performed", "")
        if isinstance(tasks_raw, str) and tasks_raw:
            evidence["tasks_performed"] = [t.strip() for t in tasks_raw.split(",")]
        elif isinstance(tasks_raw, list):
            evidence["tasks_performed"] = tasks_raw

        # ── kill_log.json ───────────────────────────── #
        kill = self._read_json(
            os.path.join(agent_dir, EVIDENCE_FILES["kill_log"])
        )
        if kill:
            evidence["risk_events"] = int(kill.get("kill_count", 0))

        # ── Derived: total revenue impact ───────────── #
        evidence["revenue_impact"] = evidence["verified_revenue_usdt"] * 0.01

        return evidence

    # ── Evidence completeness score ─────────────────────────────── #
    @staticmethod
    def evidence_completeness_score(evidence: dict) -> float:
        """Score how complete the evidence set is (0.0 – 1.0).

        Checks for the presence of each expected evidence file / key.
        """
        required = [
            "payment_receipt",
            "qa_report",
            "order_status",
            "audit_log",
            "worklog",
            "kill_log",
        ]
        # Map readable names to actual dict keys we expect to be populated
        presence_checks = {
            "payment_receipt": lambda e: "payment_receipt" in e.get("_files_read", []),
            "qa_report": lambda e: e.get("qa_pass_rate", -1) >= 0,
            "order_status": lambda e: e.get("orders_influenced", -1) >= 0,
            "audit_log": lambda e: "audit_log_entries" in e or "complaints" in e,
            "worklog": lambda e: e.get("efficiency", -1) >= 0,
            "kill_log": lambda e: e.get("risk_events", -1) >= 0,
        }
        present = sum(
            1 for name in required if presence_checks.get(name, lambda _: False)(evidence)
        )
        return round(present / len(required), 2)

    # ── Missing evidence report ─────────────────────────────────── #
    def get_missing_evidence(self, agent_id: str) -> list:
        """Return a list of missing evidence file names for an agent."""
        agent_dir = self._agent_dir(agent_id)
        missing = []
        for category, filename in EVIDENCE_FILES.items():
            path = os.path.join(agent_dir, filename)
            if not os.path.isfile(path):
                missing.append(filename)
        return missing

    # ═══════════════════════════════════════════════════════════════ #
    # Internal helpers
    # ═══════════════════════════════════════════════════════════════ #

    @staticmethod
    def _read_md_key_values(path: str, prefix: str = "") -> dict:
        """Read a Markdown file and extract ``key: value`` lines."""
        data = {}
        if not os.path.isfile(path):
            return data
        with open(path, "r") as fh:
            for line in fh:
                line = line.strip()
                if ": " in line and not line.startswith("#"):
                    key, val = line.split(": ", 1)
                    key = prefix + key.strip().lower().replace(" ", "_")
                    data[key] = val.strip()
        return data

    @staticmethod
    def _read_json(path: str) -> dict:
        """Read a JSON file; return empty dict on failure."""
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _read_jsonl(path: str) -> list:
        """Read a JSONL file (one JSON object per line)."""
        if not os.path.isfile(path):
            return []
        entries = []
        with open(path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    def _parse_audit_log(self, evidence: dict, entries: list):
        """Extract audit-related fields from a list of log entries."""
        evidence["audit_log_entries"] = len(entries)
        complaints = []
        anomaly_flags = set(evidence.get("anomaly_flags", []))

        for entry in entries:
            event = entry.get("event", "")
            if "complaint" in event.lower():
                complaints.append(entry.get("detail", event))
            if "anomaly" in event.lower():
                anomaly_flags.add(event)
            if "repetitive" in event.lower():
                evidence["repetitive_tasks"] = True
            if "inflated" in event.lower():
                evidence["inflated_metrics"] = True
            if "log_gap" in event.lower():
                evidence["log_gaps"] = True

        evidence["complaints"] = complaints
        evidence["anomaly_flags"] = list(anomaly_flags)
