#!/usr/bin/env python
"""
Simple KFP v1 Pipeline Compiler using ContainerOp with add_env_variable.

Bypasses component.yaml loading since those files use an incompatible format.
"""
from pathlib import Path
from kfp import dsl
from kfp.compiler import Compiler
from kubernetes.client.models import V1EnvVar


@dsl.pipeline(
    name='FLTS Time Series Pipeline',
    description='Complete forecasting pipeline: preprocess -> train (3 models) -> eval -> inference'
)
def flts_pipeline(
    dataset_name: str = 'PobleSec',
    identifier: str = 'run-001',
    mlflow_uri: str = 'http://mlflow:5000',
    gateway_url: str = 'http://fastapi-app:8000'
):
    """Simplified FLTS pipeline with essential parameters"""
    
    # Preprocess
    preprocess = dsl.ContainerOp(
        name='preprocess',
        image='flts-preprocess:latest',
        command=['python', 'main.py'],
        file_outputs={
            'training_data': '/tmp/outputs/training_data/data',
            'inference_data': '/tmp/outputs/inference_data/data',
            'config_hash': '/tmp/outputs/config_hash/data'
        }
    )
    preprocess.add_env_variable(V1EnvVar(name='USE_KFP', value='1'))
    preprocess.add_env_variable(V1EnvVar(name='DATASET_NAME', value=dataset_name))
    preprocess.add_env_variable(V1EnvVar(name='GATEWAY_URL', value=gateway_url))
    preprocess.add_env_variable(V1EnvVar(name='KFP_TRAINING_DATA_OUTPUT_PATH', value='/tmp/outputs/training_data/data'))
    preprocess.add_env_variable(V1EnvVar(name='KFP_INFERENCE_DATA_OUTPUT_PATH', value='/tmp/outputs/inference_data/data'))
    preprocess.add_env_variable(V1EnvVar(name='KFP_CONFIG_HASH_OUTPUT_PATH', value='/tmp/outputs/config_hash/data'))
    
    # Train GRU
    gru = dsl.ContainerOp(
        name='train-gru',
        image='train-container:latest',
        file_outputs={'model': '/tmp/outputs/model/data'}
    )
    gru.add_env_variable(V1EnvVar(name='USE_KFP', value='1'))
    gru.add_env_variable(V1EnvVar(name='MODEL_TYPE', value='GRU'))
    gru.add_env_variable(V1EnvVar(name='MLFLOW_TRACKING_URI', value=mlflow_uri))
    gru.add_env_variable(V1EnvVar(name='KFP_TRAINING_DATA_INPUT_PATH', value=preprocess.outputs['training_data']))
    gru.add_env_variable(V1EnvVar(name='KFP_MODEL_OUTPUT_PATH', value='/tmp/outputs/model/data'))
    gru.after(preprocess)
    
    # Train LSTM
    lstm = dsl.ContainerOp(
        name='train-lstm',
        image='train-container:latest',
        file_outputs={'model': '/tmp/outputs/model/data'}
    )
    lstm.add_env_variable(V1EnvVar(name='USE_KFP', value='1'))
    lstm.add_env_variable(V1EnvVar(name='MODEL_TYPE', value='LSTM'))
    lstm.add_env_variable(V1EnvVar(name='MLFLOW_TRACKING_URI', value=mlflow_uri))
    lstm.add_env_variable(V1EnvVar(name='KFP_TRAINING_DATA_INPUT_PATH', value=preprocess.outputs['training_data']))
    lstm.add_env_variable(V1EnvVar(name='KFP_MODEL_OUTPUT_PATH', value='/tmp/outputs/model/data'))
    lstm.after(preprocess)
    
    # Train Prophet
    prophet = dsl.ContainerOp(
        name='train-prophet',
        image='nonml-container:latest',
        file_outputs={'model': '/tmp/outputs/model/data'}
    )
    prophet.add_env_variable(V1EnvVar(name='USE_KFP', value='1'))
    prophet.add_env_variable(V1EnvVar(name='MODEL_TYPE', value='PROPHET'))
    prophet.add_env_variable(V1EnvVar(name='MLFLOW_TRACKING_URI', value=mlflow_uri))
    prophet.add_env_variable(V1EnvVar(name='KFP_TRAINING_DATA_INPUT_PATH', value=preprocess.outputs['training_data']))
    prophet.add_env_variable(V1EnvVar(name='KFP_MODEL_OUTPUT_PATH', value='/tmp/outputs/model/data'))
    prophet.after(preprocess)
    
    # Evaluate
    eval_op = dsl.ContainerOp(
        name='evaluate',
        image='eval-container:latest',
        file_outputs={'promotion': '/tmp/outputs/promotion_pointer/data'}
    )
    eval_op.add_env_variable(V1EnvVar(name='USE_KFP', value='1'))
    eval_op.add_env_variable(V1EnvVar(name='MLFLOW_TRACKING_URI', value=mlflow_uri))
    eval_op.add_env_variable(V1EnvVar(name='KFP_GRU_MODEL_INPUT_PATH', value=gru.outputs['model']))
    eval_op.add_env_variable(V1EnvVar(name='KFP_LSTM_MODEL_INPUT_PATH', value=lstm.outputs['model']))
    eval_op.add_env_variable(V1EnvVar(name='KFP_PROPHET_MODEL_INPUT_PATH', value=prophet.outputs['model']))
    eval_op.add_env_variable(V1EnvVar(name='KFP_PROMOTION_OUTPUT_PATH', value='/tmp/outputs/promotion_pointer/data'))
    eval_op.after(gru, lstm, prophet)
    
    # Inference
    inf = dsl.ContainerOp(
        name='inference',
        image='inference-container:latest',
        command=['python', '-m', 'main'],
        file_outputs={'results': '/tmp/outputs/inference_results/data'}
    )
    inf.add_env_variable(V1EnvVar(name='USE_KFP', value='1'))
    inf.add_env_variable(V1EnvVar(name='MLFLOW_TRACKING_URI', value=mlflow_uri))
    inf.add_env_variable(V1EnvVar(name='KFP_INFERENCE_DATA_INPUT_PATH', value=preprocess.outputs['inference_data']))
    inf.add_env_variable(V1EnvVar(name='KFP_PROMOTED_MODEL_INPUT_PATH', value=eval_op.outputs['promotion']))
    inf.add_env_variable(V1EnvVar(name='KFP_INFERENCE_RESULTS_OUTPUT_PATH', value='/tmp/outputs/inference_results/data'))
    inf.after(eval_op)


if __name__ == '__main__':
    output = Path(__file__).parent / "flts_pipeline.yaml"
    print(f"Compiling to: {output}")
    
    try:
        Compiler().compile(flts_pipeline, str(output))
        size = output.stat().st_size
        print(f"✓ Success: {size:,} bytes")
    except Exception as e:
        print(f"✗ Failed: {e}")
        raise
