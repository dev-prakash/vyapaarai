#!/bin/bash

echo "🧪 Testing Complete VyaparAI Order Flow"
echo "======================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
echo -e "${YELLOW}1. Checking services...${NC}"
curl -s http://localhost:8000/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Backend is running${NC}"
else
    echo "❌ Backend is not running. Start it with: ./scripts/start-local.sh"
    exit 1
fi

curl -s http://localhost:3000 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend is running${NC}"
else
    echo "❌ Frontend is not running. Start it with: ./scripts/start-local.sh"
    exit 1
fi

# Test 1: Health Check
echo -e "\n${YELLOW}2. Testing API Health...${NC}"
curl -s http://localhost:8000/health | python -m json.tool

# Test 2: Send RCS Webhook
echo -e "\n${YELLOW}3. Sending test order via RCS webhook...${NC}"
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/webhooks/rcs \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "text": "भाई, 2 kg basmati rice, 1 litre fortune oil, 500g tata salt भेज दो",
      "messageId": "test-msg-001"
    },
    "senderPhoneNumber": "+919876543210",
    "agentId": "vyaparai-agent"
  }')

echo $RESPONSE | python -m json.tool
ORDER_ID=$(echo $RESPONSE | python -c "import sys, json; print(json.load(sys.stdin).get('order_id', ''))" 2>/dev/null)

if [ -z "$ORDER_ID" ]; then
    echo "❌ Failed to create order"
    exit 1
fi

echo -e "${GREEN}✓ Order created: $ORDER_ID${NC}"

# Test 3: Check WebSocket
echo -e "\n${YELLOW}4. Check PWA Dashboard...${NC}"
echo "📱 Open http://localhost:3000 in your browser"
echo "👀 You should see the new order appear in real-time!"

# Test 4: Get order details
echo -e "\n${YELLOW}5. Fetching order details...${NC}"
sleep 2
curl -s http://localhost:8000/api/v1/orders/$ORDER_ID | python -m json.tool

# Test 5: Accept order
echo -e "\n${YELLOW}6. Accepting order...${NC}"
curl -s -X POST http://localhost:8000/api/v1/orders/confirm/$ORDER_ID | python -m json.tool

echo -e "\n${GREEN}✅ Complete flow test successful!${NC}"
echo "Check the PWA dashboard to see the order status updated to 'accepted'"
