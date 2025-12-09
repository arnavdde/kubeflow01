#!/usr/bin/env python
"""
compile_pipeline_v1.py

KFP v1.8.22 Pipeline Compilation using ContainerOp (no YAML loading).

The component.yaml files use a format incompatible with KFP v1.8.22 SDK loading,
so we define components directly in Python using dsl.ContainerOp.

Usage:
    python compile_pipeline_v1.py
"""
import sys
from pathlib import Path
from kfp import dsl
from kfp.compiler import Compiler


@dsl.pipeline(
    name='FLTS Time Series Forecasting Pipeline',
    description='End-to-end time-series forecasting with preprocessing, multi-model training, eval, and inference'
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
    handle_nans: str = 'true',
    nans_threshold: float = 0.33,
    nans_knn: int = 2,
    clip_enable: str = 'false',
    clip_method: str = 'iqr',
    clip_factor: float = 1.5,
    time_features_enable: str = 'true',
    lags_enable: str = 'false',
    lags_n: int = 0,
    scaler: str = 'MinMaxScaler',
    
    # Training parameters
    hidden_size: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 0.001,
    batch_size: int = 32,
    num_epochs: int = 50,
    early_stopping_patience: int = 10,
    window_size: int = 12,
    
    # Prophet parameters
    seasonality_mode: str = "multiplicative",
    changepoint_prior_scale: float = 0.05,
    seasonality_prior_scale: float = 10.0,
    holidays_prior_scale: float = 10.0,
    yearly_seasonality: str = 'true',
    weekly_seasonality: str = 'true',
    daily_seasonality: str = 'false',
    
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
    """FLTS forecasting pipeline using KFP v1 ContainerOp"""
    
    # Step 1: Preprocessing
    preprocess_op = dsl.ContainerOp(
        name='preprocess-data',
        image='flts-preprocess:latest',
        command=['python', 'main.py'],
        file_outputs={
            'training_data': '/tmp/outputs/training_data/data',
            'inference_data': '/tmp/outputs/inference_data/data',
            'config_hash': '/tmp/outputs/config_hash/data',
            'config_json': '/tmp/outputs/config_json/data'
        },
        arguments=[]
    ).set_env_variable('USE_KFP', '1') \
     .set_env_variable('DATASET_NAME', dataset_name) \
     .set_env_variable('IDENTIFIER', identifier) \
     .set_env_variable('SAMPLE_TRAIN_ROWS', sample_train_rows) \
     .set_env_variable('SAMPLE_TEST_ROWS', sample_test_rows) \
     .set_env_variable('SAMPLE_STRATEGY', sample_strategy) \
     .set_env_variable('SAMPLE_SEED', sample_seed) \
     .set_env_variable('FORCE_REPROCESS', force_reprocess) \
     .set_env_variable('EXTRA_HASH_SALT', extra_hash_salt) \
     .set_env_variable('HANDLE_NANS', handle_nans) \
     .set_env_variable('NANS_THRESHOLD', nans_threshold) \
     .set_env_variable('NANS_KNN', nans_knn) \
     .set_env_variable('CLIP_ENABLE', clip_enable) \
     .set_env_variable('CLIP_METHOD', clip_method) \
     .set_env_variable('CLIP_FACTOR', clip_factor) \
     .set_env_variable('TIME_FEATURES_ENABLE', time_features_enable) \
     .set_env_variable('LAGS_ENABLE', lags_enable) \
     .set_env_variable('LAGS_N', lags_n) \
     .set_env_variable('SCALER', scaler) \
     .set_env_variable('GATEWAY_URL', gateway_url) \
     .set_env_variable('INPUT_BUCKET', input_bucket) \
     .set_env_variable('OUTPUT_BUCKET', output_bucket) \
     .set_env_variable('KFP_TRAINING_DATA_OUTPUT_PATH', '/tmp/outputs/training_data/data') \
     .set_env_variable('KFP_INFERENCE_DATA_OUTPUT_PATH', '/tmp/outputs/inference_data/data') \
     .set_env_variable('KFP_CONFIG_HASH_OUTPUT_PATH', '/tmp/outputs/config_hash/data') \
     .set_env_variable('KFP_CONFIG_JSON_OUTPUT_PATH', '/tmp/outputs/config_json/data')
    
    preprocess_op.set_display_name('Preprocess Data')
    
    # Step 2a: Train GRU
    gru_op = dsl.ContainerOp(
        name='train-gru',
        image='train-container:latest',
        file_outputs={
            'model': '/tmp/outputs/model/data',
            'metrics': '/tmp/outputs/metrics/data',
            'run_id': '/tmp/outputs/run_id/data'
        }
    ).set_env_variable('USE_KFP', '1') \
     .set_env_variable('MODEL_TYPE', 'GRU') \
     .set_env_variable('CONFIG_HASH', preprocess_op.outputs['config_hash']) \
     .set_env_variable('MLFLOW_TRACKING_URI', mlflow_tracking_uri) \
     .set_env_variable('MLFLOW_S3_ENDPOINT_URL', mlflow_s3_endpoint) \
     .set_env_variable('GATEWAY_URL', gateway_url) \
     .set_env_variable('HIDDEN_SIZE', hidden_size) \
     .set_env_variable('NUM_LAYERS', num_layers) \
     .set_env_variable('DROPOUT', dropout) \
     .set_env_variable('LEARNING_RATE', learning_rate) \
     .set_env_variable('BATCH_SIZE', batch_size) \
     .set_env_variable('NUM_EPOCHS', num_epochs) \
     .set_env_variable('EARLY_STOPPING_PATIENCE', early_stopping_patience) \
     .set_env_variable('WINDOW_SIZE', window_size) \
     .set_env_variable('KFP_TRAINING_DATA_INPUT_PATH', preprocess_op.outputs['training_data']) \
     .set_env_variable('KFP_MODEL_OUTPUT_PATH', '/tmp/outputs/model/data') \
     .set_env_variable('KFP_METRICS_OUTPUT_PATH', '/tmp/outputs/metrics/data') \
     .set_env_variable('KFP_RUN_ID_OUTPUT_PATH', '/tmp/outputs/run_id/data') \
     .set_env_variable('AWS_ACCESS_KEY_ID', 'minio_access_key') \
     .set_env_variable('AWS_SECRET_ACCESS_KEY', 'minio_secret_key')
    
    gru_op.set_display_name('Train GRU')
    gru_op.after(preprocess_op)
    
    # Step 2b: Train LSTM
    lstm_op = dsl.ContainerOp(
        name='train-lstm',
        image='train-container:latest',
        file_outputs={
            'model': '/tmp/outputs/model/data',
            'metrics': '/tmp/outputs/metrics/data',
            'run_id': '/tmp/outputs/run_id/data'
        }
    ).set_env_variable('USE_KFP', '1') \
     .set_env_variable('MODEL_TYPE', 'LSTM') \
     .set_env_variable('CONFIG_HASH', preprocess_op.outputs['config_hash']) \
     .set_env_variable('MLFLOW_TRACKING_URI', mlflow_tracking_uri) \
     .set_env_variable('MLFLOW_S3_ENDPOINT_URL', mlflow_s3_endpoint) \
     .set_env_variable('GATEWAY_URL', gateway_url) \
     .set_env_variable('HIDDEN_SIZE', hidden_size) \
     .set_env_variable('NUM_LAYERS', num_layers) \
     .set_env_variable('DROPOUT', dropout) \
     .set_env_variable('LEARNING_RATE', learning_rate) \
     .set_env_variable('BATCH_SIZE', batch_size) \
     .set_env_variable('NUM_EPOCHS', num_epochs) \
     .set_env_variable('EARLY_STOPPING_PATIENCE', early_stopping_patience) \
     .set_env_variable('WINDOW_SIZE', window_size) \
     .set_env_variable('KFP_TRAINING_DATA_INPUT_PATH', preprocess_op.outputs['training_data']) \
     .set_env_variable('KFP_MODEL_OUTPUT_PATH', '/tmp/outputs/model/data') \
     .set_env_variable('KFP_METRICS_OUTPUT_PATH', '/tmp/outputs/metrics/data') \
     .set_env_variable('KFP_RUN_ID_OUTPUT_PATH', '/tmp/outputs/run_id/data') \
     .set_env_variable('AWS_ACCESS_KEY_ID', 'minio_access_key') \
     .set_env_variable('AWS_SECRET_ACCESS_KEY', 'minio_secret_key')
    
    lstm_op.set_display_name('Train LSTM')
    lstm_op.after(preprocess_op)
    
    # Step 2c: Train Prophet
    prophet_op = dsl.ContainerOp(
        name='train-prophet',
        image='nonml-container:latest',
        file_outputs={
            'model': '/tmp/outputs/model/data',
            'metrics': '/tmp/outputs/metrics/data',
            'run_id': '/tmp/outputs/run_id/data'
        }
    ).set_env_variable('USE_KFP', '1') \
     .set_env_variable('MODEL_TYPE', 'PROPHET') \
     .set_env_variable('CONFIG_HASH', preprocess_op.outputs['config_hash']) \
     .set_env_variable('MLFLOW_TRACKING_URI', mlflow_tracking_uri) \
     .set_env_variable('MLFLOW_S3_ENDPOINT_URL', mlflow_s3_endpoint) \
     .set_env_variable('GATEWAY_URL', gateway_url) \
     .set_env_variable('SEASONALITY_MODE', seasonality_mode) \
     .set_env_variable('CHANGEPOINT_PRIOR_SCALE', changepoint_prior_scale) \
     .set_env_variable('SEASONALITY_PRIOR_SCALE', seasonality_prior_scale) \
     .set_env_variable('HOLIDAYS_PRIOR_SCALE', holidays_prior_scale) \
     .set_env_variable('DAILY_SEASONALITY', daily_seasonality) \
     .set_env_variable('WEEKLY_SEASONALITY', weekly_seasonality) \
     .set_env_variable('YEARLY_SEASONALITY', yearly_seasonality) \
     .set_env_variable('KFP_TRAINING_DATA_INPUT_PATH', preprocess_op.outputs['training_data']) \
     .set_env_variable('KFP_MODEL_OUTPUT_PATH', '/tmp/outputs/model/data') \
     .set_env_variable('KFP_METRICS_OUTPUT_PATH', '/tmp/outputs/metrics/data') \
     .set_env_variable('KFP_RUN_ID_OUTPUT_PATH', '/tmp/outputs/run_id/data') \
     .set_env_variable('AWS_ACCESS_KEY_ID', 'minio_access_key') \
     .set_env_variable('AWS_SECRET_ACCESS_KEY', 'minio_secret_key')
    
    prophet_op.set_display_name('Train Prophet')
    prophet_op.after(preprocess_op)
    
    # Step 3: Evaluation
    eval_op = dsl.ContainerOp(
        name='evaluate-models',
        image='eval-container:latest',
        file_outputs={
            'promotion_pointer': '/tmp/outputs/promotion_pointer/data',
            'eval_metadata': '/tmp/outputs/eval_metadata/data'
        }
    ).set_env_variable('USE_KFP', '1') \
     .set_env_variable('CONFIG_HASH', preprocess_op.outputs['config_hash']) \
     .set_env_variable('IDENTIFIER', identifier) \
     .set_env_variable('MLFLOW_TRACKING_URI', mlflow_tracking_uri) \
     .set_env_variable('MLFLOW_S3_ENDPOINT_URL', mlflow_s3_endpoint) \
     .set_env_variable('GATEWAY_URL', gateway_url) \
     .set_env_variable('PROMOTION_BUCKET', promotion_bucket) \
     .set_env_variable('SCORE_WEIGHTS', f'{{"rmse": {rmse_weight}, "mae": {mae_weight}, "mse": {mse_weight}}}') \
     .set_env_variable('KFP_GRU_MODEL_INPUT_PATH', gru_op.outputs['model']) \
     .set_env_variable('KFP_LSTM_MODEL_INPUT_PATH', lstm_op.outputs['model']) \
     .set_env_variable('KFP_PROPHET_MODEL_INPUT_PATH', prophet_op.outputs['model']) \
     .set_env_variable('KFP_PROMOTION_OUTPUT_PATH', '/tmp/outputs/promotion_pointer/data') \
     .set_env_variable('KFP_EVAL_METADATA_OUTPUT_PATH', '/tmp/outputs/eval_metadata/data') \
     .set_env_variable('AWS_ACCESS_KEY_ID', 'minio_access_key') \
     .set_env_variable('AWS_SECRET_ACCESS_KEY', 'minio_secret_key')
    
    eval_op.set_display_name('Evaluate & Promote Best Model')
    eval_op.after(gru_op, lstm_op, prophet_op)
    
    # Step 4: Inference
    inference_op = dsl.ContainerOp(
        name='run-inference',
        image='inference-container:latest',
        command=['python', '-m', 'main'],
        file_outputs={
            'inference_results': '/tmp/outputs/inference_results/data',
            'inference_metadata': '/tmp/outputs/inference_metadata/data'
        }
    ).set_env_variable('USE_KFP', '1') \
     .set_env_variable('IDENTIFIER', identifier) \
     .set_env_variable('MLFLOW_TRACKING_URI', mlflow_tracking_uri) \
     .set_env_variable('MLFLOW_S3_ENDPOINT_URL', mlflow_s3_endpoint) \
     .set_env_variable('GATEWAY_URL', gateway_url) \
     .set_env_variable('INFERENCE_LOG_BUCKET', inference_log_bucket) \
     .set_env_variable('INFERENCE_LENGTH', inference_length) \
     .set_env_variable('SAMPLE_IDX', sample_idx) \
     .set_env_variable('ENABLE_MICROBATCH', enable_microbatch) \
     .set_env_variable('BATCH_SIZE', inference_batch_size) \
     .set_env_variable('KFP_INFERENCE_DATA_INPUT_PATH', preprocess_op.outputs['inference_data']) \
     .set_env_variable('KFP_PROMOTED_MODEL_INPUT_PATH', eval_op.outputs['promotion_pointer']) \
     .set_env_variable('KFP_INFERENCE_RESULTS_OUTPUT_PATH', '/tmp/outputs/inference_results/data') \
     .set_env_variable('KFP_INFERENCE_METADATA_OUTPUT_PATH', '/tmp/outputs/inference_metadata/data') \
     .set_env_variable('AWS_ACCESS_KEY_ID', 'minio_access_key') \
     .set_env_variable('AWS_SECRET_ACCESS_KEY', 'minio_secret_key') \
     .set_env_variable('AWS_DEFAULT_REGION', 'us-east-1') \
     .set_env_variable('DISABLE_BUCKET_ENSURE', '0') \
     .set_env_variable('DISABLE_STARTUP_INFERENCE', '1')
    
    inference_op.set_display_name('Run Inference')
    inference_op.after(eval_op)


def main():
    """Compile the pipeline to YAML"""
    output_file = Path(__file__).parent / "flts_pipeline.yaml"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("FLTS Pipeline Compilation (KFP v1.8.22)")
    print("="*70)
    print(f"\nCompiling pipeline to: {output_file}\n")
    
    try:
        Compiler().compile(
            pipeline_func=flts_pipeline,
            package_path=str(output_file)
        )
        
        if output_file.exists():
            size = output_file.stat().st_size
            print("="*70)
            print(f"✓ SUCCESS: Pipeline YAML generated")
            print(f"  Location: {output_file}")
            print(f"  Size: {size:,} bytes")
            print("="*70)
            print("\nNext steps:")
            print("  1. Review the YAML file")
            print("  2. Upload to Kubeflow Pipelines")
            print("  3. Create a pipeline run")
            return 0
        else:
            print("ERROR: Compilation succeeded but file not found")
            return 1
            
    except Exception as e:
        print(f"ERROR: Compilation failed")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
