# Secrets and Endpoints Strategy

**Date**: December 17, 2025  
**Objective**: Document how KFP v2 pipeline components receive credentials and service endpoints

---

## Overview

The FLTS pipeline requires access to three external services:
1. **MinIO** - Object storage for datasets, models, and artifacts
2. **MLflow** - Experiment tracking and model registry
3. **FastAPI Gateway** - HTTP interface to MinIO (optional convenience layer)

This document defines the **single source of truth** for how components discover and authenticate to these services.

---

## Strategy: Environment Variables + Runtime Parameters

**Chosen Approach**: Hybrid configuration via KFP pipeline parameters + Kubernetes ConfigMap/Secrets

**Rationale**:
- ✅ Explicit and traceable (parameters visible in KFP UI)
- ✅ Override-friendly (can customize per run without code changes)
- ✅ Kubernetes-native (leverages ConfigMap for config, Secret for credentials)
- ✅ No hidden state (all values passed explicitly or defaulted visibly)

**Rejected Approaches**:
- ❌ Hardcoded values - No flexibility, security risk
- ❌ ServiceAccount auto-discovery - Too implicit, hard to debug
- ❌ Per-component Secrets - Duplication, harder to manage

---

## Implementation Details

### 1. Configuration Source Hierarchy

Components resolve configuration in this order (first match wins):

1. **KFP Pipeline Parameters** (highest priority)
   - Passed at run creation time via `submit_run_v2.py`
   - Example: `--gateway-url http://custom-gateway:8000`

2. **Kubernetes ConfigMap** (cluster defaults)
   - Namespace-scoped configuration
   - Applied once, used by all runs
   - Example: `kubectl create configmap flts-config --from-literal=MINIO_ENDPOINT=minio-service:9000`

3. **Kubernetes Secret** (sensitive credentials)
   - Namespace-scoped secrets
   - Injected as environment variables
   - Example: `kubectl create secret generic flts-secrets --from-literal=MINIO_ACCESS_KEY=minioadmin`

4. **Python Code Defaults** (fallback)
   - Defined in `kubeflow_pipeline/config/runtime_defaults.py`
   - Development/Minikube-friendly defaults
   - Used if no overrides provided

### 2. In-Cluster DNS Endpoints

**Assumption**: All services deployed in `default` namespace on Minikube.

| Service | Kubernetes Service Name | In-Cluster DNS | External Port |
|---------|------------------------|----------------|---------------|
| MinIO | `minio-service` | `minio-service.default.svc.cluster.local:9000` | `localhost:9000` (port-forward) |
| MLflow | `mlflow` | `mlflow.default.svc.cluster.local:5000` | `localhost:5000` (port-forward) |
| Gateway | `fastapi-app` | `fastapi-app.default.svc.cluster.local:8000` | `localhost:8000` (port-forward) |
| Postgres | `postgres` | `postgres.default.svc.cluster.local:5432` | `localhost:5432` (port-forward) |

**Note**: If services are in a different namespace (e.g., `flts-prod`), update DNS to:
```
<service-name>.<namespace>.svc.cluster.local:<port>
```

### 3. Environment Variables Used by Components

All KFP components receive these environment variables (via pipeline parameters or ConfigMap/Secret):

#### MinIO Configuration
```bash
MINIO_ENDPOINT=minio-service.default.svc.cluster.local:9000
MINIO_ACCESS_KEY=minioadmin         # From Secret
MINIO_SECRET_KEY=minioadmin         # From Secret
MINIO_SECURE=false                  # true for HTTPS
AWS_ACCESS_KEY_ID=minioadmin        # Alias for boto3
AWS_SECRET_ACCESS_KEY=minioadmin    # Alias for boto3
AWS_S3_ENDPOINT_URL=http://minio-service.default.svc.cluster.local:9000
AWS_DEFAULT_REGION=us-east-1
AWS_S3_ADDRESSING_STYLE=path
```

#### MLflow Configuration
```bash
MLFLOW_TRACKING_URI=http://mlflow.default.svc.cluster.local:5000
MLFLOW_S3_ENDPOINT_URL=http://minio-service.default.svc.cluster.local:9000
```

#### Gateway Configuration
```bash
GATEWAY_URL=http://fastapi-app.default.svc.cluster.local:8000
```

#### Bucket Names
```bash
BUCKET_DATASET=dataset
BUCKET_PROCESSED=processed-data
BUCKET_MLFLOW=mlflow
BUCKET_PREDICTIONS=predictions
BUCKET_PROMOTION=model-promotion
BUCKET_INFERENCE_LOGS=inference-txt-logs
```

---

## Setup Instructions

### Option A: Quick Start (Development/Minikube)

**Use built-in defaults** - No ConfigMap/Secret needed if services follow standard naming.

1. Deploy services with expected names:
   ```bash
   helm install flts .helm/ -f .helm/values-dev.yaml
   ```

2. Run pipeline with defaults:
   ```bash
   python kubeflow_pipeline/submit_run_v2.py
   ```

3. Components will use defaults from `runtime_defaults.py`.

### Option B: Kubernetes ConfigMap + Secret (Recommended)

**Step 1: Create ConfigMap for non-sensitive configuration**
```bash
kubectl create configmap flts-config \
  --from-literal=MINIO_ENDPOINT=minio-service.default.svc.cluster.local:9000 \
  --from-literal=MLFLOW_TRACKING_URI=http://mlflow.default.svc.cluster.local:5000 \
  --from-literal=GATEWAY_URL=http://fastapi-app.default.svc.cluster.local:8000 \
  --from-literal=BUCKET_DATASET=dataset \
  --from-literal=BUCKET_PROCESSED=processed-data \
  --from-literal=BUCKET_MLFLOW=mlflow \
  --from-literal=BUCKET_PREDICTIONS=predictions \
  --from-literal=BUCKET_PROMOTION=model-promotion \
  --from-literal=BUCKET_INFERENCE_LOGS=inference-txt-logs \
  --from-literal=AWS_DEFAULT_REGION=us-east-1 \
  --from-literal=AWS_S3_ADDRESSING_STYLE=path \
  --from-literal=MINIO_SECURE=false
```

**Step 2: Create Secret for credentials**
```bash
kubectl create secret generic flts-secrets \
  --from-literal=MINIO_ACCESS_KEY=minioadmin \
  --from-literal=MINIO_SECRET_KEY=minioadmin \
  --from-literal=AWS_ACCESS_KEY_ID=minioadmin \
  --from-literal=AWS_SECRET_ACCESS_KEY=minioadmin
```

**Step 3: Verify resources**
```bash
kubectl get configmap flts-config -o yaml
kubectl get secret flts-secrets -o yaml
```

**Step 4: Use in pipeline components** (requires updating `components_v2.py`):
```python
from kfp import dsl

@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=["boto3", "pandas"],
)
def preprocess_component(...):
    import os
    
    # These will be auto-injected by KFP if ConfigMap/Secret refs added
    minio_endpoint = os.environ.get("MINIO_ENDPOINT")
    minio_access_key = os.environ.get("MINIO_ACCESS_KEY")
    # ... rest of component logic
```

To inject ConfigMap/Secret into components, modify KFP task configuration:
```python
from kubernetes import client as k8s_client

preproc_task = preprocess_component(...)
preproc_task.add_env_variable(k8s_client.V1EnvVar(
    name="MINIO_ENDPOINT",
    value_from=k8s_client.V1EnvVarSource(
        config_map_key_ref=k8s_client.V1ConfigMapKeySelector(
            name="flts-config",
            key="MINIO_ENDPOINT"
        )
    )
))
```

### Option C: Pipeline Parameter Override (Runtime Flexibility)

**Override at submission time without modifying cluster resources:**

```bash
python kubeflow_pipeline/submit_run_v2.py \
  --gateway-url http://custom-gateway:8000 \
  --mlflow-uri http://custom-mlflow:5000 \
  --dataset ElBorn \
  --identifier step10-test-001
```

This passes values directly to pipeline parameters, which components receive as function arguments.

---

## Security Considerations

### Credentials Management

**Current Approach** (Development):
- Plain-text credentials in ConfigMap/Secret
- Acceptable for Minikube/local testing
- **NOT suitable for production**

**Production Recommendations**:
1. **External Secrets Operator**: Sync credentials from AWS Secrets Manager, HashiCorp Vault, etc.
2. **Workload Identity**: Use cloud provider IAM roles (GKE Workload Identity, EKS IRSA)
3. **Sealed Secrets**: Encrypt secrets at rest in Git
4. **Rotate Regularly**: Automate credential rotation

### Network Security

**Current Approach** (Development):
- HTTP (unencrypted) connections
- All services in same cluster

**Production Recommendations**:
1. **TLS/HTTPS**: Enable HTTPS for MLflow, MinIO (with valid certificates)
2. **Network Policies**: Restrict pod-to-pod communication
3. **Service Mesh**: Use Istio/Linkerd for mTLS and observability
4. **Egress Control**: Whitelist allowed external destinations

---

## Troubleshooting

### Issue: Component can't connect to MinIO

**Symptoms**: Connection refused, DNS resolution failure

**Checks**:
1. Verify service exists:
   ```bash
   kubectl get svc minio-service
   ```

2. Check DNS resolution from pod:
   ```bash
   kubectl run -it --rm debug --image=busybox --restart=Never -- \
     nslookup minio-service.default.svc.cluster.local
   ```

3. Test connectivity:
   ```bash
   kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
     curl -v http://minio-service.default.svc.cluster.local:9000/minio/health/live
   ```

4. Check component logs for actual endpoint used:
   ```bash
   kubectl logs -n kubeflow <component-pod-name>
   ```

### Issue: Authentication failures

**Symptoms**: 403 Forbidden, Invalid access key

**Checks**:
1. Verify secret exists and has correct keys:
   ```bash
   kubectl get secret flts-secrets -o jsonpath='{.data.MINIO_ACCESS_KEY}' | base64 -d
   ```

2. Confirm secret is mounted in pod:
   ```bash
   kubectl describe pod <component-pod-name>
   # Look for "Environment Variables from: flts-secrets"
   ```

3. Check actual credentials used (from component logs):
   ```bash
   # Add debug logging in component to print (masked) config
   ```

### Issue: Wrong endpoint being used

**Symptoms**: Component tries to connect to localhost, old IP, etc.

**Checks**:
1. Print effective configuration in component:
   ```python
   import os
   print(f"MINIO_ENDPOINT: {os.getenv('MINIO_ENDPOINT')}")
   ```

2. Check pipeline parameter values in KFP UI:
   - Navigate to run details
   - Check "Input Parameters" section

3. Verify ConfigMap values:
   ```bash
   kubectl get configmap flts-config -o yaml
   ```

---

## Validation Checklist

Before running Step 10 E2E pipeline:

- [ ] Services deployed and running: `kubectl get svc`
- [ ] DNS resolution works: `nslookup minio-service.default.svc.cluster.local`
- [ ] HTTP connectivity works: `curl http://minio-service:9000/minio/health/live`
- [ ] ConfigMap created (if using): `kubectl get configmap flts-config`
- [ ] Secret created (if using): `kubectl get secret flts-secrets`
- [ ] Defaults in `runtime_defaults.py` match cluster setup
- [ ] Submit script uses correct `--host` for KFP API
- [ ] Pipeline parameters include all required endpoints

---

## Future Enhancements

1. **Auto-Discovery**: Service mesh or operator-based endpoint discovery
2. **Credential Rotation**: Automated secret updates without pod restarts
3. **Multi-Tenant**: Per-team namespaces with isolated credentials
4. **Observability**: OpenTelemetry tracing for cross-service calls
5. **Policy Enforcement**: OPA/Gatekeeper for configuration validation

---

**Document Version**: 1.0  
**Last Updated**: December 17, 2025  
**Maintainer**: Step 10 Migration Team
