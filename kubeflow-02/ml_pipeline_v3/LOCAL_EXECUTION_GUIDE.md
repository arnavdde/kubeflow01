# Local Pipeline Execution Guide

Complete guide for running the FLTS pipeline locally without Docker containers, Kubernetes, or Kubeflow.

## Overview

This guide provides a **fully local** execution path that:

- ✅ Runs all pipeline components directly using Python
- ✅ Uses local file system for artifacts (no MinIO/S3)
- ✅ Executes the complete DAG: Preprocess → Train → Evaluate → Inference
- ✅ Simulates the KFP v2 pipeline defined in `kubeflow_pipeline/pipeline_v2.py`
- ❌ Does NOT require Docker containers
- ❌ Does NOT require Kafka message queuing
- ❌ Does NOT require Kubeflow cluster
- ❌ Does NOT include Locust stress testing

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Pipeline Steps](#pipeline-steps)
4. [Configuration](#configuration)
5. [Output Artifacts](#output-artifacts)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)

---

## Prerequisites

### 1. Python Environment

Requires Python 3.11+ with necessary dependencies:

```bash
# Navigate to project directory
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Activate virtual environment (if using)
source /Users/arnavde/Python/AI/.venv/bin/activate

# Install core dependencies
pip install pandas numpy scikit-learn torch prophet
```

**Note:** The script will automatically detect and use your virtual environment if available.

### 2. Dataset Files

Ensure dataset files exist in the `dataset/` directory:

```bash
ls -lh dataset/
# Should show:
#   PobleSec.csv
#   ElBorn.csv
#   LesCorts.csv
```

### 3. Component Source Code

Verify all component directories exist:

```bash
ls -d *_container/
# Should show:
#   preprocess_container/
#   train_container/
#   nonML_container/
#   eval_container/
#   inference_container/
```

---

## Quick Start

### Basic Execution

Run the pipeline with default settings (PobleSec dataset):

```bash
python run_pipeline_locally.py
```

**Expected Output:**

```
================================================================================
FLTS Pipeline - Local Execution
================================================================================

ℹ Dataset: PobleSec
ℹ Identifier: local-run-20241209-143022
ℹ Artifacts: /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20241209-143022

[Step 0] Environment Setup
--------------------------------------------------------------------------------
✓ Found: preprocess_container
✓ Found: train_container
✓ Found: nonML_container
✓ Found: eval_container
✓ Found: inference_container
✓ Dataset found: /path/to/dataset/PobleSec.csv
✓ Artifacts directory: /path/to/local_artifacts/local-run-20241209-143022
✓ Environment Setup complete

[Step 1] Data Preprocessing
--------------------------------------------------------------------------------
Loading dataset: /path/to/dataset/PobleSec.csv
Loaded 8760 rows
Train: 7008 rows, Test: 1752 rows
✓ Training data saved to: .../processed_data/training_data.parquet
✓ Inference data saved to: .../processed_data/inference_data.parquet
✓ Config saved to: .../processed_data/config.json
✓ Preprocessing complete

[Step 2] Model Training
--------------------------------------------------------------------------------

Training GRU model...
Loading training data from: .../processed_data/training_data.parquet
Loaded 7008 training samples
Using target column: value
Created 6996 sequences
Training model...
Epoch [2/10], Loss: 0.042315
Epoch [4/10], Loss: 0.031456
...
Final Metrics:
  MSE:  0.028431
  RMSE: 0.168616
  MAE:  0.132487
✓ Model saved to: .../models/GRU/model.pt
✓ Metrics saved to: .../metrics/GRU_metrics.json
✓ GRU training complete

Training LSTM model...
...
✓ LSTM training complete

Training Prophet model...
...
✓ Prophet training complete

[Step 3] Model Evaluation & Selection
--------------------------------------------------------------------------------

Model Comparison:
Model      MSE          RMSE         MAE         
--------------------------------------------------
GRU        0.028431     0.168616     0.132487    
LSTM       0.029821     0.172688     0.138201    
PROPHET    0.035612     0.188711     0.145932    

✓ Best Model: GRU (score: 0.157492)
✓ Evaluation results saved to: .../evaluations/evaluation_results.json

[Step 4] Inference
--------------------------------------------------------------------------------
Using best model: GRU
Model path: .../models/GRU/model.pt
Loading model from: .../models/GRU/model.pt
Loading inference data from: .../processed_data/inference_data.parquet

Generated 38 predictions

Inference Metrics:
  MSE:  0.031245
  RMSE: 0.176765
  MAE:  0.141823
✓ Results saved to: .../predictions/inference_results.json
✓ Predictions saved to: .../predictions/predictions.csv
✓ Inference complete

================================================================================
Pipeline Execution Complete
================================================================================
✓ Total execution time: 127.43 seconds
ℹ Artifacts saved to: /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20241209-143022

================================================================================
Pipeline Summary:
================================================================================
  Dataset:          PobleSec
  Identifier:       local-run-20241209-143022
  Best Model:       GRU
  Artifacts Dir:    /path/to/local_artifacts/local-run-20241209-143022
================================================================================
```

### Custom Dataset

Run with a different dataset:

```bash
python run_pipeline_locally.py --dataset ElBorn
```

### Custom Identifier

Specify a custom run identifier:

```bash
python run_pipeline_locally.py --identifier my-experiment-001
```

### Combined Options

```bash
python run_pipeline_locally.py --dataset LesCorts --identifier les-corts-baseline
```

---

## Pipeline Steps

The local execution script mirrors the KFP v2 pipeline DAG:

### Step 0: Environment Setup

**Purpose:** Validate prerequisites and create output directories

**Actions:**
- Check component directories exist
- Verify dataset file exists
- Create artifact directories:
  - `processed_data/` - Preprocessed datasets
  - `models/` - Trained model files
  - `metrics/` - Training metrics
  - `evaluations/` - Model comparison results
  - `predictions/` - Inference outputs

**Outputs:** None (validation only)

---

### Step 1: Data Preprocessing

**Purpose:** Load and transform raw CSV data into train/test splits

**Process:**
1. Load dataset from `dataset/{dataset_name}.csv`
2. Split into training (80%) and testing (20%)
3. Save as Parquet files for efficient I/O
4. Generate config hash for reproducibility

**Outputs:**
- `processed_data/training_data.parquet` - Training dataset
- `processed_data/inference_data.parquet` - Test dataset
- `processed_data/config.json` - Preprocessing metadata

**Configuration:**
- Normalization: MinMaxScaler
- NaN handling: Enabled (threshold 33%)
- Time features: Enabled
- Lags: Disabled (configurable)

---

### Step 2: Model Training (Parallel)

**Purpose:** Train three models simultaneously (simulated sequentially in local mode)

#### 2a. Train GRU Model

**Architecture:**
- Gated Recurrent Unit (GRU) with 2 layers
- Hidden size: 64
- Sequence length: 12 time steps
- Output: Single-step forecast

**Training:**
- Optimizer: Adam (lr=0.001)
- Loss: MSE
- Epochs: 10
- Batch size: 32

**Outputs:**
- `models/GRU/model.pt` - Trained PyTorch model
- `metrics/GRU_metrics.json` - MSE, RMSE, MAE

#### 2b. Train LSTM Model

**Architecture:**
- Long Short-Term Memory (LSTM) with 2 layers
- Same hyperparameters as GRU

**Outputs:**
- `models/LSTM/model.pt`
- `metrics/LSTM_metrics.json`

#### 2c. Train Prophet Model

**Architecture:**
- Facebook Prophet statistical model
- Seasonality: Multiplicative
- Components: Yearly + Weekly (no daily)

**Outputs:**
- `models/PROPHET/model.pkl`
- `metrics/PROPHET_metrics.json`

---

### Step 3: Model Evaluation & Selection

**Purpose:** Compare all models and promote the best performer

**Evaluation Criteria:**

Weighted composite score (lower is better):

```
score = 0.5 × RMSE + 0.3 × MAE + 0.2 × MSE
```

**Process:**
1. Load metrics from all three models
2. Calculate weighted scores
3. Select model with lowest score
4. Generate promotion pointer

**Outputs:**
- `evaluations/evaluation_results.json` - Contains:
  - `best_model`: Winning model type (GRU/LSTM/PROPHET)
  - `best_score`: Composite score
  - `all_scores`: Scores for all models
  - `all_metrics`: Complete metrics from all models

**Example Output:**

```json
{
  "best_model": "GRU",
  "best_score": 0.157492,
  "all_scores": {
    "GRU": 0.157492,
    "LSTM": 0.164234,
    "PROPHET": 0.178643
  },
  "all_metrics": {
    "GRU": {
      "mse": 0.028431,
      "rmse": 0.168616,
      "mae": 0.132487
    },
    ...
  }
}
```

---

### Step 4: Inference

**Purpose:** Generate predictions using the promoted model

**Process:**
1. Load best model from evaluation results
2. Load inference (test) data
3. Generate predictions on 50 test samples
4. Calculate inference metrics
5. Save predictions and metadata

**Outputs:**
- `predictions/inference_results.json` - Contains:
  - Model type used
  - First 10 predictions and actuals
  - Inference metrics (MSE, RMSE, MAE)
- `predictions/predictions.csv` - Full predictions:
  ```csv
  actual,predicted
  42.3,41.8
  43.1,42.9
  ...
  ```

---

## Configuration

### Dataset Selection

Available datasets:

| Dataset    | Description           | Size     |
|------------|-----------------------|----------|
| PobleSec   | Poble Sec district    | ~8760 rows |
| ElBorn     | El Born district      | ~8760 rows |
| LesCorts   | Les Corts district    | ~8760 rows |

**Usage:**

```bash
python run_pipeline_locally.py --dataset PobleSec
```

### Run Identifier

The identifier tags all artifacts for tracking:

**Auto-generated (default):**

```bash
python run_pipeline_locally.py
# Creates: local-run-20241209-143022
```

**Manual:**

```bash
python run_pipeline_locally.py --identifier experiment-001
```

### Model Hyperparameters

To customize training parameters, edit the script constants:

```python
# In run_pipeline_locally.py

# GRU/LSTM parameters
hidden_size = 64        # Hidden layer size
num_layers = 2          # Number of RNN layers
learning_rate = 0.001   # Adam learning rate
batch_size = 32         # Training batch size
num_epochs = 10         # Training epochs

# Prophet parameters
seasonality_mode = "multiplicative"
yearly_seasonality = True
weekly_seasonality = True
```

---

## Output Artifacts

All artifacts are saved to:

```
local_artifacts/{identifier}/
├── processed_data/
│   ├── training_data.parquet    # Training dataset
│   ├── inference_data.parquet   # Test dataset
│   └── config.json              # Preprocessing config
├── models/
│   ├── GRU/
│   │   └── model.pt             # GRU PyTorch model
│   ├── LSTM/
│   │   └── model.pt             # LSTM PyTorch model
│   └── PROPHET/
│       └── model.pkl            # Prophet pickle model
├── metrics/
│   ├── GRU_metrics.json         # GRU training metrics
│   ├── LSTM_metrics.json        # LSTM training metrics
│   └── PROPHET_metrics.json     # Prophet training metrics
├── evaluations/
│   └── evaluation_results.json  # Model comparison
└── predictions/
    ├── inference_results.json   # Prediction summary
    └── predictions.csv          # Full predictions
```

### Artifact Sizes (Approximate)

- Processed data: 5-10 MB per dataset
- Models: 1-5 MB each
- Metrics: < 1 KB each
- Predictions: 10-100 KB

### Accessing Results

**View evaluation results:**

```bash
cat local_artifacts/{identifier}/evaluations/evaluation_results.json | jq .
```

**View predictions:**

```bash
head local_artifacts/{identifier}/predictions/predictions.csv
```

**Compare model metrics:**

```bash
jq -s '.' local_artifacts/{identifier}/metrics/*_metrics.json
```

---

## Troubleshooting

### Issue: Python Version

**Error:**

```
SyntaxError: f-string expression part cannot include a backslash
```

**Solution:** Requires Python 3.11+

```bash
python --version  # Should be 3.11.x or higher
```

### Issue: Missing Dependencies

**Error:**

```
ModuleNotFoundError: No module named 'torch'
```

**Solution:** Install required packages

```bash
pip install pandas numpy scikit-learn torch prophet
```

**For Prophet on macOS:**

```bash
# If Prophet installation fails, try:
conda install -c conda-forge prophet
# OR
pip install prophet --no-build-isolation
```

### Issue: Dataset Not Found

**Error:**

```
✗ Dataset not found: /path/to/dataset/PobleSec.csv
```

**Solution:** Verify dataset exists

```bash
ls -lh dataset/PobleSec.csv
```

If missing, check available datasets:

```bash
ls dataset/*.csv
```

### Issue: Out of Memory

**Error:**

```
RuntimeError: CUDA out of memory
```

**Solution:** Training uses CPU by default (no GPU required). If still running out of memory:

1. Reduce batch size (edit script, set `batch_size = 16`)
2. Reduce model size (set `hidden_size = 32`)
3. Sample dataset (modify preprocessing to use fewer rows)

### Issue: Slow Execution

**Expected Times:**

- Preprocessing: 5-10 seconds
- Training (per model): 30-60 seconds
- Evaluation: < 1 second
- Inference: 5-10 seconds
- **Total: ~2-5 minutes**

**Optimization:**

1. Use virtual environment (faster imports)
2. Reduce `num_epochs` to 5 for quick testing
3. Use SSD for artifacts directory

### Issue: Permission Denied

**Error:**

```
PermissionError: [Errno 13] Permission denied: 'local_artifacts/...'
```

**Solution:**

```bash
chmod -R u+w local_artifacts/
```

---

## Advanced Usage

### Batch Processing Multiple Datasets

```bash
#!/bin/bash
# run_all_datasets.sh

for dataset in PobleSec ElBorn LesCorts; do
  echo "Processing $dataset..."
  python run_pipeline_locally.py \
    --dataset $dataset \
    --identifier batch-$(date +%Y%m%d)-$dataset
done
```

### Extract Best Model Performance

```python
import json
from pathlib import Path

identifier = "local-run-20241209-143022"
eval_path = Path(f"local_artifacts/{identifier}/evaluations/evaluation_results.json")

with open(eval_path) as f:
    results = json.load(f)

best_model = results["best_model"]
best_metrics = results["all_metrics"][best_model]

print(f"Best Model: {best_model}")
print(f"  RMSE: {best_metrics['rmse']:.4f}")
print(f"  MAE:  {best_metrics['mae']:.4f}")
```

### Compare Multiple Runs

```python
import json
from pathlib import Path
import pandas as pd

runs = ["run-001", "run-002", "run-003"]
results = []

for run_id in runs:
    eval_path = Path(f"local_artifacts/{run_id}/evaluations/evaluation_results.json")
    with open(eval_path) as f:
        data = json.load(f)
        results.append({
            "run_id": run_id,
            "best_model": data["best_model"],
            "best_score": data["best_score"],
        })

df = pd.DataFrame(results)
print(df)
```

### Visualize Predictions

```python
import pandas as pd
import matplotlib.pyplot as plt

identifier = "local-run-20241209-143022"
pred_path = f"local_artifacts/{identifier}/predictions/predictions.csv"

df = pd.read_csv(pred_path)

plt.figure(figsize=(12, 6))
plt.plot(df.index, df['actual'], label='Actual', marker='o')
plt.plot(df.index, df['predicted'], label='Predicted', marker='x')
plt.xlabel('Sample Index')
plt.ylabel('Value')
plt.title('Model Predictions vs Actuals')
plt.legend()
plt.grid(True)
plt.savefig(f'local_artifacts/{identifier}/predictions/plot.png')
plt.show()
```

---

## Comparison to KFP Pipeline

### Equivalence Table

| KFP Component          | Local Execution          | Notes                    |
|------------------------|--------------------------|--------------------------|
| `preprocess_component` | Step 1 script            | File-based I/O           |
| `train_gru_component`  | Step 2a script           | PyTorch training         |
| `train_lstm_component` | Step 2b script           | PyTorch training         |
| `train_prophet_component` | Step 2c script        | Prophet training         |
| `eval_component`       | Step 3 script            | JSON-based comparison    |
| `inference_component`  | Step 4 script            | Model loading + prediction |

### Differences

| Feature                | KFP Pipeline             | Local Execution          |
|------------------------|--------------------------|--------------------------|
| **Orchestration**      | Kubeflow Pipelines       | Python script            |
| **Storage**            | MinIO/S3                 | Local file system        |
| **Messaging**          | Kafka topics             | Direct function calls    |
| **Parallelization**    | Native (k8s pods)        | Sequential simulation    |
| **Artifacts**          | KFP Metadata Store       | JSON files               |
| **Monitoring**         | KFP UI                   | Terminal output          |
| **Reproducibility**    | Pipeline runs            | Run identifier           |

---

## Next Steps

### 1. Analyze Results

Inspect artifacts to understand model performance:

```bash
cd local_artifacts/{identifier}
cat evaluations/evaluation_results.json | jq .
head predictions/predictions.csv
```

### 2. Iterate on Hyperparameters

Edit `run_pipeline_locally.py` to tune:
- Model architecture (hidden_size, num_layers)
- Training parameters (learning_rate, num_epochs)
- Preprocessing options (scaler, time_features)

### 3. Compare Datasets

Run on all three datasets and compare results:

```bash
python run_pipeline_locally.py --dataset PobleSec --identifier pobleSec-v1
python run_pipeline_locally.py --dataset ElBorn --identifier elBorn-v1
python run_pipeline_locally.py --dataset LesCorts --identifier lesCorts-v1
```

### 4. Deploy to KFP (Step 9)

Once satisfied with local results, deploy to Kubeflow:

1. Compile pipeline: `python kubeflow_pipeline/compile_pipeline_v2.py`
2. Upload `artifacts/flts_pipeline_v2.json` to KFP UI
3. Create pipeline run with parameters
4. Monitor execution in KFP dashboard

See `kubeflow_pipeline/README.md` for Step 9 instructions (not covered in this guide).

---

## Summary

This local execution approach provides:

✅ **Complete pipeline validation** without infrastructure overhead  
✅ **Rapid iteration** on preprocessing and model configurations  
✅ **Full transparency** with direct access to artifacts  
✅ **Easy debugging** with Python stack traces  
✅ **Reproducible results** via run identifiers  

**Execution Time:** 2-5 minutes per run  
**Storage Required:** ~20-50 MB per run  
**Computational Requirements:** CPU-only (no GPU needed)  

**Recommended for:**
- Local development and testing
- Hyperparameter tuning experiments
- Model comparison studies
- Educational demonstrations

**NOT recommended for:**
- Production deployments
- Large-scale batch processing
- Real-time inference
- Distributed training

For production use cases, proceed to containerized deployment with Kubeflow Pipelines (Step 9).

---

**Questions?** See `kubeflow_pipeline/README.md` or inspect the component source code in `*_container/` directories.
