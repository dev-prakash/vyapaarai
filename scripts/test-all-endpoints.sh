#!/bin/bash

# VyaparAI API Endpoints Test Script
# Tests all API endpoints and reports performance

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

# Test results storage (using simple variables for compatibility)
test_results=""
response_times=""
response_sizes=""

echo -e "${BLUE}🧪 VyaparAI API Endpoints Test${NC}"
echo "================================="

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
    
    # Store results
    test_results["$method:$endpoint"]="$http_status"
    response_times["$method:$endpoint"]="$response_time"
    response_sizes["$method:$endpoint"]="$response_size"
    
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

# Test all endpoints
echo -e "\n${BLUE}1. Health Endpoints${NC}"
echo "-------------------"
test_endpoint "GET" "/health" "" "Basic health check"
test_endpoint "GET" "/health/detailed" "" "Detailed health check"

echo -e "\n${BLUE}2. Authentication Endpoints${NC}"
echo "------------------------------"
test_endpoint "POST" "/api/v1/auth/send-otp" '{"phone": "+919876543210"}' "Send OTP"
test_endpoint "POST" "/api/v1/auth/verify-otp" '{"phone": "+919876543210", "otp": "1234"}' "Verify OTP"
test_endpoint "POST" "/api/v1/auth/login" '{"phone": "+919876543210", "password": "test123"}' "Login"
test_endpoint "GET" "/api/v1/auth/me" "" "Get current user"

echo -e "\n${BLUE}3. Order Endpoints${NC}"
echo "---------------------"
test_endpoint "GET" "/api/v1/orders" "" "List orders"
test_endpoint "GET" "/api/v1/orders?store_id=STORE-001" "" "List orders with store filter"
test_endpoint "POST" "/api/v1/orders/test/generate-order" "" "Generate test order"
test_endpoint "GET" "/api/v1/orders/history" "" "Order history"
test_endpoint "GET" "/api/v1/orders/stats/daily" "" "Daily statistics"
test_endpoint "GET" "/api/v1/orders/metrics" "" "Order metrics"

echo -e "\n${BLUE}4. Analytics Endpoints${NC}"
echo "-------------------------"
test_endpoint "GET" "/api/v1/analytics/overview" "" "Analytics overview"
test_endpoint "GET" "/api/v1/analytics/revenue" "" "Revenue analytics"
test_endpoint "GET" "/api/v1/analytics/orders" "" "Order analytics"

echo -e "\n${BLUE}5. Customer Endpoints${NC}"
echo "-------------------------"
test_endpoint "GET" "/api/v1/customers" "" "List customers"
test_endpoint "POST" "/api/v1/customers" '{"name": "Test Customer", "phone": "+919876543210"}' "Create customer"

echo -e "\n${BLUE}6. Inventory Endpoints${NC}"
echo "-------------------------"
test_endpoint "GET" "/api/v1/inventory/products" "" "List products"
test_endpoint "POST" "/api/v1/inventory/products" '{"name": "Test Product", "price": 100}' "Create product"

echo -e "\n${BLUE}7. Notification Endpoints${NC}"
echo "----------------------------"
test_endpoint "GET" "/api/v1/notifications/settings" "" "Notification settings"
test_endpoint "POST" "/api/v1/notifications/send" '{"message": "Test notification"}' "Send notification"

# Generate summary
echo -e "\n${BLUE}📊 TEST SUMMARY${NC}"
echo "================"

# Count results
success_count=0
warning_count=0
error_count=0
total_count=0

for key in "${!test_results[@]}"; do
    status="${test_results[$key]}"
    total_count=$((total_count + 1))
    
    if [ "$status" = "200" ]; then
        success_count=$((success_count + 1))
    elif [ "$status" = "404" ] || [ "$status" = "401" ]; then
        warning_count=$((warning_count + 1))
    else
        error_count=$((error_count + 1))
    fi
done

echo "Total endpoints tested: $total_count"
echo "Successful (200): $success_count"
echo "Warnings (404/401): $warning_count"
echo "Errors: $error_count"

# Performance analysis
echo -e "\n${BLUE}⚡ PERFORMANCE ANALYSIS${NC}"
echo "========================"

# Calculate average response time
total_time=0
valid_responses=0

for key in "${!response_times[@]}"; do
    time="${response_times[$key]}"
    if [[ "$time" =~ ^[0-9]+\.?[0-9]*$ ]]; then
        total_time=$(echo "$total_time + $time" | bc -l)
        valid_responses=$((valid_responses + 1))
    fi
done

if [ $valid_responses -gt 0 ]; then
    avg_time=$(echo "scale=3; $total_time / $valid_responses" | bc -l)
    echo "Average response time: ${avg_time}s"
    
    # Find fastest and slowest
    fastest_time=999
    slowest_time=0
    fastest_endpoint=""
    slowest_endpoint=""
    
    for key in "${!response_times[@]}"; do
        time="${response_times[$key]}"
        if [[ "$time" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            if (( $(echo "$time < $fastest_time" | bc -l) )); then
                fastest_time=$time
                fastest_endpoint=$key
            fi
            if (( $(echo "$time > $slowest_time" | bc -l) )); then
                slowest_time=$time
                slowest_endpoint=$key
            fi
        fi
    done
    
    echo "Fastest endpoint: $fastest_endpoint (${fastest_time}s)"
    echo "Slowest endpoint: $slowest_endpoint (${slowest_time}s)"
fi

# Response size analysis
echo -e "\n${BLUE}📏 RESPONSE SIZE ANALYSIS${NC}"
echo "========================="

total_size=0
valid_sizes=0

for key in "${!response_sizes[@]}"; do
    size="${response_sizes[$key]}"
    if [[ "$size" =~ ^[0-9]+$ ]]; then
        total_size=$((total_size + size))
        valid_sizes=$((valid_sizes + 1))
    fi
done

if [ $valid_sizes -gt 0 ]; then
    avg_size=$((total_size / valid_sizes))
    echo "Average response size: ${avg_size} bytes"
    echo "Total data transferred: ${total_size} bytes"
fi

# Detailed results
echo -e "\n${BLUE}📋 DETAILED RESULTS${NC}"
echo "===================="

echo "Endpoint,Method,Status,Response Time,Response Size"
for key in "${!test_results[@]}"; do
    method=$(echo "$key" | cut -d: -f1)
    endpoint=$(echo "$key" | cut -d: -f2)
    status="${test_results[$key]}"
    time="${response_times[$key]}"
    size="${response_sizes[$key]}"
    echo "$endpoint,$method,$status,$time,$size"
done

# Recommendations
echo -e "\n${BLUE}💡 RECOMMENDATIONS${NC}"
echo "=================="

if [ $error_count -gt 0 ]; then
    echo "❌ Fix failing endpoints:"
    for key in "${!test_results[@]}"; do
        status="${test_results[$key]}"
        if [ "$status" != "200" ] && [ "$status" != "404" ] && [ "$status" != "401" ]; then
            echo "  - $key: $status"
        fi
    done
fi

if [ $warning_count -gt 0 ]; then
    echo "⚠️  Review endpoints returning 404/401:"
    for key in "${!test_results[@]}"; do
        status="${test_results[$key]}"
        if [ "$status" = "404" ] || [ "$status" = "401" ]; then
            echo "  - $key: $status"
        fi
    done
fi

# Performance recommendations
if [ $valid_responses -gt 0 ]; then
    if (( $(echo "$avg_time > 1" | bc -l) )); then
        echo "🐌 Consider optimizing slow endpoints (avg > 1s)"
    fi
    
    if (( $(echo "$avg_time > 3" | bc -l) )); then
        echo "🚨 Critical: Endpoints are very slow (avg > 3s)"
    fi
fi

echo -e "\n${BLUE}📄 Test completed at $(date)${NC}"
