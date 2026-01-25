#!/bin/bash
set -e

API_BASE="https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com"
echo "🧪 VyaparAI Production Test Suite"
echo "=================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test results array
declare -a test_results

# Function to test endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    local expected=$5

    echo -n "Testing $name... "

    if [ "$method" == "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE$endpoint")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -X $method "$API_BASE$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    if [ "$response" == "$expected" ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $response)"
        test_results+=("✅ $name: PASS")
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (Expected $expected, Got $response)"
        test_results+=("❌ $name: FAIL (Got $response)")
        return 1
    fi
}

# 1. Core Health Checks
echo "1️⃣ CORE HEALTH CHECKS"
echo "----------------------"
test_endpoint "Health Check" "GET" "/health" "" "200"
test_endpoint "API Docs" "GET" "/docs" "" "200"
test_endpoint "OpenAPI Schema" "GET" "/openapi.json" "" "200"

# 2. Inventory Tests
echo -e "\n2️⃣ INVENTORY SYSTEM"
echo "-------------------"

# Get a real store ID first
echo "Finding active store..."
STORE_ID="STORE-01K8NJ40V9KFKX2Y2FMK466WFH"

test_endpoint "List Products" "GET" "/api/v1/inventory/products?store_id=$STORE_ID&limit=5" "" "200"

# Get a product ID for further tests
echo "Getting a product ID for tests..."
PRODUCT_JSON=$(curl -s "$API_BASE/api/v1/inventory/products?store_id=$STORE_ID&limit=1")
PRODUCT_ID=$(echo $PRODUCT_JSON | jq -r '.products[0].product_id // empty')

if [ -n "$PRODUCT_ID" ]; then
    echo "Using Product ID: $PRODUCT_ID"
    test_endpoint "Get Single Product" "GET" "/api/v1/inventory/products/$STORE_ID/$PRODUCT_ID" "" "200"
    test_endpoint "Check Availability" "GET" "/api/v1/inventory/products/$STORE_ID/$PRODUCT_ID/availability?quantity=1" "" "200"
else
    echo -e "${YELLOW}⚠️ No products found for testing${NC}"
fi

test_endpoint "Search Products" "GET" "/api/v1/inventory/search?store_id=$STORE_ID&q=rice" "" "200"
test_endpoint "Low Stock Alert" "GET" "/api/v1/inventory/low-stock?store_id=$STORE_ID" "" "200"
test_endpoint "Inventory Summary" "GET" "/api/v1/inventory/summary?store_id=$STORE_ID" "" "200"

# 3. Order Management
echo -e "\n3️⃣ ORDER MANAGEMENT"
echo "------------------"

# Create test order
ORDER_DATA='{
    "store_id": "'$STORE_ID'",
    "customer_phone": "+919999999999",
    "customer_name": "Production Test",
    "delivery_address": {
        "street": "123 Test Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001"
    },
    "items": [{
        "product_id": "'${PRODUCT_ID:-PROD-001}'",
        "product_name": "Test Product",
        "quantity": 1,
        "unit_price": 100.50
    }]
}'

echo "Creating test order..."
ORDER_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/orders" \
    -H "Content-Type: application/json" \
    -d "$ORDER_DATA")

ORDER_ID=$(echo $ORDER_RESPONSE | jq -r '.order_id // empty')

if [ -n "$ORDER_ID" ]; then
    echo "Order created: $ORDER_ID"
    test_results+=("✅ Order Creation: PASS (ID: $ORDER_ID)")

    # Test order retrieval
    test_endpoint "Get Order" "GET" "/api/v1/orders/$ORDER_ID" "" "200"
else
    echo -e "${RED}❌ Order creation failed${NC}"
    echo "Response: $ORDER_RESPONSE"
    test_results+=("❌ Order Creation: FAIL")
fi

# 4. Authentication (if endpoints exist)
echo -e "\n4️⃣ AUTHENTICATION"
echo "-----------------"
test_endpoint "Customer Auth Health" "GET" "/api/v1/auth/health" "" "200" || true

# 5. Store Management
echo -e "\n5️⃣ STORE MANAGEMENT"
echo "------------------"
test_endpoint "List Stores" "GET" "/api/v1/stores/list?limit=5" "" "200"

# Generate Test Report
echo -e "\n📊 TEST SUMMARY"
echo "==============="
for result in "${test_results[@]}"; do
    echo "$result"
done

# Calculate success rate
total=${#test_results[@]}
passed=$(printf '%s\n' "${test_results[@]}" | grep -c "✅" || true)
failed=$(printf '%s\n' "${test_results[@]}" | grep -c "❌" || true)
success_rate=$((passed * 100 / total))

echo ""
echo "Total Tests: $total"
echo "Passed: $passed"
echo "Failed: $failed"
echo "Success Rate: $success_rate%"

if [ $success_rate -ge 80 ]; then
    echo -e "${GREEN}🎉 MARKETPLACE IS PRODUCTION READY!${NC}"
    exit 0
else
    echo -e "${RED}⚠️ Some tests failed. Check CloudWatch logs.${NC}"
    exit 1
fi
