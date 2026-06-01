"""
AgentScorecard — Core data model for agent performance scoring.
Part of the V5 Hermes Revenue Agent Network.
"""
import json
from datetime import date


class AgentScorecard:
    """Represents a complete performance evaluation for an agent."""

    def __init__(
        self,
        agent_id: str = "",
        agent_type: str = "",
        score_date: str = None,
        total_score: float = 0.0,
        grade: str = "",
        revenue_impact: float = 0.0,
        delivery_quality: float = 0.0,
        compliance_safety: float = 0.0,
        efficiency: float = 0.0,
        learning_evolution: float = 0.0,
        honesty_auditability: float = 0.0,
        verified_revenue_usdt: float = 0.0,
        orders_influenced: int = 0,
        qa_pass_rate: float = 0.0,
        risk_events: int = 0,
        anomaly_flags: list = None,
        evidence: list = None,
        recommended_action: str = "",
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.date = score_date if score_date else str(date.today())
        self.total_score = total_score
        self.grade = grade
        self.revenue_impact = revenue_impact
        self.delivery_quality = delivery_quality
        self.compliance_safety = compliance_safety
        self.efficiency = efficiency
        self.learning_evolution = learning_evolution
        self.honesty_auditability = honesty_auditability
        self.verified_revenue_usdt = verified_revenue_usdt
        self.orders_influenced = orders_influenced
        self.qa_pass_rate = qa_pass_rate
        self.risk_events = risk_events
        self.anomaly_flags = anomaly_flags if anomaly_flags is not None else []
        self.evidence = evidence if evidence is not None else []
        self.recommended_action = recommended_action

    # ------------------------------------------------------------------ #
    # Grade boundaries (0–100 scale)
    # ------------------------------------------------------------------ #
    GRADE_BOUNDARIES = [
        (90, "S"),
        (80, "A"),
        (65, "B"),
        (50, "C"),
        (0,  "D"),
    ]

    def set_grade(self) -> str:
        """Calculate total score from dimensions and determine grade."""
        self.total_score = (
            self.revenue_impact +
            self.delivery_quality +
            self.compliance_safety +
            self.efficiency +
            self.learning_evolution +
            self.honesty_auditability
        )
        if self.total_score < 0 or self.grade == "FRAUD":
            self.grade = "FRAUD"
            return self.grade
        for threshold, letter in self.GRADE_BOUNDARIES:
            if self.total_score >= threshold:
                self.grade = letter
                return self.grade
        self.grade = "D"
        return self.grade

    def to_dict(self) -> dict:
        """Serialize the scorecard to a dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "date": self.date,
            "total_score": self.total_score,
            "grade": self.grade,
            "revenue_impact": self.revenue_impact,
            "delivery_quality": self.delivery_quality,
            "compliance_safety": self.compliance_safety,
            "efficiency": self.efficiency,
            "learning_evolution": self.learning_evolution,
            "honesty_auditability": self.honesty_auditability,
            "verified_revenue_usdt": self.verified_revenue_usdt,
            "orders_influenced": self.orders_influenced,
            "qa_pass_rate": self.qa_pass_rate,
            "risk_events": self.risk_events,
            "anomaly_flags": list(self.anomaly_flags),
            "evidence": list(self.evidence),
            "recommended_action": self.recommended_action,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentScorecard":
        """Reconstruct a scorecard from a dictionary."""
        return cls(
            agent_id=data.get("agent_id", ""),
            agent_type=data.get("agent_type", ""),
            score_date=data.get("date", str(date.today())),
            total_score=data.get("total_score", 0.0),
            grade=data.get("grade", ""),
            revenue_impact=data.get("revenue_impact", 0.0),
            delivery_quality=data.get("delivery_quality", 0.0),
            compliance_safety=data.get("compliance_safety", 0.0),
            efficiency=data.get("efficiency", 0.0),
            learning_evolution=data.get("learning_evolution", 0.0),
            honesty_auditability=data.get("honesty_auditability", 0.0),
            verified_revenue_usdt=data.get("verified_revenue_usdt", 0.0),
            orders_influenced=data.get("orders_influenced", 0),
            qa_pass_rate=data.get("qa_pass_rate", 0.0),
            risk_events=data.get("risk_events", 0),
            anomaly_flags=data.get("anomaly_flags", []),
            evidence=data.get("evidence", []),
            recommended_action=data.get("recommended_action", ""),
        )

    def to_json(self) -> str:
        """Serialize the scorecard to a JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    def __repr__(self) -> str:
        return (
            f"AgentScorecard(agent_id={self.agent_id!r}, "
            f"grade={self.grade!r}, total_score={self.total_score})"
        )
