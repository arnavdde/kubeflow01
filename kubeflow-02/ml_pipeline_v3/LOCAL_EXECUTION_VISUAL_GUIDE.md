# Local Pipeline Execution - Visual Guide

## Architecture Comparison

### Containerized Pipeline (KFP v2)
```
┌─────────────────────────────────────────────────────────────────────┐
│                        Kubeflow Pipelines                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Kubernetes Cluster                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │  │
│  │  │ Preprocess  │  │   Train     │  │    Eval     │          │  │
│  │  │  Container  │→ │  Containers │→ │  Container  │          │  │
│  │  │  (Docker)   │  │   (Docker)  │  │  (Docker)   │          │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │  │
│  │         │                │                 │                  │  │
│  └─────────┼────────────────┼─────────────────┼──────────────────┘  │
│            ↓                ↓                 ↓                      │
│    ┌────────────────────────────────────────────────┐               │
│    │              MinIO (S3 Storage)                │               │
│    │  - Datasets      - Models      - Metrics       │               │
│    └────────────────────────────────────────────────┘               │
│                                                                      │
│    ┌────────────────────────────────────────────────┐               │
│    │              Kafka (Messaging)                 │               │
│    │  - training-data  - model-training  - etc.     │               │
│    └────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

### Local Execution (This Implementation)
```
┌─────────────────────────────────────────────────────────────────────┐
│                    Local Python Environment                         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              run_pipeline_locally.py                         │  │
│  │                                                               │  │
│  │  Step 1: Preprocess  ────────────────────────────┐           │  │
│  │      ↓                                            │           │  │
│  │  Step 2a: Train GRU  ─┐                          │           │  │
│  │  Step 2b: Train LSTM ─┤ (Sequential)             │           │  │
│  │  Step 2c: Train Prophet┘                         │           │  │
│  │      ↓                                            │           │  │
│  │  Step 3: Evaluate  ───────────────────────────┐  │           │  │
│  │      ↓                                         │  │           │  │
│  │  Step 4: Inference  ──────────────────────┐   │  │           │  │
│  │                                            ↓   ↓  ↓           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                               │   │  │               │
│                                               ↓   ↓  ↓               │
│    ┌────────────────────────────────────────────────────┐           │
│    │       Local File System (local_artifacts/)         │           │
│    │  - processed_data/  - models/  - metrics/          │           │
│    │  - evaluations/     - predictions/                 │           │
│    └────────────────────────────────────────────────────┘           │
│                                                                      │
│  No Docker ❌  No Kubernetes ❌  No MinIO ❌  No Kafka ❌           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  USER                                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
         ./quickstart_local.sh
         (or python run_pipeline_locally.py)
                     │
                     ↓
    ┌────────────────────────────────────────┐
    │  STEP 0: Environment Setup             │
    │  - Check Python version                │
    │  - Verify component directories        │
    │  - Validate dataset exists             │
    │  - Create artifact directories         │
    └────────────────┬───────────────────────┘
                     │ ✓ Environment OK
                     ↓
    ┌────────────────────────────────────────┐
    │  STEP 1: Data Preprocessing            │
    │  - Load dataset/{name}.csv             │
    │  - Split train (80%) / test (20%)      │
    │  - Save training_data.parquet          │
    │  - Save inference_data.parquet         │
    └────────────────┬───────────────────────┘
                     │ training_data ──────┐
                     │ inference_data ─┐   │
                     ↓                 │   │
    ┌────────────────────────────────────────┐
    │  STEP 2a: Train GRU Model              │
    │  Input: training_data.parquet          │
    │  - Create sequences (length 12)        │
    │  - Build GRU network (2 layers, 64)    │
    │  - Train 10 epochs                     │
    │  - Calculate metrics (MSE/RMSE/MAE)    │
    │  Output: models/GRU/model.pt           │
    │          metrics/GRU_metrics.json      │
    └────────────────┬───────────────────────┘
                     │ GRU model ─────┐
                     ↓                │
    ┌────────────────────────────────────────┐
    │  STEP 2b: Train LSTM Model             │
    │  Input: training_data.parquet          │
    │  - Create sequences                    │
    │  - Build LSTM network                  │
    │  - Train model                         │
    │  Output: models/LSTM/model.pt          │
    │          metrics/LSTM_metrics.json     │
    └────────────────┬───────────────────────┘
                     │ LSTM model ────┤
                     ↓                │
    ┌────────────────────────────────────────┐
    │  STEP 2c: Train Prophet Model          │
    │  Input: training_data.parquet          │
    │  - Prepare ds/y format                 │
    │  - Train Prophet                       │
    │  - Calculate metrics                   │
    │  Output: models/PROPHET/model.pkl      │
    │          metrics/PROPHET_metrics.json  │
    └────────────────┬───────────────────────┘
                     │ Prophet model ─┘
                     ↓
    ┌────────────────────────────────────────┐
    │  STEP 3: Model Evaluation              │
    │  Input: All 3 models + metrics         │
    │  - Load all metrics files              │
    │  - Calculate weighted scores:          │
    │    score = 0.5×RMSE + 0.3×MAE + 0.2×MSE│
    │  - Select best (lowest score)          │
    │  - Generate promotion pointer          │
    │  Output: evaluation_results.json       │
    │    { "best_model": "GRU" }             │
    └────────────────┬───────────────────────┘
                     │ best_model (GRU)
                     │ inference_data ─────────┘
                     ↓
    ┌────────────────────────────────────────┐
    │  STEP 4: Inference                     │
    │  Input: Best model (GRU)               │
    │         inference_data.parquet         │
    │  - Load promoted model                 │
    │  - Generate predictions (50 samples)   │
    │  - Calculate metrics on test data      │
    │  - Save predictions & actuals          │
    │  Output: predictions/predictions.csv   │
    │          predictions/inference_results │
    └────────────────┬───────────────────────┘
                     │
                     ↓
    ┌────────────────────────────────────────┐
    │  COMPLETE                              │
    │  All artifacts in local_artifacts/     │
    │  Best model: GRU                       │
    │  Predictions: 50 samples               │
    │  Runtime: ~3 minutes                   │
    └────────────────────────────────────────┘
```

---

## Data Flow

```
dataset/PobleSec.csv (8760 rows)
         │
         │ STEP 1: Preprocess
         │ (80/20 split)
         ↓
    ┌─────────────────┬─────────────────┐
    │                 │                 │
    ↓                 ↓                 ↓
training_data    inference_data    config.json
(7008 rows)      (1752 rows)       (metadata)
    │                 │
    │                 └──────────────────────┐
    │ STEP 2: Train                          │
    ↓                                        │
┌───────────────────────┐                   │
│  Create sequences     │                   │
│  (12 timesteps)       │                   │
│  6996 sequences       │                   │
└──────┬────────────────┘                   │
       │                                     │
       ├──→ GRU Model ──→ GRU metrics       │
       │                                     │
       ├──→ LSTM Model ─→ LSTM metrics      │
       │                                     │
       └──→ Prophet ────→ Prophet metrics   │
                │                            │
                │ STEP 3: Evaluate           │
                ↓                            │
         Best Model (GRU)                    │
                │                            │
                │ STEP 4: Inference          │
                │                            │
                └────────────────┬───────────┘
                                 ↓
                         predictions.csv
                         (50 predictions)
                         actual | predicted
                         42.3   | 41.8
                         43.1   | 42.9
                         ...
```

---

## File System Layout

```
ml_pipeline_v3/
│
├── run_pipeline_locally.py          ← Main execution script
├── quickstart_local.sh              ← Quick launcher
├── README_LOCAL.md                  ← Quick reference
├── LOCAL_EXECUTION_GUIDE.md         ← Complete guide
├── LOCAL_SETUP_SUMMARY.md           ← Setup summary
│
├── dataset/                         ← Input data
│   ├── PobleSec.csv
│   ├── ElBorn.csv
│   └── LesCorts.csv
│
├── local_artifacts/                 ← Output (created at runtime)
│   └── local-run-20241209-143022/
│       ├── processed_data/
│       │   ├── training_data.parquet
│       │   ├── inference_data.parquet
│       │   └── config.json
│       ├── models/
│       │   ├── GRU/
│       │   │   └── model.pt
│       │   ├── LSTM/
│       │   │   └── model.pt
│       │   └── PROPHET/
│       │       └── model.pkl
│       ├── metrics/
│       │   ├── GRU_metrics.json
│       │   ├── LSTM_metrics.json
│       │   └── PROPHET_metrics.json
│       ├── evaluations/
│       │   └── evaluation_results.json
│       └── predictions/
│           ├── inference_results.json
│           └── predictions.csv
│
├── preprocess_container/            ← Component source
├── train_container/
├── nonML_container/
├── eval_container/
├── inference_container/
│
└── kubeflow_pipeline/               ← KFP definitions
    ├── components_v2.py
    ├── pipeline_v2.py
    └── README.md
```

---

## Component Mapping

### KFP v2 Components → Local Scripts

```
┌─────────────────────────────────────────────────────────────────┐
│  KFP v2 Component          │  Local Execution                   │
├────────────────────────────┼────────────────────────────────────┤
│  @dsl.component            │  Python function in                │
│  preprocess_component      │  run_pipeline_locally.py           │
│  - base_image:             │  - Inline script generation        │
│    flts-preprocess:latest  │  - Direct pandas/numpy usage       │
│  - I/O: dsl.Output[Dataset]│  - Save to .parquet file          │
├────────────────────────────┼────────────────────────────────────┤
│  train_gru_component       │  run_train_model("GRU")            │
│  - base_image:             │  - PyTorch model definition        │
│    train-container:latest  │  - Training loop                   │
│  - I/O: dsl.Output[Model]  │  - Save to .pt file               │
├────────────────────────────┼────────────────────────────────────┤
│  train_lstm_component      │  run_train_model("LSTM")           │
│  train_prophet_component   │  run_train_model("PROPHET")        │
├────────────────────────────┼────────────────────────────────────┤
│  eval_component            │  run_evaluation()                  │
│  - Compare models          │  - Load all metrics JSON           │
│  - Select best             │  - Calculate weighted scores       │
│  - Write promotion pointer │  - Save evaluation_results.json    │
├────────────────────────────┼────────────────────────────────────┤
│  inference_component       │  run_inference()                   │
│  - Load promoted model     │  - Load best model file            │
│  - Generate predictions    │  - Predict on test data            │
│  - Save results            │  - Save predictions.csv            │
└────────────────────────────┴────────────────────────────────────┘
```

---

## Performance Comparison

```
┌──────────────────────────────────────────────────────────────────┐
│  Metric              │  Containerized  │  Local Execution       │
├──────────────────────┼─────────────────┼────────────────────────┤
│  Setup Time          │  ~10 minutes    │  < 1 minute            │
│  First Run           │  ~5 minutes     │  ~3 minutes            │
│  Subsequent Runs     │  ~5 minutes     │  ~3 minutes            │
│  Disk Space          │  ~2 GB (images) │  ~50 MB (artifacts)    │
│  Memory Usage        │  ~4 GB          │  ~1 GB                 │
│  CPU Usage           │  Multiple pods  │  Single process        │
│  Parallelization     │  Native         │  Sequential simulation │
│  Artifact Access     │  Via MinIO API  │  Direct file access    │
│  Debugging           │  Container logs │  Python stack traces   │
│  Iteration Speed     │  Moderate       │  Fast                  │
└──────────────────────┴─────────────────┴────────────────────────┘
```

---

## Model Training Details

### GRU Model
```
Architecture:
  Input → GRU(64, layers=2) → Linear(1) → Output

Training:
  Optimizer: Adam(lr=0.001)
  Loss: MSELoss
  Epochs: 10
  Batch size: 32
  Sequences: 6996 (from 7008 training samples)
  Sequence length: 12 timesteps

Output:
  model.pt (PyTorch checkpoint)
  - model_state_dict
  - scaler (MinMaxScaler)
  - hyperparameters
```

### LSTM Model
```
Architecture:
  Input → LSTM(64, layers=2) → Linear(1) → Output

Training:
  Same as GRU (only RNN type differs)

Output:
  model.pt (PyTorch checkpoint)
```

### Prophet Model
```
Architecture:
  Statistical model (not neural network)
  - Trend: Piecewise linear
  - Seasonality: Multiplicative
  - Components: Yearly + Weekly

Training:
  No epochs (single fit)
  Uses Stan optimization

Output:
  model.pkl (Prophet object)
```

---

## Evaluation Scoring

```
For each model (GRU, LSTM, Prophet):

1. Calculate metrics on training data:
   - MSE  = mean((predicted - actual)²)
   - RMSE = sqrt(MSE)
   - MAE  = mean(|predicted - actual|)

2. Calculate composite score:
   score = 0.5 × RMSE + 0.3 × MAE + 0.2 × MSE
   
3. Select model with lowest score

Example:
┌─────────┬────────┬────────┬────────┬────────┐
│ Model   │  MSE   │  RMSE  │  MAE   │ Score  │
├─────────┼────────┼────────┼────────┼────────┤
│ GRU     │ 0.0284 │ 0.1686 │ 0.1325 │ 0.1575 │ ← Best
│ LSTM    │ 0.0298 │ 0.1727 │ 0.1382 │ 0.1642 │
│ PROPHET │ 0.0356 │ 0.1887 │ 0.1459 │ 0.1786 │
└─────────┴────────┴────────┴────────┴────────┘

Winner: GRU (score: 0.1575)
```

---

## Quick Command Reference

```bash
# Run pipeline (default)
./quickstart_local.sh

# Run with specific dataset
./quickstart_local.sh ElBorn

# Direct Python execution
python run_pipeline_locally.py --dataset LesCorts --identifier test-001

# View best model
cat local_artifacts/*/evaluations/evaluation_results.json | jq '.best_model'

# View predictions
head local_artifacts/*/predictions/predictions.csv

# Compare all models
jq -s '.' local_artifacts/*/metrics/*_metrics.json

# Clean artifacts
rm -rf local_artifacts/

# Get help
python run_pipeline_locally.py --help
```

---

## Success Indicators

When pipeline completes successfully, you should see:

```
✓ Environment Setup complete
✓ Preprocessing complete
✓ GRU training complete
✓ LSTM training complete
✓ Prophet training complete
✓ Best Model: [GRU|LSTM|PROPHET] (score: X.XXXX)
✓ Inference complete
✓ Total execution time: XXX.XX seconds
```

And these files created:

```
local_artifacts/{identifier}/
├── processed_data/          ← 2 parquet files + config
├── models/                  ← 3 model files (pt/pkl)
├── metrics/                 ← 3 JSON files
├── evaluations/             ← 1 JSON file
└── predictions/             ← 1 CSV + 1 JSON
```

**Total files:** 11  
**Total size:** ~20-50 MB  
**Time to results:** 2-5 minutes

---

**Ready to execute? Run:** `./quickstart_local.sh`
