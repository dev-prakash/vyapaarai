# Product Image Upload Feature Documentation

## Overview

The Product Image Upload feature allows administrators to upload multiple high-quality images for products in the global product catalog. This feature supports drag-and-drop uploads, image preview, primary image selection, and automatic processing of images in multiple sizes.

## Date Added
November 14, 2025

## Components

### 1. ProductImageUpload Component
**Location**: `/frontend-pwa/src/components/Admin/ProductImageUpload.tsx`

**Features**:
- Drag-and-drop file upload
- Multiple image selection (up to 10 images per product)
- Image preview before upload
- Primary image selection (mark one image as the main product image)
- Progress indicators during upload
- File validation (size: 10MB max, formats: JPEG, PNG, WEBP, GIF)
- Error handling and retry mechanisms
- Accessibility compliant

**Props**:
```typescript
interface ProductImageUploadProps {
  productId: string;           // Required: Product ID to associate images with
  storeId?: string;           // Optional: Store ID if store-specific
  existingImages?: string[];  // Array of existing image URLs
  onUploadSuccess?: (urls: Record<string, string>) => void;
  onUploadError?: (error: string) => void;
  maxImages?: number;         // Default: 10
}
```

### 2. GlobalProductEntryForm Integration
**Location**: `/frontend-pwa/src/components/Admin/GlobalProductEntryForm.tsx`

The Product Image Upload component is integrated as the third tab in the Global Product Entry Form:

**Tab Structure**:
1. **Basic Info** - Product name, brand, category, barcode, MRP, description
2. **Attributes** - Size, weight, manufacturer, ingredients, country of origin
3. **Images** ⭐ (NEW) - Multiple product image upload
4. **Additional** - Verification status, quality score, metadata

**Important Notes**:
- Images can only be uploaded AFTER the product is created (requires product_id)
- For new products, a message is displayed: "Save the product first to upload images"
- For existing products, the full upload interface is available

## Backend API

### Endpoint
```
POST /api/v1/product-media/products/{product_id}/upload-images
```

### Request
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Authorization**: Required (JWT token)

**Form Data**:
- `files`: Multiple image files (max 10)
- `primary_image_index`: Index of the primary image (default: 0)
- `store_id`: (Optional) Store ID for store-specific images

### Response
```json
{
  "success": true,
  "processed_count": 4,
  "failed_count": 0,
  "canonical_urls": {
    "thumbnail": "https://cdn.example.com/products/ABC123/thumbnail.jpg",
    "medium": "https://cdn.example.com/products/ABC123/medium.jpg",
    "large": "https://cdn.example.com/products/ABC123/large.jpg",
    "original": "https://cdn.example.com/products/ABC123/original.jpg"
  },
  "message": "Images uploaded successfully"
}
```

## Image Processing

### Image Sizes
The backend automatically generates 4 versions of each image:
1. **Thumbnail**: 200px (max width/height)
2. **Medium**: 800px (max width/height)
3. **Large**: 1024px (max width/height)
4. **Original**: Unchanged (max 10MB)

### Image Storage
- **S3 Bucket**: `vyapaarai-product-images-prod`
- **CloudFront CDN**: Distribution EGVDTSEKZSJCI (d2asjaaus4m4w2.cloudfront.net)
- **Naming Pattern**: `products/{product_id}/{size}/{timestamp}-{hash}.{ext}`

### Image Optimization
- Format conversion to JPEG (quality: 85%)
- Maintains aspect ratio
- Automatic compression
- WebP support (optional, via Pillow)

## Lambda Configuration

### Function Details
- **Function Name**: vyaparai-api-prod
- **Runtime**: Python 3.11
- **Memory**: 512 MB
- **Timeout**: 30 seconds
- **Region**: ap-south-1

### Lambda Layer
- **Layer Name**: image-processing-layer:3
- **Size**: 4.4 MB
- **Dependencies**: Pillow 10.4.0

### IAM Permissions
The Lambda function has the following S3 permissions via `lambda-s3-policy`:
- `s3:PutObject`
- `s3:PutObjectAcl`
- `s3:GetObject`
- `s3:DeleteObject`
- `s3:ListBucket`

## Usage Guide

### For Administrators

1. **Navigate to Admin Product Catalog**
   - Go to Admin Dashboard
   - Click "Global Product Catalog"

2. **Edit an Existing Product**
   - Click the 3-dot menu (⋮) next to any product
   - Select "Edit"
   - The product edit dialog opens with 4 tabs

3. **Upload Images**
   - Click on the "Images" tab (third tab)
   - Drag and drop images or click to select files
   - Preview selected images before uploading
   - Click the star icon to mark an image as primary
   - Click "Upload X Images" to start upload

4. **View Upload Progress**
   - Progress bar shows upload percentage
   - Success/error messages appear at the top
   - Successfully uploaded images are automatically associated with the product

### For New Products

1. Create the product first in the "Basic Info" tab
2. Fill in required fields (name, category)
3. Click "Add Product" to save
4. After creation, edit the product again
5. Now the "Images" tab will be fully functional

## Validation Rules

### File Validation
- **Maximum file size**: 10 MB per image
- **Supported formats**: JPEG, PNG, WEBP, GIF
- **Maximum images**: 10 per product
- **Minimum images**: 1 (optional, but recommended)

### Upload Constraints
- Cannot upload if product doesn't exist (must have product_id)
- Cannot exceed available slots (existing + new ≤ max_images)
- All files must pass size and format validation

## Error Handling

### Common Errors

1. **"No images selected"**
   - Cause: Attempting to upload without selecting files
   - Solution: Select at least one image file

2. **"Files too large"**
   - Cause: One or more files exceed 10MB limit
   - Solution: Compress or resize images before upload

3. **"Cannot add X images. Only Y slots available"**
   - Cause: Trying to upload more images than remaining slots
   - Solution: Remove some existing images or select fewer files

4. **"Some files were rejected"**
   - Cause: Files failed format or size validation
   - Solution: Check file formats and sizes

5. **"Upload failed"** (500 error)
   - Cause: Server-side error (S3, Lambda, etc.)
   - Solution: Check Lambda logs, S3 permissions, retry upload

## Deployment

### Frontend Deployment
1. Build the frontend: `npm run build`
2. Sync to S3: `aws s3 sync dist/ s3://vyaparai-frontend-491065739648/ --delete`
3. Invalidate CloudFront cache:
   ```bash
   aws cloudfront create-invalidation --distribution-id E3J03QP8JNTADS --paths "/*"
   aws cloudfront create-invalidation --distribution-id E1VOV7MOO3DLKR --paths "/*"
   aws cloudfront create-invalidation --distribution-id E2X34H86KGI5XR --paths "/*"
   ```

### Backend Deployment
1. Build Lambda: `./scripts/docker_lambda_build.sh`
2. Deploy: `aws lambda update-function-code --function-name vyaparai-api-prod --zip-file fileb://lambda_function.zip --region ap-south-1`

### Lambda Layer Deployment
1. Create layer package: `pip install -r layer_requirements.txt -t python/`
2. Zip layer: `zip -r layer.zip python/`
3. Upload to S3: `aws s3 cp layer.zip s3://vyapaarai-product-images-prod/layers/`
4. Publish layer: `aws lambda publish-layer-version --layer-name image-processing-layer --content S3Bucket=vyapaarai-product-images-prod,S3Key=layers/layer.zip`

## Database Schema

### Global Products Table
**Table Name**: `vyaparai-global-products-prod`

**Relevant Fields**:
```
product_id: String (Primary Key)
name: String
canonical_image_urls: Map {
  thumbnail: String
  medium: String
  large: String
  original: String
}
image_hash: String (for deduplication)
updated_at: String (ISO timestamp)
```

## Performance Considerations

### Upload Speed
- Average upload time: 2-5 seconds per image
- Concurrent uploads: Up to 10 images processed simultaneously
- Network dependency: Upload speed varies based on user's connection

### S3 Costs
- Storage: ~$0.023 per GB/month (S3 Standard)
- Transfer: ~$0.09 per GB transferred out to internet
- Requests: ~$0.005 per 1,000 PUT requests

### CloudFront Caching
- Cache TTL: 31536000 seconds (1 year)
- Cache invalidation: ~$0.005 per invalidation path
- Edge locations: Global distribution for fast delivery

## Security

### Access Control
- Admin-only feature (requires admin JWT token)
- Product-level permissions (future: per-product access control)
- S3 bucket policy: Private by default, public read via CloudFront

### File Upload Security
- File type validation (MIME type checking)
- File size limits (prevents DoS attacks)
- Virus scanning: Not implemented (future consideration)
- Content validation: Image format verification via Pillow

## Future Enhancements

### Planned Features
1. **Bulk Image Upload** - Upload images for multiple products at once
2. **Image Cropping** - Allow in-browser image cropping before upload
3. **Image Editor** - Basic editing tools (rotate, resize, filters)
4. **Image Tags** - Add metadata tags to images (e.g., "front", "back", "label")
5. **Image Variants** - Support for color/style variants with separate images
6. **Image Compression** - Client-side compression before upload
7. **WebP Conversion** - Automatic WebP generation for better performance
8. **Image Search** - Reverse image search to find similar products
9. **Image Analytics** - Track which images get more views/clicks
10. **Video Upload** - Support for product videos

### Technical Improvements
1. **Progressive Upload** - Upload images one at a time with retry logic
2. **Background Processing** - Move image processing to async queue
3. **CDN Optimization** - Implement responsive images with srcset
4. **Image Lazy Loading** - Improve page load performance
5. **Image Preloading** - Prefetch images for better UX
6. **Error Recovery** - Automatic retry for failed uploads
7. **Upload Resume** - Resume interrupted uploads
8. **Batch Delete** - Delete multiple images at once

## Troubleshooting

### Images Tab Not Appearing

**Symptoms**: Only 3 tabs visible instead of 4 when editing a product

**Solutions**:
1. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Clear browser cache completely
3. Unregister service workers:
   - Open DevTools (F12)
   - Go to Application tab
   - Click Service Workers
   - Click Unregister
4. Wait for CloudFront cache invalidation (1-2 minutes)
5. Verify you're accessing the correct CloudFront URL

### Upload Fails with 403 Error

**Cause**: Lambda doesn't have S3 permissions

**Solution**:
1. Check IAM role: `vyaparai-lambda-role`
2. Verify `lambda-s3-policy` is attached
3. Check policy permissions for S3 bucket

### Upload Fails with 500 Error

**Cause**: Lambda error or timeout

**Solution**:
1. Check CloudWatch logs: `/aws/lambda/vyaparai-api-prod`
2. Verify Lambda layer is attached
3. Check Lambda timeout settings (should be ≥30s)
4. Verify Pillow is available in Lambda environment

### Images Don't Display After Upload

**Cause**: CloudFront caching or S3 permissions

**Solution**:
1. Verify S3 objects are publicly accessible via CloudFront
2. Check CloudFront distribution settings
3. Verify S3 bucket CORS configuration
4. Check browser console for CORS errors

## Code Examples

### Using ProductImageUpload Component

```typescript
import ProductImageUpload from './ProductImageUpload';

// In your component
<ProductImageUpload
  productId="GP1234567890"
  existingImages={[
    'https://cdn.example.com/products/GP1234567890/original.jpg'
  ]}
  maxImages={10}
  onUploadSuccess={(urls) => {
    console.log('Upload successful!', urls);
    // Update product data with new image URLs
  }}
  onUploadError={(error) => {
    console.error('Upload failed:', error);
    // Show error message to user
  }}
/>
```

### Backend API Call Example

```python
import requests

url = "https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com/api/v1/product-media/products/GP1234567890/upload-images"

files = [
    ('files', open('image1.jpg', 'rb')),
    ('files', open('image2.jpg', 'rb')),
]

data = {
    'primary_image_index': '0'
}

headers = {
    'Authorization': 'Bearer <JWT_TOKEN>'
}

response = requests.post(url, files=files, data=data, headers=headers)
print(response.json())
```

## Related Documentation

- [Admin Product Catalog Documentation](./admin-product-catalog.md)
- [Lambda Deployment Guide](../backend/docs/lambda-deployment.md)
- [S3 Image Storage Configuration](../infrastructure/s3-setup.md)
- [CloudFront CDN Setup](../infrastructure/cloudfront-setup.md)

## Changelog

### November 14, 2025 - Initial Release
- Added ProductImageUpload component
- Integrated into GlobalProductEntryForm as Images tab
- Deployed Lambda function with image processing
- Created Lambda layer for Pillow dependency
- Added S3 permissions to Lambda role
- Deployed to all CloudFront distributions
- Fixed TabPanel ordering issue

## Support

For issues or questions:
- Check CloudWatch logs: `/aws/lambda/vyaparai-api-prod`
- Review this documentation
- Contact: devprakash.iitmandi@gmail.com
