"""
Enterprise Cart API
Handles server-side cart management with DynamoDB persistence
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import boto3
from decimal import Decimal
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cart", tags=["cart"])

# DynamoDB setup
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
carts_table = dynamodb.Table('vyaparai-carts-prod')
inventory_table = dynamodb.Table('vyaparai-store-inventory-prod')

# Models
class AddToCartRequest(BaseModel):
    store_id: str = Field(..., description="Store ID")
    product_id: str = Field(..., description="Product ID")
    quantity: int = Field(..., ge=1, description="Quantity to add")
    special_instructions: Optional[str] = Field(None, description="Special instructions")

class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(..., ge=0, description="New quantity (0 to remove)")

class CartItemResponse(BaseModel):
    product_id: str
    product_name: str
    brand_name: Optional[str]
    quantity: int
    unit_price: Decimal
    mrp: Optional[Decimal]
    item_total: Decimal
    image_url: Optional[str]
    special_instructions: Optional[str]
    max_stock: int

class CartResponse(BaseModel):
    cart_id: str
    store_id: str
    items: List[Dict[str, Any]]
    item_count: int
    subtotal: Decimal
    delivery_fee: Decimal
    tax: Decimal
    total: Decimal
    updated_at: str


def get_session_id(session_token: Optional[str] = Header(None, alias="X-Session-ID")) -> str:
    """Get or create session ID for cart"""
    if session_token:
        return session_token
    return f"guest-{uuid.uuid4()}"


@router.post("/add")
async def add_to_cart(
    request: AddToCartRequest,
    session_id: str = Depends(get_session_id)
):
    """Add item to cart with inventory validation"""
    try:
        # Validate inventory
        inv_response = inventory_table.get_item(
            Key={
                'store_id': request.store_id,
                'product_id': request.product_id
            }
        )
        
        if 'Item' not in inv_response:
            raise HTTPException(status_code=404, detail="Product not found in store")
        
        inventory = inv_response['Item']
        
        # Check if product is active
        if not inventory.get('is_active', True):
            raise HTTPException(status_code=400, detail="Product is not available")
        
        # Check stock availability  
        current_stock = int(inventory.get('current_stock', 0))
        if current_stock < request.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock. Only {current_stock} available"
            )
        
        # Get or create cart
        cart_id = f"{session_id}#{request.store_id}"
        cart_response = carts_table.get_item(Key={
            'customer_id': session_id,
            'store_id': request.store_id
        })
        
        if 'Item' in cart_response:
            cart = cart_response['Item']
            items = cart.get('items', [])
        else:
            items = []
        
        # Check if item already in cart
        existing_item = next((item for item in items if item['product_id'] == request.product_id), None)
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item['quantity'] + request.quantity
            if new_quantity > current_stock:
                raise HTTPException(
                    status_code=400,
                    detail=f"Total quantity would exceed stock. Max: {current_stock}"
                )
            existing_item['quantity'] = new_quantity
            existing_item['item_total'] = Decimal(str(existing_item['unit_price'])) * new_quantity
        else:
            # Add new item
            new_item = {
                'product_id': request.product_id,
                'product_name': inventory.get('product_name'),
                'brand_name': inventory.get('brand_name'),
                'quantity': request.quantity,
                'unit_price': Decimal(str(inventory.get('selling_price', 0))),
                'mrp': Decimal(str(inventory.get('mrp', 0))) if inventory.get('mrp') else None,
                'item_total': Decimal(str(inventory.get('selling_price', 0))) * request.quantity,
                'image_url': f"https://vyapaarai-product-images-prod.s3.ap-south-1.amazonaws.com/{request.product_id}/thumbnail.jpg",
                'special_instructions': request.special_instructions,
                'max_stock': current_stock
            }
            items.append(new_item)
        
        # Calculate totals
        subtotal = sum(Decimal(str(item['item_total'])) for item in items)
        item_count = sum(item['quantity'] for item in items)
        delivery_fee = Decimal('0') if subtotal >= 500 else Decimal('20')
        tax = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
        total = subtotal + delivery_fee + tax
        
        # Save cart with TTL (7 days)
        ttl = int((datetime.utcnow() + timedelta(days=7)).timestamp())
        
        carts_table.put_item(
            Item={
                'customer_id': session_id,
                'store_id': request.store_id,
                'cart_id': cart_id,
                'items': items,
                'item_count': item_count,
                'subtotal': subtotal,
                'delivery_fee': delivery_fee,
                'tax': tax,
                'total': total,
                'updated_at': datetime.utcnow().isoformat(),
                'expires_at': ttl
            }
        )
        
        return {
            'success': True,
            'cart': {
                'cart_id': cart_id,
                'store_id': request.store_id,
                'items': items,
                'item_count': item_count,
                'subtotal': float(subtotal),
                'delivery_fee': float(delivery_fee),
                'tax': float(tax),
                'total': float(total),
                'updated_at': datetime.utcnow().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add to cart: {str(e)}")


@router.get("")
async def get_cart(
    store_id: str,
    session_id: str = Depends(get_session_id)
):
    """Get current cart"""
    try:
        cart_id = f"{session_id}#{store_id}"
        response = carts_table.get_item(Key={
            'customer_id': session_id,
            'store_id': store_id
        })
        
        if 'Item' not in response:
            return {
                'success': True,
                'cart': {
                    'cart_id': cart_id,
                    'store_id': store_id,
                    'items': [],
                    'item_count': 0,
                    'subtotal': 0,
                    'delivery_fee': 20,
                    'tax': 0,
                    'total': 20
                }
            }
        
        cart = response['Item']
        
        # Convert Decimals to float for JSON
        return {
            'success': True,
            'cart': {
                'cart_id': cart['cart_id'],
                'store_id': cart['store_id'],
                'items': cart.get('items', []),
                'item_count': cart.get('item_count', 0),
                'subtotal': float(cart.get('subtotal', 0)),
                'delivery_fee': float(cart.get('delivery_fee', 0)),
                'tax': float(cart.get('tax', 0)),
                'total': float(cart.get('total', 0)),
                'updated_at': cart.get('updated_at')
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cart: {str(e)}")


@router.put("/{product_id}")
async def update_cart_item(
    product_id: str,
    request: UpdateCartItemRequest,
    store_id: str,
    session_id: str = Depends(get_session_id)
):
    """Update cart item quantity"""
    try:
        cart_id = f"{session_id}#{store_id}"
        cart_response = carts_table.get_item(Key={
            'customer_id': session_id,
            'store_id': store_id
        })
        
        if 'Item' not in cart_response:
            raise HTTPException(status_code=404, detail="Cart not found")
        
        cart = cart_response['Item']
        items = cart.get('items', [])
        
        # Find and update item
        item = next((i for i in items if i['product_id'] == product_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Item not in cart")
        
        if request.quantity == 0:
            # Remove item
            items = [i for i in items if i['product_id'] != product_id]
        else:
            # Validate stock
            if request.quantity > item['max_stock']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quantity exceeds available stock ({item['max_stock']})"
                )
            item['quantity'] = request.quantity
            item['item_total'] = Decimal(str(item['unit_price'])) * request.quantity
        
        # Recalculate totals
        subtotal = sum(Decimal(str(i['item_total'])) for i in items)
        item_count = sum(i['quantity'] for i in items)
        delivery_fee = Decimal('0') if subtotal >= 500 else Decimal('20')
        tax = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
        total = subtotal + delivery_fee + tax
        
        # Update cart
        ttl = int((datetime.utcnow() + timedelta(days=7)).timestamp())
        
        carts_table.put_item(
            Item={
                **cart,
                'items': items,
                'item_count': item_count,
                'subtotal': subtotal,
                'delivery_fee': delivery_fee,
                'tax': tax,
                'total': total,
                'updated_at': datetime.utcnow().isoformat(),
                'expires_at': ttl
            }
        )
        
        return {'success': True, 'message': 'Cart updated successfully'}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def clear_cart(
    store_id: str,
    session_id: str = Depends(get_session_id)
):
    """Clear entire cart"""
    try:
        cart_id = f"{session_id}#{store_id}"
        carts_table.delete_item(Key={
            'customer_id': session_id,
            'store_id': store_id
        })

        return {'success': True, 'message': 'Cart cleared successfully'}

    except Exception as e:
        logger.error(f"Error clearing cart: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_carts(
    session_id: str = Depends(get_session_id)
):
    """Get all carts for authenticated user across all stores"""
    try:
        # Query all carts for this customer
        response = carts_table.query(
            KeyConditionExpression='customer_id = :customer_id',
            ExpressionAttributeValues={
                ':customer_id': session_id
            }
        )

        if not response.get('Items'):
            return {
                'total_carts': 0,
                'total_items': 0,
                'grand_total': 0.0,
                'stores': []
            }

        stores_data = []
        total_items = 0
        grand_total = 0.0

        for cart in response['Items']:
            store_id = cart.get('store_id')
            items = cart.get('items', [])
            item_count = cart.get('item_count', 0)
            cart_total = float(cart.get('total', 0))

            total_items += item_count
            grand_total += cart_total

            # Get store name (try to fetch from stores table, fallback to ID)
            store_name = store_id
            try:
                stores_table = dynamodb.Table('vyaparai-stores-prod')
                store_response = stores_table.get_item(Key={'store_id': store_id})
                if 'Item' in store_response:
                    store_name = store_response['Item'].get('business_name', store_id)
            except Exception as e:
                logger.warning(f"Could not fetch store name for {store_id}: {str(e)}")

            stores_data.append({
                'store_id': store_id,
                'store_name': store_name,
                'items': item_count,
                'total': cart_total,
                'updated_at': cart.get('updated_at'),
                'items_detail': [
                    {
                        'product_id': item.get('product_id'),
                        'product_name': item.get('product_name'),
                        'quantity': item.get('quantity'),
                        'unit_price': float(item.get('unit_price', 0)),
                        'image_url': item.get('image_url')
                    }
                    for item in items
                ]
            })

        return {
            'total_carts': len(stores_data),
            'total_items': total_items,
            'grand_total': grand_total,
            'stores': stores_data
        }

    except Exception as e:
        logger.error(f"Error getting all carts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get carts: {str(e)}")
