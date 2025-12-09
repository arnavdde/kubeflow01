"""
Pipeline Compilation Script for FLTS KFP v2 Pipeline

This script compiles the Python pipeline definition into a YAML specification
that can be uploaded to Kubeflow Pipelines UI for execution.

Usage:
    # Compile with default settings
    python compile_pipeline.py
    
    # Compile with custom output file
    python compile_pipeline.py --output custom_pipeline.yaml
    
    # Compile lightweight version for testing
    python compile_pipeline.py --lightweight
    
    # Specify component directory
    python compile_pipeline.py --components-dir ./components
"""

import argparse
import sys
from pathlib import Path
from kfp import components
from kfp import compiler as kfp_compiler
from kfp import dsl


def load_components_from_yaml(components_dir: Path):
    """
    Load all component definitions from YAML files (KFP v1).
    
    Args:
        components_dir: Path to directory containing component subdirectories
        
    Returns:
        dict: Component name -> loaded component function
    """
    comps = {}
    
    component_names = [
        'preprocess',
        'train_gru',
        'train_lstm',
        'train_prophet',
        'eval',
        'inference'
    ]
    
    for name in component_names:
        component_path = components_dir / name / 'component.yaml'
        if not component_path.exists():
            raise FileNotFoundError(
                f"Component definition not found: {component_path}\n"
                f"Expected structure: {components_dir}/{name}/component.yaml"
            )
        
        print(f"Loading component: {name} from {component_path}")
        comps[name] = components.load_component_from_file(str(component_path))
    
    return comps


def build_pipeline(components: dict):
    """
    Build the complete pipeline using loaded components.
    
    Args:
        components: dict of loaded component functions
        
    Returns:
        Pipeline function ready for compilation
    """
    
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
        """Complete FLTS forecasting pipeline"""
        
        # Step 1: Preprocessing
        preprocess_task = components['preprocess'](
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
        preprocess_task.set_caching_options(False)
        
        # Step 2: Parallel Training
        gru_train_task = components['train_gru'](
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
        
        lstm_train_task = components['train_lstm'](
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
        
        prophet_train_task = components['train_prophet'](
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
        
        # Step 3: Evaluation
        eval_task = components['eval'](
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
        
        # Step 4: Inference
        inference_task = components['inference'](
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
    
    return flts_pipeline


def compile_pipeline(
    components_dir: Path,
    output_file: Path,
    lightweight: bool = False
):
    """
    Compile the pipeline to YAML format.
    
    Args:
        components_dir: Directory containing component YAML definitions
        output_file: Output YAML file path
        lightweight: If True, compile with reduced parameters for testing
    """
    print(f"\n{'='*70}")
    print("FLTS Pipeline Compilation")
    print(f"{'='*70}\n")
    
    # Load components
    print("Step 1: Loading component definitions...")
    components = load_components_from_yaml(components_dir)
    print(f"✓ Loaded {len(components)} components\n")
    
    # Build pipeline
    print("Step 2: Building pipeline definition...")
    pipeline_func = build_pipeline(components)
    print("✓ Pipeline structure created\n")
    
    # Compile to YAML
    print(f"Step 3: Compiling to {output_file}...")
    try:
        kfp_compiler.Compiler().compile(
            pipeline_func=pipeline_func,
            package_path=str(output_file)
        )
        print(f"✓ Pipeline compiled successfully\n")
    except Exception as e:
        print(f"✗ Compilation failed: {e}\n")
        raise
    
    # Verify output
    if output_file.exists():
        file_size = output_file.stat().st_size
        print(f"{'='*70}")
        print(f"✓ SUCCESS: Pipeline YAML created")
        print(f"  File: {output_file}")
        print(f"  Size: {file_size:,} bytes")
        print(f"{'='*70}\n")
        print("Next steps:")
        print("  1. Review the generated YAML file")
        print("  2. Upload to Kubeflow Pipelines UI")
        print("  3. Create a run with desired parameters")
        print("  4. Monitor execution in KFP dashboard\n")
    else:
        raise RuntimeError("Compilation succeeded but output file not found")


def main():
    parser = argparse.ArgumentParser(
        description='Compile FLTS KFP v2 Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Standard compilation
  python compile_pipeline.py
  
  # Custom output location
  python compile_pipeline.py -o /tmp/my_pipeline.yaml
  
  # Specify components directory
  python compile_pipeline.py -c ./components
  
  # Lightweight for testing
  python compile_pipeline.py --lightweight
        '''
    )
    
    parser.add_argument(
        '-c', '--components-dir',
        type=Path,
        default=Path(__file__).parent / 'components',
        help='Directory containing component YAML files (default: ./components)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path(__file__).parent / 'pipeline.job.yaml',
        help='Output YAML file path (default: ./pipeline.job.yaml)'
    )
    
    parser.add_argument(
        '--lightweight',
        action='store_true',
        help='Compile lightweight version with reduced parameters for testing'
    )
    
    args = parser.parse_args()
    
    # Validate components directory
    if not args.components_dir.exists():
        print(f"ERROR: Components directory not found: {args.components_dir}")
        print(f"Expected structure:")
        print(f"  {args.components_dir}/")
        print(f"    preprocess/component.yaml")
        print(f"    train_gru/component.yaml")
        print(f"    train_lstm/component.yaml")
        print(f"    train_prophet/component.yaml")
        print(f"    eval/component.yaml")
        print(f"    inference/component.yaml")
        sys.exit(1)
    
    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Compile
    try:
        compile_pipeline(
            components_dir=args.components_dir,
            output_file=args.output,
            lightweight=args.lightweight
        )
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
