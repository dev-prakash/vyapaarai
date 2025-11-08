"""
Image Processing Service
Handles image downloading, hashing, thumbnailing, and S3 storage for product imports
"""

import requests
import hashlib
import io
import re
from PIL import Image
import imagehash
import boto3
from typing import List, Dict, Optional, Tuple
import time
import os

# S3 setup
s3_client = boto3.client('s3')
IMAGE_BUCKET = 'vyapaarai-product-images-prod'

class ImageProcessor:
    """Handle image downloading, hashing, thumbnailing, and S3 storage"""
    
    def __init__(self):
        self.s3_client = s3_client
        self.bucket = IMAGE_BUCKET
        self.max_image_size = 10 * 1024 * 1024  # 10MB max
        self.supported_formats = {'JPEG', 'PNG', 'WEBP', 'GIF'}
    
    def process_images(self, image_urls: List[str], product_id: str) -> Dict[str, any]:
        """
        Download images, compute hash, generate thumbnails, upload to S3
        
        Args:
            image_urls: List of image URLs to process
            product_id: Product ID for S3 key prefix
        
        Returns:
            {
                "canonical_urls": {
                    "original": "s3://bucket/product_id/original.jpg",
                    "thumbnail": "s3://bucket/product_id/thumb.jpg",
                    "medium": "s3://bucket/product_id/medium.jpg"
                },
                "image_hash": "abc123def456",  # perceptual hash of first image
                "processed_count": 3,
                "failed_count": 0
            }
        """
        
        if not image_urls:
            return {"canonical_urls": {}, "image_hash": None, "processed_count": 0, "failed_count": 0}
        
        processed = {
            "canonical_urls": {},
            "image_hash": None,
            "processed_count": 0,
            "failed_count": 0
        }
        
        # Process first image (primary)
        try:
            primary_img_data = self.download_image(image_urls[0])
            primary_img = Image.open(io.BytesIO(primary_img_data))
            
            # Validate image format
            if primary_img.format not in self.supported_formats:
                raise ValueError(f"Unsupported image format: {primary_img.format}")
            
            # Compute perceptual hash
            processed['image_hash'] = str(imagehash.phash(primary_img))
            
            # Generate different sizes
            sizes = {
                "original": primary_img,
                "medium": self.resize_image(primary_img, max_size=800),
                "thumbnail": self.resize_image(primary_img, max_size=200)
            }
            
            # Upload to S3
            for size_name, img in sizes.items():
                s3_key = f"{product_id}/{size_name}.jpg"
                img_bytes = self.image_to_bytes(img)
                
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=img_bytes,
                    ContentType='image/jpeg',
                    CacheControl='public, max-age=31536000'  # 1 year cache
                )
                
                processed['canonical_urls'][size_name] = f"s3://{self.bucket}/{s3_key}"
                processed['processed_count'] += 1
            
            # Process additional images (image_2 to image_10)
            for idx, url in enumerate(image_urls[1:], start=2):
                try:
                    img_data = self.download_image(url)
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Validate format
                    if img.format not in self.supported_formats:
                        print(f"Skipping image {idx}: unsupported format {img.format}")
                        processed['failed_count'] += 1
                        continue
                    
                    # Store additional images
                    s3_key = f"{product_id}/image_{idx}.jpg"
                    img_bytes = self.image_to_bytes(img)
                    
                    self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=s3_key,
                        Body=img_bytes,
                        ContentType='image/jpeg',
                        CacheControl='public, max-age=31536000'
                    )
                    
                    processed['canonical_urls'][f'image_{idx}'] = f"s3://{self.bucket}/{s3_key}"
                    processed['processed_count'] += 1
                    
                except Exception as e:
                    print(f"Failed to process image {idx}: {str(e)}")
                    processed['failed_count'] += 1
                    continue
        
        except Exception as e:
            raise ValueError(f"Failed to process primary image: {str(e)}")
        
        return processed
    
    def download_image(self, url: str, timeout: int = 10) -> bytes:
        """
        Download image from URL with timeout and validation
        
        Args:
            url: Image URL to download
            timeout: Request timeout in seconds
        
        Returns:
            Image data as bytes
        
        Raises:
            ValueError: If download fails or content is invalid
        """
        try:
            # Validate URL format
            if not self.is_valid_url(url):
                raise ValueError(f"Invalid URL format: {url}")
            
            # Download with timeout
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Validate content type
            content_type = response.headers.get('Content-Type', '').lower()
            if not any(fmt in content_type for fmt in ['image/', 'application/octet-stream']):
                raise ValueError(f"Invalid content type: {content_type}")
            
            # Check content length
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > self.max_image_size:
                raise ValueError(f"Image too large: {content_length} bytes")
            
            # Download content
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > self.max_image_size:
                    raise ValueError(f"Image too large: {len(content)} bytes")
            
            if len(content) == 0:
                raise ValueError("Empty image content")
            
            return content
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to download image: {str(e)}")
        except Exception as e:
            raise ValueError(f"Image download error: {str(e)}")
    
    def is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        url_pattern = re.compile(
            r'^https?://'  # http or https
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None
    
    def resize_image(self, img: Image.Image, max_size: int) -> Image.Image:
        """
        Resize image maintaining aspect ratio
        
        Args:
            img: PIL Image object
            max_size: Maximum width or height in pixels
        
        Returns:
            Resized PIL Image
        """
        # Convert to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparency
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Resize maintaining aspect ratio
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return img
    
    def image_to_bytes(self, img: Image.Image, format: str = 'JPEG', quality: int = 85) -> bytes:
        """
        Convert PIL Image to bytes
        
        Args:
            img: PIL Image object
            format: Output format (JPEG, PNG, etc.)
            quality: JPEG quality (1-100)
        
        Returns:
            Image data as bytes
        """
        output = io.BytesIO()
        
        # Ensure RGB mode for JPEG
        if format == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        img.save(output, format=format, quality=quality, optimize=True)
        return output.getvalue()
    
    def compute_image_hash(self, image_data: bytes) -> str:
        """
        Compute perceptual hash for image deduplication
        
        Args:
            image_data: Image data as bytes
        
        Returns:
            Perceptual hash as string
        """
        try:
            img = Image.open(io.BytesIO(image_data))
            return str(imagehash.phash(img))
        except Exception as e:
            raise ValueError(f"Failed to compute image hash: {str(e)}")
    
    def validate_image_urls(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        Validate a list of image URLs
        
        Returns:
            {
                "valid": ["url1", "url2"],
                "invalid": ["url3", "url4"],
                "errors": {"url3": "Invalid format", "url4": "Connection failed"}
            }
        """
        result = {
            "valid": [],
            "invalid": [],
            "errors": {}
        }
        
        for url in urls:
            try:
                # Quick validation without full download
                response = requests.head(url, timeout=5)
                response.raise_for_status()
                
                content_type = response.headers.get('Content-Type', '').lower()
                if 'image/' in content_type:
                    result["valid"].append(url)
                else:
                    result["invalid"].append(url)
                    result["errors"][url] = f"Invalid content type: {content_type}"
                    
            except Exception as e:
                result["invalid"].append(url)
                result["errors"][url] = str(e)
        
        return result
    
    def cleanup_failed_uploads(self, product_id: str, failed_keys: List[str]) -> bool:
        """
        Clean up failed image uploads from S3
        
        Args:
            product_id: Product ID
            failed_keys: List of S3 keys that failed to upload
        
        Returns:
            True if cleanup successful
        """
        try:
            for key in failed_keys:
                self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            print(f"Error cleaning up failed uploads: {e}")
            return False
