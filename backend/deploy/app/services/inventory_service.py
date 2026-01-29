"""
Inventory Service - DynamoDB Integration
Connects to real DynamoDB tables for product and inventory management

Supports:
- Global catalog products (admin-managed)
- Store-specific custom products (store owner-managed)
- Product visibility rules for multi-tenancy
- Promotion workflow for custom products to global catalog
"""

from typing import List, Dict, Optional, Any
from decimal import Decimal
import asyncio
import logging
import os
import uuid
import time
import threading
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.core.config import settings
from app.database.stats_repository import get_stats_repository

logger = logging.getLogger(__name__)


# ==================== IN-MEMORY CACHE ====================
# Cache for inventory summary to reduce DynamoDB queries
# Persists across Lambda warm invocations for low-cost performance boost

class InventorySummaryCache:
    """
    Thread-safe in-memory cache for inventory summaries.

    Uses TTL-based expiration to ensure data freshness while
    reducing DynamoDB read operations.
    """

    def __init__(self, default_ttl: int = 60):
        """
        Initialize cache with default TTL.

        Args:
            default_ttl: Time-to-live in seconds (default 60s)
        """
        self._cache: Dict[str, Dict] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl

    def get(self, store_id: str) -> Optional[Dict]:
        """
        Get cached summary for a store if not expired.

        Args:
            store_id: Store ID to lookup

        Returns:
            Cached summary dict or None if not found/expired
        """
        with self._lock:
            if store_id not in self._cache:
                return None

            # Check if expired
            cached_time = self._timestamps.get(store_id, 0)
            if time.time() - cached_time > self.default_ttl:
                # Expired - remove from cache
                del self._cache[store_id]
                del self._timestamps[store_id]
                logger.debug(f"Cache expired for store {store_id}")
                return None

            logger.debug(f"Cache hit for store {store_id}")
            return self._cache[store_id].copy()

    def set(self, store_id: str, summary: Dict) -> None:
        """
        Cache a summary for a store.

        Args:
            store_id: Store ID
            summary: Summary data to cache
        """
        with self._lock:
            self._cache[store_id] = summary.copy()
            self._timestamps[store_id] = time.time()
            logger.debug(f"Cached summary for store {store_id}")

    def invalidate(self, store_id: str) -> None:
        """
        Invalidate cache for a specific store.

        Args:
            store_id: Store ID to invalidate
        """
        with self._lock:
            if store_id in self._cache:
                del self._cache[store_id]
                del self._timestamps[store_id]
                logger.debug(f"Cache invalidated for store {store_id}")

    def invalidate_all(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            logger.debug("All cache entries invalidated")

    def stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            now = time.time()
            active_entries = sum(
                1 for store_id in self._cache
                if now - self._timestamps.get(store_id, 0) <= self.default_ttl
            )
            return {
                "total_entries": len(self._cache),
                "active_entries": active_entries,
                "ttl_seconds": self.default_ttl
            }


# Global cache instance (persists across Lambda warm invocations)
_inventory_summary_cache = InventorySummaryCache(default_ttl=60)

# Product source types
PRODUCT_SOURCE_GLOBAL = 'global_catalog'
PRODUCT_SOURCE_CUSTOM = 'store_custom'

# Visibility types
VISIBILITY_STORE_ONLY = 'store_only'
VISIBILITY_GLOBAL = 'global'

# Promotion status types
PROMOTION_STATUS_NONE = 'none'
PROMOTION_STATUS_PENDING = 'pending_review'
PROMOTION_STATUS_APPROVED = 'approved'
PROMOTION_STATUS_REJECTED = 'rejected'
PROMOTION_STATUS_PROMOTED = 'promoted'


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
        # Check if we're in production
        self.is_production = settings.ENVIRONMENT.lower() == 'production'

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

            if self.is_production:
                # In production, fail loudly - don't silently fall back to mock mode
                logger.critical(
                    "CRITICAL: DynamoDB connection failed in PRODUCTION. "
                    "Service cannot operate without database connection. "
                    "Failing startup to prevent data inconsistency."
                )
                raise RuntimeError(
                    f"DynamoDB connection required in production but failed: {e}"
                )

            logger.warning(
                "Inventory service will use fallback mode. "
                "WARNING: This is NOT suitable for production use!"
            )
            self.use_mock = True
            self.dynamodb = None

    # ==================== PRE-COMPUTED STATS UPDATES ====================
    # These methods update the stats table atomically when inventory changes.
    # Pattern: Stripe-style running totals (update on write, not compute on read)

    async def _update_stats_on_product_add(
        self,
        store_id: str,
        selling_price: float,
        current_stock: int,
        min_stock_level: int
    ) -> None:
        """
        Update stats when a new product is added.

        Args:
            store_id: Store ID
            selling_price: Product selling price
            current_stock: Initial stock quantity
            min_stock_level: Minimum stock level threshold
        """
        try:
            stats_repo = get_stats_repository()
            stock_value = selling_price * current_stock

            # Determine stock status
            is_out_of_stock = current_stock == 0
            is_low_stock = 0 < current_stock <= min_stock_level

            await stats_repo.update_stats_atomic(
                store_id=store_id,
                delta_total_products=1,
                delta_active_products=1,
                delta_stock_value=stock_value,
                delta_out_of_stock=1 if is_out_of_stock else 0,
                delta_low_stock=1 if is_low_stock else 0
            )
            logger.debug(f"Stats updated for product add in store {store_id}")

        except Exception as e:
            # Log but don't fail the main operation - stats can be reconciled later
            logger.error(f"Error updating stats on product add: {e}")

    async def _update_stats_on_product_delete(
        self,
        store_id: str,
        product: Dict,
        hard_delete: bool
    ) -> None:
        """
        Update stats when a product is deleted.

        Args:
            store_id: Store ID
            product: Product being deleted (to get price/stock info)
            hard_delete: True if permanently deleted, False if soft deleted
        """
        try:
            stats_repo = get_stats_repository()
            selling_price = float(product.get('selling_price', 0))
            current_stock = int(product.get('current_stock', 0))
            min_stock_level = int(product.get('min_stock_level', 10))
            was_active = product.get('is_active', True)

            if not was_active:
                # Product was already archived, nothing to update for active stats
                if hard_delete:
                    # Just decrement total and archived counts
                    await stats_repo.update_stats_atomic(
                        store_id=store_id,
                        delta_total_products=-1,
                        delta_archived_products=-1
                    )
                return

            stock_value = selling_price * current_stock
            is_out_of_stock = current_stock == 0
            is_low_stock = 0 < current_stock <= min_stock_level

            if hard_delete:
                # Permanently deleted - remove from all counts
                await stats_repo.update_stats_atomic(
                    store_id=store_id,
                    delta_total_products=-1,
                    delta_active_products=-1,
                    delta_stock_value=-stock_value,
                    delta_out_of_stock=-1 if is_out_of_stock else 0,
                    delta_low_stock=-1 if is_low_stock else 0
                )
            else:
                # Soft deleted (archived) - move from active to archived
                await stats_repo.update_stats_atomic(
                    store_id=store_id,
                    delta_active_products=-1,
                    delta_archived_products=1,
                    delta_stock_value=-stock_value,
                    delta_out_of_stock=-1 if is_out_of_stock else 0,
                    delta_low_stock=-1 if is_low_stock else 0
                )

            logger.debug(f"Stats updated for product delete in store {store_id}")

        except Exception as e:
            logger.error(f"Error updating stats on product delete: {e}")

    async def _update_stats_on_archive_toggle(
        self,
        store_id: str,
        product: Dict,
        new_is_active: bool
    ) -> None:
        """
        Update stats when a product is archived or unarchived.

        Args:
            store_id: Store ID
            product: Product being toggled
            new_is_active: New active status (True = unarchived, False = archived)
        """
        try:
            stats_repo = get_stats_repository()
            selling_price = float(product.get('selling_price', 0))
            current_stock = int(product.get('current_stock', 0))
            min_stock_level = int(product.get('min_stock_level', 10))

            stock_value = selling_price * current_stock
            is_out_of_stock = current_stock == 0
            is_low_stock = 0 < current_stock <= min_stock_level

            if new_is_active:
                # Unarchiving - move from archived to active
                await stats_repo.update_stats_atomic(
                    store_id=store_id,
                    delta_active_products=1,
                    delta_archived_products=-1,
                    delta_stock_value=stock_value,
                    delta_out_of_stock=1 if is_out_of_stock else 0,
                    delta_low_stock=1 if is_low_stock else 0
                )
            else:
                # Archiving - move from active to archived
                await stats_repo.update_stats_atomic(
                    store_id=store_id,
                    delta_active_products=-1,
                    delta_archived_products=1,
                    delta_stock_value=-stock_value,
                    delta_out_of_stock=-1 if is_out_of_stock else 0,
                    delta_low_stock=-1 if is_low_stock else 0
                )

            logger.debug(f"Stats updated for archive toggle in store {store_id}")

        except Exception as e:
            logger.error(f"Error updating stats on archive toggle: {e}")

    async def _update_stats_on_stock_change(
        self,
        store_id: str,
        product: Dict,
        previous_stock: int,
        new_stock: int
    ) -> None:
        """
        Update stats when stock quantity changes.

        Args:
            store_id: Store ID
            product: Product with updated stock
            previous_stock: Stock before change
            new_stock: Stock after change
        """
        try:
            stats_repo = get_stats_repository()
            selling_price = float(product.get('selling_price', 0))
            min_stock_level = int(product.get('min_stock_level', 10))
            is_active = product.get('is_active', True)

            # Only update stats for active products
            if not is_active:
                return

            # Calculate stock value delta
            stock_value_delta = selling_price * (new_stock - previous_stock)

            # Determine changes in stock status counts
            was_out_of_stock = previous_stock == 0
            is_out_of_stock = new_stock == 0
            was_low_stock = 0 < previous_stock <= min_stock_level
            is_low_stock = 0 < new_stock <= min_stock_level

            delta_out_of_stock = 0
            if was_out_of_stock and not is_out_of_stock:
                delta_out_of_stock = -1  # No longer out of stock
            elif not was_out_of_stock and is_out_of_stock:
                delta_out_of_stock = 1  # Now out of stock

            delta_low_stock = 0
            if was_low_stock and not is_low_stock:
                delta_low_stock = -1  # No longer low stock
            elif not was_low_stock and is_low_stock:
                delta_low_stock = 1  # Now low stock

            await stats_repo.update_stats_atomic(
                store_id=store_id,
                delta_stock_value=stock_value_delta,
                delta_out_of_stock=delta_out_of_stock,
                delta_low_stock=delta_low_stock
            )

            logger.debug(f"Stats updated for stock change in store {store_id}: "
                        f"{previous_stock} -> {new_stock}")

        except Exception as e:
            logger.error(f"Error updating stats on stock change: {e}")

    async def get_products(self, store_id: str, category: str = None,
                          status: str = None, search: str = None,
                          page: int = 1, limit: int = 50,
                          include_inactive: bool = False) -> Dict:
        """
        Get products for a store with filtering and pagination

        Args:
            store_id: Store ID to get inventory for
            category: Filter by category
            status: Filter by status ('active', 'inactive', 'archived', 'all')
            search: Search term for product name
            page: Page number (1-indexed)
            limit: Items per page
            include_inactive: If True, include soft-deleted/archived products
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
                # By default, filter out soft-deleted products (is_active=False)
                # unless include_inactive is True or status explicitly requests them
                product_is_active = product.get('is_active', True)

                if status == 'all':
                    # Show all products regardless of is_active
                    pass
                elif status == 'archived' or status == 'inactive':
                    # Only show archived/inactive products
                    if product_is_active:
                        continue
                elif status == 'active':
                    # Only show active products
                    if not product_is_active:
                        continue
                else:
                    # Default behavior: only show active products unless include_inactive
                    if not include_inactive and not product_is_active:
                        continue

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
                          quantity_change: int, reason: str = None,
                          max_retries: int = 3) -> Dict:
        """
        Update product stock with atomic conditional updates (RACE CONDITION SAFE)

        Uses DynamoDB conditional expressions to ensure atomic updates.
        Prevents overselling by validating stock availability atomically.

        Args:
            store_id: Store ID
            product_id: Product ID
            quantity_change: Positive for addition, negative for reduction
            reason: Reason for stock change
            max_retries: Maximum retry attempts for conditional check failures

        Returns:
            Dict with success status and stock details
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - no stock updates"}

        for attempt in range(max_retries):
            try:
                # For stock reduction, use atomic conditional update
                if quantity_change < 0:
                    required_stock = abs(quantity_change)

                    # Atomic update with condition: current_stock >= required amount
                    # This prevents race conditions and overselling
                    try:
                        response = await asyncio.to_thread(
                            self.store_inventory_table.update_item,
                            Key={'store_id': store_id, 'product_id': product_id},
                            UpdateExpression='SET current_stock = current_stock + :change, updated_at = :updated_at',
                            ConditionExpression='attribute_exists(product_id) AND current_stock >= :required',
                            ExpressionAttributeValues={
                                ':change': quantity_change,  # Negative value
                                ':required': required_stock,
                                ':updated_at': datetime.utcnow().isoformat()
                            },
                            ReturnValues='ALL_NEW'
                        )

                        updated_product = response.get('Attributes', {})
                        new_stock = int(updated_product.get('current_stock', 0))
                        previous_stock = new_stock - quantity_change  # Calculate previous

                        logger.info(
                            f"Stock updated (atomic): {product_id} in {store_id} | "
                            f"{previous_stock} → {new_stock} ({quantity_change:+d}) | "
                            f"Reason: {reason or 'Not specified'}"
                        )

                        # Invalidate cache after stock change
                        self.invalidate_summary_cache(store_id)

                        # Update pre-computed stats
                        await self._update_stats_on_stock_change(
                            store_id=store_id,
                            product=updated_product,
                            previous_stock=previous_stock,
                            new_stock=new_stock
                        )

                        return {
                            "success": True,
                            "previous_stock": previous_stock,
                            "new_stock": new_stock,
                            "change": quantity_change,
                            "product": decimal_to_float(updated_product),
                            "atomic": True
                        }

                    except ClientError as e:
                        error_code = e.response['Error']['Code']

                        if error_code == 'ConditionalCheckFailedException':
                            # Stock insufficient or product doesn't exist
                            # Get current stock to provide useful error info
                            current_product = await self.get_product(store_id, product_id)
                            if not current_product:
                                return {"success": False, "error": "Product not found"}

                            current_stock = int(current_product.get('current_stock', 0))
                            logger.warning(
                                f"Insufficient stock for {product_id}: "
                                f"available={current_stock}, required={required_stock}"
                            )
                            return {
                                "success": False,
                                "error": "Insufficient stock",
                                "current_stock": current_stock,
                                "requested_change": quantity_change,
                                "required": required_stock
                            }
                        raise  # Re-raise other errors

                else:
                    # For stock addition, use atomic increment (no condition needed)
                    response = await asyncio.to_thread(
                        self.store_inventory_table.update_item,
                        Key={'store_id': store_id, 'product_id': product_id},
                        UpdateExpression='SET current_stock = if_not_exists(current_stock, :zero) + :change, updated_at = :updated_at',
                        ExpressionAttributeValues={
                            ':change': quantity_change,
                            ':zero': 0,
                            ':updated_at': datetime.utcnow().isoformat()
                        },
                        ReturnValues='ALL_NEW'
                    )

                    updated_product = response.get('Attributes', {})
                    new_stock = int(updated_product.get('current_stock', 0))
                    previous_stock = new_stock - quantity_change

                    logger.info(
                        f"Stock updated (atomic add): {product_id} in {store_id} | "
                        f"{previous_stock} → {new_stock} ({quantity_change:+d}) | "
                        f"Reason: {reason or 'Not specified'}"
                    )

                    # Invalidate cache after stock change
                    self.invalidate_summary_cache(store_id)

                    # Update pre-computed stats
                    await self._update_stats_on_stock_change(
                        store_id=store_id,
                        product=updated_product,
                        previous_stock=previous_stock,
                        new_stock=new_stock
                    )

                    return {
                        "success": True,
                        "previous_stock": previous_stock,
                        "new_stock": new_stock,
                        "change": quantity_change,
                        "product": decimal_to_float(updated_product),
                        "atomic": True
                    }

            except ClientError as e:
                error_code = e.response['Error']['Code']

                # Retry on throughput exceeded
                if error_code == 'ProvisionedThroughputExceededException' and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.1  # Exponential backoff
                    logger.warning(f"DynamoDB throughput exceeded, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                logger.error(f"DynamoDB error updating stock: {error_code} - {e}")
                return {"success": False, "error": f"Database error: {error_code}"}

            except Exception as e:
                logger.error(f"Error updating stock: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Max retries exceeded"}

    async def update_stock_bulk_transactional(
        self, store_id: str,
        items: List[Dict[str, Any]],
        reason: str = None
    ) -> Dict:
        """
        Update stock for multiple items in a single atomic transaction.

        Uses DynamoDB TransactWriteItems to ensure ALL updates succeed or
        ALL fail together. This prevents partial order fulfillment issues.

        Args:
            store_id: Store ID
            items: List of dicts with 'product_id' and 'quantity_change'
            reason: Reason for stock changes

        Returns:
            Dict with success status and details for each item

        Example:
            await update_stock_bulk_transactional(
                store_id="STORE-001",
                items=[
                    {"product_id": "PROD-001", "quantity_change": -2},
                    {"product_id": "PROD-002", "quantity_change": -1}
                ],
                reason="Order ORD-12345"
            )
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - no stock updates"}

        if not items:
            return {"success": True, "items": [], "message": "No items to update"}

        # DynamoDB transactions support max 100 items
        if len(items) > 100:
            return {"success": False, "error": "Maximum 100 items per transaction"}

        try:
            # Build transact items
            transact_items = []

            for item in items:
                product_id = item.get('product_id')
                quantity_change = item.get('quantity_change', 0)

                if not product_id:
                    return {"success": False, "error": f"Missing product_id in item: {item}"}

                if quantity_change < 0:
                    # Stock reduction with condition
                    required_stock = abs(quantity_change)
                    transact_items.append({
                        'Update': {
                            'TableName': self.store_inventory_table.table_name,
                            'Key': {
                                'store_id': {'S': store_id},
                                'product_id': {'S': product_id}
                            },
                            'UpdateExpression': 'SET current_stock = current_stock + :change, updated_at = :updated_at',
                            'ConditionExpression': 'attribute_exists(product_id) AND current_stock >= :required',
                            'ExpressionAttributeValues': {
                                ':change': {'N': str(quantity_change)},
                                ':required': {'N': str(required_stock)},
                                ':updated_at': {'S': datetime.utcnow().isoformat()}
                            }
                        }
                    })
                else:
                    # Stock addition (no condition)
                    transact_items.append({
                        'Update': {
                            'TableName': self.store_inventory_table.table_name,
                            'Key': {
                                'store_id': {'S': store_id},
                                'product_id': {'S': product_id}
                            },
                            'UpdateExpression': 'SET current_stock = if_not_exists(current_stock, :zero) + :change, updated_at = :updated_at',
                            'ExpressionAttributeValues': {
                                ':change': {'N': str(quantity_change)},
                                ':zero': {'N': '0'},
                                ':updated_at': {'S': datetime.utcnow().isoformat()}
                            }
                        }
                    })

            # Execute transaction
            # Use boto3.client directly instead of dynamodb.meta.client
            # to avoid serialization issues with transact_write_items
            import boto3
            client = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'ap-south-1'))
            await asyncio.to_thread(
                client.transact_write_items,
                TransactItems=transact_items
            )

            logger.info(
                f"Bulk stock update (transactional): {len(items)} items in {store_id} | "
                f"Reason: {reason or 'Not specified'}"
            )

            # Invalidate cache after bulk stock change
            self.invalidate_summary_cache(store_id)

            return {
                "success": True,
                "items_updated": len(items),
                "store_id": store_id,
                "reason": reason,
                "transactional": True
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']

            if error_code == 'TransactionCanceledException':
                # Transaction failed - find which item(s) caused the failure
                cancellation_reasons = e.response.get('CancellationReasons', [])
                failed_items = []

                for i, reason_obj in enumerate(cancellation_reasons):
                    if reason_obj.get('Code') == 'ConditionalCheckFailed':
                        item = items[i] if i < len(items) else {}
                        failed_items.append({
                            "product_id": item.get('product_id'),
                            "reason": "Insufficient stock"
                        })
                    elif reason_obj.get('Code') != 'None':
                        item = items[i] if i < len(items) else {}
                        failed_items.append({
                            "product_id": item.get('product_id'),
                            "reason": reason_obj.get('Code', 'Unknown')
                        })

                logger.warning(
                    f"Bulk stock update transaction cancelled: {failed_items}"
                )

                return {
                    "success": False,
                    "error": "Transaction cancelled - insufficient stock",
                    "failed_items": failed_items
                }

            logger.error(f"DynamoDB transaction error: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}

        except Exception as e:
            logger.error(f"Error in bulk stock update: {e}")
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

    async def get_inventory_summary(self, store_id: str, skip_cache: bool = False) -> Dict:
        """
        Get inventory summary statistics for a store.

        Uses in-memory caching with 60s TTL to reduce DynamoDB queries.
        Cache persists across Lambda warm invocations for better performance.

        Args:
            store_id: Store ID
            skip_cache: If True, bypass cache and fetch fresh data

        Returns:
            Dict with inventory summary statistics
        """
        if self.use_mock:
            return self._get_mock_summary()

        # Try cache first (unless skip_cache is True)
        if not skip_cache:
            cached_summary = _inventory_summary_cache.get(store_id)
            if cached_summary:
                logger.info(f"Returning cached inventory summary for store {store_id}")
                return cached_summary

        try:
            # Query all products for store
            response = await asyncio.to_thread(
                self.store_inventory_table.query,
                KeyConditionExpression=Key('store_id').eq(store_id)
            )

            products = response.get('Items', [])

            # Filter to only active products for all metrics
            active_products_list = [p for p in products if p.get('is_active', True)]

            total_products = len(active_products_list)
            active_products = total_products  # All counted products are active
            out_of_stock = sum(1 for p in active_products_list if int(p.get('current_stock', 0)) == 0)
            low_stock = sum(
                1 for p in active_products_list
                if 0 < int(p.get('current_stock', 0)) <= int(p.get('min_stock_level', 10))
            )

            # Calculate total inventory value (only for active products)
            total_value = sum(
                int(p.get('current_stock', 0)) * float(p.get('selling_price', 0))
                for p in active_products_list
            )

            # Count archived products separately
            archived_count = len(products) - total_products

            summary = {
                "total_products": total_products,
                "active_products": active_products,
                "archived_products": archived_count,
                "out_of_stock": out_of_stock,
                "low_stock": low_stock,
                "total_stock_value": round(total_value, 2)
            }

            # Cache the result
            _inventory_summary_cache.set(store_id, summary)
            logger.info(f"Fetched and cached inventory summary for store {store_id}")

            return summary

        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return self._get_mock_summary()

    def invalidate_summary_cache(self, store_id: str) -> None:
        """
        Invalidate the cached inventory summary for a store.

        Call this after stock updates to ensure fresh data on next request.

        Args:
            store_id: Store ID to invalidate
        """
        _inventory_summary_cache.invalidate(store_id)

    def get_cache_stats(self) -> Dict:
        """Get cache statistics for monitoring."""
        return _inventory_summary_cache.stats()

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

    # ==================== CUSTOM PRODUCT MANAGEMENT ====================

    def _generate_custom_product_id(self) -> str:
        """Generate a unique product ID for custom products"""
        # Format: CUST_{timestamp}_{random} for easy identification
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:8].upper()
        return f"CUST_{timestamp}_{random_suffix}"

    def _generate_sku(self, product_name: str, store_id: str) -> str:
        """Generate a SKU for custom product"""
        # Format: SKU-{first 3 chars of name}-{store suffix}-{random}
        name_prefix = ''.join(c for c in product_name[:3].upper() if c.isalnum()) or 'PRD'
        store_suffix = store_id[-4:] if len(store_id) >= 4 else store_id
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"SKU-{name_prefix}-{store_suffix}-{random_suffix}"

    async def create_custom_product(
        self,
        store_id: str,
        user_id: str,
        product_data: Dict[str, Any]
    ) -> Dict:
        """
        Create a store-specific custom product.

        Custom products are:
        - Only visible to the store that created them
        - Can be promoted to global catalog by admin
        - Have product_source='store_custom'

        Args:
            store_id: Store ID creating the product
            user_id: User ID of the store owner
            product_data: Product details (name, price, stock, etc.)

        Returns:
            Dict with success status and created product
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot create products"}

        try:
            # Generate unique product ID
            product_id = self._generate_custom_product_id()

            # Generate SKU if not provided
            sku = product_data.get('sku')
            if not sku:
                sku = self._generate_sku(product_data.get('product_name', 'Product'), store_id)

            # Build the product item
            now = datetime.utcnow().isoformat()

            product_item = {
                # Keys
                'store_id': store_id,
                'product_id': product_id,

                # Custom product metadata
                'product_source': PRODUCT_SOURCE_CUSTOM,
                'source_store_id': store_id,
                'visibility': VISIBILITY_STORE_ONLY,
                'promotion_status': PROMOTION_STATUS_NONE,
                'created_by_user_id': user_id,

                # Product details
                'product_name': product_data.get('product_name'),
                'brand': product_data.get('brand', ''),
                'category': product_data.get('category', 'Uncategorized'),
                'subcategory': product_data.get('subcategory', ''),
                'description': product_data.get('description', ''),
                'sku': sku,
                'barcode': product_data.get('barcode', ''),

                # Pricing
                'selling_price': Decimal(str(product_data.get('selling_price', 0))),
                'cost_price': Decimal(str(product_data.get('cost_price', 0))),
                'mrp': Decimal(str(product_data.get('mrp', 0))),
                'tax_rate': Decimal(str(product_data.get('tax_rate', 18))),
                'discount_percentage': Decimal(str(product_data.get('discount_percentage', 0))),

                # GST fields
                'hsn_code': product_data.get('hsn_code', ''),
                'gst_rate': Decimal(str(product_data.get('gst_rate', 18))),
                'cess_rate': Decimal(str(product_data.get('cess_rate', 0))),
                'is_gst_exempt': product_data.get('is_gst_exempt', False),
                'gst_category': product_data.get('gst_category', ''),

                # Inventory
                'current_stock': int(product_data.get('current_stock', 0)),
                'min_stock_level': int(product_data.get('min_stock_level', 10)),
                'max_stock_level': int(product_data.get('max_stock_level', 1000)),
                'unit': product_data.get('unit', 'piece'),

                # Flags
                'is_active': True,
                'is_returnable': product_data.get('is_returnable', True),
                'is_perishable': product_data.get('is_perishable', False),

                # Image (if provided)
                'image': product_data.get('image', ''),
                'image_urls': product_data.get('image_urls', {}),

                # Timestamps
                'created_at': now,
                'updated_at': now,
            }

            # Remove empty string values to keep DynamoDB clean
            product_item = {k: v for k, v in product_item.items()
                          if v is not None and v != '' and v != {}}

            # Ensure required fields are present
            if not product_item.get('product_name'):
                return {"success": False, "error": "Product name is required"}
            if not product_item.get('selling_price') or product_item['selling_price'] <= 0:
                return {"success": False, "error": "Valid selling price is required"}

            # Create the product in DynamoDB
            await asyncio.to_thread(
                self.store_inventory_table.put_item,
                Item=product_item,
                ConditionExpression='attribute_not_exists(product_id)'
            )

            logger.info(
                f"Custom product created: {product_id} in store {store_id} | "
                f"Name: {product_item['product_name']} | Created by: {user_id}"
            )

            # Invalidate cache after creating new product
            self.invalidate_summary_cache(store_id)

            # Update pre-computed stats (async, non-blocking for main operation)
            await self._update_stats_on_product_add(
                store_id=store_id,
                selling_price=float(product_item.get('selling_price', 0)),
                current_stock=int(product_item.get('current_stock', 0)),
                min_stock_level=int(product_item.get('min_stock_level', 10))
            )

            return {
                "success": True,
                "product_id": product_id,
                "sku": sku,
                "product": decimal_to_float(product_item),
                "message": "Custom product created successfully"
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ConditionalCheckFailedException':
                return {"success": False, "error": "Product ID collision - please retry"}
            logger.error(f"DynamoDB error creating custom product: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error creating custom product: {e}")
            return {"success": False, "error": str(e)}

    async def update_custom_product(
        self,
        store_id: str,
        product_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Dict:
        """
        Update a store-specific custom product.

        Only the store that created the product can update it.
        Products pending promotion cannot be updated.

        Args:
            store_id: Store ID
            product_id: Product ID to update
            user_id: User making the update
            updates: Fields to update

        Returns:
            Dict with success status and updated product
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot update products"}

        try:
            # First, verify the product exists in this store's inventory
            existing_product = await self.get_product(store_id, product_id)

            if not existing_product:
                return {"success": False, "error": "Product not found"}

            is_custom_product = existing_product.get('product_source') == PRODUCT_SOURCE_CUSTOM

            # For custom products, verify ownership
            if is_custom_product and existing_product.get('source_store_id') != store_id:
                return {"success": False, "error": "Not authorized to update this product"}

            if existing_product.get('promotion_status') == PROMOTION_STATUS_PENDING:
                return {"success": False, "error": "Cannot update product pending promotion review"}

            # Build update expression
            update_parts = []
            expression_values = {}
            expression_names = {}

            # Store-specific fields (can be updated for ANY product in store inventory)
            store_specific_fields = {
                'selling_price', 'cost_price', 'mrp', 'tax_rate',
                'discount_percentage', 'current_stock', 'min_stock_level',
                'max_stock_level', 'is_active', 'is_returnable',
                'is_perishable', 'location',
                # GST fields
                'hsn_code', 'gst_rate', 'cess_rate', 'is_gst_exempt', 'gst_category'
            }

            # Product detail fields (can ONLY be updated for custom products)
            product_detail_fields = {
                'product_name', 'brand', 'brand_name', 'category', 'subcategory',
                'description', 'barcode', 'sku', 'unit', 'image', 'image_urls',
                'size', 'size_unit', 'variant_type'
            }

            # Determine allowed fields based on product type
            if is_custom_product:
                allowed_fields = store_specific_fields | product_detail_fields
            else:
                # Global catalog products: only store-specific fields
                allowed_fields = store_specific_fields

            for field, value in updates.items():
                if field not in allowed_fields:
                    continue

                # Convert numeric fields to Decimal
                if field in {'selling_price', 'cost_price', 'mrp', 'tax_rate', 'discount_percentage',
                             'gst_rate', 'cess_rate'}:
                    value = Decimal(str(value)) if value is not None else Decimal('0')
                elif field in {'current_stock', 'min_stock_level', 'max_stock_level'}:
                    value = int(value) if value is not None else 0

                attr_name = f"#{field}"
                attr_value = f":{field}"
                update_parts.append(f"{attr_name} = {attr_value}")
                expression_names[attr_name] = field
                expression_values[attr_value] = value

            if not update_parts:
                return {"success": False, "error": "No valid fields to update"}

            # Add updated_at timestamp
            update_parts.append("#updated_at = :updated_at")
            expression_names["#updated_at"] = "updated_at"
            expression_values[":updated_at"] = datetime.utcnow().isoformat()

            update_expression = "SET " + ", ".join(update_parts)

            response = await asyncio.to_thread(
                self.store_inventory_table.update_item,
                Key={'store_id': store_id, 'product_id': product_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
                ReturnValues='ALL_NEW'
            )

            updated_product = response.get('Attributes', {})

            logger.info(
                f"Custom product updated: {product_id} in store {store_id} | "
                f"Updated by: {user_id} | Fields: {list(updates.keys())}"
            )

            # Invalidate cache if stock or price changed (affects summary)
            stock_or_price_fields = {'current_stock', 'selling_price', 'is_active'}
            if stock_or_price_fields & set(updates.keys()):
                self.invalidate_summary_cache(store_id)

            return {
                "success": True,
                "product": decimal_to_float(updated_product),
                "message": "Product updated successfully"
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error updating custom product: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error updating custom product: {e}")
            return {"success": False, "error": str(e)}

    async def delete_custom_product(
        self,
        store_id: str,
        product_id: str,
        user_id: str,
        hard_delete: bool = False
    ) -> Dict:
        """
        Delete (or soft-delete) a product from store inventory.

        By default, performs soft delete (sets is_active=False).
        Hard delete removes the item completely (only for custom products).

        Works for both custom products and products added from global catalog.
        Global catalog products can only be soft-deleted (removed from store inventory view).

        Args:
            store_id: Store ID
            product_id: Product ID to delete
            user_id: User making the deletion
            hard_delete: If True, permanently removes the product (custom products only)

        Returns:
            Dict with success status
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot delete products"}

        try:
            # Verify the product exists in this store's inventory
            existing_product = await self.get_product(store_id, product_id)

            if not existing_product:
                return {"success": False, "error": "Product not found"}

            is_custom = existing_product.get('product_source') == PRODUCT_SOURCE_CUSTOM

            # For custom products, verify ownership
            if is_custom and existing_product.get('source_store_id') != store_id:
                return {"success": False, "error": "Not authorized to delete this product"}

            # Hard delete only allowed for custom products
            if hard_delete and not is_custom:
                return {"success": False, "error": "Cannot hard delete global catalog products. Use soft delete instead."}

            if hard_delete:
                # Permanently delete the product
                await asyncio.to_thread(
                    self.store_inventory_table.delete_item,
                    Key={'store_id': store_id, 'product_id': product_id}
                )

                logger.info(
                    f"Custom product hard deleted: {product_id} from store {store_id} | "
                    f"Deleted by: {user_id}"
                )

                # Invalidate cache after product deletion
                self.invalidate_summary_cache(store_id)

                # Update pre-computed stats
                await self._update_stats_on_product_delete(
                    store_id=store_id,
                    product=existing_product,
                    hard_delete=True
                )

                return {
                    "success": True,
                    "message": "Product permanently deleted",
                    "hard_delete": True
                }
            else:
                # Soft delete - set is_active to False
                await asyncio.to_thread(
                    self.store_inventory_table.update_item,
                    Key={'store_id': store_id, 'product_id': product_id},
                    UpdateExpression='SET is_active = :inactive, updated_at = :updated_at, deleted_by = :user_id',
                    ExpressionAttributeValues={
                        ':inactive': False,
                        ':updated_at': datetime.utcnow().isoformat(),
                        ':user_id': user_id
                    }
                )

                logger.info(
                    f"Custom product soft deleted: {product_id} from store {store_id} | "
                    f"Deleted by: {user_id}"
                )

                # Invalidate cache after product deactivation
                self.invalidate_summary_cache(store_id)

                # Update pre-computed stats (soft delete = archive)
                await self._update_stats_on_product_delete(
                    store_id=store_id,
                    product=existing_product,
                    hard_delete=False
                )

                return {
                    "success": True,
                    "message": "Product deactivated (soft deleted)",
                    "hard_delete": False
                }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error deleting custom product: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error deleting custom product: {e}")
            return {"success": False, "error": str(e)}

    async def duplicate_product(
        self,
        store_id: str,
        product_id: str,
        user_id: str
    ) -> Dict:
        """
        Duplicate a product in the store's inventory.

        Creates a copy of the product with:
        - New unique product ID
        - "(Copy)" suffix added to product name
        - Stock reset to 0

        Works for both custom products and products added from global catalog.

        Args:
            store_id: Store ID
            product_id: Product ID to duplicate
            user_id: User making the duplication

        Returns:
            Dict with success status and new product details
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot duplicate products"}

        try:
            # Get the source product
            source_product = await self.get_product(store_id, product_id)

            if not source_product:
                return {"success": False, "error": "Product not found"}

            # Generate new product ID
            new_product_id = self._generate_custom_product_id()
            now = datetime.utcnow().isoformat()

            # Create the duplicate product
            duplicate_item = dict(source_product)

            # Update keys and metadata for the duplicate
            duplicate_item['store_id'] = store_id
            duplicate_item['product_id'] = new_product_id

            # Add "(Copy)" to the name
            original_name = duplicate_item.get('product_name', duplicate_item.get('name', 'Product'))
            duplicate_item['product_name'] = f"{original_name} (Copy)"

            # Reset stock to 0 - user should set initial stock
            duplicate_item['current_stock'] = 0

            # Mark as custom product (duplicates are always store-specific)
            duplicate_item['product_source'] = PRODUCT_SOURCE_CUSTOM
            duplicate_item['source_store_id'] = store_id
            duplicate_item['visibility'] = VISIBILITY_STORE_ONLY
            duplicate_item['promotion_status'] = PROMOTION_STATUS_NONE

            # Update timestamps and creator
            duplicate_item['created_at'] = now
            duplicate_item['updated_at'] = now
            duplicate_item['created_by_user_id'] = user_id
            duplicate_item['duplicated_from'] = product_id

            # Generate new SKU
            duplicate_item['sku'] = self._generate_sku(
                duplicate_item.get('product_name', 'Product'),
                store_id
            )

            # Remove global_data if present (it's for display only)
            duplicate_item.pop('global_data', None)

            # Convert numeric fields to Decimal for DynamoDB
            for field in ['selling_price', 'cost_price', 'mrp', 'tax_rate', 'discount_percentage',
                         'gst_rate', 'cess_rate']:
                if field in duplicate_item and duplicate_item[field] is not None:
                    duplicate_item[field] = Decimal(str(duplicate_item[field]))

            for field in ['current_stock', 'min_stock_level', 'max_stock_level']:
                if field in duplicate_item and duplicate_item[field] is not None:
                    duplicate_item[field] = int(duplicate_item[field])

            # Remove empty string values
            duplicate_item = {k: v for k, v in duplicate_item.items()
                           if v is not None and v != '' and v != {}}

            # Save the duplicate to DynamoDB
            await asyncio.to_thread(
                self.store_inventory_table.put_item,
                Item=duplicate_item
            )

            logger.info(
                f"Product duplicated: {product_id} -> {new_product_id} in store {store_id} | "
                f"Duplicated by: {user_id}"
            )

            # Invalidate cache after creating new product
            self.invalidate_summary_cache(store_id)

            # Update pre-computed stats (duplicated product is a new product)
            await self._update_stats_on_product_add(
                store_id=store_id,
                selling_price=float(duplicate_item.get('selling_price', 0)),
                current_stock=int(duplicate_item.get('current_stock', 0)),
                min_stock_level=int(duplicate_item.get('min_stock_level', 10))
            )

            return {
                "success": True,
                "new_product_id": new_product_id,
                "product": decimal_to_float(duplicate_item),
                "message": "Product duplicated successfully"
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error duplicating product: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error duplicating product: {e}")
            return {"success": False, "error": str(e)}

    async def archive_product(
        self,
        store_id: str,
        product_id: str,
        user_id: str
    ) -> Dict:
        """
        Toggle archive status of a product in the store's inventory.

        If product is active (is_active=True), it will be archived (is_active=False).
        If product is archived (is_active=False), it will be unarchived (is_active=True).

        Works for both custom products and products added from global catalog.

        Args:
            store_id: Store ID
            product_id: Product ID to archive/unarchive
            user_id: User making the change

        Returns:
            Dict with success status and new is_active state
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot archive products"}

        try:
            # Get the product
            existing_product = await self.get_product(store_id, product_id)

            if not existing_product:
                return {"success": False, "error": "Product not found"}

            # Toggle the is_active status
            current_status = existing_product.get('is_active', True)
            new_status = not current_status
            now = datetime.utcnow().isoformat()

            # Update the product
            await asyncio.to_thread(
                self.store_inventory_table.update_item,
                Key={'store_id': store_id, 'product_id': product_id},
                UpdateExpression='SET is_active = :status, updated_at = :updated_at, archived_by = :user_id',
                ExpressionAttributeValues={
                    ':status': new_status,
                    ':updated_at': now,
                    ':user_id': user_id
                }
            )

            action = 'unarchived' if new_status else 'archived'
            logger.info(
                f"Product {action}: {product_id} in store {store_id} | "
                f"Changed by: {user_id}"
            )

            # Invalidate cache after status change
            self.invalidate_summary_cache(store_id)

            # Update pre-computed stats
            await self._update_stats_on_archive_toggle(
                store_id=store_id,
                product=existing_product,
                new_is_active=new_status
            )

            return {
                "success": True,
                "is_active": new_status,
                "status": "active" if new_status else "archived",
                "message": f"Product {action} successfully"
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error archiving product: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error archiving product: {e}")
            return {"success": False, "error": str(e)}

    def filter_visible_products(
        self,
        products: List[Dict],
        requesting_store_id: str,
        user_type: str = 'store_owner'
    ) -> List[Dict]:
        """
        Filter products based on visibility rules.

        Visibility Rules:
        - Global catalog products: Visible to all
        - Store custom products: Only visible to the source store
        - Admin can see all products

        Args:
            products: List of products to filter
            requesting_store_id: Store ID making the request
            user_type: 'store_owner', 'customer', or 'admin'

        Returns:
            Filtered list of products
        """
        if user_type == 'admin':
            # Admin can see all products
            return products

        visible_products = []
        for product in products:
            product_source = product.get('product_source', PRODUCT_SOURCE_GLOBAL)
            source_store_id = product.get('source_store_id')

            # Global catalog products are always visible
            if product_source == PRODUCT_SOURCE_GLOBAL:
                visible_products.append(product)
            # Custom products only visible to source store
            elif product_source == PRODUCT_SOURCE_CUSTOM:
                if source_store_id == requesting_store_id:
                    visible_products.append(product)
                # else: not visible - skip

        return visible_products

    # ==================== PROMOTION WORKFLOW ====================

    def _calculate_quality_score(self, product: Dict) -> Dict:
        """
        Calculate quality score for promotion eligibility.

        Returns dict with score, checks, and eligibility status.
        """
        checks = {
            'has_name': bool(product.get('product_name')),
            'has_description': len(product.get('description', '')) >= 20,
            'has_category': bool(product.get('category')) and product.get('category') != 'Uncategorized',
            'has_price': float(product.get('selling_price', 0)) > 0,
            'has_image': bool(product.get('image') or product.get('image_urls')),
            'has_barcode': bool(product.get('barcode')),
            'has_brand': bool(product.get('brand')),
            'has_unit': bool(product.get('unit')),
        }

        score = sum(checks.values()) / len(checks) * 100
        eligible = score >= 60  # 60% threshold for promotion

        return {
            'score': round(score, 1),
            'checks': checks,
            'eligible': eligible,
            'missing': [k.replace('has_', '') for k, v in checks.items() if not v]
        }

    async def request_promotion(
        self,
        store_id: str,
        product_id: str,
        user_id: str
    ) -> Dict:
        """
        Request promotion of a custom product to the global catalog.

        Requirements:
        - Product must be a custom product
        - Product must belong to the requesting store
        - Product must not already be pending promotion
        - Product must meet minimum quality criteria

        Args:
            store_id: Store ID
            product_id: Product ID to promote
            user_id: User making the request

        Returns:
            Dict with success status and quality check results
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot request promotion"}

        try:
            # Get the product
            product = await self.get_product(store_id, product_id)

            if not product:
                return {"success": False, "error": "Product not found"}

            # Validate it's a custom product from this store
            if product.get('product_source') != PRODUCT_SOURCE_CUSTOM:
                return {"success": False, "error": "Only custom products can be promoted"}

            if product.get('source_store_id') != store_id:
                return {"success": False, "error": "Not authorized to promote this product"}

            # Check if already pending or promoted
            current_status = product.get('promotion_status', PROMOTION_STATUS_NONE)
            if current_status == PROMOTION_STATUS_PENDING:
                return {"success": False, "error": "Product is already pending promotion review"}
            if current_status == PROMOTION_STATUS_PROMOTED:
                return {"success": False, "error": "Product has already been promoted to global catalog"}

            # Calculate quality score
            quality_result = self._calculate_quality_score(product)

            if not quality_result['eligible']:
                return {
                    "success": False,
                    "error": "Product does not meet minimum quality criteria for promotion",
                    "quality_score": quality_result['score'],
                    "missing_fields": quality_result['missing'],
                    "checks": quality_result['checks']
                }

            # Update product with promotion status
            now = datetime.utcnow().isoformat()

            await asyncio.to_thread(
                self.store_inventory_table.update_item,
                Key={'store_id': store_id, 'product_id': product_id},
                UpdateExpression='''SET
                    promotion_status = :status,
                    promotion_request_date = :request_date,
                    promotion_requested_by = :user_id,
                    quality_score = :score,
                    updated_at = :updated_at
                ''',
                ExpressionAttributeValues={
                    ':status': PROMOTION_STATUS_PENDING,
                    ':request_date': now,
                    ':user_id': user_id,
                    ':score': Decimal(str(quality_result['score'])),
                    ':updated_at': now
                }
            )

            logger.info(
                f"Promotion requested: {product_id} from store {store_id} | "
                f"Quality score: {quality_result['score']} | Requested by: {user_id}"
            )

            return {
                "success": True,
                "message": "Promotion request submitted for admin review",
                "product_id": product_id,
                "quality_score": quality_result['score'],
                "checks": quality_result['checks'],
                "promotion_status": PROMOTION_STATUS_PENDING
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error requesting promotion: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error requesting promotion: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_promotion_request(
        self,
        store_id: str,
        product_id: str,
        user_id: str
    ) -> Dict:
        """
        Cancel a pending promotion request.

        Only products with 'pending_review' status can be cancelled.

        Args:
            store_id: Store ID
            product_id: Product ID
            user_id: User cancelling the request

        Returns:
            Dict with success status
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot cancel promotion"}

        try:
            # Get the product
            product = await self.get_product(store_id, product_id)

            if not product:
                return {"success": False, "error": "Product not found"}

            if product.get('source_store_id') != store_id:
                return {"success": False, "error": "Not authorized to cancel this promotion"}

            if product.get('promotion_status') != PROMOTION_STATUS_PENDING:
                return {"success": False, "error": "Only pending promotions can be cancelled"}

            # Reset promotion status
            now = datetime.utcnow().isoformat()

            await asyncio.to_thread(
                self.store_inventory_table.update_item,
                Key={'store_id': store_id, 'product_id': product_id},
                UpdateExpression='''SET
                    promotion_status = :status,
                    promotion_cancelled_at = :cancelled_at,
                    promotion_cancelled_by = :user_id,
                    updated_at = :updated_at
                ''',
                ExpressionAttributeValues={
                    ':status': PROMOTION_STATUS_NONE,
                    ':cancelled_at': now,
                    ':user_id': user_id,
                    ':updated_at': now
                }
            )

            logger.info(
                f"Promotion cancelled: {product_id} from store {store_id} | "
                f"Cancelled by: {user_id}"
            )

            return {
                "success": True,
                "message": "Promotion request cancelled",
                "product_id": product_id,
                "promotion_status": PROMOTION_STATUS_NONE
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error cancelling promotion: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error cancelling promotion: {e}")
            return {"success": False, "error": str(e)}

    async def get_promotion_requests(
        self,
        store_id: str
    ) -> List[Dict]:
        """
        Get all promotion requests for a store.

        Returns products with any promotion status other than 'none'.

        Args:
            store_id: Store ID

        Returns:
            List of products with promotion requests
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

            # Filter to products with promotion activity
            promotion_products = [
                p for p in products
                if p.get('promotion_status') and p.get('promotion_status') != PROMOTION_STATUS_NONE
            ]

            # Sort by promotion request date (newest first)
            promotion_products.sort(
                key=lambda x: x.get('promotion_request_date', ''),
                reverse=True
            )

            return decimal_to_float(promotion_products)

        except Exception as e:
            logger.error(f"Error getting promotion requests: {e}")
            return []

    async def add_from_global_catalog(
        self,
        store_id: str,
        user_id: str,
        global_product_id: str,
        inventory_data: Dict[str, Any]
    ) -> Dict:
        """
        Add a product from the global catalog to a store's inventory.

        This creates a store inventory record linked to a global catalog product.

        Args:
            store_id: Store ID
            user_id: User ID of the store owner
            global_product_id: Product ID from global catalog
            inventory_data: Store-specific inventory data (price, stock, etc.)

        Returns:
            Dict with success status and created inventory record
        """
        if self.use_mock:
            return {"success": False, "error": "Mock mode - cannot add products"}

        try:
            # First, verify the global product exists
            global_product = await self._get_global_product(global_product_id)

            if not global_product:
                return {"success": False, "error": f"Global product not found: {global_product_id}"}

            # Check if this product is already in the store's inventory
            existing = await self.get_product(store_id, global_product_id)
            if existing:
                return {
                    "success": False,
                    "error": "Product already exists in your inventory",
                    "existing_product": decimal_to_float(existing)
                }

            # Build the store inventory item
            now = datetime.utcnow().isoformat()

            inventory_item = {
                # Keys
                'store_id': store_id,
                'product_id': global_product_id,

                # Product metadata from global catalog
                'product_source': PRODUCT_SOURCE_GLOBAL,
                'product_name': global_product.get('name', global_product.get('product_name', '')),
                'brand_name': global_product.get('brand', ''),
                'barcode': global_product.get('barcode', ''),
                'category': global_product.get('category', ''),

                # Store-specific inventory data
                'selling_price': Decimal(str(inventory_data.get('selling_price', 0))),
                'cost_price': Decimal(str(inventory_data.get('cost_price', 0))),
                'mrp': Decimal(str(global_product.get('mrp', inventory_data.get('mrp', 0)))),
                'current_stock': int(inventory_data.get('current_stock', 0)),
                'min_stock_level': int(inventory_data.get('min_stock_level', 10)),
                'max_stock_level': int(inventory_data.get('max_stock_level', 100)),
                'reorder_point': int(inventory_data.get('reorder_point', 10)),

                # Additional store data
                'location': inventory_data.get('location', ''),
                'notes': inventory_data.get('notes', ''),

                # Flags
                'is_active': inventory_data.get('is_active', True),

                # Timestamps
                'created_at': now,
                'updated_at': now,
                'added_by_user_id': user_id,
            }

            # Remove empty values
            inventory_item = {k: v for k, v in inventory_item.items()
                            if v is not None and v != ''}

            # Create the inventory record
            await asyncio.to_thread(
                self.store_inventory_table.put_item,
                Item=inventory_item
            )

            logger.info(
                f"Product added from global catalog: {global_product_id} to store {store_id} | "
                f"Added by: {user_id}"
            )

            # Invalidate cache after adding new product
            self.invalidate_summary_cache(store_id)

            # Update pre-computed stats
            await self._update_stats_on_product_add(
                store_id=store_id,
                selling_price=float(inventory_item.get('selling_price', 0)),
                current_stock=int(inventory_item.get('current_stock', 0)),
                min_stock_level=int(inventory_item.get('min_stock_level', 10))
            )

            return {
                "success": True,
                "product_id": global_product_id,
                "product": decimal_to_float(inventory_item),
                "message": "Product added to inventory from global catalog"
            }

        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"DynamoDB error adding from catalog: {error_code} - {e}")
            return {"success": False, "error": f"Database error: {error_code}"}
        except Exception as e:
            logger.error(f"Error adding from global catalog: {e}")
            return {"success": False, "error": str(e)}

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
            "total_stock_value": 0,
            "error": "DynamoDB not available - using fallback mode"
        }


# Global instance
inventory_service = InventoryService()
