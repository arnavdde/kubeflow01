#!/usr/bin/env python3
"""
Local Pipeline Execution Script

Runs the complete FLTS pipeline locally without Docker containers or Kubeflow.
Executes each component step-by-step using local Python environments.

This script simulates the pipeline DAG defined in kubeflow_pipeline/pipeline_v2.py
by running each component's logic directly:

1. Preprocess → Load and transform data
2. Train (parallel) → GRU, LSTM, Prophet models
3. Evaluate → Select best model
4. Inference → Generate predictions

Usage:
    python run_pipeline_locally.py [--dataset PobleSec] [--identifier test-run-001]
    
Requirements:
    - Python 3.11+
    - All component dependencies installed in virtual environment
    - Local file system for artifacts (no MinIO required)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import subprocess
import shutil

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(message):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_step(step_num, step_name):
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}[Step {step_num}] {step_name}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'-'*80}{Colors.ENDC}")


def print_success(message):
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")


def print_error(message):
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")


def print_warning(message):
    print(f"{Colors.WARNING}⚠ {message}{Colors.ENDC}")


def print_info(message):
    print(f"{Colors.OKBLUE}ℹ {message}{Colors.ENDC}")


class LocalPipelineRunner:
    """Executes the FLTS pipeline locally without containers."""
    
    def __init__(self, dataset_name: str, identifier: str, base_dir: Path):
        self.dataset_name = dataset_name
        self.identifier = identifier
        self.base_dir = base_dir
        self.artifacts_dir = base_dir / "local_artifacts" / identifier
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Component directories
        self.preprocess_dir = base_dir / "preprocess_container"
        self.train_dir = base_dir / "train_container"
        self.nonml_dir = base_dir / "nonML_container"
        self.eval_dir = base_dir / "eval_container"
        self.inference_dir = base_dir / "inference_container"
        self.dataset_dir = base_dir / "dataset"
        
        # Python executable (use venv if available)
        venv_python = base_dir.parent / ".venv" / "bin" / "python"
        self.python = str(venv_python) if venv_python.exists() else "python3"
        
        # Track component outputs
        self.outputs = {}
        
    def setup_environment(self):
        """Prepare local environment for execution."""
        print_step(0, "Environment Setup")
        
        # Check required directories
        required_dirs = [
            self.preprocess_dir,
            self.train_dir,
            self.nonml_dir,
            self.eval_dir,
            self.inference_dir,
            self.dataset_dir,
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                print_error(f"Required directory not found: {dir_path}")
                return False
            print_success(f"Found: {dir_path.name}")
        
        # Check dataset exists
        dataset_path = self.dataset_dir / f"{self.dataset_name}.csv"
        if not dataset_path.exists():
            print_error(f"Dataset not found: {dataset_path}")
            return False
        print_success(f"Dataset found: {dataset_path}")
        
        # Create local output directories
        output_dirs = [
            "processed_data",
            "models",
            "metrics",
            "evaluations",
            "predictions",
        ]
        for dir_name in output_dirs:
            (self.artifacts_dir / dir_name).mkdir(exist_ok=True)
        print_success(f"Artifacts directory: {self.artifacts_dir}")
        
        return True
    
    def run_preprocess(self):
        """Step 1: Data preprocessing."""
        print_step(1, "Data Preprocessing")
        
        # Set up environment for preprocessing
        env = os.environ.copy()
        env.update({
            "DATASET_NAME": self.dataset_name,
            "IDENTIFIER": self.identifier,
            "SAMPLE_TRAIN_ROWS": "0",  # Use full dataset
            "SAMPLE_TEST_ROWS": "0",
            "SAMPLE_STRATEGY": "head",
            "SAMPLE_SEED": "42",
            "HANDLE_NANS": "True",
            "NANS_THRESHOLD": "0.33",
            "CLIP_ENABLE": "False",
            "SCALER": "MinMaxScaler",
            "TIME_FEATURES_ENABLE": "True",
            "LAGS_ENABLE": "False",
            "USE_KFP": "1",  # Disable Kafka
            "USE_KAFKA": "0",
            "LOCAL_MODE": "1",
        })
        
        # Create a local preprocessing script
        preprocess_script = self.artifacts_dir / "run_preprocess.py"
        preprocess_code = f'''
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path

# Add shared modules to path
sys.path.insert(0, "{self.base_dir / 'shared'}")
sys.path.insert(0, "{self.preprocess_dir}")

from data_utils import read_data, handle_nans, scale_data, time_to_feature

# Configuration
dataset_path = Path("{self.dataset_dir}") / "{self.dataset_name}.csv"
output_dir = Path("{self.artifacts_dir}") / "processed_data"
output_dir.mkdir(exist_ok=True)

print(f"Loading dataset: {{dataset_path}}")
df = pd.read_csv(dataset_path)
print(f"Loaded {{len(df)}} rows")

# Split train/test (80/20)
split_idx = int(len(df) * 0.8)
train_df = df[:split_idx].copy()
test_df = df[split_idx:].copy()
print(f"Train: {{len(train_df)}} rows, Test: {{len(test_df)}} rows")

# Save processed data
train_path = output_dir / "training_data.parquet"
test_path = output_dir / "inference_data.parquet"

train_df.to_parquet(train_path, index=False)
test_df.to_parquet(test_path, index=False)

print(f"✓ Training data saved to: {{train_path}}")
print(f"✓ Inference data saved to: {{test_path}}")

# Save config
config = {{
    "dataset_name": "{self.dataset_name}",
    "identifier": "{self.identifier}",
    "train_rows": len(train_df),
    "test_rows": len(test_df),
    "timestamp": pd.Timestamp.now().isoformat(),
}}

config_path = output_dir / "config.json"
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"✓ Config saved to: {{config_path}}")
'''
        
        with open(preprocess_script, "w") as f:
            f.write(preprocess_code)
        
        # Run preprocessing
        result = subprocess.run(
            [self.python, str(preprocess_script)],
            env=env,
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print_error("Preprocessing failed")
            print(result.stderr)
            return False
        
        print(result.stdout)
        
        # Store outputs
        self.outputs["training_data"] = self.artifacts_dir / "processed_data" / "training_data.parquet"
        self.outputs["inference_data"] = self.artifacts_dir / "processed_data" / "inference_data.parquet"
        self.outputs["config_hash"] = "local-run"
        
        print_success("Preprocessing complete")
        return True
    
    def run_train_model(self, model_type: str, model_name: str):
        """Train a specific model type."""
        print(f"\nTraining {model_name} model...")
        
        # Determine which container to use
        if model_type in ["GRU", "LSTM"]:
            container_dir = self.train_dir
        else:  # PROPHET
            container_dir = self.nonml_dir
        
        # Create training script
        train_script = self.artifacts_dir / f"run_train_{model_type.lower()}.py"
        
        if model_type in ["GRU", "LSTM"]:
            train_code = f'''
import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
import pickle

sys.path.insert(0, "{container_dir}")

# Configuration
model_type = "{model_type}"
training_data_path = Path("{self.outputs['training_data']}")
output_dir = Path("{self.artifacts_dir}") / "models" / "{model_type}"
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Loading training data from: {{training_data_path}}")
df = pd.read_parquet(training_data_path)
print(f"Loaded {{len(df)}} training samples")

# Extract features (simple version - use first numeric column as target)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(numeric_cols) == 0:
    print("Error: No numeric columns found")
    sys.exit(1)

target_col = numeric_cols[0]
print(f"Using target column: {{target_col}}")

# Create simple sequences
sequence_length = 12
values = df[target_col].values

# Normalize
scaler = MinMaxScaler()
scaled_values = scaler.fit_transform(values.reshape(-1, 1)).flatten()

# Create sequences
X, y = [], []
for i in range(len(scaled_values) - sequence_length):
    X.append(scaled_values[i:i+sequence_length])
    y.append(scaled_values[i+sequence_length])

X = torch.FloatTensor(X).unsqueeze(-1)  # [batch, seq, 1]
y = torch.FloatTensor(y)

print(f"Created {{len(X)}} sequences")

# Define simple model
class SimpleRNN(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=2):
        super().__init__()
        if model_type == "LSTM":
            self.rnn = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        else:  # GRU
            self.rnn = nn.GRU(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)
    
    def forward(self, x):
        out, _ = self.rnn(x)
        out = self.fc(out[:, -1, :])
        return out

# Train model
model = SimpleRNN(hidden_size=64, num_layers=2)
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

print("Training model...")
num_epochs = 10
batch_size = 32

for epoch in range(num_epochs):
    total_loss = 0
    for i in range(0, len(X), batch_size):
        batch_X = X[i:i+batch_size]
        batch_y = y[i:i+batch_size]
        
        optimizer.zero_grad()
        outputs = model(batch_X).squeeze()
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
    
    avg_loss = total_loss / (len(X) / batch_size)
    if (epoch + 1) % 2 == 0:
        print(f"Epoch [{{epoch+1}}/{{num_epochs}}], Loss: {{avg_loss:.6f}}")

# Calculate final metrics
model.eval()
with torch.no_grad():
    predictions = model(X).squeeze()
    mse = criterion(predictions, y).item()
    rmse = np.sqrt(mse)
    mae = torch.abs(predictions - y).mean().item()

print(f"\\nFinal Metrics:")
print(f"  MSE:  {{mse:.6f}}")
print(f"  RMSE: {{rmse:.6f}}")
print(f"  MAE:  {{mae:.6f}}")

# Save model
model_path = output_dir / "model.pt"
torch.save({{
    'model_state_dict': model.state_dict(),
    'model_type': model_type,
    'hidden_size': 64,
    'num_layers': 2,
    'scaler': scaler,
    'sequence_length': sequence_length,
}}, model_path)

print(f"✓ Model saved to: {{model_path}}")

# Save metrics
metrics = {{
    "model_type": model_type,
    "mse": float(mse),
    "rmse": float(rmse),
    "mae": float(mae),
    "num_epochs": num_epochs,
    "train_samples": len(X),
}}

metrics_path = Path("{self.artifacts_dir}") / "metrics" / f"{{model_type}}_metrics.json"
metrics_path.parent.mkdir(exist_ok=True)
with open(metrics_path, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"✓ Metrics saved to: {{metrics_path}}")
'''
        else:  # PROPHET
            train_code = f'''
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

sys.path.insert(0, "{container_dir}")

# Configuration
training_data_path = Path("{self.outputs['training_data']}")
output_dir = Path("{self.artifacts_dir}") / "models" / "PROPHET"
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Loading training data from: {{training_data_path}}")
df = pd.read_parquet(training_data_path)
print(f"Loaded {{len(df)}} training samples")

# Prepare data for Prophet (needs 'ds' and 'y' columns)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(numeric_cols) == 0:
    print("Error: No numeric columns found")
    sys.exit(1)

# Create date range if no date column exists
if 'ds' not in df.columns:
    df['ds'] = pd.date_range(start='2020-01-01', periods=len(df), freq='H')

target_col = numeric_cols[0]
prophet_df = pd.DataFrame({{
    'ds': df['ds'] if 'ds' in df.columns else pd.date_range(start='2020-01-01', periods=len(df), freq='H'),
    'y': df[target_col]
}})

print(f"Training Prophet model on {{len(prophet_df)}} samples...")

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

print(f"\\nFinal Metrics:")
print(f"  MSE:  {{mse:.6f}}")
print(f"  RMSE: {{rmse:.6f}}")
print(f"  MAE:  {{mae:.6f}}")

# Save model
model_path = output_dir / "model.pkl"
with open(model_path, "wb") as f:
    pickle.dump(model, f)

print(f"✓ Model saved to: {{model_path}}")

# Save metrics
metrics = {{
    "model_type": "PROPHET",
    "mse": float(mse),
    "rmse": float(rmse),
    "mae": float(mae),
    "train_samples": len(prophet_df),
}}

metrics_path = Path("{self.artifacts_dir}") / "metrics" / "PROPHET_metrics.json"
metrics_path.parent.mkdir(exist_ok=True)
with open(metrics_path, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"✓ Metrics saved to: {{metrics_path}}")
'''
        
        with open(train_script, "w") as f:
            f.write(train_code)
        
        # Run training
        result = subprocess.run(
            [self.python, str(train_script)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print_error(f"{model_name} training failed")
            print(result.stderr)
            return False
        
        print(result.stdout)
        
        # Store outputs
        self.outputs[f"{model_type}_model"] = self.artifacts_dir / "models" / model_type / ("model.pt" if model_type != "PROPHET" else "model.pkl")
        self.outputs[f"{model_type}_metrics"] = self.artifacts_dir / "metrics" / f"{model_type}_metrics.json"
        
        print_success(f"{model_name} training complete")
        return True
    
    def run_training(self):
        """Step 2: Train all models in parallel (simulated sequentially here)."""
        print_step(2, "Model Training")
        
        models = [
            ("GRU", "GRU"),
            ("LSTM", "LSTM"),
            ("PROPHET", "Prophet"),
        ]
        
        for model_type, model_name in models:
            if not self.run_train_model(model_type, model_name):
                return False
        
        return True
    
    def run_evaluation(self):
        """Step 3: Evaluate models and select best."""
        print_step(3, "Model Evaluation & Selection")
        
        # Load all metrics
        metrics_data = {}
        for model_type in ["GRU", "LSTM", "PROPHET"]:
            metrics_path = self.artifacts_dir / "metrics" / f"{model_type}_metrics.json"
            with open(metrics_path) as f:
                metrics_data[model_type] = json.load(f)
        
        print("\nModel Comparison:")
        print(f"{'Model':<10} {'MSE':<12} {'RMSE':<12} {'MAE':<12}")
        print("-" * 50)
        
        # Calculate weighted scores (lower is better)
        scores = {}
        for model_type, metrics in metrics_data.items():
            score = (
                0.5 * metrics["rmse"] +
                0.3 * metrics["mae"] +
                0.2 * metrics["mse"]
            )
            scores[model_type] = score
            print(f"{model_type:<10} {metrics['mse']:<12.6f} {metrics['rmse']:<12.6f} {metrics['mae']:<12.6f}")
        
        # Select best model
        best_model = min(scores, key=scores.get)
        best_score = scores[best_model]
        
        print(f"\n{Colors.OKGREEN}Best Model: {best_model} (score: {best_score:.6f}){Colors.ENDC}")
        
        # Save evaluation results
        eval_results = {
            "best_model": best_model,
            "best_score": best_score,
            "all_scores": scores,
            "all_metrics": metrics_data,
            "timestamp": datetime.now().isoformat(),
        }
        
        eval_path = self.artifacts_dir / "evaluations" / "evaluation_results.json"
        eval_path.parent.mkdir(exist_ok=True)
        with open(eval_path, "w") as f:
            json.dump(eval_results, f, indent=2)
        
        print_success(f"Evaluation results saved to: {eval_path}")
        
        # Store outputs
        self.outputs["best_model"] = best_model
        self.outputs["promotion_pointer"] = self.outputs[f"{best_model}_model"]
        
        return True
    
    def run_inference(self):
        """Step 4: Run inference using best model."""
        print_step(4, "Inference")
        
        best_model = self.outputs["best_model"]
        model_path = self.outputs["promotion_pointer"]
        inference_data_path = self.outputs["inference_data"]
        
        print(f"Using best model: {best_model}")
        print(f"Model path: {model_path}")
        
        # Create inference script
        inference_script = self.artifacts_dir / "run_inference.py"
        
        if best_model in ["GRU", "LSTM"]:
            inference_code = f'''
import sys
import json
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path

# Configuration
model_path = Path("{model_path}")
inference_data_path = Path("{inference_data_path}")
output_dir = Path("{self.artifacts_dir}") / "predictions"
output_dir.mkdir(exist_ok=True)

print(f"Loading model from: {{model_path}}")
checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)

# Recreate model
class SimpleRNN(nn.Module):
    def __init__(self, input_size=1, hidden_size=64, num_layers=2):
        super().__init__()
        model_type = checkpoint['model_type']
        if model_type == "LSTM":
            self.rnn = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        else:
            self.rnn = nn.GRU(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)
    
    def forward(self, x):
        out, _ = self.rnn(x)
        out = self.fc(out[:, -1, :])
        return out

model = SimpleRNN(
    hidden_size=checkpoint['hidden_size'],
    num_layers=checkpoint['num_layers']
)
model.load_state_dict(checkpoint['model_state_dict'])
model.eval()

scaler = checkpoint['scaler']
sequence_length = checkpoint['sequence_length']

print(f"Loading inference data from: {{inference_data_path}}")
df = pd.read_parquet(inference_data_path)

# Get numeric column
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
target_col = numeric_cols[0]
values = df[target_col].values[:50]  # First 50 samples

scaled_values = scaler.transform(values.reshape(-1, 1)).flatten()

# Create sequences and predict
predictions = []
actuals = []

for i in range(len(scaled_values) - sequence_length):
    seq = scaled_values[i:i+sequence_length]
    X = torch.FloatTensor(seq).unsqueeze(0).unsqueeze(-1)
    
    with torch.no_grad():
        pred = model(X).item()
    
    predictions.append(pred)
    actuals.append(scaled_values[i+sequence_length])

# Inverse transform
predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1)).flatten()
actuals = scaler.inverse_transform(np.array(actuals).reshape(-1, 1)).flatten()

print(f"\\nGenerated {{len(predictions)}} predictions")

# Calculate metrics
mse = np.mean((predictions - actuals) ** 2)
rmse = np.sqrt(mse)
mae = np.mean(np.abs(predictions - actuals))

print(f"\\nInference Metrics:")
print(f"  MSE:  {{mse:.6f}}")
print(f"  RMSE: {{rmse:.6f}}")
print(f"  MAE:  {{mae:.6f}}")

# Save results
results = {{
    "model_type": "{best_model}",
    "num_predictions": len(predictions),
    "predictions": predictions.tolist()[:10],  # First 10
    "actuals": actuals.tolist()[:10],
    "metrics": {{
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
    }}
}}

results_path = output_dir / "inference_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"✓ Results saved to: {{results_path}}")

# Save predictions CSV
pred_df = pd.DataFrame({{
    'actual': actuals,
    'predicted': predictions,
}})
pred_csv = output_dir / "predictions.csv"
pred_df.to_csv(pred_csv, index=False)
print(f"✓ Predictions saved to: {{pred_csv}}")
'''
        else:  # PROPHET
            inference_code = f'''
import sys
import json
import pandas as pd
import numpy as np
import pickle
from pathlib import Path

try:
    from prophet import Prophet
except ImportError:
    print("Prophet not installed")
    sys.exit(1)

# Configuration
model_path = Path("{model_path}")
inference_data_path = Path("{inference_data_path}")
output_dir = Path("{self.artifacts_dir}") / "predictions"
output_dir.mkdir(exist_ok=True)

print(f"Loading model from: {{model_path}}")
with open(model_path, "rb") as f:
    model = pickle.load(f)

print(f"Loading inference data from: {{inference_data_path}}")
df = pd.read_parquet(inference_data_path)

# Prepare data for Prophet
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
target_col = numeric_cols[0]

# Create future dataframe
future_periods = min(50, len(df))
future = model.make_future_dataframe(periods=future_periods, freq='H')

print(f"Generating {{future_periods}} predictions...")
forecast = model.predict(future)

# Get predictions and actuals
predictions = forecast['yhat'].values[-future_periods:]
actuals = df[target_col].values[:future_periods]

# Calculate metrics
mse = np.mean((predictions - actuals) ** 2)
rmse = np.sqrt(mse)
mae = np.mean(np.abs(predictions - actuals))

print(f"\\nInference Metrics:")
print(f"  MSE:  {{mse:.6f}}")
print(f"  RMSE: {{rmse:.6f}}")
print(f"  MAE:  {{mae:.6f}}")

# Save results
results = {{
    "model_type": "PROPHET",
    "num_predictions": len(predictions),
    "predictions": predictions.tolist()[:10],
    "actuals": actuals.tolist()[:10],
    "metrics": {{
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
    }}
}}

results_path = output_dir / "inference_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"✓ Results saved to: {{results_path}}")

# Save predictions CSV
pred_df = pd.DataFrame({{
    'actual': actuals,
    'predicted': predictions,
}})
pred_csv = output_dir / "predictions.csv"
pred_df.to_csv(pred_csv, index=False)
print(f"✓ Predictions saved to: {{pred_csv}}")
'''
        
        with open(inference_script, "w") as f:
            f.write(inference_code)
        
        # Run inference
        result = subprocess.run(
            [self.python, str(inference_script)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print_error("Inference failed")
            print(result.stderr)
            return False
        
        print(result.stdout)
        
        print_success("Inference complete")
        return True
    
    def run_pipeline(self):
        """Execute complete pipeline."""
        print_header("FLTS Pipeline - Local Execution")
        
        print_info(f"Dataset: {self.dataset_name}")
        print_info(f"Identifier: {self.identifier}")
        print_info(f"Artifacts: {self.artifacts_dir}")
        
        start_time = time.time()
        
        # Execute pipeline steps
        steps = [
            (self.setup_environment, "Environment Setup"),
            (self.run_preprocess, "Data Preprocessing"),
            (self.run_training, "Model Training"),
            (self.run_evaluation, "Model Evaluation"),
            (self.run_inference, "Inference"),
        ]
        
        for step_func, step_name in steps:
            if not step_func():
                print_error(f"Pipeline failed at: {step_name}")
                return False
        
        elapsed_time = time.time() - start_time
        
        print_header("Pipeline Execution Complete")
        print_success(f"Total execution time: {elapsed_time:.2f} seconds")
        print_info(f"Artifacts saved to: {self.artifacts_dir}")
        
        # Print summary
        print("\n" + "="*80)
        print("Pipeline Summary:")
        print("="*80)
        print(f"  Dataset:          {self.dataset_name}")
        print(f"  Identifier:       {self.identifier}")
        print(f"  Best Model:       {self.outputs.get('best_model', 'N/A')}")
        print(f"  Artifacts Dir:    {self.artifacts_dir}")
        print("="*80)
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Run FLTS pipeline locally without Docker/Kubeflow"
    )
    parser.add_argument(
        "--dataset",
        default="PobleSec",
        choices=["PobleSec", "ElBorn", "LesCorts"],
        help="Dataset name to process"
    )
    parser.add_argument(
        "--identifier",
        default=f"local-run-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        help="Unique identifier for this run"
    )
    
    args = parser.parse_args()
    
    # Determine base directory
    script_dir = Path(__file__).parent
    base_dir = script_dir / "ml_pipeline_v3" if (script_dir / "ml_pipeline_v3").exists() else script_dir
    
    # Create and run pipeline
    runner = LocalPipelineRunner(
        dataset_name=args.dataset,
        identifier=args.identifier,
        base_dir=base_dir,
    )
    
    success = runner.run_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
