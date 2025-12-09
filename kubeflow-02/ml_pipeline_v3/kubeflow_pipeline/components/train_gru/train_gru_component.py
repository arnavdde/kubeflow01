"""KFP v2 Component Wrapper for GRU Training.

This module provides the Kubeflow Pipelines v2 component definition for training
GRU (Gated Recurrent Unit) time-series forecasting models. It wraps the existing
train_container logic with USE_KFP=1 flag to enable KFP artifact I/O.
"""

from typing import NamedTuple
from kfp.dsl import component, Dataset, Model, Artifact, Output


@component(
    base_image="train-container:latest",
    packages_to_install=[]
)
def train_gru_component(
    training_data: Dataset,
    config_hash: str,
    model: Output[Model],
    metrics: Output[Artifact],
    run_id: Output[str],
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    hidden_size: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 0.001,
    batch_size: int = 32,
    num_epochs: int = 50,
    early_stopping_patience: int = 10,
    window_size: int = 12
):
    """Train GRU time-series forecasting model.
    
    Args:
        training_data: Preprocessed training dataset (MinIO URI + metadata)
        config_hash: SHA256 hash of preprocessing config for run lineage
        mlflow_tracking_uri: MLflow tracking server endpoint
        mlflow_s3_endpoint: MinIO endpoint for MLflow artifacts
        gateway_url: FastAPI gateway for MinIO downloads
        hidden_size: GRU hidden layer dimensionality
        num_layers: Number of stacked GRU layers
        dropout: Dropout probability for regularization
        learning_rate: Adam optimizer learning rate
        batch_size: Training batch size
        num_epochs: Number of training epochs
        early_stopping_patience: Epochs without improvement before stopping
        window_size: Lookback window for sequence input
        model: Output model artifact (MLflow URI)
        metrics: Output test metrics (RMSE, MAE, MSE, composite)
        run_id: Output MLflow run ID
    
    Returns:
        NamedTuple with model, metrics, and run_id outputs
    """
    import os
    import json
    from collections import namedtuple
    
    # Set environment variables for container execution
    os.environ["USE_KFP"] = "1"
    os.environ["MODEL_TYPE"] = "GRU"
    os.environ["CONFIG_HASH"] = config_hash
    os.environ["MLFLOW_TRACKING_URI"] = mlflow_tracking_uri
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = mlflow_s3_endpoint
    os.environ["GATEWAY_URL"] = gateway_url
    os.environ["HIDDEN_SIZE"] = str(hidden_size)
    os.environ["NUM_LAYERS"] = str(num_layers)
    os.environ["DROPOUT"] = str(dropout)
    os.environ["LEARNING_RATE"] = str(learning_rate)
    os.environ["BATCH_SIZE"] = str(batch_size)
    os.environ["NUM_EPOCHS"] = str(num_epochs)
    os.environ["EARLY_STOPPING_PATIENCE"] = str(early_stopping_patience)
    os.environ["WINDOW_SIZE"] = str(window_size)
    os.environ["KFP_TRAINING_DATA_INPUT_PATH"] = training_data.path
    os.environ["KFP_MODEL_OUTPUT_PATH"] = model.path
    os.environ["KFP_METRICS_OUTPUT_PATH"] = metrics.path
    os.environ["KFP_RUN_ID_OUTPUT_PATH"] = run_id.path
    os.environ["AWS_ACCESS_KEY_ID"] = "minio_access_key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "minio_secret_key"
    
    # Import and execute training logic
    # NOTE: The actual training is performed by train_container/main.py
    # which reads KFP_* environment variables and writes outputs
    from train_container import main
    
    # Read outputs written by container
    with open(model.path, 'r') as f:
        model_data = json.load(f)
    model.uri = model_data['uri']
    model.metadata.update(model_data['metadata'])
    
    with open(metrics.path, 'r') as f:
        metrics_data = json.load(f)
    metrics.metadata.update(metrics_data)
    
    with open(run_id.path, 'r') as f:
        run_id_value = f.read().strip()
    
    # Return as NamedTuple
    GRUOutputs = namedtuple('GRUOutputs', ['model', 'metrics', 'run_id'])
    return GRUOutputs(model, metrics, run_id_value)
