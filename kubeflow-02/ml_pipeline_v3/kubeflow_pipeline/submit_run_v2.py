"""
KFP v2 Programmatic Pipeline Submission Script

Compiles, uploads, and runs the FLTS pipeline in Kubeflow Pipelines.
Provides a repeatable, scriptable interface for Step 10 E2E runs.

Usage:
    # Full workflow: compile → upload → create experiment → run
    python submit_run_v2.py
    
    # Skip compilation (use existing spec)
    python submit_run_v2.py --skip-compile
    
    # Custom parameters
    python submit_run_v2.py --dataset ElBorn --identifier step10-test-001 --experiment step10-validation
    
    # Dry run (compile + validate only)
    python submit_run_v2.py --dry-run
    
Requirements:
    - KFP v2 SDK installed (kfp>=2.0.0)
    - kubectl configured with access to Kubeflow cluster
    - KFP API server reachable (via port-forward or in-cluster)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import kfp
    from kfp import compiler
    from kfp.client import Client
except ImportError:
    print("Error: kfp package not installed")
    print("Install with: pip install 'kfp>=2.0.0,<3.0.0'")
    sys.exit(1)

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kubeflow_pipeline.pipeline_v2 import flts_pipeline
from kubeflow_pipeline.config.runtime_defaults import RuntimeConfig


class Color:
    """Terminal color codes."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(msg: str):
    """Print section header."""
    print(f"\n{Color.HEADER}{Color.BOLD}{'='*80}{Color.END}")
    print(f"{Color.HEADER}{Color.BOLD}{msg}{Color.END}")
    print(f"{Color.HEADER}{Color.BOLD}{'='*80}{Color.END}\n")


def print_step(step: str, msg: str):
    """Print step message."""
    print(f"{Color.CYAN}{Color.BOLD}[{step}]{Color.END} {msg}")


def print_success(msg: str):
    """Print success message."""
    print(f"{Color.GREEN}✓ {msg}{Color.END}")


def print_error(msg: str):
    """Print error message."""
    print(f"{Color.RED}✗ {msg}{Color.END}")


def print_warning(msg: str):
    """Print warning message."""
    print(f"{Color.YELLOW}⚠ {msg}{Color.END}")


def print_info(msg: str):
    """Print info message."""
    print(f"{Color.BLUE}ℹ {msg}{Color.END}")


class KFPSubmitter:
    """Handles KFP v2 pipeline compilation, upload, and execution."""
    
    def __init__(
        self,
        kfp_host: str,
        namespace: str = "kubeflow",
        skip_compile: bool = False,
        pipeline_spec_path: Optional[Path] = None,
        dry_run: bool = False,
    ):
        self.kfp_host = kfp_host
        self.namespace = namespace
        self.skip_compile = skip_compile
        self.pipeline_spec_path = pipeline_spec_path or Path("artifacts/flts_pipeline_v2.json")
        self.dry_run = dry_run
        self.client: Optional[Client] = None
        
        # Paths
        self.repo_root = Path(__file__).parent.parent
        self.artifacts_dir = self.repo_root / "artifacts"
        self.artifacts_dir.mkdir(exist_ok=True)
        
    def compile_pipeline(self) -> bool:
        """Compile pipeline to KFP v2 IR spec."""
        print_step("1/5", "Compiling Pipeline")
        
        if self.skip_compile and self.pipeline_spec_path.exists():
            print_info(f"Skipping compilation (using existing spec)")
            print_info(f"Spec: {self.pipeline_spec_path}")
            return True
        
        try:
            print_info(f"Pipeline function: flts_pipeline")
            print_info(f"Output path: {self.pipeline_spec_path}")
            
            compiler.Compiler().compile(
                pipeline_func=flts_pipeline,
                package_path=str(self.pipeline_spec_path),
            )
            
            if not self.pipeline_spec_path.exists():
                raise FileNotFoundError(f"Compiled spec not found: {self.pipeline_spec_path}")
            
            file_size = self.pipeline_spec_path.stat().st_size
            print_success(f"Compilation successful ({file_size:,} bytes)")
            
            # Validate JSON structure
            with open(self.pipeline_spec_path) as f:
                spec = json.load(f)
                print_info(f"Pipeline name: {spec.get('pipelineInfo', {}).get('name', 'N/A')}")
                print_info(f"SDK version: {spec.get('sdkVersion', 'N/A')}")
            
            return True
            
        except Exception as e:
            print_error(f"Compilation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def connect_to_kfp(self) -> bool:
        """Establish connection to KFP API server."""
        print_step("2/5", "Connecting to KFP")
        
        if self.dry_run:
            print_warning("Dry run mode - skipping KFP connection")
            return True
        
        try:
            print_info(f"KFP host: {self.kfp_host}")
            print_info(f"Namespace: {self.namespace}")
            
            self.client = Client(
                host=self.kfp_host,
                namespace=self.namespace,
            )
            
            # Test connection
            print_info("Testing connection...")
            
            # Try to list experiments (validates auth and connectivity)
            experiments = self.client.list_experiments(page_size=1)
            print_success(f"Connected to KFP API (found {experiments.total_size or 0} experiments)")
            
            return True
            
        except Exception as e:
            print_error(f"Connection failed: {e}")
            print_info("\nTroubleshooting:")
            print_info("  1. Verify KFP is running: kubectl get pods -n kubeflow")
            print_info("  2. Port-forward if needed: kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80")
            print_info("  3. Check --host parameter matches your setup")
            return False
    
    def upload_pipeline(self, pipeline_name: str) -> Optional[str]:
        """Upload pipeline to KFP."""
        print_step("3/5", "Uploading Pipeline")
        
        if self.dry_run:
            print_warning("Dry run mode - skipping upload")
            return "dry-run-pipeline-id"
        
        try:
            # Check if pipeline already exists
            existing = None
            try:
                pipelines = self.client.list_pipelines(page_size=100)
                for pipeline in (pipelines.pipelines or []):
                    if pipeline.display_name == pipeline_name:
                        existing = pipeline
                        break
            except:
                pass
            
            if existing:
                print_info(f"Pipeline '{pipeline_name}' already exists (ID: {existing.pipeline_id})")
                print_info("Creating new version...")
                
                # Upload new version
                pipeline = self.client.upload_pipeline_version(
                    pipeline_package_path=str(self.pipeline_spec_path),
                    pipeline_id=existing.pipeline_id,
                    pipeline_version_name=f"v{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                )
                
                pipeline_id = existing.pipeline_id
                print_success(f"New version uploaded: {pipeline.name}")
                
            else:
                print_info(f"Uploading new pipeline: {pipeline_name}")
                
                pipeline = self.client.upload_pipeline(
                    pipeline_package_path=str(self.pipeline_spec_path),
                    pipeline_name=pipeline_name,
                )
                
                pipeline_id = pipeline.pipeline_id
                print_success(f"Pipeline uploaded: {pipeline_name}")
            
            print_info(f"Pipeline ID: {pipeline_id}")
            return pipeline_id
            
        except Exception as e:
            print_error(f"Upload failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_experiment(self, experiment_name: str) -> Optional[str]:
        """Create or get experiment."""
        print_step("4/5", "Setting Up Experiment")
        
        if self.dry_run:
            print_warning("Dry run mode - skipping experiment creation")
            return "dry-run-experiment-id"
        
        try:
            # Try to get existing experiment
            experiment = None
            try:
                experiment = self.client.get_experiment(experiment_name=experiment_name)
                print_info(f"Using existing experiment: {experiment_name}")
            except:
                # Create new experiment
                print_info(f"Creating new experiment: {experiment_name}")
                experiment = self.client.create_experiment(name=experiment_name)
                print_success(f"Experiment created: {experiment_name}")
            
            experiment_id = experiment.experiment_id
            print_info(f"Experiment ID: {experiment_id}")
            
            return experiment_id
            
        except Exception as e:
            print_error(f"Experiment setup failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_run(
        self,
        experiment_id: str,
        run_name: str,
        pipeline_params: dict,
    ) -> Optional[str]:
        """Create and start pipeline run."""
        print_step("5/5", "Starting Pipeline Run")
        
        if self.dry_run:
            print_warning("Dry run mode - skipping run creation")
            print_info(f"Would start run with parameters:")
            for key, value in pipeline_params.items():
                print_info(f"  {key}: {value}")
            return "dry-run-run-id"
        
        try:
            print_info(f"Run name: {run_name}")
            print_info(f"Parameters:")
            for key, value in pipeline_params.items():
                print_info(f"  {key}: {value}")
            
            # Create run from pipeline package
            run = self.client.create_run_from_pipeline_package(
                pipeline_file=str(self.pipeline_spec_path),
                experiment_id=experiment_id,
                run_name=run_name,
                arguments=pipeline_params,
                enable_caching=False,  # Disable caching for reproducibility
            )
            
            run_id = run.run_id
            print_success(f"Run started successfully")
            print_info(f"Run ID: {run_id}")
            
            # Construct UI URL
            ui_url = self.kfp_host.replace('/apis/v2beta1', '')
            run_url = f"{ui_url}/#/runs/details/{run_id}"
            print_info(f"View in UI: {run_url}")
            
            return run_id
            
        except Exception as e:
            print_error(f"Run creation failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def submit_pipeline(
        self,
        pipeline_name: str,
        experiment_name: str,
        run_name: str,
        pipeline_params: dict,
    ) -> bool:
        """Execute complete submission workflow."""
        print_header("KFP v2 Pipeline Submission")
        
        # Print configuration
        print_info(f"KFP Host: {self.kfp_host}")
        print_info(f"Namespace: {self.namespace}")
        print_info(f"Pipeline: {pipeline_name}")
        print_info(f"Experiment: {experiment_name}")
        print_info(f"Run: {run_name}")
        print_info(f"Dry Run: {self.dry_run}")
        
        # Step 1: Compile
        if not self.compile_pipeline():
            return False
        
        # Step 2: Connect to KFP
        if not self.connect_to_kfp():
            return False
        
        # Step 3: Upload pipeline
        pipeline_id = self.upload_pipeline(pipeline_name)
        if not pipeline_id:
            return False
        
        # Step 4: Create experiment
        experiment_id = self.create_experiment(experiment_name)
        if not experiment_id:
            return False
        
        # Step 5: Create and start run
        run_id = self.create_run(experiment_id, run_name, pipeline_params)
        if not run_id:
            return False
        
        # Success summary
        print_header("Submission Complete")
        print_success("Pipeline submitted successfully")
        print()
        print(f"{Color.BOLD}Run Details:{Color.END}")
        print(f"  Pipeline ID:   {pipeline_id}")
        print(f"  Experiment ID: {experiment_id}")
        print(f"  Run ID:        {run_id}")
        print()
        
        if not self.dry_run:
            print(f"{Color.BOLD}Next Steps:{Color.END}")
            print(f"  1. Monitor run in KFP UI")
            print(f"  2. Check pod logs: kubectl logs -n {self.namespace} <pod-name>")
            print(f"  3. Validate artifacts in MinIO")
            print(f"  4. Verify MLflow tracking")
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Submit KFP v2 pipeline for FLTS forecasting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Standard submission
  python submit_run_v2.py
  
  # Skip compilation (use existing spec)
  python submit_run_v2.py --skip-compile
  
  # Custom experiment and run names
  python submit_run_v2.py --experiment step10-test --run test-001
  
  # Custom parameters
  python submit_run_v2.py --dataset ElBorn --identifier custom-run-001
  
  # Dry run (validate without executing)
  python submit_run_v2.py --dry-run
  
  # Custom KFP host (port-forwarded)
  python submit_run_v2.py --host http://localhost:8080
        """,
    )
    
    # Connection parameters
    parser.add_argument(
        "--host",
        default=os.getenv("KFP_HOST", "http://localhost:8080"),
        help="KFP API server host (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--namespace",
        default=os.getenv("KFP_NAMESPACE", "kubeflow"),
        help="Kubernetes namespace (default: kubeflow)",
    )
    
    # Pipeline parameters
    parser.add_argument(
        "--pipeline-name",
        default="flts-time-series-pipeline-v2",
        help="Pipeline name in KFP (default: flts-time-series-pipeline-v2)",
    )
    parser.add_argument(
        "--experiment",
        default=f"step10-{datetime.now().strftime('%Y%m%d')}",
        help="Experiment name (default: step10-YYYYMMDD)",
    )
    parser.add_argument(
        "--run",
        default=f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        help="Run name (default: run-YYYYMMDD-HHMMSS)",
    )
    
    # Runtime parameters
    parser.add_argument(
        "--dataset",
        default="PobleSec",
        choices=["PobleSec", "ElBorn", "LesCorts"],
        help="Dataset name (default: PobleSec)",
    )
    parser.add_argument(
        "--identifier",
        default="default-run",
        help="Run identifier for tracking (default: default-run)",
    )
    parser.add_argument(
        "--gateway-url",
        help="Override gateway URL (default: from runtime_defaults)",
    )
    parser.add_argument(
        "--mlflow-uri",
        help="Override MLflow tracking URI (default: from runtime_defaults)",
    )
    
    # Compilation options
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Skip compilation (use existing pipeline spec)",
    )
    parser.add_argument(
        "--pipeline-spec",
        type=Path,
        default=Path("artifacts/flts_pipeline_v2.json"),
        help="Path to pipeline spec (default: artifacts/flts_pipeline_v2.json)",
    )
    
    # Execution options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compile and validate only (don't submit to KFP)",
    )
    
    args = parser.parse_args()
    
    # Load runtime configuration
    config = RuntimeConfig()
    
    # Build pipeline parameters
    pipeline_params = {
        "dataset_name": args.dataset,
        "identifier": args.identifier,
        "gateway_url": args.gateway_url or config.gateway_url,
        "mlflow_tracking_uri": args.mlflow_uri or config.mlflow_tracking_uri,
        # Add more parameters as needed
        "hidden_size": 64,
        "num_layers": 2,
        "dropout": 0.2,
        "learning_rate": 0.001,
        "batch_size": 32,
        "num_epochs": 50,
    }
    
    # Create submitter
    submitter = KFPSubmitter(
        kfp_host=args.host,
        namespace=args.namespace,
        skip_compile=args.skip_compile,
        pipeline_spec_path=args.pipeline_spec,
        dry_run=args.dry_run,
    )
    
    # Submit pipeline
    success = submitter.submit_pipeline(
        pipeline_name=args.pipeline_name,
        experiment_name=args.experiment,
        run_name=args.run,
        pipeline_params=pipeline_params,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
