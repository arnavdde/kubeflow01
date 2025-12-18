#!/bin/bash
# Quick Start Script for Local Pipeline Execution
# 
# This script provides a one-command way to run the complete FLTS pipeline locally.
# No Docker, Kafka, or Kubeflow required.

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================================================${NC}"
echo -e "${BLUE}FLTS Pipeline - Local Quick Start${NC}"
echo -e "${BLUE}========================================================================${NC}\n"

# Check Python version
echo -e "${BLUE}[1/5] Checking Python version...${NC}"
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_CMD="python3"
    echo -e "${GREEN}✓ Found Python ${PYTHON_VERSION}${NC}"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version | awk '{print $2}')
    PYTHON_CMD="python"
    echo -e "${GREEN}✓ Found Python ${PYTHON_VERSION}${NC}"
else
    echo -e "${RED}✗ Python not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Check if virtual environment exists
echo -e "\n${BLUE}[2/5] Checking virtual environment...${NC}"
VENV_PATH="../.venv/bin/python"
if [ -f "$VENV_PATH" ]; then
    PYTHON_CMD="$VENV_PATH"
    echo -e "${GREEN}✓ Using virtual environment: $VENV_PATH${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment not found, using system Python${NC}"
fi

# Check required packages
echo -e "\n${BLUE}[3/5] Checking dependencies...${NC}"
MISSING_PACKAGES=()

# Check pandas
if ! $PYTHON_CMD -c "import pandas" &> /dev/null; then
    MISSING_PACKAGES+=("pandas")
    echo -e "${RED}✗ Missing: pandas${NC}"
else
    echo -e "${GREEN}✓ Found: pandas${NC}"
fi

# Check numpy
if ! $PYTHON_CMD -c "import numpy" &> /dev/null; then
    MISSING_PACKAGES+=("numpy")
    echo -e "${RED}✗ Missing: numpy${NC}"
else
    echo -e "${GREEN}✓ Found: numpy${NC}"
fi

# Check torch
if ! $PYTHON_CMD -c "import torch" &> /dev/null; then
    MISSING_PACKAGES+=("torch")
    echo -e "${RED}✗ Missing: torch${NC}"
else
    echo -e "${GREEN}✓ Found: torch${NC}"
fi

# Check scikit-learn (imports as sklearn)
if ! $PYTHON_CMD -c "import sklearn" &> /dev/null; then
    MISSING_PACKAGES+=("scikit-learn")
    echo -e "${RED}✗ Missing: scikit-learn${NC}"
else
    echo -e "${GREEN}✓ Found: scikit-learn${NC}"
fi

# Check pyarrow (needed for parquet)
if ! $PYTHON_CMD -c "import pyarrow" &> /dev/null; then
    MISSING_PACKAGES+=("pyarrow")
    echo -e "${RED}✗ Missing: pyarrow${NC}"
else
    echo -e "${GREEN}✓ Found: pyarrow${NC}"
fi

if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    echo -e "\n${YELLOW}Installing missing packages...${NC}"
    $PYTHON_CMD -m pip install "${MISSING_PACKAGES[@]}" --quiet
    echo -e "${GREEN}✓ Packages installed${NC}"
fi

# Check dataset
echo -e "\n${BLUE}[4/5] Checking dataset...${NC}"
DATASET=${1:-"PobleSec"}
DATASET_PATH="dataset/${DATASET}.csv"

if [ ! -f "$DATASET_PATH" ]; then
    echo -e "${RED}✗ Dataset not found: $DATASET_PATH${NC}"
    echo -e "${YELLOW}Available datasets:${NC}"
    ls dataset/*.csv 2>/dev/null || echo "No datasets found"
    exit 1
fi

echo -e "${GREEN}✓ Dataset found: $DATASET_PATH${NC}"

# Run pipeline
echo -e "\n${BLUE}[5/5] Running pipeline...${NC}"
echo -e "${BLUE}========================================================================${NC}\n"

IDENTIFIER="local-run-$(date +%Y%m%d-%H%M%S)"

$PYTHON_CMD run_pipeline_locally.py \
    --dataset "$DATASET" \
    --identifier "$IDENTIFIER"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}========================================================================${NC}"
    echo -e "${GREEN}Pipeline execution completed successfully!${NC}"
    echo -e "${GREEN}========================================================================${NC}\n"
    echo -e "${BLUE}Results saved to:${NC} local_artifacts/${IDENTIFIER}"
    echo -e "\n${BLUE}Next steps:${NC}"
    echo -e "  • View evaluation: ${GREEN}cat local_artifacts/${IDENTIFIER}/evaluations/evaluation_results.json${NC}"
    echo -e "  • View predictions: ${GREEN}cat local_artifacts/${IDENTIFIER}/predictions/predictions.csv${NC}"
    echo -e "  • See full guide: ${GREEN}cat LOCAL_EXECUTION_GUIDE.md${NC}"
else
    echo -e "\n${RED}========================================================================${NC}"
    echo -e "${RED}Pipeline execution failed (exit code: $EXIT_CODE)${NC}"
    echo -e "${RED}========================================================================${NC}\n"
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo -e "  • Check LOCAL_EXECUTION_GUIDE.md for common issues"
    echo -e "  • Verify all dependencies are installed"
    echo -e "  • Check log output above for error details"
    exit $EXIT_CODE
fi
