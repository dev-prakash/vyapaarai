# Admin Workflow and Bulk Import Capabilities

## Overview

This document describes the comprehensive admin workflow and bulk import capabilities implemented for the VyapaarAI hybrid product catalog strategy. The system enables both admin seeding and store owner contributions with quality controls.

## Architecture

### Product Status System

The system supports six distinct product statuses:

1. **`admin_created`** - Pre-populated by admin with high quality data
2. **`pending`** - Added by store owner, awaiting admin approval
3. **`verified`** - Admin approved, high quality and accurate
4. **`community`** - Store-created, basic validation passed
5. **`flagged`** - Flagged for review due to quality issues
6. **`migrated`** - Migrated from legacy system

### Quality Scoring System

Products are automatically scored based on data completeness:

- **Excellent (100 points)**: Professional images, complete data, verified barcodes
- **Good (80 points)**: Good images, mostly complete data
- **Fair (60 points)**: Basic data, acceptable images
- **Poor (40 points)**: Incomplete data, poor images
- **Needs Review (20 points)**: Missing critical information

### Quality Score Calculation

```python
# Required fields (40 points)
- Name: 15 points
- Brand: 10 points
- Category: 15 points

# Identification (30 points)
- Barcode: 30 points

# Images (20 points)
- Original image: 10 points
- Thumbnail: 5 points
- Medium size: 5 points

# Additional data (10 points)
- Description: 5 points
- Weight: 5 points
```

## API Endpoints

### 1. Get Product Statuses and Quality Definitions

**Endpoint**: `GET /api/v1/admin/products/statuses`

**Description**: Returns available product statuses and quality score definitions.

**Response**:
```json
{
  "success": true,
  "product_statuses": {
    "admin_created": "Pre-populated by admin with high quality data",
    "pending": "Added by store owner, awaiting admin approval",
    "verified": "Admin approved, high quality and accurate",
    "community": "Store-created, basic validation passed",
    "flagged": "Flagged for review due to quality issues",
    "migrated": "Migrated from legacy system"
  },
  "quality_scores": {
    "excellent": {"score": 100, "criteria": "Professional images, complete data, verified barcodes"},
    "good": {"score": 80, "criteria": "Good images, mostly complete data"},
    "fair": {"score": 60, "criteria": "Basic data, acceptable images"},
    "poor": {"score": 40, "criteria": "Incomplete data, poor images"},
    "needs_review": {"score": 20, "criteria": "Missing critical information"}
  }
}
```

### 2. Get Products Needing Review

**Endpoint**: `GET /api/v1/admin/products/needing-review`

**Description**: Returns products that need admin review (pending, flagged, or low quality).

**Query Parameters**:
- `limit` (optional): Number of products to return (default: 50)
- `last_key` (optional): Pagination token

**Response**:
```json
{
  "success": true,
  "products": [...],
  "count": 5,
  "last_key": "eyJwcm9kdWN0X2lkIjoi...",
  "has_more": false
}
```

### 3. Get Products by Status

**Endpoint**: `GET /api/v1/admin/products/by-status/{status}`

**Description**: Returns products filtered by verification status.

**Path Parameters**:
- `status`: One of the valid product statuses

**Query Parameters**:
- `limit` (optional): Number of products to return (default: 50)
- `last_key` (optional): Pagination token

### 4. Update Product Status

**Endpoint**: `PUT /api/v1/admin/products/{product_id}/status`

**Description**: Updates product verification status with admin tracking.

**Request Body**:
```json
{
  "status": "verified",
  "notes": "Product verified after quality review"
}
```

**Response**:
```json
{
  "success": true,
  "message": "Product status updated to verified",
  "product_id": "prod_abc123",
  "new_status": "verified"
}
```

### 5. Bulk Update Product Status

**Endpoint**: `POST /api/v1/admin/products/bulk-update-status`

**Description**: Bulk update product statuses.

**Request Body**:
```json
{
  "product_ids": ["prod_abc123", "prod_def456"],
  "status": "verified",
  "notes": "Bulk verification after quality review"
}
```

**Response**:
```json
{
  "success": true,
  "results": {
    "total_requested": 2,
    "successful": 2,
    "failed": 0,
    "errors": []
  },
  "message": "Updated 2 out of 2 products"
}
```

### 6. Bulk Import Products

**Endpoint**: `POST /api/v1/admin/products/bulk-import`

**Description**: Bulk import products for admin seeding.

**Request Body**:
```json
{
  "products": [
    {
      "name": "Premium Basmati Rice 1kg",
      "brand": "Tilda",
      "category": "Food & Beverages",
      "barcode": "8901234567890",
      "canonical_image_urls": {
        "original": "https://example.com/rice1.jpg",
        "thumbnail": "https://example.com/rice1_thumb.jpg"
      },
      "attributes": {
        "description": "Premium quality basmati rice",
        "weight": "1kg",
        "origin": "India"
      }
    }
  ],
  "source": "admin_seeding"
}
```

**Response**:
```json
{
  "success": true,
  "import_stats": {
    "total_imported": 1,
    "successful": 1,
    "failed": 0,
    "duplicates_found": 0,
    "errors": []
  },
  "message": "Import completed: 1 successful, 0 failed, 0 duplicates found"
}
```

### 7. Get Product Status History

**Endpoint**: `GET /api/v1/admin/products/{product_id}/history`

**Description**: Returns product status change history.

**Response**:
```json
{
  "success": true,
  "product_id": "prod_abc123",
  "current_status": "verified",
  "status_history": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "from_status": "pending",
      "to_status": "verified",
      "updated_by": "admin_user",
      "notes": "Product verified after quality review"
    }
  ],
  "last_updated_by": "admin_user",
  "admin_notes": "Product verified after quality review"
}
```

### 8. Get Product Quality Analytics

**Endpoint**: `GET /api/v1/admin/analytics/product-quality`

**Description**: Returns product quality analytics for admin dashboard.

**Response**:
```json
{
  "success": true,
  "analytics": {
    "status_distribution": {
      "pending": 5,
      "verified": 10,
      "admin_created": 2,
      "migrated": 4
    },
    "quality_score_stats": {
      "average": 75.5,
      "min": 20,
      "max": 100,
      "count": 21
    },
    "total_products": 21,
    "products_needing_review": 5
  }
}
```

## Authentication and Authorization

All admin endpoints require:
1. Valid JWT token in Authorization header
2. User role must be `admin`
3. Non-admin users receive "Admin access required" error

## Database Schema Updates

### Global Products Table

New fields added to support admin workflow:

```python
{
  "quality_score": 85,           # Calculated quality score (0-100)
  "import_source": "admin",      # Source of product creation
  "last_updated_by": "admin_user", # Last user to update product
  "admin_notes": "Verified product", # Admin notes
  "status_history": [            # Array of status changes
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "from_status": "pending",
      "to_status": "verified",
      "updated_by": "admin_user",
      "notes": "Product verified"
    }
  ]
}
```

## Usage Examples

### Admin Seeding Workflow

1. **Prepare Product Data**: Create JSON array of products with complete information
2. **Bulk Import**: Use `/api/v1/admin/products/bulk-import` to seed catalog
3. **Review Results**: Check import statistics for success/failure rates
4. **Quality Review**: Use `/api/v1/admin/products/needing-review` to find products needing attention

### Quality Control Workflow

1. **Identify Issues**: Use analytics endpoint to find low-quality products
2. **Review Products**: Get products by status (pending, flagged)
3. **Update Status**: Use individual or bulk status update endpoints
4. **Track Changes**: Review status history for audit trail

### Store Owner Contribution Workflow

1. **Store Creates Product**: Product automatically gets `pending` status
2. **Admin Reviews**: Admin uses review endpoints to assess quality
3. **Admin Approves/Rejects**: Update status to `verified` or `flagged`
4. **Quality Tracking**: System tracks all changes with timestamps and notes

## Testing

A comprehensive test suite is available in `test_admin_workflow.py` that covers:

- ✅ Product status retrieval
- ✅ Products needing review
- ✅ Products by status filtering
- ✅ Bulk import functionality
- ✅ Quality analytics
- ✅ Access control (admin vs non-admin)

## Benefits

1. **Quality Control**: Automated quality scoring and admin review workflows
2. **Scalability**: Bulk import capabilities for large product catalogs
3. **Audit Trail**: Complete history of product status changes
4. **Flexibility**: Support for both admin seeding and community contributions
5. **Analytics**: Comprehensive quality metrics and status distribution
6. **Security**: Role-based access control for admin functions

## Future Enhancements

1. **Automated Quality Checks**: AI-powered quality assessment
2. **Batch Processing**: Asynchronous bulk operations for large datasets
3. **Quality Thresholds**: Configurable quality score requirements
4. **Notification System**: Alerts for products needing review
5. **Advanced Analytics**: Trend analysis and quality improvement insights

