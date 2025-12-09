# FLTS Kubeflow Pipeline (KFP v2)

**Pure Python time-series forecasting pipeline using Kubeflow Pipelines SDK v2**

Complete runbook for local development, compilation, and testing. **Step 9 (deployment to Kubeflow cluster) is intentionally NOT covered here.**

---

## 📋 Table of Contents

- [What This Is](#what-this-is)
- [What This Is NOT](#what-this-is-not)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Pipeline Structure](#pipeline-structure)
- [Components](#components)
- [Pipeline Parameters](#pipeline-parameters)
- [Testing](#testing)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)
- [KFP v1 → v2 Migration](#kfp-v1--v2-migration)

---

## ✅ What This Is

A complete KFP v2 pipeline definition for time-series forecasting with:

- **Pure Python components** using `@dsl.component` decorator
- **No YAML dependencies** - all component definitions in Python code
- **Type-safe interfaces** using `dsl.Input`, `dsl.Output`, `dsl.Dataset`, `dsl.Model`
- **Local compilation** to KFP v2 IR JSON spec
- **Unit tests** to validate pipeline structure
- **Docker-based component execution** (images: `flts-preprocess:latest`, `train-container:latest`, etc.)

**Pipeline DAG:**

```
┌──────────────┐
│  Preprocess  │  Load CSV, transform, split
└──────┬───────┘
       │
       ├─────────────┬─────────────┐
       ▼             ▼             ▼
   ┌──────┐     ┌───────┐     ┌─────────┐
   │ GRU  │     │ LSTM  │     │ Prophet │  Train 3 models
   └──┬───┘     └───┬───┘     └────┬────┘  (parallel)
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

---

## ❌ What This Is NOT

This README does **NOT** cover:

- ❌ **Step 9**: Uploading pipeline to Kubeflow Pipelines UI
- ❌ **Step 9**: Submitting runs to KFP cluster
- ❌ **Step 9**: Kubernetes deployment
- ❌ **Step 9**: `kfp.Client()` usage for pipeline submission
- ❌ **Step 9**: Port-forwarding to KFP API server

**Why?** This work stops at Step 8 (pipeline definition and compilation). Step 9 (deployment and execution) is a separate concern requiring cluster access.

---

## ⚙️ Prerequisites

### 1. Python Environment

Requires Python 3.11+ with KFP v2 SDK:

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install KFP v2
pip install "kfp>=2.0.0,<3.0.0"
```

**Verify installation:**
```bash
python -c "import kfp; print('KFP version:', kfp.__version__)"
# Expected: KFP version: 2.15.2 (or similar 2.x)
```

### 2. Docker Images

All component images must be built (for eventual execution, not for compilation):

```bash
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Build all images
docker-compose -f docker-compose.yaml build

# Or build individually
docker build -t flts-preprocess:latest components/preprocess/
docker build -t train-container:latest components/train_gru/
docker build -t eval-container:latest components/eval/
docker build -t inference-container:latest components/inference/
```

**Note:** Compilation does NOT require running containers - it only needs image names to be specified in component definitions.

### 3. Directory Structure

Ensure this structure exists:

```
kubeflow_pipeline/
├── README.md (this file)
├── components_v2.py          # Component definitions
├── pipeline_v2.py            # Pipeline DAG
├── compile_pipeline_v2.py    # Compilation script
├── CHANGES_KFP_VERSION.md    # Migration notes
├── tests/
│   ├── test_kfp_v2_pipeline.py  # Unit tests
│   └── run_all_tests.sh         # Test harness
├── _deprecated/              # Old KFP v1 artifacts
│   ├── README.md
│   ├── compile_kfp_v1.py
│   └── compile_pipeline_v1.py
└── artifacts/
    └── flts_pipeline_v2.json  # Compiled output (generated)
```

---

## 🚀 Quick Start

### Step 1: Verify Environment

```bash
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3

# Activate virtual environment (if using)
source /Users/arnavde/Python/AI/.venv/bin/activate

# Check KFP version
python -c "import kfp; print('KFP version:', kfp.__version__)"
# Expected: 2.15.2
```

### Step 2: Compile Pipeline

```bash
python kubeflow_pipeline/compile_pipeline_v2.py
```

**Expected output:**
```
======================================================================
KFP v2 Pipeline Compilation
======================================================================

Pipeline: flts_pipeline
Output:   artifacts/flts_pipeline_v2.json

✓ Compilation successful

Compiled pipeline spec:
  Path: artifacts/flts_pipeline_v2.json
  Size: 40,500 bytes
```

**Artifacts created:**
- `artifacts/flts_pipeline_v2.json` - KFP v2 IR spec (40,500 bytes)

### Step 3: Run Tests

```bash
bash kubeflow_pipeline/tests/run_all_tests.sh
```

**Expected output:**
```
=======================================================================
✓ All Step 8 Tests PASSED
=======================================================================

Step 8 (Pipeline Definition) is COMPLETE.
Step 9 (Deployment) has NOT been started.
```

---

## 🏗️ Pipeline Structure

### Component Files

**`components_v2.py`** (225 lines):
- Single source of truth for all 6 components
- Uses `@dsl.component(base_image="...")` decorator
- Type-safe I/O: `dsl.Output[dsl.Dataset]`, `dsl.Input[dsl.Model]`, etc.

**Example component:**
```python
@dsl.component(base_image="flts-preprocess:latest")
def preprocess_component(
    # Outputs first (Python syntax requirement)
    training_data: dsl.Output[dsl.Dataset],
    inference_data: dsl.Output[dsl.Dataset],
    config_hash: dsl.OutputPath(str),
    config_json: dsl.OutputPath(str),
    
    # Required inputs with None defaults (allows KFP to inject)
    dataset_name: str = None,
    identifier: str = None,
    
    # Optional parameters with defaults
    sample_train_rows: int = 0,
    sample_test_rows: int = 0,
    # ... more params
):
    """Preprocesses raw CSV data for training/inference."""
    pass  # Container handles actual execution
```

**`pipeline_v2.py`** (169 lines):
- Defines the DAG using `@dsl.pipeline` decorator
- Wires components together using `.outputs`
- Exposes 12 key parameters for runtime configuration

**Example pipeline:**
```python
@dsl.pipeline(
    name="flts-time-series-pipeline",
    description="End-to-end time-series forecasting with KFP v2"
)
def flts_pipeline(
    dataset_name: str = "PobleSec",
    identifier: str = "flts-run-001",
    # ... 10 more params
):
    # Step 1: Preprocess
    preprocess_task = preprocess_component(
        dataset_name=dataset_name,
        identifier=identifier,
        # ... all params
    )
    
    # Step 2: Train models (parallel)
    gru_task = train_gru_component(
        training_data=preprocess_task.outputs['training_data'],
        # ...
    )
    lstm_task = train_lstm_component(...)
    prophet_task = train_prophet_component(...)
    
    # Step 3: Evaluate
    eval_task = eval_component(
        gru_model=gru_task.outputs['model'],
        lstm_model=lstm_task.outputs['model'],
        prophet_model=prophet_task.outputs['model'],
        # ...
    )
    
    # Step 4: Inference
    inference_task = inference_component(
        inference_data=preprocess_task.outputs['inference_data'],
        # ...
    )
```

**`compile_pipeline_v2.py`** (103 lines):
- Dedicated compilation script with CLI interface
- Uses `kfp.compiler.Compiler().compile()`
- Outputs JSON IR spec to `artifacts/flts_pipeline_v2.json`

---

## 🧩 Components

### 1. Preprocess Component

- **Image**: `flts-preprocess:latest`
- **Purpose**: Load CSV, apply transformations, split train/test
- **Inputs**: None (reads from MinIO via env vars)
- **Outputs**:
  - `training_data` (Dataset) - Processed training data
  - `inference_data` (Dataset) - Test data for inference
  - `config_hash` (String) - Config hash for reproducibility
  - `config_json` (String) - Full config JSON

**Key Parameters:**
- `dataset_name` (str): CSV filename (e.g., "PobleSec")
- `sample_train_rows` (int): Row limit (0=all)
- `sample_strategy` (str): "head", "tail", or "random"
- `handle_nans` (bool): Enable NaN imputation
- `scaler` (str): "MinMaxScaler", "StandardScaler", "RobustScaler"

### 2. Train GRU Component

- **Image**: `train-container:latest`
- **Purpose**: Train Gated Recurrent Unit model
- **Inputs**: `training_data` (Dataset)
- **Outputs**:
  - `model` (Model) - Trained GRU model
  - `metrics` (Artifact) - Training metrics
  - `run_id` (String) - MLflow run ID

**Key Parameters:**
- `hidden_size` (int): Hidden layer size
- `num_layers` (int): RNN depth
- `learning_rate` (float): Adam LR
- `num_epochs` (int): Max training epochs

### 3. Train LSTM Component

- **Image**: `train-container:latest`
- **Purpose**: Train Long Short-Term Memory model
- **Inputs/Outputs**: Same as GRU
- **Difference**: Uses LSTM architecture (via `MODEL_TYPE=lstm` env var)

### 4. Train Prophet Component

- **Image**: `nonml-container:latest`
- **Purpose**: Train Facebook Prophet statistical model
- **Inputs**: `training_data` (Dataset)
- **Outputs**: Same as GRU/LSTM
- **Key Parameters**:
  - `seasonality_mode` (str): "additive" or "multiplicative"
  - `yearly_seasonality` (bool): Enable yearly patterns

### 5. Evaluation Component

- **Image**: `eval-container:latest`
- **Purpose**: Compare all models, select best performer
- **Inputs**:
  - `gru_model`, `lstm_model`, `prophet_model` (Models)
  - `gru_metrics`, `lstm_metrics`, `prophet_metrics` (Artifacts)
- **Outputs**:
  - `promotion_pointer` (Artifact) - Best model pointer
  - `eval_metadata` (Artifact) - Evaluation results

**Selection Criteria:**
- Weighted composite score: `0.5*RMSE + 0.3*MAE + 0.2*MSE`
- Lowest score wins

### 6. Inference Component

- **Image**: `inference-container:latest`
- **Purpose**: Generate predictions using promoted model
- **Inputs**:
  - `inference_data` (Dataset) - Test data
  - Promoted model (selected by eval)
- **Outputs**:
  - `inference_results` (Artifact) - JSONL predictions
  - `inference_metadata` (Artifact) - Inference stats

**Key Parameters:**
- `inference_length` (int): Forecast horizon
- `sample_idx` (int): Which test sample to use

---

## 📊 Pipeline Parameters

The pipeline exposes 12 parameters for runtime configuration:

```python
flts_pipeline(
    # Data parameters
    dataset_name: str = "PobleSec",       # CSV filename
    identifier: str = "flts-run-001",     # Run ID for tracking
    
    # Training parameters
    hidden_size: int = 64,                # RNN hidden size
    num_layers: int = 2,                  # RNN depth
    dropout: float = 0.2,                 # Dropout rate
    learning_rate: float = 0.001,         # Adam LR
    batch_size: int = 32,                 # Batch size
    num_epochs: int = 50,                 # Max epochs
    
    # Sampling parameters
    sample_train_rows: int = 0,           # Train subset (0=all)
    sample_test_rows: int = 0,            # Test subset (0=all)
    
    # Inference parameters
    inference_length: int = 1,            # Forecast steps
    sample_idx: int = 0,                  # Test sample index
)
```

**To customize:** Modify parameters when creating pipeline run (Step 9, not covered here).

---

## 🧪 Testing

### Test Suite Structure

**`test_kfp_v2_pipeline.py`** (132 lines):
- 3 unit tests for Step 8 validation
- Tests run automatically via test harness

**Tests:**
1. **Component Validation**: Verify all 6 components have `component_spec`
2. **Pipeline Decoration**: Verify pipeline has `pipeline_spec`
3. **Compilation Test**: Compile to tempfile, validate JSON structure

**`run_all_tests.sh`** (64 lines):
- Bash harness for complete validation
- Runs: version check, compilation, artifact verification, unit tests, v1 reference check

### Running Tests

**Full test suite:**
```bash
bash kubeflow_pipeline/tests/run_all_tests.sh
```

**Individual tests:**
```bash
# Just unit tests
python kubeflow_pipeline/tests/test_kfp_v2_pipeline.py

# Just compilation
python kubeflow_pipeline/compile_pipeline_v2.py

# Just version check
python -c "import kfp; print(kfp.__version__)"
```

**Expected results:**
- All tests pass ✅
- `artifacts/flts_pipeline_v2.json` created (40,500 bytes)
- No KFP v1 references found

---

## 🛠️ Development Workflow

### Modifying Components

After changing component logic (e.g., adding parameter):

1. **Update `components_v2.py`**:
   ```python
   @dsl.component(base_image="flts-preprocess:latest")
   def preprocess_component(
       # ... existing params
       new_param: str = "default_value",  # Add new param
   ):
       pass
   ```

2. **Update `pipeline_v2.py`** to pass the parameter:
   ```python
   preprocess_task = preprocess_component(
       # ... existing args
       new_param=new_param,  # Wire from pipeline params
   )
   ```

3. **Recompile:**
   ```bash
   python kubeflow_pipeline/compile_pipeline_v2.py
   ```

4. **Test:**
   ```bash
   bash kubeflow_pipeline/tests/run_all_tests.sh
   ```

### Adding New Component

1. **Add to `components_v2.py`:**
   ```python
   @dsl.component(base_image="my-new-component:latest")
   def my_new_component(
       output_data: dsl.Output[dsl.Artifact],
       input_data: dsl.Input[dsl.Dataset] = None,
   ):
       pass
   ```

2. **Wire into `pipeline_v2.py`:**
   ```python
   my_task = my_new_component(
       input_data=preprocess_task.outputs['training_data']
   )
   ```

3. **Recompile and test** as above

### Parameter Ordering (CRITICAL)

Python requires outputs (no defaults) before optional params (with defaults):

**✅ Correct:**
```python
def my_component(
    output1: dsl.Output[dsl.Dataset],      # Output first
    input_required: dsl.Input[dsl.Dataset] = None,  # Required input with None
    param_optional: int = 42,              # Optional param with default
):
```

**❌ Incorrect:**
```python
def my_component(
    param_optional: int = 42,              # Optional param BEFORE output
    output1: dsl.Output[dsl.Dataset],      # Causes SyntaxError!
):
```

---

## 🔍 Troubleshooting

### Compilation Errors

**Issue**: `ModuleNotFoundError: No module named 'kfp'`
```bash
# Solution: Install KFP v2
pip install "kfp>=2.0.0,<3.0.0"
```

**Issue**: `ModuleNotFoundError: No module named 'kubeflow_pipeline'`
```bash
# Solution: Run from correct directory
cd /Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3
python kubeflow_pipeline/compile_pipeline_v2.py
```

**Issue**: `SyntaxError: non-default argument follows default argument`
```python
# Solution: Reorder parameters - outputs first, then inputs with None, then optionals
# See "Parameter Ordering" section above
```

### Test Failures

**Issue**: Component validation fails with "missing component_spec"
```bash
# Solution: Ensure @dsl.component decorator is present
# Check components_v2.py has @dsl.component(base_image="...") above each function
```

**Issue**: Pipeline compilation produces 0-byte file
```bash
# Solution: Check for Python errors during compilation
python kubeflow_pipeline/compile_pipeline_v2.py 2>&1 | tee compile_log.txt
```

### Version Conflicts

**Issue**: `ImportError: cannot import name 'ContainerOp' from 'kfp.dsl'`
```bash
# Solution: You have KFP v1 installed, need v2
pip uninstall kfp kfp-pipeline-spec kfp-server-api
pip install "kfp>=2.0.0,<3.0.0"
```

**Issue**: Pydantic version warning
```bash
# Warning: "mlflow 2.x requires pydantic>=2.0, but you have 1.10.24"
# Solution: Non-critical, compilation still works
# To fix (optional): pip install --upgrade pydantic
```

---

## 🔄 KFP v1 → v2 Migration

This project migrated from KFP v1.8.22 to v2.15.2. Key changes documented in `CHANGES_KFP_VERSION.md`.

### What Changed

**Before (v1):**
- Used `kfp.dsl.ContainerOp` for components
- Loaded components from YAML files
- Compiled to Argo Workflow YAML (9,695 bytes)
- Files: `compile_kfp_v1.py`, `compile_pipeline_v1.py`

**After (v2):**
- Uses `@dsl.component` decorator for pure Python components
- No YAML files - all definitions in Python
- Compiles to KFP v2 IR JSON (40,500 bytes)
- Files: `components_v2.py`, `pipeline_v2.py`, `compile_pipeline_v2.py`

### Breaking Changes

- ❌ `kfp.dsl.ContainerOp` removed
- ❌ `kfp.components.load_component_from_file()` removed
- ✅ `@dsl.component` decorator required
- ✅ Type annotations mandatory: `dsl.Input`, `dsl.Output`, `dsl.Dataset`, etc.
- ✅ JSON IR spec instead of YAML

### V1 Artifacts

Old v1 code moved to `_deprecated/`:
- `compile_kfp_v1.py` - v1 compilation attempt
- `compile_pipeline_v1.py` - v1 ContainerOp approach
- `README_v1.md` - Old README

**Do NOT use v1 code** - retained only for historical reference.

---

## 📚 Additional Resources

**Official Documentation:**
- [KFP v2 SDK Documentation](https://kubeflow-pipelines.readthedocs.io/en/latest/)
- [Kubeflow Pipelines Overview](https://www.kubeflow.org/docs/components/pipelines/)
- [KFP v2 Migration Guide](https://www.kubeflow.org/docs/components/pipelines/v2/migration/)

**Component Images:**
- Built from: `components/preprocess/`, `components/train_gru/`, etc.
- Dockerfile locations: See component directories
- MinIO integration: All components use S3-compatible storage

**Related Files:**
- `CHANGES_KFP_VERSION.md` - Detailed migration notes
- `_deprecated/README.md` - V1 deprecation notice
- `docker-compose.yaml` - Local infrastructure (MinIO, MLflow, etc.)

---

## 📝 Summary

**This runbook covers:**
- ✅ Step 0: Environment setup (KFP v2.15.2)
- ✅ Step 1: V1 artifact cleanup
- ✅ Step 2: Pure Python component definitions
- ✅ Step 3: Pipeline DAG implementation
- ✅ Step 4: Compilation to JSON IR
- ✅ Step 5: Testing and validation
- ✅ Step 8: Complete pipeline definition

**What's NOT covered (Step 9):**
- ❌ Uploading to Kubeflow cluster
- ❌ Creating pipeline runs
- ❌ Kubernetes deployment
- ❌ `kfp.Client()` usage

**Key Artifacts:**
- `artifacts/flts_pipeline_v2.json` (40,500 bytes) - Ready for Step 9 deployment
- `components_v2.py` (225 lines) - All component definitions
- `pipeline_v2.py` (169 lines) - Pipeline DAG
- `compile_pipeline_v2.py` (103 lines) - Compilation script

---

**Questions?** Check `CHANGES_KFP_VERSION.md` for migration details or inspect test output from `run_all_tests.sh`.

**Next Steps (Step 9 - Not Covered Here):**
1. Upload `artifacts/flts_pipeline_v2.json` to KFP UI
2. Create pipeline run with desired parameters
3. Monitor execution and collect results

**End of Step 8. Step 9 intentionally NOT started.**
