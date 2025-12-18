
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

sys.path.insert(0, "/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/train_container")

# Configuration
model_type = "GRU"
training_data_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152156/processed_data/training_data.parquet")
output_dir = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152156") / "models" / "GRU"
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Loading training data from: {training_data_path}")
df = pd.read_parquet(training_data_path)
print(f"Loaded {len(df)} training samples")

# Extract features (simple version - use first numeric column as target)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if len(numeric_cols) == 0:
    print("Error: No numeric columns found")
    sys.exit(1)

target_col = numeric_cols[0]
print(f"Using target column: {target_col}")

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

print(f"Created {len(X)} sequences")

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
        print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {avg_loss:.6f}")

# Calculate final metrics
model.eval()
with torch.no_grad():
    predictions = model(X).squeeze()
    mse = criterion(predictions, y).item()
    rmse = np.sqrt(mse)
    mae = torch.abs(predictions - y).mean().item()

print(f"\nFinal Metrics:")
print(f"  MSE:  {mse:.6f}")
print(f"  RMSE: {rmse:.6f}")
print(f"  MAE:  {mae:.6f}")

# Save model
model_path = output_dir / "model.pt"
torch.save({
    'model_state_dict': model.state_dict(),
    'model_type': model_type,
    'hidden_size': 64,
    'num_layers': 2,
    'scaler': scaler,
    'sequence_length': sequence_length,
}, model_path)

print(f"✓ Model saved to: {model_path}")

# Save metrics
metrics = {
    "model_type": model_type,
    "mse": float(mse),
    "rmse": float(rmse),
    "mae": float(mae),
    "num_epochs": num_epochs,
    "train_samples": len(X),
}

metrics_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152156") / "metrics" / f"{model_type}_metrics.json"
metrics_path.parent.mkdir(exist_ok=True)
with open(metrics_path, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"✓ Metrics saved to: {metrics_path}")
