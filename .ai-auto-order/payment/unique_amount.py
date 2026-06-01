#!/usr/bin/env python3
"""
Unique Amount Generator — 订单级唯一金额
基础价格 + 唯一尾数 = 每订单不同金额
用于防止重复交易哈希攻击
"""
import json
import hashlib
import os
from datetime import datetime
from pathlib import Path

AMOUNT_CONFIG_PATH = Path("/root/.ai-auto-order/rules/pricing_rules.yaml")


def parse_pricing():
    """简易 YAML 解析，获取服务定价"""
    import re
    content = AMOUNT_CONFIG_PATH.read_text()
    services = {}
    
    # 提取服务块
    blocks = re.findall(r'  - id: (\w+)\n    name: "([^"]+)"([\s\S]*?)(?=\n  - id:|\n#)', content)
    
    for sid, sname, sbody in blocks:
        tiers = re.findall(r'      - name: "([^"]+)"\n        price_usdt: ([\d.]+)', sbody)
        services[sid] = {
            "name": sname,
            "tiers": {t[0].lower(): float(t[1]) for t in tiers}
        }
    
    return services


def generate_tail(order_id: str, timestamp: str = None) -> float:
    """生成唯一尾数（0.01 - 0.99）"""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    # 基于订单号和时间戳的确定性哈希
    raw = f"{order_id}-{timestamp}-v4"
    hash_val = hashlib.sha256(raw.encode()).hexdigest()
    
    # 取前6位十六进制转十进制，映射到 0.01-0.99
    tail_int = int(hash_val[:6], 16) % 99 + 1
    return round(tail_int / 100, 2)


def generate_invoice_amount(service_id: str, tier: str, order_id: str = None) -> dict:
    """生成唯一 Invoice 金额"""
    services = parse_pricing()
    
    if service_id not in services:
        raise ValueError(f"未知服务: {service_id}")
    
    tier_key = tier.lower()
    if tier_key not in services[service_id]["tiers"]:
        raise ValueError(f"未知套餐: {tier} (可选: {list(services[service_id]['tiers'].keys())})")
    
    base_price = services[service_id]["tiers"][tier_key]
    
    if order_id is None:
        import uuid
        order_id = str(uuid.uuid4())[:8]
    
    tail = generate_tail(order_id)
    total = round(base_price + tail, 2)
    
    return {
        "order_id": order_id,
        "service": services[service_id]["name"],
        "tier": tier,
        "base_price": base_price,
        "tail": tail,
        "total_usdt": total,
        "currency": "USDT",
        "network": "ERC20",
        "wallet": "0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46",
        "generated_at": datetime.now().isoformat(),
    }


def verify_invoice_amount(order_id: str, paid_amount: float, expected_amount: float) -> dict:
    """验证付款金额是否匹配"""
    difference = round(abs(paid_amount - expected_amount), 4)
    
    if difference == 0:
        return {"match": True, "status": "exact", "difference": 0}
    elif difference <= 0.05:
        return {"match": True, "status": "within_tolerance", "difference": difference}
    elif paid_amount < expected_amount:
        return {"match": False, "status": "underpaid", "difference": difference, 
                "shortfall": round(expected_amount - paid_amount, 2)}
    else:
        return {"match": False, "status": "overpaid", "difference": difference,
                "excess": round(paid_amount - expected_amount, 2)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        invoice = generate_invoice_amount(sys.argv[1], sys.argv[2])
        print(json.dumps(invoice, indent=2))
        print(f"\n客户需支付: {invoice['total_usdt']} USDT (基础 {invoice['base_price']} + 尾数 {invoice['tail']})")
    else:
        print("用法: python3 unique_amount.py <service_id> <tier>")
        print("服务:")
        for sid, sinfo in parse_pricing().items():
            tiers = ", ".join(sinfo["tiers"].keys())
            print(f"  {sid}: {sinfo['name']} ({tiers})")
