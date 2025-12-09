#!/usr/bin/env bash
# KFP v2 Step 8 Test Harness
# Runs all validation tests to confirm Step 8 completion

set -euo pipefail

ROOT="/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3"
VENV="/Users/arnavde/Python/AI/.venv"

cd "$ROOT"

echo "======================================================================="
echo "KFP v2 Step 8 Test Harness"
echo "======================================================================="
echo ""

# Test 1: Verify KFP version
echo "Test: KFP Version Check"
echo "-----------------------------------------------------------------------"
"$VENV/bin/python" -c "import kfp; print(f'KFP version: {kfp.__version__}'); assert kfp.__version__.startswith('2.'), 'Must be KFP v2'"
echo "✓ KFP v2 confirmed"
echo ""

# Test 2: Compile pipeline
echo "Test: Pipeline Compilation"
echo "-----------------------------------------------------------------------"
"$VENV/bin/python" kubeflow_pipeline/compile_pipeline_v2.py --output artifacts/flts_pipeline_v2.json
echo ""

# Test 3: Verify artifacts
echo "Test: Artifact Verification"
echo "-----------------------------------------------------------------------"
if [ -f "artifacts/flts_pipeline_v2.json" ]; then
    SIZE=$(wc -c < artifacts/flts_pipeline_v2.json | tr -d ' ')
    echo "✓ Pipeline spec exists: artifacts/flts_pipeline_v2.json"
    echo "  Size: $SIZE bytes"
    
    if [ "$SIZE" -gt 10000 ]; then
        echo "✓ File size reasonable (>10KB)"
    else
        echo "✗ File size too small"
        exit 1
    fi
else
    echo "✗ Pipeline spec not found"
    exit 1
fi
echo ""

# Test 4: Run unit tests
echo "Test: Component & Pipeline Tests"
echo "-----------------------------------------------------------------------"
"$VENV/bin/python" kubeflow_pipeline/tests/test_kfp_v2_pipeline.py
echo ""

# Test 5: Verify no v1 references
echo "Test: No KFP v1 References"
echo "-----------------------------------------------------------------------"
if grep -r "ContainerOp\|kfp\.dsl\.ContainerOp" kubeflow_pipeline --include="*.py" --exclude-dir="_deprecated" 2>/dev/null; then
    echo "✗ Found KFP v1 references in active code"
    exit 1
else
    echo "✓ No KFP v1 references found in active code"
fi
echo ""

echo "======================================================================="
echo "✓ All Step 8 Tests PASSED"
echo "======================================================================="
echo ""
echo "Step 8 (Pipeline Definition) is COMPLETE."
echo "Step 9 (Deployment) has NOT been started."
echo ""
echo "Artifacts:"
echo "  - kubeflow_pipeline/components_v2.py (component definitions)"
echo "  - kubeflow_pipeline/pipeline_v2.py (pipeline DAG)"
echo "  - kubeflow_pipeline/compile_pipeline_v2.py (compiler script)"
echo "  - artifacts/flts_pipeline_v2.json (compiled spec)"
echo ""
