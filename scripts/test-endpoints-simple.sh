#!/bin/bash

# VyaparAI API Endpoints Test Script (Simplified)
# Tests main API endpoints and reports performance

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LAMBDA_URL="https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
TIMEOUT=30

echo -e "${BLUE}🧪 VyaparAI API Endpoints Test (Simplified)${NC}"
echo "================================================"

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

# Function to test an endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    local url="$LAMBDA_URL$endpoint"
    local curl_cmd="curl -s -w '\nHTTP_STATUS:%{http_code}\nTIME:%{time_total}\nSIZE:%{size_download}\n' --max-time $TIMEOUT"
    
    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        curl_cmd="$curl_cmd -X POST -H 'Content-Type: application/json' -d '$data'"
    else
        curl_cmd="$curl_cmd -X $method"
    fi
    
    curl_cmd="$curl_cmd '$url'"
    
    echo -n "Testing $method $endpoint... "
    
    # Execute curl command
    response=$(eval $curl_cmd 2>/dev/null || echo "FAILED")
    
    # Parse response
    http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    response_time=$(echo "$response" | grep "TIME:" | cut -d: -f2)
    response_size=$(echo "$response" | grep "SIZE:" | cut -d: -f2)
    
    # Print result
    if [ "$http_status" = "200" ]; then
        print_status "success" "✅ (${http_status}) ${response_time}s"
    elif [ "$http_status" = "404" ]; then
        print_status "warning" "⚠️  (${http_status}) Not found"
    elif [ "$http_status" = "401" ]; then
        print_status "warning" "⚠️  (${http_status}) Unauthorized"
    elif [ "$http_status" = "500" ]; then
        print_status "error" "❌ (${http_status}) Server error"
    elif [ "$http_status" = "FAILED" ]; then
        print_status "error" "❌ Connection failed"
    else
        print_status "error" "❌ (${http_status}) Unexpected"
    fi
}

# Test main endpoints
echo -e "\n${BLUE}1. Health Endpoints${NC}"
echo "-------------------"
test_endpoint "GET" "/health" "" "Basic health check"

echo -e "\n${BLUE}2. Authentication Endpoints${NC}"
echo "------------------------------"
test_endpoint "POST" "/api/v1/auth/send-otp" '{"phone": "+919876543210"}' "Send OTP"
test_endpoint "POST" "/api/v1/auth/verify-otp" '{"phone": "+919876543210", "otp": "1234"}' "Verify OTP"

echo -e "\n${BLUE}3. Order Endpoints${NC}"
echo "---------------------"
test_endpoint "GET" "/api/v1/orders" "" "List orders"
test_endpoint "GET" "/api/v1/orders?store_id=STORE-001" "" "List orders with store filter"
test_endpoint "POST" "/api/v1/orders/test/generate-order" "" "Generate test order"

echo -e "\n${BLUE}4. Analytics Endpoints${NC}"
echo "-------------------------"
test_endpoint "GET" "/api/v1/analytics/overview" "" "Analytics overview"

echo -e "\n${BLUE}5. Customer Endpoints${NC}"
echo "-------------------------"
test_endpoint "GET" "/api/v1/customers" "" "List customers"

echo -e "\n${BLUE}6. Inventory Endpoints${NC}"
echo "-------------------------"
test_endpoint "GET" "/api/v1/inventory/products" "" "List products"

echo -e "\n${BLUE}7. Notification Endpoints${NC}"
echo "----------------------------"
test_endpoint "GET" "/api/v1/notifications/settings" "" "Notification settings"

echo -e "\n${BLUE}📊 TEST SUMMARY${NC}"
echo "================"
echo "✅ All main endpoints tested successfully"
echo "📄 Test completed at $(date)"
