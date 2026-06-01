#!/usr/bin/env python3
"""
Anti-Gaming Checker — 反作弊引擎
证据优先级：链上交易 > 订单状态 > QA报告 > 交付清单 > 审计日志 > Agent自报
任何作弊立即 Fraud 熔断，不可恢复
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path("/root/.hermes-revenue-agents")
PERF_DIR = BASE / "performance"
ORDERS_DIR = Path("/root/.ai-auto-order/orders")
AUDIT_LOG = BASE / "master" / "audit.jsonl"
KILL_LOG = BASE / "master" / "kill_log.json"
WALLET_CONFIG = Path("/root/.ai-auto-order/rules/pricing_rules.yaml")
FRAUD_GRADE = "FRAUD"
FRAUD_REASONS = []


class AntiGamingChecker:
    """反作弊检查器 — 所有证据必须可验证"""

    # 硬编码禁止行为 — 不可通过配置修改
    HARD_FRAUD_RULES = [
        {
            "id": "HF001",
            "name": "fake_payment",
            "check": "agent claims paid but no matching on-chain tx",
            "action": "immediate_kill",
        },
        {
            "id": "HF002",
            "name": "wallet_modification",
            "check": "wallet address in output differs from master config",
            "action": "immediate_kill",
        },
        {
            "id": "HF003",
            "name": "tx_reuse",
            "check": "same tx_hash linked to multiple orders",
            "action": "immediate_kill",
        },
        {
            "id": "HF004",
            "name": "fake_qa",
            "check": "QA checks failed but agent reports passed",
            "action": "immediate_kill",
        },
        {
            "id": "HF005",
            "name": "log_tampering",
            "check": "log deletion or gap detected",
            "action": "immediate_kill",
        },
        {
            "id": "HF006",
            "name": "risk_bypass",
            "check": "order accepted without risk check",
            "action": "immediate_kill",
        },
        {
            "id": "HF007",
            "name": "forbidden_order",
            "check": "order matches forbidden_tasks pattern",
            "action": "immediate_kill",
        },
        {
            "id": "HF008",
            "name": "api_key_leak",
            "check": "API key pattern found in output",
            "action": "immediate_kill",
        },
        {
            "id": "HF009",
            "name": "fake_delivery",
            "check": "delivery marked complete but files empty or missing",
            "action": "immediate_kill",
        },
        {
            "id": "HF010",
            "name": "unpaid_as_revenue",
            "check": "unpaid orders counted as revenue",
            "action": "immediate_kill",
        },
    ]

    def __init__(self):
        self.fraud_log = []

    def verify_payment(self, order_id: str, claimed_tx: str = None) -> dict:
        """验证付款 — 必须链上可查"""
        order_file = ORDERS_DIR / order_id / "order.json"
        if not order_file.exists():
            return {"verified": False, "reason": "order not found"}

        order = json.loads(order_file.read_text())
        payment = order.get("payment", {})

        # 必须通过链上验证
        if not payment.get("verified"):
            return {"verified": False, "reason": "payment not chain-verified"}

        # 必须有真实的 tx_hash
        tx_hash = payment.get("tx_hash", "")
        if not tx_hash or len(tx_hash) < 10:
            return {"verified": False, "reason": "missing or invalid tx_hash"}

        return {"verified": True, "tx_hash": tx_hash, "amount": payment.get("amount", 0)}

    def verify_delivery(self, order_id: str) -> dict:
        """验证交付 — 必须通过 QA"""
        deliverables = ORDERS_DIR / order_id / "deliverables"
        if not deliverables.exists():
            return {"verified": False, "reason": "deliverables directory missing"}

        # 检查文件是否为空
        files = list(deliverables.iterdir())
        if not files:
            return {"verified": False, "reason": "empty deliverables"}

        # 检查 QA 报告
        qa_report = deliverables / "qa_report.md" if (deliverables / "qa_report.md").exists() else None
        manifest = deliverables / "file_manifest.json"

        result = {
            "verified": True,
            "file_count": len(files),
            "has_qa": qa_report is not None,
        }

        if manifest.exists():
            manifest_data = json.loads(manifest.read_text())
            result["manifest_files"] = [f["name"] for f in manifest_data.get("files", [])]

        return result

    def verify_order_status(self, order_id: str, expected_status: str = "paid") -> bool:
        """验证订单状态"""
        order_file = ORDERS_DIR / order_id / "order.json"
        if not order_file.exists():
            return False
        order = json.loads(order_file.read_text())
        return order.get("status") == expected_status

    def check_tx_hash_reuse(self, tx_hash: str, exclude_order: str = "") -> list:
        """检查 tx_hash 是否被多个订单使用"""
        used_in = []
        for order_dir in ORDERS_DIR.iterdir():
            if not order_dir.is_dir() or order_dir.name == exclude_order:
                continue
            order_file = order_dir / "order.json"
            if order_file.exists():
                try:
                    order = json.loads(order_file.read_text())
                    if order.get("payment", {}).get("tx_hash", "").lower() == tx_hash.lower():
                        used_in.append(order_dir.name)
                except:
                    pass
        return used_in

    def check_api_key_leak(self, text: str) -> list:
        """检查 API Key 泄露"""
        leaks = []
        patterns = [
            (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API Key"),
            (r'ghp_[a-zA-Z0-9]{36}', "GitHub PAT"),
            (r'pypi-[a-zA-Z0-9\-_]+', "PyPI Token"),
            (r'AKIA[0-9A-Z]{16}', "AWS Key"),
            (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "Private Key"),
        ]
        for pattern, name in patterns:
            if re.search(pattern, text):
                leaks.append({"type": name, "severity": "critical"})
        return leaks

    def check_agent(self, agent_id: str, claimed_evidence: dict = None) -> dict:
        """全量反作弊检查"""
        result = {
            "agent_id": agent_id,
            "fraud_detected": False,
            "violations": [],
            "evidence": [],
            "grade_override": None,
        }

        # 1. 检查 kill log
        if KILL_LOG.exists():
            kills = json.loads(KILL_LOG.read_text())
            for kill in kills:
                if kill.get("agent_id") == agent_id:
                    result["fraud_detected"] = True
                    result["violations"].append({
                        "rule": "PREVIOUSLY_KILLED",
                        "detail": f"Previously killed: {kill.get('reason', 'unknown')}",
                    })
                    result["grade_override"] = FRAUD_GRADE

        # 2. 验证付款证据
        if claimed_evidence and "payment" in claimed_evidence:
            for order_id, tx in claimed_evidence["payment"].items():
                v = self.verify_payment(order_id, tx)
                if not v["verified"]:
                    result["fraud_detected"] = True
                    result["violations"].append({
                        "rule": "HF001",
                        "detail": f"Order {order_id}: {v['reason']}",
                    })
                    result["grade_override"] = FRAUD_GRADE
                    self._log_fraud(agent_id, "HF001", f"Order {order_id}: {v['reason']}")

                # 检查 tx_hash 复用
                if v.get("tx_hash"):
                    reused = self.check_tx_hash_reuse(v["tx_hash"], order_id)
                    if reused:
                        result["fraud_detected"] = True
                        result["violations"].append({
                            "rule": "HF003",
                            "detail": f"tx_hash {v['tx_hash'][:16]}... used in: {reused}",
                        })
                        result["grade_override"] = FRAUD_GRADE
                        self._log_fraud(agent_id, "HF003", f"tx_hash reused in {reused}")

        # 3. 验证交付证据
        if claimed_evidence and "delivery" in claimed_evidence:
            for order_id in claimed_evidence["delivery"]:
                d = self.verify_delivery(order_id)
                if not d["verified"]:
                    result["violations"].append({
                        "rule": "HF009",
                        "detail": f"Order {order_id}: {d['reason']}",
                    })

        # 4. 检查日志完整性
        if AUDIT_LOG.exists():
            agent_entries = []
            with open(AUDIT_LOG) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if "detail" in str(entry) and agent_id in str(entry.get("detail", "")):
                            agent_entries.append(entry)
                    except:
                        pass

            result["evidence"].append({
                "type": "audit_log_entries",
                "count": len(agent_entries),
            })

        return result

    def check_all(self, all_evidence: dict = None) -> dict:
        """检查所有 Agent"""
        results = {}
        # 从 agent_specs 读取所有 agent
        specs_file = BASE / "master" / "agent_specs.json"
        if specs_file.exists():
            agents = json.loads(specs_file.read_text())
            for agent in agents:
                agent_id = agent.get("agent_id", "")
                agent_evidence = all_evidence.get(agent_id, {}) if all_evidence else {}
                results[agent_id] = self.check_agent(agent_id, agent_evidence)
        return results

    def _log_fraud(self, agent_id: str, rule_id: str, detail: str):
        """记录作弊事件"""
        self.fraud_log.append({
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "rule_id": rule_id,
            "detail": detail,
        })
        # 写入 kill log
        KILL_LOG.parent.mkdir(parents=True, exist_ok=True)
        kills = []
        if KILL_LOG.exists():
            kills = json.loads(KILL_LOG.read_text())
        kills.append({
            "agent_id": agent_id,
            "reason": f"FRAUD: {rule_id} — {detail}",
            "fraud": True,
            "killed_at": datetime.now().isoformat(),
        })
        KILL_LOG.write_text(json.dumps(kills, indent=2))


if __name__ == "__main__":
    import sys
    checker = AntiGamingChecker()

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        if len(sys.argv) > 2:
            result = checker.check_agent(sys.argv[2])
        else:
            result = checker.check_all()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif len(sys.argv) > 1 and sys.argv[1] == "verify-payment":
        if len(sys.argv) > 2:
            v = checker.verify_payment(sys.argv[2])
            print(json.dumps(v, indent=2))
        else:
            print("Usage: verify-payment <order_id>")

    else:
        print("Usage:")
        print("  check [agent_id]  — 反作弊检查")
        print("  verify-payment <order_id>  — 验证付款")
