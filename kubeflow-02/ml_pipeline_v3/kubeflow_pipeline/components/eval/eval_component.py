"""KFP v2 Component Wrapper for Model Evaluation.

This module provides the Kubeflow Pipelines v2 component definition for evaluating
and selecting the best time-series forecasting model from GRU, LSTM, and Prophet candidates.
It wraps the existing eval_container logic with USE_KFP=1 flag to enable KFP artifact I/O.
"""

from typing import NamedTuple
from kfp.dsl import component, Model, Artifact, Output


@component(
    base_image="eval-container:latest",
    packages_to_install=[]
)
def eval_models_component(
    gru_model: Model,
    lstm_model: Model,
    prophet_model: Model,
    config_hash: str,
    promotion_pointer: Output[Artifact],
    eval_metadata: Output[Artifact],
    identifier: str = "",
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    promotion_bucket: str = "model-promotion",
    rmse_weight: float = 0.5,
    mae_weight: float = 0.3,
    mse_weight: float = 0.2
):
    """Evaluate and select the best time-series forecasting model.
    
    Args:
        gru_model: Trained GRU model artifact with test metrics
        lstm_model: Trained LSTM model artifact with test metrics
        prophet_model: Trained Prophet model artifact with test metrics
        config_hash: SHA256 hash of preprocessing config for run lineage
        promotion_pointer: Output promotion pointer (MinIO URI to selected model)
        eval_metadata: Output detailed evaluation results
        identifier: Pipeline run identifier for promotion history
        mlflow_tracking_uri: MLflow tracking server endpoint
        mlflow_s3_endpoint: MinIO endpoint for MLflow artifacts
        gateway_url: FastAPI gateway for MinIO uploads
        promotion_bucket: MinIO bucket for promotion history
        rmse_weight: Weight for RMSE in composite score (default 0.5)
        mae_weight: Weight for MAE in composite score (default 0.3)
        mse_weight: Weight for MSE in composite score (default 0.2)
    
    Returns:
        None (outputs written to promotion_pointer and eval_metadata)
    """
    import os
    import json
    
    # Set environment variables for container execution
    os.environ["USE_KFP"] = "1"
    os.environ["CONFIG_HASH"] = config_hash
    os.environ["IDENTIFIER"] = identifier
    os.environ["MLFLOW_TRACKING_URI"] = mlflow_tracking_uri
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = mlflow_s3_endpoint
    os.environ["GATEWAY_URL"] = gateway_url
    os.environ["PROMOTION_BUCKET"] = promotion_bucket
    os.environ["SCORE_WEIGHTS"] = json.dumps({"rmse": rmse_weight, "mae": mae_weight, "mse": mse_weight})
    os.environ["KFP_GRU_MODEL_INPUT_PATH"] = gru_model.path
    os.environ["KFP_LSTM_MODEL_INPUT_PATH"] = lstm_model.path
    os.environ["KFP_PROPHET_MODEL_INPUT_PATH"] = prophet_model.path
    os.environ["KFP_PROMOTION_OUTPUT_PATH"] = promotion_pointer.path
    os.environ["KFP_EVAL_METADATA_OUTPUT_PATH"] = eval_metadata.path
    os.environ["AWS_ACCESS_KEY_ID"] = "minio_access_key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "minio_secret_key"
    
    # Import and execute evaluation logic
    # NOTE: The actual evaluation is performed by eval_container/main.py
    # which reads KFP_* environment variables and writes outputs
    from eval_container import main
    
    # Read outputs written by container
    with open(promotion_pointer.path, 'r') as f:
        pointer_data = json.load(f)
    promotion_pointer.uri = pointer_data['uri']
    promotion_pointer.metadata.update(pointer_data['metadata'])
    
    with open(eval_metadata.path, 'r') as f:
        metadata = json.load(f)
    eval_metadata.metadata.update(metadata)
