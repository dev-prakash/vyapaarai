#!/usr/bin/env python3
"""
Simple test script for async import endpoints
"""
import requests
import json

# Test the async import endpoints
API_BASE_URL = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"

def test_async_import_endpoints():
    """Test the async import endpoints"""
    
    # Test data
    test_products = [
        {
            "name": "Test Product 1",
            "category": "Test Category",
            "brand": "Test Brand",
            "barcode": "1234567890123",
            "description": "Test product description",
            "canonical_image_urls": {
                "original": "https://example.com/image1.jpg"
            },
            "attributes": {
                "weight": "500g",
                "size": "Medium"
            }
        },
        {
            "name": "Test Product 2", 
            "category": "Test Category",
            "brand": "Test Brand 2",
            "barcode": "1234567890124",
            "description": "Test product description 2",
            "canonical_image_urls": {
                "original": "https://example.com/image2.jpg"
            },
            "attributes": {
                "weight": "1kg",
                "size": "Large"
            }
        }
    ]
    
    # Test 1: Create async import job
    print("Testing async import job creation...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/admin/products/bulk-import-async",
            json={
                "products": test_products,
                "import_type": "admin_bulk_import",
                "created_by": "test_admin"
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test_token"  # This will fail auth, but we can see if endpoint exists
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: Check import job status
    print("Testing import job status check...")
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/admin/import-jobs/test_job_id",
            headers={
                "Authorization": "Bearer test_token"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_async_import_endpoints()
