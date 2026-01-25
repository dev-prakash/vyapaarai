# Product Image Population Guide

This guide explains how to automatically fetch and upload images for all products in your VyaparAI catalog.

## 🎯 Overview

The script will:
1. Fetch all 173 products from DynamoDB (`vyaparai-global-products-prod`)
2. Search Pexels API for relevant product images
3. Download high-quality images
4. Upload images to your product media service
5. Generate thumbnails automatically (200px, 800px, 1024px)

## 📋 Prerequisites

1. **Pexels API Key** (Free)
   - Go to: https://www.pexels.com/api/
   - Click "Get Started" and sign up (free account)
   - Create an API key
   - Copy your API key

2. **Python Dependencies**
   ```bash
   pip install boto3 requests
   ```

3. **AWS Credentials**
   - Ensure AWS CLI is configured with access to DynamoDB
   - Region: `ap-south-1`

## 🚀 Usage

### Step 1: Set Pexels API Key

```bash
export PEXELS_API_KEY='your-pexels-api-key-here'
```

### Step 2: Test with 5 Products (Recommended First)

```bash
cd backend
python scripts/populate_product_images.py --mode test
```

This will:
- Process first 5 products only
- Show detailed progress
- Let you verify everything works

### Step 3: Run Full Population

Once you've verified the test run works:

```bash
python scripts/populate_product_images.py --mode full
```

This will process all 173 products.

### Step 4: Process Single Product (Optional)

To update a specific product:

```bash
python scripts/populate_product_images.py --mode single --product-id prod_abc123
```

## 📊 What to Expect

### Test Mode Output Example:
```
============================================================
VyaparAI Product Image Population Script
============================================================
✓ Admin login successful

📦 Fetching products from DynamoDB...
✓ Found 173 products

🧪 TEST MODE: Processing first 5 products

[1/5]
============================================================
Processing: Basmati Rice 1kg
Product ID: prod_abc123
Brand: Tata, Category: Grocery
   Searching Pexels for: 'Basmati Rice 1kg Tata Grocery'
   Downloaded image to: /tmp/product_images/prod_abc123.jpg
   ✓ Uploaded 1 image(s) for prod_abc123
   Processed: 1, Failed: 0
   Image credit: John Doe (https://pexels.com/photo/123456)
✓ Successfully uploaded image for: Basmati Rice 1kg

...

============================================================
SUMMARY
============================================================
Total products processed: 5
Images found on Pexels:   4
Images uploaded:          4
Failed:                   1
Skipped (already have):   0
Duration:                 45.2 seconds
============================================================
```

## ⚙️ Configuration

Edit `scripts/populate_product_images.py` to customize:

```python
# Rate limiting (avoid API throttling)
PEXELS_DELAY = 1.0     # Delay between Pexels API calls
UPLOAD_DELAY = 2.0     # Delay between uploads

# API endpoints
API_BASE_URL = 'https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com'
DYNAMODB_TABLE = 'vyaparai-global-products-prod'
```

## 🔍 How It Works

1. **Product Fetching**: Scans DynamoDB table for all products
2. **Image Search**: Builds search query from product name + brand + category
3. **Smart Selection**: Chooses square-oriented images (best for product listings)
4. **Download**: Saves high-quality (large2x) images temporarily
5. **Upload**: Uses product media API to upload images
6. **Auto Processing**: API automatically creates thumbnails and stores in S3
7. **Cleanup**: Removes temporary downloaded files

## 📸 Image Attribution

All images from Pexels are free to use (Pexels License). The script logs photographer credits.

## ⚠️ Important Notes

1. **Skips Existing Images**: Products that already have images are automatically skipped
2. **Rate Limiting**: Built-in delays prevent API throttling
3. **Free Tier**: Pexels allows generous free usage for commercial projects
4. **Quality**: Images are high-resolution (1920x1280 or larger)
5. **Square Format**: Script prefers square images for consistent product displays

## 🐛 Troubleshooting

### Error: "Pexels API key required"
- Make sure you've exported PEXELS_API_KEY environment variable
- Or use: `--api-key 'your-key'` flag

### Error: "Failed to authenticate"
- Check admin credentials in script (ADMIN_EMAIL, ADMIN_PASSWORD)
- Verify API endpoint is correct

### Error: "No images found"
- Some products may not have relevant images on Pexels
- Try modifying search terms in script
- Consider manual upload for these products

### Upload fails
- Check Lambda function is running
- Verify S3 bucket permissions
- Ensure network connectivity

## 📈 Performance

- **Test mode (5 products)**: ~1-2 minutes
- **Full mode (173 products)**: ~45-60 minutes
  - ~20-30 seconds per product (search + download + upload + processing)

## 🎨 Sample Search Queries Generated

The script builds intelligent search queries:

- "Basmati Rice 1kg Tata Grocery" → Rice product image
- "Coca Cola 500ml Coca-Cola Beverages" → Coke bottle
- "Surf Excel 1kg Detergent HUL" → Detergent pack
- "Amul Butter 100g Amul Dairy" → Butter product

## ✅ Post-Processing

After the script completes:

1. Check product images at: `https://vyapaarai-product-images-prod.s3.amazonaws.com/`
2. Verify in admin panel
3. Products will have:
   - Original high-res image
   - 200px thumbnail
   - 800px medium size
   - 1024px large size

## 🔄 Re-running

Safe to re-run anytime:
- Skips products that already have images
- No duplicate uploads
- Only processes products without images

## 📞 Support

If you encounter issues:
1. Check logs in console output
2. Verify AWS permissions
3. Test with single product first (`--mode single`)
4. Check Pexels API quota
