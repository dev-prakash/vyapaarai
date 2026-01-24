"""
Enterprise Product Media Management Service
Handles multipart file uploads, validation, processing, and S3 storage
"""

import io
import boto3
from PIL import Image
from typing import List, Dict, Optional, BinaryIO, Tuple

# Optional: imagehash for perceptual hashing (deduplication)
try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
from fastapi import UploadFile, HTTPException
import logging
import uuid
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

# S3 Configuration
S3_CLIENT = boto3.client('s3')
IMAGE_BUCKET = 'vyapaarai-product-images-prod'

# Validation Constants
MAX_IMAGES_PER_PRODUCT = 10
MAX_VIDEOS_PER_PRODUCT = 2
MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 100
SUPPORTED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}
SUPPORTED_VIDEO_FORMATS = {'MP4', 'WEBM', 'MOV'}
SUPPORTED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    'video/mp4', 'video/webm', 'video/quicktime'
}

# Image Sizes
IMAGE_SIZES = {
    'thumbnail': 200,
    'medium': 800,
    'large': 1024
}


class ProductMediaService:
    """
    Enterprise-grade product media management service

    Features:
    - Multipart file upload support
    - Comprehensive validation (size, format, content-type)
    - Automatic thumbnail generation
    - Perceptual hashing for deduplication
    - S3 storage with proper caching headers
    - Transaction-safe operations
    - Async processing support
    """

    def __init__(self):
        self.s3_client = S3_CLIENT
        self.bucket = IMAGE_BUCKET
        self.max_image_size = MAX_IMAGE_SIZE_MB * 1024 * 1024
        self.max_video_size = MAX_VIDEO_SIZE_MB * 1024 * 1024

    async def upload_product_images(
        self,
        product_id: str,
        files: List[UploadFile],
        existing_image_count: int = 0,
        primary_image_index: int = 0
    ) -> Dict:
        """
        Upload multiple product images with validation and processing

        Args:
            product_id: Product ID for S3 key prefix
            files: List of UploadFile objects from FastAPI
            existing_image_count: Number of existing images
            primary_image_index: Index of primary image (default: 0)

        Returns:
            {
                "canonical_urls": {
                    "original": "https://...",
                    "thumbnail": "https://...",
                    "medium": "https://...",
                    "image_2": "https://...",
                    ...
                },
                "image_hash": "abc123",
                "processed_count": 5,
                "failed_count": 0,
                "total_images": 5,
                "primary_image": "original"
            }

        Raises:
            HTTPException: For validation errors or processing failures
        """
        # Validation: Check total image count
        total_count = existing_image_count + len(files)
        if total_count > MAX_IMAGES_PER_PRODUCT:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_IMAGES_PER_PRODUCT} images allowed per product. "
                       f"You have {existing_image_count} existing images and attempting to upload {len(files)}."
            )

        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate all files before processing
        await self._validate_files(files, is_video=False)

        # Process images
        result = {
            "canonical_urls": {},
            "image_hash": None,
            "processed_count": 0,
            "failed_count": 0,
            "total_images": total_count,
            "primary_image": None,
            "errors": []
        }

        try:
            # Process primary image first
            primary_file = files[primary_image_index]
            primary_result = await self._process_and_upload_image(
                product_id,
                primary_file,
                is_primary=True
            )

            result['canonical_urls'].update(primary_result['urls'])
            result['image_hash'] = primary_result['image_hash']
            result['primary_image'] = 'original'
            result['processed_count'] += 1

            logger.info(f"Processed primary image for product {product_id}")

            # Process additional images
            image_index = existing_image_count + 2  # Start after existing + primary
            for idx, file in enumerate(files):
                if idx == primary_image_index:
                    continue  # Skip primary (already processed)

                try:
                    additional_result = await self._process_and_upload_image(
                        product_id,
                        file,
                        is_primary=False,
                        image_number=image_index
                    )

                    result['canonical_urls'].update(additional_result['urls'])
                    result['processed_count'] += 1
                    image_index += 1

                except Exception as e:
                    logger.error(f"Failed to process image {idx}: {str(e)}")
                    result['failed_count'] += 1
                    result['errors'].append({
                        'file': file.filename,
                        'error': str(e)
                    })

            logger.info(
                f"Upload complete for product {product_id}: "
                f"{result['processed_count']} succeeded, {result['failed_count']} failed"
            )

            return result

        except Exception as e:
            logger.error(f"Fatal error uploading images for product {product_id}: {str(e)}")
            # Attempt cleanup of any uploaded files
            await self._cleanup_uploaded_files(product_id, result['canonical_urls'])
            raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    async def _process_and_upload_image(
        self,
        product_id: str,
        file: UploadFile,
        is_primary: bool = False,
        image_number: int = None
    ) -> Dict:
        """
        Process single image: validate, resize, generate thumbnails, upload to S3

        Returns:
            {
                "urls": {
                    "original": "https://...",
                    "thumbnail": "https://...",
                    "medium": "https://..."
                },
                "image_hash": "abc123" (only for primary)
            }
        """
        # Read file content
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Validate file size
        if len(content) > self.max_image_size:
            raise ValueError(
                f"Image {file.filename} exceeds maximum size of {MAX_IMAGE_SIZE_MB}MB"
            )

        # Open and validate image
        try:
            img = Image.open(io.BytesIO(content))

            # Validate format
            if img.format not in SUPPORTED_IMAGE_FORMATS:
                raise ValueError(f"Unsupported format: {img.format}")

            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                    img = background

        except Exception as e:
            raise ValueError(f"Invalid image file {file.filename}: {str(e)}")

        urls = {}
        image_hash = None

        # Compute perceptual hash for primary image (if available)
        if is_primary and IMAGEHASH_AVAILABLE:
            image_hash = str(imagehash.phash(img))

        # Generate and upload different sizes
        if is_primary:
            # Primary image: original, thumbnail, medium, large
            sizes = {
                'original': img,
                'thumbnail': self._resize_image(img, IMAGE_SIZES['thumbnail']),
                'medium': self._resize_image(img, IMAGE_SIZES['medium']),
                'large': self._resize_image(img, IMAGE_SIZES['large'])
            }

            for size_name, sized_img in sizes.items():
                s3_key = f"{product_id}/{size_name}.jpg"
                s3_url = await self._upload_to_s3(sized_img, s3_key)
                urls[size_name] = s3_url
        else:
            # Additional images: stored as image_2, image_3, etc.
            s3_key = f"{product_id}/image_{image_number}.jpg"
            s3_url = await self._upload_to_s3(img, s3_key)
            urls[f'image_{image_number}'] = s3_url

        return {
            'urls': urls,
            'image_hash': image_hash
        }

    async def _upload_to_s3(self, img: Image.Image, s3_key: str) -> str:
        """
        Upload image to S3 with proper headers

        Returns:
            Public S3 URL
        """
        # Convert image to bytes
        img_bytes = self._image_to_bytes(img)

        # Upload to S3
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=img_bytes,
                ContentType='image/jpeg',
                CacheControl='public, max-age=31536000',  # 1 year cache
                Metadata={
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'service': 'product-media-service'
                }
            )

            # Return public URL with region
            return f"https://{self.bucket}.s3.ap-south-1.amazonaws.com/{s3_key}"

        except Exception as e:
            logger.error(f"S3 upload failed for {s3_key}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

    async def delete_product_images(
        self,
        product_id: str,
        image_keys: Optional[List[str]] = None
    ) -> Dict:
        """
        Delete product images from S3

        Args:
            product_id: Product ID
            image_keys: Specific image keys to delete (e.g., ['image_2', 'image_3'])
                       If None, deletes all images for product

        Returns:
            {
                "deleted_count": 5,
                "failed_count": 0,
                "deleted_keys": ["image_2", "image_3"]
            }
        """
        try:
            result = {
                "deleted_count": 0,
                "failed_count": 0,
                "deleted_keys": []
            }

            if image_keys is None:
                # Delete all images for product
                prefix = f"{product_id}/"
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=prefix
                )

                if 'Contents' in response:
                    for obj in response['Contents']:
                        try:
                            self.s3_client.delete_object(
                                Bucket=self.bucket,
                                Key=obj['Key']
                            )
                            result['deleted_count'] += 1
                            result['deleted_keys'].append(obj['Key'])
                        except Exception as e:
                            logger.error(f"Failed to delete {obj['Key']}: {str(e)}")
                            result['failed_count'] += 1
            else:
                # Delete specific images
                for key in image_keys:
                    try:
                        s3_key = f"{product_id}/{key}.jpg"
                        self.s3_client.delete_object(
                            Bucket=self.bucket,
                            Key=s3_key
                        )
                        result['deleted_count'] += 1
                        result['deleted_keys'].append(key)
                    except Exception as e:
                        logger.error(f"Failed to delete {key}: {str(e)}")
                        result['failed_count'] += 1

            return result

        except Exception as e:
            logger.error(f"Error deleting images for product {product_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    async def _validate_files(self, files: List[UploadFile], is_video: bool = False) -> None:
        """
        Validate uploaded files before processing

        Raises:
            HTTPException: If validation fails
        """
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        max_count = MAX_VIDEOS_PER_PRODUCT if is_video else MAX_IMAGES_PER_PRODUCT
        if len(files) > max_count:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {max_count} {'videos' if is_video else 'images'} allowed per upload"
            )

        for file in files:
            # Validate content type
            if file.content_type not in SUPPORTED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported content type: {file.content_type}. "
                           f"Supported types: {', '.join(SUPPORTED_MIME_TYPES)}"
                )

            # Validate filename
            if not file.filename:
                raise HTTPException(status_code=400, detail="File has no filename")

    async def _cleanup_uploaded_files(self, product_id: str, urls: Dict) -> None:
        """
        Clean up uploaded files in case of failure
        """
        try:
            keys_to_delete = []
            for key, url in urls.items():
                # Extract S3 key from URL
                if f"{product_id}/" in url:
                    s3_key = url.split(f".s3.amazonaws.com/")[1]
                    keys_to_delete.append(s3_key)

            for key in keys_to_delete:
                try:
                    self.s3_client.delete_object(Bucket=self.bucket, Key=key)
                except Exception as e:
                    logger.error(f"Failed to cleanup {key}: {str(e)}")

        except Exception as e:
            logger.error(f"Cleanup failed for product {product_id}: {str(e)}")

    def _resize_image(self, img: Image.Image, max_size: int) -> Image.Image:
        """Resize image maintaining aspect ratio"""
        img_copy = img.copy()
        img_copy.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return img_copy

    def _image_to_bytes(self, img: Image.Image, quality: int = 85) -> bytes:
        """Convert PIL Image to JPEG bytes"""
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()

    async def get_product_images(self, product_id: str) -> Dict:
        """
        Get all images for a product from S3 with public URLs

        Returns:
            {
                "product_id": "GP123",
                "images": {
                    "original": "https://...",
                    "thumbnail": "https://...",
                    "medium": "https://...",
                    "image_2": "https://...",
                    ...
                },
                "total_count": 5
            }
        """
        try:
            prefix = f"{product_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )

            images = {}
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # Extract image name (e.g., 'original', 'image_2')
                    image_name = key.split('/')[-1].replace('.jpg', '')

                    # Use public S3 URL (bucket is configured for public read access)
                    images[image_name] = f"https://{self.bucket}.s3.ap-south-1.amazonaws.com/{key}"

            return {
                "product_id": product_id,
                "images": images,
                "total_count": len(images)
            }

        except Exception as e:
            logger.error(f"Error fetching images for product {product_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch images: {str(e)}")


# Singleton instance
product_media_service = ProductMediaService()
