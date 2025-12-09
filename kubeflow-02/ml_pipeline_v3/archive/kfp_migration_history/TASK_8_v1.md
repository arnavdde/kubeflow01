# TASK 8: Kubeflow Pipeline (KFP v2) Definition

**Status**: ✅ COMPLETE  
**Date**: November 25, 2025  
**Objective**: Build a complete KFP v2 pipeline definition that orchestrates all 6 migrated components

---

## 📋 Overview

Task 8 creates the top-level pipeline orchestration layer that chains all KFP-ready components (created in Tasks 1-7) into a single executable workflow. This pipeline definition serves as the entry point for running end-to-end forecasting jobs in Kubeflow Pipelines.

---

## 🏗️ Pipeline Architecture

### Component Flow (DAG)

```
┌─────────────────────────────────────────────────────────────┐
│                      FLTS Pipeline DAG                       │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────┐
                    │  PREPROCESS   │
                    │               │
                    │ Load CSV      │
                    │ Transform     │
                    │ Split Data    │
                    └───────┬───────┘
                            │
                    ┌───────┴───────┐
                    │               │
            training_data    inference_data
                    │               │
        ┌───────────┼───────────┐   │
        │           │           │   │
        ▼           ▼           ▼   │
    ┌─────┐    ┌──────┐   ┌────────┐│
    │ GRU │    │ LSTM │   │PROPHET ││
    │TRAIN│    │TRAIN │   │ TRAIN  ││
    └──┬──┘    └───┬──┘   └───┬────┘│
       │           │           │     │
       └───────────┼───────────┘     │
                   │                 │
            3 Model Artifacts        │
                   │                 │
                   ▼                 │
            ┌────────────┐           │
            │    EVAL    │           │
            │            │           │
            │ Compare    │           │
            │ Select Best│           │
            └─────┬──────┘           │
                  │                  │
          promotion_pointer          │
                  │                  │
                  └──────────┬───────┘
                             │
                             ▼
                      ┌─────────────┐
                      │  INFERENCE  │
                      │             │
                      │  Predict    │
                      │  Write JSONL│
                      └─────────────┘
```

### Pipeline Characteristics

- **Total Components**: 6 (preprocess, 3x training, eval, inference)
- **Parallel Execution**: 3 training components run simultaneously
- **Sequential Dependencies**: preprocess → train → eval → inference
- **Artifact Types**: Dataset, Model, Artifact, String
- **Execution Time**: ~5-15 minutes (dataset dependent)

---

## 📦 Artifacts Produced

### 1. Preprocess Component

| Artifact | Type | Location | Description |
|----------|------|----------|-------------|
| `training_data` | Dataset | MinIO: `processed-data/<identifier>_train.parquet` | Preprocessed training data with metadata |
| `inference_data` | Dataset | MinIO: `processed-data/<identifier>_test.parquet` | Preprocessed test/inference data |
| `config_hash` | String | KFP metadata | SHA256 hash of preprocessing config (lineage) |
| `config_json` | String | KFP metadata | Canonical preprocessing configuration JSON |

**Metadata Structure** (training_data):
```json
{
  "uri": "minio://processed-data/flts-run-001_train.parquet",
  "format": "parquet",
  "rows": 8760,
  "columns": 15,
  "config_hash": "a3f5b9c...",
  "timestamp": "2025-11-25T10:30:00Z"
}
```

### 2. Training Components (GRU, LSTM, Prophet)

| Artifact | Type | Location | Description |
|----------|------|----------|-------------|
| `model` | Model | MLflow: `mlflow://<run_id>/model` | Trained model with MLflow URI |
| `metrics` | Artifact | MinIO: `model-metrics/<identifier>_<model_type>.json` | Test metrics (RMSE, MAE, MSE) |
| `run_id` | String | KFP metadata | MLflow run identifier |

**Metrics Structure**:
```json
{
  "model_type": "gru",
  "test_rmse": 0.0452,
  "test_mae": 0.0321,
  "test_mse": 0.0020,
  "composite_score": 0.0364,
  "training_epochs": 42,
  "mlflow_run_id": "abc123...",
  "timestamp": "2025-11-25T10:45:00Z"
}
```

### 3. Eval Component

| Artifact | Type | Location | Description |
|----------|------|----------|-------------|
| `promotion_pointer` | Artifact | MinIO: `model-promotion/promotion-<identifier>.json` | Canonical pointer to best model |
| `eval_metadata` | Artifact | MinIO: `model-promotion/eval-metadata-<identifier>.json` | Detailed evaluation results |

**Promotion Pointer Structure**:
```json
{
  "promoted_model_uri": "mlflow://5/abc123.../model",
  "promoted_model_type": "lstm",
  "promotion_timestamp": "2025-11-25T10:50:00Z",
  "composite_score": 0.0348,
  "individual_scores": {
    "gru": 0.0364,
    "lstm": 0.0348,
    "prophet": 0.0412
  },
  "identifier": "flts-run-001"
}
```

### 4. Inference Component

| Artifact | Type | Location | Description |
|----------|------|----------|-------------|
| `inference_results` | Artifact | MinIO: `inference-logs/inference-<identifier>.jsonl` | Structured predictions (JSONL) |
| `inference_metadata` | Artifact | MinIO: `inference-logs/inference-metadata-<identifier>.json` | Execution metadata |

**Inference Results Structure** (JSONL):
```jsonl
{"timestamp":"2025-11-25T11:00:00Z","prediction":0.452,"actual":0.448,"error":0.004}
{"timestamp":"2025-11-25T12:00:00Z","prediction":0.461,"actual":0.455,"error":0.006}
```

---

## 🔌 Input/Output Contracts

### Component Interfaces

#### 1. Preprocess Component

**Inputs**:
```python
dataset_name: str                    # CSV filename (e.g., "PobleSec")
identifier: str                      # Unique run ID
sample_train_rows: int = 0           # Training sample size (0=all)
sample_test_rows: int = 0            # Test sample size (0=all)
sample_strategy: str = "head"        # Sampling method
handle_nans: bool = True             # Enable NaN handling
clip_enable: bool = False            # Enable outlier clipping
time_features_enable: bool = True    # Extract time features
scaler: str = "MinMaxScaler"         # Scaling method
gateway_url: str                     # FastAPI MinIO gateway
input_bucket: str = "dataset"        # Source bucket
output_bucket: str = "processed-data"# Destination bucket
# ... (19 total inputs)
```

**Outputs**:
```python
training_data: Output[Dataset]       # Preprocessed training data
inference_data: Output[Dataset]      # Preprocessed inference data
config_hash: OutputPath(str)         # Config hash for lineage
config_json: OutputPath(str)         # Full config JSON
```

#### 2. Train Components (GRU/LSTM/Prophet)

**Inputs** (GRU/LSTM):
```python
training_data: Input[Dataset]        # From preprocess
config_hash: str                     # For lineage tracking
hidden_size: int = 64                # Network architecture
num_layers: int = 2                  # RNN layers
dropout: float = 0.2                 # Dropout rate
learning_rate: float = 0.001         # Optimizer LR
batch_size: int = 32                 # Training batch size
num_epochs: int = 50                 # Max epochs
early_stopping_patience: int = 10    # ES patience
window_size: int = 12                # Time series window
mlflow_tracking_uri: str             # MLflow server
gateway_url: str                     # MinIO gateway
```

**Inputs** (Prophet):
```python
training_data: Input[Dataset]        # From preprocess
config_hash: str                     # For lineage
seasonality_mode: str = "multiplicative"
changepoint_prior_scale: float = 0.05
yearly_seasonality: bool = True
weekly_seasonality: bool = True
# ... Prophet-specific params
```

**Outputs** (All Training):
```python
model: Output[Model]                 # Trained model (MLflow URI)
metrics: Output[Artifact]            # Performance metrics
run_id: OutputPath(str)              # MLflow run ID
```

#### 3. Eval Component

**Inputs**:
```python
gru_model: Input[Model]              # From GRU training
lstm_model: Input[Model]             # From LSTM training
prophet_model: Input[Model]          # From Prophet training
config_hash: str                     # For lineage
identifier: str                      # Run ID
rmse_weight: float = 0.5             # Composite score weight
mae_weight: float = 0.3              # Composite score weight
mse_weight: float = 0.2              # Composite score weight
mlflow_tracking_uri: str
gateway_url: str
promotion_bucket: str = "model-promotion"
```

**Outputs**:
```python
promotion_pointer: Output[Artifact]  # Best model pointer
eval_metadata: Output[Artifact]      # Evaluation details
```

#### 4. Inference Component

**Inputs**:
```python
inference_data: Input[Dataset]       # From preprocess
promoted_model: Input[Model]         # From eval (best model)
identifier: str                      # Run ID
inference_length: int = 1            # Prediction steps
sample_idx: int = 0                  # Sample selection
enable_microbatch: str = "false"     # Microbatching flag
batch_size: int = 32                 # Inference batch size
mlflow_tracking_uri: str
gateway_url: str
inference_log_bucket: str = "inference-logs"
```

**Outputs**:
```python
inference_results: Output[Artifact]  # JSONL predictions
inference_metadata: Output[Artifact] # Execution metadata
```

---

## 🔗 Dependency Graph

### Execution Order

1. **Preprocess** (no dependencies)
   - Reads: CSV from MinIO `dataset` bucket
   - Writes: Parquet to MinIO `processed-data` bucket
   - Duration: ~30-60 seconds

2. **Training (Parallel)** (depends on Preprocess)
   - **GRU Training**: reads `training_data` Dataset
   - **LSTM Training**: reads `training_data` Dataset
   - **Prophet Training**: reads `training_data` Dataset
   - All write models to MLflow, metrics to MinIO
   - Duration: ~3-10 minutes (parallel execution)

3. **Eval** (depends on all 3 Training)
   - Reads: 3 Model artifacts from training
   - Compares metrics, selects best model
   - Writes: promotion pointer to MinIO
   - Duration: ~10-20 seconds

4. **Inference** (depends on Eval + Preprocess)
   - Reads: `inference_data` Dataset (from Preprocess)
   - Reads: `promoted_model` Model (from Eval)
   - Writes: predictions to MinIO `inference-logs`
   - Duration: ~20-40 seconds

### Critical Path

```
Preprocess → Training (slowest of 3) → Eval → Inference
Total: ~5-15 minutes depending on dataset size and epochs
```

### Parallelization Opportunities

- **Training components**: Fully parallelizable (no interdependencies)
- **Potential speedup**: 3x if sufficient cluster resources
- **Resource requirements**: Each trainer needs GPU (if available)

---

## 🛠️ Compilation Instructions

### Prerequisites

1. **KFP SDK v2 installed**:
   ```bash
   pip install kfp>=2.0.0
   ```

2. **Component definitions exist**:
   ```bash
   ls kubeflow_pipeline/components/*/component.yaml
   # Expected: 6 component.yaml files
   ```

3. **Docker images built**:
   ```bash
   docker images | grep -E 'flts-preprocess|train-container|eval-container|inference-container'
   ```

### Compilation Steps

#### Step 1: Navigate to Pipeline Directory
```bash
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/kubeflow_pipeline
```

#### Step 2: Run Compilation Script
```bash
python compile_pipeline.py
```

**Expected Output**:
```
======================================================================
FLTS Pipeline Compilation
======================================================================

Step 1: Loading component definitions...
Loading component: preprocess from components/preprocess/component.yaml
Loading component: train_gru from components/train_gru/component.yaml
Loading component: train_lstm from components/train_lstm/component.yaml
Loading component: train_prophet from components/train_prophet/component.yaml
Loading component: eval from components/eval/component.yaml
Loading component: inference from components/inference/component.yaml
✓ Loaded 6 components

Step 2: Building pipeline definition...
✓ Pipeline structure created

Step 3: Compiling to pipeline.job.yaml...
✓ Pipeline compiled successfully

======================================================================
✓ SUCCESS: Pipeline YAML created
  File: pipeline.job.yaml
  Size: ~50,000 bytes
======================================================================

Next steps:
  1. Review the generated YAML file
  2. Upload to Kubeflow Pipelines UI
  3. Create a run with desired parameters
  4. Monitor execution in KFP dashboard
```

#### Step 3: Verify Compilation
```bash
# Check file exists
ls -lh pipeline.job.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('pipeline.job.yaml'))"

# Inspect structure
head -n 100 pipeline.job.yaml
```

### Advanced Compilation Options

```bash
# Custom output location
python compile_pipeline.py -o /tmp/custom_pipeline.yaml

# Specify components directory
python compile_pipeline.py -c ./custom_components

# Lightweight version (reduced parameters for testing)
python compile_pipeline.py --lightweight
```

---

## 🚀 Submission Instructions

### Method 1: Kubeflow Pipelines UI (Recommended)

#### Upload Pipeline

1. **Access KFP UI**:
   - Local cluster: `http://localhost:8080`
   - Remote cluster: `https://<kubeflow-domain>/pipeline`

2. **Navigate to Pipelines**:
   - Click **Pipelines** in left sidebar
   - Click **Upload Pipeline** button

3. **Upload Compiled YAML**:
   - **Pipeline Name**: "FLTS Time Series Forecasting v2"
   - **Pipeline Description**: "End-to-end forecasting with GRU/LSTM/Prophet"
   - **Upload file**: Select `pipeline.job.yaml`
   - Click **Create**

4. **Verify Upload**:
   - Pipeline appears in list
   - Click pipeline name
   - View DAG visualization (should show 6 components)

#### Create Run

1. **Start New Run**:
   - From pipeline page, click **Create Run**
   - Or: **Runs** → **Create Run** → Select pipeline

2. **Configure Run**:
   - **Run name**: `flts-pobleSec-run-001`
   - **Experiment**: Select or create new
   - **Run type**: One-off or Recurring

3. **Set Parameters**:
   ```yaml
   # Core parameters
   dataset_name: "PobleSec"
   identifier: "pobleSec-run-001"
   
   # Preprocessing
   sample_train_rows: 0  # Use full dataset
   handle_nans: true
   time_features_enable: true
   scaler: "MinMaxScaler"
   
   # Training
   num_epochs: 50
   hidden_size: 64
   batch_size: 32
   learning_rate: 0.001
   
   # Evaluation
   rmse_weight: 0.5
   mae_weight: 0.3
   mse_weight: 0.2
   
   # Infrastructure
   gateway_url: "http://fastapi-app:8000"
   mlflow_tracking_uri: "http://mlflow:5000"
   ```

4. **Launch**:
   - Review parameters
   - Click **Start**

### Method 2: KFP SDK (Programmatic)

```python
import kfp

# Connect to KFP
client = kfp.Client(host='http://localhost:8080')

# Create experiment
experiment = client.create_experiment(
    name='FLTS Production Runs',
    description='Production forecasting runs'
)

# Upload pipeline
pipeline_id = client.upload_pipeline(
    pipeline_package_path='pipeline.job.yaml',
    pipeline_name='FLTS Time Series Forecasting v2'
)

# Submit run
run = client.run_pipeline(
    experiment_id=experiment.id,
    job_name='flts-pobleSec-run-001',
    pipeline_id=pipeline_id,
    params={
        'dataset_name': 'PobleSec',
        'identifier': 'pobleSec-run-001',
        'num_epochs': 50,
        'hidden_size': 64
    }
)

print(f"Run started: {run.id}")
print(f"View at: http://localhost:8080/#/runs/details/{run.id}")
```

### Method 3: kubectl (Direct Application)

```bash
# Apply pipeline as Kubernetes resource
kubectl apply -f pipeline.job.yaml -n kubeflow

# Monitor run
kubectl get pods -n kubeflow | grep flts-
kubectl logs <pod-name> -n kubeflow -f
```

---

## 🧪 Testing Plan

### Level 1: Compilation Test

**Objective**: Verify pipeline compiles without errors

```bash
python compile_pipeline.py
echo $?  # Should be 0 (success)
```

**Success Criteria**:
- `pipeline.job.yaml` created
- File size > 10KB
- Valid YAML syntax
- Contains all 6 component definitions

### Level 2: Component Import Test

**Objective**: Verify all components load correctly

```python
# test_components.py
from kfp import dsl
from pathlib import Path

components_dir = Path("components")

# Test each component loads
for comp_name in ['preprocess', 'train_gru', 'train_lstm', 
                   'train_prophet', 'eval', 'inference']:
    comp_path = components_dir / comp_name / "component.yaml"
    assert comp_path.exists(), f"Missing: {comp_path}"
    
    comp = dsl.load_component_from_file(str(comp_path))
    assert comp is not None, f"Failed to load: {comp_name}"
    print(f"✓ {comp_name} loaded successfully")

print("\n✓ All components loaded successfully")
```

### Level 3: Smoke Test (Lightweight Pipeline)

**Objective**: Run fast end-to-end test with minimal data

```bash
# Compile lightweight version
python compile_pipeline.py --lightweight

# Or manually set lightweight parameters:
# - sample_train_rows: 1000
# - sample_test_rows: 100
# - num_epochs: 10
# - early_stopping_patience: 3
```

**Expected Duration**: ~2-3 minutes

**Success Criteria**:
- All components complete successfully
- Artifacts created in MinIO
- Models logged to MLflow
- Inference results written

### Level 4: Full Integration Test

**Objective**: Run complete pipeline with production settings

**Test Datasets**:
1. **PobleSec** (small): ~8,760 rows, ~2-3 min training
2. **ElBorn** (medium): ~17,520 rows, ~5-7 min training
3. **LesCorts** (large): ~26,280 rows, ~8-12 min training

**Test Procedure**:
```bash
# 1. Upload pipeline to KFP
# 2. Create run with production parameters
# 3. Monitor execution
# 4. Validate outputs
```

**Validation Checklist**:
- [ ] Preprocess completes, produces 2 Datasets
- [ ] All 3 training components complete
- [ ] Models registered in MLflow with metrics
- [ ] Eval selects best model (lowest composite score)
- [ ] Inference produces JSONL predictions
- [ ] All artifacts accessible in MinIO
- [ ] Run metadata complete in KFP UI

### Level 5: Failure Recovery Test

**Objective**: Verify pipeline handles failures gracefully

**Test Scenarios**:
1. **Invalid dataset**: Non-existent CSV → Preprocess fails
2. **OOM error**: Batch size too large → Training fails
3. **MLflow unavailable**: Tracking server down → Training fails
4. **MinIO unavailable**: Storage down → All steps fail

**Expected Behavior**:
- Clear error messages in component logs
- Failed component status in KFP UI
- Remaining components don't execute (fail fast)
- No partial artifacts left in inconsistent state

### Test Automation Script

```bash
#!/bin/bash
# test_pipeline.sh

set -e

echo "=== FLTS Pipeline Test Suite ==="

# Test 1: Compilation
echo "Test 1: Compilation..."
python compile_pipeline.py
[ -f pipeline.job.yaml ] || exit 1
echo "✓ Compilation passed"

# Test 2: Component loading
echo "Test 2: Component loading..."
python test_components.py
echo "✓ Component loading passed"

# Test 3: YAML validation
echo "Test 3: YAML validation..."
python -c "import yaml; yaml.safe_load(open('pipeline.job.yaml'))"
echo "✓ YAML validation passed"

# Test 4: Smoke test (requires KFP cluster)
if [ "$SKIP_SMOKE_TEST" != "true" ]; then
    echo "Test 4: Smoke test..."
    python submit_test_run.py --lightweight
    echo "✓ Smoke test passed"
fi

echo "=== All tests passed ==="
```

---

## ⚠️ Common Failure Modes

### 1. Image Pull Errors

**Symptom**: Component pods stuck in `ErrImagePull` or `ImagePullBackOff`

**Cause**: Docker images not accessible to Kubernetes cluster

**Solution**:
```bash
# Option A: Push to container registry
docker tag flts-preprocess:latest <registry>/flts-preprocess:latest
docker push <registry>/flts-preprocess:latest

# Option B: Load into cluster directly (minikube/kind)
minikube image load flts-preprocess:latest
kind load docker-image flts-preprocess:latest

# Option C: Update component.yaml with registry path
# Edit components/preprocess/component.yaml
image: <registry>/flts-preprocess:latest
```

### 2. Artifact Not Found

**Symptom**: Downstream component fails with "Artifact path not found"

**Cause**: 
- MinIO bucket doesn't exist
- Upstream component didn't write artifact
- Incorrect artifact path in metadata

**Diagnosis**:
```bash
# Check MinIO buckets
mc ls minio/processed-data/
mc ls minio/model-promotion/

# Check component logs for write confirmation
kubectl logs <upstream-pod> -n kubeflow | grep "Writing artifact"

# Verify artifact metadata
mc cat minio/processed-data/<identifier>-metadata.json
```

**Solution**:
```bash
# Create missing bucket
mc mb minio/<bucket-name>

# Re-run failed component
# (KFP will automatically retry if configured)
```

### 3. MLflow Connection Errors

**Symptom**: Training component fails with "Connection refused to MLflow tracking server"

**Cause**:
- MLflow service not running
- Incorrect tracking URI
- Network policy blocking access

**Diagnosis**:
```bash
# Check MLflow pod
kubectl get pods -n kubeflow | grep mlflow

# Test connectivity from component pod
kubectl exec <training-pod> -n kubeflow -- curl http://mlflow:5000/health

# Check environment variables
kubectl exec <training-pod> -n kubeflow -- env | grep MLFLOW
```

**Solution**:
```bash
# Restart MLflow
kubectl rollout restart deployment/mlflow -n kubeflow

# Verify service
kubectl get svc mlflow -n kubeflow

# Update tracking URI if needed
# (pass correct value in pipeline parameters)
```

### 4. Out of Memory (OOM)

**Symptom**: Training pod killed with exit code 137 (OOMKilled)

**Cause**: 
- Batch size too large
- Model architecture too large
- Insufficient pod memory limits

**Diagnosis**:
```bash
# Check pod status
kubectl describe pod <training-pod> -n kubeflow

# Look for: "Reason: OOMKilled"
```

**Solution**:
```yaml
# Option A: Reduce batch size
params:
  batch_size: 16  # Instead of 32

# Option B: Increase pod memory
# Edit component.yaml
resources:
  limits:
    memory: "8Gi"  # Instead of 4Gi
  requests:
    memory: "4Gi"

# Option C: Reduce model size
params:
  hidden_size: 32  # Instead of 64
  num_layers: 1    # Instead of 2
```

### 5. NaN Loss During Training

**Symptom**: Training component completes but model unusable (NaN predictions)

**Cause**:
- Learning rate too high
- Unhandled NaN values in data
- Numerical instability

**Diagnosis**:
```bash
# Check training logs
kubectl logs <training-pod> -n kubeflow | grep -i "nan\|loss"

# Check MLflow metrics
# (view in MLflow UI: http://mlflow:5000)
```

**Solution**:
```yaml
# Reduce learning rate
params:
  learning_rate: 0.0001  # Instead of 0.001

# Enable preprocessing safeguards
params:
  handle_nans: true
  clip_enable: true

# Add gradient clipping (code change)
# In train_container.py:
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
```

### 6. Eval Component Selects Wrong Model

**Symptom**: Eval completes but promoted model has poor performance

**Cause**:
- Incorrect composite score weights
- Models not fully trained (early stopping too aggressive)
- Test set too small or unrepresentative

**Diagnosis**:
```bash
# Check eval metadata
mc cat minio/model-promotion/eval-metadata-<identifier>.json | jq

# Compare individual model scores
# (check RMSE, MAE, MSE for each model)
```

**Solution**:
```yaml
# Adjust composite weights
params:
  rmse_weight: 0.6  # Prioritize RMSE
  mae_weight: 0.3
  mse_weight: 0.1

# Allow more training
params:
  num_epochs: 100
  early_stopping_patience: 15

# Use larger test set
params:
  sample_test_rows: 2000  # Instead of 100
```

### 7. Pipeline Hangs/Stalls

**Symptom**: Pipeline runs indefinitely without progress

**Cause**:
- Deadlock in component
- Waiting for external resource
- Kubernetes resource constraints

**Diagnosis**:
```bash
# Check pod status
kubectl get pods -n kubeflow | grep flts-

# Check pod logs
kubectl logs <stuck-pod> -n kubeflow --tail 100

# Check resource usage
kubectl top pods -n kubeflow | grep flts-

# Check events
kubectl get events -n kubeflow --sort-by='.lastTimestamp'
```

**Solution**:
```bash
# Cancel stuck run (in KFP UI or via API)
# Increase timeouts in component.yaml if needed
# Check cluster resources: kubectl describe nodes
```

---

## 📊 Pipeline Metadata

### Compilation Details

- **KFP SDK Version**: 2.0.0+
- **Python Version**: 3.10+
- **Pipeline Format**: KFP v2 YAML
- **Component Definition Format**: KFP component YAML v2

### Resource Requirements

**Per Component** (default):
```yaml
preprocess:
  cpu: 1 core
  memory: 2Gi
  duration: ~30-60s

train_gru / train_lstm:
  cpu: 2 cores
  memory: 4Gi
  gpu: 1 (optional, recommended)
  duration: ~3-10 min

train_prophet:
  cpu: 1 core
  memory: 2Gi
  duration: ~1-3 min

eval:
  cpu: 1 core
  memory: 1Gi
  duration: ~10-20s

inference:
  cpu: 1 core
  memory: 2Gi
  duration: ~20-40s
```

**Total Cluster Requirements**:
- **Min**: 4 CPU cores, 8Gi memory (sequential execution)
- **Recommended**: 8 CPU cores, 16Gi memory, 2 GPUs (parallel training)

### Storage Requirements

**MinIO Buckets**:
- `dataset`: ~50MB (input CSVs)
- `processed-data`: ~100-200MB per run (Parquet files)
- `model-promotion`: ~10KB per run (JSON pointers)
- `inference-logs`: ~1-5MB per run (JSONL predictions)

**MLflow Storage**:
- ~50-100MB per model (artifacts + metadata)
- 3 models per run × 50-100MB = 150-300MB per run

**Total per Run**: ~350-700MB

---

## ✅ Validation Checklist

### Pre-Deployment

- [ ] All 6 component.yaml files exist
- [ ] All Docker images built and tagged
- [ ] KFP SDK v2 installed (`pip list | grep kfp`)
- [ ] MinIO running and accessible
- [ ] MLflow running and accessible
- [ ] FastAPI gateway running (Part A complete)

### Compilation

- [ ] `python compile_pipeline.py` runs without errors
- [ ] `pipeline.job.yaml` created (size > 10KB)
- [ ] YAML syntax valid (`python -c "import yaml; yaml.safe_load(open('pipeline.job.yaml'))"`)
- [ ] All 6 components listed in YAML

### Deployment

- [ ] Pipeline uploaded to KFP UI successfully
- [ ] Pipeline appears in pipelines list
- [ ] DAG visualization shows 6 components with correct connections
- [ ] No upload errors in KFP logs

### Execution

- [ ] Test run created successfully
- [ ] All components start (pods created)
- [ ] Preprocess completes, produces artifacts
- [ ] All 3 training components complete
- [ ] Eval completes, selects model
- [ ] Inference completes, produces predictions
- [ ] Run marked as "Succeeded" in KFP UI

### Validation

- [ ] Preprocessed data in MinIO `processed-data` bucket
- [ ] 3 models in MLflow with metrics
- [ ] Promotion pointer in MinIO `model-promotion` bucket
- [ ] Inference results in MinIO `inference-logs` bucket
- [ ] All artifacts accessible and well-formed (valid JSON/Parquet/JSONL)

---

## 🔄 Integration with Existing Infrastructure

### MinIO Configuration

Pipeline expects these buckets to exist:
```bash
mc mb minio/dataset               # Input CSVs
mc mb minio/processed-data        # Preprocessed Parquet
mc mb minio/model-promotion       # Promotion pointers
mc mb minio/inference-logs        # Inference results
```

If using custom bucket names, pass via parameters:
```yaml
params:
  input_bucket: "my-custom-dataset-bucket"
  output_bucket: "my-custom-processed-bucket"
  # etc.
```

### MLflow Configuration

Pipeline assumes MLflow tracking server at `http://mlflow:5000` with MinIO backend for artifact storage.

**MLflow Environment**:
```bash
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_S3_ENDPOINT_URL=http://minio:9000
AWS_ACCESS_KEY_ID=<minio-access-key>
AWS_SECRET_ACCESS_KEY=<minio-secret-key>
```

### Docker Compose Integration

Pipeline components use images from `docker-compose.kfp.yaml`:
- `flts-preprocess:latest`
- `train-container:latest`
- `eval-container:latest`
- `inference-container:latest`

To rebuild all images:
```bash
docker-compose -f docker-compose.kfp.yaml build
```

---

## 📈 Future Enhancements

### Phase 1 (Immediate)
- [ ] Add pipeline versioning (semver in metadata)
- [ ] Create additional lightweight test pipelines
- [ ] Add parameter validation (input constraints)
- [ ] Implement retry logic for transient failures

### Phase 2 (Short-term)
- [ ] Add XGBoost/Transformer training components
- [ ] Implement A/B testing (multiple model deployment)
- [ ] Add data drift detection (before preprocessing)
- [ ] Create dashboard for run monitoring

### Phase 3 (Long-term)
- [ ] Hyperparameter tuning (KFP loops or Katib integration)
- [ ] Automated model retraining on schedule
- [ ] Multi-dataset batch processing
- [ ] Integration with production serving (KServe)

---

## 📚 References

- **KFP v2 Documentation**: https://www.kubeflow.org/docs/components/pipelines/v2/
- **KFP SDK Reference**: https://kubeflow-pipelines.readthedocs.io/
- **Component Authoring Guide**: https://www.kubeflow.org/docs/components/pipelines/v2/components/
- **Pipeline Compilation**: https://www.kubeflow.org/docs/components/pipelines/v2/compile-a-pipeline/

---

## ✅ Task 8 Completion Summary

**Deliverables Created**:
1. ✅ `kubeflow_pipeline/pipeline.py` - Complete pipeline definition with all 6 components
2. ✅ `kubeflow_pipeline/compile_pipeline.py` - Compilation script with CLI interface
3. ✅ `kubeflow_pipeline/README.md` - Comprehensive user documentation
4. ✅ `TASK_8.md` - This document (architecture, contracts, testing, troubleshooting)

**Validation Status**:
- ✅ Pipeline structure correct (DAG with proper dependencies)
- ✅ All 6 components integrated
- ✅ Artifact chaining validated (Dataset → Model → Artifact flow)
- ✅ Parameter types compatible with KFP v2
- ✅ Compilation script functional
- ⏳ End-to-end execution test (requires KFP cluster deployment)

**Next Steps** (Task 9+):
- Deploy pipeline to KFP cluster
- Run end-to-end validation tests
- Monitor production runs
- Iterate based on performance metrics

---

**Task 8 Status**: ✅ **COMPLETE**  
**Date Completed**: November 25, 2025
