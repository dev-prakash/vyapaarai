#!/usr/bin/env python3
"""
Load sample product data for VyaparAI inventory system testing
"""

import requests
import json
import time
from decimal import Decimal

class SampleProductLoader:
    def __init__(self, api_url="https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"):
        self.api_url = api_url
        self.products = []
        self.loaded_count = 0
        self.failed_count = 0
    
    def get_sample_products(self):
        """Define sample Indian grocery products"""
        return [
            {
                "name": "Basmati Rice 1kg",
                "description": "Premium quality basmati rice with long grains",
                "category": "Grains",
                "subcategory": "Rice",
                "price": 150.00,
                "mrp": 180.00,
                "cost_price": 120.00,
                "current_stock": 50,
                "min_stock_level": 10,
                "max_stock_level": 200,
                "unit": "kg",
                "brand": "Royal",
                "sku": "RICE-BASMATI-1KG",
                "supplier_name": "Grain Suppliers Ltd",
                "supplier_contact": "+91-9876543210",
                "supplier_email": "grain@suppliers.com"
            },
            {
                "name": "Toor Dal 1kg",
                "description": "Organic toor dal rich in protein",
                "category": "Pulses",
                "subcategory": "Dal",
                "price": 120.00,
                "mrp": 140.00,
                "cost_price": 90.00,
                "current_stock": 30,
                "min_stock_level": 5,
                "max_stock_level": 100,
                "unit": "kg",
                "brand": "Organic",
                "sku": "PULSE-TOOR-1KG",
                "supplier_name": "Organic Foods",
                "supplier_contact": "+91-9876543211",
                "supplier_email": "organic@foods.com"
            },
            {
                "name": "Sunflower Oil 1L",
                "description": "Pure sunflower cooking oil",
                "category": "Oil",
                "subcategory": "Cooking Oil",
                "price": 180.00,
                "mrp": 200.00,
                "cost_price": 150.00,
                "current_stock": 25,
                "min_stock_level": 8,
                "max_stock_level": 80,
                "unit": "liter",
                "brand": "Nature Fresh",
                "sku": "OIL-SUNFLOWER-1L",
                "supplier_name": "Oil Distributors",
                "supplier_contact": "+91-9876543212",
                "supplier_email": "oil@distributors.com"
            },
            {
                "name": "Turmeric Powder 100g",
                "description": "Pure turmeric powder for cooking",
                "category": "Spices",
                "subcategory": "Powder",
                "price": 45.00,
                "mrp": 50.00,
                "cost_price": 35.00,
                "current_stock": 40,
                "min_stock_level": 10,
                "max_stock_level": 150,
                "unit": "packet",
                "brand": "Spice Master",
                "sku": "SPICE-TURMERIC-100G",
                "supplier_name": "Spice Traders",
                "supplier_contact": "+91-9876543213",
                "supplier_email": "spice@traders.com"
            },
            {
                "name": "Onions 1kg",
                "description": "Fresh red onions",
                "category": "Vegetables",
                "subcategory": "Root Vegetables",
                "price": 35.00,
                "mrp": 40.00,
                "cost_price": 25.00,
                "current_stock": 2,  # Low stock for testing
                "min_stock_level": 5,
                "max_stock_level": 50,
                "unit": "kg",
                "brand": "Fresh Farm",
                "sku": "VEG-ONION-1KG",
                "supplier_name": "Local Farmers",
                "supplier_contact": "+91-9876543214",
                "supplier_email": "farmers@local.com"
            },
            {
                "name": "Tomatoes 1kg",
                "description": "Fresh red tomatoes",
                "category": "Vegetables",
                "subcategory": "Fruits",
                "price": 45.00,
                "mrp": 50.00,
                "cost_price": 30.00,
                "current_stock": 0,  # Out of stock for testing
                "min_stock_level": 5,
                "max_stock_level": 40,
                "unit": "kg",
                "brand": "Fresh Farm",
                "sku": "VEG-TOMATO-1KG",
                "supplier_name": "Local Farmers",
                "supplier_contact": "+91-9876543214",
                "supplier_email": "farmers@local.com"
            },
            {
                "name": "Wheat Flour 2kg",
                "description": "Whole wheat flour for rotis",
                "category": "Grains",
                "subcategory": "Flour",
                "price": 80.00,
                "mrp": 90.00,
                "cost_price": 60.00,
                "current_stock": 15,
                "min_stock_level": 8,
                "max_stock_level": 100,
                "unit": "kg",
                "brand": "Aashirvaad",
                "sku": "GRAIN-WHEAT-2KG",
                "supplier_name": "Flour Mills",
                "supplier_contact": "+91-9876543215",
                "supplier_email": "flour@mills.com"
            },
            {
                "name": "Sugar 1kg",
                "description": "Refined white sugar",
                "category": "Essentials",
                "subcategory": "Sweeteners",
                "price": 45.00,
                "mrp": 50.00,
                "cost_price": 35.00,
                "current_stock": 60,
                "min_stock_level": 10,
                "max_stock_level": 150,
                "unit": "kg",
                "brand": "Tata",
                "sku": "ESS-SUGAR-1KG",
                "supplier_name": "Sugar Suppliers",
                "supplier_contact": "+91-9876543216",
                "supplier_email": "sugar@suppliers.com"
            },
            {
                "name": "Salt 1kg",
                "description": "Iodized table salt",
                "category": "Essentials",
                "subcategory": "Seasonings",
                "price": 20.00,
                "mrp": 25.00,
                "cost_price": 15.00,
                "current_stock": 80,
                "min_stock_level": 10,
                "max_stock_level": 200,
                "unit": "kg",
                "brand": "Tata",
                "sku": "ESS-SALT-1KG",
                "supplier_name": "Salt Traders",
                "supplier_contact": "+91-9876543217",
                "supplier_email": "salt@traders.com"
            },
            {
                "name": "Milk 1L",
                "description": "Fresh cow milk",
                "category": "Dairy",
                "subcategory": "Milk",
                "price": 60.00,
                "mrp": 65.00,
                "cost_price": 45.00,
                "current_stock": 10,
                "min_stock_level": 5,
                "max_stock_level": 30,
                "unit": "liter",
                "brand": "Amul",
                "sku": "DAIRY-MILK-1L",
                "supplier_name": "Dairy Farm",
                "supplier_contact": "+91-9876543218",
                "supplier_email": "dairy@farm.com"
            }
        ]
    
    def create_product(self, product_data):
        """Create a single product via API"""
        try:
            response = requests.post(
                f"{self.api_url}/api/v1/inventory/products",
                json=product_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('success'):
                    print(f"✅ Created: {product_data['name']}")
                    self.loaded_count += 1
                    return True
                else:
                    print(f"❌ Failed: {product_data['name']} - {result.get('message', 'Unknown error')}")
                    self.failed_count += 1
                    return False
            else:
                print(f"❌ Failed: {product_data['name']} - HTTP {response.status_code}")
                self.failed_count += 1
                return False
                
        except Exception as e:
            print(f"❌ Error creating {product_data['name']}: {str(e)}")
            self.failed_count += 1
            return False
    
    def load_all_products(self):
        """Load all sample products"""
        print("🛒 Loading sample products for VyaparAI inventory system...")
        print("=" * 60)
        
        products = self.get_sample_products()
        
        for i, product in enumerate(products, 1):
            print(f"[{i}/{len(products)}] Creating product: {product['name']}")
            self.create_product(product)
            time.sleep(0.5)  # Small delay to avoid overwhelming the API
        
        print("\n" + "=" * 60)
        print(f"📊 LOADING SUMMARY:")
        print(f"✅ Successfully loaded: {self.loaded_count}")
        print(f"❌ Failed to load: {self.failed_count}")
        print(f"📦 Total products: {len(products)}")
        
        if self.loaded_count > 0:
            print(f"\n🎉 Sample products loaded successfully!")
            print(f"🌐 Check inventory at: {self.api_url}/api/v1/inventory/products")
        else:
            print(f"\n⚠️ No products were loaded. Check API connectivity.")
    
    def verify_products_loaded(self):
        """Verify that products were loaded successfully"""
        try:
            response = requests.get(f"{self.api_url}/api/v1/inventory/products")
            if response.status_code == 200:
                result = response.json()
                products = result.get('products', [])
                print(f"\n🔍 VERIFICATION:")
                print(f"📦 Products in system: {len(products)}")
                
                if products:
                    print(f"📋 Sample products:")
                    for product in products[:5]:  # Show first 5
                        stock_status = "🟢 In Stock" if product.get('current_stock', 0) > 0 else "🔴 Out of Stock"
                        print(f"  • {product['name']} - {stock_status} ({product.get('current_stock', 0)} {product.get('unit', 'units')})")
                    
                    if len(products) > 5:
                        print(f"  ... and {len(products) - 5} more products")
                
                return len(products) > 0
            else:
                print(f"❌ Verification failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Verification error: {str(e)}")
            return False

def main():
    """Main function to run the product loader"""
    loader = SampleProductLoader()
    
    # Load products
    loader.load_all_products()
    
    # Verify loading
    print("\n" + "=" * 60)
    loader.verify_products_loaded()
    
    print(f"\n🚀 Next steps:")
    print(f"1. Test inventory endpoints: {loader.api_url}/api/v1/inventory/products")
    print(f"2. Check low stock alerts: {loader.api_url}/api/v1/inventory/products/low-stock")
    print(f"3. View inventory summary: {loader.api_url}/api/v1/inventory/inventory/summary")
    print(f"4. Test order creation with stock validation")

if __name__ == "__main__":
    main()
