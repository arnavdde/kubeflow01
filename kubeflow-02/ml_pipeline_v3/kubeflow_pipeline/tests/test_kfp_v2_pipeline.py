"""
KFP v2 Pipeline Tests

Tests for Step 8 completion validation:
1. Component validation
2. Pipeline decoration
3. Compilation to JSON
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kfp import compiler, dsl
from kubeflow_pipeline.components_v2 import (
    preprocess_component,
    train_gru_component,
    train_lstm_component,
    train_prophet_component,
    eval_component,
    inference_component,
)
from kubeflow_pipeline.pipeline_v2 import flts_pipeline


def test_components_are_valid():
    """Verify all components are KFP v2 components."""
    components = {
        'preprocess_component': preprocess_component,
        'train_gru_component': train_gru_component,
        'train_lstm_component': train_lstm_component,
        'train_prophet_component': train_prophet_component,
        'eval_component': eval_component,
        'inference_component': inference_component,
    }

    for name, comp in components.items():
        # KFP v2 components have component_spec attribute
        assert hasattr(comp, 'component_spec'), f"{name} missing component_spec"
        # component_spec should have implementation and be non-None
        assert comp.component_spec is not None, f"{name} has None component_spec"
        print(f"  ✓ {name}: Valid KFP v2 component")

    return True


def test_pipeline_is_decorated():
    """Test that the pipeline function is properly decorated."""
    print("\nTest 2: Pipeline Decoration")
    print("-" * 50)
    
    assert hasattr(flts_pipeline, 'pipeline_spec'), "Pipeline missing pipeline_spec"
    print("  ✓ flts_pipeline: Valid KFP v2 pipeline")
    return True


def test_pipeline_compilation():
    """Test that pipeline compiles to valid JSON."""
    print("\nTest 3: Pipeline Compilation")
    print("-" * 50)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_pipeline.json")
        print(f"  Compiling to: {output_path}")
        
        compiler.Compiler().compile(
            pipeline_func=flts_pipeline,
            package_path=output_path
        )
        
        assert os.path.exists(output_path), "Compilation output not found"
        
        size = os.path.getsize(output_path)
        print(f"  ✓ Compilation successful ({size:,} bytes)")
        
        # Validate JSON structure - KFP v2 spec is at root level
        with open(output_path, 'r') as f:
            spec = json.load(f)
        
        # KFP v2 IR spec has these top-level keys
        assert 'pipelineInfo' in spec or 'components' in spec, "Missing required top-level keys"
        print(f"  ✓ Valid KFP v2 IR spec structure")
        
    return True


def run_all_tests():
    """Run all Step 8 tests."""
    print("=" * 70)
    print("KFP v2 Step 8 Tests")
    print("=" * 70)
    
    tests = [
        test_components_are_valid,
        test_pipeline_is_decorated,
        test_pipeline_compilation,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
