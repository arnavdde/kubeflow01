
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path

# Add shared modules to path
sys.path.insert(0, "/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/shared")
sys.path.insert(0, "/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/preprocess_container")

from data_utils import read_data, handle_nans, scale_data, time_to_feature

# Configuration
dataset_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/dataset") / "PobleSec.csv"
output_dir = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-154751") / "processed_data"
output_dir.mkdir(exist_ok=True)

print(f"Loading dataset: {dataset_path}")
df = pd.read_csv(dataset_path)
print(f"Loaded {len(df)} rows")

# Split train/test (80/20)
split_idx = int(len(df) * 0.8)
train_df = df[:split_idx].copy()
test_df = df[split_idx:].copy()
print(f"Train: {len(train_df)} rows, Test: {len(test_df)} rows")

# Save processed data
train_path = output_dir / "training_data.parquet"
test_path = output_dir / "inference_data.parquet"

train_df.to_parquet(train_path, index=False)
test_df.to_parquet(test_path, index=False)

print(f"✓ Training data saved to: {train_path}")
print(f"✓ Inference data saved to: {test_path}")

# Save config
config = {
    "dataset_name": "PobleSec",
    "identifier": "local-run-20251209-154751",
    "train_rows": len(train_df),
    "test_rows": len(test_df),
    "timestamp": pd.Timestamp.now().isoformat(),
}

config_path = output_dir / "config.json"
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"✓ Config saved to: {config_path}")
