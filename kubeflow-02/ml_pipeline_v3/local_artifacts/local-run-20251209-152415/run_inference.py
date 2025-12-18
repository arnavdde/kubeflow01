
import sys
import json
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path

# Configuration
model_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152415/models/GRU/model.pt")
inference_data_path = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152415/processed_data/inference_data.parquet")
output_dir = Path("/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3/local_artifacts/local-run-20251209-152415") / "predictions"
output_dir.mkdir(exist_ok=True)

print(f"Loading model from: {model_path}")
checkpoint = torch.load(model_path, map_location='cpu')

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

print(f"Loading inference data from: {inference_data_path}")
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

print(f"\nGenerated {len(predictions)} predictions")

# Calculate metrics
mse = np.mean((predictions - actuals) ** 2)
rmse = np.sqrt(mse)
mae = np.mean(np.abs(predictions - actuals))

print(f"\nInference Metrics:")
print(f"  MSE:  {mse:.6f}")
print(f"  RMSE: {rmse:.6f}")
print(f"  MAE:  {mae:.6f}")

# Save results
results = {
    "model_type": "GRU",
    "num_predictions": len(predictions),
    "predictions": predictions.tolist()[:10],  # First 10
    "actuals": actuals.tolist()[:10],
    "metrics": {
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
    }
}

results_path = output_dir / "inference_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"✓ Results saved to: {results_path}")

# Save predictions CSV
pred_df = pd.DataFrame({
    'actual': actuals,
    'predicted': predictions,
})
pred_csv = output_dir / "predictions.csv"
pred_df.to_csv(pred_csv, index=False)
print(f"✓ Predictions saved to: {pred_csv}")
