"""Prophet Training Component Package.

Exports the KFP v2 component for training Prophet time-series forecasting models.
"""

from .train_prophet_component import train_prophet_component

__all__ = ['train_prophet_component']
