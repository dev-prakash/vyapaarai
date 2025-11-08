#!/bin/bash

# VyaparAI Deployment Status Check Script
# Checks Lambda function status and tests API endpoints

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LAMBDA_URL="https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
AWS_REGION="ap-south-1"
FUNCTION_NAME="vyaparai-api-prod"

echo -e "${BLUE}🔍 VyaparAI Deployment Status Check${NC}"
echo "=========================================="

# Function to print status
print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "success" ]; then
        echo -e "${GREEN}✅ $message${NC}"
    elif [ "$status" = "warning" ]; then
        echo -e "${YELLOW}⚠️  $message${NC}"
    else
        echo -e "${RED}❌ $message${NC}"
    fi
}

# Check if AWS CLI is installed and configured
echo -e "\n${BLUE}1. AWS CLI Configuration${NC}"
echo "------------------------"

if ! command -v aws &> /dev/null; then
    print_status "error" "AWS CLI not installed"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    print_status "error" "AWS CLI not configured or no permissions"
    exit 1
else
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_status "success" "AWS CLI configured (Account: $ACCOUNT_ID)"
fi

# Check Lambda function status
echo -e "\n${BLUE}2. Lambda Function Status${NC}"
echo "---------------------------"

# Try to get function details
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" &> /dev/null; then
    print_status "success" "Lambda function '$FUNCTION_NAME' exists"
    
    # Get function details
    FUNCTION_INFO=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION")
    CODE_SIZE=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.CodeSize // 0')
    RUNTIME=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Runtime // "unknown"')
    TIMEOUT=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.Timeout // 0')
    MEMORY_SIZE=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.MemorySize // 0')
    LAST_MODIFIED=$(echo "$FUNCTION_INFO" | jq -r '.Configuration.LastModified // "unknown"')
    
    echo "   Runtime: $RUNTIME"
    echo "   Code Size: $((CODE_SIZE / 1024 / 1024)) MB"
    echo "   Timeout: ${TIMEOUT}s"
    echo "   Memory: ${MEMORY_SIZE}MB"
    echo "   Last Modified: $LAST_MODIFIED"
    
    # Check if code size exceeds limit
    if [ "$CODE_SIZE" -gt 262144000 ]; then  # 250MB in bytes
        print_status "warning" "Code size exceeds Lambda limit (250MB)"
    else
        print_status "success" "Code size within Lambda limits"
    fi
else
    print_status "error" "Lambda function '$FUNCTION_NAME' not found"
    echo "   Trying alternative function names..."
    
    # Try to list functions and find VyaparAI related ones
    FUNCTIONS=$(aws lambda list-functions --region "$AWS_REGION" --query 'Functions[?contains(FunctionName, `vyaparai`) || contains(FunctionName, `VyaparAI`)].FunctionName' --output text)
    
    if [ -n "$FUNCTIONS" ]; then
        echo "   Found VyaparAI functions:"
        for func in $FUNCTIONS; do
            echo "   - $func"
        done
    else
        print_status "error" "No VyaparAI Lambda functions found"
    fi
fi

# Test Lambda Function URL
echo -e "\n${BLUE}3. Lambda Function URL Test${NC}"
echo "----------------------------"

if curl -s -o /dev/null -w "HTTP Status: %{http_code}, Response Time: %{time_total}s\n" "$LAMBDA_URL/health" 2>/dev/null; then
    print_status "success" "Lambda Function URL is accessible"
else
    print_status "error" "Lambda Function URL is not accessible"
    echo "   URL: $LAMBDA_URL"
fi

# Test API endpoints
echo -e "\n${BLUE}4. API Endpoints Test${NC}"
echo "----------------------"

ENDPOINTS=(
    "/health"
    "/api/v1/auth/send-otp"
    "/api/v1/orders"
    "/api/v1/orders/test/generate-order"
)

for endpoint in "${ENDPOINTS[@]}"; do
    echo -n "Testing $endpoint... "
    
    if [ "$endpoint" = "/api/v1/auth/send-otp" ]; then
        # POST request for send-otp
        RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nTIME:%{time_total}" -X POST \
            -H "Content-Type: application/json" \
            -d '{"phone": "+919876543210"}' \
            "$LAMBDA_URL$endpoint" 2>/dev/null || echo "FAILED")
    elif [ "$endpoint" = "/api/v1/orders/test/generate-order" ]; then
        # POST request for generate-order
        RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nTIME:%{time_total}" -X POST \
            -H "Content-Type: application/json" \
            "$LAMBDA_URL$endpoint" 2>/dev/null || echo "FAILED")
    else
        # GET request for other endpoints
        RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nTIME:%{time_total}" \
            "$LAMBDA_URL$endpoint" 2>/dev/null || echo "FAILED")
    fi
    
    HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
    RESPONSE_TIME=$(echo "$RESPONSE" | grep "TIME:" | cut -d: -f2)
    
    if [ "$HTTP_STATUS" = "200" ]; then
        print_status "success" "✅ (${HTTP_STATUS}) ${RESPONSE_TIME}s"
    elif [ "$HTTP_STATUS" = "404" ]; then
        print_status "warning" "⚠️  (${HTTP_STATUS}) Endpoint not found"
    else
        print_status "error" "❌ (${HTTP_STATUS}) Failed"
    fi
done

# Check CloudWatch logs
echo -e "\n${BLUE}5. CloudWatch Logs${NC}"
echo "-------------------"

LOG_GROUP="/aws/lambda/$FUNCTION_NAME"

if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region "$AWS_REGION" &> /dev/null; then
    print_status "success" "CloudWatch log group exists"
    
    # Get recent log streams
    RECENT_STREAMS=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --max-items 3 \
        --region "$AWS_REGION" \
        --query 'logStreams[].logStreamName' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$RECENT_STREAMS" ]; then
        echo "   Recent log streams:"
        for stream in $RECENT_STREAMS; do
            echo "   - $stream"
        done
    fi
else
    print_status "warning" "CloudWatch log group not found"
fi

# Performance metrics
echo -e "\n${BLUE}6. Performance Metrics${NC}"
echo "------------------------"

# Test response time for health endpoint
HEALTH_RESPONSE=$(curl -s -w "\nTIME:%{time_total}\nSIZE:%{size_download}\n" "$LAMBDA_URL/health" 2>/dev/null || echo "FAILED")
RESPONSE_TIME=$(echo "$HEALTH_RESPONSE" | grep "TIME:" | cut -d: -f2)
RESPONSE_SIZE=$(echo "$HEALTH_RESPONSE" | grep "SIZE:" | cut -d: -f2)

if [ "$RESPONSE_TIME" != "" ] && [ "$RESPONSE_TIME" != "FAILED" ]; then
    echo "   Health endpoint response time: ${RESPONSE_TIME}s"
    echo "   Response size: ${RESPONSE_SIZE} bytes"
    
    if (( $(echo "$RESPONSE_TIME < 1" | bc -l) )); then
        print_status "success" "Response time is good (< 1s)"
    elif (( $(echo "$RESPONSE_TIME < 3" | bc -l) )); then
        print_status "warning" "Response time is acceptable (< 3s)"
    else
        print_status "error" "Response time is slow (> 3s)"
    fi
else
    print_status "error" "Could not measure performance"
fi

# Summary
echo -e "\n${BLUE}📊 DEPLOYMENT SUMMARY${NC}"
echo "======================"

# Count successful checks
SUCCESS_COUNT=0
TOTAL_CHECKS=6

# This is a simplified summary - in a real script you'd track each check
print_status "success" "Deployment status check completed"
echo ""
echo "Next steps:"
echo "1. Review any warnings or errors above"
echo "2. Check CloudWatch logs for detailed error information"
echo "3. Monitor Lambda function metrics in AWS Console"
echo "4. Consider optimizing package size if needed"

echo -e "\n${BLUE}📄 Detailed logs available in CloudWatch${NC}"
echo "Log Group: /aws/lambda/$FUNCTION_NAME"
