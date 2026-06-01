#!/usr/bin/env python3
"""
Order Engine — 全自动订单管理
解析需求 -> 风险检测 -> 报价 -> 付款验证 -> 执行 -> QA -> 交付
"""
import json
import uuid
import re
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path("/root/.ai-auto-order")
ORDERS_DIR = BASE / "orders"
RULES_DIR = BASE / "rules"

# 订单状态枚举
ORDER_STATUS = [
    "draft",              # 草稿
    "clarification",      # 等待客户补充
    "quoted",             # 已报价
    "awaiting_payment",   # 等待付款
    "paid",               # 已付款
    "underpaid",          # 金额不足
    "overpaid",           # 金额多付
    "expired",            # 订单过期
    "in_progress",        # 执行中
    "qa_check",           # 质量检查中
    "fixing",             # 自动修复中
    "delivered",          # 已交付
    "failed",             # 执行失败
    "rejected",           # 已拒绝
    "refund_manual",      # 需人工退款
]


class OrderEngine:
    """全自动订单引擎"""
    
    def __init__(self):
        self.rejection_rules = self._load_yaml(RULES_DIR / "rejection_rules.yaml")
        self.pricing_rules = self._load_yaml(RULES_DIR / "pricing_rules.yaml")
        self.acceptance_rules = self._load_yaml(RULES_DIR / "acceptance_rules.yaml")
    
    def _load_yaml(self, path):
        """简易 YAML 加载"""
        if not path.exists():
            return {}
        content = path.read_text()
        result = {}
        # 简单解析顶层结构
        for line in content.split("\n"):
            m = re.match(r'^(\w+):\s*(.*)', line)
            if m:
                result[m.group(1)] = m.group(2).strip('"')
        return result
    
    def create_order(self, request_text: str, contact: str = "") -> dict:
        """创建新订单"""
        order_id = "ORD-" + datetime.now().strftime("%Y%m%d") + "-" + str(uuid.uuid4())[:6].upper()
        
        order = {
            "order_id": order_id,
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "request": request_text,
            "contact": contact,
            "service": None,
            "tier": None,
            "risk_level": "unknown",
            "clarity_score": 0.0,
            "deliverability_score": 0.0,
            "invoice": None,
            "payment": None,
            "delivery": None,
            "messages": [],
            "fix_attempts": 0,
        }
        
        self._save_order(order)
        return order
    
    def classify_request(self, request_text: str) -> dict:
        """分类需求 -> 匹配服务类型"""
        text_lower = request_text.lower()
        
        # 服务类型检测
        services = {
            "github_polish": ["readme", "github", "仓库", "美化", "文档", "license", "contributing"],
            "pypi_release": ["pypi", "pip", "发布", "python包", "package", "build", "twine"],
            "cli_tool": ["cli", "命令行", "command line", "tool", "工具", "terminal"],
            "automation_script": ["自动化", "script", "脚本", "自动", "excel", "csv", "file"],
            "product_launch": ["产品", "launch", "上线", "发布", "推广", "产品方案"],
        }
        
        scores = {}
        for sid, keywords in services.items():
            score = sum(1 for kw in keywords if kw in text_lower) / len(keywords)
            scores[sid] = score
        
        best_service = max(scores, key=scores.get)
        best_score = scores[best_service]
        
        return {
            "service_id": best_service if best_score > 0.1 else None,
            "confidence": best_score,
            "all_scores": scores,
        }
    
    def check_risk(self, request_text: str) -> dict:
        """风险检测"""
        text_lower = request_text.lower()
        
        # 加载拒绝规则
        reject_rules = self._load_yaml(RULES_DIR / "rejection_rules.yaml")
        hard_blocks_text = ""
        try:
            hard_blocks = re.findall(r'patterns:\n((?:\s+- "[^"]*"\n?)*)', 
                                    (RULES_DIR / "rejection_rules.yaml").read_text())
            for block in hard_blocks:
                hard_blocks_text += block
        except:
            pass
        
        # 检查硬拒绝
        hard_reject_patterns = [
            "crack", "keygen", "pirate", "phish", "scam", "exploit",
            "malware", "ransomware", "backdoor", "hack", "破解", "盗版",
            "钓鱼", "诈骗", "黑客", "刷量", "涨粉", "绕过", "代理池",
        ]
        
        for pattern in hard_reject_patterns:
            if pattern in text_lower:
                return {"risk_level": "critical", "reason": f"包含高风险关键词: {pattern}", "auto_reject": True}
        
        # 检查软拒绝
        soft_reject_patterns = [
            "保证收益", "保证排名", "理财", "投资",
        ]
        
        for pattern in soft_reject_patterns:
            if pattern in text_lower:
                return {"risk_level": "high", "reason": f"包含敏感关键词: {pattern}", "auto_reject": True}
        
        # 计算清晰度
        clarity_boosters = ["https://", "github.com/", "pip", "python", "代码", "项目", "需要", "请"]
        clarity_score = sum(1 for b in clarity_boosters if b in text_lower) / len(clarity_boosters)
        
        if len(request_text) < 50:
            return {"risk_level": "medium", "reason": "需求描述过短", "clarity_score": clarity_score, "auto_reject": False, "needs_clarification": True}
        
        return {"risk_level": "low", "reason": "通过", "clarity_score": clarity_score, "auto_reject": False}
    
    def auto_quote(self, service_id: str, tier: str = None) -> dict:
        """自动报价"""
        from payment.unique_amount import generate_invoice_amount
        
        invoice = generate_invoice_amount(service_id, tier or "basic")
        return invoice
    
    def update_status(self, order_id: str, new_status: str) -> dict:
        """更新订单状态"""
        if new_status not in ORDER_STATUS:
            raise ValueError(f"无效状态: {new_status}")
        
        order = self._get_order(order_id)
        if not order:
            return {"error": "订单不存在"}
        
        old_status = order["status"]
        order["status"] = new_status
        order["updated_at"] = datetime.now().isoformat()
        
        # 记录状态变更
        if "status_history" not in order:
            order["status_history"] = []
        order["status_history"].append({
            "from": old_status,
            "to": new_status,
            "at": datetime.now().isoformat(),
        })
        
        self._save_order(order)
        return {"success": True, "order_id": order_id, "old_status": old_status, "new_status": new_status}
    
    def process_request(self, request_text: str, contact: str = "") -> dict:
        """处理客户请求——全自动流程"""
        # 1. 创建订单
        order = self.create_order(request_text, contact)
        order_id = order["order_id"]
        
        # 2. 分类服务
        classification = self.classify_request(request_text)
        order["service_classification"] = classification
        
        if not classification["service_id"]:
            self.update_status(order_id, "clarification")
            return {
                "order_id": order_id,
                "status": "clarification",
                "message": "无法识别服务类型，请从以下服务中选择：\n1. GitHub Project Polish\n2. PyPI Package Release\n3. AI CLI Tool Builder\n4. Automation Script Service\n5. AI Product Launch System",
            }
        
        # 3. 风险检测
        risk = self.check_risk(request_text)
        order["risk_check"] = risk
        
        if risk.get("auto_reject"):
            self.update_status(order_id, "rejected")
            return {
                "order_id": order_id,
                "status": "rejected",
                "message": f"无法接单: {risk.get('reason', '需求不符合服务范围')}",
            }
        
        if risk.get("needs_clarification"):
            self.update_status(order_id, "clarification")
            return {
                "order_id": order_id,
                "status": "clarification",
                "message": "请提供更详细的需求描述，包括项目背景和期望交付物。",
            }
        
        # 4. 自动报价（使用 Basic 套餐）
        invoice = self.auto_quote(classification["service_id"], "basic")
        order["invoice"] = invoice
        self.update_status(order_id, "awaiting_payment")
        
        return {
            "order_id": order_id,
            "status": "awaiting_payment",
            "message": f"报价已生成",
            "invoice": {
                "total_usdt": invoice["total_usdt"],
                "wallet": invoice["wallet"],
                "network": invoice["network"],
                "currency": invoice["currency"],
            },
            "payment_note": f"请支付 {invoice['total_usdt']} USDT (ERC20) 到 {invoice['wallet']}",
        }
    
    def confirm_payment(self, order_id: str, tx_hash: str) -> dict:
        """确认付款"""
        from payment.chain_scanner import verify_payment
        
        result = verify_payment(order_id, tx_hash)
        
        if result.get("verified"):
            self.update_status(order_id, "paid")
            order = self._get_order(order_id)
            order["payment"] = result
            self._save_order(order)
            return {"success": True, "message": "付款已确认，订单自动开工!"}
        elif result.get("reason") == "amount_mismatch":
            return {"success": False, "message": f"金额不匹配: 收到 {result.get('received')} USDT, 期望 {result.get('expected')} USDT"}
        else:
            return {"success": False, "message": f"付款验证失败: {result.get('reason', '未知错误')}"}
    
    def _save_order(self, order: dict):
        """保存订单"""
        order_dir = ORDERS_DIR / order["order_id"]
        order_dir.mkdir(parents=True, exist_ok=True)
        (order_dir / "order.json").write_text(json.dumps(order, indent=2, ensure_ascii=False))
    
    def _get_order(self, order_id: str) -> dict:
        """获取订单"""
        order_file = ORDERS_DIR / order_id / "order.json"
        if order_file.exists():
            return json.loads(order_file.read_text())
        return None
    
    def get_order_status(self, order_id: str) -> dict:
        """获取订单状态"""
        order = self._get_order(order_id)
        if not order:
            return {"error": "订单不存在"}
        return {
            "order_id": order["order_id"],
            "status": order["status"],
            "created_at": order["created_at"],
            "updated_at": order["updated_at"],
        }
    
    def list_orders(self, status_filter: str = None) -> list:
        """列出订单"""
        orders = []
        for order_dir in sorted(ORDERS_DIR.iterdir(), reverse=True):
            if not order_dir.is_dir():
                continue
            order = self._get_order(order_dir.name)
            if order:
                if status_filter and order["status"] != status_filter:
                    continue
                orders.append({
                    "order_id": order["order_id"],
                    "status": order["status"],
                    "created_at": order["created_at"],
                    "request_preview": order["request"][:100],
                })
        return orders


if __name__ == "__main__":
    import sys
    
    engine = OrderEngine()
    
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        orders = engine.list_orders(status)
        print(f"共 {len(orders)} 个订单:")
        for o in orders:
            print(f"  [{o['status']}] {o['order_id']}: {o['request_preview']}")
    
    elif len(sys.argv) > 2 and sys.argv[1] == "submit":
        result = engine.process_request(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif len(sys.argv) > 2 and sys.argv[1] == "pay":
        result = engine.confirm_payment(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    else:
        print("用法:")
        print("  python3 order_engine.py submit \"<需求描述>\"")
        print("  python3 order_engine.py pay <order_id> <tx_hash>")
        print("  python3 order_engine.py list [status]")
