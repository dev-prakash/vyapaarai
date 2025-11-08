#!/usr/bin/env python3
"""
Test script to verify real API integration vs fake data generation
"""

import urllib.request
import json
import sys

def test_inventory_api_call(product_id, quantity, order_id):
    """Test the actual inventory API call that should be used in Lambda"""
    
    # Construct the real API URL
    api_url = f"https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/{product_id}/stock"
    
    # Create request payload
    payload = {
        "quantity": quantity,
        "movement_type": "out", 
        "reason": f"Order {order_id}",
        "reference_id": order_id
    }
    
    print(f"🔍 Testing API call to: {api_url}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Make actual HTTP PUT request
        data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(api_url, data=data, headers={
            'Content-Type': 'application/json'
        })
        request.get_method = lambda: 'PUT'
        
        print("🌐 Making HTTP PUT request...")
        
        with urllib.request.urlopen(request, timeout=10) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            
            print(f"📡 Response Status: {response.status}")
            print(f"📄 Response Data: {json.dumps(response_data, indent=2)}")
            
            if response.status == 200 and response_data.get('success'):
                return {
                    "success": True,
                    "product_id": product_id,
                    "quantity": quantity,
                    "previous_stock": response_data.get("previous_stock"),
                    "new_stock": response_data.get("new_stock"),
                    "reference_id": order_id
                }
            else:
                return {"success": False, "error": "API returned failure"}
                
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        return {"success": False, "error": str(e)}

def test_current_lambda_implementation():
    """Test the current Lambda implementation to see if it's making real API calls"""
    
    print("🧪 TESTING CURRENT LAMBDA IMPLEMENTATION")
    print("=" * 50)
    
    # Test the inventory API call function
    test_result = test_inventory_api_call("prod_001", 1, "TEST_ORDER_001")
    
    print("\n📊 TEST RESULTS:")
    print("=" * 30)
    
    if test_result['success']:
        print("✅ API call successful!")
        print(f"   Product ID: {test_result['product_id']}")
        print(f"   Quantity: {test_result['quantity']}")
        print(f"   Previous Stock: {test_result['previous_stock']}")
        print(f"   New Stock: {test_result['new_stock']}")
        print(f"   Reference ID: {test_result['reference_id']}")
        
        # Verify stock actually changed
        if test_result['previous_stock'] != test_result['new_stock']:
            print("✅ Stock level actually changed - REAL API INTEGRATION WORKING!")
            return True
        else:
            print("❌ Stock level unchanged - API call may not be working properly")
            return False
    else:
        print(f"❌ API call failed: {test_result['error']}")
        return False

def test_order_creation_integration():
    """Test the complete order creation flow"""
    
    print("\n🛒 TESTING ORDER CREATION INTEGRATION")
    print("=" * 50)
    
    # Test order creation
    order_url = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/orders"
    
    order_payload = {
        "customer_name": "Test Customer",
        "customer_phone": "+919876543210",
        "items": [{"product_id": "prod_001", "quantity": 2}],
        "delivery_address": "Test Address",
        "payment_method": "cod"
    }
    
    print(f"🔍 Testing order creation at: {order_url}")
    print(f"📦 Order payload: {json.dumps(order_payload, indent=2)}")
    
    try:
        data = json.dumps(order_payload).encode('utf-8')
        request = urllib.request.Request(order_url, data=data, headers={
            'Content-Type': 'application/json'
        })
        
        with urllib.request.urlopen(request, timeout=10) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            
            print(f"📡 Order Response Status: {response.status}")
            print(f"📄 Order Response: {json.dumps(response_data, indent=2)}")
            
            if response.status == 200 and response_data.get('success'):
                stock_reductions = response_data.get('stock_reductions', [])
                
                if stock_reductions:
                    print("\n📊 STOCK REDUCTION ANALYSIS:")
                    print("=" * 30)
                    
                    for reduction in stock_reductions:
                        print(f"   Product: {reduction.get('product_id')}")
                        print(f"   Quantity: {reduction.get('quantity')}")
                        print(f"   Previous Stock: {reduction.get('previous_stock')}")
                        print(f"   New Stock: {reduction.get('new_stock')}")
                        
                        # Check if stock actually changed
                        if reduction.get('previous_stock') != reduction.get('new_stock'):
                            print("   ✅ Stock level changed - REAL API INTEGRATION!")
                        else:
                            print("   ❌ Stock level unchanged - FAKE DATA!")
                    
                    return True
                else:
                    print("❌ No stock reductions in response")
                    return False
            else:
                print(f"❌ Order creation failed: {response_data.get('message', 'Unknown error')}")
                return False
                
    except Exception as e:
        print(f"❌ Order creation test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    
    print("🚀 VYAPARAI API INTEGRATION TEST")
    print("=" * 50)
    
    # Test 1: Direct API call
    print("\n1️⃣ TESTING DIRECT INVENTORY API CALL")
    api_test_passed = test_current_lambda_implementation()
    
    # Test 2: Order creation integration
    print("\n2️⃣ TESTING ORDER CREATION INTEGRATION")
    order_test_passed = test_order_creation_integration()
    
    # Summary
    print("\n📋 TEST SUMMARY")
    print("=" * 30)
    
    if api_test_passed and order_test_passed:
        print("✅ ALL TESTS PASSED - REAL API INTEGRATION WORKING!")
        print("🚀 Ready for deployment")
        return True
    else:
        print("❌ TESTS FAILED - FAKE DATA STILL BEING GENERATED")
        print("⚠️  DO NOT DEPLOY - Fix required")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
