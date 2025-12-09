"""
KFP v2 Pipeline Definition for FLTS Time-Series Forecasting

This module defines the complete DAG using KFP v2 DSL and the components
from components_v2.py.

Pipeline Flow:
1. Preprocess → splits data into training and inference datasets
2. Train (parallel) → GRU, LSTM, Prophet models trained simultaneously
3. Evaluate → selects best model based on weighted metrics
4. Inference → generates predictions using the promoted model

Usage:
    # Compile pipeline
    python pipeline_v2.py
    
    # Or use the dedicated compiler
    python compile_pipeline_v2.py --output artifacts/flts_pipeline_v2.json
"""

from kfp import dsl, compiler
from kubeflow_pipeline.components_v2 import (
    preprocess_component,
    train_gru_component,
    train_lstm_component,
    train_prophet_component,
    eval_component,
    inference_component,
)


@dsl.pipeline(
    name="flts-time-series-pipeline",
    description="End-to-end FLTS pipeline in KFP v2 (preprocess → train → eval → inference)",
)
def flts_pipeline(
    # Preprocessing parameters
    dataset_name: str = "PobleSec",
    identifier: str = "default-run",
    sample_train_rows: int = 0,
    sample_test_rows: int = 0,
    
    # Training hyperparameters
    hidden_size: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 0.001,
    batch_size: int = 32,
    num_epochs: int = 50,
    
    # Infrastructure
    gateway_url: str = "http://fastapi-app:8000",
    mlflow_tracking_uri: str = "http://mlflow:5000",
):
    """
    Complete FLTS forecasting pipeline using KFP v2.
    
    Args:
        dataset_name: Name of dataset to process (e.g., 'PobleSec')
        identifier: Unique run identifier for tracking
        sample_train_rows: Number of training rows to sample (0=all)
        sample_test_rows: Number of test rows to sample (0=all)
        hidden_size: Hidden layer size for neural models
        num_layers: Number of layers for neural models
        dropout: Dropout rate for neural models
        learning_rate: Learning rate for training
        batch_size: Training batch size
        num_epochs: Number of training epochs
        gateway_url: FastAPI gateway URL for MinIO
        mlflow_tracking_uri: MLflow tracking server URL
    """
    
    # Step 1: Preprocessing
    preproc_task = preprocess_component(
        dataset_name=dataset_name,
        identifier=identifier,
        sample_train_rows=sample_train_rows,
        sample_test_rows=sample_test_rows,
        gateway_url=gateway_url,
    )
    preproc_task.set_display_name("Preprocess Data")
    
    # Step 2: Parallel training of three models
    gru_task = train_gru_component(
        training_data=preproc_task.outputs["training_data"],
        config_hash=preproc_task.outputs["config_hash"],
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        batch_size=batch_size,
        num_epochs=num_epochs,
    )
    gru_task.set_display_name("Train GRU Model")
    
    lstm_task = train_lstm_component(
        training_data=preproc_task.outputs["training_data"],
        config_hash=preproc_task.outputs["config_hash"],
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url,
        hidden_size=hidden_size,
        num_layers=num_layers,
        dropout=dropout,
        learning_rate=learning_rate,
        batch_size=batch_size,
        num_epochs=num_epochs,
    )
    lstm_task.set_display_name("Train LSTM Model")
    
    prophet_task = train_prophet_component(
        training_data=preproc_task.outputs["training_data"],
        config_hash=preproc_task.outputs["config_hash"],
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url,
    )
    prophet_task.set_display_name("Train Prophet Model")
    
    # Step 3: Evaluation (waits for all 3 training tasks)
    eval_task = eval_component(
        gru_model=gru_task.outputs["model"],
        lstm_model=lstm_task.outputs["model"],
        prophet_model=prophet_task.outputs["model"],
        config_hash=preproc_task.outputs["config_hash"],
        identifier=identifier,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url,
    )
    eval_task.set_display_name("Evaluate & Promote Best Model")
    
    # Step 4: Inference (waits for eval)
    inference_task = inference_component(
        inference_data=preproc_task.outputs["inference_data"],
        promoted_model=eval_task.outputs["promotion_pointer"],
        identifier=identifier,
        mlflow_tracking_uri=mlflow_tracking_uri,
        gateway_url=gateway_url,
    )
    inference_task.set_display_name("Run Inference")


# Simple main guard for testing compilation
if __name__ == "__main__":
    print("=" * 70)
    print("KFP v2 Pipeline Compilation Test")
    print("=" * 70)
    print()
    
    output_path = "flts_pipeline_v2_test.json"
    print(f"Compiling pipeline to: {output_path}")
    
    try:
        compiler.Compiler().compile(
            pipeline_func=flts_pipeline,
            package_path=output_path,
        )
        
        import os
        size = os.path.getsize(output_path)
        print(f"✓ Compilation successful")
        print(f"✓ Output: {output_path} ({size:,} bytes)")
        print()
        print("=" * 70)
        print("Pipeline ready for deployment")
        print("=" * 70)
        
    except Exception as e:
        print(f"✗ Compilation failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
