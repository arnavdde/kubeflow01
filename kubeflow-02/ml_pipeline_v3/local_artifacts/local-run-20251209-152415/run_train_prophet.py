
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
import pickle

try:
    from prophet import Prophet
except ImportError:
    print("Prophet not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "prophet", "--quiet"])
    from prophet import Prophet

sys.path.insert(0, "/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/nonML_container")

# Configuration
training_data_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152415/processed_data/training_data.parquet")
output_dir = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152415") / "models" / "PROPHET"
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Loading training data from: {training_data_path}")
df = pd.read_parquet(training_data_path)
print(f"Loaded {len(df)} training samples")

# Prepare data for Prophet (needs 'ds' and 'y' columns)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(numeric_cols) == 0:
    print("Error: No numeric columns found")
    sys.exit(1)

# Create date range if no date column exists
if 'ds' not in df.columns:
    df['ds'] = pd.date_range(start='2020-01-01', periods=len(df), freq='H')

target_col = numeric_cols[0]
prophet_df = pd.DataFrame({
    'ds': df['ds'] if 'ds' in df.columns else pd.date_range(start='2020-01-01', periods=len(df), freq='H'),
    'y': df[target_col]
})

print(f"Training Prophet model on {len(prophet_df)} samples...")

# Train Prophet model
model = Prophet(
    seasonality_mode='multiplicative',
    yearly_seasonality=True,
    weekly_seasonality=True,
    daily_seasonality=False,
)

model.fit(prophet_df)

# Make predictions on training data to calculate metrics
forecast = model.predict(prophet_df)

# Calculate metrics
predictions = forecast['yhat'].values
actuals = prophet_df['y'].values

mse = np.mean((predictions - actuals) ** 2)
rmse = np.sqrt(mse)
mae = np.mean(np.abs(predictions - actuals))

print(f"\nFinal Metrics:")
print(f"  MSE:  {mse:.6f}")
print(f"  RMSE: {rmse:.6f}")
print(f"  MAE:  {mae:.6f}")

# Save model
model_path = output_dir / "model.pkl"
with open(model_path, "wb") as f:
    pickle.dump(model, f)

print(f"✓ Model saved to: {model_path}")

# Save metrics
metrics = {
    "model_type": "PROPHET",
    "mse": float(mse),
    "rmse": float(rmse),
    "mae": float(mae),
    "train_samples": len(prophet_df),
}

metrics_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152415") / "metrics" / "PROPHET_metrics.json"
metrics_path.parent.mkdir(exist_ok=True)
with open(metrics_path, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"✓ Metrics saved to: {metrics_path}")
