"""
Enterprise Product Media API Endpoints
Handles multipart file uploads for product images and videos
"""

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
import logging
import re

from app.services.product_media_service import product_media_service
from app.services.inventory_service import inventory_service
from app.core.security import get_current_store_owner

logger = logging.getLogger(__name__)

# Validation patterns
PRODUCT_ID_PATTERN = re.compile(r'^[A-Za-z0-9_\-]{1,100}$')

router = APIRouter(prefix="/product-media", tags=["product-media"])


class ImageUploadResponse(BaseModel):
    """Response model for image upload"""
    success: bool
    message: str
    canonical_urls: dict
    image_hash: Optional[str]
    processed_count: int
    failed_count: int
    total_images: int
    primary_image: Optional[str]
    errors: Optional[list] = []


class ImageDeleteResponse(BaseModel):
    """Response model for image deletion"""
    success: bool
    message: str
    deleted_count: int
    failed_count: int
    deleted_keys: list


class ImageListResponse(BaseModel):
    """Response model for image listing"""
    success: bool
    product_id: str
    images: dict
    total_count: int


def validate_product_id(product_id: str) -> str:
    """Validate product ID format to prevent path traversal and injection"""
    if not product_id or not PRODUCT_ID_PATTERN.match(product_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid product ID format. Only alphanumeric characters, hyphens, and underscores allowed."
        )
    return product_id


@router.post(
    "/products/{product_id}/upload-images",
    response_model=ImageUploadResponse,
    summary="Upload Product Images",
    description="""
    Upload multiple images for a product (max 10 images per product).

    **Features:**
    - Automatic thumbnail generation (200px, 800px, 1024px)
    - Perceptual hashing for duplicate detection
    - Format validation (JPEG, PNG, WEBP, GIF)
    - Size validation (max 10MB per image)
    - S3 storage with CDN caching

    **Supported Formats:** JPEG, PNG, WEBP, GIF
    **Max File Size:** 10MB per image
    **Max Images:** 10 per product

    **Example Usage:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/product-media/products/GP123/upload-images" \\
         -H "Authorization: Bearer YOUR_TOKEN" \\
         -F "files=@image1.jpg" \\
         -F "files=@image2.jpg" \\
         -F "primary_image_index=0"
    ```

    **Authentication Required:** Yes (store owner only)
    """
)
async def upload_product_images(
    product_id: str,
    files: List[UploadFile] = File(
        ...,
        description="Product images to upload (max 10 images, 10MB each)"
    ),
    primary_image_index: int = Form(
        0,
        description="Index of the primary image (0-based)"
    ),
    store_id: Optional[str] = Form(
        None,
        description="Store ID (optional, for verification)"
    ),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Upload multiple images for a product

    The first uploaded image (or specified by primary_image_index) becomes the primary image
    and generates all size variants (original, thumbnail, medium, large).
    Additional images are stored as image_2, image_3, etc.
    """
    try:
        # Validate product_id format to prevent path traversal
        validate_product_id(product_id)

        # Verify store ownership if store_id provided
        if store_id:
            user_store_id = current_user.get('store_id')
            if user_store_id and user_store_id != store_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only upload images to your own store's products"
                )

        logger.info(
            f"User {current_user.get('user_id', 'unknown')} uploading {len(files)} images "
            f"for product {product_id}, primary index: {primary_image_index}"
        )

        # Validate product exists (optional but recommended)
        if store_id:
            product = await inventory_service.get_product(store_id, product_id)
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {product_id} not found in store {store_id}"
                )

        # Validate primary_image_index
        if primary_image_index < 0 or primary_image_index >= len(files):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid primary_image_index: {primary_image_index}. "
                       f"Must be between 0 and {len(files) - 1}"
            )

        # Get existing image count (if product exists in global products table)
        # TODO: Integrate with global products service to get existing count
        existing_image_count = 0

        # Upload images
        result = await product_media_service.upload_product_images(
            product_id=product_id,
            files=files,
            existing_image_count=existing_image_count,
            primary_image_index=primary_image_index
        )

        # TODO: Update DynamoDB global products table with new canonical_urls
        # This would require integration with product catalog service

        logger.info(
            f"Successfully uploaded images for product {product_id}: "
            f"{result['processed_count']} succeeded, {result['failed_count']} failed"
        )

        return ImageUploadResponse(
            success=True,
            message=f"Successfully uploaded {result['processed_count']} images",
            canonical_urls=result['canonical_urls'],
            image_hash=result['image_hash'],
            processed_count=result['processed_count'],
            failed_count=result['failed_count'],
            total_images=result['total_images'],
            primary_image=result['primary_image'],
            errors=result.get('errors', [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading images for product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload images: {str(e)}"
        )


@router.get(
    "/products/{product_id}/images",
    response_model=ImageListResponse,
    summary="List Product Images",
    description="Get all images for a product from S3"
)
async def get_product_images(product_id: str):
    """
    Retrieve all images for a product

    Returns URLs for all image variants:
    - original: Full resolution
    - thumbnail: 200x200px
    - medium: 800x800px
    - large: 1024x1024px
    - image_2 through image_10: Additional images
    """
    try:
        logger.info(f"Fetching images for product {product_id}")

        result = await product_media_service.get_product_images(product_id)

        return ImageListResponse(
            success=True,
            product_id=result['product_id'],
            images=result['images'],
            total_count=result['total_count']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching images for product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch images: {str(e)}"
        )


@router.delete(
    "/products/{product_id}/images",
    response_model=ImageDeleteResponse,
    summary="Delete Product Images",
    description="""
    Delete specific images or all images for a product.

    **Example - Delete specific images:**
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/product-media/products/GP123/images?image_keys=image_2&image_keys=image_3" \\
         -H "Authorization: Bearer YOUR_TOKEN"
    ```

    **Example - Delete all images:**
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/product-media/products/GP123/images" \\
         -H "Authorization: Bearer YOUR_TOKEN"
    ```

    **Authentication Required:** Yes (store owner only)
    """
)
async def delete_product_images(
    product_id: str,
    image_keys: Optional[List[str]] = Query(
        None,
        description="Specific image keys to delete (e.g., 'image_2', 'image_3'). "
                    "If not provided, deletes all images."
    ),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Delete product images from S3

    If image_keys is not provided, deletes ALL images for the product.
    If image_keys is provided, deletes only those specific images.
    """
    try:
        # Validate product_id format to prevent path traversal
        validate_product_id(product_id)

        # Validate image_keys if provided
        if image_keys:
            for key in image_keys:
                if not re.match(r'^(original|thumbnail|medium|large|image_\d+)$', key):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid image key: {key}"
                    )

        logger.info(
            f"User {current_user.get('user_id', 'unknown')} deleting images for product {product_id}, "
            f"keys: {image_keys if image_keys else 'ALL'}"
        )

        result = await product_media_service.delete_product_images(
            product_id=product_id,
            image_keys=image_keys
        )

        # TODO: Update DynamoDB to remove deleted image URLs

        return ImageDeleteResponse(
            success=True,
            message=f"Successfully deleted {result['deleted_count']} images",
            deleted_count=result['deleted_count'],
            failed_count=result['failed_count'],
            deleted_keys=result['deleted_keys']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting images for product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete images: {str(e)}"
        )


@router.post(
    "/products/{product_id}/reorder-images",
    summary="Reorder Product Images",
    description="Reorder product images by updating their keys in S3"
)
async def reorder_product_images(
    product_id: str,
    new_order: List[str] = Form(
        ...,
        description="New order of image keys (e.g., ['image_3', 'image_2', 'image_5'])"
    )
):
    """
    Reorder product images

    This endpoint allows you to change the order of product images.
    The first image in the list becomes image_2, second becomes image_3, etc.
    Primary image (original, thumbnail, medium, large) is not affected.
    """
    try:
        logger.info(f"Reordering images for product {product_id}: {new_order}")

        # TODO: Implement reordering logic
        # This would involve:
        # 1. Copy objects in S3 to new keys
        # 2. Delete old keys
        # 3. Update DynamoDB with new order

        return {
            "success": True,
            "message": "Image reordering not yet implemented",
            "product_id": product_id,
            "new_order": new_order
        }

    except Exception as e:
        logger.error(f"Error reordering images for product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reorder images: {str(e)}"
        )


@router.get(
    "/health",
    summary="Product Media Service Health Check",
    description="Check if the product media service is healthy"
)
async def health_check():
    """Health check endpoint"""
    try:
        # Test S3 connection
        product_media_service.s3_client.list_buckets()

        return {
            "status": "healthy",
            "service": "product-media-service",
            "s3_bucket": product_media_service.bucket,
            "max_images_per_product": 10,
            "max_image_size_mb": 10,
            "supported_formats": ["JPEG", "PNG", "WEBP", "GIF"]
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )
