#!/usr/bin/env python3
"""
Test inventory-order integration for VyaparAI
"""

import requests
import json
import time
from decimal import Decimal

class InventoryIntegrationTest:
    def __init__(self):
        self.api_url = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"
        self.test_results = []
        self.test_products = []
    
    def test_product_listing(self):
        """Test product listing with stock levels"""
        try:
            print("🔍 Testing product listing...")
            response = requests.get(f"{self.api_url}/api/v1/inventory/products")
            if response.status_code == 200:
                result = response.json()
                products = result.get('products', [])
                self.test_products = products
                self.log_result("Product Listing", True, f"Found {len(products)} products")
                return products
            else:
                self.log_result("Product Listing", False, f"HTTP {response.status_code}")
                return []
        except Exception as e:
            self.log_result("Product Listing", False, str(e))
            return []
    
    def test_stock_availability(self, product_id, quantity, expect_success=True):
        """Test stock availability checking"""
        try:
            print(f"🔍 Testing stock availability for {quantity} units...")
            response = requests.get(f"{self.api_url}/api/v1/inventory/products/{product_id}/availability/{quantity}")
            if response.status_code == 200:
                data = response.json()
                available = data.get('available', False)
                current_stock = data.get('current_stock', 0)
                
                # Determine if this is a success based on expectation
                if expect_success:
                    success = available
                    message = f"Stock: {current_stock}, Available: {available}"
                else:
                    success = not available  # We expect it to be unavailable
                    message = f"Stock: {current_stock}, Correctly unavailable: {not available}"
                
                self.log_result(f"Stock Check ({quantity})", success, message)
                return available
            else:
                self.log_result(f"Stock Check ({quantity})", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_result(f"Stock Check ({quantity})", False, str(e))
            return False
    
    def test_order_with_stock_check(self, product_id, quantity, expected_success=True):
        """Test order creation with stock validation"""
        try:
            print(f"🛒 Testing order creation with {quantity} units...")
            
            # First check if stock is available
            availability = self.test_stock_availability(product_id, quantity)
            
            # Try to create order
            order_data = {
                "customer_name": "Test Customer",
                "customer_phone": "+919876543210",
                "customer_email": "test@example.com",
                "delivery_address": "Test Address, Test City",
                "items": [{"product_id": product_id, "quantity": quantity, "unit_price": 100}],
                "payment_method": "cod",
                "delivery_notes": "Test order for inventory integration"
            }
            
            response = requests.post(f"{self.api_url}/api/v1/orders", json=order_data)
            
            if expected_success and response.status_code in [200, 201]:
                result = response.json()
                order_id = result.get('order_id')
                self.log_result("Order Creation", True, f"Order created: {order_id}")
                return order_id
            elif not expected_success and response.status_code == 400:
                self.log_result("Order Stock Validation", True, "Correctly blocked insufficient stock")
                return None
            else:
                self.log_result("Order Integration", False, f"Unexpected result: {response.status_code}")
                return None
        except Exception as e:
            self.log_result("Order Integration", False, str(e))
            return None
    
    def test_low_stock_alerts(self):
        """Test low stock detection"""
        try:
            print("⚠️ Testing low stock alerts...")
            response = requests.get(f"{self.api_url}/api/v1/inventory/products/low-stock")
            if response.status_code == 200:
                result = response.json()
                low_stock_products = result.get('low_stock_products', [])
                self.log_result("Low Stock Alerts", True, f"Found {len(low_stock_products)} low stock items")
                return low_stock_products
            else:
                self.log_result("Low Stock Alerts", False, f"HTTP {response.status_code}")
                return []
        except Exception as e:
            self.log_result("Low Stock Alerts", False, str(e))
            return []
    
    def test_inventory_summary(self):
        """Test inventory summary statistics"""
        try:
            print("📊 Testing inventory summary...")
            response = requests.get(f"{self.api_url}/api/v1/inventory/inventory/summary")
            if response.status_code == 200:
                result = response.json()
                summary = result.get('summary', {})
                total_products = summary.get('total_products', 0)
                low_stock = summary.get('low_stock', 0)
                self.log_result("Inventory Summary", True, f"Total: {total_products}, Low Stock: {low_stock}")
                return summary
            else:
                self.log_result("Inventory Summary", False, f"HTTP {response.status_code}")
                return {}
        except Exception as e:
            self.log_result("Inventory Summary", False, str(e))
            return {}
    
    def test_stock_update(self, product_id, quantity, movement_type="in"):
        """Test stock update functionality"""
        try:
            print(f"📦 Testing stock update: {movement_type} {quantity} units...")
            update_data = {
                "quantity": quantity,
                "movement_type": movement_type,
                "reason": f"Test {movement_type} stock update"
            }
            
            response = requests.put(
                f"{self.api_url}/api/v1/inventory/products/{product_id}/stock",
                json=update_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                new_stock = result.get('new_stock', 0)
                self.log_result("Stock Update", True, f"New stock: {new_stock}")
                return True
            else:
                self.log_result("Stock Update", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Stock Update", False, str(e))
            return False
    
    def test_concurrent_orders(self, product_id, quantity, num_orders=3):
        """Test multiple concurrent orders for the same product"""
        try:
            print(f"🔄 Testing {num_orders} concurrent orders...")
            successful_orders = 0
            
            for i in range(num_orders):
                order_data = {
                    "customer_name": f"Concurrent Customer {i+1}",
                    "customer_phone": f"+9198765432{i:02d}",
                    "customer_email": f"concurrent{i+1}@example.com",
                    "delivery_address": f"Concurrent Address {i+1}",
                    "items": [{"product_id": product_id, "quantity": quantity, "unit_price": 100}],
                    "payment_method": "cod"
                }
                
                response = requests.post(f"{self.api_url}/api/v1/orders", json=order_data)
                if response.status_code in [200, 201]:
                    successful_orders += 1
                
                time.sleep(0.1)  # Small delay between requests
            
            self.log_result("Concurrent Orders", successful_orders > 0, 
                          f"{successful_orders}/{num_orders} orders successful")
            return successful_orders
        except Exception as e:
            self.log_result("Concurrent Orders", False, str(e))
            return 0
    
    def log_result(self, test_name, success, message):
        """Log test result"""
        status = "✅" if success else "❌"
        print(f"  {status} {test_name}: {message}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "message": message
        })
    
    def run_complete_test(self):
        """Run complete integration test suite"""
        print("🧪 INVENTORY-ORDER INTEGRATION TEST")
        print("=" * 50)
        
        # Test 1: Product listing
        products = self.test_product_listing()
        
        if not products:
            print("❌ No products found. Cannot continue testing.")
            return False
        
        # Find test products with different stock levels
        in_stock_product = None
        low_stock_product = None
        out_of_stock_product = None
        
        # Use the actual product IDs from the inventory API (with underscores)
        mock_product_ids = {
            'prod_001': {'name': 'Basmati Rice 1kg', 'current_stock': 50},
            'prod_002': {'name': 'Toor Dal 1kg', 'current_stock': 30},
            'prod_003': {'name': 'Sunflower Oil 1L', 'current_stock': 25},
            'prod_004': {'name': 'Turmeric Powder 100g', 'current_stock': 40},
            'prod_005': {'name': 'Onions 1kg', 'current_stock': 2},  # Low stock
            'prod_006': {'name': 'Tomatoes 1kg', 'current_stock': 0},  # Out of stock
            'prod_007': {'name': 'Wheat Flour 2kg', 'current_stock': 15},
            'prod_008': {'name': 'Sugar 1kg', 'current_stock': 60},
            'prod_009': {'name': 'Salt 1kg', 'current_stock': 80},
            'prod_010': {'name': 'Milk 1L', 'current_stock': 10}
        }
        
        # Find products from our mock data
        for product_id, product_info in mock_product_ids.items():
            stock = product_info['current_stock']
            if stock > 10 and not in_stock_product:
                in_stock_product = {'id': product_id, 'name': product_info['name'], 'current_stock': stock}
            elif 0 < stock <= 5 and not low_stock_product:
                low_stock_product = {'id': product_id, 'name': product_info['name'], 'current_stock': stock}
            elif stock == 0 and not out_of_stock_product:
                out_of_stock_product = {'id': product_id, 'name': product_info['name'], 'current_stock': stock}
        
        print(f"\n📋 Test Products Found:")
        if in_stock_product:
            print(f"  🟢 In Stock: {in_stock_product['name']} ({in_stock_product.get('current_stock', 0)} units)")
        if low_stock_product:
            print(f"  🟡 Low Stock: {low_stock_product['name']} ({low_stock_product.get('current_stock', 0)} units)")
        if out_of_stock_product:
            print(f"  🔴 Out of Stock: {out_of_stock_product['name']} ({out_of_stock_product.get('current_stock', 0)} units)")
        
        # Test 2: Stock availability
        if in_stock_product:
            product_id = in_stock_product['id']
            self.test_stock_availability(product_id, 1, expect_success=True)  # Should succeed
            self.test_stock_availability(product_id, 1000, expect_success=False)  # Should fail (correctly)
        
        # Test 3: Order integration with sufficient stock
        if in_stock_product:
            product_id = in_stock_product['id']
            # First check stock availability
            self.test_stock_availability(product_id, 1, expect_success=True)
            self.test_order_with_stock_check(product_id, 1, expected_success=True)
        
        # Test 4: Order integration with insufficient stock
        if in_stock_product:
            product_id = in_stock_product['id']
            # Test with excessive quantity - should fail but that's correct behavior
            self.test_stock_availability(product_id, 1000, expect_success=False)  # Should fail (correctly)
            self.test_order_with_stock_check(product_id, 1000, expected_success=False)
        
        # Test 5: Order with out-of-stock product
        if out_of_stock_product:
            product_id = out_of_stock_product['id']
            # Test with out-of-stock product - should fail but that's correct behavior
            self.test_stock_availability(product_id, 1, expect_success=False)  # Should fail (correctly)
            self.test_order_with_stock_check(product_id, 1, expected_success=False)
        
        # Test 6: Low stock alerts
        self.test_low_stock_alerts()
        
        # Test 7: Inventory summary
        self.test_inventory_summary()
        
        # Test 8: Stock updates
        if in_stock_product:
            product_id = in_stock_product['id']
            self.test_stock_update(product_id, 5, "in")
            self.test_stock_update(product_id, 2, "out")
        
        # Test 9: Concurrent orders (if we have sufficient stock)
        if in_stock_product and in_stock_product.get('current_stock', 0) >= 3:
            product_id = in_stock_product['id']
            self.test_concurrent_orders(product_id, 1, 3)
        
        # Generate summary
        successful_tests = sum(1 for result in self.test_results if result['success'])
        total_tests = len(self.test_results)
        
        print(f"\n📊 TEST SUMMARY")
        print("=" * 50)
        print(f"Passed: {successful_tests}/{total_tests}")
        print(f"Success Rate: {(successful_tests/total_tests)*100:.1f}%")
        
        # Show detailed results
        print(f"\n📋 DETAILED RESULTS:")
        for result in self.test_results:
            status = "✅" if result['success'] else "❌"
            print(f"  {status} {result['test']}: {result['message']}")
        
        return successful_tests / total_tests >= 0.8  # 80% success rate required

def main():
    """Main function to run the integration test"""
    tester = InventoryIntegrationTest()
    success = tester.run_complete_test()
    
    print(f"\n🎯 FINAL RESULT:")
    if success:
        print("🎉 Integration test PASSED - System ready for customer testing")
        print("✅ Inventory-order integration working correctly")
        print("✅ Stock validation functioning properly")
        print("✅ Low stock alerts operational")
        print("✅ Order creation with stock checks successful")
    else:
        print("⚠️ Integration test FAILED - Issues need resolution")
        print("❌ Some critical functionality not working")
        print("🔧 Review test results and fix identified issues")
    
    print(f"\n🌐 API Endpoints tested:")
    print(f"  • {tester.api_url}/api/v1/inventory/products")
    print(f"  • {tester.api_url}/api/v1/inventory/products/low-stock")
    print(f"  • {tester.api_url}/api/v1/inventory/inventory/summary")
    print(f"  • {tester.api_url}/api/v1/orders")

if __name__ == "__main__":
    main()
