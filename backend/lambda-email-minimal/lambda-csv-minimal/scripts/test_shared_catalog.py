import sys
import os
import time
import json
from datetime import datetime, timedelta

import requests
import jwt

BASE_URL = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws"

# Local JWT generator matching backend expectations
JWT_SECRET = "vyaparai-jwt-secret-2024-secure"
JWT_ALGORITHM = "HS256"


def create_jwt(user_id: str, email: str, store_id: str, role: str = "store_owner") -> str:
    """Create a JWT token with user and store information - matches backend format"""
    payload = {
        "user_id": user_id,
        "email": email,
        "store_id": store_id,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=30)  # Token expires in 30 days
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def auth_headers(store_id: str):
    token = create_jwt("user_automation", f"{store_id}@example.com", store_id)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def post(path: str, store_id: str, data: dict):
    url = f"{BASE_URL}{path}"
    start = time.time()
    resp = requests.post(url, headers=auth_headers(store_id), json=data, timeout=30)
    dt = round((time.time() - start) * 1000)
    return resp, dt


def get(path: str, store_id: str, params: dict | None = None):
    url = f"{BASE_URL}{path}"
    start = time.time()
    resp = requests.get(url, headers=auth_headers(store_id), params=params or {}, timeout=30)
    dt = round((time.time() - start) * 1000)
    return resp, dt


def scenario_basic_crud(products):
    results = {"name": "Basic CRUD Operations", "steps": []}
    store_id = "store_mumbai_001"
    # Create
    for p in products:
        payload = {
            "name": p["name"],
            "brand": p.get("brand"),
            "category": p.get("category"),
            "barcode": p.get("barcode"),
            "price": p.get("price"),
            "quantity": p.get("quantity"),
        }
        resp, dt = post("/api/v1/inventory/products", store_id, payload)
        results["steps"].append({"op": "create", "status": resp.status_code, "ms": dt, "body": safe_json(resp)})

    # List with pagination
    resp, dt = get("/api/v1/inventory/products", store_id, params={"limit": 2})
    body = safe_json(resp)
    results["steps"].append({"op": "list", "status": resp.status_code, "ms": dt, "count": len(body.get("products", []))})
    return results


def scenario_dedup(dupes):
    results = {"name": "Cross-Store Deduplication", "steps": []}
    created_ids = set()
    for item in dupes:
        payload = {
            "name": item["name"],
            "brand": item.get("brand"),
            "category": "Test",
            "barcode": item.get("barcode"),
            "price": item.get("price"),
            "quantity": item.get("quantity"),
        }
        resp, dt = post("/api/v1/inventory/products", item["store_context"], payload)
        body = safe_json(resp)
        if body.get("global_product_id"):
            created_ids.add(body["global_product_id"])
        results["steps"].append({"store": item["store_context"], "status": resp.status_code, "ms": dt})
    results["unique_global_products"] = len(created_ids)
    return results


def scenario_matching():
    results = {"name": "Product Matching Intelligence", "steps": []}
    store_id = "store_mumbai_001"
    tests = [
        {"name": "Basmati Rice 1kg", "brand": "India Gate", "barcode": "8901030875391"},
        {"name": "Bashmati Rice 1KG", "brand": "India Gate"},
        {"name": "बासमती चावल 1kg", "brand": "India Gate"},
        {"name": "Fresh Onion 1kg", "brand": "Local Farm"},
    ]
    for t in tests:
        resp, dt = post("/api/v1/inventory/products/match", store_id, t)
        results["steps"].append({"query": t, "status": resp.status_code, "ms": dt, "body": safe_json(resp)})
    return results


def scenario_regional(products):
    results = {"name": "Regional Language Support", "steps": []}
    store_id = "store_mumbai_001"
    # Get one product id for regional tests
    resp, _ = get("/api/v1/inventory/products", store_id, params={"limit": 1})
    pid = safe_json(resp).get("products", [{}])[0].get("product_id")
    if not pid:
        results["steps"].append({"error": "No products available for regional tests"})
        return results
    # Contribute a regional name
    payload = {"region_code": "IN-MH", "regional_name": "बासमती चावल 1kg"}
    resp, dt = post(f"/api/v1/inventory/products/{pid}/regional-names", store_id, payload)
    results["steps"].append({"op": "contribute", "status": resp.status_code, "ms": dt, "body": safe_json(resp)})
    # Search by regional
    resp, dt = get("/api/v1/inventory/products/search-regional", store_id, params={"name": "बासमती", "region": "IN-MH"})
    results["steps"].append({"op": "search", "status": resp.status_code, "ms": dt, "count": len(safe_json(resp).get("results", []))})
    # Analytics
    resp, dt = get("/api/v1/analytics/regional-coverage", store_id)
    results["steps"].append({"op": "analytics", "status": resp.status_code, "ms": dt})
    return results


def scenario_csv_upload():
    results = {"name": "CSV Bulk Upload Testing", "steps": []}
    store_id = "store_mumbai_001"
    
    # Create CSV content
    csv_content = '''name,brand,category,barcode,price,quantity,supplier,location
"Wheat Flour 5kg","Aashirvaad","Flour & Grains","8901030875123",185.00,25,"Distributor A","Aisle 1"
"Turmeric Powder 100g","MDH","Spices","8901020200123",45.00,100,"Spice Supplier","Aisle 2"
"Coconut Oil 500ml","Parachute","Cooking Oil","8901030800456",120.00,40,"Oil Distributor","Aisle 3"
"Green Tea 100g","Tata Tea","Beverages","8901030875789",85.00,60,"Tea Supplier","Aisle 4"
"Basmati Rice 1kg","India Gate","Rice & Grains","8901030875391",120.00,30,"Rice Supplier","Aisle 1"
"Tomato 1kg","Fresh Farm","Vegetables",,40.00,50,"Local Vendor","Cold Storage"
"Potato 1kg","Local Farm","Vegetables",,30.00,80,"Local Vendor","Cold Storage"
"Curd 400g","Amul","Dairy","8901020200678",24.00,45,"Dairy Supplier","Refrigerated"'''
    
    # Upload CSV
    files = {'file': ('test_products.csv', csv_content, 'text/csv')}
    headers = {"Authorization": f"Bearer {create_jwt('user_automation', f'{store_id}@example.com', store_id)}"}
    url = f"{BASE_URL}/api/v1/inventory/bulk-upload/csv"
    
    start = time.time()
    resp = requests.post(url, headers=headers, files=files, timeout=60)
    dt = round((time.time() - start) * 1000)
    
    body = safe_json(resp)
    results["steps"].append({"op": "upload", "status": resp.status_code, "ms": dt, "body": body})
    
    # Check job status if job_id was returned
    if body.get("job_id"):
        job_id = body["job_id"]
        resp, dt = get(f"/api/v1/inventory/bulk-upload/jobs/{job_id}/status", store_id)
        results["steps"].append({"op": "status", "status": resp.status_code, "ms": dt, "body": safe_json(resp)})
    
    return results


def safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


def main():
    report = {"started_at": datetime.utcnow().isoformat()}

    products_with_barcodes = [
        {"name": "Basmati Rice 1kg", "brand": "India Gate", "category": "Rice & Grains", "barcode": "8901030875391", "price": 120.00, "quantity": 50},
        {"name": "Brinjal 500g", "brand": "Fresh Vegetables", "category": "Vegetables", "barcode": "1234567890123", "price": 25.00, "quantity": 100},
        {"name": "Tata Salt 1kg", "brand": "Tata", "category": "Spices & Condiments", "barcode": "8901030800009", "price": 22.00, "quantity": 200},
        {"name": "Amul Milk 500ml", "brand": "Amul", "category": "Dairy", "barcode": "8901020200005", "price": 26.00, "quantity": 75},
    ]

    duplicate_test_products = [
        {"store_context": "store_mumbai_001", "name": "Basmati Rice 1kg", "brand": "India Gate", "barcode": "8901030875391", "price": 125.00, "quantity": 40},
        {"store_context": "store_delhi_001", "name": "Basmati Rice 1kg", "brand": "India Gate", "barcode": "8901030875391", "price": 118.00, "quantity": 60},
        {"store_context": "store_chennai_001", "name": "பாஸ்மதி அரிசி 1kg", "brand": "India Gate", "barcode": "8901030875391", "price": 122.00, "quantity": 35},
    ]

    sections = []
    sections.append(scenario_basic_crud(products_with_barcodes))
    sections.append(scenario_dedup(duplicate_test_products))
    sections.append(scenario_matching())
    sections.append(scenario_regional(products_with_barcodes))
    sections.append(scenario_csv_upload())

    report["sections"] = sections
    report["finished_at"] = datetime.utcnow().isoformat()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


