#!/usr/bin/env python3
"""
Master Controller — V5 Revenue Agent Network
任务分发、Agent 管理、配额、熔断、审计
"""
import json
import uuid
import re
from datetime import datetime
from pathlib import Path

BASE = Path("/root/.hermes-revenue-agents")
AGENT_SPEC_FILE = BASE / "master" / "agent_specs.json"
STATE_FILE = BASE / "master" / "state.json"
AUDIT_LOG = BASE / "master" / "audit.jsonl"
KILL_LOG = BASE / "master" / "kill_log.json"


class AgentSpec:
    """子代理规范"""
    def __init__(self, spec: dict):
        self.agent_id = spec.get("agent_id", "")
        self.agent_type = spec.get("agent_type", "")
        self.platform = spec.get("platform", "local")
        self.allowed_tasks = spec.get("allowed_tasks", [])
        self.forbidden_tasks = spec.get("forbidden_tasks", [])
        self.max_runs_per_day = spec.get("max_runs_per_day", 10)
        self.max_runtime_minutes = spec.get("max_runtime_minutes", 30)
        self.max_network_requests = spec.get("max_network_requests", 100)
        self.secrets_scope = spec.get("secrets_scope", "public_only")
        self.wallet_access = spec.get("wallet_access", "public_address_only")
        self.can_modify_wallet_address = spec.get("can_modify_wallet_address", False)
        self.can_create_child_agent = spec.get("can_create_child_agent", False)
        self.can_publish_external = spec.get("can_publish_external_content", False)
        self.requires_qa = spec.get("requires_qa", True)
        self.kill_switch_enabled = spec.get("kill_switch_enabled", True)
        self.status = spec.get("status", "idle")  # idle/running/error/killed
        self.created_at = spec.get("created_at", datetime.now().isoformat())
        self.last_heartbeat = spec.get("last_heartbeat", datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class MasterController:
    """主控制器 — 管理所有子代理"""
    
    def __init__(self):
        self.agents = {}
        self.state = self._load_state()
        self._load_agents()
    
    def _load_state(self) -> dict:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {"task_queue": [], "completed_tasks": [], "kill_list": []}
    
    def _save_state(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2))
    
    def _load_agents(self):
        """加载 Agent 规范"""
        if AGENT_SPEC_FILE.exists():
            specs = json.loads(AGENT_SPEC_FILE.read_text())
            for spec in specs:
                agent = AgentSpec(spec)
                self.agents[agent.agent_id] = agent
    
    def register_agent(self, spec: dict) -> str:
        """注册新子代理"""
        agent = AgentSpec(spec)
        
        # 安全底线：禁止创建子代理的子代理
        if spec.get("can_create_child_agent", False) and spec.get("agent_type") != "master":
            return {"error": "只有 Master Controller 可以创建子代理"}
        
        # 安全底线：禁止子代理修改钱包
        if spec.get("can_modify_wallet_address", False) and spec.get("agent_type") != "master":
            return {"error": "只有 Master Controller 可以修改钱包地址"}
        
        self.agents[agent.agent_id] = agent
        self._save_agent_specs()
        self._audit("agent_registered", agent.agent_id)
        return {"success": True, "agent_id": agent.agent_id}
    
    def _save_agent_specs(self):
        specs = [a.to_dict() for a in self.agents.values()]
        AGENT_SPEC_FILE.write_text(json.dumps(specs, indent=2))
    
    def dispatch(self, task_id: str, agent_id: str, priority: int = 2) -> dict:
        """分发任务"""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found"}
        
        # Kill switch check
        if agent_id in self.state.get("kill_list", []):
            return {"error": f"Agent {agent_id} is killed"}
        
        # Task whitelist check
        if task_id not in agent.allowed_tasks:
            return {"error": f"Task {task_id} not in allowed tasks for {agent_id}"}
        
        # Enqueue
        task = {
            "task_id": task_id,
            "agent_id": agent_id,
            "priority": priority,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
        }
        self.state["task_queue"].append(task)
        self._save_state()
        self._audit("task_dispatched", f"{task_id} -> {agent_id}")
        return {"success": True, "task": task}
    
    def complete_task(self, task_id: str, agent_id: str, result: dict):
        """完成任务"""
        self.state["task_queue"] = [t for t in self.state["task_queue"] 
                                     if not (t["task_id"] == task_id and t["agent_id"] == agent_id)]
        self.state["completed_tasks"].append({
            "task_id": task_id,
            "agent_id": agent_id,
            "result": result,
            "completed_at": datetime.now().isoformat(),
        })
        self._save_state()
        self._audit("task_completed", f"{task_id} by {agent_id}")
    
    def kill_agent(self, agent_id: str, reason: str = ""):
        """熔断 — 停止子代理"""
        if agent_id not in self.state["kill_list"]:
            self.state["kill_list"].append(agent_id)
        if agent_id in self.agents:
            self.agents[agent_id].status = "killed"
        self._save_state()
        self._save_agent_specs()
        self._audit("agent_killed", f"{agent_id}: {reason}")
        
        # 记录 kill 日志
        KILL_LOG.parent.mkdir(parents=True, exist_ok=True)
        kills = []
        if KILL_LOG.exists():
            kills = json.loads(KILL_LOG.read_text())
        kills.append({
            "agent_id": agent_id,
            "reason": reason,
            "killed_at": datetime.now().isoformat(),
        })
        KILL_LOG.write_text(json.dumps(kills, indent=2))
    
    def resume_agent(self, agent_id: str):
        """恢复子代理"""
        self.state["kill_list"] = [k for k in self.state["kill_list"] if k != agent_id]
        if agent_id in self.agents:
            self.agents[agent_id].status = "idle"
        self._save_state()
        self._save_agent_specs()
        self._audit("agent_resumed", agent_id)
    
    def is_killed(self, agent_id: str) -> bool:
        return agent_id in self.state.get("kill_list", [])
    
    def _audit(self, event: str, detail: str):
        """审计日志"""
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "event": event,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def get_status(self) -> dict:
        """系统状态"""
        return {
            "agents": {k: {"status": v.status} for k, v in self.agents.items()},
            "queue_size": len(self.state["task_queue"]),
            "completed": len(self.state["completed_tasks"]),
            "killed_agents": self.state["kill_list"],
        }


# 子代理工厂
def create_default_agents() -> list[dict]:
    """创建所有标准子代理"""
    return [
        {
            "agent_id": "opportunity_agent",
            "agent_type": "opportunity",
            "platform": "local",
            "allowed_tasks": [
                "scan_github_trends", "scan_pypi_trends", "scan_hn_trends",
                "analyze_dev_pain_points", "generate_opportunity_report",
            ],
            "forbidden_tasks": ["scrape_private_data", "bypass_rate_limits", "create_accounts"],
            "max_runs_per_day": 3,
            "max_runtime_minutes": 15,
            "max_network_requests": 50,
            "secrets_scope": "public_read_only",
            "wallet_access": "none",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": False,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "content_agent",
            "agent_type": "content",
            "platform": "local",
            "allowed_tasks": [
                "draft_twitter_post", "draft_reddit_post", "draft_devto_article",
                "draft_release_notes", "draft_tutorial", "update_readme",
            ],
            "forbidden_tasks": [
                "auto_publish_to_third_party", "create_fake_reviews", "spam_platforms",
                "impersonate_users", "star_farming",
            ],
            "max_runs_per_day": 5,
            "max_runtime_minutes": 20,
            "max_network_requests": 30,
            "secrets_scope": "public_read_only",
            "wallet_access": "none",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": True,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "risk_agent",
            "agent_type": "risk",
            "platform": "local",
            "allowed_tasks": [
                "check_order_risk", "reject_illegal_order", "flag_high_risk_order",
                "request_clarification", "generate_rejection_reason",
            ],
            "forbidden_tasks": [
                "approve_illegal_order", "bypass_risk_check", "modify_rejection_rules",
            ],
            "max_runs_per_day": 100,
            "max_runtime_minutes": 5,
            "max_network_requests": 10,
            "secrets_scope": "public_read_only",
            "wallet_access": "none",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": False,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "quote_agent",
            "agent_type": "quote",
            "platform": "local",
            "allowed_tasks": [
                "generate_quote", "create_invoice", "validate_service_tier",
                "calculate_complexity", "generate_unique_amount",
            ],
            "forbidden_tasks": [
                "modify_prices_outside_rules", "waive_payment", "create_fake_invoice",
            ],
            "max_runs_per_day": 50,
            "max_runtime_minutes": 5,
            "max_network_requests": 5,
            "secrets_scope": "public_read_only",
            "wallet_access": "public_address_only",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": False,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "payment_agent",
            "agent_type": "payment",
            "platform": "local",
            "allowed_tasks": [
                "verify_usdt_transaction", "check_tx_hash", "validate_payment_amount",
                "check_duplicate_tx", "generate_payment_receipt",
            ],
            "forbidden_tasks": [
                "modify_wallet_address", "access_private_key", "fake_payment_confirmation",
                "bypass_payment_verification", "create_fake_receipt",
            ],
            "max_runs_per_day": 100,
            "max_runtime_minutes": 10,
            "max_network_requests": 30,
            "secrets_scope": "public_read_only",
            "wallet_access": "public_address_only",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": False,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "delivery_agent",
            "agent_type": "delivery",
            "platform": "local",
            "allowed_tasks": [
                "create_workspace", "fetch_repo", "generate_deliverables",
                "run_qa", "auto_fix", "package_delivery",
            ],
            "forbidden_tasks": [
                "modify_wallet_address", "access_private_key", "mark_failed_as_success",
                "deliver_outside_scope", "bypass_qa",
            ],
            "max_runs_per_day": 20,
            "max_runtime_minutes": 60,
            "max_network_requests": 100,
            "secrets_scope": "repo_write",
            "wallet_access": "none",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": True,
            "requires_qa": True,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "revenue_agent",
            "agent_type": "revenue",
            "platform": "local",
            "allowed_tasks": [
                "calculate_daily_revenue", "analyze_conversion", "suggest_price_changes",
                "identify_top_services", "generate_revenue_report",
            ],
            "forbidden_tasks": [
                "modify_prices_directly", "promise_guaranteed_returns",
                "make_financial_projections_without_disclaimer",
            ],
            "max_runs_per_day": 2,
            "max_runtime_minutes": 15,
            "max_network_requests": 20,
            "secrets_scope": "public_read_only",
            "wallet_access": "public_address_only",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": False,
            "kill_switch_enabled": True,
        },
        {
            "agent_id": "ip_protection_agent",
            "agent_type": "security",
            "platform": "local",
            "allowed_tasks": [
                "scan_for_ip_leaks", "check_dns_records", "check_readme_for_ip",
                "check_js_for_ip", "generate_ip_leak_report",
            ],
            "forbidden_tasks": [
                "set_up_open_proxy", "bypass_firewall", "scan_external_targets",
                "expose_origin_ip", "disable_security",
            ],
            "max_runs_per_day": 2,
            "max_runtime_minutes": 10,
            "max_network_requests": 20,
            "secrets_scope": "repo_write",
            "wallet_access": "none",
            "can_modify_wallet_address": False,
            "can_create_child_agent": False,
            "can_publish_external_content": False,
            "requires_qa": False,
            "kill_switch_enabled": True,
        },
    ]


if __name__ == "__main__":
    import sys
    mc = MasterController()
    
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        agents = create_default_agents()
        for a in agents:
            mc.register_agent(a)
        print(f"✅ 已注册 {len(agents)} 个子代理")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "status":
        status = mc.get_status()
        print(json.dumps(status, indent=2))
    
    elif len(sys.argv) > 2 and sys.argv[1] == "kill":
        mc.kill_agent(sys.argv[2], "manual")
        print(f"🔴 Agent {sys.argv[2]} 已停止")
    
    elif len(sys.argv) > 2 and sys.argv[1] == "resume":
        mc.resume_agent(sys.argv[2])
        print(f"🟢 Agent {sys.argv[2]} 已恢复")
    
    else:
        print("用法:")
        print("  python3 master_controller.py init     — 初始化所有子代理")
        print("  python3 master_controller.py status   — 查看系统状态")
        print("  python3 master_controller.py kill <id> — 熔断子代理")
        print("  python3 master_controller.py resume <id> — 恢复子代理")
