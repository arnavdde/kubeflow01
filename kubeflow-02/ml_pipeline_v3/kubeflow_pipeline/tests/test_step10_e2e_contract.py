"""
Step 10 End-to-End Contract Validation

Validates that a completed KFP pipeline run has produced all expected artifacts
and metadata. This is the acceptance test for Step 10 completion.

Usage:
    # Validate specific run
    python test_step10_e2e_contract.py --run-id <run-id>
    
    # Validate latest run in experiment
    python test_step10_e2e_contract.py --experiment step10-test --latest
    
    # Dry run (check tool connectivity only)
    python test_step10_e2e_contract.py --dry-run

Requirements:
    - kfp (for KFP API access)
    - boto3 (for MinIO validation)
    - requests (for MLflow API)
    - kubectl configured (for direct pod inspection)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

try:
    import requests
    import boto3
    from botocore.exceptions import ClientError
    import kfp
    from kfp.client import Client
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Install with: pip install kfp boto3 requests")
    sys.exit(1)

# Add parent for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from kubeflow_pipeline.config.runtime_defaults import RuntimeConfig


class Color:
    """Terminal colors."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(msg: str):
    print(f"\n{Color.BOLD}{'='*80}{Color.END}")
    print(f"{Color.BOLD}{msg}{Color.END}")
    print(f"{Color.BOLD}{'='*80}{Color.END}\n")


def print_test(name: str, status: str, details: str = ""):
    """Print test result."""
    if status == "PASS":
        icon = f"{Color.GREEN}✓{Color.END}"
        status_text = f"{Color.GREEN}PASS{Color.END}"
    elif status == "FAIL":
        icon = f"{Color.RED}✗{Color.END}"
        status_text = f"{Color.RED}FAIL{Color.END}"
    elif status == "WARN":
        icon = f"{Color.YELLOW}⚠{Color.END}"
        status_text = f"{Color.YELLOW}WARN{Color.END}"
    else:
        icon = f"{Color.BLUE}ℹ{Color.END}"
        status_text = f"{Color.BLUE}{status}{Color.END}"
    
    print(f"{icon} {name:<50} [{status_text}]")
    if details:
        print(f"    {details}")


class Step10Validator:
    """Validates Step 10 E2E pipeline run."""
    
    def __init__(
        self,
        run_id: str,
        kfp_host: str,
        namespace: str,
        config: RuntimeConfig,
    ):
        self.run_id = run_id
        self.kfp_host = kfp_host
        self.namespace = namespace
        self.config = config
        
        self.kfp_client: Optional[Client] = None
        self.s3_client = None
        
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "tests": [],
            "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0},
        }
    
    def add_result(self, test_name: str, status: str, details: str = ""):
        """Record test result."""
        self.results["tests"].append({
            "name": test_name,
            "status": status,
            "details": details,
        })
        self.results["summary"]["total"] += 1
        
        if status == "PASS":
            self.results["summary"]["passed"] += 1
        elif status == "FAIL":
            self.results["summary"]["failed"] += 1
        elif status == "WARN":
            self.results["summary"]["warnings"] += 1
        
        print_test(test_name, status, details)
    
    def setup_clients(self) -> bool:
        """Initialize KFP and MinIO clients."""
        print_header("Setting Up Clients")
        
        try:
            # KFP Client
            self.kfp_client = Client(host=self.kfp_host, namespace=self.namespace)
            self.add_result("KFP Client", "PASS", f"Connected to {self.kfp_host}")
            
            # S3/MinIO Client
            endpoint_url = self.config.minio_endpoint
            if not endpoint_url.startswith("http"):
                endpoint_url = f"http://{endpoint_url}"
            
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=self.config.minio_access_key,
                aws_secret_access_key=self.config.minio_secret_key,
                region_name='us-east-1',
            )
            
            # Test MinIO connection
            self.s3_client.list_buckets()
            self.add_result("MinIO Client", "PASS", f"Connected to {endpoint_url}")
            
            return True
            
        except Exception as e:
            self.add_result("Client Setup", "FAIL", str(e))
            return False
    
    def validate_kfp_run_status(self) -> bool:
        """Validate KFP run completed successfully."""
        print_header("Test 1: KFP Run Status")
        
        try:
            run = self.kfp_client.get_run(self.run_id)
            
            # Check run status
            status = run.run.status if hasattr(run.run, 'status') else "UNKNOWN"
            
            # Get state (KFP v2 uses state field)
            state = None
            if hasattr(run.run, 'state'):
                state = run.run.state
            
            self.add_result(
                "Run Status",
                "PASS" if state == "SUCCEEDED" or status == "Succeeded" else "FAIL",
                f"State: {state or status}"
            )
            
            # Check run metadata
            if hasattr(run.run, 'created_at'):
                created_at = run.run.created_at
                self.add_result("Run Created", "PASS", f"At {created_at}")
            
            if hasattr(run.run, 'finished_at'):
                finished_at = run.run.finished_at
                if finished_at:
                    self.add_result("Run Finished", "PASS", f"At {finished_at}")
                else:
                    self.add_result("Run Finished", "WARN", "Still running or no finish time")
            
            return state == "SUCCEEDED" or status == "Succeeded"
            
        except Exception as e:
            self.add_result("KFP Run Validation", "FAIL", str(e))
            return False
    
    def validate_minio_artifacts(self) -> bool:
        """Validate expected artifacts exist in MinIO."""
        print_header("Test 2: MinIO Artifacts")
        
        # Expected artifacts (adjust paths based on your pipeline)
        expected_objects = [
            (self.config.bucket_processed, "processed_data.parquet", "Training data"),
            (self.config.bucket_processed, ".meta.json", "Metadata sidecar"),
            (self.config.bucket_predictions, "predictions/", "Predictions directory"),
        ]
        
        all_passed = True
        
        for bucket, prefix, description in expected_objects:
            try:
                # List objects with prefix
                response = self.s3_client.list_objects_v2(
                    Bucket=bucket,
                    Prefix=prefix,
                    MaxKeys=10,
                )
                
                if response.get('KeyCount', 0) > 0:
                    keys = [obj['Key'] for obj in response.get('Contents', [])]
                    self.add_result(
                        f"MinIO: {description}",
                        "PASS",
                        f"Found in {bucket}/{prefix} ({response['KeyCount']} objects)"
                    )
                else:
                    self.add_result(
                        f"MinIO: {description}",
                        "FAIL",
                        f"No objects found in {bucket}/{prefix}"
                    )
                    all_passed = False
                    
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchBucket':
                    self.add_result(
                        f"MinIO: {description}",
                        "FAIL",
                        f"Bucket '{bucket}' does not exist"
                    )
                else:
                    self.add_result(
                        f"MinIO: {description}",
                        "FAIL",
                        f"Error: {e}"
                    )
                all_passed = False
            except Exception as e:
                self.add_result(
                    f"MinIO: {description}",
                    "FAIL",
                    str(e)
                )
                all_passed = False
        
        # Check model promotion pointer
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.bucket_promotion,
                Key="current.json",
            )
            pointer_data = json.loads(response['Body'].read())
            
            self.add_result(
                "Model Promotion Pointer",
                "PASS",
                f"Best model: {pointer_data.get('model_type', 'N/A')}"
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                self.add_result(
                    "Model Promotion Pointer",
                    "WARN",
                    "No current.json found (eval may not have run)"
                )
            else:
                self.add_result("Model Promotion Pointer", "FAIL", str(e))
                all_passed = False
        except Exception as e:
            self.add_result("Model Promotion Pointer", "FAIL", str(e))
            all_passed = False
        
        return all_passed
    
    def validate_mlflow_runs(self) -> bool:
        """Validate MLflow tracking data."""
        print_header("Test 3: MLflow Experiment Tracking")
        
        try:
            mlflow_api = self.config.mlflow_tracking_uri.rstrip('/')
            
            # Search for runs (simple health check)
            response = requests.get(
                f"{mlflow_api}/api/2.0/mlflow/runs/search",
                params={"max_results": 10},
                timeout=10,
            )
            
            if response.status_code == 200:
                data = response.json()
                runs = data.get('runs', [])
                
                self.add_result(
                    "MLflow API",
                    "PASS",
                    f"Found {len(runs)} recent runs"
                )
                
                # Check if any runs have our identifier
                # (This is a weak test - ideally query by tag/param)
                if len(runs) > 0:
                    self.add_result(
                        "MLflow Run Exists",
                        "PASS",
                        f"Recent run ID: {runs[0]['info']['run_id'][:8]}..."
                    )
                else:
                    self.add_result(
                        "MLflow Run Exists",
                        "WARN",
                        "No recent runs found"
                    )
                
                return True
            else:
                self.add_result(
                    "MLflow API",
                    "FAIL",
                    f"Status {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.add_result("MLflow Validation", "FAIL", str(e))
            return False
    
    def validate_gateway_response(self) -> bool:
        """Validate gateway is responding (optional)."""
        print_header("Test 4: Gateway Availability")
        
        try:
            response = requests.get(
                f"{self.config.gateway_url}/",
                timeout=5,
            )
            
            if response.status_code < 500:
                self.add_result(
                    "Gateway Health",
                    "PASS",
                    f"Status {response.status_code}"
                )
                return True
            else:
                self.add_result(
                    "Gateway Health",
                    "WARN",
                    f"Status {response.status_code} (still accessible)"
                )
                return True
                
        except Exception as e:
            self.add_result("Gateway Health", "WARN", f"Not accessible: {e}")
            return True  # Non-critical
    
    def run_validation(self) -> bool:
        """Execute full validation suite."""
        print_header(f"Step 10 E2E Validation - Run {self.run_id}")
        
        # Setup
        if not self.setup_clients():
            return False
        
        # Run tests
        test_results = [
            self.validate_kfp_run_status(),
            self.validate_minio_artifacts(),
            self.validate_mlflow_runs(),
            self.validate_gateway_response(),
        ]
        
        # Summary
        print_header("Validation Summary")
        print(f"Total Tests:  {self.results['summary']['total']}")
        print(f"Passed:       {Color.GREEN}{self.results['summary']['passed']}{Color.END}")
        print(f"Failed:       {Color.RED}{self.results['summary']['failed']}{Color.END}")
        print(f"Warnings:     {Color.YELLOW}{self.results['summary']['warnings']}{Color.END}")
        print()
        
        # Verdict
        if self.results['summary']['failed'] > 0:
            print(f"{Color.RED}❌ VALIDATION FAILED{Color.END}")
            print("\nFailed Tests:")
            for test in self.results['tests']:
                if test['status'] == 'FAIL':
                    print(f"  - {test['name']}: {test['details']}")
            return False
        elif self.results['summary']['warnings'] > 0:
            print(f"{Color.YELLOW}⚠ VALIDATION PASSED WITH WARNINGS{Color.END}")
            print("\nWarnings:")
            for test in self.results['tests']:
                if test['status'] == 'WARN':
                    print(f"  - {test['name']}: {test['details']}")
            return True
        else:
            print(f"{Color.GREEN}✅ ALL VALIDATIONS PASSED{Color.END}")
            return True
    
    def save_report(self, output_path: Path):
        """Save validation report to JSON."""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n✓ Report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate Step 10 E2E pipeline run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--run-id",
        help="KFP run ID to validate",
    )
    parser.add_argument(
        "--experiment",
        help="Experiment name (used with --latest)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Validate latest run in experiment",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("KFP_HOST", "http://localhost:8080"),
        help="KFP API host",
    )
    parser.add_argument(
        "--namespace",
        default=os.getenv("KFP_NAMESPACE", "kubeflow"),
        help="Kubernetes namespace",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("migration/step10/validation_report.json"),
        help="Output path for validation report",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test connectivity only (no validation)",
    )
    
    args = parser.parse_args()
    
    # Load config
    config = RuntimeConfig()
    
    # Determine run ID
    run_id = args.run_id
    
    if not run_id and args.latest:
        # Get latest run from experiment
        try:
            client = Client(host=args.host, namespace=args.namespace)
            experiment = client.get_experiment(experiment_name=args.experiment)
            runs = client.list_runs(experiment_id=experiment.experiment_id, page_size=1)
            
            if runs.runs:
                run_id = runs.runs[0].run_id
                print(f"Using latest run: {run_id}")
            else:
                print("Error: No runs found in experiment")
                sys.exit(1)
        except Exception as e:
            print(f"Error fetching latest run: {e}")
            sys.exit(1)
    
    if not run_id and not args.dry_run:
        print("Error: Must specify --run-id or --experiment with --latest")
        sys.exit(1)
    
    # Dry run mode
    if args.dry_run:
        print_header("Dry Run - Testing Connectivity")
        validator = Step10Validator(
            run_id="dry-run",
            kfp_host=args.host,
            namespace=args.namespace,
            config=config,
        )
        success = validator.setup_clients()
        sys.exit(0 if success else 1)
    
    # Run validation
    validator = Step10Validator(
        run_id=run_id,
        kfp_host=args.host,
        namespace=args.namespace,
        config=config,
    )
    
    success = validator.run_validation()
    
    # Save report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    validator.save_report(args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
