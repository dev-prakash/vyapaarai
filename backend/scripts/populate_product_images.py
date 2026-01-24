#!/usr/bin/env python3
"""
Bulk Product Image Population Script
Fetches free images from Pexels API and uploads to product catalog

Usage:
    python populate_product_images.py --mode test           # Test with 5 products
    python populate_product_images.py --mode full           # Process all products
    python populate_product_images.py --product-id prod_123 # Single product
"""

import os
import sys
import json
import time
import boto3
import requests
import argparse
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

# Configuration
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')  # Get your free key from https://pexels.com/api
DYNAMODB_TABLE = 'vyaparai-global-products-prod'
REGION = 'ap-south-1'
API_BASE_URL = 'https://jxxi8dtx1f.execute-api.ap-south-1.amazonaws.com'
ADMIN_EMAIL = 'nimda.vai@gmail.com'
ADMIN_PASSWORD = 'Admin@123!'

# Rate limiting
PEXELS_DELAY = 1.0  # Delay between Pexels API calls (seconds)
UPLOAD_DELAY = 2.0  # Delay between uploads (seconds)

# Directory for downloaded images
TEMP_DIR = Path('/tmp/product_images')
TEMP_DIR.mkdir(exist_ok=True)


class PexelsImageFetcher:
    """Fetches product images from Pexels API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.pexels.com/v1'
        self.headers = {'Authorization': api_key}

    def search_product_image(self, product_name: str, brand: str = None, category: str = None) -> Optional[Dict]:
        """
        Search for product image on Pexels

        Args:
            product_name: Product name (e.g., "Basmati Rice")
            brand: Brand name (optional)
            category: Product category (optional)

        Returns:
            Image data dict or None
        """
        # Build search query
        search_terms = []

        # Add product name
        if product_name:
            search_terms.append(product_name)

        # Add brand for specificity
        if brand:
            search_terms.append(brand)

        # Add category context
        if category:
            search_terms.append(category)

        query = ' '.join(search_terms)

        print(f"   Searching Pexels for: '{query}'")

        try:
            response = requests.get(
                f'{self.base_url}/search',
                headers=self.headers,
                params={
                    'query': query,
                    'per_page': 3,  # Get top 3 results
                    'orientation': 'square'  # Square images work best for products
                },
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            if data.get('photos') and len(data['photos']) > 0:
                photo = data['photos'][0]  # Use first result

                return {
                    'url': photo['src']['large2x'],  # High quality image
                    'photographer': photo['photographer'],
                    'photographer_url': photo['photographer_url'],
                    'pexels_url': photo['url']
                }
            else:
                print(f"   No images found for: {query}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"   Error fetching from Pexels: {e}")
            return None

    def download_image(self, image_url: str, save_path: Path) -> bool:
        """Download image from URL to local file"""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(response.content)

            print(f"   Downloaded image to: {save_path}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"   Error downloading image: {e}")
            return False


class ProductImageUploader:
    """Uploads images to VyaparAI product media API"""

    def __init__(self, api_base_url: str, admin_email: str, admin_password: str):
        self.api_base_url = api_base_url
        self.admin_email = admin_email
        self.admin_password = admin_password
        self.token = None

    def login(self) -> bool:
        """Authenticate and get admin token"""
        try:
            response = requests.post(
                f'{self.api_base_url}/api/v1/admin/auth/login',
                json={'email': self.admin_email, 'password': self.admin_password},
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('token'):
                self.token = data['token']
                print("✓ Admin login successful")
                return True
            else:
                print(f"✗ Login failed: {data}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"✗ Login error: {e}")
            return False

    def upload_product_images(self, product_id: str, image_paths: List[Path]) -> bool:
        """
        Upload images for a product

        Args:
            product_id: Product ID (e.g., "prod_abc123")
            image_paths: List of image file paths to upload

        Returns:
            True if successful
        """
        if not self.token:
            print("   Error: Not authenticated. Call login() first.")
            return False

        try:
            files = [('files', (path.name, open(path, 'rb'), 'image/jpeg')) for path in image_paths]

            response = requests.post(
                f'{self.api_base_url}/api/v1/product-media/products/{product_id}/upload-images',
                headers={'Authorization': f'Bearer {self.token}'},
                files=files,
                timeout=60
            )

            # Close file handles
            for _, (_, file_handle, _) in files:
                file_handle.close()

            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ Uploaded {len(image_paths)} image(s) for {product_id}")
                print(f"   Processed: {data.get('processed_count', 0)}, Failed: {data.get('failed_count', 0)}")
                return True
            else:
                print(f"   ✗ Upload failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"   ✗ Upload error: {e}")
            return False


class ProductImagePopulator:
    """Main orchestrator for populating product images"""

    def __init__(self, pexels_api_key: str, dynamodb_table: str, region: str):
        self.pexels = PexelsImageFetcher(pexels_api_key)
        self.uploader = ProductImageUploader(API_BASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD)
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.table_name = dynamodb_table

        # Statistics
        self.stats = {
            'total_products': 0,
            'images_found': 0,
            'images_uploaded': 0,
            'failed': 0,
            'skipped': 0
        }

    def fetch_all_products(self) -> List[Dict]:
        """Fetch all products from DynamoDB"""
        print("\n📦 Fetching products from DynamoDB...")

        products = []
        last_evaluated_key = None

        while True:
            scan_kwargs = {'TableName': self.table_name}

            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

            response = self.dynamodb.scan(**scan_kwargs)

            # Convert DynamoDB format to regular dict
            for item in response.get('Items', []):
                product = self._parse_dynamodb_item(item)
                products.append(product)

            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break

        print(f"✓ Found {len(products)} products")
        return products

    def _parse_dynamodb_item(self, item: Dict) -> Dict:
        """Convert DynamoDB item format to regular Python dict"""
        product = {}

        for key, value in item.items():
            if 'S' in value:
                product[key] = value['S']
            elif 'N' in value:
                product[key] = int(value['N']) if '.' not in value['N'] else float(value['N'])
            elif 'M' in value:
                product[key] = self._parse_dynamodb_item(value['M'])
            elif 'L' in value:
                product[key] = [self._parse_dynamodb_value(v) for v in value['L']]
            elif 'BOOL' in value:
                product[key] = value['BOOL']

        return product

    def _parse_dynamodb_value(self, value: Dict):
        """Parse a single DynamoDB value"""
        if 'S' in value:
            return value['S']
        elif 'N' in value:
            return int(value['N']) if '.' not in value['N'] else float(value['N'])
        elif 'M' in value:
            return self._parse_dynamodb_item(value['M'])
        elif 'L' in value:
            return [self._parse_dynamodb_value(v) for v in value['L']]
        elif 'BOOL' in value:
            return value['BOOL']
        return None

    def process_product(self, product: Dict) -> bool:
        """
        Process a single product: search, download, and upload image

        Args:
            product: Product dict from DynamoDB

        Returns:
            True if successful
        """
        product_id = product.get('product_id')
        product_name = product.get('name', '')
        brand = product.get('brand', '')
        category = product.get('category', '')

        print(f"\n{'='*60}")
        print(f"Processing: {product_name}")
        print(f"Product ID: {product_id}")
        print(f"Brand: {brand}, Category: {category}")

        # Check if product already has images
        canonical_urls = product.get('canonical_image_urls', {})
        if isinstance(canonical_urls, dict) and canonical_urls.get('original'):
            print(f"⊘ Product already has images. Skipping.")
            self.stats['skipped'] += 1
            return False

        # Search for image on Pexels
        image_data = self.pexels.search_product_image(product_name, brand, category)

        if not image_data:
            print(f"✗ No image found for: {product_name}")
            self.stats['failed'] += 1
            return False

        self.stats['images_found'] += 1

        # Download image
        image_filename = f"{product_id}.jpg"
        image_path = TEMP_DIR / image_filename

        if not self.pexels.download_image(image_data['url'], image_path):
            print(f"✗ Failed to download image")
            self.stats['failed'] += 1
            return False

        # Rate limiting
        time.sleep(PEXELS_DELAY)

        # Upload to VyaparAI
        if self.uploader.upload_product_images(product_id, [image_path]):
            print(f"✓ Successfully uploaded image for: {product_name}")
            print(f"   Image credit: {image_data['photographer']} ({image_data['pexels_url']})")
            self.stats['images_uploaded'] += 1

            # Clean up downloaded file
            image_path.unlink()

            # Rate limiting
            time.sleep(UPLOAD_DELAY)

            return True
        else:
            print(f"✗ Failed to upload image")
            self.stats['failed'] += 1
            return False

    def run(self, mode: str = 'test', product_id: Optional[str] = None):
        """
        Run the image population process

        Args:
            mode: 'test' (5 products), 'full' (all products), 'single' (one product)
            product_id: Specific product ID (for single mode)
        """
        print("\n" + "="*60)
        print("VyaparAI Product Image Population Script")
        print("="*60)

        # Login to admin API
        if not self.uploader.login():
            print("\n✗ Failed to authenticate. Exiting.")
            return

        # Fetch products
        if mode == 'single' and product_id:
            # Fetch single product
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'product_id': {'S': product_id}}
            )

            if 'Item' not in response:
                print(f"\n✗ Product not found: {product_id}")
                return

            products = [self._parse_dynamodb_item(response['Item'])]
        else:
            products = self.fetch_all_products()

        # Filter based on mode
        if mode == 'test':
            products = products[:5]
            print(f"\n🧪 TEST MODE: Processing first 5 products")
        elif mode == 'full':
            print(f"\n🚀 FULL MODE: Processing all {len(products)} products")

        self.stats['total_products'] = len(products)

        # Process products
        start_time = datetime.now()

        for idx, product in enumerate(products, 1):
            print(f"\n[{idx}/{len(products)}]")
            self.process_product(product)

        # Print summary
        duration = (datetime.now() - start_time).total_seconds()

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Total products processed: {self.stats['total_products']}")
        print(f"Images found on Pexels:   {self.stats['images_found']}")
        print(f"Images uploaded:          {self.stats['images_uploaded']}")
        print(f"Failed:                   {self.stats['failed']}")
        print(f"Skipped (already have):   {self.stats['skipped']}")
        print(f"Duration:                 {duration:.1f} seconds")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(description='Populate product images from Pexels API')
    parser.add_argument('--mode', choices=['test', 'full', 'single'], default='test',
                       help='Processing mode: test (5 products), full (all), single (one)')
    parser.add_argument('--product-id', help='Product ID for single mode')
    parser.add_argument('--api-key', help='Pexels API key (or set PEXELS_API_KEY env var)')

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or PEXELS_API_KEY

    if not api_key:
        print("\n✗ ERROR: Pexels API key required!")
        print("\nGet your free API key from: https://pexels.com/api")
        print("\nUsage:")
        print("  export PEXELS_API_KEY='your-api-key-here'")
        print("  python populate_product_images.py --mode test")
        print("\nOr:")
        print("  python populate_product_images.py --api-key 'your-api-key-here' --mode test")
        sys.exit(1)

    if args.mode == 'single' and not args.product_id:
        print("\n✗ ERROR: --product-id required for single mode")
        sys.exit(1)

    # Run populator
    populator = ProductImagePopulator(api_key, DYNAMODB_TABLE, REGION)
    populator.run(mode=args.mode, product_id=args.product_id)


if __name__ == '__main__':
    main()
