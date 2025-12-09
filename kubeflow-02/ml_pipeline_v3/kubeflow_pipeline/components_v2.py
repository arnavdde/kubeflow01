"""
KFP v2 Component Definitions for FLTS Pipeline

This module defines all pipeline components using KFP v2 @dsl.component decorator.
These components replace the YAML-based component definitions and are the single
source of truth for the KFP v2 pipeline.

Components:
1. preprocess_component - Data preprocessing
2. train_gru_component - GRU model training
3. train_lstm_component - LSTM model training
4. train_prophet_component - Prophet model training
5. eval_component - Model evaluation and promotion
6. inference_component - Inference execution

Note: The container images handle the actual execution logic. These component
definitions specify the interface contract and let KFP v2 handle orchestration.
"""

from kfp import dsl
from typing import Optional


@dsl.component(
    base_image="flts-preprocess:latest",
)
def preprocess_component(
    training_data: dsl.Output[dsl.Dataset],
    inference_data: dsl.Output[dsl.Dataset],
    config_hash: dsl.OutputPath(str),
    config_json: dsl.OutputPath(str),
    dataset_name: str = "PobleSec",
    identifier: str = "default",
    sample_train_rows: int = 0,
    sample_test_rows: int = 0,
    sample_strategy: str = "head",
    sample_seed: int = 42,
    force_reprocess: int = 0,
    extra_hash_salt: str = "",
    handle_nans: bool = True,
    nans_threshold: float = 0.33,
    nans_knn: int = 2,
    clip_enable: bool = False,
    clip_method: str = "iqr",
    clip_factor: float = 1.5,
    time_features_enable: bool = True,
    lags_enable: bool = False,
    lags_n: int = 0,
    scaler: str = "MinMaxScaler",
    gateway_url: str = "http://fastapi-app:8000",
    input_bucket: str = "dataset",
    output_bucket: str = "processed-data",
):
    """
    Preprocess raw time-series data into training and inference datasets.
    
    The container image (flts-preprocess:latest) handles the actual preprocessing logic.
    KFP v2 will pass these parameters to the container, which reads them and writes
    outputs to the specified paths.
    """
    pass  # Container handles execution


@dsl.component(
    base_image="train-container:latest",
)
def train_gru_component(
    model: dsl.Output[dsl.Model],
    metrics: dsl.OutputPath(str),
    run_id: dsl.OutputPath(str),
    training_data: dsl.Input[dsl.Dataset] = None,
    config_hash: str = "",
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
    window_size: int = 12,
):
    """
    Train GRU (Gated Recurrent Unit) model for time-series forecasting.
    
    Container: train-container:latest with MODEL_TYPE=GRU env variable.
    """
    pass


@dsl.component(
    base_image="train-container:latest",
)
def train_lstm_component(
    model: dsl.Output[dsl.Model],
    metrics: dsl.OutputPath(str),
    run_id: dsl.OutputPath(str),
    training_data: dsl.Input[dsl.Dataset] = None,
    config_hash: str = "",
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
    window_size: int = 12,
):
    """
    Train LSTM (Long Short-Term Memory) model for time-series forecasting.
    
    Container: train-container:latest with MODEL_TYPE=LSTM env variable.
    """
    pass


@dsl.component(
    base_image="nonml-container:latest",
)
def train_prophet_component(
    model: dsl.Output[dsl.Model],
    metrics: dsl.OutputPath(str),
    run_id: dsl.OutputPath(str),
    training_data: dsl.Input[dsl.Dataset] = None,
    config_hash: str = "",
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    seasonality_mode: str = "multiplicative",
    changepoint_prior_scale: float = 0.05,
    seasonality_prior_scale: float = 10.0,
    holidays_prior_scale: float = 10.0,
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = True,
    daily_seasonality: bool = False,
):
    """
    Train Prophet model for time-series forecasting.
    
    Container: nonml-container:latest with MODEL_TYPE=PROPHET env variable.
    """
    pass


@dsl.component(
    base_image="eval-container:latest",
)
def eval_component(
    promotion_pointer: dsl.Output[dsl.Artifact],
    eval_metadata: dsl.OutputPath(str),
    gru_model: dsl.Input[dsl.Model] = None,
    lstm_model: dsl.Input[dsl.Model] = None,
    prophet_model: dsl.Input[dsl.Model] = None,
    config_hash: str = "",
    identifier: str = "default",
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    promotion_bucket: str = "model-promotion",
    rmse_weight: float = 0.5,
    mae_weight: float = 0.3,
    mse_weight: float = 0.2,
):
    """
    Evaluate all trained models and promote the best one.
    
    Compares GRU, LSTM, and Prophet models using weighted metrics,
    selects the best performer, and writes a promotion pointer artifact.
    """
    pass


@dsl.component(
    base_image="inference-container:latest",
)
def inference_component(
    inference_results: dsl.Output[dsl.Artifact],
    inference_metadata: dsl.OutputPath(str),
    inference_data: dsl.Input[dsl.Dataset] = None,
    promoted_model: dsl.Input[dsl.Artifact] = None,
    identifier: str = "default",
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    inference_log_bucket: str = "inference-logs",
    inference_length: int = 1,
    sample_idx: int = 0,
    enable_microbatch: str = "false",
    batch_size: int = 32,
):
    """
    Run inference using the promoted model.
    
    Loads the best model from the promotion pointer and generates predictions
    on the inference dataset.
    """
    pass


# Smoke test to verify component signatures
if __name__ == "__main__":
    print("KFP v2 Components Smoke Test")
    print("=" * 70)
    
    components = [
        ("preprocess_component", preprocess_component),
        ("train_gru_component", train_gru_component),
        ("train_lstm_component", train_lstm_component),
        ("train_prophet_component", train_prophet_component),
        ("eval_component", eval_component),
        ("inference_component", inference_component),
    ]
    
    for name, comp_func in components:
        # Verify it's a component
        if hasattr(comp_func, 'component_spec'):
            print(f"✓ {name}: Valid KFP v2 component")
        else:
            print(f"✗ {name}: NOT a valid component")
            raise ValueError(f"{name} is not decorated as @dsl.component")
    
    print("=" * 70)
    print(f"✓ All {len(components)} components validated successfully")
