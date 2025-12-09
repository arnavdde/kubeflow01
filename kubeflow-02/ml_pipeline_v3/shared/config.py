"""
Global Configuration for ML Pipeline

This module provides centralized configuration for the entire pipeline,
including feature flags for Kafka deprecation and KFP migration.

Feature Flags:
    USE_KFP: If True (default), all containers run in KFP mode with artifact-based I/O.
             If False, legacy Kafka mode is enabled (deprecated, for emergency rollback only).
    
    USE_KAFKA: If True, Kafka dependencies are available (deprecated).
               If False (default), Kafka is fully disabled and imports are gated.

Migration Status:
    - Tasks 1-6: Complete (all components support KFP mode)
    - Task 7: In progress (Kafka deprecation)
    - Default mode: KFP (USE_KFP=1, USE_KAFKA=0)

Usage:
    from shared.config import USE_KFP, USE_KAFKA
    
    if USE_KFP:
        # KFP mode logic
        process_artifacts()
    elif USE_KAFKA:
        # Legacy Kafka mode (deprecated)
        process_kafka_messages()
"""

import os

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Primary feature flag: KFP mode (default enabled)
USE_KFP = int(os.getenv("USE_KFP", "1"))

# Legacy feature flag: Kafka mode (default disabled, deprecated)
# Only set to True for emergency rollback scenarios
USE_KAFKA = os.getenv("USE_KAFKA", "false").lower() in {"1", "true", "yes"}

# Validation: Cannot run both modes simultaneously
if USE_KFP and USE_KAFKA:
    raise ValueError(
        "Invalid configuration: USE_KFP and USE_KAFKA cannot both be enabled. "
        "Choose one mode: USE_KFP=1 (default, recommended) or USE_KAFKA=1 (deprecated)."
    )

# If neither mode is explicitly enabled, default to KFP
if not USE_KFP and not USE_KAFKA:
    USE_KFP = 1
    print("Warning: Neither USE_KFP nor USE_KAFKA explicitly set. Defaulting to USE_KFP=1 (KFP mode).")

# ============================================================================
# DEPLOYMENT MODE
# ============================================================================

DEPLOYMENT_MODE = "KFP" if USE_KFP else "KAFKA" if USE_KAFKA else "UNKNOWN"

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ["USE_KFP", "USE_KAFKA", "DEPLOYMENT_MODE"]
