"""
Inventory Management Lambda Handler
Handles all inventory-related operations with the new data model
"""

import json
import boto3
import uuid
import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Database configuration
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'vyaparai')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

# DynamoDB for caching (optional)
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')

class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types in JSON serialization"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super(DecimalEncoder, self).default(obj)

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

def create_response(status_code: int, body: dict, headers: dict = None) -> dict:
    """Create a standardized API response"""
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, cls=DecimalEncoder)
    }

# ============================================
# GENERIC PRODUCTS HANDLERS
# ============================================

def get_generic_products(event: dict) -> dict:
    """Get all generic products or search by query"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get query parameters
        params = event.get('queryStringParameters', {}) or {}
        search_query = params.get('search', '')
        category_id = params.get('category_id')
        product_type = params.get('product_type')
        limit = int(params.get('limit', 100))
        offset = int(params.get('offset', 0))
        
        # Build SQL query
        sql = """
            SELECT 
                gp.id,
                gp.name,
                gp.category_id,
                gp.subcategory_id,
                gp.product_type,
                gp.hsn_code,
                gp.default_unit,
                gp.searchable_keywords,
                gp.typical_sizes,
                gp.attributes_template,
                c.name as category_name,
                sc.name as subcategory_name
            FROM generic_products gp
            LEFT JOIN categories c ON gp.category_id = c.id
            LEFT JOIN categories sc ON gp.subcategory_id = sc.id
            WHERE gp.is_active = true
        """
        
        conditions = []
        params_list = []
        
        if search_query:
            conditions.append("""
                (LOWER(gp.name) LIKE %s OR 
                 %s = ANY(LOWER(gp.searchable_keywords::text)::text[]))
            """)
            params_list.extend([f'%{search_query.lower()}%', search_query.lower()])
        
        if category_id:
            conditions.append("(gp.category_id = %s OR gp.subcategory_id = %s)")
            params_list.extend([category_id, category_id])
        
        if product_type:
            conditions.append("gp.product_type = %s")
            params_list.append(product_type)
        
        if conditions:
            sql += " AND " + " AND ".join(conditions)
        
        sql += " ORDER BY gp.name LIMIT %s OFFSET %s"
        params_list.extend([limit, offset])
        
        cur.execute(sql, params_list)
        products = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return create_response(200, {
            'success': True,
            'products': products,
            'count': len(products),
            'offset': offset,
            'limit': limit
        })
        
    except Exception as e:
        print(f"Error fetching generic products: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def get_categories(event: dict) -> dict:
    """Get product categories hierarchy"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all categories with parent relationships
        cur.execute("""
            SELECT 
                id,
                name,
                parent_id,
                level,
                icon_url,
                display_order
            FROM categories
            WHERE is_active = true
            ORDER BY level, display_order, name
        """)
        
        categories = cur.fetchall()
        
        # Build hierarchy
        category_tree = []
        category_map = {cat['id']: cat for cat in categories}
        
        for cat in categories:
            if cat['parent_id'] is None:
                cat['subcategories'] = []
                category_tree.append(cat)
            else:
                parent = category_map.get(cat['parent_id'])
                if parent:
                    if 'subcategories' not in parent:
                        parent['subcategories'] = []
                    parent['subcategories'].append(cat)
        
        cur.close()
        conn.close()
        
        return create_response(200, {
            'success': True,
            'categories': category_tree
        })
        
    except Exception as e:
        print(f"Error fetching categories: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

# ============================================
# STORE PRODUCTS HANDLERS
# ============================================

def get_store_products(event: dict) -> dict:
    """Get all products for a specific store"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get store_id from path or query parameters
        params = event.get('queryStringParameters', {}) or {}
        store_id = params.get('store_id')
        
        if not store_id:
            return create_response(400, {
                'success': False,
                'error': 'store_id is required'
            })
        
        # Additional filters
        status = params.get('status', 'active')
        category_id = params.get('category_id')
        search_query = params.get('search', '')
        
        sql = """
            SELECT 
                sp.*,
                b.name as brand_name,
                gp.name as generic_product_name,
                c.name as category_name,
                CASE 
                    WHEN sp.current_stock = 0 THEN 'out_of_stock'
                    WHEN sp.current_stock <= sp.min_stock_level THEN 'low_stock'
                    ELSE 'in_stock'
                END as stock_status,
                (sp.current_stock <= sp.min_stock_level AND sp.current_stock > 0) as is_low_stock,
                (sp.current_stock = 0) as is_out_of_stock
            FROM store_products sp
            LEFT JOIN brands b ON sp.brand_id = b.id
            LEFT JOIN generic_products gp ON sp.generic_product_id = gp.id
            LEFT JOIN categories c ON gp.category_id = c.id
            WHERE sp.store_id = %s
        """
        
        params_list = [store_id]
        
        if status != 'all':
            sql += " AND sp.status = %s"
            params_list.append(status)
        
        if category_id:
            sql += " AND gp.category_id = %s"
            params_list.append(category_id)
        
        if search_query:
            sql += """ AND (
                LOWER(sp.product_name) LIKE %s OR
                LOWER(sp.sku) LIKE %s OR
                sp.barcode = %s
            )"""
            search_pattern = f'%{search_query.lower()}%'
            params_list.extend([search_pattern, search_pattern, search_query])
        
        sql += " ORDER BY sp.product_name"
        
        cur.execute(sql, params_list)
        products = cur.fetchall()
        
        # Get summary statistics
        cur.execute("""
            SELECT 
                COUNT(*) as total_products,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_products,
                COUNT(CASE WHEN current_stock = 0 THEN 1 END) as out_of_stock,
                COUNT(CASE WHEN current_stock <= min_stock_level AND current_stock > 0 THEN 1 END) as low_stock,
                SUM(current_stock * selling_price) as total_stock_value
            FROM store_products
            WHERE store_id = %s
        """, [store_id])
        
        summary = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return create_response(200, {
            'success': True,
            'products': products,
            'summary': summary
        })
        
    except Exception as e:
        print(f"Error fetching store products: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def create_store_product(event: dict) -> dict:
    """Create a new product for a store"""
    try:
        body = json.loads(event.get('body', '{}'))
        store_id = body.get('store_id')
        
        if not store_id:
            return create_response(400, {
                'success': False,
                'error': 'store_id is required'
            })
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Generate product ID and SKU if not provided
        product_id = str(uuid.uuid4())
        sku = body.get('sku') or f"SKU-{product_id[:8].upper()}"
        
        # Insert product
        cur.execute("""
            INSERT INTO store_products (
                id, store_id, generic_product_id, sku, barcode,
                product_name, brand_id, variant_type, size, size_unit,
                mrp, cost_price, selling_price, tax_rate, discount_percentage,
                current_stock, min_stock_level, max_stock_level,
                reorder_point, reorder_quantity, description,
                status, is_returnable, is_perishable
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) RETURNING *
        """, (
            product_id, store_id, body.get('generic_product_id'),
            sku, body.get('barcode'),
            body.get('product_name'), body.get('brand_id'),
            body.get('variant_type'), body.get('size'), body.get('size_unit'),
            body.get('mrp'), body.get('cost_price'), body.get('selling_price'),
            body.get('tax_rate', 0), body.get('discount_percentage', 0),
            body.get('current_stock', 0), body.get('min_stock_level', 10),
            body.get('max_stock_level', 1000),
            body.get('reorder_point', 10), body.get('reorder_quantity', 50),
            body.get('description'),
            body.get('status', 'active'), body.get('is_returnable', True),
            body.get('is_perishable', False)
        ))
        
        new_product = cur.fetchone()
        
        # Create initial stock movement record
        cur.execute("""
            INSERT INTO stock_movements (
                store_product_id, movement_type, quantity,
                balance_after, reference_type, reason
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            product_id, 'purchase', body.get('current_stock', 0),
            body.get('current_stock', 0), 'initial_stock',
            'Initial stock entry'
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return create_response(201, {
            'success': True,
            'product': new_product,
            'message': 'Product created successfully'
        })
        
    except Exception as e:
        print(f"Error creating product: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def update_product_stock(event: dict) -> dict:
    """Update stock levels for a product"""
    try:
        path_params = event.get('pathParameters', {}) or {}
        product_id = path_params.get('product_id')
        body = json.loads(event.get('body', '{}'))
        
        if not product_id:
            return create_response(400, {
                'success': False,
                'error': 'product_id is required'
            })
        
        movement_type = body.get('movement_type', 'adjustment')
        quantity = body.get('quantity', 0)
        reason = body.get('reason', '')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get current stock
        cur.execute("""
            SELECT current_stock, min_stock_level, max_stock_level
            FROM store_products
            WHERE id = %s
        """, [product_id])
        
        product = cur.fetchone()
        if not product:
            return create_response(404, {
                'success': False,
                'error': 'Product not found'
            })
        
        current_stock = float(product['current_stock'])
        
        # Calculate new stock based on movement type
        if movement_type == 'in' or movement_type == 'purchase':
            new_stock = current_stock + quantity
        elif movement_type == 'out' or movement_type == 'sale':
            new_stock = current_stock - quantity
        elif movement_type == 'set':
            new_stock = quantity
        elif movement_type == 'adjustment':
            new_stock = current_stock + quantity  # Can be positive or negative
        else:
            return create_response(400, {
                'success': False,
                'error': f'Invalid movement_type: {movement_type}'
            })
        
        # Validate new stock level
        if new_stock < 0:
            return create_response(400, {
                'success': False,
                'error': 'Stock cannot be negative'
            })
        
        # Update stock
        cur.execute("""
            UPDATE store_products
            SET current_stock = %s,
                last_stock_update = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
        """, [new_stock, product_id])
        
        updated_product = cur.fetchone()
        
        # Record stock movement
        cur.execute("""
            INSERT INTO stock_movements (
                store_product_id, movement_type, quantity,
                balance_after, reference_type, reason, performed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            product_id, movement_type,
            quantity if movement_type in ['in', 'purchase', 'set'] else -quantity,
            new_stock, 'manual_update', reason,
            body.get('performed_by')
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Check if low stock alert is needed
        alert_message = None
        if new_stock <= float(product['min_stock_level']):
            alert_message = 'Product is now low on stock' if new_stock > 0 else 'Product is out of stock'
        
        return create_response(200, {
            'success': True,
            'product': updated_product,
            'previous_stock': current_stock,
            'new_stock': new_stock,
            'alert': alert_message,
            'message': 'Stock updated successfully'
        })
        
    except Exception as e:
        print(f"Error updating stock: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def get_stock_movements(event: dict) -> dict:
    """Get stock movement history for a product or store"""
    try:
        params = event.get('queryStringParameters', {}) or {}
        product_id = params.get('product_id')
        store_id = params.get('store_id')
        limit = int(params.get('limit', 50))
        offset = int(params.get('offset', 0))
        
        if not product_id and not store_id:
            return create_response(400, {
                'success': False,
                'error': 'Either product_id or store_id is required'
            })
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT 
                sm.*,
                sp.product_name,
                sp.sku
            FROM stock_movements sm
            JOIN store_products sp ON sm.store_product_id = sp.id
            WHERE 1=1
        """
        
        params_list = []
        
        if product_id:
            sql += " AND sm.store_product_id = %s"
            params_list.append(product_id)
        
        if store_id:
            sql += " AND sp.store_id = %s"
            params_list.append(store_id)
        
        sql += " ORDER BY sm.created_at DESC LIMIT %s OFFSET %s"
        params_list.extend([limit, offset])
        
        cur.execute(sql, params_list)
        movements = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return create_response(200, {
            'success': True,
            'movements': movements,
            'count': len(movements)
        })
        
    except Exception as e:
        print(f"Error fetching stock movements: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

def get_low_stock_alerts(event: dict) -> dict:
    """Get products with low stock for a store"""
    try:
        params = event.get('queryStringParameters', {}) or {}
        store_id = params.get('store_id')
        
        if not store_id:
            return create_response(400, {
                'success': False,
                'error': 'store_id is required'
            })
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get low stock products
        cur.execute("""
            SELECT 
                sp.*,
                b.name as brand_name,
                gp.name as generic_product_name,
                c.name as category_name,
                CASE 
                    WHEN sp.current_stock = 0 THEN 'out_of_stock'
                    ELSE 'low_stock'
                END as alert_type,
                sp.min_stock_level - sp.current_stock as shortage_quantity
            FROM store_products sp
            LEFT JOIN brands b ON sp.brand_id = b.id
            LEFT JOIN generic_products gp ON sp.generic_product_id = gp.id
            LEFT JOIN categories c ON gp.category_id = c.id
            WHERE sp.store_id = %s
                AND sp.status = 'active'
                AND sp.current_stock <= sp.min_stock_level
            ORDER BY 
                sp.current_stock = 0 DESC,
                (sp.min_stock_level - sp.current_stock) DESC
        """, [store_id])
        
        alerts = cur.fetchall()
        
        # Get expiring products (within 7 days)
        cur.execute("""
            SELECT 
                pb.*,
                sp.product_name,
                sp.sku
            FROM product_batches pb
            JOIN store_products sp ON pb.store_product_id = sp.id
            WHERE sp.store_id = %s
                AND pb.expiry_date IS NOT NULL
                AND pb.expiry_date <= CURRENT_DATE + INTERVAL '7 days'
                AND pb.remaining_quantity > 0
            ORDER BY pb.expiry_date
        """, [store_id])
        
        expiring_products = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return create_response(200, {
            'success': True,
            'low_stock_alerts': alerts,
            'expiring_products': expiring_products,
            'total_alerts': len(alerts) + len(expiring_products)
        })
        
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return create_response(500, {
            'success': False,
            'error': str(e)
        })

# ============================================
# MAIN HANDLER
# ============================================

def lambda_handler(event, context):
    """Main Lambda handler for inventory management"""
    
    # Handle CORS preflight
    if event.get('httpMethod') == 'OPTIONS':
        return create_response(200, {'message': 'OK'})
    
    # Get request details
    path = event.get('path', '')
    method = event.get('httpMethod', '')
    
    # Route to appropriate handler
    try:
        # Generic Products endpoints
        if path == '/api/v1/inventory/generic-products' and method == 'GET':
            return get_generic_products(event)
        
        elif path == '/api/v1/inventory/categories' and method == 'GET':
            return get_categories(event)
        
        # Store Products endpoints
        elif path == '/api/v1/inventory/products' and method == 'GET':
            return get_store_products(event)
        
        elif path == '/api/v1/inventory/products' and method == 'POST':
            return create_store_product(event)
        
        elif path.startswith('/api/v1/inventory/products/') and '/stock' in path and method == 'PUT':
            return update_product_stock(event)
        
        elif path == '/api/v1/inventory/stock-movements' and method == 'GET':
            return get_stock_movements(event)
        
        elif path == '/api/v1/inventory/alerts' and method == 'GET':
            return get_low_stock_alerts(event)
        
        else:
            return create_response(404, {
                'success': False,
                'error': f'Endpoint not found: {method} {path}'
            })
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return create_response(500, {
            'success': False,
            'error': 'Internal server error'
        })

# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'httpMethod': 'GET',
        'path': '/api/v1/inventory/products',
        'queryStringParameters': {
            'store_id': 'test-store-123'
        }
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))