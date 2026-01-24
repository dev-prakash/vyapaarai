#!/bin/bash
# VyapaarAI Test Runner
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}VyapaarAI Test Suite${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/backend" 2>/dev/null || cd "$PROJECT_ROOT"

# Activate venv if exists
[ -d "venv" ] && source venv/bin/activate
[ -d "../venv" ] && source ../venv/bin/activate

TEST_TYPE=${1:-"unit"}

case $TEST_TYPE in
    "unit")
        pytest tests/unit -v -m "not slow"
        ;;
    "regression")
        pytest tests -v -m regression
        ;;
    "integration")
        docker-compose -f "$PROJECT_ROOT/docker-compose.yml" up -d
        sleep 3
        VYAPAARAI_ENV=test pytest tests/integration -v
        docker-compose -f "$PROJECT_ROOT/docker-compose.yml" down
        ;;
    "all")
        pytest tests -v
        ;;
    "coverage")
        pytest tests -v --cov=app --cov-report=html --cov-report=term-missing
        ;;
    *)
        echo "Usage: ./run_tests.sh [unit|regression|integration|all|coverage]"
        exit 1
        ;;
esac

[ $? -eq 0 ] && echo -e "${GREEN}Tests passed${NC}" || echo -e "${RED}Tests failed${NC}"
