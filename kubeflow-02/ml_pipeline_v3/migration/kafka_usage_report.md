# Kafka Usage Report - FLTS Pipeline

**Generated:** November 24, 2025  
**Purpose:** Complete inventory of all Kafka communication in the pipeline for KFP v2 migration

---

## Executive Summary

The FLTS pipeline uses Kafka for asynchronous message passing between 6 containerized stages:
1. **Preprocess** (producer only)
2. **Train Containers** (GRU, LSTM, Prophet - consumer + producer)
3. **Eval** (consumer + producer)
4. **Inference** (consumer, multiple topics)

All Kafka operations are centralized in `shared/kafka_utils.py` and imported into each container's local `kafka_utils.py`.

---

## Kafka Topics Inventory

### 1. `training-data`
**Purpose:** Claim checks for preprocessed training datasets  
**Producer:** `preprocess_container`  
**Consumers:** `train_gru`, `train_lstm`, `nonml_prophet`  
**Message Schema:**
```json
{
  "bucket": "processed-data",
  "object": "processed_data.parquet",
  "size": 123456,
  "v": 1,
  "identifier": "run-xyz"
}
```

### 2. `inference-data`
**Purpose:** Claim checks for preprocessed inference/test datasets  
**Producer:** `preprocess_container`  
**Consumers:** `inference_container`  
**Message Schema:**
```json
{
  "bucket": "processed-data",
  "object": "test_processed_data.parquet",
  "object_key": "test_processed_data.parquet",
  "size": 123456,
  "operation": "post: test data",
  "v": 1,
  "identifier": "run-xyz"
}
```

### 3. `model-training`
**Purpose:** Training lifecycle events (RUNNING, SUCCESS) with model metadata  
**Producers:** `train_gru`, `train_lstm`, `nonml_prophet`  
**Consumers:** `eval_container`, `inference_container`  
**Message Schema - RUNNING Event:**
```json
{
  "model_type": "GRU",
  "config_hash": "abc123...",
  "run_id": "mlflow-run-id",
  "status": "RUNNING",
  "identifier": "run-xyz"
}
```
**Message Schema - SUCCESS Event:**
```json
{
  "model_type": "GRU",
  "config_hash": "abc123...",
  "run_id": "mlflow-run-id",
  "status": "SUCCESS",
  "test_rmse": 0.123,
  "test_mae": 0.045,
  "test_mse": 0.015,
  "train_start": "2025-11-24T12:00:00Z",
  "train_end": "2025-11-24T12:05:00Z",
  "identifier": "run-xyz",
  "artifact_uri": "s3://mlflow/run-id/artifacts"
}
```

### 4. `model-selected`
**Purpose:** Promotion events from evaluator indicating best model  
**Producer:** `eval_container`  
**Consumers:** `inference_container`  
**Message Schema:**
```json
{
  "model_uri": "runs:/run-id/GRU",
  "model_type": "GRU",
  "run_id": "mlflow-run-id",
  "config_hash": "abc123...",
  "composite_score": 0.089,
  "test_rmse": 0.123,
  "test_mae": 0.045,
  "test_mse": 0.015,
  "promotion_time": "2025-11-24T12:10:00Z",
  "identifier": "run-xyz"
}
```

### 5. `performance-eval` (currently unused in main flow)
**Purpose:** Inference performance metrics  
**Producer:** `inference_container`  
**Consumers:** None (monitoring sink)

### 6. DLQ Topics
**Pattern:** `DLQ-<base-topic>`  
**Examples:** `DLQ-training-data`, `DLQ-model-training`, `DLQ-model-selected`, `DLQ-preprocess`  
**Purpose:** Dead letter queue for error handling  

---

## Container-by-Container Kafka Usage

### Preprocess Container (`preprocess_container/`)

**File:** `main.py`  
**Imports:** `kafka_utils.py` → `shared/kafka_utils.py`

**Functions Using Kafka:**

1. **`run_preprocess()`** (line ~272-355)
   - Creates producer: `producer = create_producer()`
   - Publishes to `PRODUCER_TOPIC_0` (training-data):
     ```python
     produce_message(
         producer,
         topic_train,
         {"bucket": out_bucket, "object": train_obj, "size": len(train_bytes), 
          "v": 1, "identifier": identifier},
         key="train-claim"
     )
     ```
   - Publishes to `PRODUCER_TOPIC_1` (inference-data):
     ```python
     produce_message(
         producer,
         topic_infer,
         {"bucket": out_bucket, "object": test_obj, "object_key": test_obj, 
          "size": len(test_bytes), "operation": "post: test data", 
          "v": 1, "identifier": identifier},
         key="inference-claim"
     )
     ```
   - Error handling: `publish_error(producer, "DLQ-preprocess", ...)`

**Environment Variables:**
- `KAFKA_BOOTSTRAP_SERVERS` (required)
- `PRODUCER_TOPIC_0` (default: "training-data")
- `PRODUCER_TOPIC_1` (default: "inference-data")

---

### Train Containers (`train_container/`, also used by `nonML_container/`)

**Files:** `main.py`, `kafka_utils.py`  
**Imports:** `kafka_utils.py` → `shared/kafka_utils.py`

**Functions Using Kafka:**

1. **`callback(message)`** (line ~82)
   - Kafka message receiver, puts messages in queue
   
2. **Training workflow** (line ~200-450)
   - Creates consumer: `consumer = create_consumer(CONSUMER_TOPIC, CONSUMER_GROUP_ID)`
   - Consumes from `CONSUMER_TOPIC` (training-data)
   - Starts consumer loop: `consume_messages(consumer, callback)`
   - Worker thread processes messages from queue
   
3. **`_publish_training_start()`** (line ~303-306)
   - Publishes RUNNING event to `PRODUCER_TOPIC` (model-training):
     ```python
     produce_message(producer, topic, {
         "model_type": MODEL_TYPE,
         "config_hash": CONFIG_HASH,
         "run_id": run_id,
         "status": "RUNNING",
         "identifier": identifier
     })
     ```

4. **`_publish_training_success()`** (line ~349-352)
   - Publishes SUCCESS event to `PRODUCER_TOPIC` (model-training):
     ```python
     success_payload = {
         "model_type": MODEL_TYPE,
         "config_hash": config_hash,
         "run_id": run_id,
         "status": "SUCCESS",
         "test_rmse": test_rmse,
         "test_mae": test_mae,
         "test_mse": test_mse,
         "train_start": start_time,
         "train_end": end_time,
         "identifier": identifier,
         "artifact_uri": artifact_uri
     }
     produce_message(producer, topic, success_payload, key=f"trained-{MODEL_TYPE}")
     ```

5. **Error handling** (multiple locations)
   - `publish_error(producer, f"DLQ-{PRODUCER_TOPIC}", ...)`

**Environment Variables:**
- `KAFKA_BOOTSTRAP_SERVERS` (required)
- `CONSUMER_TOPIC` (default: "training-data")
- `CONSUMER_GROUP_ID` (required, unique per model type)
- `PRODUCER_TOPIC` (default: "model-training")

---

### Eval Container (`eval_container/`)

**File:** `main.py`  
**Imports:** `kafka_utils.py` → `shared/kafka_utils.py`

**Functions Using Kafka:**

1. **`main()` consumer loop** (line ~350-469)
   - Creates consumer: `consumer = create_consumer(MODEL_TRAINING_TOPIC, GROUP_ID)`
   - Consumes from `MODEL_TRAINING_TOPIC` (model-training)
   - Tracks completion per config_hash using `_completion_tracker`
   
2. **Completion tracking logic** (line ~375-430)
   - Waits for SUCCESS messages from all expected model types
   - When all models complete for a config_hash, triggers promotion
   
3. **`promote_model()`** (line ~250-330)
   - Queries MLflow for best model
   - Writes promotion history to MinIO (`model-promotion/...`)
   - Publishes to `MODEL_SELECTED_TOPIC` (model-selected):
     ```python
     promotion_event = {
         "model_uri": best_model_uri,
         "model_type": best_model_type,
         "run_id": best_run_id,
         "config_hash": config_hash,
         "composite_score": best_score,
         "test_rmse": rmse,
         "test_mae": mae,
         "test_mse": mse,
         "promotion_time": timestamp,
         "identifier": identifier
     }
     produce_message(producer, MODEL_SELECTED_TOPIC, promotion_event, key="promotion")
     ```

4. **Error handling**
   - `publish_error(producer, DLQ_TOPIC, ...)`

**Environment Variables:**
- `KAFKA_BOOTSTRAP_SERVERS` (required)
- `MODEL_TRAINING_TOPIC` (default: "model-training")
- `MODEL_SELECTED_TOPIC` (default: "model-selected")
- `EVAL_GROUP_ID` (default: "eval-promoter")
- `DLQ_MODEL_SELECTED` (default: "DLQ-model-selected")
- `EXPECTED_MODEL_TYPES` (default: "GRU,LSTM,PROPHET")

---

### Inference Container (`inference_container/`)

**File:** `main.py`  
**Imports:** `kafka_utils.py` → `shared/kafka_utils.py`

**Functions Using Kafka:**

1. **Multi-topic consumer setup** (line ~150-250)
   - Consumes from 3 topics simultaneously:
     - `CONSUMER_TOPIC_0` (inference-data) - test datasets
     - `CONSUMER_TOPIC_1` (model-training) - fast path model load
     - `PROMOTION_TOPIC` (model-selected) - promotion pointer
   - Uses manual commit: `create_consumer_configurable(..., enable_auto_commit=False)`

2. **Promotion message handler** (line ~400-550)
   - Receives model-selected messages
   - Loads promoted model from MLflow
   - Updates internal model cache
   
3. **Training SUCCESS handler** (line ~550-650)
   - Fast path: immediately load newly trained model
   - Triggered by `RUN_INFERENCE_ON_TRAIN_SUCCESS=1`
   
4. **Inference data handler** (line ~650-800)
   - Receives test dataset claim checks
   - Downloads Parquet from MinIO
   - Runs windowed inference
   - Logs results to `inference-logs/` bucket

5. **Manual offset commit**
   - Uses `commit_offsets_sync(consumer, offsets_by_tp)`
   - Ensures at-least-once processing

6. **Producer usage**
   - Publishes inference metrics to `PRODUCER_TOPIC` (performance-eval)

**Environment Variables:**
- `KAFKA_BOOTSTRAP_SERVERS` (required)
- `CONSUMER_TOPIC_0` (default: "inference-data")
- `CONSUMER_TOPIC_1` (default: "model-training")
- `PROMOTION_TOPIC` (default: "model-selected")
- `CONSUMER_GROUP_ID` (default: "batch-forecasting-v2")
- `PRODUCER_TOPIC` (default: "performance-eval")
- `RUN_INFERENCE_ON_TRAIN_SUCCESS` (default: 1)
- Multiple concurrency/backpressure settings

---

## Shared Kafka Utilities (`shared/kafka_utils.py`)

**Functions:**

1. **`create_producer(**overrides)`**
   - Returns configured `KafkaProducer`
   - JSON serialization
   - Uses `KAFKA_BOOTSTRAP_SERVERS`

2. **`create_consumer(topic, group_id, **overrides)`**
   - Returns configured `KafkaConsumer`
   - JSON deserialization
   - Auto-commit enabled by default

3. **`create_consumer_configurable(topic, group_id, enable_auto_commit=False, ...)`**
   - Advanced consumer with manual commit control
   - Used by inference for backpressure handling

4. **`produce_message(producer, topic, value, key=None)`**
   - Sends JSON message with flush
   - Returns success boolean

5. **`consume_messages(consumer, callback)`**
   - Blocking consumer loop
   - Calls callback for each message

6. **`commit_offsets_sync(consumer, offsets_by_tp)`**
   - Manual offset commit helper

7. **`publish_error(producer, dlq_topic, operation, status, error_details, payload)`**
   - DLQ message constructor
   - Adds timestamp

---

## Docker Compose Kafka Configuration

From `docker-compose.yaml`:

```yaml
kafka:
  image: apache/kafka:3.9.1
  ports:
    - "9092:9092"
    - "9093:9093"
  environment:
    KAFKA_PROCESS_ROLES: "broker, controller"
    KAFKA_NODE_ID: 1
    # KRaft mode (no Zookeeper)
```

**All containers depend on:**
```yaml
depends_on:
  kafka:
    condition: service_healthy
```

---

## Kafka Environment Variables - Mapping Table

| Container | KAFKA_BOOTSTRAP_SERVERS | CONSUMER_TOPIC(s) | PRODUCER_TOPIC(s) | GROUP_ID |
|-----------|------------------------|-------------------|-------------------|----------|
| preprocess | kafka:9092 | - | training-data, inference-data | - |
| train_gru | kafka:9092 | training-data | model-training | train-gru |
| train_lstm | kafka:9092 | training-data | model-training | train-lstm |
| nonml_prophet | kafka:9092 | training-data | model-training | nonml-prophet |
| eval | kafka:9092 | model-training | model-selected | eval-promoter-r5 |
| inference | kafka:9092 | inference-data, model-training, model-selected | performance-eval | batch-forecasting-v2 |

---

## Message Flow Diagram (ASCII)

```
┌──────────────┐
│  Preprocess  │
└──────┬───────┘
       │
       ├─────► training-data ────► ┌────────────┐
       │                           │ Train GRU  │
       │                           └─────┬──────┘
       │                                 │
       ├─────► training-data ────► ┌────┴───────┐
       │                           │ Train LSTM │
       │                           └─────┬──────┘
       │                                 │
       ├─────► training-data ────► ┌────┴────────┐
       │                           │   Prophet   │
       │                           └─────┬───────┘
       │                                 │
       │                                 ▼
       │                          model-training ────► ┌──────┐
       │                                                │ Eval │
       │                                                └──┬───┘
       │                                                   │
       │                                                   ▼
       │                                           model-selected
       │                                                   │
       └─────► inference-data ────────────────────────────┤
                                                           │
                                                           ▼
                                                   ┌──────────────┐
                                                   │  Inference   │
                                                   └──────┬───────┘
                                                          │
                                                          ▼
                                                  performance-eval
```

---

## Verification Against docker-compose.yaml

✅ **All Kafka topics matched:**
- training-data ✓
- inference-data ✓
- model-training ✓
- model-selected ✓
- performance-eval ✓

✅ **All KAFKA_BOOTSTRAP_SERVERS references found:**
- preprocess: kafka:9092 ✓
- train containers: kafka:9092 ✓
- eval: kafka:9092 ✓
- inference: kafka:9092 ✓

✅ **All consumer/producer topic environment variables matched** to code usage

---

## Migration Impact Analysis

### High Impact (Core Pipeline):
1. **Preprocess → Train** (training-data topic)
   - Most critical path
   - Single producer, multiple consumers
   - Must preserve config_hash lineage

2. **Train → Eval** (model-training topic)
   - Complex state machine (RUNNING → SUCCESS)
   - Multi-model coordination
   - Config_hash-based grouping

3. **Eval → Inference** (model-selected topic)
   - Promotion pointer mechanism
   - Must maintain MinIO promotion history structure

### Medium Impact:
4. **Preprocess → Inference** (inference-data topic)
   - Optional path for batch inference
   - Can be triggered via API instead

5. **Train → Inference** (model-training topic, fast path)
   - Performance optimization
   - Not strictly required for correctness

### Low Impact:
6. **Inference → Monitoring** (performance-eval topic)
   - Metrics/observability
   - No downstream consumers in pipeline

---

## Claim-Check Pattern Usage

All data payloads use MinIO claim-check pattern:
- Kafka messages contain only **metadata** + **bucket/object pointers**
- Actual data (Parquet files, models) stored in MinIO
- Downloaded on-demand by consumers via gateway

**This pattern must be preserved in KFP migration:**
- KFP artifacts will point to MinIO URIs
- No change to underlying storage mechanism
- Components will still use `get_file()` / `post_file()` via gateway

---

## Error Handling & DLQ

All containers implement DLQ pattern:
```python
try:
    # operation
except Exception as e:
    publish_error(producer, f"DLQ-{topic}", operation, "Failure", str(e), payload)
```

**KFP Migration Note:**
- Replace DLQ topics with KFP task failure annotations
- Use component-level exception handling
- Log errors to MLflow or MinIO for debugging

---

## Testing Checkpoints

To validate this mapping is complete:

1. ✅ Searched for all `KafkaProducer` references
2. ✅ Searched for all `KafkaConsumer` references  
3. ✅ Searched for all `KAFKA_BOOTSTRAP_SERVERS` references
4. ✅ Searched for all `CONSUMER_TOPIC` variants
5. ✅ Searched for all `PRODUCER_TOPIC` variants
6. ✅ Cross-referenced against docker-compose.yaml
7. ✅ Verified all topic names in code match compose
8. ✅ Verified all consumer group IDs
9. ✅ Documented message schemas from code inspection
10. ✅ Traced complete message flow from preprocess → inference

---

## Next Steps (Task 2)

This report provides the foundation for Task 2: Design the KFP v2 DAG skeleton.

Each Kafka topic will be replaced with a KFP artifact:
- **training-data** → `Output[Dataset]` from preprocess_component
- **model-training** → `Output[Model]` from trainer components
- **model-selected** → `Output[Artifact]` from eval_component
- **inference-data** → `Output[Dataset]` from preprocess_component

The next step is to create `migration/kfp_plan.md` with the detailed mapping.

---

**Report Complete:** All Kafka usage has been identified and documented.
