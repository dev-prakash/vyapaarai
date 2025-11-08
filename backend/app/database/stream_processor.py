"""
DynamoDB Streams Processor for VyaparAI
Syncs completed orders from DynamoDB to PostgreSQL for analytics
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

# AWS SDK
import boto3
from botocore.exceptions import ClientError

# PostgreSQL
import asyncpg
from asyncpg.exceptions import PostgresError

logger = logging.getLogger(__name__)

@dataclass
class StreamRecord:
    """DynamoDB Stream record structure"""
    event_id: str
    event_name: str  # INSERT, MODIFY, REMOVE
    dynamodb: Dict[str, Any]
    timestamp: str

@dataclass
class OrderArchiveData:
    """Order data for PostgreSQL archive"""
    order_id: str
    customer_phone: str
    store_id: str
    items: List[Dict[str, Any]]
    total_amount: float
    status: str
    channel: str
    language: str
    intent: str
    confidence: float
    entities: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

class DynamoDBStreamProcessor:
    """
    DynamoDB Streams Processor
    Processes DynamoDB stream events and syncs to PostgreSQL
    """

    def __init__(self):
        """Initialize the stream processor"""
        self.postgres_pool = None
        self._initialize_postgres_pool()

    async def _initialize_postgres_pool(self):
        """Initialize PostgreSQL connection pool"""
        try:
            # Get RDS connection details from environment
            host = os.getenv('RDS_HOSTNAME')
            port = int(os.getenv('RDS_PORT', '5432'))
            database = os.getenv('RDS_DATABASE', 'vyaparai')
            username = os.getenv('RDS_USERNAME')
            password = os.getenv('RDS_PASSWORD')

            if not all([host, username, password]):
                logger.warning("RDS environment variables not set, stream processing will be disabled")
                self.postgres_pool = None
                return

            # Create connection pool
            self.postgres_pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password,
                min_size=2,
                max_size=10,
                command_timeout=30
            )
            logger.info("PostgreSQL connection pool initialized for stream processing")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool for stream processing: {e}")
            self.postgres_pool = None

    async def process_order_stream(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        Lambda handler for DynamoDB Streams
        Processes order table stream events
        """
        start_time = time.time()
        
        try:
            logger.info(f"Processing DynamoDB stream event: {event}")
            
            if not self.postgres_pool:
                logger.warning("PostgreSQL not available, skipping stream processing")
                return {
                    'statusCode': 200,
                    'body': 'PostgreSQL not available'
                }

            # Process each record in the stream
            records = event.get('Records', [])
            processed_count = 0
            error_count = 0

            for record in records:
                try:
                    await self._process_stream_record(record)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing stream record: {e}")
                    error_count += 1

            processing_time = (time.time() - start_time) * 1000
            
            logger.info(f"Stream processing completed: {processed_count} processed, {error_count} errors, {processing_time:.2f}ms")

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'processed_count': processed_count,
                    'error_count': error_count,
                    'processing_time_ms': processing_time
                })
            }

        except Exception as e:
            logger.error(f"Error in stream processing: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': str(e)})
            }

    async def _process_stream_record(self, record: Dict[str, Any]):
        """Process a single stream record"""
        try:
            # Parse the stream record
            stream_record = StreamRecord(
                event_id=record['eventID'],
                event_name=record['eventName'],
                dynamodb=record['dynamodb'],
                timestamp=record['kinesisApproximateArrivalTimestamp']
            )

            # Only process INSERT and MODIFY events for orders
            if stream_record.event_name not in ['INSERT', 'MODIFY']:
                logger.debug(f"Skipping {stream_record.event_name} event")
                return

            # Extract order data from the stream record
            order_data = await self._extract_order_data(stream_record)
            if not order_data:
                logger.debug("No order data found in stream record")
                return

            # Process based on order status
            if order_data.status in ['completed', 'cancelled']:
                await self._archive_completed_order(order_data)
                await self._update_analytics(order_data)
            elif order_data.status == 'pending':
                await self._update_order_archive(order_data)

        except Exception as e:
            logger.error(f"Error processing stream record {record.get('eventID', 'unknown')}: {e}")
            raise

    async def _extract_order_data(self, stream_record: StreamRecord) -> Optional[OrderArchiveData]:
        """Extract order data from DynamoDB stream record"""
        try:
            # Get the new image (after the change)
            new_image = stream_record.dynamodb.get('NewImage', {})
            if not new_image:
                return None

            # Extract order fields
            order_id = new_image.get('order_id', {}).get('S')
            customer_phone = new_image.get('customer_phone', {}).get('S')
            store_id = new_image.get('store_id', {}).get('S')
            status = new_image.get('status', {}).get('S')
            channel = new_image.get('channel', {}).get('S')
            language = new_image.get('language', {}).get('S')
            intent = new_image.get('intent', {}).get('S')
            confidence = float(new_image.get('confidence', {}).get('N', '0'))
            created_at = new_image.get('created_at', {}).get('S')
            updated_at = new_image.get('updated_at', {}).get('S')

            # Parse items and entities (JSON arrays)
            items = []
            if 'items' in new_image:
                items_data = new_image['items'].get('L', [])
                for item in items_data:
                    if 'M' in item:
                        items.append(item['M'])

            entities = []
            if 'entities' in new_image:
                entities_data = new_image['entities'].get('L', [])
                for entity in entities_data:
                    if 'M' in entity:
                        entities.append(entity['M'])

            # Parse total amount
            total_amount = float(new_image.get('total_amount', {}).get('N', '0'))

            # Parse timestamps
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if created_at else datetime.utcnow()
            updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00')) if updated_at else datetime.utcnow()

            return OrderArchiveData(
                order_id=order_id,
                customer_phone=customer_phone,
                store_id=store_id,
                items=items,
                total_amount=total_amount,
                status=status,
                channel=channel,
                language=language,
                intent=intent,
                confidence=confidence,
                entities=entities,
                created_at=created_dt,
                updated_at=updated_dt
            )

        except Exception as e:
            logger.error(f"Error extracting order data from stream record: {e}")
            return None

    async def _archive_completed_order(self, order_data: OrderArchiveData):
        """Archive completed order to PostgreSQL"""
        try:
            async with self.postgres_pool.acquire() as conn:
                # Check if order already exists in archive
                existing = await conn.fetchrow(
                    "SELECT order_id FROM order_archive WHERE order_id = $1",
                    order_data.order_id
                )

                if existing:
                    # Update existing order
                    await conn.execute("""
                        UPDATE order_archive 
                        SET 
                            customer_phone = $2,
                            store_id = $3,
                            items = $4,
                            total_amount = $5,
                            status = $6,
                            channel = $7,
                            language = $8,
                            intent = $9,
                            confidence = $10,
                            entities = $11,
                            updated_at = $12,
                            completed_at = CASE WHEN $6 = 'completed' THEN $12 ELSE completed_at END,
                            cancelled_at = CASE WHEN $6 = 'cancelled' THEN $12 ELSE cancelled_at END
                        WHERE order_id = $1
                    """, 
                    order_data.order_id,
                    order_data.customer_phone,
                    order_data.store_id,
                    json.dumps(order_data.items),
                    order_data.total_amount,
                    order_data.status,
                    order_data.channel,
                    order_data.language,
                    order_data.intent,
                    order_data.confidence,
                    json.dumps(order_data.entities),
                    order_data.updated_at
                    )
                else:
                    # Insert new order
                    await conn.execute("""
                        INSERT INTO order_archive (
                            order_id, customer_phone, store_id, items, total_amount,
                            status, channel, language, intent, confidence, entities,
                            created_at, updated_at, completed_at, cancelled_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    """,
                    order_data.order_id,
                    order_data.customer_phone,
                    order_data.store_id,
                    json.dumps(order_data.items),
                    order_data.total_amount,
                    order_data.status,
                    order_data.channel,
                    order_data.language,
                    order_data.intent,
                    order_data.confidence,
                    json.dumps(order_data.entities),
                    order_data.created_at,
                    order_data.updated_at,
                    order_data.completed_at,
                    order_data.cancelled_at
                    )

                logger.info(f"Order {order_data.order_id} archived to PostgreSQL")

        except PostgresError as e:
            logger.error(f"PostgreSQL error archiving order {order_data.order_id}: {e}")
            raise

    async def _update_order_archive(self, order_data: OrderArchiveData):
        """Update order in archive (for pending orders)"""
        try:
            async with self.postgres_pool.acquire() as conn:
                # Upsert order to archive
                await conn.execute("""
                    INSERT INTO order_archive (
                        order_id, customer_phone, store_id, items, total_amount,
                        status, channel, language, intent, confidence, entities,
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (order_id) DO UPDATE SET
                        customer_phone = EXCLUDED.customer_phone,
                        store_id = EXCLUDED.store_id,
                        items = EXCLUDED.items,
                        total_amount = EXCLUDED.total_amount,
                        status = EXCLUDED.status,
                        channel = EXCLUDED.channel,
                        language = EXCLUDED.language,
                        intent = EXCLUDED.intent,
                        confidence = EXCLUDED.confidence,
                        entities = EXCLUDED.entities,
                        updated_at = EXCLUDED.updated_at
                """,
                order_data.order_id,
                order_data.customer_phone,
                order_data.store_id,
                json.dumps(order_data.items),
                order_data.total_amount,
                order_data.status,
                order_data.channel,
                order_data.language,
                order_data.intent,
                order_data.confidence,
                json.dumps(order_data.entities),
                order_data.created_at,
                order_data.updated_at
                )

                logger.debug(f"Order {order_data.order_id} updated in archive")

        except PostgresError as e:
            logger.error(f"PostgreSQL error updating order archive {order_data.order_id}: {e}")
            raise

    async def _update_analytics(self, order_data: OrderArchiveData):
        """Update analytics tables based on order status"""
        try:
            async with self.postgres_pool.acquire() as conn:
                # Update daily store metrics
                await self._update_daily_store_metrics(conn, order_data)
                
                # Update customer analytics
                await self._update_customer_analytics(conn, order_data)
                
                # Update product analytics
                await self._update_product_analytics(conn, order_data)

        except PostgresError as e:
            logger.error(f"PostgreSQL error updating analytics for order {order_data.order_id}: {e}")
            raise

    async def _update_daily_store_metrics(self, conn, order_data: OrderArchiveData):
        """Update daily store metrics"""
        try:
            date_key = order_data.updated_at.date()
            
            # Upsert daily metrics
            await conn.execute("""
                INSERT INTO daily_store_metrics (
                    store_id, date, total_orders, total_revenue, 
                    completed_orders, cancelled_orders, unique_customers
                ) VALUES ($1, $2, 1, $3, $4, $5, 1)
                ON CONFLICT (store_id, date) DO UPDATE SET
                    total_orders = daily_store_metrics.total_orders + 1,
                    total_revenue = daily_store_metrics.total_revenue + $3,
                    completed_orders = daily_store_metrics.completed_orders + $4,
                    cancelled_orders = daily_store_metrics.cancelled_orders + $5,
                    unique_customers = CASE 
                        WHEN $6 NOT IN (
                            SELECT DISTINCT customer_phone 
                            FROM order_archive 
                            WHERE store_id = $1 AND DATE(created_at) = $2
                        ) THEN daily_store_metrics.unique_customers + 1
                        ELSE daily_store_metrics.unique_customers
                    END
            """,
            order_data.store_id,
            date_key,
            order_data.total_amount if order_data.status == 'completed' else 0,
            1 if order_data.status == 'completed' else 0,
            1 if order_data.status == 'cancelled' else 0,
            order_data.customer_phone
            )

        except PostgresError as e:
            logger.error(f"Error updating daily store metrics: {e}")
            raise

    async def _update_customer_analytics(self, conn, order_data: OrderArchiveData):
        """Update customer analytics"""
        try:
            # Upsert customer analytics
            await conn.execute("""
                INSERT INTO customer_analytics (
                    customer_phone, total_orders, total_spent, 
                    avg_order_value, last_order_date, completed_orders, cancelled_orders
                ) VALUES ($1, 1, $2, $2, $3, $4, $5)
                ON CONFLICT (customer_phone) DO UPDATE SET
                    total_orders = customer_analytics.total_orders + 1,
                    total_spent = customer_analytics.total_spent + $2,
                    avg_order_value = (customer_analytics.total_spent + $2) / (customer_analytics.total_orders + 1),
                    last_order_date = $3,
                    completed_orders = customer_analytics.completed_orders + $4,
                    cancelled_orders = customer_analytics.cancelled_orders + $5
            """,
            order_data.customer_phone,
            order_data.total_amount if order_data.status == 'completed' else 0,
            order_data.updated_at,
            1 if order_data.status == 'completed' else 0,
            1 if order_data.status == 'cancelled' else 0
            )

        except PostgresError as e:
            logger.error(f"Error updating customer analytics: {e}")
            raise

    async def _update_product_analytics(self, conn, order_data: OrderArchiveData):
        """Update product analytics"""
        try:
            # Process each item in the order
            for item in order_data.items:
                product_name = item.get('product', '')
                quantity = item.get('quantity', 0)
                price = item.get('price', 0)
                
                if product_name and quantity > 0:
                    # Upsert product analytics
                    await conn.execute("""
                        INSERT INTO product_analytics (
                            product_name, store_id, total_orders, total_quantity, 
                            total_revenue, avg_price, last_ordered_date
                        ) VALUES ($1, $2, 1, $3, $4, $5, $6)
                        ON CONFLICT (product_name, store_id) DO UPDATE SET
                            total_orders = product_analytics.total_orders + 1,
                            total_quantity = product_analytics.total_quantity + $3,
                            total_revenue = product_analytics.total_revenue + $4,
                            avg_price = (product_analytics.total_revenue + $4) / (product_analytics.total_quantity + $3),
                            last_ordered_date = $6
                    """,
                    product_name,
                    order_data.store_id,
                    quantity,
                    price * quantity if order_data.status == 'completed' else 0,
                    price,
                    order_data.updated_at
                    )

        except PostgresError as e:
            logger.error(f"Error updating product analytics: {e}")
            raise

    async def close(self):
        """Close database connections"""
        if self.postgres_pool:
            await self.postgres_pool.close()
            logger.info("PostgreSQL connection pool closed for stream processor")

# Global instance
stream_processor = DynamoDBStreamProcessor()

# Lambda handler function
async def process_order_stream(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for DynamoDB Streams"""
    return await stream_processor.process_order_stream(event, context)
