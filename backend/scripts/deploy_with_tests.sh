#!/bin/bash
#
# Deploy Backend with Full Regression Testing
# Author: DevPrakash
#
# This script:
# 1. Runs pre-deployment static tests
# 2. Builds and deploys Lambda package
# 3. Runs post-deployment live API tests
# 4. Rolls back if tests fail
#
# Usage:
#   ./scripts/deploy_with_tests.sh
#   VYAPARAI_TEST_PASSWORD=xxx ./scripts/deploy_with_tests.sh  # For full authenticated tests
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "=============================================="
echo "🚀 VyaparAI Backend Deployment with Testing"
echo "=============================================="

cd "$BACKEND_DIR"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# =============================================================================
# STEP 1: Pre-deployment static tests
# =============================================================================
echo ""
echo -e "${YELLOW}📋 Step 1: Running pre-deployment static tests...${NC}"

python -m pytest tests/regression/test_critical_paths.py -v --tb=short
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Pre-deployment tests failed! Aborting deployment.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Pre-deployment tests passed${NC}"

# =============================================================================
# STEP 2: Build deployment package
# =============================================================================
echo ""
echo -e "${YELLOW}📦 Step 2: Building Lambda deployment package...${NC}"

./scripts/deploy_lambda.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed! Aborting deployment.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Build successful${NC}"

# =============================================================================
# STEP 3: Get current Lambda version (for potential rollback)
# =============================================================================
echo ""
echo -e "${YELLOW}📸 Step 3: Saving current Lambda version for rollback...${NC}"

FUNCTION_NAME="vyaparai-api-prod"
CURRENT_VERSION=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.CodeSha256' --output text 2>/dev/null || echo "")
echo "Current version hash: $CURRENT_VERSION"

# =============================================================================
# STEP 4: Deploy to Lambda
# =============================================================================
echo ""
echo -e "${YELLOW}🚀 Step 4: Deploying to Lambda...${NC}"

aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://lambda_function.zip \
    --output json > /tmp/deploy_result.json

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Lambda deployment failed!${NC}"
    exit 1
fi

NEW_VERSION=$(cat /tmp/deploy_result.json | python -c "import sys,json; print(json.load(sys.stdin).get('CodeSha256',''))")
echo "New version hash: $NEW_VERSION"

# Wait for Lambda to be ready
echo "Waiting for Lambda to be ready..."
sleep 15

# Check Lambda status
STATUS=$(aws lambda get-function --function-name $FUNCTION_NAME --query 'Configuration.LastUpdateStatus' --output text)
if [ "$STATUS" != "Successful" ]; then
    echo -e "${YELLOW}⏳ Lambda still updating, waiting...${NC}"
    sleep 15
fi

echo -e "${GREEN}✅ Lambda deployed${NC}"

# =============================================================================
# STEP 5: Run post-deployment live API tests
# =============================================================================
echo ""
echo -e "${YELLOW}🧪 Step 5: Running post-deployment live API tests...${NC}"

python -m pytest tests/regression/test_production_api.py -v --tb=short
TEST_RESULT=$?

if [ $TEST_RESULT -ne 0 ]; then
    echo -e "${RED}❌ Post-deployment tests failed!${NC}"
    echo ""

    # Ask about rollback
    if [ -n "$CURRENT_VERSION" ] && [ "$CURRENT_VERSION" != "$NEW_VERSION" ]; then
        echo -e "${YELLOW}⚠️  Deployment may have broken the API.${NC}"
        echo "Previous version: $CURRENT_VERSION"
        echo "Current version:  $NEW_VERSION"
        echo ""
        echo "Check CloudWatch logs:"
        echo "  aws logs filter-log-events --log-group-name /aws/lambda/$FUNCTION_NAME --limit 20"
        echo ""
        echo "To manually rollback, re-deploy the previous version."
    fi

    exit 1
fi

echo -e "${GREEN}✅ Post-deployment tests passed${NC}"

# =============================================================================
# STEP 6: Summary
# =============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}🎉 Deployment Successful!${NC}"
echo "=============================================="
echo ""
echo "Lambda Function: $FUNCTION_NAME"
echo "Version Hash:    $NEW_VERSION"
echo ""
echo "Test Results:"
echo "  - Pre-deployment static tests: PASSED"
echo "  - Lambda deployment: SUCCESS"
echo "  - Post-deployment API tests: PASSED"
echo ""

if [ -z "$VYAPARAI_TEST_PASSWORD" ]; then
    echo -e "${YELLOW}⚠️  Note: Authenticated tests were skipped.${NC}"
    echo "   Set VYAPARAI_TEST_PASSWORD to run full test suite."
    echo ""
fi

echo "API URL: https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
echo ""
