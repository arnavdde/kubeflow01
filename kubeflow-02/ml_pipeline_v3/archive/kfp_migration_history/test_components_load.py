"""
Component YAML load test for KFP v1

This test verifies that all component.yaml files can be loaded successfully
using the KFP v1.8.22 components.load_component_from_file() API.
"""

import sys
from pathlib import Path
from kfp import components


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = ROOT / "components"


def main() -> int:
    print("=== Component YAML load test (KFP v1.8.22) ===")
    if not COMPONENTS_DIR.is_dir():
        print(f"[ERROR] Components dir not found: {COMPONENTS_DIR}")
        return 1

    failures = []
    successes = []
    
    for yaml_path in COMPONENTS_DIR.rglob("component.yaml"):
        rel = yaml_path.relative_to(ROOT)
        print(f"[INFO] Loading component: {rel}")
        try:
            comp = components.load_component_from_file(str(yaml_path))
            print(f"  -> OK (name: {comp.component_spec.name})")
            successes.append(rel)
        except Exception as e:
            print(f"  -> FAILED: {e}")
            failures.append((rel, str(e)))

    print(f"\n{'='*70}")
    print(f"[SUMMARY] Loaded {len(successes)}/{len(successes)+len(failures)} components successfully")
    print(f"{'='*70}")
    
    if failures:
        print("\n[ERROR] Failed components:")
        for rel, err in failures:
            print(f" - {rel}")
            print(f"   Error: {err[:200]}")  # Truncate long errors
        return 1

    print("\n✓ All components loaded successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
