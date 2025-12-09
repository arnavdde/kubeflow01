# FLTS Kubeflow Pipeline (KFP v2)

**Complete time-series forecasting pipeline for Kubeflow Pipelines v2**

This directory contains the full KFP v2 pipeline definition for the FLTS (Forecasting Load Time Series) project. The pipeline orchestrates preprocessing, multi-model training, evaluation, and inference using containerized components.

---

## 📋 Table of Contents

- [Architecture](#architecture)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Pipeline Parameters](#pipeline-parameters)
- [Compilation](#compilation)
- [Deployment](#deployment)
- [Execution](#execution)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## 🏗️ Architecture

### Pipeline Flow

```
┌─────────────────┐
│   Preprocess    │  Load CSV, transform, split
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┐
         ▼                  ▼                  ▼
    ┌─────────┐       ┌──────────┐      ┌──────────┐
    │   GRU   │       │   LSTM   │      │  Prophet │  Train 3 models
    │ Training│       │ Training │      │ Training │  (parallel)
    └────┬────┘       └─────┬────┘      └─────┬────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            ▼
                    ┌───────────────┐
                    │  Evaluation   │  Select best model
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Inference    │  Generate predictions
                    └───────────────┘
```

### Artifact Flow

| Component | Inputs | Outputs |
|-----------|--------|---------|
| **Preprocess** | CSV files from MinIO | `training_data` (Dataset)<br>`inference_data` (Dataset)<br>`config_hash` (String)<br>`config_json` (String) |
| **Train GRU** | `training_data` (Dataset) | `model` (Model)<br>`metrics` (Artifact)<br>`run_id` (String) |
| **Train LSTM** | `training_data` (Dataset) | `model` (Model)<br>`metrics` (Artifact)<br>`run_id` (String) |
| **Train Prophet** | `training_data` (Dataset) | `model` (Model)<br>`metrics` (Artifact)<br>`run_id` (String) |
| **Eval** | `gru_model`, `lstm_model`, `prophet_model` (Models) | `promotion_pointer` (Artifact)<br>`eval_metadata` (Artifact) |
| **Inference** | `inference_data` (Dataset)<br>`promoted_model` (Model) | `inference_results` (Artifact)<br>`inference_metadata` (Artifact) |

---

## 🧩 Components

### 1. Preprocess (`components/preprocess/`)
- **Image**: `flts-preprocess:latest`
- **Purpose**: Load raw CSV, apply transformations (scaling, feature engineering), split into train/test
- **Key Features**:
  - Configurable sampling (head/tail/random)
  - NaN handling (KNN imputation)
  - Outlier clipping (IQR/percentile)
  - Time feature extraction (hour, day, month)
  - Multiple scalers (MinMax, Standard, Robust)

### 2. Train GRU (`components/train_gru/`)
- **Image**: `train-container:latest`
- **Purpose**: Train Gated Recurrent Unit (GRU) model
- **Key Features**:
  - Configurable architecture (hidden size, layers, dropout)
  - Early stopping with patience
  - MLflow integration for tracking
  - CUDA-enabled training

### 3. Train LSTM (`components/train_lstm/`)
- **Image**: `train-container:latest`
- **Purpose**: Train Long Short-Term Memory (LSTM) model
- **Key Features**: Same as GRU with LSTM architecture

### 4. Train Prophet (`components/train_prophet/`)
- **Image**: `train-container:latest`
- **Purpose**: Train Facebook Prophet statistical model
- **Key Features**:
  - Seasonality modeling (yearly, weekly, daily)
  - Changepoint detection
  - Holiday effects

### 5. Eval (`components/eval/`)
- **Image**: `eval-container:latest`
- **Purpose**: Compare all models, select best performer
- **Key Features**:
  - Weighted composite score (RMSE, MAE, MSE)
  - Model promotion with canonical pointer
  - Detailed evaluation metadata

### 6. Inference (`components/inference/`)
- **Image**: `inference-container:latest`
- **Purpose**: Run predictions using promoted model
- **Key Features**:
  - Configurable inference length
  - Microbatching support
  - JSONL output format

---

## ⚙️ Prerequisites

### Infrastructure Requirements
1. **Kubeflow Pipelines v2** (v2.0.0+)
   - Installed on Kubernetes cluster
   - KFP SDK v2 installed locally (`pip install kfp>=2.0.0`)

2. **MinIO** (S3-compatible storage)
   - Running at `http://minio:9000` (or custom endpoint)
   - Buckets: `dataset`, `processed-data`, `model-promotion`, `inference-logs`

3. **MLflow** (experiment tracking)
   - Running at `http://mlflow:5000` (or custom endpoint)
   - Configured with MinIO backend

4. **FastAPI Gateway** (optional)
   - MinIO REST API at `http://fastapi-app:8000`

### Docker Images
All 6 component images must be built and accessible to Kubernetes:

```bash
# Build all images
docker-compose -f docker-compose.kfp.yaml build

# Push to registry (if using remote cluster)
docker tag flts-preprocess:latest <your-registry>/flts-preprocess:latest
docker push <your-registry>/flts-preprocess:latest
# ... repeat for other images
```

Required images:
- `flts-preprocess:latest`
- `train-container:latest`
- `eval-container:latest`
- `inference-container:latest`

### Python Environment
```bash
pip install kfp>=2.0.0
```

---

## 🚀 Quick Start

### 1. Compile the Pipeline

```bash
cd kubeflow_pipeline
python compile_pipeline.py
```

Output: `pipeline.job.yaml`

### 2. Upload to KFP UI

1. Navigate to Kubeflow Pipelines UI
2. Click **Pipelines** → **Upload Pipeline**
3. Select `pipeline.job.yaml`
4. Name: "FLTS Time Series Forecasting"
5. Click **Create**

### 3. Create a Run

1. Click **Create Run** from pipeline page
2. Select experiment (or create new)
3. Configure parameters (see [Pipeline Parameters](#pipeline-parameters))
4. Click **Start**

### 4. Monitor Execution

- View run progress in KFP dashboard
- Check component logs for detailed output
- Inspect artifacts in MinIO buckets
- View metrics in MLflow UI

---

## 📊 Pipeline Parameters

### Preprocessing Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dataset_name` | string | `"PobleSec"` | Dataset to process (CSV filename without extension) |
| `identifier` | string | `"flts-run-001"` | Unique run identifier for lineage tracking |
| `sample_train_rows` | int | `0` | Rows to sample for training (0=all) |
| `sample_test_rows` | int | `0` | Rows to sample for testing (0=all) |
| `sample_strategy` | string | `"head"` | Sampling method: `head`, `tail`, `random` |
| `sample_seed` | int | `42` | Random seed for reproducibility |
| `handle_nans` | bool | `true` | Enable NaN imputation |
| `nans_threshold` | float | `0.33` | Drop columns with >33% NaNs |
| `nans_knn` | int | `2` | KNN neighbors for imputation |
| `clip_enable` | bool | `false` | Enable outlier clipping |
| `clip_method` | string | `"iqr"` | Clipping method: `iqr`, `percentile` |
| `time_features_enable` | bool | `true` | Extract time features (hour, day, etc.) |
| `lags_enable` | bool | `false` | Add lagged features |
| `scaler` | string | `"MinMaxScaler"` | Scaler: `MinMaxScaler`, `StandardScaler`, `RobustScaler` |

### Training Parameters (shared across GRU/LSTM)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hidden_size` | int | `64` | Hidden layer size |
| `num_layers` | int | `2` | Number of RNN layers |
| `dropout` | float | `0.2` | Dropout rate |
| `learning_rate` | float | `0.001` | Adam optimizer learning rate |
| `batch_size` | int | `32` | Training batch size |
| `num_epochs` | int | `50` | Maximum training epochs |
| `early_stopping_patience` | int | `10` | Epochs to wait before stopping |
| `window_size` | int | `12` | Time series window size |

### Prophet Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seasonality_mode` | string | `"multiplicative"` | Seasonality: `additive`, `multiplicative` |
| `changepoint_prior_scale` | float | `0.05` | Changepoint flexibility |
| `yearly_seasonality` | bool | `true` | Enable yearly patterns |
| `weekly_seasonality` | bool | `true` | Enable weekly patterns |
| `daily_seasonality` | bool | `false` | Enable daily patterns |

### Evaluation Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rmse_weight` | float | `0.5` | RMSE weight in composite score |
| `mae_weight` | float | `0.3` | MAE weight in composite score |
| `mse_weight` | float | `0.2` | MSE weight in composite score |

### Inference Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `inference_length` | int | `1` | Number of future steps to predict |
| `sample_idx` | int | `0` | Which sample to use for inference |
| `enable_microbatch` | string | `"false"` | Enable microbatching: `"true"`, `"false"` |
| `inference_batch_size` | int | `32` | Inference batch size |

### Infrastructure Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gateway_url` | string | `"http://fastapi-app:8000"` | FastAPI MinIO gateway URL |
| `mlflow_tracking_uri` | string | `"http://mlflow:5000"` | MLflow tracking server |
| `mlflow_s3_endpoint` | string | `"http://minio:9000"` | MLflow S3 endpoint (MinIO) |
| `input_bucket` | string | `"dataset"` | MinIO bucket for raw datasets |
| `output_bucket` | string | `"processed-data"` | MinIO bucket for preprocessed data |
| `promotion_bucket` | string | `"model-promotion"` | MinIO bucket for promotion pointers |
| `inference_log_bucket` | string | `"inference-logs"` | MinIO bucket for inference results |

---

## 🔧 Compilation

### Standard Compilation

```bash
python compile_pipeline.py
```

Output: `pipeline.job.yaml` in current directory

### Custom Options

```bash
# Custom output location
python compile_pipeline.py -o /path/to/output.yaml

# Specify components directory
python compile_pipeline.py -c ../custom_components

# Lightweight version (reduced parameters for testing)
python compile_pipeline.py --lightweight
```

### Verification

Check compilation success:
```bash
# Verify output file exists
ls -lh pipeline.job.yaml

# Inspect YAML structure
head -n 50 pipeline.job.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('pipeline.job.yaml'))"
```

---

## 🌐 Deployment

### Option 1: KFP UI (Recommended for Production)

1. **Navigate to KFP UI**:
   - Local: `http://localhost:8080` (port-forward if needed)
   - Remote: `https://<your-kubeflow-domain>/pipeline`

2. **Upload Pipeline**:
   - Click **Pipelines** → **Upload Pipeline**
   - Select `pipeline.job.yaml`
   - Name: "FLTS Time Series Forecasting v2"
   - Description: "End-to-end forecasting with GRU/LSTM/Prophet"
   - Click **Create**

3. **Verify Upload**:
   - Pipeline appears in list
   - Click to view DAG visualization

### Option 2: KFP SDK (Programmatic)

```python
import kfp

client = kfp.Client(host='http://localhost:8080')

# Upload pipeline
pipeline_id = client.upload_pipeline(
    pipeline_package_path='pipeline.job.yaml',
    pipeline_name='FLTS Time Series Forecasting v2'
)

print(f"Pipeline uploaded: {pipeline_id}")
```

### Option 3: kubectl (Direct YAML)

```bash
# Apply pipeline as Kubernetes resource
kubectl apply -f pipeline.job.yaml -n kubeflow
```

---

## ▶️ Execution

### Option 1: KFP UI

1. Click **Create Run** from pipeline page
2. **Run Details**:
   - Name: `flts-run-pobleSec-2024`
   - Experiment: Select or create new
3. **Parameters** (customize as needed):
   ```yaml
   dataset_name: "PobleSec"
   identifier: "pobleSec-run-001"
   num_epochs: 50
   hidden_size: 64
   ```
4. Click **Start**

### Option 2: KFP SDK

```python
import kfp

client = kfp.Client(host='http://localhost:8080')

# Create experiment
experiment = client.create_experiment('FLTS Production Runs')

# Submit run
run = client.run_pipeline(
    experiment_id=experiment.id,
    job_name='flts-run-pobleSec-001',
    pipeline_id='<your-pipeline-id>',
    params={
        'dataset_name': 'PobleSec',
        'identifier': 'pobleSec-run-001',
        'num_epochs': 50,
        'hidden_size': 64
    }
)

print(f"Run submitted: {run.id}")
```

### Quick Test Run (Lightweight)

For fast validation, use minimal parameters:

```python
params = {
    'dataset_name': 'PobleSec',
    'identifier': 'test-run-001',
    'sample_train_rows': 1000,  # Use subset
    'sample_test_rows': 100,
    'num_epochs': 10,           # Fewer epochs
    'early_stopping_patience': 3
}
```

---

## 📈 Monitoring

### KFP Dashboard

- **Run Status**: View overall pipeline status (Running/Succeeded/Failed)
- **Component Logs**: Click each component to view stdout/stderr
- **Artifacts**: Download output artifacts (models, metrics, predictions)
- **Execution Graph**: Visual DAG with component statuses

### Component Logs

**Via UI**:
1. Click on component in run graph
2. Select **Logs** tab
3. View real-time output

**Via kubectl**:
```bash
# List pods in run
kubectl get pods -n kubeflow | grep flts-run

# View logs
kubectl logs <pod-name> -n kubeflow

# Follow logs in real-time
kubectl logs -f <pod-name> -n kubeflow
```

### MinIO Artifacts

Check intermediate artifacts:
```bash
# List processed datasets
mc ls minio/processed-data/

# Download promotion pointer
mc cp minio/model-promotion/promotion-pointer-<identifier>.json ./

# View inference results
mc cat minio/inference-logs/inference-results-<identifier>.jsonl | jq
```

### MLflow Experiments

View training metrics:
1. Navigate to MLflow UI: `http://localhost:5000`
2. Select experiment: "FLTS Pipeline Runs"
3. Compare model performance (RMSE, MAE, loss curves)
4. Download model artifacts

---

## 🔍 Troubleshooting

### Compilation Errors

**Issue**: `FileNotFoundError: component.yaml not found`
```bash
# Solution: Verify components directory structure
ls components/*/component.yaml

# Expected:
# components/preprocess/component.yaml
# components/train_gru/component.yaml
# ...
```

**Issue**: `ModuleNotFoundError: No module named 'kfp'`
```bash
# Solution: Install KFP SDK
pip install kfp>=2.0.0
```

### Image Pull Errors

**Issue**: `ErrImagePull` in component pods
```bash
# Solution 1: Verify images exist locally
docker images | grep flts

# Solution 2: Push to accessible registry
docker tag flts-preprocess:latest <registry>/flts-preprocess:latest
docker push <registry>/flts-preprocess:latest

# Solution 3: Update component.yaml with full image path
# Edit components/preprocess/component.yaml
image: <registry>/flts-preprocess:latest
```

### Artifact Not Found

**Issue**: Component fails with "Artifact path not found"
```bash
# Solution: Check MinIO connectivity
kubectl exec -it <pod-name> -n kubeflow -- curl http://minio:9000

# Verify bucket exists
mc ls minio/<bucket-name>

# Check environment variables
kubectl exec <pod-name> -n kubeflow -- env | grep MINIO
```

### MLflow Connection Errors

**Issue**: "Connection refused to MLflow tracking server"
```bash
# Solution: Verify MLflow is running
kubectl get pods -n kubeflow | grep mlflow

# Port-forward for testing
kubectl port-forward -n kubeflow svc/mlflow 5000:5000

# Test connectivity from component
kubectl exec <pod-name> -n kubeflow -- curl http://mlflow:5000/health
```

### Training Failures

**Issue**: OOM (Out of Memory) errors during training
```yaml
# Solution: Reduce batch size in pipeline parameters
params:
  batch_size: 16  # Instead of 32
  num_epochs: 30  # Reduce if needed
```

**Issue**: NaN loss during training
```yaml
# Solution: Adjust learning rate and preprocessing
params:
  learning_rate: 0.0001  # Smaller LR
  clip_enable: true      # Enable outlier clipping
  handle_nans: true      # Ensure NaN handling
```

### Debugging Tips

1. **Enable verbose logging**:
   - Set `LOG_LEVEL=DEBUG` in component environment variables

2. **Check component health**:
   ```bash
   kubectl describe pod <pod-name> -n kubeflow
   ```

3. **Inspect artifact metadata**:
   ```bash
   mc cat minio/processed-data/<identifier>-metadata.json | jq
   ```

4. **Test components locally**:
   ```bash
   docker run -it --rm \
     -e USE_KFP=1 \
     -e MINIO_ENDPOINT=host.docker.internal:9000 \
     flts-preprocess:latest \
     python preprocess_container.py --help
   ```

---

## 🛠️ Development

### Local Testing

Test pipeline compilation without KFP cluster:
```bash
# Dry-run compilation
python compile_pipeline.py --output /tmp/test_pipeline.yaml

# Validate YAML
python -c "import yaml; yaml.safe_load(open('/tmp/test_pipeline.yaml'))"
```

### Modifying Components

After updating component code:

1. **Rebuild container**:
   ```bash
   docker-compose -f docker-compose.kfp.yaml build <service-name>
   ```

2. **Update component.yaml** (if signature changed):
   - Edit `components/<component>/component.yaml`
   - Update inputs/outputs

3. **Recompile pipeline**:
   ```bash
   python compile_pipeline.py
   ```

4. **Upload new version**:
   - Upload to KFP UI with incremented version
   - Or use same pipeline ID to overwrite

### Adding New Components

1. **Create component directory**:
   ```bash
   mkdir -p components/my_component
   ```

2. **Create component.yaml**:
   ```yaml
   name: my_component
   description: Custom component
   inputs:
     - {name: input_data, type: Dataset}
   outputs:
     - {name: output_data, type: Artifact}
   implementation:
     container:
       image: my-component:latest
       command: [python, my_component.py]
       args:
         - --input-data
         - {inputPath: input_data}
         - --output-data
         - {outputPath: output_data}
   ```

3. **Update pipeline.py**:
   - Load new component
   - Add to pipeline DAG

4. **Recompile and test**

### Version Control

Track pipeline versions:
```bash
# Tag compiled pipeline
git add pipeline.job.yaml
git commit -m "Pipeline v2.1.0: Added XGBoost component"
git tag v2.1.0
```

---

## 📚 Additional Resources

- [Kubeflow Pipelines Documentation](https://www.kubeflow.org/docs/components/pipelines/)
- [KFP SDK v2 Reference](https://kubeflow-pipelines.readthedocs.io/)
- [MinIO Python SDK](https://min.io/docs/minio/linux/developers/python/API.html)
- [MLflow Tracking](https://mlflow.org/docs/latest/tracking.html)

---

## 📝 License

Internal use only - FLTS Project

---

**Questions?** Contact the ML Infrastructure team or file an issue in the project repository.
