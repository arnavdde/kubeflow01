"""LSTM Training Component Package.

Exports the KFP v2 component for training LSTM time-series forecasting models.
"""

from .train_lstm_component import train_lstm_component

__all__ = ['train_lstm_component']
