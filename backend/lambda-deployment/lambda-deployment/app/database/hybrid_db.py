"""
Hybrid Database Manager for VyaparAI
Combines DynamoDB for hot-path operations and PostgreSQL for analytics
"""

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import uuid

# AWS SDK
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# PostgreSQL
import asyncpg
from asyncpg.exceptions import PostgresError

# Local imports
from ..services.unified_order_service import OrderProcessingResult

logger = logging.getLogger(__name__)

@dataclass
class OrderData:
    """Order data structure for DynamoDB"""
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
    created_at: str
    updated_at: str
    ttl: Optional[int] = None

@dataclass
class SessionData:
    """Session data structure for DynamoDB"""
    session_id: str
    customer_phone: str
    store_id: str
    context: Dict[str, Any]
    last_activity: str
    ttl: Optional[int] = None

@dataclass
class StoreData:
    """Store data structure for PostgreSQL"""
    store_id: str
    name: str
    owner_id: str
    address: Dict[str, Any]
    contact_info: Dict[str, Any]
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class ProductData:
    """Product data structure for PostgreSQL"""
    product_id: str
    store_id: str
    name: str
    category: str
    brand: str
    price: float
    unit: str
    stock_quantity: int
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class HybridOrderResult:
    """Result from hybrid database operations"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0
    source: str = "unknown"  # "dynamodb" or "postgresql"

class HybridDatabase:
    """
    Hybrid Database Manager
    Handles both DynamoDB (hot-path) and PostgreSQL (analytics) operations
    """

    def __init__(self):
        """Initialize the hybrid database manager"""
        self.dynamodb = None
        self.postgres_pool = None
        self._initialize_dynamodb()
        self._initialize_postgres_pool()
        self._build_table_names()

    def _initialize_dynamodb(self):
        """Initialize DynamoDB client"""
        try:
            self.dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
            logger.info("DynamoDB client initialized successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            self.dynamodb = None
        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB: {e}")
            self.dynamodb = None

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
                logger.warning("RDS environment variables not set, PostgreSQL operations will be disabled")
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
            logger.info("PostgreSQL connection pool initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            self.postgres_pool = None

    def _build_table_names(self):
        """Build table names from environment variables"""
        self.table_names = {
            'orders': os.getenv('DYNAMODB_ORDERS_TABLE', 'vyaparai-orders-dev'),
            'sessions': os.getenv('DYNAMODB_SESSIONS_TABLE', 'vyaparai-sessions-dev'),
            'rate_limits': os.getenv('DYNAMODB_RATE_LIMITS_TABLE', 'vyaparai-rate-limits-dev'),
            'stores': os.getenv('DYNAMODB_STORES_TABLE', 'vyaparai-stores-dev'),
            'products': os.getenv('DYNAMODB_PRODUCTS_TABLE', 'vyaparai-products-dev'),
            'metrics': os.getenv('DYNAMODB_METRICS_TABLE', 'vyaparai-metrics-dev')
        }

    # DynamoDB Operations

    async def create_order(self, order_data: OrderData) -> HybridOrderResult:
        """Create a new order in DynamoDB"""
        start_time = time.time()
        
        if not self.dynamodb:
            return HybridOrderResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        try:
            table = self.dynamodb.Table(self.table_names['orders'])
            
            # Prepare item for DynamoDB
            item = {
                'pk': f"ORDER#{order_data.order_id}",
                'sk': f"CUSTOMER#{order_data.customer_phone}",
                'gsi1pk': f"STORE#{order_data.store_id}",
                'gsi1sk': order_data.created_at,
                'gsi2pk': f"STATUS#{order_data.status}",
                'gsi2sk': order_data.created_at,
                'gsi3pk': f"CHANNEL#{order_data.channel}",
                'gsi3sk': order_data.created_at,
                'order_id': order_data.order_id,
                'customer_phone': order_data.customer_phone,
                'store_id': order_data.store_id,
                'items': order_data.items,
                'total_amount': order_data.total_amount,
                'status': order_data.status,
                'channel': order_data.channel,
                'language': order_data.language,
                'intent': order_data.intent,
                'confidence': order_data.confidence,
                'entities': order_data.entities,
                'created_at': order_data.created_at,
                'updated_at': order_data.updated_at
            }

            if order_data.ttl:
                item['ttl'] = order_data.ttl

            await asyncio.to_thread(table.put_item, Item=item)

            return HybridOrderResult(
                success=True,
                data=order_data.order_id,
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        except ClientError as e:
            logger.error(f"DynamoDB error creating order: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

    async def get_order(self, order_id: str) -> HybridOrderResult:
        """Get order from DynamoDB"""
        start_time = time.time()
        
        if not self.dynamodb:
            return HybridOrderResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        try:
            table = self.dynamodb.Table(self.table_names['orders'])
            
            # Query by order_id using GSI
            response = await asyncio.to_thread(
                table.query,
                IndexName='GSI1',
                KeyConditionExpression='gsi1pk = :pk',
                ExpressionAttributeValues={
                    ':pk': f"ORDER#{order_id}"
                }
            )

            if response['Items']:
                item = response['Items'][0]
                order_data = OrderData(
                    order_id=item['order_id'],
                    customer_phone=item['customer_phone'],
                    store_id=item['store_id'],
                    items=item['items'],
                    total_amount=item['total_amount'],
                    status=item['status'],
                    channel=item['channel'],
                    language=item['language'],
                    intent=item['intent'],
                    confidence=item['confidence'],
                    entities=item['entities'],
                    created_at=item['created_at'],
                    updated_at=item['updated_at']
                )

                return HybridOrderResult(
                    success=True,
                    data=order_data,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    source="dynamodb"
                )
            else:
                return HybridOrderResult(
                    success=False,
                    error="Order not found",
                    processing_time_ms=(time.time() - start_time) * 1000,
                    source="dynamodb"
                )

        except ClientError as e:
            logger.error(f"DynamoDB error getting order: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

    async def update_order_status(self, order_id: str, status: str) -> HybridOrderResult:
        """Update order status in DynamoDB"""
        start_time = time.time()
        
        if not self.dynamodb:
            return HybridOrderResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        try:
            table = self.dynamodb.Table(self.table_names['orders'])
            
            # Update the order status
            response = await asyncio.to_thread(
                table.update_item,
                Key={
                    'pk': f"ORDER#{order_id}",
                    'sk': f"CUSTOMER#{order_id}"  # This will be updated based on actual data
                },
                UpdateExpression='SET #status = :status, #updated_at = :updated_at, gsi2pk = :gsi2pk',
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#updated_at': 'updated_at'
                },
                ExpressionAttributeValues={
                    ':status': status,
                    ':updated_at': datetime.utcnow().isoformat(),
                    ':gsi2pk': f"STATUS#{status}"
                },
                ReturnValues='ALL_NEW'
            )

            return HybridOrderResult(
                success=True,
                data=response['Attributes'],
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        except ClientError as e:
            logger.error(f"DynamoDB error updating order status: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

    async def get_customer_orders(self, customer_phone: str, limit: int = 10) -> HybridOrderResult:
        """Get customer orders from DynamoDB"""
        start_time = time.time()
        
        if not self.dynamodb:
            return HybridOrderResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        try:
            table = self.dynamodb.Table(self.table_names['orders'])
            
            response = await asyncio.to_thread(
                table.query,
                KeyConditionExpression='sk = :customer_phone',
                ExpressionAttributeValues={
                    ':customer_phone': f"CUSTOMER#{customer_phone}"
                },
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )

            orders = []
            for item in response['Items']:
                order_data = OrderData(
                    order_id=item['order_id'],
                    customer_phone=item['customer_phone'],
                    store_id=item['store_id'],
                    items=item['items'],
                    total_amount=item['total_amount'],
                    status=item['status'],
                    channel=item['channel'],
                    language=item['language'],
                    intent=item['intent'],
                    confidence=item['confidence'],
                    entities=item['entities'],
                    created_at=item['created_at'],
                    updated_at=item['updated_at']
                )
                orders.append(order_data)

            return HybridOrderResult(
                success=True,
                data=orders,
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        except ClientError as e:
            logger.error(f"DynamoDB error getting customer orders: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

    async def create_session(self, session_data: SessionData) -> HybridOrderResult:
        """Create a new session in DynamoDB"""
        start_time = time.time()
        
        if not self.dynamodb:
            return HybridOrderResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        try:
            table = self.dynamodb.Table(self.table_names['sessions'])
            
            item = {
                'pk': f"SESSION#{session_data.session_id}",
                'gsi1pk': f"CUSTOMER#{session_data.customer_phone}",
                'gsi1sk': session_data.last_activity,
                'session_id': session_data.session_id,
                'customer_phone': session_data.customer_phone,
                'store_id': session_data.store_id,
                'context': session_data.context,
                'last_activity': session_data.last_activity
            }

            if session_data.ttl:
                item['ttl'] = session_data.ttl

            await asyncio.to_thread(table.put_item, Item=item)

            return HybridOrderResult(
                success=True,
                data=session_data.session_id,
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        except ClientError as e:
            logger.error(f"DynamoDB error creating session: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

    async def update_rate_limit(self, key: str, limit_type: str, current_count: int) -> HybridOrderResult:
        """Update rate limit in DynamoDB"""
        start_time = time.time()
        
        if not self.dynamodb:
            return HybridOrderResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        try:
            table = self.dynamodb.Table(self.table_names['rate_limits'])
            
            # Set TTL to 1 hour from now
            ttl = int(time.time()) + 3600
            
            item = {
                'pk': f"RATE_LIMIT#{key}",
                'sk': limit_type,
                'gsi1pk': limit_type,
                'gsi1sk': str(int(time.time())),
                'current_count': current_count,
                'last_updated': datetime.utcnow().isoformat(),
                'ttl': ttl
            }

            await asyncio.to_thread(table.put_item, Item=item)

            return HybridOrderResult(
                success=True,
                data=current_count,
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

        except ClientError as e:
            logger.error(f"DynamoDB error updating rate limit: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="dynamodb"
            )

    # PostgreSQL Operations

    async def get_store_details(self, store_id: str) -> HybridOrderResult:
        """Get store details from PostgreSQL"""
        start_time = time.time()
        
        if not self.postgres_pool:
            return HybridOrderResult(
                success=False,
                error="PostgreSQL not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

        try:
            async with self.postgres_pool.acquire() as conn:
                query = """
                    SELECT store_id, name, owner_id, address, contact_info, settings, 
                           created_at, updated_at
                    FROM stores 
                    WHERE store_id = $1
                """
                row = await conn.fetchrow(query, store_id)
                
                if row:
                    store_data = StoreData(
                        store_id=row['store_id'],
                        name=row['name'],
                        owner_id=row['owner_id'],
                        address=row['address'],
                        contact_info=row['contact_info'],
                        settings=row['settings'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    
                    return HybridOrderResult(
                        success=True,
                        data=store_data,
                        processing_time_ms=(time.time() - start_time) * 1000,
                        source="postgresql"
                    )
                else:
                    return HybridOrderResult(
                        success=False,
                        error="Store not found",
                        processing_time_ms=(time.time() - start_time) * 1000,
                        source="postgresql"
                    )

        except PostgresError as e:
            logger.error(f"PostgreSQL error getting store details: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

    async def search_products(self, store_id: str, query: str, limit: int = 10) -> HybridOrderResult:
        """Search products in PostgreSQL"""
        start_time = time.time()
        
        if not self.postgres_pool:
            return HybridOrderResult(
                success=False,
                error="PostgreSQL not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

        try:
            async with self.postgres_pool.acquire() as conn:
                search_query = """
                    SELECT product_id, store_id, name, category, brand, price, unit, 
                           stock_quantity, metadata, created_at, updated_at
                    FROM products 
                    WHERE store_id = $1 
                    AND (name ILIKE $2 OR brand ILIKE $2 OR category ILIKE $2)
                    AND stock_quantity > 0
                    ORDER BY name
                    LIMIT $3
                """
                
                rows = await conn.fetch(search_query, store_id, f"%{query}%", limit)
                
                products = []
                for row in rows:
                    product_data = ProductData(
                        product_id=row['product_id'],
                        store_id=row['store_id'],
                        name=row['name'],
                        category=row['category'],
                        brand=row['brand'],
                        price=row['price'],
                        unit=row['unit'],
                        stock_quantity=row['stock_quantity'],
                        metadata=row['metadata'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    products.append(product_data)

                return HybridOrderResult(
                    success=True,
                    data=products,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    source="postgresql"
                )

        except PostgresError as e:
            logger.error(f"PostgreSQL error searching products: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

    async def get_store_analytics(self, store_id: str, days: int = 30) -> HybridOrderResult:
        """Get store analytics from PostgreSQL"""
        start_time = time.time()
        
        if not self.postgres_pool:
            return HybridOrderResult(
                success=False,
                error="PostgreSQL not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

        try:
            async with self.postgres_pool.acquire() as conn:
                analytics_query = """
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as total_orders,
                        SUM(total_amount) as total_revenue,
                        AVG(total_amount) as avg_order_value,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
                        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders
                    FROM order_archive 
                    WHERE store_id = $1 
                    AND created_at >= NOW() - INTERVAL '$2 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """
                
                rows = await conn.fetch(analytics_query, store_id, days)
                
                analytics = []
                for row in rows:
                    analytics.append({
                        'date': row['date'].isoformat(),
                        'total_orders': row['total_orders'],
                        'total_revenue': float(row['total_revenue'] or 0),
                        'avg_order_value': float(row['avg_order_value'] or 0),
                        'completed_orders': row['completed_orders'],
                        'cancelled_orders': row['cancelled_orders']
                    })

                return HybridOrderResult(
                    success=True,
                    data=analytics,
                    processing_time_ms=(time.time() - start_time) * 1000,
                    source="postgresql"
                )

        except PostgresError as e:
            logger.error(f"PostgreSQL error getting store analytics: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

    async def get_customer_analytics(self, customer_phone: str) -> HybridOrderResult:
        """Get customer analytics from PostgreSQL"""
        start_time = time.time()
        
        if not self.postgres_pool:
            return HybridOrderResult(
                success=False,
                error="PostgreSQL not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

        try:
            async with self.postgres_pool.acquire() as conn:
                analytics_query = """
                    SELECT 
                        COUNT(*) as total_orders,
                        SUM(total_amount) as total_spent,
                        AVG(total_amount) as avg_order_value,
                        MAX(created_at) as last_order_date,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
                        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders
                    FROM order_archive 
                    WHERE customer_phone = $1
                """
                
                row = await conn.fetchrow(analytics_query, customer_phone)
                
                if row:
                    analytics = {
                        'total_orders': row['total_orders'],
                        'total_spent': float(row['total_spent'] or 0),
                        'avg_order_value': float(row['avg_order_value'] or 0),
                        'last_order_date': row['last_order_date'].isoformat() if row['last_order_date'] else None,
                        'completed_orders': row['completed_orders'],
                        'cancelled_orders': row['cancelled_orders']
                    }
                    
                    return HybridOrderResult(
                        success=True,
                        data=analytics,
                        processing_time_ms=(time.time() - start_time) * 1000,
                        source="postgresql"
                    )
                else:
                    return HybridOrderResult(
                        success=True,
                        data={
                            'total_orders': 0,
                            'total_spent': 0.0,
                            'avg_order_value': 0.0,
                            'last_order_date': None,
                            'completed_orders': 0,
                            'cancelled_orders': 0
                        },
                        processing_time_ms=(time.time() - start_time) * 1000,
                        source="postgresql"
                    )

        except PostgresError as e:
            logger.error(f"PostgreSQL error getting customer analytics: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

    # Hybrid Operations

    async def calculate_order_total(self, items: List[Dict[str, Any]], store_id: str) -> HybridOrderResult:
        """Calculate order total using PostgreSQL for pricing"""
        start_time = time.time()
        
        if not self.postgres_pool:
            return HybridOrderResult(
                success=False,
                error="PostgreSQL not initialized",
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

        try:
            async with self.postgres_pool.acquire() as conn:
                total = 0.0
                calculated_items = []
                
                for item in items:
                    product_name = item.get('product', '').lower()
                    quantity = item.get('quantity', 0)
                    
                    # Get product price from PostgreSQL
                    price_query = """
                        SELECT price, unit, stock_quantity 
                        FROM products 
                        WHERE store_id = $1 
                        AND LOWER(name) = $2
                        LIMIT 1
                    """
                    
                    row = await conn.fetchrow(price_query, store_id, product_name)
                    
                    if row:
                        price = row['price']
                        unit = row['unit']
                        stock = row['stock_quantity']
                        
                        item_total = price * quantity
                        total += item_total
                        
                        calculated_items.append({
                            **item,
                            'price': price,
                            'unit': unit,
                            'stock_quantity': stock,
                            'total': item_total
                        })
                    else:
                        # Use default price if product not found
                        default_price = 50.0  # Default price
                        item_total = default_price * quantity
                        total += item_total
                        
                        calculated_items.append({
                            **item,
                            'price': default_price,
                            'unit': 'piece',
                            'stock_quantity': 0,
                            'total': item_total
                        })

                return HybridOrderResult(
                    success=True,
                    data={
                        'total': total,
                        'items': calculated_items
                    },
                    processing_time_ms=(time.time() - start_time) * 1000,
                    source="postgresql"
                )

        except PostgresError as e:
            logger.error(f"PostgreSQL error calculating order total: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="postgresql"
            )

    async def process_order_with_analytics(self, order_result: OrderProcessingResult, store_id: str) -> HybridOrderResult:
        """Process order and update analytics in both databases"""
        start_time = time.time()
        
        try:
            # Create order in DynamoDB
            order_data = OrderData(
                order_id=str(uuid.uuid4()),
                customer_phone="",  # Extract from order_result
                store_id=store_id,
                items=order_result.entities,
                total_amount=0.0,  # Calculate from items
                status="pending",
                channel=order_result.channel_format,
                language=order_result.language,
                intent=order_result.intent,
                confidence=order_result.confidence,
                entities=order_result.entities,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat()
            )
            
            # Calculate total using PostgreSQL
            total_result = await self.calculate_order_total(order_data.items, store_id)
            if total_result.success:
                order_data.total_amount = total_result.data['total']
                order_data.items = total_result.data['items']
            
            # Save to DynamoDB
            db_result = await self.create_order(order_data)
            
            if db_result.success:
                return HybridOrderResult(
                    success=True,
                    data={
                        'order_id': order_data.order_id,
                        'total_amount': order_data.total_amount,
                        'items': order_data.items
                    },
                    processing_time_ms=(time.time() - start_time) * 1000,
                    source="hybrid"
                )
            else:
                return db_result

        except Exception as e:
            logger.error(f"Error processing order with analytics: {e}")
            return HybridOrderResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
                source="hybrid"
            )

    async def close(self):
        """Close database connections"""
        if self.postgres_pool:
            await self.postgres_pool.close()
            logger.info("PostgreSQL connection pool closed")

# Global instance
hybrid_db = HybridDatabase()
