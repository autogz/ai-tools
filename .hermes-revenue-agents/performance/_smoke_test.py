#!/usr/bin/env python3
"""Quick smoke-test: import all modules and exercise key methods."""
import sys
sys.path.insert(0, "/root/.hermes-revenue-agents")

from performance.agent_scorecard import AgentScorecard
from performance.scoring_engine import ScoringEngine
from performance.anti_gaming_checker import AntiGamingChecker
from performance.audit_evidence_collector import AuditEvidenceCollector
from performance.incentive_engine import IncentiveEngine
from performance.promotion_engine import PromotionEngine
from performance.demotion_engine import DemotionEngine
from performance.anomaly_detector import AnomalyDetector
import json

print("=== All modules imported OK ===")

# 1. AgentScorecard
sc = AgentScorecard(agent_id="test-01", agent_type="content_agent")
sc.total_score = 86
sc.set_grade()
assert sc.grade == "A"
d = sc.to_dict()
sc2 = AgentScorecard.from_dict(d)
assert sc2.grade == "A"
json_str = sc.to_json()
parsed = json.loads(json_str)
assert parsed["grade"] == "A"
print("OK agent_scorecard: to_dict, from_dict, set_grade, to_json all passed")

# 2. ScoringEngine
engine = ScoringEngine(rules_path="/root/.hermes-revenue-agents/performance/../score_rules.yaml")
evidence = {
    "agent_type": "content_agent",
    "revenue_impact": 22.5,
    "delivery_quality": 18.0,
    "compliance_safety": 17.0,
    "efficiency": 13.5,
    "learning_evolution": 8.0,
    "honesty_auditability": 7.0,
    "verified_revenue_usdt": 2250.0,
    "orders_influenced": 47,
    "qa_pass_rate": 94.5,
    "risk_events": 1,
}
scored = engine.score_agent("test-01", evidence)
assert scored.total_score > 0
print(f"OK scoring_engine: scored grade={scored.grade} total={scored.total_score}")

# 3. AntiGamingChecker
checker = AntiGamingChecker(rules_path="/root/.hermes-revenue-agents/performance/../anti_gaming_rules.yaml")
results = checker.check_agent("test-01", {"fake_payment": True})
assert any(r[1] and r[2] == "critical" for r in results)
print(f"OK anti_gaming_checker: hard_gaming={checker.has_hard_gaming(results)}")

# 4. AuditEvidenceCollector
collector = AuditEvidenceCollector()
score = collector.evidence_completeness_score({})
assert 0.0 <= score <= 1.0
missing = collector.get_missing_evidence("nonexistent-agent")
print(f"OK audit_evidence_collector: completeness={score} missing={len(missing)}")

# 5. IncentiveEngine
inc = IncentiveEngine()
assert inc.calculate_quota_adjustment("S") == 1.5
assert inc.calculate_quota_adjustment("A") == 1.0
assert inc.calculate_quota_adjustment("B") == 0.5
assert inc.calculate_quota_adjustment("C") == 0.25
assert inc.calculate_quota_adjustment("D") == 0.0
assert inc.calculate_quota_adjustment("FRAUD") == 0.0
assert inc.get_task_priority("S") == "high"
assert inc.get_agent_level("A") == "A"
print("OK incentive_engine: quota, priority, level all correct")

# 6. PromotionEngine
prom = PromotionEngine()
hist = ["B"] * 5 + ["A"] * 2
promoted, new_grade, reason = prom.check_promotion("test-01", "B", hist)
assert promoted
assert new_grade == "A"
print(f"OK promotion_engine: promoted -> {new_grade}")

# 7. DemotionEngine
dem = DemotionEngine()
violations = [{"rule_id": "HG-001", "type": "hard_gaming", "date": "2026-05-30"}]
demoted, new_grade, reason = dem.check_demotion("test-01", "A", violations)
assert demoted
assert new_grade == "FRAUD"
print(f"OK demotion_engine: demoted -> {new_grade}")

# 8. AnomalyDetector
ad = AnomalyDetector()
activity = {
    "revenue_baseline": 100.0,
    "current_revenue": 500.0,
    "qa_pass_rate_baseline": 80.0,
    "current_qa_pass_rate": 95.0,
    "task_volume_baseline": 10,
    "current_task_volume": 60,
    "log_timestamps": ["2026-05-30T00:00:00", "2026-05-30T04:00:00"],
    "tx_hashes": ["0xabc"] * 3,
}
anomalies = ad.detect("test-01", activity)
print(f"OK anomaly_detector: {len(anomalies)} anomalies found")
for a in anomalies:
    print(f"    [{a['severity']}] {a['type']}")

# 9. Example JSON
with open("/root/.hermes-revenue-agents/performance/agent_scorecard_example.json") as f:
    example = json.load(f)
assert example["total_score"] == 86
assert example["grade"] == "A"
print("OK agent_scorecard_example.json: valid, score=86 grade=A")

print("\n=== ALL 9 TESTS PASSED ===")
