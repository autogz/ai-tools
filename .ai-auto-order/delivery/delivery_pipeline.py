#!/usr/bin/env python3
"""
Delivery Pipeline — 自动交付系统
workspace_creator -> repo_fetcher -> executor -> qa_checker -> packager -> notifier
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path("/root/.ai-auto-order")
ORDERS_DIR = BASE / "orders"


class DeliveryPipeline:
    """自动交付流水线"""
    
    def __init__(self):
        self.qa_results = []
    
    def create_workspace(self, order_id: str) -> Path:
        """创建订单工作区"""
        workspace = ORDERS_DIR / order_id / "deliverables"
        workspace.mkdir(parents=True, exist_ok=True)
        self._log(order_id, "workspace_created", str(workspace))
        return workspace
    
    def generate_readme(self, workspace: Path, service_type: str):
        """生成 README.md"""
        readme_content = f"""# Project Documentation

## Overview
Auto-generated deliverable for service: {service_type}

## Installation
```bash
pip install -r requirements.txt
```

## Usage
See individual documentation files.

## License
MIT
"""
        (workspace / "README.md").write_text(readme_content)
    
    def generate_security(self, workspace: Path):
        """生成 SECURITY.md"""
        content = """# Security Policy

## Supported Versions
Latest release only.

## Reporting
Report vulnerabilities via GitHub Issues.
"""
        (workspace / "SECURITY.md").write_text(content)
    
    def generate_disclaimer(self, workspace: Path):
        """生成 DISCLAIMER.md"""
        content = """# Disclaimer

This software is provided "as is", without warranty of any kind.
"""
        (workspace / "DISCLAIMER.md").write_text(content)
    
    def run_qa(self, workspace: Path, order_id: str) -> dict:
        """运行质量检查"""
        results = {
            "order_id": order_id,
            "timestamp": datetime.now().isoformat(),
            "checks": [],
            "passed": True,
        }
        
        # 检查文件是否存在
        required_files = ["README.md", "SECURITY.md", "DISCLAIMER.md"]
        for f in required_files:
            exists = (workspace / f).exists()
            results["checks"].append({
                "check": f"file_exists:{f}",
                "passed": exists,
            })
            if not exists:
                results["passed"] = False
        
        # 检查 README 大小
        readme = workspace / "README.md"
        if readme.exists():
            size = len(readme.read_text())
            results["checks"].append({
                "check": "readme_size",
                "passed": size > 50,
                "size": size,
            })
            if size < 50:
                results["passed"] = False
        
        # 检查 Markdown 渲染
        for md_file in workspace.glob("*.md"):
            content = md_file.read_text()
            # 检查未闭合的代码块
            opens = content.count("```")
            if opens % 2 != 0:
                results["checks"].append({
                    "check": f"markdown_code_blocks:{md_file.name}",
                    "passed": False,
                    "reason": "未闭合的代码块",
                })
                results["passed"] = False
        
        self.qa_results = results
        self._log(order_id, "qa_completed", json.dumps(results))
        return results
    
    def auto_fix(self, qa_result: dict, workspace: Path) -> bool:
        """自动修复 QA 问题"""
        fixed = False
        
        for check in qa_result.get("checks", []):
            if check["passed"]:
                continue
            
            # 修复缺失文件
            if check["check"].startswith("file_exists:"):
                missing_file = check["check"].split(":")[1]
                if missing_file == "SECURITY.md":
                    self.generate_security(workspace)
                    fixed = True
                elif missing_file == "DISCLAIMER.md":
                    self.generate_disclaimer(workspace)
                    fixed = True
            
            # 修复代码块
            if "markdown_code_blocks" in check["check"]:
                md_path = workspace / check["check"].split(":")[1]
                if md_path.exists():
                    content = md_path.read_text()
                    content += "\n```\n"
                    md_path.write_text(content)
                    fixed = True
        
        return fixed
    
    def package_delivery(self, workspace: Path, order_id: str) -> Path:
        """打包交付物"""
        manifest = {"files": []}
        for f in sorted(workspace.iterdir()):
            manifest["files"].append({
                "name": f.name,
                "size": f.stat().st_size,
            })
        
        manifest_path = workspace / "file_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        
        self._log(order_id, "delivery_packaged", f"{len(manifest['files'])} files")
        return manifest_path
    
    def run(self, order_id: str, service_type: str) -> dict:
        """全自动交付流水线"""
        print(f"🚀 开始交付: {order_id}")
        
        # 1. 创建工作区
        workspace = self.create_workspace(order_id)
        print(f"  📁 工作区: {workspace}")
        
        # 2. 生成交付物
        print(f"  📝 生成交付物...")
        self.generate_readme(workspace, service_type)
        self.generate_security(workspace)
        self.generate_disclaimer(workspace)
        
        # 3. QA 检查
        print(f"  🔍 QA 检查...")
        qa = self.run_qa(workspace, order_id)
        
        if qa["passed"]:
            print(f"  ✅ QA 通过")
        else:
            print(f"  ⚠️ QA 未通过，尝试自动修复...")
            for attempt in range(3):
                fixed = self.auto_fix(qa, workspace)
                if fixed:
                    qa = self.run_qa(workspace, order_id)
                    if qa["passed"]:
                        print(f"  ✅ 修复成功 (第 {attempt+1} 轮)")
                        break
                else:
                    # 降级交付
                    print(f"  ⚠️ 无法修复，生成降级交付物")
                    (workspace / "known_issues.md").write_text(
                        f"# Known Issues\n\nFollowing QA issues could not be auto-fixed:\n"
                    )
                    break
        
        # 4. 打包
        manifest = self.package_delivery(workspace, order_id)
        print(f"  📦 打包完成: {len(json.loads(manifest.read_text())['files'])} 个文件")
        
        return {
            "order_id": order_id,
            "status": "delivered",
            "workspace": str(workspace),
            "qa_passed": qa["passed"],
            "delivery_time": datetime.now().isoformat(),
            "files": [f.name for f in sorted(workspace.iterdir())],
        }
    
    def _log(self, order_id: str, event: str, details: str = ""):
        """记录事件"""
        log_file = ORDERS_DIR / order_id / "worklog.md"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(f"- [{datetime.now().isoformat()}] {event}: {details}\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        pipeline = DeliveryPipeline()
        result = pipeline.run(sys.argv[1], sys.argv[2])
        print(json.dumps(result, indent=2))
    else:
        print("用法: python3 delivery_pipeline.py <order_id> <service_type>")
