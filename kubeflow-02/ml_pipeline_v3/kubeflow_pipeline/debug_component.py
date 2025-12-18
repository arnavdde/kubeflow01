"""
Debug Component for Step 10 - Infrastructure Validation

This component tests DNS resolution and HTTP connectivity to all required services
before running the main pipeline. It helps catch 80% of Step 10 configuration issues.

Usage:
    # Standalone test
    python debug_component_test.py
    
    # In pipeline (add as first task)
    from kubeflow_pipeline.debug_component import debug_infrastructure_component
    
    debug_task = debug_infrastructure_component(
        minio_endpoint="minio-service.default.svc.cluster.local:9000",
        mlflow_uri="http://mlflow.default.svc.cluster.local:5000",
        gateway_url="http://fastapi-app.default.svc.cluster.local:8000",
    )
"""

from kfp import dsl


@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["requests>=2.31.0", "boto3>=1.28.0"],
)
def debug_infrastructure_component(
    validation_report: dsl.OutputPath(str),
    minio_endpoint: str = "minio-service.default.svc.cluster.local:9000",
    minio_access_key: str = "minioadmin",
    minio_secret_key: str = "minioadmin",
    mlflow_uri: str = "http://mlflow.default.svc.cluster.local:5000",
    gateway_url: str = "http://fastapi-app.default.svc.cluster.local:8000",
    postgres_host: str = "postgres.default.svc.cluster.local",
    postgres_port: int = 5432,
):
    """
    Validate infrastructure connectivity for FLTS pipeline.
    
    Tests:
    1. DNS resolution for all service hostnames
    2. HTTP health checks (MinIO, MLflow, Gateway)
    3. MinIO S3 API connectivity
    4. Postgres connectivity (for MLflow backend)
    
    Args:
        validation_report: Output path for validation results (JSON)
        minio_endpoint: MinIO endpoint (host:port)
        minio_access_key: MinIO access key
        minio_secret_key: MinIO secret key
        mlflow_uri: MLflow tracking URI
        gateway_url: FastAPI gateway URL
        postgres_host: Postgres hostname
        postgres_port: Postgres port
    """
    import json
    import os
    import socket
    import sys
    from datetime import datetime
    from urllib.parse import urlparse
    
    # Import installed packages
    import requests
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError
    
    # Results accumulator
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "tests": [],
        "summary": {"total": 0, "passed": 0, "failed": 0},
    }
    
    def add_result(test_name: str, status: str, details: str = ""):
        """Add test result to accumulator."""
        results["tests"].append({
            "name": test_name,
            "status": status,
            "details": details,
        })
        results["summary"]["total"] += 1
        if status == "PASS":
            results["summary"]["passed"] += 1
        else:
            results["summary"]["failed"] += 1
    
    def print_header(msg: str):
        """Print section header."""
        print("\n" + "=" * 70)
        print(msg)
        print("=" * 70)
    
    def test_dns_resolution(hostname: str) -> bool:
        """Test DNS resolution for a hostname."""
        try:
            # Remove port if present
            host = hostname.split(":")[0]
            ip = socket.gethostbyname(host)
            add_result(
                f"DNS: {hostname}",
                "PASS",
                f"Resolved to {ip}"
            )
            print(f"✓ DNS: {hostname} → {ip}")
            return True
        except socket.gaierror as e:
            add_result(
                f"DNS: {hostname}",
                "FAIL",
                f"Resolution failed: {e}"
            )
            print(f"✗ DNS: {hostname} - FAILED: {e}")
            return False
    
    def test_http_health(url: str, endpoint: str = "/") -> bool:
        """Test HTTP connectivity to a service."""
        full_url = f"{url}{endpoint}"
        try:
            response = requests.get(full_url, timeout=10)
            if response.status_code < 500:  # Accept 2xx, 3xx, 4xx (service is responding)
                add_result(
                    f"HTTP: {url}",
                    "PASS",
                    f"Status {response.status_code}"
                )
                print(f"✓ HTTP: {url} - Status {response.status_code}")
                return True
            else:
                add_result(
                    f"HTTP: {url}",
                    "FAIL",
                    f"Status {response.status_code}"
                )
                print(f"✗ HTTP: {url} - FAILED: Status {response.status_code}")
                return False
        except requests.RequestException as e:
            add_result(
                f"HTTP: {url}",
                "FAIL",
                f"Connection failed: {e}"
            )
            print(f"✗ HTTP: {url} - FAILED: {e}")
            return False
    
    def test_minio_s3_api() -> bool:
        """Test MinIO S3 API connectivity."""
        try:
            # Parse endpoint
            if not minio_endpoint.startswith("http"):
                endpoint_url = f"http://{minio_endpoint}"
            else:
                endpoint_url = minio_endpoint
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=minio_access_key,
                aws_secret_access_key=minio_secret_key,
                region_name='us-east-1',
            )
            
            # List buckets (should work even if empty)
            response = s3_client.list_buckets()
            bucket_count = len(response.get('Buckets', []))
            
            add_result(
                "MinIO S3 API",
                "PASS",
                f"Connected successfully, {bucket_count} buckets found"
            )
            print(f"✓ MinIO S3 API: {bucket_count} buckets found")
            return True
            
        except (ClientError, EndpointConnectionError) as e:
            add_result(
                "MinIO S3 API",
                "FAIL",
                f"Connection failed: {e}"
            )
            print(f"✗ MinIO S3 API - FAILED: {e}")
            return False
    
    def test_postgres_connection() -> bool:
        """Test Postgres connectivity (basic socket test)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((postgres_host.split(":")[0], postgres_port))
            sock.close()
            
            if result == 0:
                add_result(
                    f"Postgres: {postgres_host}:{postgres_port}",
                    "PASS",
                    "Port is open"
                )
                print(f"✓ Postgres: {postgres_host}:{postgres_port} - Port is open")
                return True
            else:
                add_result(
                    f"Postgres: {postgres_host}:{postgres_port}",
                    "FAIL",
                    f"Port is closed (error code {result})"
                )
                print(f"✗ Postgres: {postgres_host}:{postgres_port} - Port is closed")
                return False
                
        except Exception as e:
            add_result(
                f"Postgres: {postgres_host}:{postgres_port}",
                "FAIL",
                f"Connection test failed: {e}"
            )
            print(f"✗ Postgres: {postgres_host}:{postgres_port} - FAILED: {e}")
            return False
    
    # ========================================================================
    # Main Validation Sequence
    # ========================================================================
    
    print_header("FLTS Pipeline Infrastructure Validation")
    
    # Extract hostnames
    minio_host = minio_endpoint.split(":")[0]
    mlflow_host = urlparse(mlflow_uri).netloc.split(":")[0]
    gateway_host = urlparse(gateway_url).netloc.split(":")[0]
    
    # Test 1: DNS Resolution
    print_header("Test 1: DNS Resolution")
    dns_results = [
        test_dns_resolution(minio_host),
        test_dns_resolution(mlflow_host),
        test_dns_resolution(gateway_host),
        test_dns_resolution(postgres_host),
    ]
    
    # Test 2: HTTP Health Checks
    print_header("Test 2: HTTP Health Checks")
    http_results = [
        test_http_health(f"http://{minio_endpoint}", "/minio/health/live"),
        test_http_health(mlflow_uri, "/health"),
        test_http_health(gateway_url, "/"),
    ]
    
    # Test 3: MinIO S3 API
    print_header("Test 3: MinIO S3 API Connectivity")
    minio_result = test_minio_s3_api()
    
    # Test 4: Postgres Connection
    print_header("Test 4: Postgres Connection (MLflow Backend)")
    postgres_result = test_postgres_connection()
    
    # Summary
    print_header("Validation Summary")
    print(f"Total Tests:  {results['summary']['total']}")
    print(f"Passed:       {results['summary']['passed']}")
    print(f"Failed:       {results['summary']['failed']}")
    print()
    
    if results['summary']['failed'] > 0:
        print("❌ VALIDATION FAILED - Some services are unreachable")
        print("\nFailed Tests:")
        for test in results['tests']:
            if test['status'] == 'FAIL':
                print(f"  - {test['name']}: {test['details']}")
        print("\nTroubleshooting:")
        print("  1. Check service pods: kubectl get pods -A")
        print("  2. Check service endpoints: kubectl get svc -A")
        print("  3. Check DNS: kubectl run -it --rm debug --image=busybox -- nslookup <hostname>")
        print("  4. Check connectivity: kubectl run -it --rm debug --image=curlimages/curl -- curl -v <url>")
        sys.exit(1)
    else:
        print("✅ ALL VALIDATIONS PASSED - Infrastructure is ready")
    
    # Write report
    with open(validation_report, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Validation report written to: {validation_report}")
    print("=" * 70)


# ============================================================================
# Standalone Test Script
# ============================================================================

if __name__ == "__main__":
    """
    Test the debug component locally.
    
    Usage:
        python debug_component.py
        
        # With custom endpoints
        MINIO_ENDPOINT=localhost:9000 \
        MLFLOW_URI=http://localhost:5000 \
        GATEWAY_URL=http://localhost:8000 \
        python debug_component.py
    """
    import os
    import tempfile
    
    # Get config from environment
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio-service.default.svc.cluster.local:9000")
    mlflow_uri = os.getenv("MLFLOW_URI", "http://mlflow.default.svc.cluster.local:5000")
    gateway_url = os.getenv("GATEWAY_URL", "http://fastapi-app.default.svc.cluster.local:8000")
    
    # Create temp file for report
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        report_path = f.name
    
    print("Testing debug component with configuration:")
    print(f"  MinIO Endpoint:  {minio_endpoint}")
    print(f"  MLflow URI:      {mlflow_uri}")
    print(f"  Gateway URL:     {gateway_url}")
    print(f"  Report Path:     {report_path}")
    
    try:
        # Call component function directly
        debug_infrastructure_component.python_func(
            validation_report=report_path,
            minio_endpoint=minio_endpoint,
            mlflow_uri=mlflow_uri,
            gateway_url=gateway_url,
        )
        
        # Print report
        print("\n" + "=" * 70)
        print("Validation Report:")
        print("=" * 70)
        with open(report_path) as f:
            import json
            report = json.load(f)
            print(json.dumps(report, indent=2))
        
    except SystemExit as e:
        if e.code != 0:
            print("\n❌ Validation failed")
            import sys
            sys.exit(1)
    finally:
        # Cleanup
        if os.path.exists(report_path):
            os.unlink(report_path)
    
    print("\n✅ Debug component test complete")
