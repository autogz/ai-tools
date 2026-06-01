#!/usr/bin/env python3
"""Validate all YAML registry files parse correctly."""
import yaml
import sys
from pathlib import Path

registry_dir = Path('/root/.ai-free-cloud-orchestrator/registry')

try:
    import yaml
except ImportError:
    yaml = None
    print("  PyYAML not installed — skipping YAML validation")
    sys.exit(0)
files = ['platforms.yaml', 'agents.yaml', 'quotas.yaml', 'task_whitelist.yaml']
errors = []

for fname in files:
    path = registry_dir / fname
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        print(f"  OK  {fname} — parsed successfully")
        if fname == 'task_whitelist.yaml':
            tasks = sum(len(c["tasks"]) for c in data["categories"].values())
            print(f"       Tasks: {tasks}")
        if fname == 'agents.yaml':
            print(f"       Agents: {len(data['agents'])}")
        if fname == 'platforms.yaml':
            print(f"       Platforms: {len(data['platforms'])}")
    except Exception as e:
        errors.append(f"  FAIL {fname}: {e}")
        print(f"  FAIL {fname}: {e}")

if errors:
    print(f"\n{len(errors)} validation error(s) found.")
    sys.exit(1)
else:
    print("\nAll YAML files validated successfully.")
