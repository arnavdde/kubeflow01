# Step 10 Quick Start Guide

**Purpose**: Get from "repo + laptop" to "first successful KFP v2 E2E run" in minimal steps.

---

## Prerequisites

- macOS with Docker Desktop installed
- kubectl installed
- Minikube installed
- Helm installed (optional, for service deployment)
- Git repo cloned and up to date

---

## Part 1: Infrastructure Setup (~30-60 minutes)

### 1.1 Start Docker Desktop
```bash
# If Docker is slow/stuck, restart it
killall Docker
open /Applications/Docker.app

# Wait for Docker to start (~30-60 seconds)
docker ps
```

### 1.2 Start Minikube Cluster
```bash
# Start with recommended resources
minikube start --cpus=4 --memory=8192 --disk-size=50g

# Verify cluster is running
kubectl cluster-info
kubectl get nodes

# Should show:
# NAME       STATUS   ROLES           AGE   VERSION
# minikube   Ready    control-plane   1m    v1.xx.x
```

### 1.3 Install Kubeflow Pipelines (Standalone)

**Option A: Minimal Installation (Recommended for Step 10)**
```bash
# Install KFP standalone (without full Kubeflow)
export PIPELINE_VERSION=2.0.5

kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=$PIPELINE_VERSION"
kubectl wait --for condition=established --timeout=60s crd/applications.app.k8s.io

kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/platform-agnostic?ref=$PIPELINE_VERSION"

# Wait for pods to be ready (~2-5 minutes)
kubectl wait --for=condition=ready --timeout=300s -n kubeflow pod -l app=ml-pipeline

# Verify installation
kubectl get pods -n kubeflow
kubectl get svc -n kubeflow
```

**Option B: Full Kubeflow (If needed)**
```bash
# Follow official guide: https://www.kubeflow.org/docs/started/installing-kubeflow/
# (More complex, not needed for Step 10)
```

### 1.4 Deploy Supporting Services

**Using Helm (Recommended)**
```bash
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Check if Helm chart exists
ls -la .helm/

# Deploy services to default namespace
helm install flts .helm/ -f .helm/values-dev.yaml

# Wait for pods (~2-3 minutes)
kubectl wait --for=condition=ready --timeout=300s pod -l app=minio
kubectl wait --for=condition=ready --timeout=300s pod -l app=mlflow
kubectl wait --for=condition=ready --timeout=300s pod -l app=fastapi-app

# Verify
kubectl get pods
kubectl get svc
```

**Manual Deployment (If Helm not available)**
```bash
# Use docker-compose.kfp.yaml as reference to create K8s manifests
# (More work, not recommended)
```

### 1.5 Verify Infrastructure with Debug Component
```bash
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Test debug component locally (adjust endpoints)
MINIO_ENDPOINT=minio-service.default.svc.cluster.local:9000 \
MLFLOW_URI=http://mlflow.default.svc.cluster.local:5000 \
GATEWAY_URL=http://fastapi-app.default.svc.cluster.local:8000 \
python3 kubeflow_pipeline/debug_component.py

# Expected output:
# ✓ DNS: minio-service.default.svc.cluster.local → 10.x.x.x
# ✓ HTTP: http://minio:9000 - Status 200
# ✓ MinIO S3 API: 3 buckets found
# ✓ Postgres: postgres:5432 - Port is open
# ✅ ALL VALIDATIONS PASSED
```

---

## Part 2: First Pipeline Run (~10-20 minutes)

### 2.1 Port-Forward KFP UI (Optional, for UI access)
```bash
# In a separate terminal
kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80

# Access UI at: http://localhost:8080
```

### 2.2 Submit Pipeline Run
```bash
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Ensure KFP SDK is installed
pip3 install 'kfp>=2.0.0,<3.0.0' boto3 requests

# Submit run
python3 kubeflow_pipeline/submit_run_v2.py \
  --host http://localhost:8080 \
  --experiment step10-quickstart \
  --run quickstart-001 \
  --dataset PobleSec \
  --identifier step10-test-001

# Expected output:
# [1/5] Compiling Pipeline
# ✓ Compilation successful (40,500 bytes)
# [2/5] Connecting to KFP
# ✓ Connected to KFP API (found 0 experiments)
# [3/5] Uploading Pipeline
# ✓ Pipeline uploaded: flts-time-series-pipeline-v2
# [4/5] Setting Up Experiment
# ✓ Experiment created: step10-quickstart
# [5/5] Starting Pipeline Run
# ✓ Run started successfully
# Run ID: abc123...
# View in UI: http://localhost:8080/#/runs/details/abc123...
```

### 2.3 Monitor Run Progress

**Option A: KFP UI**
```
1. Open: http://localhost:8080
2. Navigate to "Runs" tab
3. Click on your run: "quickstart-001"
4. Watch pipeline graph update in real-time
```

**Option B: kubectl CLI**
```bash
# List KFP workflow pods
kubectl get pods -n kubeflow | grep quickstart

# Watch specific component
kubectl logs -n kubeflow <component-pod-name> -f

# Example:
kubectl logs -n kubeflow preprocess-abc123 -f
kubectl logs -n kubeflow train-gru-abc123 -f
```

**Expected Timeline**:
- Preprocess: ~1-2 minutes
- Train (GRU, LSTM, Prophet parallel): ~3-5 minutes each
- Eval: ~30 seconds
- Inference: ~1-2 minutes
- **Total**: ~8-12 minutes

### 2.4 Validate Run
```bash
# Wait for run to complete (Status: Succeeded in UI)

# Run validation script
python3 kubeflow_pipeline/tests/test_step10_e2e_contract.py \
  --run-id <run-id-from-step-2.2> \
  --host http://localhost:8080 \
  --output migration/step10/validation_report.json

# Expected output:
# Test 1: KFP Run Status
# ✓ Run Status [PASS] State: SUCCEEDED
# Test 2: MinIO Artifacts
# ✓ MinIO: Training data [PASS]
# ✓ Model Promotion Pointer [PASS] Best model: GRU
# Test 3: MLflow Experiment Tracking
# ✓ MLflow API [PASS] Found 3 recent runs
# Test 4: Gateway Availability
# ✓ Gateway Health [PASS] Status 200
#
# ✅ ALL VALIDATIONS PASSED
```

---

## Part 3: Capture Proof Pack (~10 minutes)

### 3.1 Screenshots

**KFP UI - Pipeline Graph**
```
1. Open: http://localhost:8080/#/runs/details/<run-id>
2. Click "Graph" tab
3. Screenshot showing green checkmarks on all nodes
4. Save as: migration/step10/screenshots/pipeline_graph.png
```

**KFP UI - Run Details**
```
1. On same run page, click "Run details" tab
2. Screenshot showing:
   - Run ID
   - Status: Succeeded
   - Duration
   - Input parameters
3. Save as: migration/step10/screenshots/run_details.png
```

**Component Logs**
```
1. In KFP UI, click on a component node (e.g., train-gru)
2. Click "Logs" tab
3. Screenshot showing successful execution logs
4. Save as: migration/step10/screenshots/component_logs.png
```

**MinIO Artifacts**
```bash
# Port-forward MinIO console
kubectl port-forward svc/minio-service 9001:9001

# Open: http://localhost:9001
# Login: minioadmin / minioadmin
# Browse buckets: processed-data, model-promotion, predictions
# Screenshot bucket contents
# Save as: migration/step10/screenshots/minio_artifacts.png
```

**MLflow Run Page**
```bash
# Port-forward MLflow
kubectl port-forward svc/mlflow 5000:5000

# Open: http://localhost:5000
# Find experiment: step10-quickstart
# Click on a run
# Screenshot showing:
#   - Run ID
#   - Parameters
#   - Metrics
#   - Artifacts
# Save as: migration/step10/screenshots/mlflow_run.png
```

### 3.2 Update Completion Report
```bash
# Edit migration/step10/COMPLETION.md
# Fill in:
#   - Run ID
#   - Pipeline ID
#   - Experiment ID
#   - Timestamps
#   - Artifact listings
#   - Screenshot references
#   - Check off all boxes

# Commit changes
git add migration/step10/
git commit -m "Complete Step 10: KFP v2 E2E run successful"
```

---

## Troubleshooting

### Issue: Minikube won't start
```bash
# Check Docker
docker ps

# Delete and recreate cluster
minikube delete
minikube start --cpus=4 --memory=8192 --disk-size=50g

# Check logs
minikube logs
```

### Issue: KFP pods not starting
```bash
# Check pod status
kubectl get pods -n kubeflow

# Describe failing pod
kubectl describe pod <pod-name> -n kubeflow

# Check events
kubectl get events -n kubeflow --sort-by='.lastTimestamp'

# Common fixes:
# - Increase Minikube memory: minikube config set memory 10240
# - Wait longer (KFP can take 5+ minutes on first start)
# - Check image pull: kubectl describe pod <pod> -n kubeflow | grep -A5 Events
```

### Issue: Service pods not starting
```bash
# Check pods
kubectl get pods

# Describe failing pod
kubectl describe pod <pod-name>

# Check PVC (if using Helm with persistence)
kubectl get pvc

# Common fixes:
# - Check resource limits in values-dev.yaml
# - Verify MinIO init job completed: kubectl get jobs
# - Check logs: kubectl logs <pod-name>
```

### Issue: Debug component fails
```bash
# Test DNS from within cluster
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup minio-service.default.svc.cluster.local

# Test HTTP from within cluster
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl -v http://minio-service.default.svc.cluster.local:9000/minio/health/live

# Common fixes:
# - Verify service names: kubectl get svc
# - Check endpoints: kubectl get endpoints
# - Verify namespace: services must be in default namespace
```

### Issue: Submit script fails
```bash
# Check KFP API connectivity
curl http://localhost:8080/apis/v2beta1/pipelines

# Check port-forward
ps aux | grep "port-forward"

# Re-establish port-forward
kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80

# Common fixes:
# - Restart port-forward
# - Check --host parameter matches port-forward
# - Verify namespace: --namespace kubeflow
```

### Issue: Run fails with ImagePullBackOff
```bash
# Check pod events
kubectl describe pod <pod-name> -n kubeflow

# Common issue: Components use custom images (flts-preprocess:latest, etc.)
# which need to be built and loaded into Minikube

# Solution: Build and load images
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Build images
docker-compose build preprocess train_gru train_lstm nonml_prophet eval inference

# Load into Minikube
minikube image load flts-preprocess:latest
minikube image load train-container:latest
minikube image load nonml-container:latest
minikube image load eval-container:latest
minikube image load inference-container:latest

# Verify
minikube image ls | grep flts
```

---

## Success Criteria

✅ **Step 10 Complete When**:
1. Minikube cluster running
2. Kubeflow Pipelines installed
3. Supporting services deployed and healthy
4. Pipeline submitted via `submit_run_v2.py`
5. Run status: Succeeded
6. All validation tests passed
7. Screenshots captured
8. Artifacts verified in MinIO
9. MLflow runs created
10. Completion report updated

---

## Time Estimates

**First-time setup**:
- Infrastructure: 30-60 minutes
- First run: 10-20 minutes
- Validation: 10 minutes
- Screenshots: 10 minutes
- **Total**: ~60-100 minutes

**Subsequent runs**:
- Submit: 1 minute
- Execute: 8-12 minutes
- Validate: 2 minutes
- **Total**: ~11-15 minutes

---

## Reference Commands

```bash
# Cluster management
minikube start --cpus=4 --memory=8192 --disk-size=50g
minikube stop
minikube delete
minikube status

# KFP access
kubectl port-forward -n kubeflow svc/ml-pipeline-ui 8080:80
kubectl port-forward -n kubeflow svc/ml-pipeline 8888:8888  # API server

# Service access
kubectl port-forward svc/minio-service 9000:9000  # MinIO API
kubectl port-forward svc/minio-service 9001:9001  # MinIO Console
kubectl port-forward svc/mlflow 5000:5000         # MLflow UI
kubectl port-forward svc/fastapi-app 8000:8000    # Gateway API

# Monitoring
kubectl get pods -A -w
kubectl logs -f <pod-name>
kubectl describe pod <pod-name>
kubectl get events --sort-by='.lastTimestamp'

# Cleanup
helm uninstall flts
kubectl delete namespace kubeflow
minikube delete
```

---

**Guide Version**: 1.0  
**Last Updated**: December 17, 2025  
**Tested On**: macOS, Minikube, Kubeflow Pipelines 2.0.5
