#!/usr/bin/env python
"""
Test that the compiled pipeline YAML exists and has valid structure.

This is a sanity check, not a full validation - it ensures the pipeline
file is present, non-empty, and contains expected components.
"""
import sys
import yaml
from pathlib import Path


def test_compiled_pipeline():
    """Verify compiled pipeline YAML structure"""
    pipeline_file = Path(__file__).parent.parent / "flts_pipeline.yaml"
    
    print("="*70)
    print("Compiled Pipeline Sanity Test")
    print("="*70)
    
    # Test 1: File exists
    print(f"\nTest 1: File existence...")
    if not pipeline_file.exists():
        print(f"  ✗ FAILED: {pipeline_file} not found")
        return False
    print(f"  ✓ File exists: {pipeline_file}")
    
    # Test 2: File size
    print(f"\nTest 2: File size...")
    size = pipeline_file.stat().st_size
    if size == 0:
        print(f"  ✗ FAILED: File is empty")
        return False
    print(f"  ✓ Size: {size:,} bytes")
    
    # Test 3: Valid YAML
    print(f"\nTest 3: YAML syntax...")
    try:
        with open(pipeline_file) as f:
            spec = yaml.safe_load(f)
    except Exception as e:
        print(f"  ✗ FAILED: Invalid YAML - {e}")
        return False
    print(f"  ✓ Valid YAML")
    
    # Test 4: Argo Workflow structure
    print(f"\nTest 4: Argo Workflow structure...")
    if spec.get('apiVersion') != 'argoproj.io/v1alpha1':
        print(f"  ✗ FAILED: Not an Argo Workflow (apiVersion={spec.get('apiVersion')})")
        return False
    if spec.get('kind') != 'Workflow':
        print(f"  ✗ FAILED: Not a Workflow (kind={spec.get('kind')})")
        return False
    print(f"  ✓ Argo Workflow format")
    
    # Test 5: Pipeline metadata
    print(f"\nTest 5: Pipeline metadata...")
    metadata = spec.get('metadata', {})
    annotations = metadata.get('annotations', {})
    kfp_version = annotations.get('pipelines.kubeflow.org/kfp_sdk_version')
    if kfp_version != '1.8.22':
        print(f"  ✗ FAILED: Wrong KFP version (expected 1.8.22, got {kfp_version})")
        return False
    print(f"  ✓ KFP v1.8.22 metadata present")
    
    # Test 6: Expected components
    print(f"\nTest 6: Component presence...")
    templates = spec.get('spec', {}).get('templates', [])
    template_names = {t['name'] for t in templates}
    
    expected_components = {
        'preprocess',
        'train-gru',
        'train-lstm',
        'train-prophet',
        'evaluate',
        'inference'
    }
    
    missing = expected_components - template_names
    if missing:
        print(f"  ✗ FAILED: Missing components: {missing}")
        print(f"  Found: {template_names}")
        return False
    
    print(f"  ✓ All 6 components present:")
    for comp in sorted(expected_components):
        print(f"    - {comp}")
    
    # Test 7: Container images
    print(f"\nTest 7: Container images...")
    images_found = set()
    for template in templates:
        if 'container' in template and 'image' in template['container']:
            images_found.add(template['container']['image'])
    
    expected_images = {
        'flts-preprocess:latest',
        'train-container:latest',
        'nonml-container:latest',
        'eval-container:latest',
        'inference-container:latest'
    }
    
    missing_images = expected_images - images_found
    if missing_images:
        print(f"  ⚠ WARNING: Some expected images not found: {missing_images}")
    else:
        print(f"  ✓ All expected container images present")
    
    print(f"\n{'='*70}")
    print("✓ ALL TESTS PASSED")
    print(f"{'='*70}")
    return True


if __name__ == '__main__':
    success = test_compiled_pipeline()
    sys.exit(0 if success else 1)
