"""
VyaparAI WebSocket Handler for Real-Time Order Notifications
Enterprise-grade implementation using AWS API Gateway WebSocket API
"""

import json
import os
import logging
import boto3
from datetime import datetime
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
connections_table = dynamodb.Table(os.environ.get('CONNECTIONS_TABLE', 'vyaparai-websocket-connections'))
orders_table = dynamodb.Table(os.environ.get('ORDERS_TABLE', 'vyaparai-orders-prod'))


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB"""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def json_dumps(obj):
    """JSON dumps with Decimal support"""
    return json.dumps(obj, cls=DecimalEncoder)


def connect_handler(event, context):
    """
    Handle WebSocket $connect route
    Stores connection with store_id for targeted broadcasts
    """
    connection_id = event['requestContext']['connectionId']

    # Extract store_id from query string
    query_params = event.get('queryStringParameters') or {}
    store_id = query_params.get('store_id', 'unknown')
    user_type = query_params.get('user_type', 'store_owner')

    logger.info(f"New connection: {connection_id} for store: {store_id}")

    try:
        # Store connection in DynamoDB
        connections_table.put_item(
            Item={
                'connectionId': connection_id,
                'storeId': store_id,
                'userType': user_type,
                'connectedAt': datetime.utcnow().isoformat(),
                'ttl': int(datetime.utcnow().timestamp()) + 86400  # 24 hour TTL
            }
        )

        return {
            'statusCode': 200,
            'body': json_dumps({'message': 'Connected', 'connectionId': connection_id})
        }

    except Exception as e:
        logger.error(f"Failed to store connection: {str(e)}")
        return {
            'statusCode': 500,
            'body': json_dumps({'error': 'Failed to connect'})
        }


def disconnect_handler(event, context):
    """
    Handle WebSocket $disconnect route
    Removes connection from DynamoDB
    """
    connection_id = event['requestContext']['connectionId']

    logger.info(f"Disconnection: {connection_id}")

    try:
        connections_table.delete_item(
            Key={'connectionId': connection_id}
        )

        return {
            'statusCode': 200,
            'body': json_dumps({'message': 'Disconnected'})
        }

    except Exception as e:
        logger.error(f"Failed to remove connection: {str(e)}")
        return {
            'statusCode': 500,
            'body': json_dumps({'error': 'Failed to disconnect'})
        }


def default_handler(event, context):
    """
    Handle WebSocket $default route (messages from clients)
    Supports: ping, subscribe, unsubscribe
    """
    connection_id = event['requestContext']['connectionId']
    domain = event['requestContext']['domainName']
    stage = event['requestContext']['stage']

    # Create API Gateway Management API client
    endpoint_url = f"https://{domain}/{stage}"
    apigw_client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=endpoint_url
    )

    try:
        body = json.loads(event.get('body', '{}'))
        action = body.get('action', 'ping')

        if action == 'ping':
            # Respond with pong
            response_data = {
                'type': 'pong',
                'timestamp': datetime.utcnow().isoformat()
            }

        elif action == 'subscribe':
            # Update subscription for store
            store_id = body.get('store_id')
            if store_id:
                connections_table.update_item(
                    Key={'connectionId': connection_id},
                    UpdateExpression='SET storeId = :sid',
                    ExpressionAttributeValues={':sid': store_id}
                )
            response_data = {
                'type': 'subscribed',
                'store_id': store_id
            }

        elif action == 'get_orders':
            # Fetch recent orders for the store
            store_id = body.get('store_id')
            if store_id:
                response = orders_table.scan(
                    FilterExpression='store_id = :sid',
                    ExpressionAttributeValues={':sid': store_id},
                    Limit=50
                )
                orders = response.get('Items', [])
                response_data = {
                    'type': 'orders',
                    'orders': orders
                }
            else:
                response_data = {'type': 'error', 'message': 'store_id required'}

        else:
            response_data = {
                'type': 'unknown_action',
                'action': action
            }

        # Send response back to client
        apigw_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json_dumps(response_data).encode('utf-8')
        )

        return {'statusCode': 200, 'body': 'Message processed'}

    except json.JSONDecodeError:
        logger.error("Invalid JSON in message body")
        return {'statusCode': 400, 'body': 'Invalid JSON'}

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}


def broadcast_to_store(store_id: str, message: dict, endpoint_url: str):
    """
    Broadcast message to all connections for a specific store
    """
    apigw_client = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url=endpoint_url
    )

    # Get all connections for this store
    try:
        response = connections_table.query(
            IndexName='storeId-index',
            KeyConditionExpression='storeId = :sid',
            ExpressionAttributeValues={':sid': store_id}
        )
        connections = response.get('Items', [])

        logger.info(f"Broadcasting to {len(connections)} connections for store {store_id}")

        stale_connections = []

        for conn in connections:
            connection_id = conn['connectionId']
            try:
                apigw_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json_dumps(message).encode('utf-8')
                )
                logger.info(f"Sent to connection {connection_id}")

            except apigw_client.exceptions.GoneException:
                # Connection is stale, mark for cleanup
                stale_connections.append(connection_id)
                logger.warning(f"Stale connection: {connection_id}")

            except Exception as e:
                logger.error(f"Failed to send to {connection_id}: {str(e)}")

        # Clean up stale connections
        for conn_id in stale_connections:
            try:
                connections_table.delete_item(Key={'connectionId': conn_id})
            except Exception as e:
                logger.error(f"Failed to delete stale connection {conn_id}: {str(e)}")

        return len(connections) - len(stale_connections)

    except Exception as e:
        logger.error(f"Failed to broadcast to store {store_id}: {str(e)}")
        return 0


def stream_handler(event, context):
    """
    Handle DynamoDB Streams events for order table
    Broadcasts new orders to connected store dashboards
    """
    websocket_endpoint = os.environ.get('WEBSOCKET_ENDPOINT', '')

    if not websocket_endpoint:
        logger.error("WEBSOCKET_ENDPOINT not configured")
        return {'statusCode': 500, 'body': 'WebSocket endpoint not configured'}

    for record in event.get('Records', []):
        event_name = record.get('eventName')

        # Only process INSERT (new orders) and MODIFY (status changes)
        if event_name not in ['INSERT', 'MODIFY']:
            continue

        try:
            # Get the new image (current state of the item)
            new_image = record.get('dynamodb', {}).get('NewImage', {})

            if not new_image:
                continue

            # Convert DynamoDB format to regular dict
            order = deserialize_dynamodb_item(new_image)
            store_id = order.get('store_id')

            if not store_id:
                logger.warning("Order missing store_id, skipping broadcast")
                continue

            # Determine message type
            if event_name == 'INSERT':
                message_type = 'new_order'
                logger.info(f"New order {order.get('id')} for store {store_id}")
            else:
                message_type = 'order_updated'
                logger.info(f"Order {order.get('id')} updated for store {store_id}")

            # Build broadcast message
            message = {
                'type': message_type,
                'order': {
                    'id': order.get('id'),
                    'order_number': order.get('order_number'),
                    'store_id': store_id,
                    'customer_name': order.get('customer_name'),
                    'customer_phone': order.get('customer_phone'),
                    'items': order.get('items', []),
                    'total_amount': order.get('total_amount'),
                    'status': order.get('status'),
                    'payment_status': order.get('payment_status'),
                    'payment_method': order.get('payment_method'),
                    'created_at': order.get('created_at'),
                    'updated_at': order.get('updated_at')
                },
                'timestamp': datetime.utcnow().isoformat()
            }

            # Broadcast to all connected clients for this store
            sent_count = broadcast_to_store(store_id, message, websocket_endpoint)
            logger.info(f"Broadcast {message_type} to {sent_count} clients for store {store_id}")

        except Exception as e:
            logger.error(f"Error processing stream record: {str(e)}")
            continue

    return {'statusCode': 200, 'body': 'Stream processed'}


def deserialize_dynamodb_item(item: dict) -> dict:
    """Convert DynamoDB item format to regular Python dict"""
    result = {}

    for key, value in item.items():
        result[key] = deserialize_dynamodb_value(value)

    return result


def deserialize_dynamodb_value(value: dict):
    """Convert a single DynamoDB value to Python type"""
    if 'S' in value:
        return value['S']
    elif 'N' in value:
        num_str = value['N']
        if '.' in num_str:
            return float(num_str)
        return int(num_str)
    elif 'BOOL' in value:
        return value['BOOL']
    elif 'NULL' in value:
        return None
    elif 'L' in value:
        return [deserialize_dynamodb_value(v) for v in value['L']]
    elif 'M' in value:
        return deserialize_dynamodb_item(value['M'])
    elif 'SS' in value:
        return set(value['SS'])
    elif 'NS' in value:
        return {float(n) if '.' in n else int(n) for n in value['NS']}
    else:
        return str(value)


# Lambda handler routing
def lambda_handler(event, context):
    """
    Main Lambda handler - routes to appropriate function based on route
    """
    route_key = event.get('requestContext', {}).get('routeKey', 'unknown')

    logger.info(f"Received event for route: {route_key}")

    if route_key == '$connect':
        return connect_handler(event, context)
    elif route_key == '$disconnect':
        return disconnect_handler(event, context)
    elif route_key == '$default':
        return default_handler(event, context)
    elif 'Records' in event:
        # DynamoDB Streams trigger
        return stream_handler(event, context)
    else:
        logger.warning(f"Unknown route: {route_key}")
        return {'statusCode': 400, 'body': f'Unknown route: {route_key}'}
