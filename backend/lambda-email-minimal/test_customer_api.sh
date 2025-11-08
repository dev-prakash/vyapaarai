#!/bin/bash

API_BASE="https://api.vyaparai.com"

echo "=== Testing Customer Registration ==="
REGISTER_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/customers/register" \
  -H "Content-Type: application/json" \
  -d "{\"phone\":\"+919876543210\",\"first_name\":\"Raj\",\"last_name\":\"Kumar\",\"email\":\"raj.kumar@test.com\"}")

echo "$REGISTER_RESPONSE" | python3 -m json.tool
echo ""

# Extract customer_id and token
CUSTOMER_ID=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('customer', {}).get('customer_id', ''))" 2>/dev/null || echo "")
TOKEN=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('token', ''))" 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    echo "=== Testing Get Profile ==="
    curl -s -X GET "$API_BASE/api/v1/customers/profile" \
      -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
    echo ""

    echo "=== Testing Add Address ==="
    curl -s -X POST "$API_BASE/api/v1/customers/addresses" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"line1\":\"123 MG Road\",\"line2\":\"Apartment 4B\",\"city\":\"Bangalore\",\"state\":\"Karnataka\",\"pincode\":\"560001\",\"phone\":\"+919876543210\",\"landmark\":\"Near Metro\",\"type\":\"home\",\"is_default\":true}" | python3 -m json.tool
    echo ""

    echo "=== Testing Add UPI Payment Method ==="
    curl -s -X POST "$API_BASE/api/v1/customers/payment-methods" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"type\":\"upi\",\"upi_id\":\"raj@paytm\",\"provider\":\"paytm\",\"is_default\":true}" | python3 -m json.tool
    echo ""

    echo "=== Testing Updated Profile ==="
    curl -s -X GET "$API_BASE/api/v1/customers/profile" \
      -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
    echo ""
fi

echo "=== All tests completed ==="
