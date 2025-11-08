# VyaparAI Product Catalog API Testing Guide

## Overview
This guide provides comprehensive examples for testing all API endpoints in the VyaparAI Product Catalog system.

## Prerequisites
- Valid JWT tokens for admin and store owner roles
- API base URL: `https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws`
- Tools: curl, Postman, or any HTTP client

## Authentication Setup

### Generate JWT Tokens
```python
import jwt
from datetime import datetime, timedelta

JWT_SECRET = 'vyaparai-jwt-secret-2024-secure'
JWT_ALGO = 'HS256'

def create_admin_jwt():
    payload = {
        'user_id': 'admin_user',
        'email': 'admin@vyapaarai.com',
        'store_id': 'admin_store',
        'role': 'admin',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def create_store_owner_jwt():
    payload = {
        'user_id': 'store_owner_123',
        'email': 'owner@store.com',
        'store_id': 'store_123',
        'role': 'store_owner',
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

# Generate tokens
admin_token = create_admin_jwt()
store_token = create_store_owner_jwt()
```

---

## Admin API Testing

### 1. Product Management

#### Get Product Statuses
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/statuses" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "success": true,
  "statuses": {
    "admin_created": "Pre-populated by admin with high quality data",
    "pending": "Added by store owner, awaiting admin approval",
    "verified": "Admin approved, high quality and accurate",
    "community": "Store-created, basic validation passed",
    "flagged": "Flagged for review due to quality issues",
    "migrated": "Migrated from legacy system"
  },
  "quality_scores": {
    "excellent": {"score": 100, "criteria": "Professional images, complete data"},
    "good": {"score": 80, "criteria": "Good images, mostly complete data"},
    "fair": {"score": 60, "criteria": "Basic data, acceptable images"},
    "poor": {"score": 40, "criteria": "Incomplete data, poor images"},
    "needs_review": {"score": 20, "criteria": "Missing critical information"}
  }
}
```

#### Get Products Needing Review
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/needing-review" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

#### Get Products by Status
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/by-status/pending" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

#### Update Product Status
```bash
curl -X PUT "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/{product_id}/status" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "verified",
    "notes": "High quality product with complete data"
  }'
```

#### Bulk Update Product Status
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/bulk-update-status" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "criteria": {
      "min_quality_score": 80,
      "current_status": "pending"
    },
    "new_status": "verified",
    "notes": "Auto-approved based on quality score"
  }'
```

### 2. Product Import

#### Import Common Indian Products
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/import/common-indian-products" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### Preview Common Indian Products
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/import/common-indian-products/preview" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

#### Import from Open Food Facts
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/import/open-food-facts" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 50,
    "category": "rice"
  }'
```

#### Validate Imported Products
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/import/validate-products" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "product_ids": ["prod_123", "prod_456"]
  }'
```

### 3. Analytics

#### Get Product Quality Analytics
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/analytics/product-quality" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

#### Get Import Analytics
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/import/analytics" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

#### Get Regional Coverage Analytics
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/analytics/regional-coverage" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

### 4. System Management

#### Validate Cleanup Status
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/cleanup/validate" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

#### Execute Catalog Cleanup (DANGER!)
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/cleanup/catalog" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation": "DELETE_ALL_CATALOG_DATA",
    "clear_csv_jobs": false
  }'
```

#### Get Product History
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/{product_id}/history" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

---

## Store Owner API Testing

### 1. Inventory Management

#### Get Store Inventory
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

#### Add Product to Inventory
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Basmati Rice 1kg",
    "brand": "India Gate",
    "category": "Rice & Grains",
    "barcode": "8901030875391",
    "quantity": 50,
    "cost_price": "120.00",
    "selling_price": "150.00",
    "reorder_level": 10,
    "supplier": "Local Supplier",
    "location": "Aisle 1, Shelf 2",
    "notes": "Premium quality rice"
  }'
```

#### Update Product in Inventory
```bash
curl -X PUT "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/{product_id}" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "quantity": 75,
    "cost_price": "115.00",
    "selling_price": "145.00",
    "reorder_level": 15,
    "location": "Aisle 1, Shelf 3"
  }'
```

#### Remove Product from Inventory
```bash
curl -X DELETE "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/{product_id}" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

### 2. Product Matching

#### Find Existing Products
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/match" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Basmati Rice 1kg",
    "brand": "India Gate",
    "barcode": "8901030875391"
  }'
```

#### Get Global Product Details
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/global/{product_id}" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

### 3. Regional Language Support

#### Add Regional Name
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/{product_id}/regional-names" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "region_code": "IN-MH",
    "regional_name": "बासमती चावल 1kg"
  }'
```

#### Get Regional Names
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/{product_id}/regional-names" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

#### Search by Regional Name
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products/search-regional?name=चावल&region=IN-MH" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

### 4. Bulk Operations

#### Download CSV Template
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/bulk-upload/template" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

#### Upload CSV
```bash
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/bulk-upload/csv" \
  -H "Authorization: Bearer {store_token}" \
  -F "file=@inventory.csv"
```

#### Check Upload Status
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/bulk-upload/jobs/{job_id}/status" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

### 5. Store Profile Management

#### Get Store Region
```bash
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/profile/region" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json"
```

#### Update Store Region
```bash
curl -X PUT "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/stores/profile/region" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "region_code": "IN-MH",
    "primary_language": "marathi",
    "address": "Mumbai, Maharashtra"
  }'
```

---

## Test Scenarios

### Scenario 1: Complete Product Lifecycle
1. **Store Owner**: Add new product to inventory
2. **Admin**: Review and approve product
3. **Store Owner**: Update inventory quantities
4. **Store Owner**: Add regional name
5. **Admin**: Check analytics

### Scenario 2: Bulk Import Process
1. **Store Owner**: Download CSV template
2. **Store Owner**: Upload CSV with inventory data
3. **Store Owner**: Monitor upload progress
4. **Admin**: Review imported products
5. **Admin**: Approve high-quality products

### Scenario 3: Product Matching
1. **Store Owner**: Search for existing product
2. **Store Owner**: Use existing product if found
3. **Store Owner**: Create new product if not found
4. **Admin**: Review new product creation

### Scenario 4: Regional Language Support
1. **Store Owner**: Set store region
2. **Store Owner**: Add regional names for products
3. **Store Owner**: Search using regional names
4. **Admin**: Monitor regional coverage

---

## Error Testing

### Test Invalid Authentication
```bash
# Test without token
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products"

# Test with invalid token
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer invalid_token"
```

### Test Permission Errors
```bash
# Store owner trying to access admin endpoint
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/admin/products/statuses" \
  -H "Authorization: Bearer {store_token}"
```

### Test Invalid Data
```bash
# Test with invalid price format
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Product",
    "cost_price": 120.0,
    "selling_price": 150.0
  }'
```

---

## Performance Testing

### Load Testing with Multiple Requests
```bash
# Test concurrent requests
for i in {1..10}; do
  curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
    -H "Authorization: Bearer {store_token}" &
done
wait
```

### Large Data Testing
```bash
# Test with large CSV upload
curl -X POST "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/bulk-upload/csv" \
  -H "Authorization: Bearer {store_token}" \
  -F "file=@large_inventory.csv"
```

---

## Monitoring & Debugging

### Check Response Times
```bash
# Time the request
time curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}"
```

### Verbose Output
```bash
# Get detailed response information
curl -v -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}"
```

### Save Responses
```bash
# Save response to file
curl -X GET "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory/products" \
  -H "Authorization: Bearer {store_token}" \
  -o response.json
```

---

## Automated Testing Script

```python
import requests
import json
import time

class APITester:
    def __init__(self, base_url, admin_token, store_token):
        self.base_url = base_url
        self.admin_headers = {"Authorization": f"Bearer {admin_token}"}
        self.store_headers = {"Authorization": f"Bearer {store_token}"}
    
    def test_endpoint(self, method, endpoint, headers, data=None, expected_status=200):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            
            if response.status_code == expected_status:
                print(f"✅ {method} {endpoint} - Status: {response.status_code}")
                return response.json()
            else:
                print(f"❌ {method} {endpoint} - Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ {method} {endpoint} - Error: {e}")
            return None
    
    def run_all_tests(self):
        print("=== Running API Tests ===")
        
        # Admin tests
        print("\n--- Admin Tests ---")
        self.test_endpoint("GET", "/api/v1/admin/products/statuses", self.admin_headers)
        self.test_endpoint("GET", "/api/v1/admin/products/needing-review", self.admin_headers)
        self.test_endpoint("GET", "/api/v1/admin/analytics/product-quality", self.admin_headers)
        
        # Store owner tests
        print("\n--- Store Owner Tests ---")
        self.test_endpoint("GET", "/api/v1/inventory/products", self.store_headers)
        self.test_endpoint("GET", "/api/v1/inventory/bulk-upload/template", self.store_headers)
        
        # Permission tests
        print("\n--- Permission Tests ---")
        self.test_endpoint("GET", "/api/v1/admin/products/statuses", self.store_headers, expected_status=200)
        
        print("\n=== Tests Complete ===")

# Usage
# tester = APITester(base_url, admin_token, store_token)
# tester.run_all_tests()
```

This testing guide provides comprehensive examples for testing all aspects of the VyaparAI Product Catalog API system.



