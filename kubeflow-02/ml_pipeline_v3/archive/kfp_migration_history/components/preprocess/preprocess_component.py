"""Kubeflow Pipelines v2 component for FLTS preprocessing.

This module provides a Python-based component wrapper that loads the
container-based component definition from component.yaml.

Usage:
    from kubeflow_pipeline.components.preprocess.preprocess_component import preprocess_component
    
    @dsl.pipeline(name='flts-pipeline')
    def my_pipeline():
        preprocess_task = preprocess_component(
            dataset_name='PobleSec',
            identifier='run-001',
            sample_train_rows=50
        )
"""
from typing import NamedTuple
from kfp import dsl
from kfp.dsl import component, Dataset, Input, Output
import os


# Load the container-based component from YAML
_COMPONENT_YAML_PATH = os.path.join(os.path.dirname(__file__), 'component.yaml')


@component(
    base_image='flts-preprocess:latest',
    packages_to_install=[]  # All dependencies in base image
)
def preprocess_component(
    dataset_name: str,
    identifier: str,
    training_data: Output[Dataset],
    inference_data: Output[Dataset],
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
):
    """Preprocess raw time-series data into training and inference datasets.
    
    This component wraps the existing preprocess_container with USE_KFP=1 flag,
    replacing Kafka producer calls with KFP artifact writes.
    
    Args:
        dataset_name: Name of the dataset (e.g., 'PobleSec')
        identifier: Run identifier for lineage tracking
        training_data: Output dataset artifact (training Parquet)
        inference_data: Output dataset artifact (test Parquet)
        sample_train_rows: Number of training rows to sample (0=all)
        sample_test_rows: Number of test rows to sample (0=all)
        sample_strategy: Sampling strategy ('head' or 'random')
        sample_seed: Random seed for reproducible sampling
        force_reprocess: Force reprocessing even if cached (1=force)
        extra_hash_salt: Salt to force new config hash
        handle_nans: Enable NaN handling
        nans_threshold: NaN threshold for column dropping
        nans_knn: KNN window for imputation
        clip_enable: Enable outlier clipping
        clip_method: Clipping method ('iqr' or 'percentile')
        clip_factor: IQR multiplier for outlier detection
        time_features_enable: Enable time-based features
        lags_enable: Enable lag features
        lags_n: Number of lag steps
        scaler: Scaler method (MinMaxScaler, StandardScaler, etc.)
        gateway_url: MinIO gateway URL
        input_bucket: Input bucket for raw CSV files
        output_bucket: Output bucket for Parquet files
    
    Returns:
        Tuple of (config_hash: str, config_json: str)
    """
    import os
    import json
    import subprocess
    from collections import namedtuple
    
    # Set environment variables for the container
    env = os.environ.copy()
    env.update({
        'USE_KFP': '1',
        'DATASET_NAME': dataset_name,
        'IDENTIFIER': identifier,
        'SAMPLE_TRAIN_ROWS': str(sample_train_rows),
        'SAMPLE_TEST_ROWS': str(sample_test_rows),
        'SAMPLE_STRATEGY': sample_strategy,
        'SAMPLE_SEED': str(sample_seed),
        'FORCE_REPROCESS': str(force_reprocess),
        'EXTRA_HASH_SALT': extra_hash_salt,
        'HANDLE_NANS': str(handle_nans).lower(),
        'NANS_THRESHOLD': str(nans_threshold),
        'NANS_KNN': str(nans_knn),
        'CLIP_ENABLE': str(clip_enable).lower(),
        'CLIP_METHOD': clip_method,
        'CLIP_FACTOR': str(clip_factor),
        'TIME_FEATURES_ENABLE': str(time_features_enable).lower(),
        'LAGS_ENABLE': str(lags_enable).lower(),
        'LAGS_N': str(lags_n),
        'SCALER': scaler,
        'GATEWAY_URL': gateway_url,
        'INPUT_BUCKET': input_bucket,
        'OUTPUT_BUCKET': output_bucket,
        'KFP_TRAINING_DATA_OUTPUT_PATH': training_data.path,
        'KFP_INFERENCE_DATA_OUTPUT_PATH': inference_data.path,
        'KFP_CONFIG_HASH_OUTPUT_PATH': '/tmp/config_hash.txt',
        'KFP_CONFIG_JSON_OUTPUT_PATH': '/tmp/config_json.txt'
    })
    
    # Run the preprocessing logic (import from existing module)
    # Note: In actual execution, this runs inside the container
    from preprocess_container.main import run_preprocess
    run_preprocess()
    
    # Read outputs
    with open('/tmp/config_hash.txt', 'r') as f:
        config_hash = f.read().strip()
    
    with open('/tmp/config_json.txt', 'r') as f:
        config_json = f.read().strip()
    
    # KFP will automatically populate training_data and inference_data artifacts
    # from the paths written by _write_kfp_artifacts()
    
    PreprocessOutputs = namedtuple('PreprocessOutputs', ['config_hash', 'config_json'])
    
    return PreprocessOutputs(config_hash=config_hash, config_json=config_json)


def load_component_from_yaml():
    """Load the container-based component from YAML file.
    
    This is an alternative to the @component decorator for cases where
    you want to use the pure YAML definition.
    
    Returns:
        ComponentSpec loaded from component.yaml
    """
    from kfp.components import load_component_from_file
    return load_component_from_file(_COMPONENT_YAML_PATH)


# For backwards compatibility, expose both the decorator-based and YAML-based components
preprocess_component_yaml = load_component_from_yaml
