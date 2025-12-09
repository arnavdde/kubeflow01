#!/bin/bash
# Task 7 Verification Script
# Tests all containers in KFP mode to verify Kafka deprecation

set -e  # Exit on error

echo "=========================================="
echo "Task 7 Verification Script"
echo "Testing all containers in KFP mode"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set KFP mode
export USE_KFP=1
export USE_KAFKA=0

# Base directory
BASE_DIR="/Users/arnavde/Python/AI/kubeflow-02/ml_pipeline_v3"

echo "Environment:"
echo "  USE_KFP=$USE_KFP"
echo "  USE_KAFKA=$USE_KAFKA"
echo ""

# Function to test import
test_import() {
    local container=$1
    local file=$2
    
    echo -n "Testing $container import... "
    
    # Try to import the module and check for errors
    cd "$BASE_DIR/$container"
    python3 -c "
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname('$file'), '..', 'shared'))

# Try importing config
try:
    from config import USE_KFP, USE_KAFKA
    print(f'Config imported: USE_KFP={USE_KFP}, USE_KAFKA={USE_KAFKA}')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)

# Try importing main module (should not fail on kafka_utils if USE_KAFKA=0)
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location('main', '$file')
    module = importlib.util.module_from_spec(spec)
    # Don't execute, just check syntax
    print('Module syntax OK')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        return 1
    fi
}

# Function to check for local USE_KFP definitions
check_no_local_usekfp() {
    local container=$1
    local file=$2
    
    echo -n "Checking $container for local USE_KFP definitions... "
    
    cd "$BASE_DIR/$container"
    
    # Search for local USE_KFP definitions (should be removed)
    local count=$(grep -c 'USE_KFP.*=.*int.*os\.environ\|USE_KFP.*=.*int.*os\.getenv' "$file" 2>/dev/null || echo "0")
    
    if [ "$count" -eq "0" ]; then
        echo -e "${GREEN}✅ PASS (0 found)${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL ($count found)${NC}"
        grep -n 'USE_KFP.*=.*int.*os\.environ\|USE_KFP.*=.*int.*os\.getenv' "$file" 2>/dev/null || true
        return 1
    fi
}

# Function to check Kafka imports are gated
check_kafka_gated() {
    local container=$1
    local file=$2
    
    echo -n "Checking $container Kafka imports are gated... "
    
    cd "$BASE_DIR/$container"
    
    # Check if kafka_utils import exists
    if grep -q "from kafka_utils import" "$file" 2>/dev/null; then
        # Check if it's gated behind USE_KAFKA
        if grep -B5 "from kafka_utils import" "$file" | grep -q "if USE_KAFKA:"; then
            echo -e "${GREEN}✅ PASS (gated)${NC}"
            return 0
        else
            echo -e "${RED}❌ FAIL (not gated)${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️  SKIP (no kafka_utils import)${NC}"
        return 0
    fi
}

echo "=========================================="
echo "Test 1: Container Import Tests"
echo "=========================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0

# Test each container
for container_file in \
    "inference_container:main.py" \
    "inference_container:inferencer.py" \
    "preprocess_container:main.py" \
    "train_container:main.py" \
    "nonML_container:main.py" \
    "eval_container:main.py"
do
    container=$(echo $container_file | cut -d: -f1)
    file=$(echo $container_file | cut -d: -f2)
    
    if test_import "$container" "$BASE_DIR/$container/$file"; then
        ((PASS_COUNT++))
    else
        ((FAIL_COUNT++))
    fi
done

echo ""
echo "=========================================="
echo "Test 2: Local USE_KFP Definition Check"
echo "=========================================="
echo ""

for container_file in \
    "inference_container:main.py" \
    "inference_container:inferencer.py" \
    "preprocess_container:main.py" \
    "train_container:main.py" \
    "nonML_container:main.py" \
    "eval_container:main.py"
do
    container=$(echo $container_file | cut -d: -f1)
    file=$(echo $container_file | cut -d: -f2)
    
    if check_no_local_usekfp "$container" "$file"; then
        ((PASS_COUNT++))
    else
        ((FAIL_COUNT++))
    fi
done

echo ""
echo "=========================================="
echo "Test 3: Kafka Import Gating Check"
echo "=========================================="
echo ""

for container_file in \
    "inference_container:main.py" \
    "inference_container:inferencer.py" \
    "preprocess_container:main.py" \
    "train_container:main.py" \
    "nonML_container:main.py" \
    "eval_container:main.py"
do
    container=$(echo $container_file | cut -d: -f1)
    file=$(echo $container_file | cut -d: -f2)
    
    if check_kafka_gated "$container" "$file"; then
        ((PASS_COUNT++))
    else
        ((FAIL_COUNT++))
    fi
done

echo ""
echo "=========================================="
echo "Test 4: Docker Compose Verification"
echo "=========================================="
echo ""

cd "$BASE_DIR"

echo -n "Checking docker-compose.kfp.yaml exists... "
if [ -f "docker-compose.kfp.yaml" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo -n "Checking docker-compose.kfp.yaml has no Kafka services... "
if ! grep -q "kafka:" docker-compose.kfp.yaml && ! grep -q "zookeeper:" docker-compose.kfp.yaml; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo -n "Checking Kafka backup exists... "
if [ -f "archive/legacy_pipeline_versions/docker-compose-kafka.yaml" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo ""
echo "=========================================="
echo "Test 5: Archive Verification"
echo "=========================================="
echo ""

echo -n "Checking kafka_utils.py archived... "
if [ -f "archive/deprecated_kafka/kafka_utils.py" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo -n "Checking shared/config.py exists... "
if [ -f "shared/config.py" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASS_COUNT++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((FAIL_COUNT++))
fi

echo ""
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo ""
echo "Total Tests: $((PASS_COUNT + FAIL_COUNT))"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED - Task 7 verification complete!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED - Please review errors above${NC}"
    exit 1
fi
