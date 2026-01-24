# VyaparAI Bulk Import System Guide

## Overview

The Bulk Import System enables administrators to import large product catalogs (thousands of products) via CSV files. The system is built for scale, reliability, and fault tolerance with async processing, checkpoint/resume capability, and comprehensive error reporting.

**Key Capabilities**:
- Async CSV processing with progress tracking
- Automatic duplicate detection
- Image processing and optimization
- Checkpoint/resume for large files (>5000 rows)
- Detailed error reporting with downloadable CSV
- Quality scoring for imported products
- Support for multi-language product names
- Regional product variations

---

## Architecture

### Components

1. **Import Job Service** (`import_job_service.py`)
   - Manages job lifecycle
   - Tracks status and progress
   - Stores job metadata in DynamoDB

2. **Background Worker** (`process_import_job.py`)
   - Lambda function for async CSV processing
   - Handles chunked processing (50 rows at a time)
   - Implements checkpoint/resume logic

3. **Product Catalog Service** (`product_catalog_service.py`)
   - Creates global products
   - Performs duplicate detection
   - Calculates quality scores

4. **Image Processor** (`image_processor.py`)
   - Downloads and processes product images
   - Generates thumbnails and optimized versions
   - Computes image hashes for deduplication

5. **DynamoDB Table**: `vyaparai-import-jobs-prod`
   - Stores job records with TTL (30 days)
   - GSIs for querying by user, status, job type

6. **S3 Buckets**:
   - `vyapaarai-bulk-uploads-prod`: Input CSV files
   - `vyapaarai-product-images-prod`: Processed images
   - Error reports stored in same bucket as input

---

## Import Job Lifecycle

### 1. Job Creation (QUEUED)
```
Admin uploads CSV → Validate structure → Create job record → Store CSV in S3 → Status: QUEUED
```

### 2. Job Processing (PROCESSING)
```
Lambda triggered → Download CSV → Parse rows → Process in chunks → Update progress
```

### 3. Chunked Processing
- Process 50 rows per chunk
- Check Lambda timeout (leave 30s buffer)
- Save checkpoint if timeout approaching
- Re-invoke Lambda with checkpoint to resume

### 4. Job Completion
- **COMPLETED**: All rows processed successfully
- **COMPLETED_WITH_ERRORS**: Some rows failed (error report generated)
- **FAILED**: Critical error occurred
- **CANCELLED**: User cancelled job

---

## CSV Format Specification

### Required Headers

**Minimum Required**:
- `name` - Product name (required)
- `category` - Product category (required)

**Recommended Headers**:
- `brand` - Brand name
- `barcode` - EAN/UPC barcode (8-13 digits)
- `additional_barcodes` - Comma-separated additional barcodes
- `description` - Product description
- `size` - Package size (e.g., "500")
- `unit` - Unit of measurement (e.g., "grams", "ml", "pieces")
- `weight` - Product weight
- `pack_size` - Number of items in pack
- `manufacturer` - Manufacturer name
- `country_of_origin` - Country code (e.g., "IN", "US")
- `ingredients` - Ingredient list

### Image Headers
- `image_url_1` to `image_url_10` - Up to 10 image URLs per product

### Nutrition Headers
- `nutrition_calories` - Calories per serving
- `nutrition_protein` - Protein content
- `nutrition_carbohydrates` - Carbs content
- `nutrition_fat` - Fat content
- `nutrition_sugar` - Sugar content
- (Add any other nutrition fields with `nutrition_` prefix)

### Regional Names Headers
- `regional_names_HI` - Hindi names (pipe-separated: "name1|name2")
- `regional_names_TA` - Tamil names
- `regional_names_TE` - Telugu names
- `regional_names_MR` - Marathi names
- `regional_names_BN` - Bengali names
- (Add any language code)

### Example CSV

```csv
name,brand,category,barcode,description,size,unit,weight,manufacturer,country_of_origin,image_url_1,image_url_2,nutrition_calories,nutrition_protein,regional_names_HI,regional_names_TA
Tata Salt,Tata,Grocery,8901234567890,Premium iodized salt,1,kg,1000,Tata Consumer Products,IN,https://example.com/tata-salt-1.jpg,https://example.com/tata-salt-2.jpg,0,0,टाटा नमक,டாடா உப்பு
Amul Butter,Amul,Dairy,8901430001234,Delicious table butter,500,grams,500,Amul,IN,https://example.com/amul-butter.jpg,,100,1,अमूल मक्खन,அமுல் வெண்ணெய்
```

---

## Import Options

Configure import behavior with these options:

```python
{
  "skip_duplicates": True,              # Skip if barcode/name+brand match exists
  "auto_verify": False,                 # Auto-verify imported products
  "default_verification_status": "admin_created",  # Status for new products
  "process_images": True,               # Download and process images
  "default_region": "IN",               # Primary region for products
  "match_strategy": "strict",           # "strict" or "fuzzy" duplicate matching
  "notification_email": "admin@example.com"  # Email for completion notification
}
```

### Match Strategies

**Strict Matching** (recommended):
- Exact barcode match, OR
- Exact name + brand match, OR
- Image hash match (if images provided)

**Fuzzy Matching**:
- Fuzzy string matching on name (Levenshtein distance)
- Useful for products with slight name variations
- Higher chance of false positives

---

## API Endpoints

### 1. Create Import Job
```http
POST /api/v1/admin/products/import

Authorization: Bearer {admin_token}
Content-Type: multipart/form-data

Body:
- file: CSV file
- job_type: "admin_product_import"
- options: JSON string (import options)

Response:
{
  "job_id": "admin_import_20250106_abc123",
  "status": "queued",
  "estimated_completion_at": "2025-01-06T10:45:00Z",
  "estimated_rows": 5000
}
```

### 2. Get Job Status
```http
GET /api/v1/admin/products/import/{job_id}

Authorization: Bearer {admin_token}

Response:
{
  "job_id": "admin_import_20250106_abc123",
  "status": "processing",
  "total_rows": 5000,
  "processed_rows": 2500,
  "successful_count": 2400,
  "duplicate_count": 75,
  "error_count": 25,
  "recent_errors": [
    {
      "row_number": 1523,
      "barcode": "1234567890123",
      "name": "Product XYZ",
      "error_code": "ValueError",
      "error_message": "Category is required"
    }
  ],
  "created_at": "2025-01-06T10:30:00Z",
  "started_at": "2025-01-06T10:31:00Z",
  "estimated_completion_at": "2025-01-06T10:45:00Z"
}
```

### 3. List User Jobs
```http
GET /api/v1/admin/products/import?limit=50

Authorization: Bearer {admin_token}

Response:
{
  "jobs": [
    {
      "job_id": "admin_import_20250106_abc123",
      "status": "completed",
      "total_rows": 5000,
      "successful_count": 4900,
      "error_count": 100,
      "created_at": "2025-01-06T10:30:00Z",
      "completed_at": "2025-01-06T10:42:15Z"
    }
  ]
}
```

### 4. Download Error Report
```http
GET /api/v1/admin/products/import/{job_id}/errors

Authorization: Bearer {admin_token}

Response: CSV file with error details
```

### 5. Cancel Job
```http
DELETE /api/v1/admin/products/import/{job_id}

Authorization: Bearer {admin_token}

Response:
{
  "job_id": "admin_import_20250106_abc123",
  "status": "cancelled"
}
```

---

## Quality Scoring

Each imported product receives a quality score (0-100) based on data completeness:

### Scoring Criteria

| Component | Points | Description |
|-----------|--------|-------------|
| Basic Info | 30 | Name (10) + Brand (10) + Category (10) |
| Barcode | 20 | Valid EAN/UPC barcode present |
| Images | 20 | At least one image processed |
| Attributes | 30 | Description (10), Weight/Size (10), Manufacturer (5), Origin (5) |

**Quality Tiers**:
- 90-100: Excellent (all data present)
- 70-89: Good (most data present)
- 50-69: Fair (basic data present)
- <50: Poor (missing critical data)

---

## Error Handling

### Common Errors

| Error Code | Description | Solution |
|------------|-------------|----------|
| `ValueError` | Missing required field | Add name/category to CSV |
| `DuplicateError` | Product already exists | Review duplicate or skip |
| `ValidationError` | Invalid data format | Fix barcode/date format |
| `ImageProcessingError` | Image download failed | Check image URL validity |
| `CategoryNotFound` | Invalid category | Use valid category name |

### Error Report CSV

When errors occur, a CSV is generated with these additional columns:
- `Error_Code` - Error type
- `Error_Message` - Detailed error message

Only rows with errors are included in the report for easy fixing.

---

## Checkpoint/Resume System

For large CSV files (>5000 rows), processing may exceed Lambda's 15-minute timeout.

### How It Works

1. Lambda processes chunks of 50 rows
2. After each chunk, checks remaining time
3. If <30 seconds remaining:
   - Save checkpoint: `{"last_processed_row": 2500}`
   - Re-invoke Lambda with checkpoint
   - Resume from checkpoint
4. Process continues until all rows complete

### Benefits
- No data loss for large imports
- Fault tolerance (Lambda can crash/timeout safely)
- Progress preserved across invocations

---

## Duplicate Detection

The system prevents duplicate products using multiple strategies:

### Detection Methods

1. **Barcode Match**
   - Exact match on primary barcode
   - Exact match on additional barcodes
   - Most reliable method

2. **Name + Brand Match**
   - Exact string match (case-insensitive)
   - Fallback when barcode not present

3. **Image Hash Match**
   - Perceptual hash of product images
   - Detects visually identical products
   - Useful for products without barcodes

### Behavior
- If duplicate detected and `skip_duplicates: true`:
  - Skip row (increment duplicate_count)
  - Continue to next row
- If duplicate detected and `skip_duplicates: false`:
  - Import anyway (creates duplicate)
  - Admin can merge later

---

## Image Processing

When `process_images: true`:

### Processing Pipeline

1. **Download** - Fetch images from URLs (image_url_1 to image_url_10)
2. **Validate** - Check format, size, dimensions
3. **Optimize** - Compress and resize
4. **Generate Thumbnails** - Create 3 sizes:
   - Small: 150x150px
   - Medium: 300x300px
   - Large: 800x800px
5. **Upload to S3** - Store in `vyapaarai-product-images-prod`
6. **Compute Hash** - Generate perceptual hash for deduplication

### Image URLs in Product

After processing, product receives:
```json
{
  "canonical_image_urls": [
    "https://cdn.vyapaarai.com/products/GP123456/image-1-large.jpg",
    "https://cdn.vyapaarai.com/products/GP123456/image-2-large.jpg"
  ],
  "image_hash": "a4b3c2d1e5f6"
}
```

---

## Best Practices

### CSV Preparation

1. **Clean Data**
   - Remove duplicate rows in CSV
   - Trim whitespace from all fields
   - Validate barcodes (8-13 digits only)

2. **Categorization**
   - Use consistent category names
   - Match existing category hierarchy
   - Avoid typos in category names

3. **Images**
   - Use high-quality images (min 800x800px)
   - Ensure URLs are publicly accessible
   - Use HTTPS URLs for security

4. **Regional Names**
   - Provide multiple name variations for better search
   - Use pipe separator: "name1|name2|name3"
   - Include common misspellings

### Performance Tips

1. **Batch Size**
   - Optimal: 1000-5000 rows per CSV
   - Large files (>5000) work but take longer
   - Split mega-files (>50K rows) into multiple jobs

2. **Image Processing**
   - If images are already hosted on CDN, skip processing
   - Set `process_images: false` for faster imports
   - Add images later via product update API

3. **Error Handling**
   - Fix errors in error report CSV
   - Re-upload error CSV as new job
   - Iteratively clean data

---

## Monitoring

### Job Status Dashboard

Track import progress via:
- Admin dashboard: `/admin/import-jobs`
- API polling: `GET /api/v1/admin/products/import/{job_id}`
- Email notifications (if configured)

### Metrics to Monitor

- **Total Rows**: Expected row count
- **Processed Rows**: Current progress
- **Success Rate**: (successful_count / total_rows) * 100
- **Duplicate Rate**: (duplicate_count / total_rows) * 100
- **Error Rate**: (error_count / total_rows) * 100

### CloudWatch Alarms (Recommended)

Set up alarms for:
- Import job failures (status = failed)
- High error rate (>10%)
- Long-running jobs (>30 minutes)

---

## Troubleshooting

### Job Stuck in QUEUED
- **Cause**: Lambda not triggered
- **Solution**: Check Lambda event source mapping, CloudWatch logs

### Job Stuck in PROCESSING
- **Cause**: Lambda crash or infinite loop
- **Solution**: Check Lambda logs, cancel and restart job

### High Error Rate
- **Cause**: Invalid CSV format or missing required fields
- **Solution**: Download error report, fix issues, re-upload

### Images Not Processing
- **Cause**: Image URLs inaccessible or invalid format
- **Solution**: Verify URLs are public, check image format (JPG/PNG)

### Duplicates Not Detected
- **Cause**: Barcode mismatch or fuzzy matching needed
- **Solution**: Verify barcode format, try fuzzy matching strategy

---

## Security Considerations

1. **Authentication**
   - Only admin users can create import jobs
   - Admin JWT token required for all API calls

2. **S3 Access**
   - CSV files stored in private S3 bucket
   - Pre-signed URLs for download (expire in 1 hour)

3. **Data Validation**
   - CSV structure validated before processing
   - Malicious content filtered (SQL injection, XSS)

4. **Rate Limiting**
   - Max 10 concurrent import jobs per user
   - Max 100 jobs per day per user

---

## Limitations

1. **File Size**: 50MB max CSV file size
2. **Row Limit**: No hard limit, but >50K rows may take hours
3. **Image URLs**: Max 10 images per product
4. **TTL**: Job records auto-delete after 30 days
5. **Concurrent Jobs**: Max 10 per user, 100 system-wide

---

## Future Enhancements

1. **Excel Support**: Import from .xlsx files
2. **Validation Preview**: Validate CSV without importing
3. **Partial Import**: Import only new/updated products
4. **Webhook Notifications**: Real-time job status via webhooks
5. **Import Templates**: Pre-configured templates for common use cases
6. **Scheduled Imports**: Cron-based recurring imports

---

## Code Examples

### Python: Create Import Job

```python
import requests

def create_import_job(csv_file_path, admin_token):
    url = "https://api.vyapaarai.com/api/v1/admin/products/import"

    headers = {
        "Authorization": f"Bearer {admin_token}"
    }

    files = {
        "file": open(csv_file_path, "rb")
    }

    data = {
        "job_type": "admin_product_import",
        "options": json.dumps({
            "skip_duplicates": True,
            "process_images": True,
            "default_region": "IN"
        })
    }

    response = requests.post(url, headers=headers, files=files, data=data)
    return response.json()

# Usage
result = create_import_job("products.csv", "your_admin_token")
print(f"Job ID: {result['job_id']}")
print(f"Status: {result['status']}")
```

### JavaScript: Poll Job Status

```javascript
async function pollJobStatus(jobId, adminToken) {
  const url = `https://api.vyapaarai.com/api/v1/admin/products/import/${jobId}`;

  const headers = {
    "Authorization": `Bearer ${adminToken}`
  };

  while (true) {
    const response = await fetch(url, { headers });
    const job = await response.json();

    console.log(`Progress: ${job.processed_rows}/${job.total_rows}`);

    if (["completed", "completed_with_errors", "failed", "cancelled"].includes(job.status)) {
      console.log(`Job finished with status: ${job.status}`);
      return job;
    }

    // Poll every 5 seconds
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
}

// Usage
const job = await pollJobStatus("admin_import_20250106_abc123", "your_admin_token");
console.log(`Success: ${job.successful_count}, Errors: ${job.error_count}`);
```

---

## Support

For issues or questions:
- Documentation: `/docs/BULK_IMPORT_GUIDE.md`
- API Reference: `/docs/API_REFERENCE_COMPLETE.md`
- Troubleshooting: `/docs/TROUBLESHOOTING.md`
- Email: support@vyapaarai.com

---

**Last Updated**: December 3, 2025
**Document Version**: 1.0.0
**Status**: Production Ready
