# VyaparAI Product Catalog & Inventory Management User Manual

## Table of Contents
1. [System Overview](#system-overview)
2. [User Roles & Permissions](#user-roles--permissions)
3. [Admin User Guide](#admin-user-guide)
4. [Store Owner Guide](#store-owner-guide)
5. [API Endpoints Reference](#api-endpoints-reference)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## System Overview

The VyaparAI Product Catalog System is a shared inventory management platform that allows:
- **Global Product Catalog**: Centralized product database with deduplication
- **Store-Specific Inventory**: Individual store inventory management
- **Regional Language Support**: Multi-language product names
- **Quality Control**: Admin approval workflow for product quality
- **Bulk Operations**: CSV uploads and bulk management tools

### Key Components
- **Global Products Table**: Master product catalog with shared data
- **Store Inventory Table**: Store-specific inventory and pricing
- **Admin Workflow**: Quality control and product approval system
- **Import Pipeline**: External data integration (Open Food Facts, etc.)

---

## User Roles & Permissions

### Admin Users
- **Full System Access**: All endpoints and operations
- **Product Approval**: Can verify, flag, or reject products
- **Bulk Operations**: Import/export large datasets
- **Analytics Access**: System-wide analytics and reporting
- **Quality Management**: Set quality standards and manage product status

### Store Owners
- **Store Inventory Management**: Manage their store's inventory
- **Product Creation**: Add new products to global catalog (pending approval)
- **Regional Names**: Contribute regional language names
- **CSV Uploads**: Bulk upload inventory via CSV
- **Limited Analytics**: Store-specific analytics only

---

## Admin User Guide

### 1. Product Catalog Management

#### 1.1 View All Products
```bash
GET /api/v1/admin/products/statuses
```
**Purpose**: Get overview of all product statuses and quality scores
**Response**: List of product statuses with counts and descriptions

#### 1.2 Review Products Needing Approval
```bash
GET /api/v1/admin/products/needing-review
```
**Purpose**: Find products that require admin review
**Response**: List of products with pending status

#### 1.3 Get Products by Status
```bash
GET /api/v1/admin/products/by-status/{status}
```
**Parameters**:
- `status`: `pending`, `verified`, `flagged`, `admin_created`, `community`, `migrated`

**Example**:
```bash
curl -X GET "https://your-api-url/api/v1/admin/products/by-status/pending" \
  -H "Authorization: Bearer {admin_jwt_token}"
```

#### 1.4 Update Product Status
```bash
PUT /api/v1/admin/products/{product_id}/status
```
**Purpose**: Approve, reject, or flag individual products

**Request Body**:
```json
{
  "status": "verified",
  "notes": "High quality product with complete data"
}
```

**Status Options**:
- `verified`: Approved for use
- `flagged`: Needs manual review
- `pending`: Awaiting approval
- `community`: Store-created, basic validation

#### 1.5 Bulk Status Updates
```bash
POST /api/v1/admin/products/bulk-update-status
```
**Purpose**: Update multiple products at once based on criteria

**Request Body**:
```json
{
  "criteria": {
    "min_quality_score": 80,
    "current_status": "pending"
  },
  "new_status": "verified",
  "notes": "Auto-approved based on quality score"
}
```

### 2. Product Import & Seeding

#### 2.1 Import Common Indian Products
```bash
POST /api/v1/admin/import/common-indian-products
```
**Purpose**: Import curated high-quality Indian products with regional names

**Request Body**:
```json
{
  "product_indices": [0, 1, 2]  // Optional: specific products to import
}
```

#### 2.2 Import from Open Food Facts
```bash
POST /api/v1/admin/import/open-food-facts
```
**Purpose**: Import products from Open Food Facts database

**Request Body**:
```json
{
  "limit": 50,
  "category": "rice"
}
```

**Categories Available**:
- `rice`, `spices`, `dairy`, `oil`, `snacks`, `beverages`

#### 2.3 Preview Import Data
```bash
GET /api/v1/admin/import/common-indian-products/preview
```
**Purpose**: Preview products before importing

#### 2.4 Validate Imported Products
```bash
POST /api/v1/admin/import/validate-products
```
**Purpose**: Validate imported products for quality and completeness

### 3. Analytics & Reporting

#### 3.1 Product Quality Analytics
```bash
GET /api/v1/admin/analytics/product-quality
```
**Response**:
```json
{
  "success": true,
  "analytics": {
    "total_products": 150,
    "products_needing_review": 12,
    "status_distribution": {
      "verified": 120,
      "pending": 12,
      "flagged": 3,
      "admin_created": 15
    },
    "quality_score_distribution": {
      "excellent": 45,
      "good": 78,
      "fair": 20,
      "poor": 5,
      "needs_review": 2
    }
  }
}
```

#### 3.2 Import Analytics
```bash
GET /api/v1/admin/import/analytics
```
**Purpose**: Track import success rates and sources

#### 3.3 Regional Coverage Analytics
```bash
GET /api/v1/analytics/regional-coverage
```
**Purpose**: Monitor regional language coverage

### 4. System Management

#### 4.1 Catalog Cleanup (DANGER ZONE)
```bash
# Validate current status
GET /api/v1/admin/cleanup/validate

# Execute full cleanup (requires confirmation)
POST /api/v1/admin/cleanup/catalog
```
**Request Body**:
```json
{
  "confirmation": "DELETE_ALL_CATALOG_DATA",
  "clear_csv_jobs": false
}
```

**⚠️ WARNING**: This will delete ALL products. A backup is automatically created.

#### 4.2 Product History Tracking
```bash
GET /api/v1/admin/products/{product_id}/history
```
**Purpose**: View complete history of product changes and approvals

---

## Store Owner Guide

### 1. Inventory Management

#### 1.1 View Store Inventory
```bash
GET /api/v1/inventory/products
```
**Purpose**: Get all products in your store's inventory
**Response**: List of products with store-specific pricing and quantities

#### 1.2 Add Product to Inventory
```bash
POST /api/v1/inventory/products
```
**Purpose**: Add a new product to global catalog and your inventory

**Request Body**:
```json
{
  "name": "Basmati Rice 1kg",
  "brand": "India Gate",
  "category": "Rice & Grains",
  "barcode": "8901030875391",
  "quantity": 50,
  "cost_price": 120.00,
  "selling_price": 150.00,
  "reorder_level": 10,
  "supplier": "Local Supplier",
  "location": "Aisle 1, Shelf 2",
  "notes": "Premium quality rice"
}
```

#### 1.3 Update Product in Inventory
```bash
PUT /api/v1/inventory/products/{product_id}
```
**Purpose**: Update store-specific inventory details

**Request Body**:
```json
{
  "quantity": 75,
  "cost_price": 115.00,
  "selling_price": 145.00,
  "reorder_level": 15,
  "location": "Aisle 1, Shelf 3"
}
```

#### 1.4 Remove Product from Inventory
```bash
DELETE /api/v1/inventory/products/{product_id}
```
**Purpose**: Remove product from your store's inventory (doesn't delete from global catalog)

### 2. Product Matching & Discovery

#### 2.1 Find Existing Products
```bash
POST /api/v1/inventory/products/match
```
**Purpose**: Check if a product already exists before creating new one

**Request Body**:
```json
{
  "name": "Basmati Rice 1kg",
  "brand": "India Gate",
  "barcode": "8901030875391"
}
```

**Response**:
```json
{
  "success": true,
  "matches": [
    {
      "product_id": "prod_123",
      "name": "Basmati Rice 1kg",
      "brand": "India Gate",
      "match_type": "exact_barcode",
      "confidence": 1.0
    }
  ],
  "recommendation": "use_existing"
}
```

#### 2.2 Get Global Product Details
```bash
GET /api/v1/inventory/products/global/{product_id}
```
**Purpose**: Get detailed information about a global product

### 3. Regional Language Support

#### 3.1 Add Regional Name
```bash
POST /api/v1/inventory/products/{product_id}/regional-names
```
**Purpose**: Contribute regional language name for a product

**Request Body**:
```json
{
  "region_code": "IN-MH",
  "regional_name": "बासमती चावल 1kg"
}
```

#### 3.2 Get Regional Names
```bash
GET /api/v1/inventory/products/{product_id}/regional-names
```
**Purpose**: View all regional names for a product

#### 3.3 Search by Regional Name
```bash
GET /api/v1/inventory/products/search-regional?name=चावल&region=IN-MH
```
**Purpose**: Find products using regional language names

### 4. Bulk Operations

#### 4.1 CSV Template Download
```bash
GET /api/v1/inventory/bulk-upload/template
```
**Purpose**: Download CSV template for bulk upload

#### 4.2 CSV Upload
```bash
POST /api/v1/inventory/bulk-upload/csv
```
**Purpose**: Upload inventory via CSV file

**Request**: Multipart form with CSV file
**Response**: Job ID for tracking progress

#### 4.3 Check Upload Status
```bash
GET /api/v1/inventory/bulk-upload/jobs/{job_id}/status
```
**Purpose**: Monitor CSV upload progress

**Response**:
```json
{
  "success": true,
  "job_status": "completed",
  "progress": {
    "total_rows": 100,
    "processed": 100,
    "successful": 95,
    "failed": 5,
    "duplicates_found": 12
  },
  "deduplication_metrics": {
    "exact_matches": 8,
    "fuzzy_matches": 4,
    "new_products": 83
  }
}
```

### 5. Store Profile Management

#### 5.1 Get Store Region
```bash
GET /api/v1/stores/profile/region
```
**Purpose**: Get your store's regional settings

#### 5.2 Update Store Region
```bash
PUT /api/v1/stores/profile/region
```
**Purpose**: Set your store's region for regional language support

**Request Body**:
```json
{
  "region_code": "IN-MH",
  "primary_language": "marathi",
  "address": "Mumbai, Maharashtra"
}
```

---

## API Endpoints Reference

### Authentication
All API calls require a JWT token in the Authorization header:
```
Authorization: Bearer {your_jwt_token}
```

### Base URL
```
https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws
```

### Common Response Format
```json
{
  "success": true|false,
  "data": {...},           // For successful responses
  "error": "error_message", // For failed responses
  "message": "description"  // Additional information
}
```

### Error Codes
- `400`: Bad Request - Invalid input data
- `401`: Unauthorized - Invalid or missing JWT token
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource doesn't exist
- `500`: Internal Server Error - Server-side error

---

## Troubleshooting

### Common Issues

#### 1. "Admin access required" Error
**Problem**: Non-admin user trying to access admin endpoints
**Solution**: Ensure your JWT token has `role: "admin"` in the payload

#### 2. "Float types are not supported" Error
**Problem**: Price values not properly formatted for DynamoDB
**Solution**: Ensure prices are sent as strings or integers, not floats
```json
// Correct
"cost_price": "120.00"
// Incorrect
"cost_price": 120.0
```

#### 3. CSV Upload Fails
**Problem**: CSV parsing errors or validation failures
**Solutions**:
- Check CSV format matches template exactly
- Ensure all required fields are present
- Verify data types (numbers, dates, etc.)
- Check for special characters in quoted fields

#### 4. Product Not Found After Creation
**Problem**: Product created but not visible in inventory
**Solutions**:
- Check if product was added to global catalog only
- Verify store_id in JWT token matches your store
- Check product status (may be pending approval)

#### 5. Regional Names Not Working
**Problem**: Regional names not displaying or saving
**Solutions**:
- Verify region_code format (e.g., "IN-MH")
- Check if store region is properly set
- Ensure regional name is in correct script/encoding

### Debugging Tips

#### 1. Check JWT Token
```bash
# Decode your JWT token to verify permissions
echo "your_jwt_token" | base64 -d
```

#### 2. Validate Request Data
```bash
# Use JSON validator for request bodies
echo '{"your": "json"}' | python -m json.tool
```

#### 3. Check API Response
```bash
# Always check the full response for error details
curl -v -X GET "your-endpoint" -H "Authorization: Bearer token"
```

---

## Best Practices

### For Admins

#### 1. Product Quality Management
- **Regular Reviews**: Check products needing review weekly
- **Quality Standards**: Maintain consistent quality criteria
- **Bulk Operations**: Use bulk updates for efficiency
- **Documentation**: Add clear notes when approving/rejecting products

#### 2. Import Management
- **Start Small**: Import in batches to monitor quality
- **Validate First**: Always preview before importing
- **Monitor Results**: Check import analytics regularly
- **Clean Data**: Remove low-quality imports promptly

#### 3. System Maintenance
- **Regular Backups**: System creates automatic backups
- **Monitor Analytics**: Track system health and usage
- **Update Standards**: Refine quality criteria based on data
- **Document Changes**: Keep records of system modifications

### For Store Owners

#### 1. Inventory Management
- **Check Existing First**: Always search before adding new products
- **Use Regional Names**: Contribute local language names
- **Maintain Accuracy**: Keep pricing and quantities current
- **Regular Updates**: Update inventory weekly or as needed

#### 2. Product Creation
- **Complete Information**: Provide all available product details
- **Quality Images**: Upload clear, high-quality product photos
- **Accurate Barcodes**: Ensure barcode numbers are correct
- **Descriptive Names**: Use clear, searchable product names

#### 3. Bulk Operations
- **Use Templates**: Always download and use the latest CSV template
- **Test Small**: Try with a few products first
- **Monitor Progress**: Check upload status regularly
- **Handle Errors**: Review and fix failed uploads promptly

#### 4. Regional Support
- **Set Store Region**: Configure your store's regional settings
- **Contribute Names**: Add regional names for common products
- **Use Local Terms**: Include local product names and variations
- **Help Community**: Contribute to regional language database

### General Best Practices

#### 1. Data Quality
- **Consistent Formatting**: Use standardized formats for all data
- **Complete Information**: Provide as much detail as possible
- **Regular Validation**: Periodically verify data accuracy
- **Error Handling**: Address data issues promptly

#### 2. Performance
- **Batch Operations**: Use bulk operations for large datasets
- **Efficient Queries**: Use specific filters to reduce response size
- **Cache Results**: Store frequently accessed data locally
- **Monitor Usage**: Track API usage and optimize as needed

#### 3. Security
- **Protect Tokens**: Keep JWT tokens secure and don't share
- **Regular Rotation**: Update tokens periodically
- **Monitor Access**: Review access logs regularly
- **Follow Permissions**: Respect role-based access controls

#### 4. Collaboration
- **Share Knowledge**: Document common issues and solutions
- **Provide Feedback**: Report bugs and suggest improvements
- **Help Others**: Assist other users when possible
- **Stay Updated**: Keep informed about system changes

---

## Support & Resources

### Getting Help
1. **Check Documentation**: Review this manual first
2. **Search Issues**: Look for similar problems in troubleshooting
3. **Contact Admin**: Reach out to system administrators
4. **Report Bugs**: Document issues with full details

### System Status
- **API Health**: Check endpoint responses for system status
- **Maintenance Windows**: System updates are announced in advance
- **Known Issues**: Current issues are documented in system status

### Updates & Changes
- **Version History**: Track system updates and new features
- **Migration Guides**: Follow guides for major system changes
- **Training Materials**: Access additional training resources
- **Community Forum**: Connect with other users

---

*This manual is regularly updated. Please check for the latest version and provide feedback for improvements.*



