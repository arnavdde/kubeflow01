# Kubeflow Pipelines v2 Migration Plan

**Date:** November 24, 2025  
**Purpose:** Detailed design for replacing Kafka with KFP v2 Input[]/Output[] artifacts

---

## Executive Summary

This plan transforms the Kafka-based FLTS pipeline into a Kubeflow Pipelines (KFP v2) DAG where:
- **Kafka topics** → **KFP artifacts** (Dataset, Model, Artifact types)
- **Message passing** → **Component dependencies** (DAG edges)
- **Consumer loops** → **Component inputs** (declarative)
- **Producer calls** → **Component outputs** (artifact writes)

**Core Principle:** Zero changes to ML logic, preprocessing algorithms, MinIO storage, MLflow tracking, or FastAPI gateway. Only the inter-component wiring changes.

---

## Kafka Topic → KFP Artifact Mapping

### 1. training-data → Training Dataset Artifact

**Kafka (Current):**
```python
# preprocess_container publishes:
produce_message(producer, "training-data", {
    "bucket": "processed-data",
    "object": "processed_data.parquet",
    "size": 123456,
    "v": 1,
    "identifier": "run-xyz"
})

# train containers consume:
consumer = create_consumer("training-data", "train-gru")
```

**KFP v2 (Target):**
```python
# Preprocess component output:
@component
def preprocess_component(...) -> NamedTuple('Outputs', [
    ('training_data', Dataset),
    ('inference_data', Dataset),
    ('config_hash', str),
    ('config_json', str)
]):
    # ... existing preprocessing logic ...
    
    # Write parquet to artifact path (MinIO-backed)
    training_data.path = f"minio://processed-data/processed_data.parquet"
    training_data.metadata = {
        "config_hash": config_hash,
        "config_json": canonical_json,
        "row_count": len(train_df),
        "identifier": identifier
    }
    return (training_data, inference_data, config_hash, config_json)

# Train component input:
@component
def train_gru_component(
    training_data: Input[Dataset],
    config_hash: str,
    ...
) -> NamedTuple('Outputs', [('model', Model), ('metrics', Artifact)]):
    # Read from artifact path (still uses gateway/MinIO)
    object_key = training_data.uri.replace("minio://processed-data/", "")
    df = read_parquet_from_gateway(object_key)
    # ... existing training logic ...
```

**Key Changes:**
- ❌ Remove: `produce_message()`, `create_consumer()`, Kafka bootstrap
- ✅ Add: `Output[Dataset]` in preprocess, `Input[Dataset]` in trainers
- ✅ Preserve: MinIO storage, config_hash in metadata, Parquet format

---

### 2. model-training → Model Artifacts + Metadata

**Kafka (Current):**
```python
# Trainers publish SUCCESS event:
success_payload = {
    "model_type": "GRU",
    "config_hash": "abc123",
    "run_id": "mlflow-run-123",
    "status": "SUCCESS",
    "test_rmse": 0.123,
    "test_mae": 0.045,
    "test_mse": 0.015,
    "train_start": "2025-11-24T12:00:00Z",
    "train_end": "2025-11-24T12:05:00Z",
    "identifier": "run-xyz",
    "artifact_uri": "s3://mlflow/..."
}
produce_message(producer, "model-training", success_payload, key="trained-GRU")

# Eval consumes and tracks completion
consumer = create_consumer("model-training", "eval-promoter")
_completion_tracker[config_hash].add(model_type)
```

**KFP v2 (Target):**
```python
# Train component outputs:
@component
def train_gru_component(...) -> NamedTuple('Outputs', [
    ('model', Model),
    ('metrics', Artifact)
]):
    # ... training + MLflow logging ...
    
    # Write model artifact metadata (still in MLflow)
    model.uri = f"runs:/{run_id}/GRU"
    model.metadata = {
        "model_type": "GRU",
        "run_id": run_id,
        "config_hash": config_hash,
        "test_rmse": test_rmse,
        "test_mae": test_mae,
        "test_mse": test_mse,
        "train_start": start_time,
        "train_end": end_time,
        "identifier": identifier,
        "mlflow_uri": mlflow.get_artifact_uri()
    }
    
    # Metrics artifact (for eval scoring)
    metrics.metadata = {
        "test_rmse": test_rmse,
        "test_mae": test_mae,
        "test_mse": test_mse,
        "composite_score": 0.5*rmse + 0.3*mae + 0.2*mse
    }
    
    return (model, metrics)

# Eval component receives all models as inputs (DAG enforces completion):
@component
def eval_component(
    gru_model: Input[Model],
    gru_metrics: Input[Artifact],
    lstm_model: Input[Model],
    lstm_metrics: Input[Artifact],
    prophet_model: Input[Model],
    prophet_metrics: Input[Artifact],
    config_hash: str
) -> NamedTuple('Outputs', [('selected_model', Model), ('promotion_event', Artifact)]):
    # All inputs present = all models completed (DAG guarantee)
    # ... existing promotion logic ...
```

**Key Changes:**
- ❌ Remove: RUNNING/SUCCESS state machine, `_completion_tracker`, Kafka events
- ✅ Add: `Output[Model]` + `Output[Artifact]` per trainer
- ✅ Simplify: DAG dependencies replace event-driven coordination
- ✅ Preserve: MLflow storage, run_id tracking, metrics calculation

**Rationale:** KFP DAG semantics naturally enforce "wait for all trainers before eval" without explicit state tracking.

---

### 3. model-selected → Promoted Model Artifact

**Kafka (Current):**
```python
# Eval publishes promotion:
promotion_event = {
    "model_uri": "runs:/xyz/GRU",
    "model_type": "GRU",
    "run_id": "xyz",
    "config_hash": "abc123",
    "composite_score": 0.089,
    "test_rmse": 0.123,
    "promotion_time": "2025-11-24T12:10:00Z",
    "identifier": "run-xyz"
}
produce_message(producer, "model-selected", promotion_event, key="promotion")

# Inference consumes promotion pointer
consumer.subscribe(["model-selected"])
# ... load model from MLflow ...
```

**KFP v2 (Target):**
```python
# Eval component output:
@component
def eval_component(...) -> NamedTuple('Outputs', [
    ('selected_model', Model),
    ('promotion_metadata', Artifact)
]):
    # ... scoring logic ...
    
    # Selected model artifact (points to winner)
    selected_model.uri = best_model_uri  # e.g., "runs:/xyz/GRU"
    selected_model.metadata = {
        "model_type": best_model_type,
        "run_id": best_run_id,
        "config_hash": config_hash,
        "composite_score": best_score,
        "test_rmse": best_rmse,
        "test_mae": best_mae,
        "test_mse": best_mse,
        "promotion_time": timestamp,
        "identifier": identifier
    }
    
    # Write promotion history to MinIO (preserve current.json structure)
    promotion_metadata.path = f"minio://model-promotion/{identifier}/{config_hash}/current.json"
    promotion_metadata.metadata = selected_model.metadata
    _write_promotion_to_minio(selected_model.metadata)
    
    return (selected_model, promotion_metadata)

# Inference component receives promoted model:
@component
def inference_component(
    inference_data: Input[Dataset],
    selected_model: Input[Model],
    config_metadata: Input[Artifact]
) -> Output[Artifact]:
    # Load model from selected_model.uri
    model_uri = selected_model.uri
    run_id = selected_model.metadata["run_id"]
    # ... existing inference logic ...
```

**Key Changes:**
- ❌ Remove: Kafka promotion topic, consumer subscription
- ✅ Add: `Output[Model]` from eval, `Input[Model]` in inference
- ✅ Preserve: MinIO promotion history, current.json structure, MLflow URIs

---

### 4. inference-data → Inference Dataset Artifact

**Kafka (Current):**
```python
# Preprocess publishes test data claim check:
produce_message(producer, "inference-data", {
    "bucket": "processed-data",
    "object": "test_processed_data.parquet",
    "size": 123456,
    "v": 1,
    "identifier": "run-xyz"
})

# Inference consumes:
consumer.subscribe(["inference-data"])
```

**KFP v2 (Target):**
```python
# Preprocess component output (already defined above):
def preprocess_component(...) -> NamedTuple('Outputs', [
    ('training_data', Dataset),
    ('inference_data', Dataset),  # ← Test dataset
    ...
]):
    inference_data.path = f"minio://processed-data/test_processed_data.parquet"
    inference_data.metadata = {
        "config_hash": config_hash,
        "row_count": len(test_df),
        "identifier": identifier
    }
    return (...)

# Inference component input (already defined above):
def inference_component(
    inference_data: Input[Dataset],  # ← Directly wired
    selected_model: Input[Model],
    ...
):
    # ... existing inference logic ...
```

**Key Changes:**
- ❌ Remove: Separate Kafka topic for inference data
- ✅ Add: Second output from preprocess, direct DAG edge to inference
- ✅ Preserve: Test data Parquet format, MinIO storage

---

### 5. performance-eval → Optional Metrics Artifact (Low Priority)

**Kafka (Current):**
```python
# Inference publishes metrics:
produce_message(producer, "performance-eval", metrics_payload)
```

**KFP v2 (Target):**
```python
# Inference component output:
@component
def inference_component(...) -> NamedTuple('Outputs', [
    ('predictions', Artifact),
    ('metrics', Artifact)  # ← Optional monitoring artifact
]):
    # ... inference ...
    
    metrics.metadata = {
        "mae": mae,
        "rmse": rmse,
        "inference_count": count,
        "timestamp": timestamp
    }
    # Write metrics to artifact (can be scraped by monitoring)
    return (predictions, metrics)
```

**Key Changes:**
- ❌ Remove: Kafka performance-eval topic
- ✅ Add: Optional metrics output artifact
- ✅ Alternative: Log metrics to MLflow instead

---

## KFP v2 DAG Structure

### Component Definitions

#### 1. Preprocess Component

**Container:** `preprocess_container/`  
**Image:** `flts-preprocess:kfp` (add USE_KFP=1 flag)

```python
@component(
    base_image="flts-preprocess:kfp",
    packages_to_install=[]  # All deps in base image
)
def preprocess_component(
    dataset_name: str,
    identifier: str,
    sample_train_rows: int = 0,
    sample_test_rows: int = 0,
    force_reprocess: int = 0,
    extra_hash_salt: str = "",
    # Config parameters
    handle_nans: bool = True,
    nans_threshold: float = 0.33,
    clip_enable: bool = False,
    time_features_enable: bool = True,
    # MinIO/Gateway config
    gateway_url: str = "http://fastapi-app:8000",
    input_bucket: str = "dataset",
    output_bucket: str = "processed-data"
) -> NamedTuple('Outputs', [
    ('training_data', Dataset),
    ('inference_data', Dataset),
    ('config_hash', str),
    ('config_json', str)
]):
    """Preprocess raw time-series data into train/test datasets.
    
    Replaces Kafka producers with artifact outputs.
    Preserves all ML logic, config hashing, MinIO claim-check pattern.
    """
    import os
    os.environ['USE_KFP'] = '1'  # Flag to disable Kafka
    os.environ['GATEWAY_URL'] = gateway_url
    os.environ['DATASET_NAME'] = dataset_name
    os.environ['IDENTIFIER'] = identifier
    # ... set all other env vars ...
    
    from preprocess_container.main import run_preprocess_kfp
    return run_preprocess_kfp()  # Modified entry point
```

**Outputs:**
- `training_data: Dataset` → MinIO path for processed_data.parquet
- `inference_data: Dataset` → MinIO path for test_processed_data.parquet
- `config_hash: str` → SHA256 hash for lineage tracking
- `config_json: str` → Canonical config JSON for metadata

**Container Modifications:**
- Add `run_preprocess_kfp()` function that returns artifacts instead of Kafka publish
- Keep all existing preprocessing logic unchanged
- Gate Kafka code with `if os.environ.get('USE_KFP') != '1':`

---

#### 2. Train Components (GRU, LSTM, Prophet)

**Containers:** `train_container/`, `nonML_container/`  
**Images:** `flts-train-gru:kfp`, `flts-train-lstm:kfp`, `flts-train-prophet:kfp`

```python
@component(
    base_image="flts-train-gru:kfp",
    packages_to_install=[]
)
def train_gru_component(
    training_data: Input[Dataset],
    config_hash: str,
    config_json: str,
    identifier: str,
    # Training hyperparameters
    hidden_size: int = 128,
    num_layers: int = 2,
    batch_size: int = 64,
    epochs: int = 10,
    learning_rate: float = 1e-4,
    input_seq_len: int = 10,
    output_seq_len: int = 1,
    # MLflow/MinIO config
    mlflow_tracking_uri: str = "http://mlflow:5000",
    gateway_url: str = "http://fastapi-app:8000"
) -> NamedTuple('Outputs', [
    ('model', Model),
    ('metrics', Artifact),
    ('run_id', str)
]):
    """Train GRU model on preprocessed data.
    
    Replaces Kafka consumer/producer with artifact I/O.
    Preserves MLflow logging, model architecture, training loop.
    """
    import os
    os.environ['USE_KFP'] = '1'
    os.environ['MODEL_TYPE'] = 'GRU'
    os.environ['CONFIG_HASH'] = config_hash
    # ... set hyperparameters as env vars ...
    
    # Read training data from artifact path
    bucket, object_key = _parse_minio_uri(training_data.uri)
    df = _download_from_gateway(gateway_url, bucket, object_key)
    
    # Run existing training logic
    from train_container.main import train_model_kfp
    run_id, test_metrics = train_model_kfp(df, config_hash, identifier)
    
    # Return artifacts
    model.uri = f"runs:/{run_id}/GRU"
    model.metadata = {
        "model_type": "GRU",
        "run_id": run_id,
        "config_hash": config_hash,
        "test_rmse": test_metrics["rmse"],
        "test_mae": test_metrics["mae"],
        "test_mse": test_metrics["mse"],
        "identifier": identifier
    }
    
    metrics.metadata = test_metrics
    
    return (model, metrics, run_id)
```

**Duplicate for LSTM and Prophet with respective MODEL_TYPE and hyperparameters.**

**Outputs (per trainer):**
- `model: Model` → MLflow run URI
- `metrics: Artifact` → Test metrics for eval scoring
- `run_id: str` → MLflow run ID for lineage

**Container Modifications:**
- Add `train_model_kfp(df, config_hash, identifier)` that returns (run_id, metrics)
- Remove Kafka consumer loop, message queue, threading
- Keep MLflow logging, model training, scaler saving unchanged
- Gate Kafka code with `if os.environ.get('USE_KFP') != '1':`

---

#### 3. Eval Component

**Container:** `eval_container/`  
**Image:** `flts-eval:kfp`

```python
@component(
    base_image="flts-eval:kfp",
    packages_to_install=[]
)
def eval_component(
    # Inputs from all trainers
    gru_model: Input[Model],
    gru_metrics: Input[Artifact],
    lstm_model: Input[Model],
    lstm_metrics: Input[Artifact],
    prophet_model: Input[Model],
    prophet_metrics: Input[Artifact],
    # Config
    config_hash: str,
    identifier: str,
    # MLflow/MinIO config
    mlflow_tracking_uri: str = "http://mlflow:5000",
    gateway_url: str = "http://fastapi-app:8000",
    promotion_bucket: str = "model-promotion"
) -> NamedTuple('Outputs', [
    ('selected_model', Model),
    ('promotion_metadata', Artifact)
]):
    """Evaluate all trained models and promote the best one.
    
    Replaces Kafka consumer (model-training topic) with direct inputs.
    Replaces Kafka producer (model-selected topic) with artifact output.
    Preserves scoring logic, promotion history, current.json structure.
    """
    import os
    os.environ['USE_KFP'] = '1'
    os.environ['CONFIG_HASH'] = config_hash
    
    # Collect all model metadata (DAG guarantees all inputs present)
    models = [
        (gru_model, gru_metrics),
        (lstm_model, lstm_metrics),
        (prophet_model, prophet_metrics)
    ]
    
    # Run existing scoring logic
    from eval_container.main import score_and_select_kfp
    best_model, best_metadata = score_and_select_kfp(models, config_hash)
    
    # Write promotion history to MinIO (preserve current.json)
    _write_promotion_to_minio(
        gateway_url, 
        promotion_bucket, 
        identifier, 
        config_hash, 
        best_metadata
    )
    
    # Return promoted model artifact
    selected_model.uri = best_model.uri
    selected_model.metadata = best_metadata
    
    promotion_metadata.path = f"minio://{promotion_bucket}/{identifier}/{config_hash}/current.json"
    promotion_metadata.metadata = best_metadata
    
    return (selected_model, promotion_metadata)
```

**Outputs:**
- `selected_model: Model` → Best model URI + metadata
- `promotion_metadata: Artifact` → Promotion history pointer

**Container Modifications:**
- Add `score_and_select_kfp(models, config_hash)` that takes list of models
- Remove Kafka consumer, `_completion_tracker`, event loop
- Keep scoring formula, promotion history writes unchanged
- Gate Kafka code with `if os.environ.get('USE_KFP') != '1':`

**Key Simplification:** No need for state tracking—KFP DAG ensures all trainers complete before eval runs.

---

#### 4. Inference Component

**Container:** `inference_container/`  
**Image:** `flts-inference:kfp`

```python
@component(
    base_image="flts-inference:kfp",
    packages_to_install=[]
)
def inference_component(
    inference_data: Input[Dataset],
    selected_model: Input[Model],
    config_hash: str,
    identifier: str,
    # Inference config
    inference_length: int = 10,
    sample_idx: int = 0,
    # MLflow/MinIO config
    mlflow_tracking_uri: str = "http://mlflow:5000",
    gateway_url: str = "http://fastapi-app:8000",
    inference_log_bucket: str = "inference-logs"
) -> NamedTuple('Outputs', [
    ('predictions', Artifact),
    ('metrics', Artifact)
]):
    """Run batch inference on test data using promoted model.
    
    Replaces Kafka consumers (inference-data, model-selected) with inputs.
    Preserves windowed inference, JSONL logging, scaler handling.
    """
    import os
    os.environ['USE_KFP'] = '1'
    os.environ['CONFIG_HASH'] = config_hash
    
    # Load inference data from artifact
    bucket, object_key = _parse_minio_uri(inference_data.uri)
    test_df = _download_from_gateway(gateway_url, bucket, object_key)
    
    # Load promoted model from MLflow
    model_uri = selected_model.uri
    run_id = selected_model.metadata["run_id"]
    
    from inference_container.inferencer import Inferencer
    inferencer = Inferencer()
    inferencer.load_model_from_uri(model_uri, run_id)
    
    # Run inference (existing logic)
    results = inferencer.run_batch_inference(
        test_df, 
        inference_length, 
        sample_idx
    )
    
    # Write JSONL to MinIO
    log_path = f"{inference_log_bucket}/{identifier}/{timestamp}/results.jsonl"
    _upload_jsonl_to_minio(gateway_url, log_path, results)
    
    # Return artifacts
    predictions.path = f"minio://{log_path}"
    predictions.metadata = {
        "num_predictions": len(results),
        "mae": results["mae"],
        "rmse": results["rmse"],
        "config_hash": config_hash
    }
    
    metrics.metadata = {
        "mae": results["mae"],
        "rmse": results["rmse"],
        "mse": results["mse"]
    }
    
    return (predictions, metrics)
```

**Outputs:**
- `predictions: Artifact` → JSONL results in MinIO
- `metrics: Artifact` → Inference metrics

**Container Modifications:**
- Add `run_batch_inference_kfp(test_df, model_uri, ...)` entry point
- Remove Kafka multi-topic consumer, promotion subscription, queue
- Keep Inferencer class, model loading, windowed inference unchanged
- Gate Kafka code with `if os.environ.get('USE_KFP') != '1':`

**Note:** FastAPI `/predict` endpoint remains unchanged for live serving (not part of batch pipeline).

---

## Pipeline DAG Definition

**File:** `kubeflow_pipeline/pipeline.py`

```python
from kfp import dsl
from kfp.dsl import pipeline

from components.preprocess.component import preprocess_component
from components.train_gru.component import train_gru_component
from components.train_lstm.component import train_lstm_component
from components.train_prophet.component import train_prophet_component
from components.eval.component import eval_component
from components.inference.component import inference_component


@pipeline(
    name="FLTS Time Series Training Pipeline",
    description="End-to-end time-series training with GRU, LSTM, Prophet models"
)
def flts_pipeline(
    dataset_name: str = "PobleSec",
    identifier: str = "run-001",
    sample_train_rows: int = 50,
    sample_test_rows: int = 50,
    # Training hyperparameters
    hidden_size: int = 128,
    num_layers: int = 2,
    batch_size: int = 64,
    epochs: int = 10,
    learning_rate: float = 1e-4,
    # Inference config
    inference_length: int = 10,
    sample_idx: int = 0,
    # Service endpoints
    gateway_url: str = "http://fastapi-app:8000",
    mlflow_tracking_uri: str = "http://mlflow:5000"
):
    """FLTS pipeline with Kubeflow artifact passing (no Kafka)."""
    
    # Step 1: Preprocess
    preprocess_task = preprocess_component(
        dataset_name=dataset_name,
        identifier=identifier,
        sample_train_rows=sample_train_rows,
        sample_test_rows=sample_test_rows,
        gateway_url=gateway_url
    )
    
    # Step 2: Parallel training (fan-out)
    train_gru_task = train_gru_component(
        training_data=preprocess_task.outputs['training_data'],
        config_hash=preprocess_task.outputs['config_hash'],
        config_json=preprocess_task.outputs['config_json'],
        identifier=identifier,
        hidden_size=hidden_size,
        num_layers=num_layers,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url
    )
    
    train_lstm_task = train_lstm_component(
        training_data=preprocess_task.outputs['training_data'],
        config_hash=preprocess_task.outputs['config_hash'],
        config_json=preprocess_task.outputs['config_json'],
        identifier=identifier,
        hidden_size=hidden_size,
        num_layers=num_layers,
        batch_size=batch_size,
        epochs=epochs,
        learning_rate=learning_rate,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url
    )
    
    train_prophet_task = train_prophet_component(
        training_data=preprocess_task.outputs['training_data'],
        config_hash=preprocess_task.outputs['config_hash'],
        config_json=preprocess_task.outputs['config_json'],
        identifier=identifier,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url
    )
    
    # Step 3: Evaluation (fan-in: waits for all trainers)
    eval_task = eval_component(
        gru_model=train_gru_task.outputs['model'],
        gru_metrics=train_gru_task.outputs['metrics'],
        lstm_model=train_lstm_task.outputs['model'],
        lstm_metrics=train_lstm_task.outputs['metrics'],
        prophet_model=train_prophet_task.outputs['model'],
        prophet_metrics=train_prophet_task.outputs['metrics'],
        config_hash=preprocess_task.outputs['config_hash'],
        identifier=identifier,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url
    )
    
    # Step 4: Batch inference (uses promoted model)
    inference_task = inference_component(
        inference_data=preprocess_task.outputs['inference_data'],
        selected_model=eval_task.outputs['selected_model'],
        config_hash=preprocess_task.outputs['config_hash'],
        identifier=identifier,
        inference_length=inference_length,
        sample_idx=sample_idx,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url
    )
```

**DAG Visualization:**

```
                 ┌─────────────┐
                 │ Preprocess  │
                 └──────┬──────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   ┌────▼────┐     ┌───▼────┐     ┌───▼──────┐
   │Train GRU│     │Train   │     │Train     │
   │         │     │LSTM    │     │Prophet   │
   └────┬────┘     └───┬────┘     └───┬──────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                  ┌────▼────┐
                  │  Eval   │
                  └────┬────┘
                       │
                  ┌────▼─────┐
                  │Inference │
                  └──────────┘
```

**Key Features:**
- **Parallel execution:** GRU, LSTM, Prophet train simultaneously
- **Automatic synchronization:** Eval waits for all trainers (DAG dependency)
- **Artifact lineage:** config_hash flows through all stages
- **MinIO backing:** All artifacts stored in MinIO (KFP uses MinIO as artifact repository)

---

## Container Image Changes

### Build Strategy

**Option 1: Add USE_KFP flag to existing images**
```dockerfile
# No changes to Dockerfile
# Runtime behavior controlled by env var: USE_KFP=1
```

**Option 2: Separate KFP images (recommended)**
```dockerfile
# Dockerfile.kfp in each container directory
FROM flts-preprocess:latest
RUN pip install kfp==2.5.0
ENV USE_KFP=1
```

**Option 3: Multi-stage build**
```dockerfile
FROM flts-preprocess:latest AS base
FROM base AS kfp
RUN pip install kfp==2.5.0
ENV USE_KFP=1
```

**Recommendation:** Option 1 for simplicity. Add `kfp` to requirements.txt in each container.

---

## Component Implementation Strategy

### Phase 1: Add KFP Entry Points (Non-Breaking)

For each container, add parallel entry point that doesn't use Kafka:

**Example: `preprocess_container/main_kfp.py`**
```python
"""KFP-compatible entry point for preprocessing."""
from __future__ import annotations
import os
from typing import NamedTuple

# Reuse existing modules (no changes)
from preprocess_runner import run_pipeline
from data_utils import read_data, to_parquet_bytes
from client_utils import get_file, post_file

def run_preprocess_kfp() -> NamedTuple:
    """Run preprocessing without Kafka, return artifacts."""
    os.environ['USE_KFP'] = '1'  # Disable Kafka code paths
    
    # Existing preprocessing logic
    train_df, test_df, config_hash, canonical_json = run_pipeline()
    
    # Write to MinIO (existing gateway)
    train_bytes = to_parquet_bytes(train_df, {"config_hash": config_hash})
    test_bytes = to_parquet_bytes(test_df, {"config_hash": config_hash})
    
    gateway = os.environ.get("GATEWAY_URL")
    post_file(gateway, "processed-data", "processed_data.parquet", train_bytes)
    post_file(gateway, "processed-data", "test_processed_data.parquet", test_bytes)
    
    # Return artifact metadata (KFP will handle artifact creation)
    Outputs = NamedTuple('Outputs', [
        ('training_data_uri', str),
        ('inference_data_uri', str),
        ('config_hash', str),
        ('config_json', str)
    ])
    
    return Outputs(
        training_data_uri="minio://processed-data/processed_data.parquet",
        inference_data_uri="minio://processed-data/test_processed_data.parquet",
        config_hash=config_hash,
        config_json=canonical_json
    )
```

**Key Principle:** New file, no modifications to existing `main.py`. Kafka path still works.

---

### Phase 2: Gate Kafka Code

Wrap Kafka imports and calls with feature flag:

**Example: `train_container/main.py`**
```python
# Before:
from kafka_utils import create_consumer, produce_message

# After:
USE_KFP = os.environ.get('USE_KFP') == '1'

if not USE_KFP:
    from kafka_utils import create_consumer, produce_message
```

```python
# Before:
consumer = create_consumer(CONSUMER_TOPIC, GROUP_ID)
consume_messages(consumer, callback)

# After:
if not USE_KFP:
    consumer = create_consumer(CONSUMER_TOPIC, GROUP_ID)
    consume_messages(consumer, callback)
else:
    # KFP path: read from artifact passed as arg
    message = _read_from_kfp_input()
    callback_kfp(message)
```

**Compatibility Matrix:**
| Mode | USE_KFP | Behavior |
|------|---------|----------|
| Kafka (legacy) | 0 or unset | Original Kafka consumer/producer loop |
| KFP | 1 | Read from Input[], write to Output[], no Kafka |
| Standalone | 2 | Direct file read, no messaging (debugging) |

---

## Artifact Storage Configuration

### MinIO as KFP Artifact Repository

**KFP Configuration (`kfp_run.yaml`):**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kfp-artifact-config
data:
  MINIO_ENDPOINT: "minio:9000"
  MINIO_ACCESS_KEY: "minioadmin"
  MINIO_SECRET_KEY: "minioadmin"
  MINIO_BUCKET: "kfp-artifacts"
  MINIO_SECURE: "false"
```

**Pipeline Root:**
```python
from kfp import compiler

compiler.Compiler().compile(
    pipeline_func=flts_pipeline,
    package_path='flts_pipeline.yaml',
    pipeline_parameters={
        'pipeline_root': 's3://kfp-artifacts/'  # MinIO bucket
    }
)
```

**Artifact Path Structure:**
```
kfp-artifacts/
├── pipelines/
│   └── flts-training-pipeline/
│       └── runs/
│           └── <run-id>/
│               ├── preprocess/
│               │   ├── training_data
│               │   └── inference_data
│               ├── train-gru/
│               │   ├── model
│               │   └── metrics
│               ├── train-lstm/
│               │   ├── model
│               │   └── metrics
│               ├── train-prophet/
│               │   ├── model
│               │   └── metrics
│               ├── eval/
│               │   ├── selected_model
│               │   └── promotion_metadata
│               └── inference/
│                   ├── predictions
│                   └── metrics
```

**Note:** This is separate from existing MinIO buckets:
- `dataset/` - raw data (unchanged)
- `processed-data/` - preprocessed parquet (unchanged)
- `mlflow/` - MLflow artifacts (unchanged)
- `model-promotion/` - promotion history (unchanged)
- `kfp-artifacts/` - **NEW** - KFP artifact metadata

**Claim-Check Pattern Preserved:**
- KFP artifacts store **pointers** to MinIO objects
- Actual data still in `processed-data/`, `mlflow/` buckets
- No duplication, just metadata layer

---

## Testing Strategy

### Unit Tests (Per Component)

**Test File:** `kubeflow_pipeline/components/preprocess/test_component.py`
```python
def test_preprocess_component_kfp_mode():
    """Verify preprocess component works without Kafka."""
    os.environ['USE_KFP'] = '1'
    
    # Mock gateway
    with patch('client_utils.get_file') as mock_get:
        mock_get.return_value = io.BytesIO(b"Date,Value\n2025-01-01,100\n")
        
        outputs = run_preprocess_kfp()
        
        assert outputs.config_hash.startswith('abc')
        assert 'minio://processed-data' in outputs.training_data_uri
        # No Kafka calls
        assert 'create_producer' not in str(mock_calls)
```

### Integration Tests (Pipeline)

**Test File:** `migration/tests/test_kfp_end_to_end.py`
```python
def test_full_pipeline_execution():
    """Test complete pipeline from preprocess to inference."""
    from kfp import Client
    
    client = Client(host='http://localhost:8080')  # KFP API
    
    run = client.create_run_from_pipeline_func(
        flts_pipeline,
        arguments={
            'dataset_name': 'PobleSec',
            'identifier': 'test-run-001',
            'sample_train_rows': 10,
            'epochs': 1  # Fast test
        }
    )
    
    # Wait for completion
    run.wait_for_run_completion(timeout=600)
    
    assert run.status == 'Succeeded'
    
    # Verify artifacts exist
    assert _minio_object_exists('processed-data/processed_data.parquet')
    assert _mlflow_run_exists(run.outputs['train_gru_task']['run_id'])
    assert _minio_object_exists('model-promotion/test-run-001/.../current.json')
```

---

## Migration Checklist

### Preprocess Component
- [ ] Add `main_kfp.py` entry point
- [ ] Return artifact URIs instead of Kafka publish
- [ ] Gate Kafka imports with `if not USE_KFP:`
- [ ] Preserve config_hash calculation
- [ ] Preserve MinIO writes via gateway
- [ ] Test: Run standalone with USE_KFP=1
- [ ] Test: Verify Parquet metadata intact

### Train Components (GRU/LSTM/Prophet)
- [ ] Add `train_kfp.py` entry point
- [ ] Accept Dataset input, return Model + metrics
- [ ] Remove Kafka consumer loop
- [ ] Preserve MLflow logging
- [ ] Preserve scaler saving
- [ ] Gate Kafka code with feature flag
- [ ] Test: Train with direct file input
- [ ] Test: Verify MLflow run created

### Eval Component
- [ ] Add `eval_kfp.py` entry point
- [ ] Accept all model inputs (no event loop)
- [ ] Return selected model artifact
- [ ] Preserve promotion history writes
- [ ] Preserve current.json structure
- [ ] Remove `_completion_tracker`
- [ ] Gate Kafka code
- [ ] Test: Score multiple models
- [ ] Test: Verify MinIO promotion files

### Inference Component
- [ ] Add `inference_kfp.py` entry point
- [ ] Accept Dataset + Model inputs
- [ ] Return predictions artifact
- [ ] Preserve Inferencer class logic
- [ ] Preserve JSONL logging
- [ ] Remove multi-topic consumer
- [ ] Gate Kafka code
- [ ] Test: Run batch inference
- [ ] Test: Verify inference-logs/ output

### Pipeline Definition
- [ ] Create `pipeline.py` with @pipeline decorator
- [ ] Wire all component dependencies
- [ ] Pass config_hash through stages
- [ ] Configure MinIO artifact repository
- [ ] Add pipeline parameters
- [ ] Test: Compile pipeline YAML
- [ ] Test: Submit to KFP

### Infrastructure
- [ ] Update container Dockerfiles (add kfp package)
- [ ] Create `docker-compose.kfp.yaml` (no Kafka)
- [ ] Deploy KFP on Kubernetes/Minikube
- [ ] Configure MinIO as artifact backend
- [ ] Update Helm chart (optional)
- [ ] Test: Full pipeline run in cluster

---

## Backwards Compatibility

**Dual-Mode Support:**
```python
def run_preprocess():
    """Backward-compatible entry point."""
    if os.environ.get('USE_KFP') == '1':
        return run_preprocess_kfp()
    else:
        return run_preprocess_kafka()  # Original implementation
```

**Deployment Options:**
1. **Kafka mode** (default): `USE_KFP=0`, docker-compose.yaml
2. **KFP mode**: `USE_KFP=1`, Kubeflow pipeline
3. **Coexistence**: Both modes in same cluster (different deployments)

**Migration Path:**
- Week 1: Add KFP entry points (non-breaking)
- Week 2: Test KFP pipeline in parallel
- Week 3: Validate results match Kafka version
- Week 4: Switch production to KFP
- Week 5: Deprecate Kafka mode (optional)

---

## Risk Mitigation

### Risk 1: Config Hash Mismatch
**Mitigation:** Pass config_hash as explicit artifact output, verify in tests

### Risk 2: MinIO Claim-Check Pattern Break
**Mitigation:** Keep gateway API unchanged, artifacts only store URIs

### Risk 3: MLflow Lineage Loss
**Mitigation:** Preserve all MLflow logging, add KFP run ID to tags

### Risk 4: Promotion Pointer Corruption
**Mitigation:** Test current.json structure matches exactly, atomic writes

### Risk 5: Inference Model Load Failure
**Mitigation:** Keep Inferencer class logic unchanged, test model URI resolution

---

## Success Criteria

Pipeline is successfully migrated when:

1. ✅ **All Kafka topics removed** from docker-compose.kfp.yaml
2. ✅ **DAG compiles** without errors (`kfp.compiler`)
3. ✅ **Pipeline runs end-to-end** (preprocess → train → eval → inference)
4. ✅ **Artifacts created** in MinIO kfp-artifacts bucket
5. ✅ **MLflow runs logged** with same structure as Kafka version
6. ✅ **Promotion history** written to model-promotion/ bucket
7. ✅ **Inference results** match Kafka pipeline output (JSONL format)
8. ✅ **Config hash** preserved through all stages
9. ✅ **No ML logic changed** (models identical to Kafka version)
10. ✅ **Backward compatibility** maintained (Kafka mode still works)

---

**Plan Complete.** Ready to proceed with Task 3: Build Preprocess Component.
