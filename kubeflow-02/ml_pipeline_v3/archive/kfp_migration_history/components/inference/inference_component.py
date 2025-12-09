"""
KFP v2 Inference Component Wrapper

This component executes time-series forecasting inference using a promoted model.
It loads preprocessed inference data, retrieves the promoted model from MLflow,
runs windowed batch inference with optional microbatching, and outputs structured
JSONL results and execution metadata.

Design:
- Input: Dataset (Parquet with DatetimeIndex), Model artifact (promotion pointer from eval)
- Output: Artifact (JSONL inference results), Artifact (execution metadata JSON)
- Container: inference-container:latest runs inference_container/main.py in KFP mode (USE_KFP=1)
- MLflow: Loads model from URI in promoted model artifact metadata
- MinIO: Writes inference logs to inference-logs bucket with identifier-based path organization
- Behavior: Preserves all windowed inference logic, microbatching, prewarm, prediction caching
"""

from kfp.dsl import component, Dataset, Model, Artifact, Input, Output
import os

@component(
    base_image="inference-container:latest",
    packages_to_install=[]
)
def run_inference_component(
    # Inputs
    inference_data: Input[Dataset],
    promoted_model: Input[Model],
    identifier: str = "",
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    inference_log_bucket: str = "inference-logs",
    inference_length: int = 1,
    sample_idx: int = 0,
    enable_microbatch: str = "false",
    batch_size: int = 32,
    # Outputs
    inference_results: Output[Artifact],
    inference_metadata: Output[Artifact],
):
    """
    Run time-series inference using a promoted model.
    
    Args:
        inference_data: Preprocessed inference data (Parquet format)
        promoted_model: Promoted model pointer from eval component
        identifier: Pipeline run identifier for log organization
        mlflow_tracking_uri: MLflow tracking server URL
        mlflow_s3_endpoint: MinIO endpoint for MLflow artifacts
        gateway_url: FastAPI gateway for MinIO operations
        inference_log_bucket: MinIO bucket for inference logs
        inference_length: Number of forecast steps per inference
        sample_idx: Starting sample index for windowed inference
        enable_microbatch: Enable microbatching ("true"/"false")
        batch_size: Microbatch size when enabled
        inference_results: Output JSONL inference results
        inference_metadata: Output execution metadata
    """
    import subprocess
    import json
    import os
    
    # Set environment variables for inference container
    env = os.environ.copy()
    env.update({
        "USE_KFP": "1",
        "IDENTIFIER": identifier,
        "MLFLOW_TRACKING_URI": mlflow_tracking_uri,
        "MLFLOW_S3_ENDPOINT_URL": mlflow_s3_endpoint,
        "GATEWAY_URL": gateway_url,
        "INFERENCE_LOG_BUCKET": inference_log_bucket,
        "INFERENCE_LENGTH": str(inference_length),
        "SAMPLE_IDX": str(sample_idx),
        "ENABLE_MICROBATCH": enable_microbatch,
        "BATCH_SIZE": str(batch_size),
        "KFP_INFERENCE_DATA_INPUT_PATH": inference_data.path,
        "KFP_PROMOTED_MODEL_INPUT_PATH": promoted_model.path,
        "KFP_INFERENCE_RESULTS_OUTPUT_PATH": inference_results.path,
        "KFP_INFERENCE_METADATA_OUTPUT_PATH": inference_metadata.path,
        "AWS_ACCESS_KEY_ID": "minio_access_key",
        "AWS_SECRET_ACCESS_KEY": "minio_secret_key",
        "AWS_DEFAULT_REGION": "us-east-1",
        "DISABLE_BUCKET_ENSURE": "0",
        "DISABLE_STARTUP_INFERENCE": "1",
    })
    
    # Execute inference container main logic
    result = subprocess.run(
        ["python", "-m", "main"],
        cwd="/inference_container",  # Adjust to actual container path
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Inference execution failed with return code {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise RuntimeError(f"Inference failed: {result.stderr}")
    
    print(f"Inference execution completed successfully")
    print(f"STDOUT: {result.stdout}")
    
    # Read and populate output artifact metadata
    # Results artifact contains JSONL predictions
    with open(inference_results.path, 'r') as f:
        results_lines = f.readlines()
        results_count = len(results_lines)
    
    inference_results.metadata["format"] = "jsonl"
    inference_results.metadata["rows"] = results_count
    
    # Metadata artifact contains execution info
    with open(inference_metadata.path, 'r') as f:
        metadata_content = json.load(f)
    
    inference_metadata.metadata["run_id"] = metadata_content.get("run_id")
    inference_metadata.metadata["model_type"] = metadata_content.get("model_type")
    inference_metadata.metadata["model_class"] = metadata_content.get("model_class")
    inference_metadata.metadata["config_hash"] = metadata_content.get("config_hash")
    inference_metadata.metadata["rows_predicted"] = metadata_content.get("rows_predicted", 0)
    
    # Store timing information if available
    if "timings_ms" in metadata_content:
        inference_metadata.metadata["timings_ms"] = metadata_content["timings_ms"]
    
    print(f"Inference results: {results_count} predictions written")
    print(f"Model: {metadata_content.get('model_type')} (run_id={metadata_content.get('run_id')})")
