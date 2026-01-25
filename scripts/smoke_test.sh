#!/bin/bash
# =============================================================================
# VyapaarAI Post-Deployment Smoke Tests
# Run after every deployment to verify critical endpoints are working.
#
# Usage:
#   ./scripts/smoke_test.sh [prod|dev]
#   ./scripts/smoke_test.sh              # defaults to prod
#
# Author: DevPrakash
# =============================================================================

set -e

# Configuration
ENV="${1:-prod}"

if [ "$ENV" = "prod" ]; then
    API_BASE="https://api.vyapaarai.com"
elif [ "$ENV" = "dev" ]; then
    API_BASE="https://api-dev.vyapaarai.com"
else
    echo "Unknown environment: $ENV"
    echo "Usage: $0 [prod|dev]"
    exit 1
fi

API_URL="$API_BASE/api/v1"

echo "=============================================="
echo " VyapaarAI Smoke Tests"
echo "=============================================="
echo "Environment: $ENV"
echo "API Base: $API_BASE"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

PASS=0
FAIL=0

# Function to run a test
run_test() {
    local name="$1"
    local expected_code="$2"
    local method="$3"
    local endpoint="$4"
    local data="$5"

    echo -n "Testing: $name... "

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint" 2>/dev/null)
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint" 2>/dev/null)
    fi

    # Extract status code (last line) and body (everything else)
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" = "$expected_code" ]; then
        echo "PASS (HTTP $http_code)"
        ((PASS++))
        return 0
    else
        echo "FAIL (expected $expected_code, got $http_code)"
        echo "  Response: $(echo "$body" | head -c 200)"
        ((FAIL++))
        return 1
    fi
}

# Function to run a test and check response content
run_test_with_content() {
    local name="$1"
    local expected_code="$2"
    local method="$3"
    local endpoint="$4"
    local data="$5"
    local expected_content="$6"

    echo -n "Testing: $name... "

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint" 2>/dev/null)
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint" 2>/dev/null)
    fi

    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" != "$expected_code" ]; then
        echo "FAIL (expected HTTP $expected_code, got $http_code)"
        echo "  Response: $(echo "$body" | head -c 200)"
        ((FAIL++))
        return 1
    fi

    if echo "$body" | grep -q "$expected_content"; then
        echo "PASS (HTTP $http_code, content verified)"
        ((PASS++))
        return 0
    else
        echo "FAIL (HTTP $http_code, missing expected content: $expected_content)"
        echo "  Response: $(echo "$body" | head -c 200)"
        ((FAIL++))
        return 1
    fi
}

echo ""
echo "=== Health & Basic Connectivity ==="

# Test 1: API is reachable
run_test "API Health Check" "200" "GET" "/health" || true

echo ""
echo "=== CRITICAL: Store Owner Login Flow ==="

# Test 2: Store verification endpoint (the bug we just fixed)
run_test_with_content \
    "Store Verification - Valid Email" \
    "200" \
    "POST" \
    "/stores/verify" \
    '{"email": "dev.prakash@gmail.com"}' \
    '"success":true' || true

# Test 3: Store verification with invalid email
run_test \
    "Store Verification - Invalid Email (404 expected)" \
    "404" \
    "POST" \
    "/stores/verify" \
    '{"email": "nonexistent@test.com"}' || true

echo ""
echo "=== GST System ==="

# Test 4: GST categories list
run_test_with_content \
    "GST Categories List" \
    "200" \
    "GET" \
    "/gst/categories" \
    "[" || true

# Test 5: GST rates reference
run_test_with_content \
    "GST Rates Reference" \
    "200" \
    "GET" \
    "/gst/rates" \
    '"rates"' || true

# Test 6: GST HSN lookup
run_test_with_content \
    "GST HSN Lookup (1905 = Biscuits)" \
    "200" \
    "GET" \
    "/gst/hsn/1905" \
    '"gst_rate"' || true

echo ""
echo "=== Customer Authentication ==="

# Test 7: Customer OTP request (should work even with unknown phone)
run_test \
    "Customer OTP Request" \
    "200" \
    "POST" \
    "/customers/auth/otp/request" \
    '{"phone": "+919999999999"}' || true

echo ""
echo "=============================================="
echo " RESULTS"
echo "=============================================="
echo " Passed: $PASS"
echo " Failed: $FAIL"
echo "=============================================="

if [ $FAIL -gt 0 ]; then
    echo ""
    echo "WARNING: Some smoke tests failed!"
    echo "Check the deployment and logs before proceeding."
    exit 1
else
    echo ""
    echo "All smoke tests passed!"
    exit 0
fi
