"""
KFP v2 Runtime Configuration Defaults

Centralized configuration for in-cluster service endpoints and credentials.
Values can be overridden via environment variables or pipeline parameters.

Usage:
    from kubeflow_pipeline.config.runtime_defaults import RuntimeConfig
    
    config = RuntimeConfig()
    print(config.minio_endpoint)  # "minio-service.default.svc.cluster.local:9000"
    
    # Override via env vars
    import os
    os.environ["MINIO_ENDPOINT"] = "custom-minio:9000"
    config = RuntimeConfig()
    print(config.minio_endpoint)  # "custom-minio:9000"
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuntimeConfig:
    """
    Runtime configuration for KFP v2 pipeline execution in-cluster.
    
    All values have defaults suitable for development/Minikube deployment.
    Override via environment variables or pass to pipeline parameters.
    """
    
    # ========================================================================
    # MinIO Configuration
    # ========================================================================
    
    minio_endpoint: str = os.getenv(
        "MINIO_ENDPOINT",
        "minio-service.default.svc.cluster.local:9000"
    )
    
    minio_access_key: str = os.getenv(
        "MINIO_ACCESS_KEY",
        "minioadmin"
    )
    
    minio_secret_key: str = os.getenv(
        "MINIO_SECRET_KEY",
        "minioadmin"
    )
    
    minio_secure: bool = os.getenv(
        "MINIO_SECURE",
        "false"
    ).lower() == "true"
    
    # ========================================================================
    # MLflow Configuration
    # ========================================================================
    
    mlflow_tracking_uri: str = os.getenv(
        "MLFLOW_TRACKING_URI",
        "http://mlflow.default.svc.cluster.local:5000"
    )
    
    mlflow_s3_endpoint_url: str = os.getenv(
        "MLFLOW_S3_ENDPOINT_URL",
        "http://minio-service.default.svc.cluster.local:9000"
    )
    
    # ========================================================================
    # FastAPI Gateway Configuration
    # ========================================================================
    
    gateway_url: str = os.getenv(
        "GATEWAY_URL",
        "http://fastapi-app.default.svc.cluster.local:8000"
    )
    
    # ========================================================================
    # MinIO Bucket Names
    # ========================================================================
    
    bucket_dataset: str = os.getenv("BUCKET_DATASET", "dataset")
    bucket_processed: str = os.getenv("BUCKET_PROCESSED", "processed-data")
    bucket_mlflow: str = os.getenv("BUCKET_MLFLOW", "mlflow")
    bucket_predictions: str = os.getenv("BUCKET_PREDICTIONS", "predictions")
    bucket_promotion: str = os.getenv("BUCKET_PROMOTION", "model-promotion")
    bucket_inference_logs: str = os.getenv("BUCKET_INFERENCE_LOGS", "inference-txt-logs")
    
    # ========================================================================
    # Pipeline Runtime Parameters
    # ========================================================================
    
    default_dataset_name: str = os.getenv("DEFAULT_DATASET_NAME", "PobleSec")
    default_identifier: str = os.getenv("DEFAULT_IDENTIFIER", "default-run")
    
    # ========================================================================
    # AWS/S3 Configuration (for boto3/MLflow)
    # ========================================================================
    
    aws_region: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    aws_addressing_style: str = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
    
    def to_env_dict(self) -> dict:
        """
        Convert configuration to environment variable dictionary.
        Useful for setting component environment variables.
        
        Returns:
            Dictionary of env var name -> value
        """
        return {
            # MinIO
            "MINIO_ENDPOINT": self.minio_endpoint,
            "MINIO_ACCESS_KEY": self.minio_access_key,
            "MINIO_SECRET_KEY": self.minio_secret_key,
            "MINIO_SECURE": str(self.minio_secure).lower(),
            
            # MLflow
            "MLFLOW_TRACKING_URI": self.mlflow_tracking_uri,
            "MLFLOW_S3_ENDPOINT_URL": self.mlflow_s3_endpoint_url,
            
            # Gateway
            "GATEWAY_URL": self.gateway_url,
            
            # Buckets
            "BUCKET_DATASET": self.bucket_dataset,
            "BUCKET_PROCESSED": self.bucket_processed,
            "BUCKET_MLFLOW": self.bucket_mlflow,
            "BUCKET_PREDICTIONS": self.bucket_predictions,
            "BUCKET_PROMOTION": self.bucket_promotion,
            "BUCKET_INFERENCE_LOGS": self.bucket_inference_logs,
            
            # AWS
            "AWS_DEFAULT_REGION": self.aws_region,
            "AWS_S3_ADDRESSING_STYLE": self.aws_addressing_style,
            "AWS_ACCESS_KEY_ID": self.minio_access_key,
            "AWS_SECRET_ACCESS_KEY": self.minio_secret_key,
        }
    
    def to_pipeline_params(self) -> dict:
        """
        Convert configuration to KFP pipeline parameter dictionary.
        
        Returns:
            Dictionary of parameter name -> value
        """
        return {
            "gateway_url": self.gateway_url,
            "mlflow_tracking_uri": self.mlflow_tracking_uri,
            "dataset_name": self.default_dataset_name,
            "identifier": self.default_identifier,
        }
    
    def __repr__(self) -> str:
        """Safe string representation (masks secrets)."""
        return (
            f"RuntimeConfig(\n"
            f"  minio_endpoint={self.minio_endpoint},\n"
            f"  minio_access_key={'***' if self.minio_access_key else None},\n"
            f"  mlflow_tracking_uri={self.mlflow_tracking_uri},\n"
            f"  gateway_url={self.gateway_url},\n"
            f"  buckets=[{self.bucket_dataset}, {self.bucket_processed}, ...]\n"
            f")"
        )


# ============================================================================
# Deployment-Specific Presets
# ============================================================================

class DevConfig(RuntimeConfig):
    """Development/Minikube configuration (same as RuntimeConfig defaults)."""
    pass


class ProdConfig(RuntimeConfig):
    """
    Production configuration.
    Override with production endpoints/credentials.
    """
    def __init__(self):
        super().__init__()
        # Example production overrides
        # self.minio_endpoint = "minio.prod.example.com:9000"
        # self.minio_secure = True
        # self.mlflow_tracking_uri = "http://mlflow.prod.example.com:5000"
        pass


def get_config(env: str = "dev") -> RuntimeConfig:
    """
    Factory function to get configuration by environment.
    
    Args:
        env: Environment name ('dev', 'prod')
        
    Returns:
        RuntimeConfig instance
    """
    env = env.lower()
    if env == "prod":
        return ProdConfig()
    else:
        return DevConfig()


# ============================================================================
# Module-Level Defaults
# ============================================================================

# Default instance for convenient imports
DEFAULT_CONFIG = RuntimeConfig()

# Service endpoints (for backward compatibility)
MINIO_ENDPOINT = DEFAULT_CONFIG.minio_endpoint
MLFLOW_TRACKING_URI = DEFAULT_CONFIG.mlflow_tracking_uri
GATEWAY_URL = DEFAULT_CONFIG.gateway_url


if __name__ == "__main__":
    """Test configuration loading."""
    import sys
    
    print("=" * 70)
    print("KFP v2 Runtime Configuration")
    print("=" * 70)
    print()
    
    config = RuntimeConfig()
    print(config)
    print()
    
    print("Environment Variables:")
    print("-" * 70)
    env_dict = config.to_env_dict()
    for key, value in sorted(env_dict.items()):
        if "KEY" in key or "SECRET" in key:
            value = "***"
        print(f"  {key:<30} = {value}")
    print()
    
    print("Pipeline Parameters:")
    print("-" * 70)
    params = config.to_pipeline_params()
    for key, value in sorted(params.items()):
        print(f"  {key:<30} = {value}")
    print()
    
    print("=" * 70)
    print("Configuration loaded successfully")
    print("=" * 70)
