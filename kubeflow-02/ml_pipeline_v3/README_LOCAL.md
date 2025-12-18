# FLTS Pipeline - Local Execution

**Run the complete time-series forecasting pipeline locally without Docker, Kubernetes, or Kubeflow.**

---

## 🚀 Quick Start (30 seconds)

```bash
cd ml_pipeline_v3
./quickstart_local.sh
```

That's it! The script will:
1. ✅ Check Python version and dependencies
2. ✅ Install any missing packages
3. ✅ Run the complete pipeline (Preprocess → Train → Evaluate → Inference)
4. ✅ Save all artifacts to `local_artifacts/`

**Expected runtime:** 2-5 minutes

---

## 📋 What Gets Executed

The local pipeline mirrors the KFP v2 DAG defined in `kubeflow_pipeline/pipeline_v2.py`:

```
┌──────────────┐
│  Preprocess  │  Load CSV, split train/test
└──────┬───────┘
       │
       ├─────────────┬─────────────┐
       ▼             ▼             ▼
   ┌──────┐     ┌───────┐     ┌─────────┐
   │ GRU  │     │ LSTM  │     │ Prophet │  Train 3 models
   └──┬───┘     └───┬───┘     └────┬────┘
      │             │              │
      └─────────────┼──────────────┘
                    ▼
             ┌─────────────┐
             │ Evaluation  │  Select best model
             └──────┬──────┘
                    ▼
             ┌────────────┐
             │ Inference  │  Generate predictions
             └────────────┘
```

**Output:** Best model selected and predictions generated on test data.

---

## 📖 Full Documentation

For detailed information, see **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)**

Topics covered:
- Prerequisites and setup
- Step-by-step pipeline execution
- Configuration options
- Output artifacts structure
- Troubleshooting
- Advanced usage examples

---

## 🎯 Usage Options

### Option 1: Quick Start Script (Recommended)

```bash
# Default dataset (PobleSec)
./quickstart_local.sh

# Custom dataset
./quickstart_local.sh ElBorn
./quickstart_local.sh LesCorts
```

### Option 2: Direct Python Execution

```bash
# Default settings
python run_pipeline_locally.py

# Custom options
python run_pipeline_locally.py --dataset ElBorn --identifier my-test-001

# Help
python run_pipeline_locally.py --help
```

---

## 📦 Output Structure

All results saved to `local_artifacts/{identifier}/`:

```
local_artifacts/local-run-20241209-143022/
├── processed_data/
│   ├── training_data.parquet      # 80% of dataset for training
│   ├── inference_data.parquet     # 20% of dataset for testing
│   └── config.json                # Preprocessing configuration
├── models/
│   ├── GRU/model.pt               # Trained GRU model
│   ├── LSTM/model.pt              # Trained LSTM model
│   └── PROPHET/model.pkl          # Trained Prophet model
├── metrics/
│   ├── GRU_metrics.json           # GRU performance (MSE, RMSE, MAE)
│   ├── LSTM_metrics.json          # LSTM performance
│   └── PROPHET_metrics.json       # Prophet performance
├── evaluations/
│   └── evaluation_results.json    # Model comparison & best model
└── predictions/
    ├── inference_results.json     # Prediction summary
    └── predictions.csv            # Predicted vs actual values
```

---

## 🔍 View Results

### Best Model

```bash
# Quick view
cat local_artifacts/local-run-*/evaluations/evaluation_results.json | jq '.best_model'

# Full comparison
cat local_artifacts/local-run-*/evaluations/evaluation_results.json | jq .
```

### Predictions

```bash
# CSV format
head local_artifacts/local-run-*/predictions/predictions.csv

# JSON summary
cat local_artifacts/local-run-*/predictions/inference_results.json | jq .
```

### Model Metrics

```bash
# All models
jq -s '.' local_artifacts/local-run-*/metrics/*_metrics.json
```

---

## ⚙️ Requirements

- **Python:** 3.11+
- **Packages:** `pandas`, `numpy`, `torch`, `prophet`, `scikit-learn`
- **Storage:** ~50 MB per run
- **Runtime:** 2-5 minutes on standard laptop

**The quickstart script auto-installs missing packages.**

---

## 🆚 Comparison to Containerized Pipeline

| Feature              | Local Execution      | Containerized (KFP)  |
|----------------------|----------------------|----------------------|
| **Setup Time**       | < 1 minute           | ~10 minutes          |
| **Dependencies**     | pip install          | Docker images        |
| **Execution**        | Python script        | Kubeflow orchestration |
| **Storage**          | Local files          | MinIO/S3             |
| **Monitoring**       | Terminal output      | KFP UI               |
| **Parallelization**  | Sequential           | Native (k8s pods)    |
| **Best For**         | Development, testing | Production, scale    |

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** `ModuleNotFoundError: No module named 'torch'`  
**Fix:** `pip install torch pandas numpy prophet scikit-learn`

**Issue:** Dataset not found  
**Fix:** Check `ls dataset/*.csv` - ensure dataset exists

**Issue:** Python version too old  
**Fix:** Install Python 3.11+ from python.org

For more help, see **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md#troubleshooting)**

---

## 📚 Related Documentation

- **[kubeflow_pipeline/README.md](kubeflow_pipeline/README.md)** - KFP v2 pipeline definition (Steps 0-8)
- **[LOCAL_EXECUTION_GUIDE.md](LOCAL_EXECUTION_GUIDE.md)** - Complete local execution guide
- **[STEP_9_VERIFICATION.md](STEP_9_VERIFICATION.md)** - Kubeflow deployment (not covered here)

---

## 🎓 Example Session

```bash
$ cd ml_pipeline_v3
$ ./quickstart_local.sh

========================================================================
FLTS Pipeline - Local Quick Start
========================================================================

[1/5] Checking Python version...
✓ Found Python 3.11.5

[2/5] Checking virtual environment...
✓ Using virtual environment: ../.venv/bin/python

[3/5] Checking dependencies...
✓ Found: pandas
✓ Found: numpy
✓ Found: torch
✓ Found: sklearn

[4/5] Checking dataset...
✓ Dataset found: dataset/PobleSec.csv

[5/5] Running pipeline...
========================================================================

================================================================================
FLTS Pipeline - Local Execution
================================================================================

ℹ Dataset: PobleSec
ℹ Identifier: local-run-20241209-143022

[Step 1] Data Preprocessing
--------------------------------------------------------------------------------
✓ Training data saved to: .../processed_data/training_data.parquet
✓ Inference data saved to: .../processed_data/inference_data.parquet
✓ Preprocessing complete

[Step 2] Model Training
--------------------------------------------------------------------------------
Training GRU model...
Epoch [10/10], Loss: 0.028431
✓ GRU training complete

Training LSTM model...
✓ LSTM training complete

Training Prophet model...
✓ Prophet training complete

[Step 3] Model Evaluation & Selection
--------------------------------------------------------------------------------
Model      MSE          RMSE         MAE         
--------------------------------------------------
GRU        0.028431     0.168616     0.132487    
LSTM       0.029821     0.172688     0.138201    
PROPHET    0.035612     0.188711     0.145932    

✓ Best Model: GRU (score: 0.157492)

[Step 4] Inference
--------------------------------------------------------------------------------
Generated 38 predictions
✓ Results saved to: .../predictions/inference_results.json

================================================================================
Pipeline Execution Complete
================================================================================
✓ Total execution time: 127.43 seconds

========================================================================
Pipeline execution completed successfully!
========================================================================

Results saved to: local_artifacts/local-run-20241209-143022

Next steps:
  • View evaluation: cat local_artifacts/local-run-20241209-143022/evaluations/evaluation_results.json
  • View predictions: cat local_artifacts/local-run-20241209-143022/predictions/predictions.csv
  • See full guide: cat LOCAL_EXECUTION_GUIDE.md
```

---

## 🎯 Next Steps

1. **Analyze Results:** Inspect `local_artifacts/` to understand model performance
2. **Iterate:** Modify hyperparameters and re-run
3. **Compare:** Run on different datasets (PobleSec, ElBorn, LesCorts)
4. **Deploy:** When satisfied, proceed to KFP deployment (Step 9)

---

## ✅ Summary

**What you get:**
- ✅ Complete pipeline execution locally
- ✅ All models trained and compared
- ✅ Best model automatically selected
- ✅ Predictions generated on test data
- ✅ Full artifacts for analysis

**No need for:**
- ❌ Docker containers
- ❌ Kubernetes cluster
- ❌ Kafka message broker
- ❌ MinIO/S3 storage
- ❌ Kubeflow installation

**Perfect for:**
- 🧪 Local development and testing
- 🔬 Hyperparameter experimentation
- 📊 Model comparison studies
- 🎓 Learning and demonstrations

---

**Ready to run? Execute:** `./quickstart_local.sh`
