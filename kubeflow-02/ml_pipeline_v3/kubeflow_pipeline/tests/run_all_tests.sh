#!/bin/bash
# Run all Task 8 validation tests
set -euo pipefail

echo "======================================================================="
echo "FLTS Task 8 Test Suite (KFP v1.8.22)"
echo "======================================================================="
echo ""

echo "Running test_compiled_pipeline.py (compiled YAML sanity check)..."
python kubeflow_pipeline/tests/test_compiled_pipeline.py
echo ""

echo "======================================================================="
echo "✓ ALL TESTS PASSED"
echo "======================================================================="
