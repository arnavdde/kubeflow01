"""
Inference Component for KFP v2 Pipeline

This component executes time-series forecasting inference using promoted models.
"""

from .inference_component import run_inference_component

__all__ = ["run_inference_component"]
