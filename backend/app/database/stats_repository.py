"""
Store Stats Repository - Pre-computed Inventory Statistics

Manages the vyaparai-store-stats-{env} DynamoDB table for instant
dashboard loading. Stats are updated atomically on inventory changes
and reconciled periodically via batch job.

Pattern: Stripe-style running totals (update on write, not compute on read)

Author: DevPrakash
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Any
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.database import STATS_TABLE

logger = logging.getLogger(__name__)


def decimal_to_float(obj: Any) -> Any:
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


def float_to_decimal(obj: Any) -> Any:
    """Convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(item) for item in obj]
    return obj


class StoreStatsRepository:
    """
    Repository for pre-computed store inventory statistics.

    Table: vyaparai-store-stats-{env}
    Primary Key: store_id (String)

    Attributes:
    - store_id (PK)
    - total_products (Number) - Count of all products
    - active_products (Number) - Count of non-archived products
    - archived_products (Number) - Count of archived products
    - total_stock_value (Number) - Sum of (price × quantity) for active products
    - low_stock_count (Number) - Products below min_stock_level
    - out_of_stock_count (Number) - Products with 0 stock
    - last_updated (String) - ISO timestamp of last update
    - last_reconciled (String) - ISO timestamp of last batch reconciliation
    - version (Number) - For optimistic locking
    """

    # Table name from central constant (avoids -prod vs -production mismatch)
    TABLE_NAME = STATS_TABLE

    def __init__(self):
        """Initialize repository with DynamoDB connection"""
        try:
            kwargs = {'region_name': settings.AWS_REGION}
            if settings.DYNAMODB_ENDPOINT:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT

            self.dynamodb = boto3.resource('dynamodb', **kwargs)
            self.table = self.dynamodb.Table(self.TABLE_NAME)
            self.client = boto3.client('dynamodb', **kwargs)

            logger.info(f"✅ StoreStatsRepository connected to {self.TABLE_NAME}")
            self.initialized = True

        except Exception as e:
            logger.error(f"⚠️ StoreStatsRepository initialization failed: {e}")
            self.initialized = False

    async def get_stats(self, store_id: str) -> Optional[Dict]:
        """
        Get pre-computed stats for a store.

        This is O(1) - single GetItem operation.

        Args:
            store_id: Store ID

        Returns:
            Stats dict or None if not found
        """
        if not self.initialized:
            logger.warning("StoreStatsRepository not initialized, returning None")
            return None

        try:
            response = await asyncio.to_thread(
                self.table.get_item,
                Key={'store_id': store_id}
            )

            item = response.get('Item')
            if item:
                return decimal_to_float(item)
            return None

        except ClientError as e:
            logger.error(f"Error getting stats for store {store_id}: {e}")
            return None

    async def initialize_stats(self, store_id: str) -> Dict:
        """
        Initialize stats for a new store with zero values.

        Args:
            store_id: Store ID

        Returns:
            Initial stats dict
        """
        if not self.initialized:
            raise RuntimeError("StoreStatsRepository not initialized")

        now = datetime.now(timezone.utc).isoformat()

        initial_stats = {
            'store_id': store_id,
            'total_products': 0,
            'active_products': 0,
            'archived_products': 0,
            'total_stock_value': Decimal('0'),
            'low_stock_count': 0,
            'out_of_stock_count': 0,
            'last_updated': now,
            'last_reconciled': now,
            'version': 1
        }

        try:
            await asyncio.to_thread(
                self.table.put_item,
                Item=initial_stats,
                ConditionExpression='attribute_not_exists(store_id)'
            )
            logger.info(f"Initialized stats for store {store_id}")
            return decimal_to_float(initial_stats)

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                # Stats already exist, return them
                return await self.get_stats(store_id)
            raise

    async def update_stats_atomic(
        self,
        store_id: str,
        delta_total_products: int = 0,
        delta_active_products: int = 0,
        delta_archived_products: int = 0,
        delta_stock_value: float = 0,
        delta_low_stock: int = 0,
        delta_out_of_stock: int = 0
    ) -> Dict:
        """
        Atomically update stats using DynamoDB ADD operation.

        This is safe for concurrent updates - uses atomic counters.

        Args:
            store_id: Store ID
            delta_total_products: Change in total products (+1 or -1)
            delta_active_products: Change in active products
            delta_archived_products: Change in archived products
            delta_stock_value: Change in total stock value
            delta_low_stock: Change in low stock count
            delta_out_of_stock: Change in out of stock count

        Returns:
            Updated stats dict
        """
        if not self.initialized:
            raise RuntimeError("StoreStatsRepository not initialized")

        now = datetime.now(timezone.utc).isoformat()

        # Build update expression for non-zero deltas
        update_parts = ['#last_updated = :now', '#version = #version + :one']
        expression_names = {
            '#last_updated': 'last_updated',
            '#version': 'version'
        }
        expression_values = {
            ':now': now,
            ':one': 1
        }

        if delta_total_products != 0:
            update_parts.append('#total_products = #total_products + :delta_total')
            expression_names['#total_products'] = 'total_products'
            expression_values[':delta_total'] = delta_total_products

        if delta_active_products != 0:
            update_parts.append('#active_products = #active_products + :delta_active')
            expression_names['#active_products'] = 'active_products'
            expression_values[':delta_active'] = delta_active_products

        if delta_archived_products != 0:
            update_parts.append('#archived_products = #archived_products + :delta_archived')
            expression_names['#archived_products'] = 'archived_products'
            expression_values[':delta_archived'] = delta_archived_products

        if delta_stock_value != 0:
            update_parts.append('#stock_value = #stock_value + :delta_value')
            expression_names['#stock_value'] = 'total_stock_value'
            expression_values[':delta_value'] = Decimal(str(delta_stock_value))

        if delta_low_stock != 0:
            update_parts.append('#low_stock = #low_stock + :delta_low')
            expression_names['#low_stock'] = 'low_stock_count'
            expression_values[':delta_low'] = delta_low_stock

        if delta_out_of_stock != 0:
            update_parts.append('#out_of_stock = #out_of_stock + :delta_oos')
            expression_names['#out_of_stock'] = 'out_of_stock_count'
            expression_values[':delta_oos'] = delta_out_of_stock

        update_expression = 'SET ' + ', '.join(update_parts)

        try:
            response = await asyncio.to_thread(
                self.table.update_item,
                Key={'store_id': store_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
                ReturnValues='ALL_NEW'
            )

            logger.debug(f"Updated stats for store {store_id}: "
                        f"products={delta_total_products}, active={delta_active_products}, "
                        f"value={delta_stock_value}")

            return decimal_to_float(response.get('Attributes', {}))

        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException':
                # Stats don't exist yet, initialize first
                await self.initialize_stats(store_id)
                # Retry the update
                return await self.update_stats_atomic(
                    store_id,
                    delta_total_products,
                    delta_active_products,
                    delta_archived_products,
                    delta_stock_value,
                    delta_low_stock,
                    delta_out_of_stock
                )
            raise

    async def set_stats(self, store_id: str, stats: Dict) -> Dict:
        """
        Set stats to specific values (used by batch reconciliation).

        Args:
            store_id: Store ID
            stats: Complete stats dict to set

        Returns:
            Updated stats dict
        """
        if not self.initialized:
            raise RuntimeError("StoreStatsRepository not initialized")

        now = datetime.now(timezone.utc).isoformat()

        item = {
            'store_id': store_id,
            'total_products': stats.get('total_products', 0),
            'active_products': stats.get('active_products', 0),
            'archived_products': stats.get('archived_products', 0),
            'total_stock_value': Decimal(str(stats.get('total_stock_value', 0))),
            'low_stock_count': stats.get('low_stock_count', 0),
            'out_of_stock_count': stats.get('out_of_stock_count', 0),
            'last_updated': now,
            'last_reconciled': now,
            'version': stats.get('version', 0) + 1
        }

        try:
            await asyncio.to_thread(
                self.table.put_item,
                Item=item
            )

            logger.info(f"Set stats for store {store_id} via reconciliation")
            return decimal_to_float(item)

        except ClientError as e:
            logger.error(f"Error setting stats for store {store_id}: {e}")
            raise

    async def ensure_table_exists(self) -> bool:
        """
        Check if stats table exists, create if not.

        Returns:
            True if table exists or was created
        """
        try:
            # Try to describe the table
            await asyncio.to_thread(
                self.client.describe_table,
                TableName=self.TABLE_NAME
            )
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Table doesn't exist, create it
                logger.info(f"Creating stats table: {self.TABLE_NAME}")

                await asyncio.to_thread(
                    self.client.create_table,
                    TableName=self.TABLE_NAME,
                    KeySchema=[
                        {'AttributeName': 'store_id', 'KeyType': 'HASH'}
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'store_id', 'AttributeType': 'S'}
                    ],
                    BillingMode='PAY_PER_REQUEST'
                )

                # Wait for table to be active
                waiter = self.client.get_waiter('table_exists')
                await asyncio.to_thread(
                    waiter.wait,
                    TableName=self.TABLE_NAME
                )

                logger.info(f"Stats table created: {self.TABLE_NAME}")
                return True
            raise


# Singleton instance
_stats_repository: Optional[StoreStatsRepository] = None


def get_stats_repository() -> StoreStatsRepository:
    """Get the singleton StoreStatsRepository instance."""
    global _stats_repository
    if _stats_repository is None:
        _stats_repository = StoreStatsRepository()
    return _stats_repository
