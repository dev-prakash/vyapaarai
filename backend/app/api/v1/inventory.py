from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from decimal import Decimal
import json
import boto3
import logging

from app.services.inventory_service import inventory_service
from app.core.security import get_current_store_owner

router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)

# DynamoDB configuration for global catalog
dynamodb_client = boto3.client('dynamodb', region_name='ap-south-1')
GLOBAL_PRODUCTS_TABLE = 'vyaparai-global-products-prod'


def parse_dynamodb_item(item: dict) -> dict:
    """Convert DynamoDB item to regular Python dict"""
    product = {}
    for key, value in item.items():
        if 'S' in value:
            product[key] = value['S']
        elif 'N' in value:
            product[key] = int(value['N']) if '.' not in value['N'] else float(value['N'])
        elif 'M' in value:
            product[key] = parse_dynamodb_item(value['M'])
        elif 'L' in value:
            product[key] = [parse_dynamodb_value(v) for v in value['L']]
        elif 'BOOL' in value:
            product[key] = value['BOOL']
        elif 'NULL' in value:
            product[key] = None
    return product


def parse_dynamodb_value(value: dict):
    """Parse a single DynamoDB value"""
    if 'S' in value:
        return value['S']
    elif 'N' in value:
        return int(value['N']) if '.' not in value['N'] else float(value['N'])
    elif 'M' in value:
        return parse_dynamodb_item(value['M'])
    elif 'L' in value:
        return [parse_dynamodb_value(v) for v in value['L']]
    elif 'BOOL' in value:
        return value['BOOL']
    elif 'NULL' in value:
        return None
    return None


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    price: float
    mrp: Optional[float] = None
    cost_price: Optional[float] = None
    current_stock: int = 0
    min_stock_level: int = 10
    max_stock_level: int = 1000
    unit: str = "piece"
    brand: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    supplier_email: Optional[str] = None
    is_featured: bool = False


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    price: Optional[float] = None
    mrp: Optional[float] = None
    cost_price: Optional[float] = None
    min_stock_level: Optional[int] = None
    max_stock_level: Optional[int] = None
    unit: Optional[str] = None
    brand: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_contact: Optional[str] = None
    supplier_email: Optional[str] = None
    is_featured: Optional[bool] = None
    status: Optional[str] = None


class StockUpdate(BaseModel):
    quantity_change: int  # Positive for add, negative for subtract
    reason: Optional[str] = None


class BulkStockUpdate(BaseModel):
    updates: List[Dict[str, Any]]


class CustomProductCreate(BaseModel):
    """Schema for creating a store-specific custom product"""
    product_name: str
    brand: Optional[str] = None
    category: str = "Uncategorized"
    subcategory: Optional[str] = None
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None  # Auto-generated if not provided

    # Pricing
    selling_price: float
    cost_price: Optional[float] = 0
    mrp: Optional[float] = 0
    tax_rate: Optional[float] = 5.0
    discount_percentage: Optional[float] = 0

    # Inventory
    current_stock: int = 0
    min_stock_level: int = 10
    max_stock_level: int = 1000
    unit: str = "piece"

    # Flags
    is_returnable: bool = True
    is_perishable: bool = False

    # Image
    image: Optional[str] = None
    image_urls: Optional[Dict[str, str]] = None


class CustomProductUpdate(BaseModel):
    """Schema for updating a store-specific custom product"""
    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from frontend

    product_name: Optional[str] = None
    brand: Optional[str] = None
    brand_name: Optional[str] = None
    brand_id: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None

    selling_price: Optional[float] = None
    cost_price: Optional[float] = None
    mrp: Optional[float] = None
    tax_rate: Optional[float] = None
    discount_percentage: Optional[float] = None

    current_stock: Optional[int] = None
    min_stock_level: Optional[int] = None
    max_stock_level: Optional[int] = None
    reorder_point: Optional[int] = None
    reorder_quantity: Optional[int] = None
    unit: Optional[str] = None
    size: Optional[float] = None
    size_unit: Optional[str] = None
    variant_type: Optional[str] = None
    location: Optional[str] = None

    is_active: Optional[bool] = None
    is_returnable: Optional[bool] = None
    is_perishable: Optional[bool] = None
    status: Optional[str] = None

    image: Optional[str] = None
    image_urls: Optional[Dict[str, str]] = None


@router.get("/products")
async def list_products(
    store_id: str = Query(..., description="Store ID"),
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000)
):
    """List products with filtering and pagination"""

    try:
        result = await inventory_service.get_products(
            store_id=store_id,
            category=category,
            status=status,
            search=search,
            page=page,
            limit=limit
        )

        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get products: {str(e)}")


@router.get("/products/{store_id}/{product_id}")
async def get_product(store_id: str, product_id: str):
    """Get product by ID for a specific store"""

    try:
        product = await inventory_service.get_product(store_id, product_id)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        return {
            "success": True,
            "product": product
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get product: {str(e)}")


@router.get("/search")
async def search_products(
    store_id: str = Query(..., description="Store ID"),
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=100)
):
    """Search products by name"""

    try:
        products = await inventory_service.search_products(store_id, q, limit)

        return {
            "success": True,
            "products": products,
            "count": len(products)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.put("/products/{store_id}/{product_id}/stock")
async def update_stock(store_id: str, product_id: str, stock_update: StockUpdate):
    """Update product stock levels"""

    try:
        result = await inventory_service.update_stock(
            store_id=store_id,
            product_id=product_id,
            quantity_change=stock_update.quantity_change,
            reason=stock_update.reason
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Stock update failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stock update failed: {str(e)}")


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    updates: CustomProductUpdate,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Update a product in the store's inventory.

    This endpoint handles updates for both custom products and products
    added from the global catalog.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        # Filter out None values from updates
        update_dict = {k: v for k, v in updates.dict().items() if v is not None}

        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")

        # First check if product exists
        existing_product = await inventory_service.get_product(store_id, product_id)
        if not existing_product:
            raise HTTPException(status_code=404, detail=f"Product {product_id} not found in store inventory")

        # Use the update_custom_product method which handles both custom and catalog products
        result = await inventory_service.update_custom_product(
            store_id=store_id,
            product_id=product_id,
            user_id=user_id,
            updates=update_dict
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Failed to update product')
            if 'Not authorized' in error_msg:
                raise HTTPException(status_code=403, detail=error_msg)
            elif 'not found' in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            elif 'Cannot update' in error_msg:
                raise HTTPException(status_code=400, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

        return {
            "success": True,
            "message": "Product updated successfully",
            "product": result.get('product')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update product: {str(e)}")


@router.get("/products/{store_id}/{product_id}/availability")
async def check_availability(store_id: str, product_id: str, quantity: int = Query(..., ge=1)):
    """Check product availability for given quantity"""

    try:
        result = await inventory_service.check_availability(store_id, product_id, quantity)

        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Availability check failed: {str(e)}")


@router.get("/low-stock")
async def get_low_stock_products(
    store_id: str = Query(..., description="Store ID"),
    threshold: Optional[int] = None
):
    """Get products with low stock levels"""

    try:
        products = await inventory_service.get_low_stock_products(store_id, threshold)

        return {
            "success": True,
            "low_stock_products": products,
            "count": len(products)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get low stock products: {str(e)}")


@router.get("/barcode/{barcode}")
async def get_product_by_barcode(barcode: str):
    """Search product by barcode in global catalog"""

    try:
        product = await inventory_service.get_product_by_barcode(barcode)

        if not product:
            raise HTTPException(status_code=404, detail="Product not found with this barcode")

        return {
            "success": True,
            "product": product
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Barcode search failed: {str(e)}")


@router.get("/summary")
async def get_inventory_summary(store_id: str = Query(..., description="Store ID")):
    """Get inventory summary statistics"""

    try:
        summary = await inventory_service.get_inventory_summary(store_id)

        # Map field names to match frontend expectations
        return {
            "success": True,
            "data": {
                "total_products": summary.get("total_products", 0),
                "active_products": summary.get("active_products", 0),
                "total_stock_value": summary.get("total_stock_value", 0),
                "low_stock_count": summary.get("low_stock", 0),
                "out_of_stock_count": summary.get("out_of_stock", 0),
                "store_id": store_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get inventory summary: {str(e)}")


@router.get("/categories")
async def get_product_categories():
    """Get all product categories"""

    try:
        # These are common categories - could be pulled from DynamoDB in future
        categories = [
            {"id": "cat_001", "name": "Grains & Cereals", "description": "Rice, wheat, flour"},
            {"id": "cat_002", "name": "Cooking Essentials", "description": "Oil, sugar, salt, spices"},
            {"id": "cat_003", "name": "Dairy & Eggs", "description": "Milk, curd, butter, eggs"},
            {"id": "cat_004", "name": "Vegetables", "description": "Fresh vegetables"},
            {"id": "cat_005", "name": "Fruits", "description": "Fresh fruits"},
            {"id": "cat_006", "name": "Beverages", "description": "Tea, coffee, juices"},
            {"id": "cat_007", "name": "Snacks & Biscuits", "description": "Chips, biscuits, namkeen"},
            {"id": "cat_008", "name": "Personal Care", "description": "Soap, shampoo, toothpaste"},
            {"id": "cat_009", "name": "Spices & Condiments", "description": "Spices, masalas, condiments"},
            {"id": "cat_010", "name": "Household", "description": "Cleaning supplies, kitchen items"}
        ]

        return {
            "success": True,
            "categories": categories,
            "count": len(categories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


@router.get("/units")
async def get_product_units():
    """Get available product units"""

    try:
        units = [
            {"value": "kg", "label": "Kilogram"},
            {"value": "g", "label": "Gram"},
            {"value": "liter", "label": "Liter"},
            {"value": "ml", "label": "Milliliter"},
            {"value": "piece", "label": "Piece"},
            {"value": "pieces", "label": "Pieces"},
            {"value": "packet", "label": "Packet"},
            {"value": "pack", "label": "Pack"},
            {"value": "box", "label": "Box"},
            {"value": "dozen", "label": "Dozen"},
            {"value": "bottle", "label": "Bottle"},
            {"value": "can", "label": "Can"}
        ]

        return {
            "success": True,
            "units": units,
            "count": len(units)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get units: {str(e)}")


# ==================== CUSTOM PRODUCT ENDPOINTS ====================

@router.post("/products/custom", status_code=201)
async def create_custom_product(
    product_data: CustomProductCreate,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Create a store-specific custom product.

    Custom products are:
    - Only visible to the store that created them
    - Can be promoted to global catalog by admin approval
    - Have a unique product ID with 'CUST_' prefix

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        result = await inventory_service.create_custom_product(
            store_id=store_id,
            user_id=user_id,
            product_data=product_data.dict()
        )

        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to create product'))

        logger.info(f"Custom product created: {result.get('product_id')} for store {store_id}")

        return {
            "success": True,
            "message": "Custom product created successfully",
            "product_id": result.get('product_id'),
            "sku": result.get('sku'),
            "product": result.get('product')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create product: {str(e)}")


@router.put("/products/custom/{product_id}")
async def update_custom_product(
    product_id: str,
    updates: CustomProductUpdate,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Update a store-specific custom product.

    Only the store that created the product can update it.
    Products pending promotion review cannot be updated.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        # Filter out None values from updates
        update_dict = {k: v for k, v in updates.dict().items() if v is not None}

        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")

        result = await inventory_service.update_custom_product(
            store_id=store_id,
            product_id=product_id,
            user_id=user_id,
            updates=update_dict
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Failed to update product')
            if 'Not authorized' in error_msg:
                raise HTTPException(status_code=403, detail=error_msg)
            elif 'not found' in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

        return {
            "success": True,
            "message": "Product updated successfully",
            "product": result.get('product')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating custom product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update product: {str(e)}")


@router.delete("/products/custom/{product_id}")
async def delete_custom_product(
    product_id: str,
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Delete a store-specific custom product.

    By default, performs soft delete (deactivates the product).
    Use hard_delete=true to permanently remove the product.

    Only the store that created the product can delete it.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        result = await inventory_service.delete_custom_product(
            store_id=store_id,
            product_id=product_id,
            user_id=user_id,
            hard_delete=hard_delete
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Failed to delete product')
            if 'Not authorized' in error_msg:
                raise HTTPException(status_code=403, detail=error_msg)
            elif 'not found' in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

        return {
            "success": True,
            "message": result.get('message'),
            "hard_delete": result.get('hard_delete', False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting custom product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete product: {str(e)}")


@router.get("/products/custom")
async def list_custom_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    List all custom products for the authenticated store.

    Returns only custom products created by this store.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        # Get all products for the store
        result = await inventory_service.get_products(
            store_id=store_id,
            page=page,
            limit=limit
        )

        # Filter to only custom products
        all_products = result.get('products', [])
        custom_products = [
            p for p in all_products
            if p.get('product_source') == 'store_custom'
        ]

        # Recalculate pagination for filtered results
        total_custom = len(custom_products)

        return {
            "success": True,
            "products": custom_products,
            "total": total_custom,
            "page": page,
            "pages": (total_custom + limit - 1) // limit if total_custom > 0 else 1,
            "has_next": page * limit < total_custom,
            "has_prev": page > 1
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing custom products: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list custom products: {str(e)}")


# ==================== PROMOTION REQUESTS ====================

@router.post("/products/{product_id}/request-promotion")
async def request_product_promotion(
    product_id: str,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Request promotion of a custom product to the global catalog.

    The product must:
    - Be a custom product created by this store
    - Meet minimum quality criteria (60% score)
    - Not already be pending promotion

    Admin will review and approve/reject the request.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        result = await inventory_service.request_promotion(
            store_id=store_id,
            product_id=product_id,
            user_id=user_id
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Failed to request promotion')
            status_code = 400

            if 'Not authorized' in error_msg:
                status_code = 403
            elif 'not found' in error_msg.lower():
                status_code = 404
            elif 'quality criteria' in error_msg.lower():
                # Return quality check details for failed criteria
                return {
                    "success": False,
                    "message": error_msg,
                    "quality_score": result.get('quality_score'),
                    "missing_fields": result.get('missing_fields'),
                    "checks": result.get('checks')
                }

            raise HTTPException(status_code=status_code, detail=error_msg)

        return {
            "success": True,
            "message": result.get('message'),
            "product_id": result.get('product_id'),
            "quality_score": result.get('quality_score'),
            "checks": result.get('checks'),
            "promotion_status": result.get('promotion_status')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting promotion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to request promotion: {str(e)}")


@router.post("/products/{product_id}/cancel-promotion")
async def cancel_product_promotion(
    product_id: str,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Cancel a pending promotion request.

    Only products with 'pending_review' status can be cancelled.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        result = await inventory_service.cancel_promotion_request(
            store_id=store_id,
            product_id=product_id,
            user_id=user_id
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Failed to cancel promotion')
            if 'Not authorized' in error_msg:
                raise HTTPException(status_code=403, detail=error_msg)
            elif 'not found' in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

        return {
            "success": True,
            "message": result.get('message'),
            "product_id": result.get('product_id'),
            "promotion_status": result.get('promotion_status')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling promotion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel promotion: {str(e)}")


@router.get("/products/promotion-requests")
async def list_promotion_requests(
    current_user: dict = Depends(get_current_store_owner)
):
    """
    List all promotion requests for the authenticated store.

    Returns products with any promotion status other than 'none',
    sorted by request date (newest first).

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        products = await inventory_service.get_promotion_requests(store_id)

        return {
            "success": True,
            "promotion_requests": products,
            "count": len(products)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing promotion requests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list promotion requests: {str(e)}")


# ==================== GLOBAL CATALOG ====================

@router.get("/global-catalog")
async def browse_global_catalog(
    limit: int = Query(100, ge=1, le=1000, description="Number of products to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in product name"),
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Browse the global product catalog for store owners.
    This endpoint allows authenticated store owners to view products from the global catalog
    to add to their store inventory.
    Requires store owner authentication.
    """
    try:
        scan_kwargs = {
            'TableName': GLOBAL_PRODUCTS_TABLE,
            'Limit': min(limit, 1000)  # Cap at 1000 for performance
        }

        # Execute scan
        response = dynamodb_client.scan(**scan_kwargs)

        # Parse products
        products = []
        for item in response.get('Items', []):
            product = parse_dynamodb_item(item)

            # Apply filters (post-scan filtering)
            if category and product.get('category', '').lower() != category.lower():
                continue
            if search and search.lower() not in product.get('name', '').lower():
                continue

            # Format product for frontend
            formatted_product = {
                'product_id': product.get('product_id'),
                'name': product.get('name'),
                'brand': product.get('brand'),
                'category': product.get('category'),
                'barcode': product.get('barcode'),
                'description': product.get('description'),
                'quality_score': product.get('quality_score'),
                'attributes': product.get('attributes', {}),
            }

            # Get MRP from attributes or top-level
            mrp = product.get('mrp')
            if not mrp and product.get('attributes'):
                mrp = product.get('attributes', {}).get('mrp')
            formatted_product['mrp'] = mrp

            # Get image from canonical_image_urls or image field
            image_urls = product.get('canonical_image_urls', {})
            if isinstance(image_urls, dict):
                formatted_product['image'] = image_urls.get('medium') or image_urls.get('original') or image_urls.get('thumbnail')
            else:
                formatted_product['image'] = product.get('image')

            products.append(formatted_product)

        logger.info(f"Global catalog browse: returning {len(products)} products")

        return {
            'success': True,
            'products': products,
            'count': len(products),
            'has_more': 'LastEvaluatedKey' in response
        }

    except Exception as e:
        logger.error(f"Error browsing global catalog: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load product catalog: {str(e)}")


class AddFromCatalogRequest(BaseModel):
    """Schema for adding a product from global catalog to store inventory"""
    global_product_id: str
    current_stock: int = 0
    selling_price: float
    cost_price: float = 0
    min_stock_level: int = 10
    max_stock_level: int = 100
    reorder_point: int = 10
    location: str = ""
    notes: str = ""
    is_active: bool = True


@router.post("/products/from-catalog", status_code=201)
async def add_product_from_catalog(
    request_data: AddFromCatalogRequest,
    current_user: dict = Depends(get_current_store_owner)
):
    """
    Add a product from the global catalog to the store's inventory.

    This creates a store inventory record linked to a global catalog product.
    Store owners can set their own pricing and stock levels.

    Requires store owner authentication.
    """
    try:
        store_id = current_user.get('store_id')
        user_id = current_user.get('user_id')

        if not store_id:
            raise HTTPException(status_code=400, detail="Store ID not found in token")

        # Validate selling price
        if request_data.selling_price <= 0:
            raise HTTPException(status_code=400, detail="Selling price must be greater than 0")

        # Call inventory service to add from catalog
        result = await inventory_service.add_from_global_catalog(
            store_id=store_id,
            user_id=user_id,
            global_product_id=request_data.global_product_id,
            inventory_data={
                'current_stock': request_data.current_stock,
                'selling_price': request_data.selling_price,
                'cost_price': request_data.cost_price,
                'min_stock_level': request_data.min_stock_level,
                'max_stock_level': request_data.max_stock_level,
                'reorder_point': request_data.reorder_point,
                'location': request_data.location,
                'notes': request_data.notes,
                'is_active': request_data.is_active
            }
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Failed to add product')
            if 'already exists' in error_msg.lower():
                raise HTTPException(status_code=409, detail=error_msg)
            elif 'not found' in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            else:
                raise HTTPException(status_code=400, detail=error_msg)

        logger.info(f"Product added from catalog: {request_data.global_product_id} to store {store_id}")

        return {
            "success": True,
            "message": "Product added to inventory successfully",
            "product_id": result.get('product_id'),
            "product": result.get('product')
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding product from catalog: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add product to inventory: {str(e)}")
