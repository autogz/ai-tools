#!/usr/bin/env python3
"""
Chain Scanner — 自动扫描链上 USDT 付款
复用 /root/usdt-monitor/monitor.py 的链上查询逻辑
"""
import json
import os
import urllib.request
import urllib.parse
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

USDT_ADDRESS = "0xafc32581a9e4ea30aa03cb8ef5879c2366d35f46"
USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "2FA6GB3TFEM2HWMMTBMD87ZJ2T3MKHD17U")

ORDERS_DIR = Path("/root/.ai-auto-order/orders")
PRICE_TOLERANCE = 0.05


def get_order(order_id: str) -> dict:
    """读取订单"""
    order_file = ORDERS_DIR / order_id / "order.json"
    if order_file.exists():
        return json.loads(order_file.read_text())
    return None


def save_order(order_id: str, data: dict):
    """保存订单"""
    order_dir = ORDERS_DIR / order_id
    order_dir.mkdir(parents=True, exist_ok=True)
    (order_dir / "order.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


def scan_transactions(since_block: int = 0) -> list[dict]:
    """扫描 USDT 交易"""
    params = urllib.parse.urlencode({
        "chainid": 1,
        "module": "account",
        "action": "tokentx",
        "address": USDT_ADDRESS,
        "contractaddress": USDT_CONTRACT,
        "sort": "desc",
        "startblock": since_block,
        "apikey": ETHERSCAN_API_KEY,
    })
    url = f"https://api.etherscan.io/v2/api?{params}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return [{"type": "error", "message": str(e)}]
    
    result_list = data.get("result", [])
    if not isinstance(result_list, list) or len(result_list) == 0:
        return []
    
    txs = []
    for tx in result_list:
        to_addr = tx.get("to", "").lower()
        if to_addr != USDT_ADDRESS.lower():
            continue
        
        txs.append({
            "tx_hash": tx.get("hash", ""),
            "from": tx.get("from", ""),
            "amount": int(tx.get("value", 0)) / 10**6,
            "block": int(tx.get("blockNumber", 0)),
            "timestamp": datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
        })
    
    return txs


def verify_payment(order_id: str, tx_hash: str) -> dict:
    """验证订单付款"""
    order = get_order(order_id)
    if not order:
        return {"verified": False, "reason": "order_not_found"}
    
    expected_amount = order.get("invoice", {}).get("total_usdt", 0)
    if expected_amount == 0:
        return {"verified": False, "reason": "no_invoice"}
    
    # 查询该交易
    params = urllib.parse.urlencode({
        "chainid": 1,
        "module": "account",
        "action": "tokentx",
        "address": USDT_ADDRESS,
        "contractaddress": USDT_CONTRACT,
        "sort": "desc",
        "apikey": ETHERSCAN_API_KEY,
    })
    url = f"https://api.etherscan.io/v2/api?{params}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"verified": False, "reason": f"api_error: {e}"}
    
    # 查找匹配交易
    for tx in data.get("result", []):
        if tx.get("hash", "").lower() != tx_hash.lower():
            continue
        
        to_addr = tx.get("to", "").lower()
        if to_addr != USDT_ADDRESS.lower():
            return {"verified": False, "reason": "wrong_recipient"}
        
        amount = int(tx.get("value", 0)) / 10**6
        sender = tx.get("from", "")
        block = int(tx.get("blockNumber", 0))
        tx_time = datetime.fromtimestamp(int(tx.get("timeStamp", 0)))
        
        # 验证金额
        if abs(amount - expected_amount) / expected_amount > PRICE_TOLERANCE:
            return {
                "verified": False,
                "reason": "amount_mismatch",
                "expected": expected_amount,
                "received": amount,
            }
        
        # 验证交易时间在 invoice 生成之后
        invoice_time = datetime.fromisoformat(order.get("invoice", {}).get("generated_at", "2000-01-01"))
        if tx_time < invoice_time:
            return {"verified": False, "reason": "transaction_before_invoice"}
        
        # 验证交易未用于其他订单
        for oid in ORDERS_DIR.iterdir():
            if not oid.is_dir() or oid.name == order_id:
                continue
            other = get_order(oid.name)
            if other and other.get("payment", {}).get("tx_hash", "").lower() == tx_hash.lower():
                return {"verified": False, "reason": "tx_already_used", "existing_order": oid.name}
        
        # 验证通过
        return {
            "verified": True,
            "amount": amount,
            "expected": expected_amount,
            "sender": sender,
            "tx_hash": tx_hash,
            "block": block,
            "timestamp": tx_time.isoformat(),
        }
    
    return {"verified": False, "reason": "tx_not_found"}


def check_pending_payments() -> list[dict]:
    """检查所有待付款订单"""
    results = []
    for order_dir in ORDERS_DIR.iterdir():
        if not order_dir.is_dir():
            continue
        order = get_order(order_dir.name)
        if order and order.get("status") == "awaiting_payment":
            # 扫描最近交易匹配金额
            txs = scan_transactions()
            for tx in txs:
                expected = order.get("invoice", {}).get("total_usdt", 0)
                if abs(tx["amount"] - expected) / expected <= PRICE_TOLERANCE:
                    # 检查是否已用于其他订单
                    result = verify_payment(order_dir.name, tx["tx_hash"])
                    if result.get("verified"):
                        results.append({
                            "order_id": order_dir.name,
                            "tx_hash": tx["tx_hash"],
                            "amount": tx["amount"],
                            "expected": expected,
                        })
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        result = verify_payment(sys.argv[1], sys.argv[2])
        print(json.dumps(result, indent=2))
    else:
        pending = check_pending_payments()
        if pending:
            print(f"发现 {len(pending)} 笔待确认付款:")
            for p in pending:
                print(f"  订单 {p['order_id']}: {p['amount']} USDT (期望 {p['expected']})")
        else:
            print("没有新的待确认付款")
