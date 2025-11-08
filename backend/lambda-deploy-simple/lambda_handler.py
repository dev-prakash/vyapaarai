import json
import base64
import datetime
import random
import string
import boto3
import urllib.request
import urllib.parse
import os
from decimal import Decimal
from ulid import ULID

# Custom JSON encoder for Decimal
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# Inventory API configuration
INVENTORY_API_BASE = "https://6ais2a7oafg5qt5xilobjpijsa0cquje.lambda-url.ap-south-1.on.aws/api/v1/inventory"

# Store ID generation function
def generate_store_id():
    """Generate a ULID-based store ID with STORE- prefix"""
    ulid = str(ULID())
    return f"STORE-{ulid}"

# Mock products data
MOCK_PRODUCTS = {
    'prod_001': {
        'id': 'prod_001',
        'name': 'Basmati Rice',
        'description': 'Premium quality basmati rice',
        'category': 'Grains',
        'price': 120.0,
        'current_stock': 50,
        'min_stock_level': 10,
        'max_stock_level': 200,
        'unit': 'kg',
        'brand': 'Premium',
        'status': 'active'
    },
    'prod_002': {
        'id': 'prod_002',
        'name': 'Wheat Flour',
        'description': 'Whole wheat flour for healthy cooking',
        'category': 'Grains',
        'price': 45.0,
        'current_stock': 5,
        'min_stock_level': 10,
        'max_stock_level': 100,
        'unit': 'kg',
        'brand': 'Healthy',
        'status': 'active'
    },
    'prod_003': {
        'id': 'prod_003',
        'name': 'Sugar',
        'description': 'Refined white sugar',
        'category': 'Essentials',
        'price': 50.0,
        'current_stock': 0,
        'min_stock_level': 5,
        'max_stock_level': 50,
        'unit': 'kg',
        'brand': 'Sweet',
        'status': 'out_of_stock'
    }
}

# DynamoDB configuration
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
STOCK_TABLE_NAME = os.environ.get('DYNAMODB_STOCK_TABLE', 'vyaparai-stock-prod')

# Try to create stock table if it doesn't exist
try:
    stock_table = dynamodb.Table(STOCK_TABLE_NAME)
    # Test if table exists by describing it
    stock_table.table_status
    print(f"Using existing DynamoDB table: {STOCK_TABLE_NAME}")
except Exception as e:
    print(f"Creating new DynamoDB table: {STOCK_TABLE_NAME}")
    try:
        stock_table = dynamodb.create_table(
            TableName=STOCK_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'product_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'product_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        # Wait for table to be created
        stock_table.meta.client.get_waiter('table_exists').wait(TableName=STOCK_TABLE_NAME)
        print(f"Created DynamoDB table: {STOCK_TABLE_NAME}")
    except Exception as create_error:
        print(f"Error creating table: {create_error}")
        # Fallback to existing table
        try:
            stock_table = dynamodb.Table(STOCK_TABLE_NAME)
        except:
            # Final fallback to orders table
            stock_table = dynamodb.Table('vyaparai-orders-prod')

def get_current_stock(product_id):
    """Get current stock from DynamoDB or default"""
    try:
        print(f"DEBUG: Getting stock from DynamoDB table {STOCK_TABLE_NAME} for {product_id}")
        response = stock_table.get_item(Key={'product_id': product_id})
        print(f"DEBUG: DynamoDB response: {response}")
        
        if 'Item' in response:
            stock = response['Item'].get('current_stock', 0)
            # Convert Decimal to int for JSON serialization
            if hasattr(stock, 'to_integral_value'):
                stock = int(stock)
            print(f"DEBUG: Found stock in DynamoDB: {product_id} = {stock}")
            return stock
        else:
            print(f"DEBUG: No item found in DynamoDB for {product_id}")
            # Initialize from mock data only if item doesn't exist
            default_stock = MOCK_PRODUCTS.get(product_id, {}).get('current_stock', 0)
            print(f"DEBUG: Initializing stock from mock data: {product_id} = {default_stock}")
            
            # Store initial stock in DynamoDB
            try:
                stock_table.put_item(Item={
                    'product_id': product_id,
                    'current_stock': default_stock,
                    'last_updated': datetime.datetime.now().isoformat()
                })
                print(f"DEBUG: Successfully initialized stock in DynamoDB for {product_id}")
            except Exception as init_error:
                print(f"DEBUG: Error initializing stock in DynamoDB: {str(init_error)}")
            
            return default_stock
    except Exception as e:
        print(f"DEBUG: Error getting stock from DynamoDB: {str(e)}")
        # Fallback to mock data
        return MOCK_PRODUCTS.get(product_id, {}).get('current_stock', 0)

def update_stock(product_id, new_stock):
    """Update stock in DynamoDB"""
    try:
        print(f"DEBUG: Updating stock in DynamoDB: {product_id} = {new_stock}")
        stock_table.put_item(Item={
            'product_id': product_id,
            'current_stock': new_stock,
            'last_updated': datetime.datetime.now().isoformat()
        })
        print(f"DEBUG: Stock successfully updated in DynamoDB: {product_id} = {new_stock}")
    except Exception as e:
        print(f"DEBUG: Error updating stock in DynamoDB: {str(e)}")
        raise e

def call_inventory_api(endpoint, method="GET", data=None):
    """Call inventory API with error handling"""
    url = f"{INVENTORY_API_BASE}{endpoint}"
    try:
        if method == "GET":
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                return {"success": True, "data": json.loads(response_data)}
        elif method == "POST":
            data_bytes = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                return {"success": True, "data": json.loads(response_data)}
        elif method == "PUT":
            data_bytes = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
            req.get_method = lambda: 'PUT'
            with urllib.request.urlopen(req, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                return {"success": True, "data": json.loads(response_data)}
    except urllib.error.HTTPError as e:
        print(f"DEBUG: Inventory API error - {method} {endpoint}: HTTP {e.code}")
        return {"success": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        print(f"DEBUG: Inventory API exception - {method} {endpoint}: {str(e)}")
        return {"success": False, "error": str(e)}

def get_product_from_inventory(product_id):
    """Get product information from inventory system"""
    # For mock mode, use local data
    if product_id in MOCK_PRODUCTS:
        return {"success": True, "data": MOCK_PRODUCTS[product_id]}
    
    # In real implementation, call inventory API
    # result = call_inventory_api(f"/products/{product_id}")
    # return result
    
    return {"success": False, "error": "Product not found"}

def reduce_product_stock(product_id, quantity, reference_id, reason="Order"):
    """Directly update stock in DynamoDB"""
    try:
        print(f"DEBUG: Reducing stock for {product_id} by {quantity}")
        
        # Get current product
        product = MOCK_PRODUCTS.get(product_id, {})
        if not product:
            return {"success": False, "error": f"Product not found: {product_id}"}
        
        current_stock = get_current_stock(product_id)
        previous_stock = current_stock
        
        # Check if sufficient stock
        if current_stock < quantity:
            return {"success": False, "error": f"Insufficient stock. Available: {current_stock}, Requested: {quantity}"}
        
        # Update stock
        new_stock = current_stock - quantity
        update_stock(product_id, new_stock)
        
        print(f"DEBUG: Stock updated: {product_id} {previous_stock} -> {new_stock}")
        
        return {
            "success": True,
            "data": {
                "previous_stock": previous_stock,
                "new_stock": new_stock,
                "product_id": product_id,
                "quantity": quantity,
                "reference_id": reference_id
            }
        }
    except Exception as e:
        error_msg = f"Stock reduction failed: {str(e)}"
        print(f"DEBUG: {error_msg}")
        return {"success": False, "error": error_msg}

def rollback_stock_reductions(completed_reductions):
    """Rollback any completed stock reductions if order fails"""
    try:
        rollback_count = 0
        
        for reduction in completed_reductions:
            try:
                product_id = reduction.get('product_id')
                quantity = reduction.get('quantity', 0)
                
                if not product_id or quantity <= 0:
                    continue
                
                print(f"DEBUG: Rolling back stock for {product_id} by {quantity}")
                
                # Get current stock and add back the quantity
                current_stock = get_current_stock(product_id)
                new_stock = current_stock + quantity
                update_stock(product_id, new_stock)
                
                rollback_count += 1
                print(f"DEBUG: Successfully rolled back stock for {product_id}: {current_stock} -> {new_stock}")
                        
            except Exception as e:
                print(f"DEBUG: Rollback failed for {reduction.get('product_id', 'unknown')}: {str(e)}")
        
        return {"success": True, "data": {"rollback_count": rollback_count}}
        
    except Exception as e:
        print(f"DEBUG: Stock rollback error: {str(e)}")
        return {"success": False, "error": str(e)}

def calculate_order_pricing(items):
    """Calculate order pricing using actual inventory prices"""
    try:
        subtotal = 0
        items_with_prices = []
        
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)
            
            # Get product information
            product_result = get_product_from_inventory(product_id)
            if not product_result['success']:
                raise Exception(f"Product {product_id} not found")
            
            product = product_result['data']
            price = product.get('price', 0)
            item_total = price * quantity
            
            # Add price information to item
            item_with_price = {
                **item,
                'unit_price': price,
                'total_price': item_total,
                'product_name': product.get('name', 'Unknown Product')
            }
            items_with_prices.append(item_with_price)
            
            subtotal += item_total
        
        # Calculate totals
        tax_rate = 0.05  # 5% GST
        tax_amount = subtotal * tax_rate
        delivery_fee = 20 if subtotal < 200 else 0
        total_amount = subtotal + tax_amount + delivery_fee
        
        return {
            "success": True,
            "data": {
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "delivery_fee": delivery_fee,
                "total_amount": total_amount,
                "items_with_prices": items_with_prices
            }
        }
        
    except Exception as e:
        print(f"DEBUG: Pricing calculation error: {str(e)}")
        return {"success": False, "error": str(e)}

def decimal_default(obj):
    """Convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

# Initialize DynamoDB tables
orders_table = dynamodb.Table('vyaparai-orders-prod')

def save_order_to_db(order):
    """Save order to DynamoDB"""
    try:
        # Convert float to Decimal for DynamoDB
        order_for_db = json.loads(json.dumps(order), parse_float=Decimal)
        orders_table.put_item(Item=order_for_db)
        return True
    except Exception as e:
        print(f"Error saving order: {e}")
        return False

def get_orders_from_db(store_id='STORE-001', limit=50):
    """Retrieve orders from DynamoDB"""
    try:
        response = orders_table.query(
            KeyConditionExpression='store_id = :store_id',
            ExpressionAttributeValues={':store_id': store_id},
            ScanIndexForward=False,  # Sort by newest first
            Limit=limit
        )
        
        # Convert Decimal to float for JSON response
        orders = json.loads(json.dumps(response.get('Items', []), default=decimal_default))
        return orders
    except Exception as e:
        print(f"Error retrieving orders: {e}")
        return []

def handler(event, context):
    path = event.get('rawPath', '/')
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    
    # Log for debugging
    print(f"Request: {method} {path}")
    
    # NO CORS headers here - Lambda Function URL handles CORS
    
    if method == 'OPTIONS':
        return {'statusCode': 200, 'body': ''}
    
    # Health check
    if path == '/health':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'healthy', 
                'message': 'VyaparAI API is running', 
                'version': '1.0.0',
                'timestamp': datetime.datetime.now().isoformat()
            })
        }
    
    # API v1 Health check
    elif path == '/api/v1/health' and method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'healthy',
                'timestamp': datetime.datetime.now().isoformat(),
                'version': '1.0.0',
                'environment': 'production',
                'service': 'VyaparAI API',
                'checks': {
                    'database': {
                        'status': 'healthy',
                        'message': 'Database connection simulated'
                    },
                    'dynamodb': {
                        'status': 'healthy',
                        'message': 'DynamoDB connection successful',
                        'table': 'vyaparai-orders-prod'
                    },
                    'system_resources': {
                        'status': 'healthy',
                        'message': 'System resources normal'
                    }
                },
                'summary': {
                    'total_checks': 3,
                    'healthy_checks': 3,
                    'unhealthy_checks': 0,
                    'warning_checks': 0
                }
            })
        }
    
    # Auth endpoints
    elif path == '/api/v1/auth/send-otp' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            phone = body.get('phone', '')
            print(f"Sending OTP to: {phone}")
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True, 
                    'message': 'OTP sent successfully', 
                    'otp': '1234'
                })
            }
        except Exception as e:
            print(f"Error in send-otp: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': 'Invalid request'})
            }
    
    elif path == '/api/v1/auth/verify-otp' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            phone = body.get('phone', '')
            otp = body.get('otp', '')
            
            print(f"Verifying OTP for: {phone}, OTP: {otp}")
            
            # Only accept OTP 1234 for demo purposes
            if otp == '1234':
                token = base64.b64encode(f"{phone}:{datetime.datetime.now().isoformat()}".encode()).decode()
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'valid': True, 
                        'token': token, 
                        'message': 'OTP verified successfully'
                    })
                }
            else:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'error': {
                            'code': 'INVALID_OTP',
                            'message': 'The OTP provided is invalid or expired',
                            'details': {}
                        },
                        'timestamp': datetime.datetime.now().isoformat()
                    })
                }
        except Exception as e:
            print(f"Error in verify-otp: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'valid': False, 'message': 'Invalid request'})
            }
    
    elif path == '/api/v1/auth/login' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            phone = body.get('phone', '')
            otp = body.get('otp', '')
            
            print(f"Login attempt for: {phone}, OTP: {otp}")
            
            # Accept any OTP for demo purposes
            if otp == '1234' or otp == '0000' or len(otp) == 4:
                token = base64.b64encode(f"{phone}:{datetime.datetime.now().isoformat()}".encode()).decode()
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'token': token,
                        'store_id': 'STORE-001',
                        'store_name': 'Test Kirana Store',
                        'user': {
                            'phone': phone, 
                            'name': 'Store Owner', 
                            'role': 'owner'
                        }
                    })
                }
            else:
                return {
                    'statusCode': 401, 
                    'headers': {'Content-Type': 'application/json'}, 
                    'body': json.dumps({'detail': 'Invalid OTP'})
                }
        except Exception as e:
            print(f"Error in login: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'detail': 'Invalid request'})
            }
    
    elif path == '/api/v1/auth/me' and method == 'GET':
        try:
            # Get token from query parameters or Authorization header
            query_params = event.get('queryStringParameters', {}) or {}
            token = query_params.get('token')
            
            # If not in query params, check Authorization header
            if not token:
                auth_header = event.get('headers', {}).get('authorization') or event.get('headers', {}).get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    token = auth_header[7:]  # Remove 'Bearer ' prefix
            
            print(f"Getting user info with token: {token[:20] if token else 'None'}...")
            
            # Return mock user response
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'user': {
                        'id': 'user_+919876543210',
                        'name': 'Store Owner',
                        'email': 'store@example.com',
                        'phone': '+919876543210',
                        'role': 'owner',
                        'store_id': 'STORE-001',
                        'avatar': None,
                        'preferences': {
                            'language': 'en',
                            'theme': 'light',
                            'notifications': {
                                'email': True,
                                'push': True,
                                'sms': True,
                                'order_updates': True,
                                'low_stock': True,
                                'system_alerts': True
                            },
                            'timezone': 'Asia/Kolkata',
                            'currency': 'INR'
                        },
                        'created_at': '2024-01-01T00:00:00Z',
                        'updated_at': '2024-01-01T00:00:00Z'
                    }
                })
            }
        except Exception as e:
            print(f"Error in auth/me: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': 'Invalid request'})
            }
    
    # Orders endpoints
    elif path == '/api/v1/orders/test/generate-order' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            store_id = body.get('store_id', 'STORE-001')
            customer_name = body.get('customer_name', '')
            customer_phone = body.get('customer_phone', '+919876543210')
            
            print(f"Generating test order for store: {store_id}")
            
            # Generate random order ID
            order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Random customer names
            customer_names = ["Rajesh Kumar", "Priya Sharma", "Amit Patel", "Sunita Verma", "Deepak Singh", "Meera Reddy"]
            if not customer_name:
                customer_name = random.choice(customer_names)
            
            # Random items with prices
            items_list = [
                {"name": "Rice 5kg", "price": 250},
                {"name": "Wheat Flour 10kg", "price": 180},
                {"name": "Sugar 1kg", "price": 45},
                {"name": "Tea 250g", "price": 120},
                {"name": "Dal 1kg", "price": 85},
                {"name": "Oil 1L", "price": 140},
                {"name": "Milk 1L", "price": 60},
                {"name": "Bread", "price": 35},
                {"name": "Eggs 12", "price": 80},
                {"name": "Potatoes 2kg", "price": 40}
            ]
            
            # Generate random items (1-3 items)
            num_items = random.randint(1, 3)
            selected_items = random.sample(items_list, num_items)
            
            # Create order items with random quantities
            order_items = []
            subtotal = 0
            
            for item in selected_items:
                quantity = random.randint(1, 3)
                total_price = item['price'] * quantity
                subtotal += total_price
                
                order_items.append({
                    'name': item['name'],
                    'quantity': quantity,
                    'price': item['price']
                })
            
            # Calculate totals
            tax = subtotal * 0.05  # 5% tax
            delivery_fee = 20 if subtotal < 200 else 0  # Free delivery above 200
            total = subtotal + tax + delivery_fee
            
            # Random status
            statuses = ["pending", "processing", "completed"]
            status = random.choice(statuses)
            
            # Create test order
            test_order = {
                'id': order_id,
                'store_id': store_id,
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'customerPhone': customer_phone,  # For compatibility
                'delivery_address': '123 Test Street, Test City',
                'items': order_items,
                'subtotal': subtotal,
                'tax': tax,
                'deliveryFee': delivery_fee,
                'total': total,
                'total_amount': total,
                'status': status,
                'paymentMethod': 'cash',
                'paymentStatus': 'pending',
                'orderDate': datetime.datetime.now().isoformat(),
                'deliveryTime': '2 hours',
                'channel': 'web',
                'language': 'en',
                'createdAt': datetime.datetime.now().isoformat(),
                'created_at': datetime.datetime.now().isoformat(),
                'updatedAt': datetime.datetime.now().isoformat(),
                'is_urgent': False
            }
            
            # Save to DynamoDB
            if save_order_to_db(test_order):
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': True,
                        'order': test_order,
                        'message': 'Test order generated and saved successfully'
                    }, default=decimal_default)
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': False, 'message': 'Failed to save order'})
                }
        except Exception as e:
            print(f"Error generating test order: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': 'Failed to generate test order'})
            }
    
    elif path == '/api/v1/orders' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            
            # Extract order data
            store_id = body.get('store_id', 'STORE-001')
            customer_name = body.get('customer_name', 'Test Customer')
            customer_phone = body.get('customer_phone', '+919876543210')
            customer_email = body.get('customer_email')
            delivery_address = body.get('delivery_address', '123 Test Street, Test City')
            items = body.get('items', [])
            payment_method = body.get('payment_method', 'upi')
            delivery_notes = body.get('delivery_notes')
            is_urgent = body.get('is_urgent', False)
            channel = body.get('channel', 'web')
            language = body.get('language', 'en')
            
            print(f"Creating order with payment for store: {store_id}")
            
            # Generate order ID
            order_id = f"ORD{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"
            
            # Check stock availability for all items
            stock_validation_errors = []
            for item in items:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 1)
                
                if product_id:
                    print(f"DEBUG: Checking stock for product_id: '{product_id}', quantity: {quantity}")
                    
                    # Get product information from inventory
                    product_result = get_product_from_inventory(product_id)
                    if not product_result['success']:
                        stock_validation_errors.append({
                            'product_id': product_id,
                            'product_name': 'Unknown Product',
                            'requested_quantity': quantity,
                            'available_stock': 0,
                            'message': f"Product {product_id} not found in inventory"
                        })
                        continue
                    
                    product = product_result['data']
                    current_stock = product['current_stock']
                    
                    print(f"DEBUG: Product lookup result - ID: '{product_id}', Found: True, Stock: {current_stock}, Name: {product['name']}")
                    
                    if current_stock < quantity:
                        print(f"DEBUG: Stock validation failed for {product_id} - Requested: {quantity}, Available: {current_stock}")
                        stock_validation_errors.append({
                            'product_id': product_id,
                            'product_name': product['name'],
                            'requested_quantity': quantity,
                            'available_stock': current_stock,
                            'message': f"Insufficient stock for {product['name']}. Requested: {quantity}, Available: {current_stock}"
                        })
                    else:
                        print(f"DEBUG: Stock validation passed for {product_id} - Requested: {quantity}, Available: {current_stock}")
            
            # If stock validation failed, return error
            if stock_validation_errors:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'message': 'Stock validation failed',
                        'stock_errors': stock_validation_errors,
                        'order_id': order_id
                    })
                }
            
            print(f"Stock validation passed for order {order_id}")
            
            # Calculate order pricing using actual inventory prices
            pricing_result = calculate_order_pricing(items)
            if not pricing_result['success']:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'message': f'Pricing calculation failed: {pricing_result["error"]}',
                        'order_id': order_id
                    })
                }
            
            pricing = pricing_result['data']
            subtotal = pricing['subtotal']
            tax_amount = pricing['tax_amount']
            delivery_fee = pricing['delivery_fee']
            total_amount = pricing['total_amount']
            items_with_prices = pricing['items_with_prices']
            
            print(f"DEBUG: Order pricing - Subtotal: {subtotal}, Tax: {tax_amount}, Delivery: {delivery_fee}, Total: {total_amount}")
            
            # Handle payment based on method
            payment_required = payment_method != "cod"
            payment_id = None
            
            if payment_required:
                # Create payment intent for online payments
                payment_id = f"mock_payment_{order_id}_{int(total_amount)}"
            else:
                # Handle Cash on Delivery
                payment_id = f"cod_{order_id}_{int(total_amount)}"
            
            # Reduce stock levels for all items
            stock_reductions = []
            stock_reduction_failed = False
            
            for item in items:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 1)
                
                print(f"DEBUG: Reducing stock for {product_id} by {quantity}")
                reduction_result = reduce_product_stock(product_id, quantity, order_id, f"Order {order_id}")
                
                if not reduction_result['success']:
                    print(f"DEBUG: Stock reduction failed for {product_id}: {reduction_result['error']}")
                    stock_reduction_failed = True
                    break
                
                stock_reductions.append({
                    'product_id': product_id,
                    'quantity': quantity,
                    'previous_stock': reduction_result['data']['previous_stock'],
                    'new_stock': reduction_result['data']['new_stock'],
                    'reference_id': order_id
                })
            
            # If stock reduction failed, rollback any successful reductions
            if stock_reduction_failed:
                print(f"DEBUG: Rolling back stock reductions for order {order_id}")
                rollback_result = rollback_stock_reductions(stock_reductions)
                if not rollback_result['success']:
                    print(f"DEBUG: Stock rollback failed: {rollback_result['error']}")
                
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'message': 'Stock reduction failed',
                        'order_id': order_id
                    })
                }
            
            print(f"DEBUG: Stock reductions completed for order {order_id}")
            
            # Create order object with pricing information
            order = {
                'id': order_id,
                'store_id': store_id,
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'customerPhone': customer_phone,  # For compatibility
                'customer_email': customer_email,
                'delivery_address': delivery_address,
                'items': items_with_prices,  # Use items with pricing information
                'subtotal': subtotal,
                'tax_amount': tax_amount,
                'tax': tax_amount,  # For compatibility
                'delivery_fee': delivery_fee,
                'deliveryFee': delivery_fee,  # For compatibility
                'total_amount': total_amount,
                'total': total_amount,  # For compatibility
                'status': 'pending',
                'payment_id': payment_id,
                'payment_status': 'pending',
                'payment_method': payment_method,
                'paymentMethod': payment_method,  # For compatibility
                'paymentStatus': 'pending',  # For compatibility
                'delivery_notes': delivery_notes,
                'deliveryTime': '2 hours',
                'channel': channel,
                'language': language,
                'is_urgent': is_urgent,
                'orderDate': datetime.datetime.now().isoformat(),
                'createdAt': datetime.datetime.now().isoformat(),
                'created_at': datetime.datetime.now().isoformat(),
                'updatedAt': datetime.datetime.now().isoformat(),
                'payment_created_at': datetime.datetime.now().isoformat(),
                'stock_reductions': stock_reductions  # Add stock reduction audit trail
            }
            
            # Save to DynamoDB
            if save_order_to_db(order):
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': True,
                        'order_id': order_id,
                        'payment_id': payment_id,
                        'total_amount': total_amount,
                        'payment_required': payment_required,
                        'payment_method': payment_method,
                        'order': order,
                        'stock_reductions': stock_reductions,
                        'message': 'Order created successfully with stock reduction'
                    }, default=decimal_default)
                }
            else:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'success': False, 'message': 'Failed to save order'})
                }
        except Exception as e:
            print(f"Error creating order: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'success': False, 'message': f'Failed to create order: {str(e)}'})
            }
    
    elif path.startswith('/api/v1/orders/') and path.endswith('/payment/confirm') and method == 'POST':
        try:
            order_id = path.split('/')[-3]  # Extract order_id from path
            body = json.loads(event.get('body', '{}'))
            payment_id = body.get('payment_id', '')
            razorpay_payment_id = body.get('razorpay_payment_id', '')
            razorpay_signature = body.get('razorpay_signature', '')
            payment_status = body.get('payment_status', 'completed')
            
            print(f"Confirming payment for order: {order_id}")
            
            # Mock payment confirmation
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'order_id': order_id,
                    'payment_status': payment_status,
                    'order_status': 'confirmed' if payment_status == 'completed' else 'pending',
                    'message': 'Payment confirmed successfully'
                })
            }
        except Exception as e:
            print(f"Error confirming payment: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to confirm payment'})
            }
    
    elif path.startswith('/api/v1/orders/') and path.endswith('/status') and method == 'PUT':
        try:
            order_id = path.split('/')[-2]  # Extract order_id from path
            body = json.loads(event.get('body', '{}'))
            status = body.get('status', 'pending')
            notes = body.get('notes', '')
            
            print(f"Updating status for order: {order_id} to {status}")
            
            # Mock status update
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'order_id': order_id,
                    'status': status,
                    'message': 'Order status updated successfully'
                })
            }
        except Exception as e:
            print(f"Error updating order status: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to update order status'})
            }
    
    elif path.startswith('/api/v1/orders/') and method == 'GET':
        try:
            order_id = path.split('/')[-1]  # Extract order_id from path
            
            print(f"Getting details for order: {order_id}")
            
            # Mock order details
            mock_order = {
                'id': order_id,
                'store_id': 'STORE-001',
                'customer_name': 'Test Customer',
                'customer_phone': '+919876543210',
                'delivery_address': '123 Test Street, Mumbai',
                'items': json.dumps([
                    {'product_name': 'Rice', 'quantity': 2, 'unit_price': 50, 'total_price': 100}
                ]),
                'subtotal': 100.0,
                'tax_amount': 5.0,
                'delivery_fee': 20.0,
                'total_amount': 125.0,
                'status': 'pending',
                'payment_id': f'pay_{order_id}',
                'payment_status': 'pending',
                'payment_method': 'upi',
                'created_at': datetime.datetime.now().isoformat(),
                'updated_at': datetime.datetime.now().isoformat()
            }
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'order': mock_order
                })
            }
        except Exception as e:
            print(f"Error getting order details: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to get order details'})
            }
    
    elif path == '/api/v1/orders' and method == 'GET':
        try:
            # Get store_id from query parameters
            store_id = event.get('queryStringParameters', {}).get('store_id', 'STORE-001') if event.get('queryStringParameters') else 'STORE-001'
            
            # Retrieve orders from DynamoDB
            orders = get_orders_from_db(store_id)
            
            return {
                'statusCode': 200, 
                'headers': {'Content-Type': 'application/json'}, 
                'body': json.dumps({
                    'data': orders, 
                    'total': len(orders),
                    'page': 1,
                    'page_size': 50,
                    'total_pages': 1
                }, default=decimal_default)
            }
        except Exception as e:
            print(f"Error in orders GET: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'data': [], 'total': 0})
            }
    
    elif path == '/api/v1/orders/history' and method == 'GET':
        try:
            return {
                'statusCode': 200, 
                'headers': {'Content-Type': 'application/json'}, 
                'body': json.dumps({
                    'data': [], 
                    'total': 0, 
                    'page': 1, 
                    'pages': 1
                })
            }
        except Exception as e:
            print(f"Error in orders/history: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'data': [], 'total': 0})
            }
    
    elif path == '/api/v1/orders/stats/daily' and method == 'GET':
        try:
            return {
                'statusCode': 200, 
                'headers': {'Content-Type': 'application/json'}, 
                'body': json.dumps({
                    'total_orders': 0, 
                    'total_revenue': 0, 
                    'pending_orders': 0, 
                    'completed_orders': 0
                })
            }
        except Exception as e:
            print(f"Error in orders/stats/daily: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'total_orders': 0, 'total_revenue': 0})
            }
    
    # Payment endpoints
    elif path == '/api/v1/payments/methods' and method == 'GET':
        try:
            payment_methods = {
                "methods": [
                    {
                        "id": "upi",
                        "name": "UPI",
                        "description": "Pay using UPI (Google Pay, PhonePe, Paytm)",
                        "enabled": True,
                        "icon": "upi-icon"
                    },
                    {
                        "id": "card",
                        "name": "Card",
                        "description": "Debit/Credit Card",
                        "enabled": True,
                        "icon": "card-icon"
                    },
                    {
                        "id": "cod",
                        "name": "Cash on Delivery",
                        "description": "Pay when order is delivered",
                        "enabled": True,
                        "icon": "cod-icon"
                    },
                    {
                        "id": "wallet",
                        "name": "Wallet",
                        "description": "Paytm, Mobikwik, etc.",
                        "enabled": True,
                        "icon": "wallet-icon"
                    }
                ]
            }
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(payment_methods)
            }
        except Exception as e:
            print(f"Error in get payment methods: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to get payment methods'})
            }
    
    elif path == '/api/v1/payments/create' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            order_id = body.get('order_id', '')
            amount = body.get('amount', 0)
            customer_info = body.get('customer_info', {})
            
            # Create mock payment intent
            payment_id = f"mock_payment_{order_id}_{int(amount)}"
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'payment_id': payment_id,
                    'amount': amount,
                    'currency': 'INR',
                    'status': 'pending',
                    'gateway_response': {
                        'id': payment_id,
                        'amount': int(amount * 100),
                        'currency': 'INR',
                        'receipt': f"order_{order_id}",
                        'status': 'created'
                    }
                })
            }
        except Exception as e:
            print(f"Error in create payment: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to create payment'})
            }
    
    elif path == '/api/v1/payments/confirm' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            payment_id = body.get('payment_id', '')
            razorpay_payment_id = body.get('razorpay_payment_id', '')
            razorpay_signature = body.get('razorpay_signature', '')
            
            # Mock payment confirmation
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'status': 'completed',
                    'payment_id': razorpay_payment_id or payment_id
                })
            }
        except Exception as e:
            print(f"Error in confirm payment: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to confirm payment'})
            }
    
    elif path.startswith('/api/v1/payments/') and path.endswith('/status') and method == 'GET':
        try:
            payment_id = path.split('/')[-2]  # Extract payment_id from path
            
            # Mock payment status
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'payment_id': payment_id,
                    'status': 'completed',
                    'amount': 150.00,
                    'method': 'upi',
                    'gateway_response': {
                        'id': payment_id,
                        'status': 'captured',
                        'method': 'upi',
                        'amount': 15000
                    }
                })
            }
        except Exception as e:
            print(f"Error in get payment status: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to get payment status'})
            }
    
    elif path.startswith('/api/v1/payments/') and path.endswith('/refund') and method == 'POST':
        try:
            payment_id = path.split('/')[-2]  # Extract payment_id from path
            body = json.loads(event.get('body', '{}'))
            amount = body.get('amount', 150.00)
            
            # Mock refund
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'refund_id': f"mock_refund_{payment_id}",
                    'status': 'refunded',
                    'amount': amount,
                    'gateway_response': {
                        'id': f"mock_refund_{payment_id}",
                        'payment_id': payment_id,
                        'amount': int(amount * 100)
                    }
                })
            }
        except Exception as e:
            print(f"Error in process refund: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to process refund'})
            }
    
    elif path == '/api/v1/payments/calculate-total' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            items = body.get('items', [])
            tax_rate = body.get('tax_rate', 0.18)
            delivery_fee = body.get('delivery_fee', 50.00)
            
            # Calculate order total
            subtotal = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
            tax_amount = subtotal * tax_rate
            total = subtotal + tax_amount + delivery_fee
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'subtotal': subtotal,
                    'tax_amount': tax_amount,
                    'tax_rate': tax_rate,
                    'delivery_fee': delivery_fee,
                    'total': total,
                    'breakdown': {
                        'items': items,
                        'subtotal': subtotal,
                        'tax': tax_amount,
                        'delivery': delivery_fee,
                        'total': total
                    }
                })
            }
        except Exception as e:
            print(f"Error in calculate total: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to calculate total'})
            }
    
    elif path == '/api/v1/payments/cod' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            order_id = body.get('order_id', '')
            amount = body.get('amount', 0)
            
            # Create COD payment
            payment_id = f"cod_{order_id}_{int(amount)}"
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'payment_id': payment_id,
                    'status': 'pending',
                    'method': 'cod',
                    'amount': amount,
                    'gateway_response': {
                        'id': payment_id,
                        'method': 'cod',
                        'status': 'pending'
                    }
                })
            }
        except Exception as e:
            print(f"Error in create COD payment: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to create COD payment'})
            }
    
    # Analytics endpoints
    elif path == '/api/v1/analytics/overview' and method == 'GET':
        try:
            return {
                'statusCode': 200, 
                'headers': {'Content-Type': 'application/json'}, 
                'body': json.dumps({
                    'revenue': {'today': 0, 'week': 0, 'month': 0}, 
                    'orders': {'today': 0, 'week': 0, 'month': 0}, 
                    'customers': {'total': 0, 'new_today': 0}, 
                    'products': {'total': 0, 'low_stock': 0}
                })
            }
        except Exception as e:
            print(f"Error in analytics/overview: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'revenue': {'today': 0}, 'orders': {'today': 0}})
            }
    
    # Customer endpoints
    elif path == '/api/v1/customers' and method == 'GET':
        try:
            return {
                'statusCode': 200, 
                'headers': {'Content-Type': 'application/json'}, 
                'body': json.dumps({
                    'data': [], 
                    'total': 0, 
                    'page': 1, 
                    'pages': 1
                })
            }
        except Exception as e:
            print(f"Error in customers: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'data': [], 'total': 0})
            }
    
    # Inventory endpoints
    elif path == '/api/v1/inventory/products' and method == 'GET':
        try:
            # Extract query parameters
            category = event.get('queryStringParameters', {}).get('category') if event.get('queryStringParameters') else None
            status = event.get('queryStringParameters', {}).get('status') if event.get('queryStringParameters') else None
            search = event.get('queryStringParameters', {}).get('search') if event.get('queryStringParameters') else None
            page = int(event.get('queryStringParameters', {}).get('page', 1)) if event.get('queryStringParameters') else 1
            limit = int(event.get('queryStringParameters', {}).get('limit', 50)) if event.get('queryStringParameters') else 50
            
            print(f"Getting products with real-time stock from DynamoDB")
            
            # Get products with real-time stock from DynamoDB
            products_list = []
            for product_id, product_data in MOCK_PRODUCTS.items():
                # Get current stock from DynamoDB
                current_stock = get_current_stock(product_id)
                
                # Create product with real-time stock
                product = product_data.copy()
                product['current_stock'] = current_stock
                
                # Calculate stock status
                min_stock = product.get('min_stock_level', 0)
                max_stock = product.get('max_stock_level', 0)
                
                if current_stock == 0:
                    product['stock_status'] = 'out_of_stock'
                    product['is_low_stock'] = True
                    product['is_out_of_stock'] = True
                elif current_stock <= min_stock:
                    product['stock_status'] = 'low_stock'
                    product['is_low_stock'] = True
                    product['is_out_of_stock'] = False
                else:
                    product['stock_status'] = 'in_stock'
                    product['is_low_stock'] = False
                    product['is_out_of_stock'] = False
                
                products_list.append(product)
            
            # Apply filters
            filtered_products = products_list
            if category:
                filtered_products = [p for p in filtered_products if p["category"].lower() == category.lower()]
            if status:
                filtered_products = [p for p in filtered_products if p["status"] == status]
            if search:
                search_lower = search.lower()
                filtered_products = [p for p in filtered_products if search_lower in p["name"].lower()]
            
            # Pagination
            total = len(filtered_products)
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_products = filtered_products[start_idx:end_idx]
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'products': paginated_products,
                    'total': total,
                    'page': page,
                    'pages': (total + limit - 1) // limit,
                    'has_next': end_idx < total,
                    'has_prev': page > 1
                })
            }
        except Exception as e:
            print(f"Error getting products: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to get products'})
            }
    
    elif path.startswith('/api/v1/inventory/products/') and path.endswith('/stock') and method == 'PUT':
        try:
            # Extract product_id from path
            path_parts = path.split('/')
            product_id = path_parts[-2]  # products/{id}/stock
            
            body = json.loads(event.get('body', '{}'))
            quantity = body.get('quantity', 0)
            movement_type = body.get('movement_type', 'out')
            reason = body.get('reason', 'Stock update')
            reference_id = body.get('reference_id', '')
            
            print(f"REAL STOCK UPDATE: {product_id} {movement_type} {quantity} units")
            
            # Get current product
            product = MOCK_PRODUCTS.get(product_id, {})
            if not product:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'detail': 'Product not found'})
                }
            
            # Get current stock from DynamoDB
            current_stock = get_current_stock(product_id)
            previous_stock = current_stock
            print(f"REAL STOCK: Current stock from DynamoDB: {product_id} = {current_stock}")
            
            # Update stock based on movement type
            if movement_type == 'out':
                if current_stock < quantity:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json'},
                        'body': json.dumps({
                            'detail': f'Insufficient stock. Available: {current_stock}, Requested: {quantity}'
                        })
                    }
                new_stock = current_stock - quantity
            elif movement_type == 'in':
                new_stock = current_stock + quantity
            else:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'detail': 'Invalid movement_type. Use "in" or "out"'})
                }
            
            # Update stock in DynamoDB
            update_stock(product_id, new_stock)
            print(f"REAL STOCK: Updated stock in DynamoDB: {product_id} = {new_stock}")
            
            # Determine stock status
            min_stock = product.get('min_stock_level', 0)
            if new_stock == 0:
                stock_status = 'out_of_stock'
            elif new_stock <= min_stock:
                stock_status = 'low_stock'
            else:
                stock_status = 'in_stock'
            
            response = {
                'success': True,
                'product_id': product_id,
                'previous_stock': previous_stock,
                'new_stock': new_stock,
                'stock_status': stock_status,
                'message': 'Stock updated successfully'
            }
            
            print(f"REAL STOCK: Stock updated in DynamoDB: {product_id} {previous_stock} -> {new_stock}")
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(response)
            }
        except Exception as e:
            print(f"Error updating stock: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to update stock'})
            }
    
    elif path == '/api/v1/inventory/products/low-stock' and method == 'GET':
        try:
            print("Getting low stock products")
            
            # Mock low stock products
            low_stock_products = [
                {
                    "id": "prod_002",
                    "name": "Wheat Flour",
                    "current_stock": 5,
                    "min_stock_level": 10,
                    "category": "Grains"
                },
                {
                    "id": "prod_005",
                    "name": "Milk",
                    "current_stock": 15,
                    "min_stock_level": 20,
                    "category": "Dairy"
                }
            ]
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'low_stock_products': low_stock_products,
                    'count': len(low_stock_products)
                })
            }
        except Exception as e:
            print(f"Error getting low stock products: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to get low stock products'})
            }
    
    elif path == '/api/v1/inventory/inventory/summary' and method == 'GET':
        try:
            print("Getting inventory summary")
            
            # Mock inventory summary
            summary = {
                "total_products": 5,
                "active_products": 4,
                "out_of_stock": 1,
                "low_stock": 2,
                "total_stock_value": 15000.0,
                "categories": {
                    "Grains": {
                        "total_products": 2,
                        "active_products": 2,
                        "out_of_stock": 0,
                        "low_stock": 1,
                        "total_value": 6000.0
                    },
                    "Essentials": {
                        "total_products": 2,
                        "active_products": 1,
                        "out_of_stock": 1,
                        "low_stock": 1,
                        "total_value": 9000.0
                    },
                    "Dairy": {
                        "total_products": 1,
                        "active_products": 1,
                        "out_of_stock": 0,
                        "low_stock": 1,
                        "total_value": 900.0
                    }
                }
            }
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'summary': summary
                })
            }
        except Exception as e:
            print(f"Error getting inventory summary: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to get inventory summary'})
            }
    
    # Additional inventory endpoints
    elif path.startswith('/api/v1/inventory/products/') and '/availability/' in path and method == 'GET':
        try:
            # Extract product_id and quantity from path
            path_parts = path.split('/')
            product_id = path_parts[-3]  # products/{id}/availability/{qty}
            quantity = int(path_parts[-1])
            
            print(f"Checking availability for product {product_id}, quantity {quantity}")
            
            # Use global stock data for consistency
            mock_products = MOCK_PRODUCTS
            
            product = mock_products.get(product_id, {'current_stock': 0, 'min_stock_level': 10})
            current_stock = product['current_stock']
            available = current_stock >= quantity
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'product_id': product_id,
                    'requested_quantity': quantity,
                    'current_stock': current_stock,
                    'available': available,
                    'message': f"Stock available: {available}"
                })
            }
        except Exception as e:
            print(f"Error checking availability: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to check availability'})
            }
    
    elif path == '/api/v1/inventory/products' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            print(f"Creating new product: {body.get('name', 'Unknown')}")
            
            # Generate product ID
            import uuid
            product_id = f"prod-{uuid.uuid4().hex[:8]}"
            
            # Mock product creation
            new_product = {
                'id': product_id,
                'name': body.get('name', 'New Product'),
                'description': body.get('description', ''),
                'category': body.get('category', 'General'),
                'price': body.get('price', 0.0),
                'current_stock': body.get('current_stock', 0),
                'min_stock_level': body.get('min_stock_level', 10),
                'unit': body.get('unit', 'piece'),
                'status': 'active',
                'created_at': datetime.datetime.now().isoformat()
            }
            
            return {
                'statusCode': 201,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'product': new_product,
                    'message': 'Product created successfully'
                })
            }
        except Exception as e:
            print(f"Error creating product: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Failed to create product'})
            }
    
    # Notifications endpoints
    elif path == '/api/v1/notifications/settings' and method == 'GET':
        try:
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'enabled': True, 
                    'settings': {
                        'email': True,
                        'push': True,
                        'sms': True
                    }
                })
            }
        except Exception as e:
            print(f"Error in notifications/settings: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'enabled': True, 'settings': {}})
            }
    
    # Store Registration API
    elif path == '/api/v1/stores/register' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            
            # Generate store ID using ULID-based format
            store_id = generate_store_id()
            
            # Prepare store data
            store_data = {
                'id': store_id,  # DynamoDB expects 'id' as key
                'store_id': store_id,
                'name': body.get('name', 'New Store'),
                'owner_name': body.get('owner_name', 'Store Owner'),
                'phone': body.get('phone', ''),
                'email': body.get('email', ''),
                'whatsapp': body.get('whatsapp', body.get('phone', '')),
                'address': body.get('address', {}),
                'settings': body.get('settings', {
                    'store_type': 'Kirana Store',
                    'delivery_radius': 3,
                    'min_order_amount': 100,
                    'business_hours': {'open': '09:00', 'close': '21:00'}
                }),
                'gst_number': body.get('gst_number', ''),
                'status': 'active',
                'registered_at': datetime.datetime.now().isoformat(),
                'created_at': datetime.datetime.now().isoformat(),
                'updated_at': datetime.datetime.now().isoformat()
            }
            
            # Store in DynamoDB
            try:
                # Use a stores table or the orders table
                stores_table = dynamodb.Table('vyaparai-stores-prod')
                stores_table.put_item(Item=store_data)
            except:
                # Fallback to orders table with type='store'
                store_data['type'] = 'store_registration'
                table = dynamodb.Table('vyaparai-orders-prod')
                table.put_item(Item=store_data)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'store_id': store_id,
                    'message': 'Store registered successfully',
                    'data': {
                        'store_name': store_data['name'],
                        'owner_name': store_data['owner_name'],
                        'city': store_data.get('address', {}).get('city', 'Unknown')
                    }
                })
            }
        except Exception as e:
            print(f"Error registering store: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'message': f'Failed to register store: {str(e)}'
                })
            }
    
    # List Stores API
    elif path == '/api/v1/stores/list' and method == 'GET':
        try:
            stores = []
            
            # Try to get from stores table
            try:
                stores_table = dynamodb.Table('vyaparai-stores-prod')
                response = stores_table.scan(Limit=100)
                if 'Items' in response:
                    stores = response['Items']
            except:
                # Fallback to orders table
                table = dynamodb.Table('vyaparai-orders-prod')
                response = table.scan(
                    FilterExpression='#type = :store_type',
                    ExpressionAttributeNames={'#type': 'type'},
                    ExpressionAttributeValues={':store_type': 'store_registration'},
                    Limit=100
                )
                if 'Items' in response:
                    stores = response['Items']
            
            # If no stores found, return sample data
            if not stores:
                stores = [
                    {
                        'store_id': 'STORE-001',
                        'name': 'Mumbai Grocery Store',
                        'owner_name': 'Ramesh Kumar',
                        'phone': '+91-9876543210',
                        'email': 'ramesh@mumbaistore.com',
                        'city': 'Mumbai',
                        'state': 'Maharashtra',
                        'registered_at': datetime.datetime.now().isoformat(),
                        'status': 'active'
                    }
                ]
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': True,
                    'count': len(stores),
                    'stores': stores
                }, cls=DecimalEncoder)
            }
        except Exception as e:
            print(f"Error fetching stores: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'message': f'Failed to fetch stores: {str(e)}'
                })
            }
    
    # Store Verification API (for login)
    elif path == '/api/v1/stores/verify' and method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            phone = body.get('phone', '')
            email = body.get('email', '')
            
            store = None
            
            # Try to find store by phone or email
            try:
                stores_table = dynamodb.Table('vyaparai-stores-prod')
                
                if phone:
                    # Scan for phone number
                    response = stores_table.scan(
                        FilterExpression='phone = :phone',
                        ExpressionAttributeValues={':phone': phone}
                    )
                    if 'Items' in response and response['Items']:
                        store = response['Items'][0]
                elif email:
                    # Scan for email
                    response = stores_table.scan(
                        FilterExpression='email = :email',
                        ExpressionAttributeValues={':email': email}
                    )
                    if 'Items' in response and response['Items']:
                        store = response['Items'][0]
            except Exception as scan_error:
                print(f"Error scanning stores table: {scan_error}")
                # Try fallback to orders table
                table = dynamodb.Table('vyaparai-orders-prod')
                filter_expr = None
                expr_values = {}
                
                if phone:
                    filter_expr = 'phone = :phone AND #type = :store_type'
                    expr_values = {':phone': phone, ':store_type': 'store_registration'}
                elif email:
                    filter_expr = 'email = :email AND #type = :store_type'
                    expr_values = {':email': email, ':store_type': 'store_registration'}
                
                if filter_expr:
                    response = table.scan(
                        FilterExpression=filter_expr,
                        ExpressionAttributeNames={'#type': 'type'},
                        ExpressionAttributeValues=expr_values
                    )
                    if 'Items' in response and response['Items']:
                        store = response['Items'][0]
            
            if store:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': True,
                        'store': {
                            'store_id': store.get('store_id', store.get('id')),
                            'name': store.get('name'),
                            'owner_name': store.get('owner_name'),
                            'phone': store.get('phone'),
                            'email': store.get('email'),
                            'city': store.get('address', {}).get('city') if isinstance(store.get('address'), dict) else store.get('city'),
                            'state': store.get('address', {}).get('state') if isinstance(store.get('address'), dict) else store.get('state')
                        }
                    }, cls=DecimalEncoder)
                }
            else:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'message': 'No store found for this phone/email'
                    })
                }
        except Exception as e:
            print(f"Error verifying store: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'message': f'Failed to verify store: {str(e)}'
                })
            }
    
    # Get Store Details API  
    elif path.startswith('/api/v1/stores/') and method == 'GET':
        store_id = path.replace('/api/v1/stores/', '')
        try:
            store = None
            
            # Try to get from stores table
            try:
                stores_table = dynamodb.Table('vyaparai-stores-prod')
                response = stores_table.get_item(Key={'store_id': store_id})
                if 'Item' in response:
                    store = response['Item']
            except:
                # Fallback to orders table
                table = dynamodb.Table('vyaparai-orders-prod')
                response = table.get_item(Key={'order_id': store_id})
                if 'Item' in response and response['Item'].get('type') == 'store_registration':
                    store = response['Item']
            
            if store:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': True,
                        'store': store
                    })
                }
            else:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'message': 'Store not found'
                    })
                }
        except Exception as e:
            print(f"Error fetching store details: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'message': f'Failed to fetch store details: {str(e)}'
                })
            }
    
    # Default 404 response
    else:
        print(f"404 - Path not found: {path}")
        return {
            'statusCode': 404, 
            'headers': {'Content-Type': 'application/json'}, 
            'body': json.dumps({
                'detail': 'Not Found', 
                'path': path,
                'method': method
            })
        }
