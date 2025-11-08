#!/bin/bash

# Test real-time order flow script
# This script tests the complete flow from login to order generation

set -e

echo "🧪 Testing VyaparAI Real-time Order Flow"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"
API_BASE_URL="${BACKEND_URL}/api/v1"

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "info") echo -e "${BLUE}ℹ️  $message${NC}" ;;
        "success") echo -e "${GREEN}✅ $message${NC}" ;;
        "warning") echo -e "${YELLOW}⚠️  $message${NC}" ;;
        "error") echo -e "${RED}❌ $message${NC}" ;;
    esac
}

# Function to check if service is running
check_service() {
    local url=$1
    local service_name=$2
    
    print_status "info" "Checking $service_name at $url"
    
    if curl -s --max-time 5 "$url" > /dev/null; then
        print_status "success" "$service_name is running"
        return 0
    else
        print_status "error" "$service_name is not running at $url"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "info" "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --max-time 5 "$url" > /dev/null; then
            print_status "success" "$service_name is ready!"
            return 0
        fi
        
        print_status "warning" "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_status "error" "$service_name failed to start after $max_attempts attempts"
    return 1
}

# Check if required tools are available
check_requirements() {
    print_status "info" "Checking requirements..."
    
    if ! command -v curl &> /dev/null; then
        print_status "error" "curl is required but not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        print_status "warning" "jq is not installed. Installing JSON parsing manually..."
        JQ_AVAILABLE=false
    else
        JQ_AVAILABLE=true
    fi
    
    print_status "success" "Requirements check completed"
}

# Test backend health
test_backend_health() {
    print_status "info" "Testing backend health..."
    
    local health_url="${BACKEND_URL}/health"
    local response=$(curl -s "$health_url")
    
    if [ "$JQ_AVAILABLE" = true ]; then
        local status=$(echo "$response" | jq -r '.status // "unknown"')
        if [ "$status" = "healthy" ]; then
            print_status "success" "Backend health check passed"
        else
            print_status "error" "Backend health check failed: $response"
            return 1
        fi
    else
        if echo "$response" | grep -q "healthy"; then
            print_status "success" "Backend health check passed"
        else
            print_status "error" "Backend health check failed: $response"
            return 1
        fi
    fi
}

# Test authentication
test_authentication() {
    print_status "info" "Testing authentication..."
    
    local login_url="${API_BASE_URL}/auth/login"
    local login_data='{"phone": "+919876543210", "otp": "1234"}'
    
    local response=$(curl -s -X POST "$login_url" \
        -H "Content-Type: application/json" \
        -d "$login_data")
    
    if [ "$JQ_AVAILABLE" = true ]; then
        local token=$(echo "$response" | jq -r '.token // empty')
        if [ -n "$token" ]; then
            print_status "success" "Authentication successful"
            echo "$token" > /tmp/vyaparai_token.txt
            return 0
        else
            print_status "error" "Authentication failed: $response"
            return 1
        fi
    else
        if echo "$response" | grep -q "token"; then
            print_status "success" "Authentication successful"
            echo "$response" | grep -o '"token":"[^"]*"' | cut -d'"' -f4 > /tmp/vyaparai_token.txt
            return 0
        else
            print_status "error" "Authentication failed: $response"
            return 1
        fi
    fi
}

# Test order generation
test_order_generation() {
    print_status "info" "Testing order generation..."
    
    local token=$(cat /tmp/vyaparai_token.txt 2>/dev/null || echo "")
    if [ -z "$token" ]; then
        print_status "error" "No authentication token available"
        return 1
    fi
    
    local order_url="${API_BASE_URL}/orders/test/generate-order"
    local order_data='{"store_id": "STORE-001", "customer_name": "Test Customer", "customer_phone": "+919876543210"}'
    
    local response=$(curl -s -X POST "$order_url" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $token" \
        -d "$order_data")
    
    if [ "$JQ_AVAILABLE" = true ]; then
        local success=$(echo "$response" | jq -r '.success // false')
        if [ "$success" = "true" ]; then
            local order_id=$(echo "$response" | jq -r '.order_id // empty')
            print_status "success" "Test order generated successfully: $order_id"
            return 0
        else
            print_status "error" "Order generation failed: $response"
            return 1
        fi
    else
        if echo "$response" | grep -q '"success":true'; then
            local order_id=$(echo "$response" | grep -o '"order_id":"[^"]*"' | cut -d'"' -f4)
            print_status "success" "Test order generated successfully: $order_id"
            return 0
        else
            print_status "error" "Order generation failed: $response"
            return 1
        fi
    fi
}

# Test WebSocket connection
test_websocket() {
    print_status "info" "Testing WebSocket connection..."
    
    # This is a basic test - in a real scenario you'd use a WebSocket client
    local ws_url=$(echo "$BACKEND_URL" | sed 's/http/ws/')
    print_status "info" "WebSocket URL: ${ws_url}/socket.io"
    
    # For now, just check if the endpoint is accessible
    local response=$(curl -s -I "${BACKEND_URL}/socket.io/" | head -1)
    if echo "$response" | grep -q "200\|101"; then
        print_status "success" "WebSocket endpoint is accessible"
    else
        print_status "warning" "WebSocket endpoint may not be accessible: $response"
    fi
}

# Test frontend
test_frontend() {
    print_status "info" "Testing frontend..."
    
    if curl -s --max-time 5 "$FRONTEND_URL" > /dev/null; then
        print_status "success" "Frontend is accessible at $FRONTEND_URL"
        print_status "info" "Open $FRONTEND_URL in your browser to see the dashboard"
    else
        print_status "error" "Frontend is not accessible at $FRONTEND_URL"
        return 1
    fi
}

# Main test flow
main() {
    echo ""
    print_status "info" "Starting VyaparAI real-time order flow test"
    echo ""
    
    # Check requirements
    check_requirements
    echo ""
    
    # Check services
    if ! check_service "$BACKEND_URL" "Backend"; then
        print_status "error" "Please start the backend first: cd vyaparai/backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
        exit 1
    fi
    
    if ! check_service "$FRONTEND_URL" "Frontend"; then
        print_status "error" "Please start the frontend first: cd vyaparai/frontend-pwa && npm run dev"
        exit 1
    fi
    
    echo ""
    
    # Wait for services to be fully ready
    wait_for_service "$BACKEND_URL" "Backend"
    wait_for_service "$FRONTEND_URL" "Frontend"
    echo ""
    
    # Run tests
    test_backend_health
    echo ""
    
    test_authentication
    echo ""
    
    test_order_generation
    echo ""
    
    test_websocket
    echo ""
    
    test_frontend
    echo ""
    
    # Summary
    print_status "success" "🎉 All tests completed successfully!"
    echo ""
    print_status "info" "Next steps:"
    echo "  1. Open $FRONTEND_URL in your browser"
    echo "  2. Login with phone: +919876543210, OTP: 1234"
    echo "  3. Click 'Generate Test Order' to see real-time updates"
    echo "  4. Watch for WebSocket events in the browser console"
    echo ""
    print_status "info" "Expected flow:"
    echo "  📱 Login → 📊 Dashboard → 🔘 Generate Order → 📦 Real-time Order Display"
    echo ""
}

# Cleanup function
cleanup() {
    rm -f /tmp/vyaparai_token.txt
}

# Set up cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"
