"""
GST API Endpoints for VyapaarAI
Provides REST APIs for GST calculation and lookup

Author: DevPrakash
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query

from app.models.gst import (
    CalculateItemGSTRequest,
    CalculateOrderGSTRequest,
    GSTCategoryResponse,
    ItemGSTBreakdown,
    OrderGSTSummary,
    ProductGSTInfo,
    UpdateProductGSTRequest,
)
from app.services.gst_service import gst_service

router = APIRouter(prefix="/gst", tags=["GST"])


# ============================================================================
# GST CATEGORY ENDPOINTS
# ============================================================================

@router.get(
    "/categories",
    response_model=List[GSTCategoryResponse],
    summary="Get all GST categories",
    description="Returns all configured GST categories with their rates and HSN prefixes"
)
async def get_gst_categories():
    """
    Get all GST categories.

    Returns list of GST categories sorted by rate, then name.
    Includes:
    - Category code and name
    - HSN prefix
    - GST rate (0%, 5%, 12%, 18%, 28%)
    - Cess rate (if applicable)
    - Description
    """
    return gst_service.get_all_gst_categories()


@router.get(
    "/categories/{rate}",
    response_model=List[GSTCategoryResponse],
    summary="Get GST categories by rate",
    description="Returns GST categories filtered by tax rate"
)
async def get_gst_categories_by_rate(
    rate: int = Path(
        ...,
        description="GST rate (0, 5, 12, 18, or 28)"
    )
):
    """Get GST categories filtered by rate."""
    valid_rates = [0, 5, 12, 18, 28]
    if rate not in valid_rates:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid rate. Must be one of {valid_rates}"
        )

    all_categories = gst_service.get_all_gst_categories()
    return [c for c in all_categories if c.gst_rate == Decimal(str(rate))]


# ============================================================================
# HSN CODE ENDPOINTS
# ============================================================================

@router.get(
    "/hsn/{hsn_code}",
    response_model=GSTCategoryResponse,
    summary="Lookup HSN code",
    description="Get GST information for an HSN code"
)
async def get_hsn_info(hsn_code: str):
    """
    Get GST information for an HSN code.

    Args:
        hsn_code: 4, 6, or 8 digit HSN code

    Returns:
        GST category information including rate

    Raises:
        404: HSN code not found
    """
    result = gst_service.get_hsn_info(hsn_code)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"HSN code {hsn_code} not found in database"
        )
    return result


@router.get(
    "/suggest",
    response_model=Optional[GSTCategoryResponse],
    summary="Suggest GST category",
    description="Suggest GST category based on product name"
)
async def suggest_gst_category(
    product_name: str = Query(
        ...,
        min_length=2,
        description="Product name to analyze"
    )
):
    """
    Suggest GST category based on product name keywords.

    This is a basic suggestion - may not be accurate for all products.
    Always verify with official HSN code lookup.
    """
    result = gst_service.suggest_gst_category(product_name)
    if not result:
        return None
    return result


# ============================================================================
# PRODUCT GST ENDPOINTS
# ============================================================================

@router.get(
    "/products/{product_id}/gst",
    response_model=ProductGSTInfo,
    summary="Get product GST info",
    description="Get GST rate and details for a specific product"
)
async def get_product_gst(
    product_id: str,
    store_id: str = Query(..., description="Store ID")
):
    """
    Get GST rate for a specific product.

    Checks in order:
    1. Store-level GST override
    2. Product-level GST rate
    3. HSN code lookup
    4. Category suggestion from name
    5. Default rate (18%)
    """
    return await gst_service.get_gst_rate_for_product(product_id, store_id)


# ============================================================================
# GST CALCULATION ENDPOINTS
# ============================================================================

@router.post(
    "/calculate/item",
    response_model=ItemGSTBreakdown,
    summary="Calculate item GST",
    description="Calculate GST for a single item with full breakdown"
)
async def calculate_item_gst(request: CalculateItemGSTRequest):
    """
    Calculate GST for a single item.

    Returns complete breakdown including:
    - CGST/SGST (intra-state) or IGST (inter-state)
    - Cess if applicable
    - Total tax and total amount
    """
    # Get product price if not provided
    if request.unit_price is None:
        from app.services.inventory_service import inventory_service
        product = await inventory_service.get_product(
            request.store_id,
            request.product_id
        )
        if not product:
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )
        unit_price = Decimal(str(product.get('selling_price', 0)))
        product_name = product.get('product_name', '')
    else:
        unit_price = request.unit_price
        product_name = ""

    breakdown = await gst_service.calculate_item_gst(
        product_id=request.product_id,
        store_id=request.store_id,
        quantity=request.quantity,
        unit_price=unit_price,
        product_name=product_name,
        is_inter_state=request.is_inter_state
    )

    # Get product name if not set
    if not breakdown.product_name:
        from app.services.inventory_service import inventory_service
        product = await inventory_service.get_product(
            request.store_id,
            request.product_id
        )
        if product:
            breakdown.product_name = product.get('product_name', '')

    return breakdown


@router.post(
    "/calculate/order",
    response_model=OrderGSTSummary,
    summary="Calculate order GST",
    description="Calculate GST for an entire order with rate-wise summary"
)
async def calculate_order_gst(request: CalculateOrderGSTRequest):
    """
    Calculate GST for an entire order.

    Returns:
    - Item-wise GST breakdown
    - Rate-wise summary (for GST filing)
    - Order totals (subtotal, tax, grand total)
    """
    items = [
        {
            'product_id': item.product_id,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'product_name': item.product_name
        }
        for item in request.items
    ]

    return await gst_service.calculate_order_gst(
        store_id=request.store_id,
        items=items,
        is_inter_state=request.is_inter_state,
        billing_state=request.billing_state
    )


# ============================================================================
# ORDER GST INVOICE ENDPOINT
# ============================================================================

@router.get(
    "/orders/{order_id}/gst-invoice",
    response_model=OrderGSTSummary,
    summary="Get order GST invoice",
    description="Get GST invoice details for an existing order"
)
async def get_order_gst_invoice(order_id: str):
    """
    Get GST invoice details for an order.

    Retrieves order and calculates GST breakdown for all items.
    """
    from app.database.hybrid_db import HybridDatabase
    db = HybridDatabase()

    result = await db.get_order(order_id)
    if not result.success:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    order = result.data

    # Parse items from order
    import json
    items_data = order.get('items', [])
    if isinstance(items_data, str):
        items_data = json.loads(items_data)

    items = [
        {
            'product_id': item.get('product_id', ''),
            'quantity': item.get('quantity', 1),
            'unit_price': Decimal(str(item.get('unit_price', 0))),
            'product_name': item.get('product_name', '')
        }
        for item in items_data
    ]

    # Calculate GST
    gst_summary = await gst_service.calculate_order_gst(
        store_id=order.get('store_id', ''),
        items=items
    )
    gst_summary.order_id = order_id

    return gst_summary


# ============================================================================
# GST RATES REFERENCE ENDPOINT
# ============================================================================

@router.get(
    "/rates",
    summary="Get GST rate slabs",
    description="Get list of valid GST rate slabs in India"
)
async def get_gst_rates():
    """
    Get all valid GST rate slabs.

    Returns:
        List of rate slabs with descriptions
    """
    return {
        "rates": [
            {
                "rate": 0,
                "description": "Essential items - Fresh vegetables, fruits, milk, grains, eggs"
            },
            {
                "rate": 5,
                "description": "Basic packaged goods - Tea, coffee, oil, sugar, spices, branded atta"
            },
            {
                "rate": 12,
                "description": "Processed foods - Butter, ghee, cheese, fruit juice, namkeen"
            },
            {
                "rate": 18,
                "description": "FMCG items - Biscuits, chips, soap, shampoo, toothpaste, chocolates"
            },
            {
                "rate": 28,
                "description": "Luxury/Sin goods - Aerated drinks, tobacco (may include additional cess)"
            }
        ],
        "default_rate": 18,
        "cess_info": "Cess applies to certain luxury goods like aerated drinks (12%), tobacco (varies)"
    }
