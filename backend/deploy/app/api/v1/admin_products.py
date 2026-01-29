"""
Admin Products API Router
Provides admin access to global product catalog management

Includes:
- Global catalog CRUD operations
- Promotion queue management for store-specific products
- Quality review and approval workflow
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import uuid
import ulid
from datetime import datetime
import logging

from app.api.v1.admin_auth import get_current_admin_user
from app.core.gst_config import (
    GST_CATEGORIES,
    GSTRate,
    get_gst_rate_from_hsn,
    get_default_gst_rate,
    suggest_category_from_product_name,
    validate_hsn_code,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/products", tags=["Admin Products"])

# DynamoDB configuration
dynamodb_client = boto3.client('dynamodb', region_name='ap-south-1')
dynamodb_resource = boto3.resource('dynamodb', region_name='ap-south-1')
GLOBAL_PRODUCTS_TABLE = 'vyaparai-global-products-prod'
STORE_INVENTORY_TABLE = 'vyaparai-store-inventory-prod'

# Table resources
global_products_table = dynamodb_resource.Table(GLOBAL_PRODUCTS_TABLE)
store_inventory_table = dynamodb_resource.Table(STORE_INVENTORY_TABLE)

# Promotion status constants
PROMOTION_STATUS_PENDING = 'pending_review'
PROMOTION_STATUS_APPROVED = 'approved'
PROMOTION_STATUS_REJECTED = 'rejected'
PROMOTION_STATUS_PROMOTED = 'promoted'


class PromotionRejectRequest(BaseModel):
    """Schema for rejecting a promotion request"""
    reason: str


class PromotionApproveRequest(BaseModel):
    """Schema for approving a promotion request with GST details"""
    hsn_code: Optional[str] = Field(None, description="HSN code for GST classification")
    gst_category: Optional[str] = Field(None, description="GST category code (e.g., BISCUITS, TEA_PACKAGED)")
    gst_rate: Optional[Decimal] = Field(None, description="GST rate override (0, 5, 12, 18, 28)")
    cess_rate: Optional[Decimal] = Field(default=Decimal("0"), description="Cess rate if applicable")
    is_gst_exempt: Optional[bool] = Field(default=False, description="Whether product is GST exempt")


class GSTSuggestionResponse(BaseModel):
    """Response for GST suggestion based on product details"""
    suggested_category: Optional[str] = None
    suggested_category_name: Optional[str] = None
    suggested_hsn_code: Optional[str] = None
    suggested_gst_rate: Decimal = Decimal("18")
    suggested_cess_rate: Decimal = Decimal("0")
    confidence: str = "low"  # low, medium, high
    all_matching_categories: List[Dict[str, Any]] = []


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


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


def _get_gst_suggestion(
    product_name: str,
    category: str = '',
    existing_hsn: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate GST suggestion based on product name and category.

    Uses multiple strategies:
    1. If HSN code exists, use it directly
    2. Try to match product name to known GST categories
    3. Try to match product category to GST categories
    4. Fall back to default 18% rate
    """
    suggestion = {
        'suggested_category': None,
        'suggested_category_name': None,
        'suggested_hsn_code': existing_hsn,
        'suggested_gst_rate': float(get_default_gst_rate().value),
        'suggested_cess_rate': 0.0,
        'confidence': 'low',
        'all_matching_categories': []
    }

    # Strategy 1: Use existing HSN code if valid
    if existing_hsn and validate_hsn_code(existing_hsn):
        gst_cat = get_gst_rate_from_hsn(existing_hsn)
        if gst_cat:
            suggestion['suggested_category'] = gst_cat.code
            suggestion['suggested_category_name'] = gst_cat.name
            suggestion['suggested_hsn_code'] = existing_hsn
            suggestion['suggested_gst_rate'] = float(gst_cat.gst_rate.value)
            suggestion['suggested_cess_rate'] = float(gst_cat.cess_rate)
            suggestion['confidence'] = 'high'
            return suggestion

    # Strategy 2: Try to match product name
    if product_name:
        category_code = suggest_category_from_product_name(product_name)
        if category_code and category_code in GST_CATEGORIES:
            gst_cat = GST_CATEGORIES[category_code]
            suggestion['suggested_category'] = gst_cat.code
            suggestion['suggested_category_name'] = gst_cat.name
            suggestion['suggested_hsn_code'] = gst_cat.hsn_prefix
            suggestion['suggested_gst_rate'] = float(gst_cat.gst_rate.value)
            suggestion['suggested_cess_rate'] = float(gst_cat.cess_rate)
            suggestion['confidence'] = 'medium'

    # Strategy 3: Find all potentially matching categories for admin to choose
    matching_categories = []
    search_terms = product_name.lower().split() if product_name else []

    for code, cat in GST_CATEGORIES.items():
        # Check if any search term matches category name or code
        cat_name_lower = cat.name.lower()
        if any(term in cat_name_lower or term in code.lower() for term in search_terms):
            matching_categories.append({
                'code': cat.code,
                'name': cat.name,
                'hsn_prefix': cat.hsn_prefix,
                'gst_rate': float(cat.gst_rate.value),
                'cess_rate': float(cat.cess_rate)
            })

    # Also check product category against GST categories
    if category:
        category_lower = category.lower()
        for code, cat in GST_CATEGORIES.items():
            if category_lower in cat.name.lower() or category_lower in code.lower():
                match_exists = any(m['code'] == cat.code for m in matching_categories)
                if not match_exists:
                    matching_categories.append({
                        'code': cat.code,
                        'name': cat.name,
                        'hsn_prefix': cat.hsn_prefix,
                        'gst_rate': float(cat.gst_rate.value),
                        'cess_rate': float(cat.cess_rate)
                    })

    # Sort by GST rate for easier review
    matching_categories.sort(key=lambda x: x['gst_rate'])
    suggestion['all_matching_categories'] = matching_categories[:10]  # Limit to top 10

    return suggestion


@router.get("/global")
async def list_global_products(
    limit: int = Query(100, ge=1, le=1000, description="Number of products to return"),
    last_key: Optional[str] = Query(None, description="Pagination key from previous response"),
    category: Optional[str] = Query(None, description="Filter by category"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    search: Optional[str] = Query(None, description="Search in product name"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all products in the global product catalog

    Admin only endpoint for viewing and managing global products
    """
    try:
        scan_kwargs = {
            'TableName': GLOBAL_PRODUCTS_TABLE,
            'Limit': limit
        }

        # Add pagination
        if last_key:
            try:
                scan_kwargs['ExclusiveStartKey'] = {'product_id': {'S': last_key}}
            except Exception:
                pass

        # Execute scan
        response = dynamodb_client.scan(**scan_kwargs)

        # Parse products
        products = []
        for item in response.get('Items', []):
            product = parse_dynamodb_item(item)

            # Apply filters
            if category and product.get('category') != category:
                continue
            if brand and product.get('brand') != brand:
                continue
            if verification_status and product.get('verification_status') != verification_status:
                continue
            if search and search.lower() not in product.get('name', '').lower():
                continue

            products.append(product)

        # Calculate actual stores_using_count from inventory
        try:
            # Scan inventory table to get all product-store mappings
            inventory_response = dynamodb_client.scan(
                TableName=STORE_INVENTORY_TABLE,
                ProjectionExpression='product_id, store_id'
            )

            # Build mapping of product_id -> set of unique store_ids
            product_stores = {}
            for inv_item in inventory_response.get('Items', []):
                product_id = inv_item.get('product_id', {}).get('S')
                store_id = inv_item.get('store_id', {}).get('S')

                if product_id and store_id:
                    if product_id not in product_stores:
                        product_stores[product_id] = set()
                    product_stores[product_id].add(store_id)

            # Update each product with actual count
            for product in products:
                product_id = product.get('product_id')
                if product_id in product_stores:
                    product['stores_using_count'] = len(product_stores[product_id])
                else:
                    product['stores_using_count'] = 0

        except Exception as e:
            logger.warning(f"Failed to calculate stores_using_count: {str(e)}")
            # If inventory scan fails, keep existing counts (or set to 0)
            for product in products:
                product['stores_using_count'] = product.get('stores_using_count', 0)

        # Prepare response
        result = {
            'success': True,
            'products': products,
            'count': len(products),
            'total_scanned': len(response.get('Items', []))
        }

        # Add pagination info
        if 'LastEvaluatedKey' in response:
            result['last_key'] = response['LastEvaluatedKey'].get('product_id', {}).get('S')
            result['has_more'] = True
        else:
            result['has_more'] = False

        return result

    except Exception as e:
        logger.error(f"Error listing global products: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list products: {str(e)}")


@router.get("/global/stats")
async def get_global_products_stats(
    current_user: dict = Depends(get_current_admin_user)
):
    """Get statistics about global product catalog"""
    try:
        # Scan all products to get stats
        products = []
        last_evaluated_key = None

        while True:
            scan_kwargs = {'TableName': GLOBAL_PRODUCTS_TABLE}
            if last_evaluated_key:
                scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

            response = dynamodb_client.scan(**scan_kwargs)

            for item in response.get('Items', []):
                products.append(parse_dynamodb_item(item))

            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break

        # Calculate statistics
        stats = {
            'total_products': len(products),
            'with_images': sum(1 for p in products if p.get('canonical_image_urls', {}).get('original')),
            'without_images': sum(1 for p in products if not p.get('canonical_image_urls', {}).get('original')),
            'by_category': {},
            'by_brand': {},
            'by_verification_status': {},
            'average_quality_score': 0
        }

        # Count by category
        for product in products:
            category = product.get('category', 'Unknown')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1

            brand = product.get('brand', 'Unknown')
            stats['by_brand'][brand] = stats['by_brand'].get(brand, 0) + 1

            status = product.get('verification_status', 'Unknown')
            stats['by_verification_status'][status] = stats['by_verification_status'].get(status, 0) + 1

        # Calculate average quality score
        quality_scores = [p.get('quality_score', 0) for p in products if p.get('quality_score')]
        if quality_scores:
            stats['average_quality_score'] = sum(quality_scores) / len(quality_scores)

        return {
            'success': True,
            'stats': stats
        }

    except Exception as e:
        logger.error(f"Error calculating stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate stats: {str(e)}")


@router.get("/global/{product_id}")
async def get_global_product(
    product_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get a single product from global catalog"""
    try:
        response = dynamodb_client.get_item(
            TableName=GLOBAL_PRODUCTS_TABLE,
            Key={'product_id': {'S': product_id}}
        )

        if 'Item' not in response:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

        product = parse_dynamodb_item(response['Item'])

        return {
            'success': True,
            'product': product
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch product: {str(e)}")


# =============================================================================
# PROMOTION QUEUE MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/promotion-queue")
async def list_promotion_queue(
    status: Optional[str] = Query(None, description="Filter by status: pending_review, approved, rejected"),
    limit: int = Query(50, ge=1, le=200, description="Number of items to return"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all products pending promotion to global catalog

    Admin only endpoint for reviewing store-specific products for promotion
    """
    try:
        # Scan inventory for products with pending promotion requests
        scan_kwargs = {
            'FilterExpression': 'promotion_status = :status',
            'ExpressionAttributeValues': {
                ':status': status if status else PROMOTION_STATUS_PENDING
            }
        }

        response = store_inventory_table.scan(**scan_kwargs)
        items = response.get('Items', [])

        # Handle pagination for large datasets
        while 'LastEvaluatedKey' in response and len(items) < limit:
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = store_inventory_table.scan(**scan_kwargs)
            items.extend(response.get('Items', []))

        # Limit results
        items = items[:limit]

        # Convert Decimals and enrich with store info
        promotion_requests = []
        for item in items:
            request = decimal_to_float(item)
            request['promotion_request_id'] = f"{item.get('store_id')}#{item.get('product_id')}"
            promotion_requests.append(request)

        # Sort by promotion request date (newest first)
        promotion_requests.sort(
            key=lambda x: x.get('promotion_request_date', ''),
            reverse=True
        )

        return {
            'success': True,
            'promotion_requests': promotion_requests,
            'count': len(promotion_requests),
            'filter_status': status if status else PROMOTION_STATUS_PENDING
        }

    except Exception as e:
        logger.error(f"Error listing promotion queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list promotion queue: {str(e)}")


@router.get("/promotion-request/{store_id}/{product_id}")
async def get_promotion_request(
    store_id: str,
    product_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Get detailed information about a promotion request

    Includes product details, quality score, and store information
    """
    try:
        # Get the product from inventory
        response = store_inventory_table.get_item(
            Key={
                'store_id': store_id,
                'product_id': product_id
            }
        )

        if 'Item' not in response:
            raise HTTPException(
                status_code=404,
                detail=f"Product not found: {store_id}/{product_id}"
            )

        item = response['Item']

        # Verify it has a promotion request
        if item.get('promotion_status') not in [
            PROMOTION_STATUS_PENDING,
            PROMOTION_STATUS_APPROVED,
            PROMOTION_STATUS_REJECTED
        ]:
            raise HTTPException(
                status_code=400,
                detail="This product does not have an active promotion request"
            )

        product = decimal_to_float(item)

        # Calculate quality metrics for admin review
        quality_checks = {
            'has_name': bool(product.get('product_name')),
            'has_description': len(str(product.get('description', ''))) >= 20,
            'has_category': bool(product.get('category')) and product.get('category') != 'Uncategorized',
            'has_valid_price': (product.get('selling_price') or 0) > 0,
            'has_image': bool(product.get('image_url') or product.get('image_urls')),
            'has_barcode': bool(product.get('barcode')),
            'has_brand': bool(product.get('brand')),
            'has_unit': bool(product.get('unit'))
        }

        quality_score = sum(quality_checks.values()) / len(quality_checks) * 100

        # Generate GST suggestion based on product name and category
        gst_suggestion = _get_gst_suggestion(
            product_name=product.get('product_name', ''),
            category=product.get('category', ''),
            existing_hsn=product.get('hsn_code')
        )

        return {
            'success': True,
            'product': product,
            'quality_checks': quality_checks,
            'quality_score': round(quality_score, 1),
            'eligible_for_promotion': quality_score >= 60,
            'promotion_status': product.get('promotion_status'),
            'promotion_request_date': product.get('promotion_request_date'),
            'gst_suggestion': gst_suggestion
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching promotion request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch promotion request: {str(e)}")


@router.post("/promotion-request/{store_id}/{product_id}/approve")
async def approve_promotion(
    store_id: str,
    product_id: str,
    gst_details: Optional[PromotionApproveRequest] = Body(default=None),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Approve a promotion request and create a global catalog product with GST details.

    This is a transactional operation that:
    1. Creates a new product in the global catalog with GST classification
    2. Updates the inventory item's promotion status
    3. Links the inventory item to the new global product

    GST Details:
    - If hsn_code is provided, GST rate is looked up automatically
    - If gst_category is provided, uses that category's rate
    - If gst_rate is provided, uses that as override
    - Falls back to auto-suggestion based on product name
    """
    try:
        # Get the product from inventory
        response = store_inventory_table.get_item(
            Key={
                'store_id': store_id,
                'product_id': product_id
            }
        )

        if 'Item' not in response:
            raise HTTPException(
                status_code=404,
                detail=f"Product not found: {store_id}/{product_id}"
            )

        item = response['Item']

        # Verify it's pending promotion
        if item.get('promotion_status') != PROMOTION_STATUS_PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Product is not pending promotion. Current status: {item.get('promotion_status')}"
            )

        # Generate new global product ID
        global_product_id = f"GLOB_{ulid.new().str}"

        # Determine GST details
        hsn_code = None
        gst_category = None
        gst_rate = get_default_gst_rate().value  # Default 18%
        cess_rate = Decimal('0')
        is_gst_exempt = False

        if gst_details:
            # Use provided GST details
            if gst_details.hsn_code and validate_hsn_code(gst_details.hsn_code):
                hsn_code = gst_details.hsn_code
                # Look up rate from HSN
                hsn_cat = get_gst_rate_from_hsn(hsn_code)
                if hsn_cat:
                    gst_category = hsn_cat.code
                    gst_rate = hsn_cat.gst_rate.value
                    cess_rate = Decimal(str(hsn_cat.cess_rate))

            if gst_details.gst_category and gst_details.gst_category in GST_CATEGORIES:
                gst_category = gst_details.gst_category
                cat = GST_CATEGORIES[gst_category]
                if not hsn_code:
                    hsn_code = cat.hsn_prefix
                gst_rate = cat.gst_rate.value
                cess_rate = Decimal(str(cat.cess_rate))

            # Allow explicit rate override
            if gst_details.gst_rate is not None:
                gst_rate = gst_details.gst_rate

            if gst_details.cess_rate is not None:
                cess_rate = gst_details.cess_rate

            if gst_details.is_gst_exempt:
                is_gst_exempt = True
                gst_rate = Decimal('0')
                cess_rate = Decimal('0')
        else:
            # Auto-suggest GST based on product name
            suggestion = _get_gst_suggestion(
                product_name=item.get('product_name', ''),
                category=item.get('category', ''),
                existing_hsn=item.get('hsn_code')
            )
            if suggestion['suggested_category']:
                gst_category = suggestion['suggested_category']
                hsn_code = suggestion['suggested_hsn_code']
                gst_rate = Decimal(str(suggestion['suggested_gst_rate']))
                cess_rate = Decimal(str(suggestion['suggested_cess_rate']))

        # Create global catalog product
        now = datetime.utcnow().isoformat() + 'Z'

        global_product = {
            'product_id': global_product_id,
            'name': item.get('product_name', 'Unknown Product'),
            'brand': item.get('brand', ''),
            'category': item.get('category', 'Uncategorized'),
            'description': item.get('description', ''),
            'base_price': item.get('selling_price', Decimal('0')),
            'mrp': item.get('mrp', item.get('selling_price', Decimal('0'))),
            'unit': item.get('unit', 'piece'),
            'barcode': item.get('barcode', ''),
            'canonical_image_urls': {
                'original': item.get('image_url', ''),
                'thumbnail': item.get('image_url', '')
            },
            # GST fields
            'hsn_code': hsn_code,
            'gst_category': gst_category,
            'gst_rate': gst_rate,
            'cess_rate': cess_rate,
            'is_gst_exempt': is_gst_exempt,
            # Metadata
            'verification_status': 'verified',
            'quality_score': Decimal(str(item.get('quality_score', 70))),
            'stores_using_count': Decimal('1'),
            'source': 'store_promotion',
            'source_store_id': store_id,
            'promoted_from_product_id': product_id,
            'promoted_by_admin_id': current_user.get('user_id', 'admin'),
            'created_at': now,
            'updated_at': now
        }

        # Use transaction to ensure atomicity
        try:
            # Create global product
            global_products_table.put_item(Item=global_product)

            # Update inventory item with GST fields inherited from global product
            store_inventory_table.update_item(
                Key={
                    'store_id': store_id,
                    'product_id': product_id
                },
                UpdateExpression="""
                    SET promotion_status = :status,
                        promoted_to_global_id = :global_id,
                        promotion_approved_at = :approved_at,
                        promotion_approved_by = :approved_by,
                        generic_product_id = :global_id,
                        product_source = :source,
                        visibility = :visibility,
                        hsn_code = :hsn_code,
                        gst_category = :gst_category,
                        gst_rate = :gst_rate,
                        cess_rate = :cess_rate,
                        is_gst_exempt = :is_gst_exempt
                """,
                ExpressionAttributeValues={
                    ':status': PROMOTION_STATUS_PROMOTED,
                    ':global_id': global_product_id,
                    ':approved_at': now,
                    ':approved_by': current_user.get('user_id', 'admin'),
                    ':source': 'global_catalog',
                    ':visibility': 'global',
                    ':hsn_code': hsn_code,
                    ':gst_category': gst_category,
                    ':gst_rate': gst_rate,
                    ':cess_rate': cess_rate,
                    ':is_gst_exempt': is_gst_exempt
                }
            )

            logger.info(
                f"Product {product_id} promoted to global catalog as {global_product_id} "
                f"with GST: {gst_rate}% (HSN: {hsn_code}, Category: {gst_category})"
            )

            return {
                'success': True,
                'message': 'Product promoted to global catalog with GST classification',
                'global_product_id': global_product_id,
                'original_product_id': product_id,
                'store_id': store_id,
                'gst_details': {
                    'hsn_code': hsn_code,
                    'gst_category': gst_category,
                    'gst_rate': float(gst_rate),
                    'cess_rate': float(cess_rate),
                    'is_gst_exempt': is_gst_exempt
                }
            }

        except Exception as tx_error:
            # If transaction fails, attempt rollback
            logger.error(f"Transaction error during promotion: {str(tx_error)}")
            try:
                global_products_table.delete_item(
                    Key={'product_id': global_product_id}
                )
            except:
                pass
            raise HTTPException(
                status_code=500,
                detail=f"Failed to complete promotion transaction: {str(tx_error)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving promotion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to approve promotion: {str(e)}")


@router.post("/promotion-request/{store_id}/{product_id}/reject")
async def reject_promotion(
    store_id: str,
    product_id: str,
    rejection: PromotionRejectRequest = Body(...),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Reject a promotion request with a reason

    The store owner will be notified and can address the issues
    """
    try:
        # Get the product from inventory
        response = store_inventory_table.get_item(
            Key={
                'store_id': store_id,
                'product_id': product_id
            }
        )

        if 'Item' not in response:
            raise HTTPException(
                status_code=404,
                detail=f"Product not found: {store_id}/{product_id}"
            )

        item = response['Item']

        # Verify it's pending promotion
        if item.get('promotion_status') != PROMOTION_STATUS_PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Product is not pending promotion. Current status: {item.get('promotion_status')}"
            )

        now = datetime.utcnow().isoformat() + 'Z'

        # Update inventory item with rejection
        store_inventory_table.update_item(
            Key={
                'store_id': store_id,
                'product_id': product_id
            },
            UpdateExpression="""
                SET promotion_status = :status,
                    promotion_rejection_reason = :reason,
                    promotion_rejected_at = :rejected_at,
                    promotion_rejected_by = :rejected_by
            """,
            ExpressionAttributeValues={
                ':status': PROMOTION_STATUS_REJECTED,
                ':reason': rejection.reason,
                ':rejected_at': now,
                ':rejected_by': current_user.get('user_id', 'admin')
            }
        )

        logger.info(f"Promotion request rejected for {store_id}/{product_id}: {rejection.reason}")

        return {
            'success': True,
            'message': 'Promotion request rejected',
            'product_id': product_id,
            'store_id': store_id,
            'rejection_reason': rejection.reason
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting promotion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reject promotion: {str(e)}")


@router.get("/promotion-queue/stats")
async def get_promotion_queue_stats(
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Get statistics about the promotion queue

    Returns counts by status for dashboard display
    """
    try:
        # Count products by promotion status
        stats = {
            'pending': 0,
            'approved': 0,
            'rejected': 0,
            'promoted': 0,
            'total': 0
        }

        # Scan for each status
        for status_key, status_value in [
            ('pending', PROMOTION_STATUS_PENDING),
            ('approved', PROMOTION_STATUS_APPROVED),
            ('rejected', PROMOTION_STATUS_REJECTED),
            ('promoted', PROMOTION_STATUS_PROMOTED)
        ]:
            response = store_inventory_table.scan(
                FilterExpression='promotion_status = :status',
                ExpressionAttributeValues={':status': status_value},
                Select='COUNT'
            )
            stats[status_key] = response.get('Count', 0)
            stats['total'] += stats[status_key]

        return {
            'success': True,
            'stats': stats
        }

    except Exception as e:
        logger.error(f"Error getting promotion queue stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# =============================================================================
# GST MANAGEMENT ENDPOINTS FOR ADMIN
# =============================================================================

@router.get("/gst/categories")
async def list_gst_categories(
    rate: Optional[int] = Query(None, description="Filter by GST rate (0, 5, 12, 18, 28)"),
    search: Optional[str] = Query(None, description="Search in category name"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all available GST categories for product classification.

    Admin can use this to find appropriate GST category when approving products.
    """
    categories = []

    for code, cat in GST_CATEGORIES.items():
        # Apply rate filter
        if rate is not None and int(cat.gst_rate.value) != rate:
            continue

        # Apply search filter
        if search and search.lower() not in cat.name.lower():
            continue

        categories.append({
            'code': cat.code,
            'name': cat.name,
            'hsn_prefix': cat.hsn_prefix,
            'gst_rate': float(cat.gst_rate.value),
            'cess_rate': float(cat.cess_rate),
            'description': getattr(cat, 'description', '')
        })

    # Sort by GST rate, then by name
    categories.sort(key=lambda x: (x['gst_rate'], x['name']))

    return {
        'success': True,
        'categories': categories,
        'count': len(categories),
        'rate_summary': {
            '0%': sum(1 for c in categories if c['gst_rate'] == 0),
            '5%': sum(1 for c in categories if c['gst_rate'] == 5),
            '12%': sum(1 for c in categories if c['gst_rate'] == 12),
            '18%': sum(1 for c in categories if c['gst_rate'] == 18),
            '28%': sum(1 for c in categories if c['gst_rate'] == 28),
        }
    }


@router.get("/gst/suggest/{product_name}")
async def suggest_gst_for_product(
    product_name: str,
    category: Optional[str] = Query(None, description="Product category for better suggestion"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Get GST suggestion for a product based on its name and category.

    Useful for admin to quickly find appropriate GST classification.
    """
    suggestion = _get_gst_suggestion(
        product_name=product_name,
        category=category or '',
        existing_hsn=None
    )

    return {
        'success': True,
        'product_name': product_name,
        'suggestion': suggestion
    }


@router.put("/global/{product_id}/gst")
async def update_global_product_gst(
    product_id: str,
    gst_details: PromotionApproveRequest = Body(...),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Update GST details for an existing global catalog product.

    Use this to correct or update GST classification for products already in the catalog.
    """
    try:
        # Verify product exists
        response = dynamodb_client.get_item(
            TableName=GLOBAL_PRODUCTS_TABLE,
            Key={'product_id': {'S': product_id}}
        )

        if 'Item' not in response:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

        # Determine GST values
        hsn_code = gst_details.hsn_code
        gst_category = gst_details.gst_category
        gst_rate = gst_details.gst_rate if gst_details.gst_rate is not None else get_default_gst_rate().value
        cess_rate = gst_details.cess_rate if gst_details.cess_rate is not None else Decimal('0')
        is_gst_exempt = gst_details.is_gst_exempt or False

        # If HSN provided, validate and lookup
        if hsn_code and validate_hsn_code(hsn_code):
            hsn_cat = get_gst_rate_from_hsn(hsn_code)
            if hsn_cat and not gst_category:
                gst_category = hsn_cat.code

        # If category provided, get details
        if gst_category and gst_category in GST_CATEGORIES:
            cat = GST_CATEGORIES[gst_category]
            if not hsn_code:
                hsn_code = cat.hsn_prefix
            if gst_details.gst_rate is None:
                gst_rate = cat.gst_rate.value
            if gst_details.cess_rate is None:
                cess_rate = Decimal(str(cat.cess_rate))

        # Handle exempt status
        if is_gst_exempt:
            gst_rate = Decimal('0')
            cess_rate = Decimal('0')

        now = datetime.utcnow().isoformat() + 'Z'

        # Update global product
        global_products_table.update_item(
            Key={'product_id': product_id},
            UpdateExpression="""
                SET hsn_code = :hsn_code,
                    gst_category = :gst_category,
                    gst_rate = :gst_rate,
                    cess_rate = :cess_rate,
                    is_gst_exempt = :is_gst_exempt,
                    gst_updated_at = :updated_at,
                    gst_updated_by = :updated_by
            """,
            ExpressionAttributeValues={
                ':hsn_code': hsn_code,
                ':gst_category': gst_category,
                ':gst_rate': gst_rate,
                ':cess_rate': cess_rate,
                ':is_gst_exempt': is_gst_exempt,
                ':updated_at': now,
                ':updated_by': current_user.get('user_id', 'admin')
            }
        )

        logger.info(f"Updated GST for global product {product_id}: {gst_rate}% (HSN: {hsn_code})")

        return {
            'success': True,
            'message': 'GST details updated successfully',
            'product_id': product_id,
            'gst_details': {
                'hsn_code': hsn_code,
                'gst_category': gst_category,
                'gst_rate': float(gst_rate),
                'cess_rate': float(cess_rate),
                'is_gst_exempt': is_gst_exempt
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating GST for product {product_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update GST: {str(e)}")


@router.get("/global/without-gst")
async def list_products_without_gst(
    limit: int = Query(100, ge=1, le=500, description="Number of products to return"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List global products that don't have GST classification.

    Useful for admin to identify products needing GST assignment.
    """
    try:
        # Scan for products without hsn_code or gst_rate
        response = dynamodb_client.scan(
            TableName=GLOBAL_PRODUCTS_TABLE,
            FilterExpression='attribute_not_exists(hsn_code) OR attribute_not_exists(gst_rate)',
            Limit=limit
        )

        products = []
        for item in response.get('Items', []):
            product = parse_dynamodb_item(item)
            # Generate suggestion for each product
            suggestion = _get_gst_suggestion(
                product_name=product.get('name', ''),
                category=product.get('category', '')
            )
            product['gst_suggestion'] = suggestion
            products.append(product)

        return {
            'success': True,
            'products': products,
            'count': len(products),
            'message': f"Found {len(products)} products without GST classification"
        }

    except Exception as e:
        logger.error(f"Error listing products without GST: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list products: {str(e)}")
