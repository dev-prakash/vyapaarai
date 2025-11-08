#!/bin/bash

# VyaparAI Order Flow Test Script
# Tests the complete flow from RCS/WhatsApp to PWA dashboard

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"
STORE_ID="STORE-001"
CUSTOMER_PHONE="+919876543210"

echo -e "${BLUE}🧪 VyaparAI Order Flow Test${NC}"
echo "=================================="

# Function to print status
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if service is running
check_service() {
    local url=$1
    local service_name=$2
    
    print_status "Checking if $service_name is running at $url..."
    
    if curl -s --max-time 5 "$url/health" > /dev/null 2>&1; then
        print_success "$service_name is running"
        return 0
    else
        print_error "$service_name is not running at $url"
        return 1
    fi
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s --max-time 5 "$url/health" > /dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start after $max_attempts attempts"
    return 1
}

# Function to send test RCS message
send_test_rcs_message() {
    local message=$1
    local order_type=$2
    
    print_status "Sending $order_type RCS message..."
    
    local response=$(curl -s -X POST "$BACKEND_URL/api/v1/webhooks/rcs" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$message\",
            \"phone\": \"$CUSTOMER_PHONE\",
            \"store_id\": \"$STORE_ID\",
            \"channel\": \"rcs\"
        }")
    
    if [ $? -eq 0 ]; then
        print_success "RCS message sent successfully"
        echo "Response: $response"
        return 0
    else
        print_error "Failed to send RCS message"
        return 1
    fi
}

# Function to send test WhatsApp message
send_test_whatsapp_message() {
    local message=$1
    local order_type=$2
    
    print_status "Sending $order_type WhatsApp message..."
    
    local response=$(curl -s -X POST "$BACKEND_URL/api/v1/webhooks/whatsapp" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$message\",
            \"phone\": \"$CUSTOMER_PHONE\",
            \"store_id\": \"$STORE_ID\",
            \"channel\": \"whatsapp\"
        }")
    
    if [ $? -eq 0 ]; then
        print_success "WhatsApp message sent successfully"
        echo "Response: $response"
        return 0
    else
        print_error "Failed to send WhatsApp message"
        return 1
    fi
}

# Function to generate test order via API
generate_test_order() {
    local order_type=$1
    
    print_status "Generating $order_type test order via API..."
    
    local response=$(curl -s -X POST "$BACKEND_URL/api/v1/orders/test/generate-order" \
        -H "Content-Type: application/json" \
        -d "{
            \"store_id\": \"$STORE_ID\",
            \"order_type\": \"$order_type\"
        }")
    
    if [ $? -eq 0 ]; then
        print_success "Test order generated successfully"
        echo "Response: $response"
        return 0
    else
        print_error "Failed to generate test order"
        return 1
    fi
}

# Function to check WebSocket connection
check_websocket_connection() {
    print_status "Checking WebSocket connection..."
    
    # This is a basic check - in a real scenario you'd need a WebSocket client
    local response=$(curl -s -I "$BACKEND_URL/socket.io/" 2>/dev/null | head -1)
    
    if echo "$response" | grep -q "HTTP"; then
        print_success "WebSocket endpoint is accessible"
        return 0
    else
        print_warning "WebSocket endpoint check failed (this is expected if not using Socket.IO)"
        return 0
    fi
}

# Function to open frontend in browser
open_frontend() {
    print_status "Opening frontend in browser..."
    
    if command -v open >/dev/null 2>&1; then
        open "$FRONTEND_URL"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$FRONTEND_URL"
    else
        print_warning "Could not open browser automatically. Please open: $FRONTEND_URL"
    fi
}

# Main test flow
main() {
    echo
    print_status "Starting VyaparAI order flow test..."
    
    # Check if backend is running
    if ! check_service "$BACKEND_URL" "Backend"; then
        print_error "Backend is not running. Please start it first:"
        echo "  cd vyaparai && docker-compose -f docker-compose.dev.yml up -d"
        exit 1
    fi
    
    # Wait for backend to be fully ready
    if ! wait_for_service "$BACKEND_URL" "Backend"; then
        exit 1
    fi
    
    # Check WebSocket connection
    check_websocket_connection
    
    echo
    print_status "Testing different order scenarios..."
    
    # Test 1: Simple grocery order via RCS
    send_test_rcs_message "2 kg rice, 1 litre oil, 500g sugar" "simple grocery"
    
    sleep 3
    
    # Test 2: Breakfast order via WhatsApp
    send_test_whatsapp_message "mujhe breakfast ke liye bread, milk, eggs chahiye" "breakfast"
    
    sleep 3
    
    # Test 3: Bulk order via API
    generate_test_order "bulk"
    
    sleep 3
    
    # Test 4: Lunch order via RCS
    send_test_rcs_message "lunch ke liye 1kg chicken, 2kg rice, vegetables" "lunch"
    
    sleep 3
    
    # Test 5: Snacks order via WhatsApp
    send_test_whatsapp_message "evening snacks: chips, coke, biscuits" "snacks"
    
    echo
    print_success "All test messages sent successfully!"
    
    echo
    print_status "Opening PWA dashboard to verify orders..."
    open_frontend
    
    echo
    print_status "Test completed! Check the PWA dashboard for new orders."
    echo
    echo "Expected flow:"
    echo "1. ✅ Messages sent to backend"
    echo "2. ✅ Backend processes orders"
    echo "3. ✅ WebSocket events emitted"
    echo "4. 🔄 PWA receives real-time updates"
    echo "5. 🔄 Store owner sees new orders"
    echo "6. 🔄 Store owner can accept/reject orders"
    echo
    echo "Dashboard URL: $FRONTEND_URL"
    echo "Backend API: $BACKEND_URL"
    echo "API Documentation: $BACKEND_URL/docs"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -b, --backend  Backend URL (default: http://localhost:8000)"
    echo "  -f, --frontend Frontend URL (default: http://localhost:3000)"
    echo "  -s, --store    Store ID (default: STORE-001)"
    echo "  -p, --phone    Customer phone (default: +919876543210)"
    echo
    echo "Examples:"
    echo "  $0                                    # Run with default settings"
    echo "  $0 -b http://localhost:8000          # Custom backend URL"
    echo "  $0 -s STORE-002                      # Custom store ID"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -b|--backend)
            BACKEND_URL="$2"
            shift 2
            ;;
        -f|--frontend)
            FRONTEND_URL="$2"
            shift 2
            ;;
        -s|--store)
            STORE_ID="$2"
            shift 2
            ;;
        -p|--phone)
            CUSTOMER_PHONE="$2"
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Run main function
main "$@"
