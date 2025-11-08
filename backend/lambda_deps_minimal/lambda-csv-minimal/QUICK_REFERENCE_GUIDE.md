# VyaparAI Product Catalog - Quick Reference Guide

## 🔑 Authentication
```bash
# All requests require JWT token
Authorization: Bearer {your_jwt_token}
```

## 📊 Admin Quick Actions

### View System Status
```bash
# Get product quality analytics
GET /api/v1/admin/analytics/product-quality

# Check products needing review
GET /api/v1/admin/products/needing-review

# Get products by status
GET /api/v1/admin/products/by-status/pending
```

### Approve Products
```bash
# Approve single product
PUT /api/v1/admin/products/{product_id}/status
{
  "status": "verified",
  "notes": "High quality product"
}

# Bulk approve high-quality products
POST /api/v1/admin/products/bulk-update-status
{
  "criteria": {"min_quality_score": 80, "current_status": "pending"},
  "new_status": "verified",
  "notes": "Auto-approved based on quality"
}
```

### Import Products
```bash
# Import common Indian products
POST /api/v1/admin/import/common-indian-products
{}

# Import from Open Food Facts
POST /api/v1/admin/import/open-food-facts
{
  "limit": 50,
  "category": "rice"
}
```

### System Management
```bash
# Check cleanup status
GET /api/v1/admin/cleanup/validate

# Execute cleanup (DANGER!)
POST /api/v1/admin/cleanup/catalog
{
  "confirmation": "DELETE_ALL_CATALOG_DATA",
  "clear_csv_jobs": false
}
```

## 🏪 Store Owner Quick Actions

### Manage Inventory
```bash
# View store inventory
GET /api/v1/inventory/products

# Add new product
POST /api/v1/inventory/products
{
  "name": "Product Name",
  "brand": "Brand Name",
  "category": "Category",
  "barcode": "1234567890",
  "quantity": 50,
  "cost_price": "120.00",
  "selling_price": "150.00"
}

# Update product
PUT /api/v1/inventory/products/{product_id}
{
  "quantity": 75,
  "cost_price": "115.00",
  "selling_price": "145.00"
}
```

### Find Existing Products
```bash
# Check if product exists
POST /api/v1/inventory/products/match
{
  "name": "Product Name",
  "brand": "Brand Name",
  "barcode": "1234567890"
}

# Get global product details
GET /api/v1/inventory/products/global/{product_id}
```

### Bulk Operations
```bash
# Download CSV template
GET /api/v1/inventory/bulk-upload/template

# Upload CSV
POST /api/v1/inventory/bulk-upload/csv
# (multipart form with CSV file)

# Check upload status
GET /api/v1/inventory/bulk-upload/jobs/{job_id}/status
```

### Regional Names
```bash
# Add regional name
POST /api/v1/inventory/products/{product_id}/regional-names
{
  "region_code": "IN-MH",
  "regional_name": "बासमती चावल 1kg"
}

# Search by regional name
GET /api/v1/inventory/products/search-regional?name=चावल&region=IN-MH
```

## 📋 Common Status Values

### Product Statuses
- `admin_created`: Pre-populated by admin (high quality)
- `pending`: Added by store owner, awaiting approval
- `verified`: Admin approved, high quality
- `community`: Store-created, basic validation passed
- `flagged`: Flagged for review due to quality issues
- `migrated`: Migrated from legacy system

### Quality Scores
- `excellent`: 100 points (Professional images, complete data)
- `good`: 80 points (Good images, mostly complete data)
- `fair`: 60 points (Basic data, acceptable images)
- `poor`: 40 points (Incomplete data, poor images)
- `needs_review`: 20 points (Missing critical information)

## 🌍 Regional Codes
- `IN-MH`: Maharashtra (Marathi)
- `IN-TN`: Tamil Nadu (Tamil)
- `IN-KA`: Karnataka (Kannada)
- `IN-GJ`: Gujarat (Gujarati)
- `IN-UP`: Uttar Pradesh (Hindi)
- `IN-WB`: West Bengal (Bengali)

## 📁 CSV Template Fields
```csv
name,brand,category,barcode,quantity,cost_price,selling_price,reorder_level,supplier,location,notes
"Product Name","Brand","Category","1234567890",50,"120.00","150.00",10,"Supplier","Aisle 1","Notes"
```

## ⚠️ Common Issues & Solutions

### "Admin access required"
- Check JWT token has `role: "admin"`
- Verify token is not expired

### "Float types are not supported"
- Send prices as strings: `"120.00"` not `120.0`
- Use Decimal format for DynamoDB

### CSV Upload Fails
- Use exact template format
- Check for special characters in quoted fields
- Ensure all required fields are present

### Product Not Visible
- Check if product was added to global catalog only
- Verify store_id in JWT token
- Check product status (may be pending)

## 🔧 Base URL
```
https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
```

## 📞 Support
- Check full manual: `PRODUCT_CATALOG_USER_MANUAL.md`
- Contact admin for system issues
- Report bugs with full error details



