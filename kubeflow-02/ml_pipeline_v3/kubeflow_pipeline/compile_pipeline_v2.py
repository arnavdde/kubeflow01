#!/usr/bin/env python
"""
KFP v2 Pipeline Compilation Script

Compiles the FLTS pipeline into a KFP v2 IR spec (JSON format) that can be
uploaded to Kubeflow Pipelines for execution.

Usage:
    # Default output
    python compile_pipeline_v2.py
    
    # Custom output location
    python compile_pipeline_v2.py --output custom/path/pipeline.json
    
Environment:
    Requires KFP v2 (kfp>=2.0.0,<3.0.0) installed in the Python environment.
"""

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kfp import compiler
from kubeflow_pipeline.pipeline_v2 import flts_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Compile FLTS KFP v2 Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard compilation
  python compile_pipeline_v2.py
  
  # Custom output location
  python compile_pipeline_v2.py --output /tmp/my_pipeline.json
  
  # Specify artifacts directory
  python compile_pipeline_v2.py --output artifacts/flts_pipeline_v2.json
        """,
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("artifacts/flts_pipeline_v2.json"),
        help="Output path for compiled pipeline spec (default: artifacts/flts_pipeline_v2.json)",
    )
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("KFP v2 Pipeline Compilation")
    print("=" * 70)
    print()
    print(f"Pipeline: flts_pipeline")
    print(f"Output:   {args.output}")
    print()
    
    try:
        # Compile using KFP v2 compiler
        compiler.Compiler().compile(
            pipeline_func=flts_pipeline,
            package_path=str(args.output),
        )
        
        # Verify output file
        if not args.output.exists():
            raise RuntimeError(f"Compilation succeeded but output file not found: {args.output}")
        
        file_size = args.output.stat().st_size
        
        print("✓ Compilation successful")
        print()
        print(f"Compiled pipeline spec:")
        print(f"  Path: {args.output}")
        print(f"  Size: {file_size:,} bytes")
        print()
        print("=" * 70)
        print("Next steps:")
        print("  1. Review the generated JSON spec")
        print("  2. Upload to Kubeflow Pipelines UI (Step 9)")
        print("  3. Create a run with desired parameters")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"✗ Compilation failed:")
        print(f"  {e}")
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
