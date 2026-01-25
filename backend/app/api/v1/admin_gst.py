"""
Admin GST Management API Endpoints
CRUD operations for GST categories and HSN mappings

Author: DevPrakash
"""

import logging
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from app.api.v1.admin_auth import get_current_admin_user
from app.repositories.gst_repository import gst_repository
from app.services.dynamic_gst_service import dynamic_gst_service
from app.core.gst_config import GST_CATEGORIES, HSN_TO_CATEGORY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/gst", tags=["Admin - GST Management"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateCategoryRequest(BaseModel):
    """Request model for creating a GST category"""
    category_code: str = Field(..., min_length=2, max_length=50, description="Unique category code")
    category_name: str = Field(..., min_length=2, max_length=100, description="Category display name")
    gst_rate: Decimal = Field(..., ge=0, le=28, description="GST rate (0, 5, 12, 18, 28)")
    hsn_prefix: str = Field(default="", description="HSN code prefix")
    cess_rate: Decimal = Field(default=Decimal("0"), ge=0, description="Additional cess rate")
    description: str = Field(default="", max_length=500, description="Category description")
    keywords: List[str] = Field(default=[], description="Keywords for product name matching")
    effective_from: Optional[str] = Field(None, description="Date when rate becomes effective (YYYY-MM-DD)")


class UpdateCategoryRequest(BaseModel):
    """Request model for updating a GST category"""
    category_name: Optional[str] = Field(None, min_length=2, max_length=100)
    gst_rate: Optional[Decimal] = Field(None, ge=0, le=28)
    hsn_prefix: Optional[str] = None
    cess_rate: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=500)
    keywords: Optional[List[str]] = None
    effective_from: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    """Response model for GST category"""
    category_code: str
    category_name: str
    gst_rate: Decimal
    hsn_prefix: str
    cess_rate: Decimal
    description: str
    keywords: List[str]
    is_active: bool
    effective_from: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class CreateHSNRequest(BaseModel):
    """Request model for creating an HSN mapping"""
    hsn_code: str = Field(..., pattern=r"^\d{4,8}$", description="HSN code (4, 6, or 8 digits)")
    category_code: str = Field(..., description="GST category code to map to")
    description: str = Field(default="", max_length=500, description="HSN code description")


class UpdateHSNRequest(BaseModel):
    """Request model for updating an HSN mapping"""
    category_code: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class HSNResponse(BaseModel):
    """Response model for HSN mapping"""
    hsn_code: str
    category_code: str
    description: str
    is_active: bool
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class CacheStatsResponse(BaseModel):
    """Response model for cache statistics"""
    categories_count: int
    hsn_mappings_count: int
    categories_stale: bool
    hsn_stale: bool
    cache_hits: int
    cache_misses: int
    hit_rate_percent: float
    ttl_seconds: float
    static_fallback_used: bool


class SeedResponse(BaseModel):
    """Response model for seeding operation"""
    categories_seeded: int
    hsn_mappings_seeded: int
    message: str


# ============================================================================
# CATEGORY ENDPOINTS
# ============================================================================

@router.get("/categories", response_model=List[CategoryResponse])
async def list_gst_categories(
    include_inactive: bool = False,
    admin: dict = Depends(get_current_admin_user)
):
    """
    List all GST categories.

    Args:
        include_inactive: Include soft-deleted categories
        admin: Current admin user (from auth)

    Returns:
        List of GST categories
    """
    try:
        categories = await gst_repository.get_all_categories(active_only=not include_inactive)

        return [
            CategoryResponse(
                category_code=cat["category_code"],
                category_name=cat.get("category_name", cat["category_code"]),
                gst_rate=Decimal(str(cat.get("gst_rate", 18))),
                hsn_prefix=cat.get("hsn_prefix", ""),
                cess_rate=Decimal(str(cat.get("cess_rate", 0))),
                description=cat.get("description", ""),
                keywords=cat.get("keywords", []),
                is_active=cat.get("is_active", True),
                effective_from=cat.get("effective_from"),
                updated_at=cat.get("updated_at"),
                updated_by=cat.get("updated_by")
            )
            for cat in categories
        ]

    except Exception as e:
        logger.error(f"Error listing GST categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list GST categories"
        )


@router.get("/categories/{category_code}", response_model=CategoryResponse)
async def get_gst_category(
    category_code: str,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Get a single GST category by code.

    Args:
        category_code: Category code to lookup
        admin: Current admin user

    Returns:
        GST category details
    """
    try:
        cat = await gst_repository.get_category(category_code)

        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category '{category_code}' not found"
            )

        return CategoryResponse(
            category_code=cat["category_code"],
            category_name=cat.get("category_name", cat["category_code"]),
            gst_rate=Decimal(str(cat.get("gst_rate", 18))),
            hsn_prefix=cat.get("hsn_prefix", ""),
            cess_rate=Decimal(str(cat.get("cess_rate", 0))),
            description=cat.get("description", ""),
            keywords=cat.get("keywords", []),
            is_active=cat.get("is_active", True),
            effective_from=cat.get("effective_from"),
            updated_at=cat.get("updated_at"),
            updated_by=cat.get("updated_by")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GST category {category_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get GST category"
        )


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_gst_category(
    request: CreateCategoryRequest,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Create a new GST category.

    Args:
        request: Category creation request
        admin: Current admin user

    Returns:
        Created GST category
    """
    try:
        # Check if category already exists
        existing = await gst_repository.get_category(request.category_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{request.category_code}' already exists"
            )

        # Validate GST rate
        valid_rates = [0, 5, 12, 18, 28]
        if int(request.gst_rate) not in valid_rates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GST rate. Must be one of: {valid_rates}"
            )

        # Create category
        cat = await gst_repository.create_category(
            category_code=request.category_code,
            category_name=request.category_name,
            gst_rate=request.gst_rate,
            hsn_prefix=request.hsn_prefix,
            admin_id=admin["id"],
            cess_rate=request.cess_rate,
            description=request.description,
            keywords=request.keywords,
            effective_from=request.effective_from
        )

        # Invalidate cache
        await dynamic_gst_service.cache.invalidate_categories()

        logger.info(f"Admin {admin['email']} created GST category {request.category_code}")

        return CategoryResponse(
            category_code=cat["category_code"],
            category_name=cat["category_name"],
            gst_rate=Decimal(str(cat["gst_rate"])),
            hsn_prefix=cat["hsn_prefix"],
            cess_rate=Decimal(str(cat["cess_rate"])),
            description=cat["description"],
            keywords=cat["keywords"],
            is_active=cat["is_active"],
            effective_from=cat.get("effective_from"),
            updated_at=cat["updated_at"],
            updated_by=cat["updated_by"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating GST category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create GST category"
        )


@router.put("/categories/{category_code}", response_model=CategoryResponse)
async def update_gst_category(
    category_code: str,
    request: UpdateCategoryRequest,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Update a GST category.

    Args:
        category_code: Category code to update
        request: Update request
        admin: Current admin user

    Returns:
        Updated GST category
    """
    try:
        # Check if category exists
        existing = await gst_repository.get_category(category_code)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category '{category_code}' not found"
            )

        # Validate GST rate if provided
        if request.gst_rate is not None:
            valid_rates = [0, 5, 12, 18, 28]
            if int(request.gst_rate) not in valid_rates:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid GST rate. Must be one of: {valid_rates}"
                )

        # Build updates dict
        updates = {k: v for k, v in request.model_dump().items() if v is not None}

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )

        # Update category
        cat = await gst_repository.update_category(category_code, updates, admin["id"])

        if not cat:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update category"
            )

        # Invalidate cache
        await dynamic_gst_service.cache.invalidate_categories()

        logger.info(f"Admin {admin['email']} updated GST category {category_code}")

        return CategoryResponse(
            category_code=cat["category_code"],
            category_name=cat.get("category_name", cat["category_code"]),
            gst_rate=Decimal(str(cat.get("gst_rate", 18))),
            hsn_prefix=cat.get("hsn_prefix", ""),
            cess_rate=Decimal(str(cat.get("cess_rate", 0))),
            description=cat.get("description", ""),
            keywords=cat.get("keywords", []),
            is_active=cat.get("is_active", True),
            effective_from=cat.get("effective_from"),
            updated_at=cat.get("updated_at"),
            updated_by=cat.get("updated_by")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating GST category {category_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update GST category"
        )


@router.delete("/categories/{category_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gst_category(
    category_code: str,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Soft delete a GST category.

    Args:
        category_code: Category code to delete
        admin: Current admin user
    """
    try:
        # Check if category exists
        existing = await gst_repository.get_category(category_code)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category '{category_code}' not found"
            )

        # Soft delete
        success = await gst_repository.delete_category(category_code, admin["id"])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete category"
            )

        # Invalidate cache
        await dynamic_gst_service.cache.invalidate_categories()

        logger.info(f"Admin {admin['email']} deleted GST category {category_code}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting GST category {category_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete GST category"
        )


# ============================================================================
# HSN ENDPOINTS
# ============================================================================

@router.get("/hsn", response_model=List[HSNResponse])
async def list_hsn_mappings(
    category_code: Optional[str] = None,
    admin: dict = Depends(get_current_admin_user)
):
    """
    List all HSN mappings, optionally filtered by category.

    Args:
        category_code: Optional category code to filter by
        admin: Current admin user

    Returns:
        List of HSN mappings
    """
    try:
        mappings = await gst_repository.get_all_hsn_mappings(category_code)

        return [
            HSNResponse(
                hsn_code=m["hsn_code"],
                category_code=m["category_code"],
                description=m.get("description", ""),
                is_active=m.get("is_active", True),
                updated_at=m.get("updated_at"),
                updated_by=m.get("updated_by")
            )
            for m in mappings
        ]

    except Exception as e:
        logger.error(f"Error listing HSN mappings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list HSN mappings"
        )


@router.get("/hsn/{hsn_code}", response_model=HSNResponse)
async def get_hsn_mapping(
    hsn_code: str,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Get an HSN mapping by code.

    Args:
        hsn_code: HSN code to lookup
        admin: Current admin user

    Returns:
        HSN mapping details
    """
    try:
        mapping = await gst_repository.get_hsn_mapping(hsn_code)

        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"HSN mapping '{hsn_code}' not found"
            )

        return HSNResponse(
            hsn_code=mapping["hsn_code"],
            category_code=mapping["category_code"],
            description=mapping.get("description", ""),
            is_active=mapping.get("is_active", True),
            updated_at=mapping.get("updated_at"),
            updated_by=mapping.get("updated_by")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HSN mapping {hsn_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get HSN mapping"
        )


@router.post("/hsn", response_model=HSNResponse, status_code=status.HTTP_201_CREATED)
async def create_hsn_mapping(
    request: CreateHSNRequest,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Create a new HSN mapping.

    Args:
        request: HSN mapping creation request
        admin: Current admin user

    Returns:
        Created HSN mapping
    """
    try:
        # Check if HSN already exists
        existing = await gst_repository.get_hsn_mapping(request.hsn_code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"HSN mapping '{request.hsn_code}' already exists"
            )

        # Verify category exists
        category = await gst_repository.get_category(request.category_code)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{request.category_code}' does not exist"
            )

        # Create mapping
        mapping = await gst_repository.create_hsn_mapping(
            hsn_code=request.hsn_code,
            category_code=request.category_code,
            admin_id=admin["id"],
            description=request.description
        )

        # Invalidate cache
        await dynamic_gst_service.cache.invalidate_hsn()

        logger.info(f"Admin {admin['email']} created HSN mapping {request.hsn_code}")

        return HSNResponse(
            hsn_code=mapping["hsn_code"],
            category_code=mapping["category_code"],
            description=mapping["description"],
            is_active=mapping["is_active"],
            updated_at=mapping["updated_at"],
            updated_by=mapping["updated_by"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating HSN mapping: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create HSN mapping"
        )


@router.put("/hsn/{hsn_code}", response_model=HSNResponse)
async def update_hsn_mapping(
    hsn_code: str,
    request: UpdateHSNRequest,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Update an HSN mapping.

    Args:
        hsn_code: HSN code to update
        request: Update request
        admin: Current admin user

    Returns:
        Updated HSN mapping
    """
    try:
        # Check if HSN exists
        existing = await gst_repository.get_hsn_mapping(hsn_code)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"HSN mapping '{hsn_code}' not found"
            )

        # Verify new category exists if provided
        if request.category_code:
            category = await gst_repository.get_category(request.category_code)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Category '{request.category_code}' does not exist"
                )

        # Build updates dict
        updates = {k: v for k, v in request.model_dump().items() if v is not None}

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid fields to update"
            )

        # Update mapping
        mapping = await gst_repository.update_hsn_mapping(hsn_code, updates, admin["id"])

        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update HSN mapping"
            )

        # Invalidate cache
        await dynamic_gst_service.cache.invalidate_hsn()

        logger.info(f"Admin {admin['email']} updated HSN mapping {hsn_code}")

        return HSNResponse(
            hsn_code=mapping["hsn_code"],
            category_code=mapping["category_code"],
            description=mapping.get("description", ""),
            is_active=mapping.get("is_active", True),
            updated_at=mapping.get("updated_at"),
            updated_by=mapping.get("updated_by")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating HSN mapping {hsn_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update HSN mapping"
        )


@router.delete("/hsn/{hsn_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hsn_mapping(
    hsn_code: str,
    admin: dict = Depends(get_current_admin_user)
):
    """
    Soft delete an HSN mapping.

    Args:
        hsn_code: HSN code to delete
        admin: Current admin user
    """
    try:
        # Check if HSN exists
        existing = await gst_repository.get_hsn_mapping(hsn_code)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"HSN mapping '{hsn_code}' not found"
            )

        # Soft delete
        success = await gst_repository.delete_hsn_mapping(hsn_code, admin["id"])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete HSN mapping"
            )

        # Invalidate cache
        await dynamic_gst_service.cache.invalidate_hsn()

        logger.info(f"Admin {admin['email']} deleted HSN mapping {hsn_code}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting HSN mapping {hsn_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete HSN mapping"
        )


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================

@router.post("/cache/refresh", response_model=dict)
async def refresh_gst_cache(
    admin: dict = Depends(get_current_admin_user)
):
    """
    Force refresh of GST cache.

    Args:
        admin: Current admin user

    Returns:
        Refresh results
    """
    try:
        result = await dynamic_gst_service.refresh_cache()
        logger.info(f"Admin {admin['email']} refreshed GST cache")
        return {
            "success": True,
            "message": "Cache refreshed successfully",
            **result
        }

    except Exception as e:
        logger.error(f"Error refreshing GST cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh cache"
        )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    admin: dict = Depends(get_current_admin_user)
):
    """
    Get GST cache statistics.

    Args:
        admin: Current admin user

    Returns:
        Cache statistics
    """
    try:
        stats = await dynamic_gst_service.get_cache_stats()
        return CacheStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cache stats"
        )


# ============================================================================
# SEEDING
# ============================================================================

@router.post("/seed", response_model=SeedResponse)
async def seed_gst_tables(
    admin: dict = Depends(get_current_admin_user)
):
    """
    Seed GST tables from static gst_config.py data.
    This is a one-time operation to migrate from static config to DynamoDB.

    Args:
        admin: Current admin user

    Returns:
        Seeding results
    """
    try:
        # Prepare categories from static config
        categories = []
        for key, cat in GST_CATEGORIES.items():
            categories.append({
                "category_code": key,
                "category_name": cat.name,
                "gst_rate": cat.gst_rate.value,
                "hsn_prefix": cat.hsn_prefix,
                "cess_rate": cat.cess_rate,
                "description": cat.description,
                "keywords": []
            })

        # Bulk upsert categories
        cat_count = await gst_repository.bulk_upsert_categories(categories, admin["id"])

        # Prepare HSN mappings from static config
        mappings = []
        for hsn_code, category_code in HSN_TO_CATEGORY.items():
            mappings.append({
                "hsn_code": hsn_code,
                "category_code": category_code,
                "description": ""
            })

        # Bulk upsert HSN mappings
        hsn_count = await gst_repository.bulk_upsert_hsn_mappings(mappings, admin["id"])

        # Refresh cache
        await dynamic_gst_service.refresh_cache()

        logger.info(f"Admin {admin['email']} seeded GST tables: {cat_count} categories, {hsn_count} HSN mappings")

        return SeedResponse(
            categories_seeded=cat_count,
            hsn_mappings_seeded=hsn_count,
            message="GST tables seeded successfully from static configuration"
        )

    except Exception as e:
        logger.error(f"Error seeding GST tables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed GST tables: {str(e)}"
        )
