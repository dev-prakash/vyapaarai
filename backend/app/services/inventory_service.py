"""
Inventory Service - DynamoDB Integration
Connects to real DynamoDB tables for product and inventory management
"""

from typing import List, Dict, Optional, Any
from decimal import Decimal
import asyncio
import logging
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


class InventoryService:
    """
    Inventory Service with real DynamoDB integration

    Tables:
    - vyaparai-global-products-prod: Global product catalog
    - vyaparai-store-inventory-prod: Store-specific inventory with stock and pricing
    """

    def __init__(self):
        """Initialize inventory service with DynamoDB connection"""
        try:
            # Initialize DynamoDB resource
            kwargs = {'region_name': settings.AWS_REGION}
            if settings.DYNAMODB_ENDPOINT:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT

            self.dynamodb = boto3.resource('dynamodb', **kwargs)

            # Get table references
            self.global_products_table = self.dynamodb.Table('vyaparai-global-products-prod')
            self.store_inventory_table = self.dynamodb.Table('vyaparai-store-inventory-prod')

            logger.info("✅ Inventory service connected to DynamoDB successfully")
            self.use_mock = False

        except Exception as e:
            logger.error(f"⚠️ DynamoDB connection failed: {e}")
            logger.warning("Inventory service will use fallback mode")
            self.use_mock = True
            self.dynamodb = None

    async def get_products(self, store_id: str, category: str = None,
                          status: str = None, search: str = None,
                          page: int = 1, limit: int = 50) -> Dict:
        """
        Get products for a store with filtering and pagination

        Args:
            store_id: Store ID to get inventory for
            category: Filter by category
            status: Filter by status
            search: Search term for product name
            page: Page number (1-indexed)
            limit: Items per page
        """
        if self.use_mock:
            return self._get_mock_response()

        try:
            # Query store inventory table
            response = await asyncio.to_thread(
                self.store_inventory_table.query,
                KeyConditionExpression=Key('store_id').eq(store_id),
                Limit=1000  # Get more for filtering
            )

            products = response.get('Items', [])

            # Apply filters
            filtered_products = []
            for product in products:
                # Get global product data if needed for search/category
                if search or category:
                    global_product = await self._get_global_product(product['product_id'])
                    if global_product:
                        product['global_data'] = global_product

                # Category filter
                if category:
                    product_category = product.get('global_data', {}).get('category', '')
                    if category.lower() not in product_category.lower():
                        continue

                # Status filter
                if status:
                    if status == 'active' and not product.get('is_active', True):
                        continue
                    elif status == 'inactive' and product.get('is_active', True):
                        continue

                # Search filter
                if search:
                    search_lower = search.lower()
                    product_name = product.get('product_name', '').lower()
                    if search_lower not in product_name:
                        continue

                filtered_products.append(product)

            # Convert Decimals to float
            filtered_products = decimal_to_float(filtered_products)

            # Pagination
            total = len(filtered_products)
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_products = filtered_products[start_idx:end_idx]

            return {
                "products": paginated_products,
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit if total > 0 else 1,
                "has_next": end_idx < total,
                "has_prev": page > 1
            }

        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return self._get_mock_response()

    async def get_product(self, store_id: str, product_id: str) -> Optional[Dict]:
        """
        Get single product with inventory details

        Args:
            store_id: Store ID
            product_id: Product ID
        """
        if self.use_mock:
            return None

        try:
            # Get from store inventory
            response = await asyncio.to_thread(
                self.store_inventory_table.get_item,
                Key={'store_id': store_id, 'product_id': product_id}
            )

            product = response.get('Item')
            if not product:
                logger.warning(f"Product {product_id} not found in store {store_id}")
                return None

            # Get global product data
            global_product = await self._get_global_product(product_id)
            if global_product:
                product['global_data'] = global_product

            return decimal_to_float(product)

        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None

    async def search_products(self, store_id: str, search_term: str, limit: int = 50) -> List[Dict]:
        """
        Search products by name, brand, or category

        Args:
            store_id: Store ID
            search_term: Search query
            limit: Maximum results
        """
        if self.use_mock:
            return []

        try:
            # Query all products for store
            response = await asyncio.to_thread(
                self.store_inventory_table.query,
                KeyConditionExpression=Key('store_id').eq(store_id),
                Limit=limit * 2  # Get more for filtering
            )

            products = response.get('Items', [])
            search_lower = search_term.lower()

            # Filter by search term
            matching_products = []
            for product in products:
                product_name = product.get('product_name', '').lower()
                if search_lower in product_name:
                    matching_products.append(product)
                    if len(matching_products) >= limit:
                        break

            return decimal_to_float(matching_products)

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []

    async def update_stock(self, store_id: str, product_id: str,
                          quantity_change: int, reason: str = None) -> Dict:
        """
        Update product stock (CRITICAL for order processing)

        Args:
            store_id: Store ID
            product_id: Product ID
            quantity_change: Positive for addition, negative for reduction
            reason: Reason for stock change
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - no stock updates"}

        try:
            # Get current product
            current_product = await self.get_product(store_id, product_id)
            if not current_product:
                return {"success": False, "error": "Product not found"}

            current_stock = int(current_product.get('current_stock', 0))
            new_stock = max(0, current_stock + quantity_change)

            # Prevent negative stock
            if new_stock < 0:
                logger.warning(f"Attempted to set negative stock for {product_id}")
                return {
                    "success": False,
                    "error": "Insufficient stock",
                    "current_stock": current_stock,
                    "requested_change": quantity_change
                }

            # Update stock in DynamoDB
            response = await asyncio.to_thread(
                self.store_inventory_table.update_item,
                Key={'store_id': store_id, 'product_id': product_id},
                UpdateExpression='SET current_stock = :new_stock, updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':new_stock': new_stock,
                    ':updated_at': datetime.utcnow().isoformat()
                },
                ReturnValues='ALL_NEW'
            )

            updated_product = response.get('Attributes', {})

            # Log stock change
            logger.info(
                f"Stock updated: {product_id} in {store_id} | "
                f"{current_stock} → {new_stock} ({quantity_change:+d}) | "
                f"Reason: {reason or 'Not specified'}"
            )

            return {
                "success": True,
                "previous_stock": current_stock,
                "new_stock": new_stock,
                "change": quantity_change,
                "product": decimal_to_float(updated_product)
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error updating stock: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error updating stock: {e}")
            return {"success": False, "error": str(e)}

    async def check_availability(self, store_id: str, product_id: str,
                                 required_quantity: int) -> Dict:
        """
        Check if product is available in required quantity

        Args:
            store_id: Store ID
            product_id: Product ID
            required_quantity: Quantity needed
        """
        if self.use_mock:
            return {"available": False, "error": "Mock mode"}

        try:
            product = await self.get_product(store_id, product_id)
            if not product:
                return {"available": False, "error": "Product not found"}

            current_stock = int(product.get('current_stock', 0))
            is_active = product.get('is_active', True)
            available = is_active and current_stock >= required_quantity

            return {
                "available": available,
                "current_stock": current_stock,
                "requested": required_quantity,
                "shortage": max(0, required_quantity - current_stock),
                "is_active": is_active
            }

        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {"available": False, "error": str(e)}

    async def get_low_stock_products(self, store_id: str, threshold: int = None) -> List[Dict]:
        """
        Get products with low stock levels

        Args:
            store_id: Store ID
            threshold: Custom threshold (uses min_stock_level if None)
        """
        if self.use_mock:
            return []

        try:
            # Query all products for store
            response = await asyncio.to_thread(
                self.store_inventory_table.query,
                KeyConditionExpression=Key('store_id').eq(store_id)
            )

            products = response.get('Items', [])
            low_stock_products = []

            for product in products:
                if not product.get('is_active', True):
                    continue

                current_stock = int(product.get('current_stock', 0))
                min_stock = int(product.get('min_stock_level', threshold or 10))

                if current_stock <= min_stock:
                    low_stock_products.append(product)

            return decimal_to_float(low_stock_products)

        except Exception as e:
            logger.error(f"Error getting low stock products: {e}")
            return []

    async def get_product_by_barcode(self, barcode: str) -> Optional[Dict]:
        """
        Search global product catalog by barcode

        Args:
            barcode: Product barcode
        """
        if self.use_mock:
            return None

        try:
            # Query barcode index
            response = await asyncio.to_thread(
                self.global_products_table.query,
                IndexName='barcode-index',
                KeyConditionExpression=Key('barcode').eq(barcode),
                Limit=1
            )

            items = response.get('Items', [])
            if items:
                return decimal_to_float(items[0])

            return None

        except Exception as e:
            logger.error(f"Error searching by barcode: {e}")
            return None

    async def get_inventory_summary(self, store_id: str) -> Dict:
        """
        Get inventory summary statistics for a store

        Args:
            store_id: Store ID
        """
        if self.use_mock:
            return self._get_mock_summary()

        try:
            # Query all products for store
            response = await asyncio.to_thread(
                self.store_inventory_table.query,
                KeyConditionExpression=Key('store_id').eq(store_id)
            )

            products = response.get('Items', [])

            total_products = len(products)
            active_products = sum(1 for p in products if p.get('is_active', True))
            out_of_stock = sum(1 for p in products if int(p.get('current_stock', 0)) == 0)
            low_stock = sum(
                1 for p in products
                if 0 < int(p.get('current_stock', 0)) <= int(p.get('min_stock_level', 10))
            )

            # Calculate total inventory value
            total_value = sum(
                int(p.get('current_stock', 0)) * float(p.get('selling_price', 0))
                for p in products
            )

            return {
                "total_products": total_products,
                "active_products": active_products,
                "out_of_stock": out_of_stock,
                "low_stock": low_stock,
                "total_inventory_value": round(total_value, 2)
            }

        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return self._get_mock_summary()

    async def _get_global_product(self, product_id: str) -> Optional[Dict]:
        """Internal method to get global product data"""
        try:
            response = await asyncio.to_thread(
                self.global_products_table.get_item,
                Key={'product_id': product_id}
            )
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error getting global product {product_id}: {e}")
            return None

    def _get_mock_response(self) -> Dict:
        """Fallback response when DynamoDB is unavailable"""
        return {
            "products": [],
            "total": 0,
            "page": 1,
            "pages": 1,
            "has_next": False,
            "has_prev": False,
            "error": "DynamoDB not available - using fallback mode"
        }

    def _get_mock_summary(self) -> Dict:
        """Fallback summary when DynamoDB is unavailable"""
        return {
            "total_products": 0,
            "active_products": 0,
            "out_of_stock": 0,
            "low_stock": 0,
            "total_inventory_value": 0,
            "error": "DynamoDB not available - using fallback mode"
        }


# Global instance
inventory_service = InventoryService()
