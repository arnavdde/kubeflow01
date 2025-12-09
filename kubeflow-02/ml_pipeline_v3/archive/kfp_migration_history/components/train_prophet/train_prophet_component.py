"""KFP v2 Component Wrapper for Prophet Training.

This module provides the Kubeflow Pipelines v2 component definition for training
Prophet time-series forecasting models. It wraps the existing nonML_container logic
with USE_KFP=1 flag to enable KFP artifact I/O.
"""

from typing import NamedTuple
from kfp.dsl import component, Dataset, Model, Artifact, Output


@component(
    base_image="nonml-container:latest",
    packages_to_install=[]
)
def train_prophet_component(
    training_data: Dataset,
    config_hash: str,
    model: Output[Model],
    metrics: Output[Artifact],
    run_id: Output[str],
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    seasonality_mode: str = "additive",
    changepoint_prior_scale: float = 0.05,
    seasonality_prior_scale: float = 10.0,
    holidays_prior_scale: float = 10.0,
    daily_seasonality: bool = True,
    weekly_seasonality: bool = True,
    yearly_seasonality: bool = True
):
    """Train Prophet time-series forecasting model.
    
    Args:
        training_data: Preprocessed training dataset (MinIO URI + metadata)
        config_hash: SHA256 hash of preprocessing config for run lineage
        mlflow_tracking_uri: MLflow tracking server endpoint
        mlflow_s3_endpoint: MinIO endpoint for MLflow artifacts
        gateway_url: FastAPI gateway for MinIO downloads
        seasonality_mode: Type of seasonality ('additive' or 'multiplicative')
        changepoint_prior_scale: Flexibility of trend changepoints
        seasonality_prior_scale: Strength of seasonality model
        holidays_prior_scale: Strength of holiday effects
        daily_seasonality: Enable daily seasonality component
        weekly_seasonality: Enable weekly seasonality component
        yearly_seasonality: Enable yearly seasonality component
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
    os.environ["MODEL_TYPE"] = "PROPHET"
    os.environ["CONFIG_HASH"] = config_hash
    os.environ["MLFLOW_TRACKING_URI"] = mlflow_tracking_uri
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = mlflow_s3_endpoint
    os.environ["GATEWAY_URL"] = gateway_url
    os.environ["SEASONALITY_MODE"] = seasonality_mode
    os.environ["CHANGEPOINT_PRIOR_SCALE"] = str(changepoint_prior_scale)
    os.environ["SEASONALITY_PRIOR_SCALE"] = str(seasonality_prior_scale)
    os.environ["HOLIDAYS_PRIOR_SCALE"] = str(holidays_prior_scale)
    os.environ["DAILY_SEASONALITY"] = str(daily_seasonality)
    os.environ["WEEKLY_SEASONALITY"] = str(weekly_seasonality)
    os.environ["YEARLY_SEASONALITY"] = str(yearly_seasonality)
    os.environ["KFP_TRAINING_DATA_INPUT_PATH"] = training_data.path
    os.environ["KFP_MODEL_OUTPUT_PATH"] = model.path
    os.environ["KFP_METRICS_OUTPUT_PATH"] = metrics.path
    os.environ["KFP_RUN_ID_OUTPUT_PATH"] = run_id.path
    os.environ["AWS_ACCESS_KEY_ID"] = "minio_access_key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "minio_secret_key"
    
    # Import and execute training logic
    # NOTE: The actual training is performed by nonML_container/main.py
    # which reads KFP_* environment variables and writes outputs
    from nonML_container import main
    
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
    ProphetOutputs = namedtuple('ProphetOutputs', ['model', 'metrics', 'run_id'])
    return ProphetOutputs(model, metrics, run_id_value)
