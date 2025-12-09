"""
FLTS (Forecasting Load Time Series) - Complete KFP v2 Pipeline

This pipeline orchestrates a full end-to-end time-series forecasting workflow:
1. Preprocess: Load raw CSV data, apply transformations, output training/inference datasets
2. Train (parallel): Train 3 models simultaneously (GRU, LSTM, Prophet)
3. Evaluate: Compare all models, select best performer, promote to production
4. Inference: Run forecasting using promoted model, write results to MinIO

All components use MinIO for artifact storage and MLflow for model tracking.
"""

from kfp import dsl
from kfp.dsl import (
    Dataset,
    Input,
    Output,
    Model,
    Artifact,
    PipelineTask
)
from typing import NamedTuple


# ============================================================================
# Component Definitions (loaded from component.yaml files)
# ============================================================================

@dsl.component_decorator
def preprocess_component(
    dataset_name: str,
    identifier: str,
    sample_train_rows: int = 0,
    sample_test_rows: int = 0,
    sample_strategy: str = 'head',
    sample_seed: int = 42,
    force_reprocess: int = 0,
    extra_hash_salt: str = '',
    handle_nans: bool = True,
    nans_threshold: float = 0.33,
    nans_knn: int = 2,
    clip_enable: bool = False,
    clip_method: str = 'iqr',
    clip_factor: float = 1.5,
    time_features_enable: bool = True,
    lags_enable: bool = False,
    lags_n: int = 0,
    scaler: str = 'MinMaxScaler',
    gateway_url: str = 'http://fastapi-app:8000',
    input_bucket: str = 'dataset',
    output_bucket: str = 'processed-data',
    training_data: Output[Dataset],
    inference_data: Output[Dataset],
    config_hash: dsl.OutputPath(str),
    config_json: dsl.OutputPath(str)
):
    """Preprocess component stub - actual implementation loaded from component.yaml"""
    pass


@dsl.component_decorator
def train_gru_component(
    training_data: Input[Dataset],
    config_hash: str,
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
    model: Output[Model],
    metrics: Output[Artifact],
    run_id: dsl.OutputPath(str)
):
    """Train GRU component stub - actual implementation loaded from component.yaml"""
    pass


@dsl.component_decorator
def train_lstm_component(
    training_data: Input[Dataset],
    config_hash: str,
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
    model: Output[Model],
    metrics: Output[Artifact],
    run_id: dsl.OutputPath(str)
):
    """Train LSTM component stub - actual implementation loaded from component.yaml"""
    pass


@dsl.component_decorator
def train_prophet_component(
    training_data: Input[Dataset],
    config_hash: str,
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
    model: Output[Model],
    metrics: Output[Artifact],
    run_id: dsl.OutputPath(str)
):
    """Train Prophet component stub - actual implementation loaded from component.yaml"""
    pass


@dsl.component_decorator
def eval_component(
    gru_model: Input[Model],
    lstm_model: Input[Model],
    prophet_model: Input[Model],
    config_hash: str,
    identifier: str = "",
    mlflow_tracking_uri: str = "http://mlflow:5000",
    mlflow_s3_endpoint: str = "http://minio:9000",
    gateway_url: str = "http://fastapi-app:8000",
    promotion_bucket: str = "model-promotion",
    rmse_weight: float = 0.5,
    mae_weight: float = 0.3,
    mse_weight: float = 0.2,
    promotion_pointer: Output[Artifact],
    eval_metadata: Output[Artifact]
):
    """Eval component stub - actual implementation loaded from component.yaml"""
    pass


@dsl.component_decorator
def inference_component(
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
    inference_results: Output[Artifact],
    inference_metadata: Output[Artifact]
):
    """Inference component stub - actual implementation loaded from component.yaml"""
    pass


# ============================================================================
# Main Pipeline Definition
# ============================================================================

@dsl.pipeline(
    name='FLTS Time Series Forecasting Pipeline',
    description='''
    End-to-end time-series forecasting pipeline with preprocessing, multi-model training,
    evaluation, and inference. Uses MinIO for artifact storage and MLflow for model tracking.
    
    Architecture:
    1. Preprocess → [Training Data, Inference Data]
    2. [GRU Training, LSTM Training, Prophet Training] (parallel) → [3 Models]
    3. Eval → [Promoted Model]
    4. Inference → [Predictions]
    ''',
    pipeline_root='minio://kubeflow-pipelines'
)
def flts_pipeline(
    # Preprocessing parameters
    dataset_name: str = 'PobleSec',
    identifier: str = 'flts-run-001',
    sample_train_rows: int = 0,
    sample_test_rows: int = 0,
    sample_strategy: str = 'head',
    sample_seed: int = 42,
    force_reprocess: int = 0,
    extra_hash_salt: str = '',
    handle_nans: bool = True,
    nans_threshold: float = 0.33,
    nans_knn: int = 2,
    clip_enable: bool = False,
    clip_method: str = 'iqr',
    clip_factor: float = 1.5,
    time_features_enable: bool = True,
    lags_enable: bool = False,
    lags_n: int = 0,
    scaler: str = 'MinMaxScaler',
    
    # Training parameters (shared across all models)
    hidden_size: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 0.001,
    batch_size: int = 32,
    num_epochs: int = 50,
    early_stopping_patience: int = 10,
    window_size: int = 12,
    
    # Prophet-specific parameters
    seasonality_mode: str = "multiplicative",
    changepoint_prior_scale: float = 0.05,
    seasonality_prior_scale: float = 10.0,
    holidays_prior_scale: float = 10.0,
    yearly_seasonality: bool = True,
    weekly_seasonality: bool = True,
    daily_seasonality: bool = False,
    
    # Evaluation parameters
    rmse_weight: float = 0.5,
    mae_weight: float = 0.3,
    mse_weight: float = 0.2,
    
    # Inference parameters
    inference_length: int = 1,
    sample_idx: int = 0,
    enable_microbatch: str = "false",
    inference_batch_size: int = 32,
    
    # Infrastructure parameters
    gateway_url: str = 'http://fastapi-app:8000',
    mlflow_tracking_uri: str = 'http://mlflow:5000',
    mlflow_s3_endpoint: str = 'http://minio:9000',
    input_bucket: str = 'dataset',
    output_bucket: str = 'processed-data',
    promotion_bucket: str = 'model-promotion',
    inference_log_bucket: str = 'inference-logs'
):
    """
    Complete FLTS forecasting pipeline.
    
    Args:
        dataset_name: Name of dataset to process (e.g., 'PobleSec', 'ElBorn')
        identifier: Unique run identifier for lineage tracking
        sample_train_rows: Number of training rows to sample (0=all)
        sample_test_rows: Number of test rows to sample (0=all)
        ... (see parameter list above for full documentation)
    
    Returns:
        Pipeline execution results with all artifacts stored in MinIO
    """
    
    # ========================================================================
    # Step 1: Preprocessing
    # ========================================================================
    
    preprocess_task = preprocess_component(
        dataset_name=dataset_name,
        identifier=identifier,
        sample_train_rows=sample_train_rows,
        sample_test_rows=sample_test_rows,
        sample_strategy=sample_strategy,
        sample_seed=sample_seed,
        force_reprocess=force_reprocess,
        extra_hash_salt=extra_hash_salt,
        handle_nans=handle_nans,
        nans_threshold=nans_threshold,
        nans_knn=nans_knn,
        clip_enable=clip_enable,
        clip_method=clip_method,
        clip_factor=clip_factor,
        time_features_enable=time_features_enable,
        lags_enable=lags_enable,
        lags_n=lags_n,
        scaler=scaler,
        gateway_url=gateway_url,
        input_bucket=input_bucket,
        output_bucket=output_bucket
    )
    preprocess_task.set_display_name('Preprocess Data')
    preprocess_task.set_caching_options(False)  # Force execution for consistent timestamps
    
    # ========================================================================
    # Step 2: Parallel Model Training (GRU, LSTM, Prophet)
    # ========================================================================
    
    # Train GRU
    gru_train_task = train_gru_component(
        training_data=preprocess_task.outputs['training_data'],
        config_hash=preprocess_task.outputs['config_hash'],
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_s3_endpoint=mlflow_s3_endpoint,
        gateway_url=gateway_url,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        batch_size=batch_size,
        num_epochs=num_epochs,
        early_stopping_patience=early_stopping_patience,
        window_size=window_size
    )
    gru_train_task.set_display_name('Train GRU Model')
    gru_train_task.after(preprocess_task)
    
    # Train LSTM
    lstm_train_task = train_lstm_component(
        training_data=preprocess_task.outputs['training_data'],
        config_hash=preprocess_task.outputs['config_hash'],
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_s3_endpoint=mlflow_s3_endpoint,
        gateway_url=gateway_url,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        batch_size=batch_size,
        num_epochs=num_epochs,
        early_stopping_patience=early_stopping_patience,
        window_size=window_size
    )
    lstm_train_task.set_display_name('Train LSTM Model')
    lstm_train_task.after(preprocess_task)
    
    # Train Prophet
    prophet_train_task = train_prophet_component(
        training_data=preprocess_task.outputs['training_data'],
        config_hash=preprocess_task.outputs['config_hash'],
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_s3_endpoint=mlflow_s3_endpoint,
        gateway_url=gateway_url,
        seasonality_mode=seasonality_mode,
        changepoint_prior_scale=changepoint_prior_scale,
        seasonality_prior_scale=seasonality_prior_scale,
        holidays_prior_scale=holidays_prior_scale,
        yearly_seasonality=yearly_seasonality,
        weekly_seasonality=weekly_seasonality,
        daily_seasonality=daily_seasonality
    )
    prophet_train_task.set_display_name('Train Prophet Model')
    prophet_train_task.after(preprocess_task)
    
    # ========================================================================
    # Step 3: Model Evaluation and Selection
    # ========================================================================
    
    eval_task = eval_component(
        gru_model=gru_train_task.outputs['model'],
        lstm_model=lstm_train_task.outputs['model'],
        prophet_model=prophet_train_task.outputs['model'],
        config_hash=preprocess_task.outputs['config_hash'],
        identifier=identifier,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_s3_endpoint=mlflow_s3_endpoint,
        gateway_url=gateway_url,
        promotion_bucket=promotion_bucket,
        rmse_weight=rmse_weight,
        mae_weight=mae_weight,
        mse_weight=mse_weight
    )
    eval_task.set_display_name('Evaluate & Select Best Model')
    eval_task.after(gru_train_task, lstm_train_task, prophet_train_task)
    
    # ========================================================================
    # Step 4: Inference with Promoted Model
    # ========================================================================
    
    inference_task = inference_component(
        inference_data=preprocess_task.outputs['inference_data'],
        promoted_model=eval_task.outputs['promotion_pointer'],
        identifier=identifier,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_s3_endpoint=mlflow_s3_endpoint,
        gateway_url=gateway_url,
        inference_log_bucket=inference_log_bucket,
        inference_length=inference_length,
        sample_idx=sample_idx,
        enable_microbatch=enable_microbatch,
        batch_size=inference_batch_size
    )
    inference_task.set_display_name('Run Inference')
    inference_task.after(eval_task)


# ============================================================================
# Helper Functions
# ============================================================================

def create_lightweight_pipeline(
    dataset_name: str = 'PobleSec',
    identifier: str = 'flts-lightweight-001',
    sample_train_rows: int = 1000,
    sample_test_rows: int = 100,
    num_epochs: int = 10
):
    """
    Create a lightweight version of the pipeline for fast testing/development.
    Reduces data size and training epochs for quick validation.
    """
    return flts_pipeline(
        dataset_name=dataset_name,
        identifier=identifier,
        sample_train_rows=sample_train_rows,
        sample_test_rows=sample_test_rows,
        num_epochs=num_epochs,
        early_stopping_patience=3
    )


if __name__ == '__main__':
    # This allows the pipeline to be compiled from command line
    print("FLTS Pipeline defined successfully.")
    print("Use compile_pipeline.py to generate the pipeline.job.yaml file.")
