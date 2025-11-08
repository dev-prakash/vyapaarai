"""
VyaparAI WebSocket Manager
Handles real-time WebSocket connections and event broadcasting
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
import socketio
from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Socket.IO server instance
sio = socketio.AsyncServer(
    cors_allowed_origins=["*"],  # Configure appropriately for production
    logger=True,
    engineio_logger=True
)

# Import orders_db for stats
try:
    from app.api.v1.orders import orders_db
except ImportError:
    # Fallback if orders_db not available
    orders_db = {}

# Store connections mapping
store_connections: Dict[str, Set[str]] = {}  # store_id -> set of socket_ids
socket_store_mapping: Dict[str, str] = {}  # socket_id -> store_id
authenticated_sockets: Set[str] = set()

class WebSocketEvent(BaseModel):
    """Base WebSocket event model"""
    event: str
    data: Any
    timestamp: datetime = datetime.now()

class OrderEvent(BaseModel):
    """Order-related WebSocket event"""
    order_id: str
    store_id: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = datetime.now()

class SocketManager:
    """Singleton WebSocket manager for VyaparAI"""
    
    def __init__(self):
        self.sio = sio
        self.store_connections = store_connections
        self.socket_store_mapping = socket_store_mapping
        self.authenticated_sockets = authenticated_sockets
    
    async def emit_to_store(self, store_id: str, event: str, data: Any):
        """Emit event to all connected clients of a specific store"""
        if store_id not in self.store_connections:
            logger.warning(f"No connections found for store {store_id}")
            return
        
        socket_ids = self.store_connections[store_id]
        if not socket_ids:
            logger.warning(f"No active connections for store {store_id}")
            return
        
        # Emit to all store connections
        for socket_id in socket_ids:
            try:
                await self.sio.emit(event, data, room=socket_id)
                logger.debug(f"Emitted {event} to socket {socket_id} for store {store_id}")
            except Exception as e:
                logger.error(f"Failed to emit {event} to socket {socket_id}: {e}")
    
    async def emit_new_order(self, order_data: Dict[str, Any]):
        """Emit new order event to store"""
        store_id = order_data.get('store_id')
        if not store_id:
            logger.error("No store_id in order data")
            return
        
        event_data = {
            'order': order_data,
            'timestamp': datetime.now().isoformat(),
            'event_type': 'new_order'
        }
        
        await self.emit_to_store(store_id, 'new_order', event_data)
        logger.info(f"Emitted new_order event for store {store_id}")
    
    async def emit_order_updated(self, order_id: str, store_id: str, updates: Dict[str, Any]):
        """Emit order update event to store"""
        event_data = {
            'order_id': order_id,
            'updates': updates,
            'timestamp': datetime.now().isoformat(),
            'event_type': 'order_updated'
        }
        
        await self.emit_to_store(store_id, 'order_updated', event_data)
        logger.info(f"Emitted order_updated event for order {order_id}")
    
    async def emit_order_status_changed(self, order_id: str, store_id: str, status: str):
        """Emit order status change event to store"""
        event_data = {
            'order_id': order_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'event_type': 'order_status_changed'
        }
        
        await self.emit_to_store(store_id, 'order_status_changed', event_data)
        logger.info(f"Emitted order_status_changed event for order {order_id}")
    
    async def emit_store_stats(self, store_id: str, stats: Dict[str, Any]):
        """Emit store statistics update"""
        event_data = {
            'stats': stats,
            'timestamp': datetime.now().isoformat(),
            'event_type': 'store_stats'
        }
        
        await self.emit_to_store(store_id, 'store_stats', event_data)
        logger.debug(f"Emitted store_stats event for store {store_id}")
    
    async def broadcast_system_alert(self, message: str, alert_type: str = 'info'):
        """Broadcast system alert to all connected clients"""
        event_data = {
            'message': message,
            'alert_type': alert_type,
            'timestamp': datetime.now().isoformat(),
            'event_type': 'system_alert'
        }
        
        await self.sio.emit('system_alert', event_data)
        logger.info(f"Broadcasted system alert: {message}")
    
    def get_store_connection_count(self, store_id: str) -> int:
        """Get number of active connections for a store"""
        return len(self.store_connections.get(store_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return len(self.socket_store_mapping)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            'total_connections': self.get_total_connections(),
            'authenticated_connections': len(self.authenticated_sockets),
            'store_connections': {
                store_id: len(sockets) 
                for store_id, sockets in self.store_connections.items()
            }
        }

# Global socket manager instance
socket_manager = SocketManager()

# =============================================================================
# SOCKET.IO EVENT HANDLERS
# =============================================================================

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    
    # Send connection confirmation
    await sio.emit('connected', {
        'message': 'Connected to VyaparAI WebSocket server',
        'timestamp': datetime.now().isoformat()
    }, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")
    
    # Clean up connection mappings
    store_id = socket_store_mapping.pop(sid, None)
    if store_id:
        store_connections[store_id].discard(sid)
        if not store_connections[store_id]:
            del store_connections[store_id]
        logger.info(f"Cleaned up connection for store {store_id}")
    
    authenticated_sockets.discard(sid)

@sio.event
async def authenticate(sid, data):
    """Authenticate client with JWT token"""
    try:
        token = data.get('token')
        store_id = data.get('store_id')
        
        if not token:
            await sio.emit('auth_error', {
                'message': 'Missing token',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            return
        
        # Verify JWT token
        try:
            import jwt
            payload = jwt.decode(token, "dev_jwt_secret_key_change_in_production", algorithms=["HS256"])
            token_store_id = payload.get('store_id')
            
            # Validate store_id if provided
            if store_id and store_id != token_store_id:
                await sio.emit('auth_error', {
                    'message': 'Store ID mismatch',
                    'timestamp': datetime.now().isoformat()
                }, room=sid)
                return
            
            # Use store_id from token if not provided
            if not store_id:
                store_id = token_store_id
            
            # Add to authenticated sockets
            authenticated_sockets.add(sid)
            
            # Add to store connections
            if store_id not in store_connections:
                store_connections[store_id] = set()
            store_connections[store_id].add(sid)
            socket_store_mapping[sid] = store_id
            
            await sio.emit('authenticated', {
                'message': 'Authentication successful',
                'store_id': store_id,
                'user': {
                    'phone': payload.get('phone'),
                    'role': payload.get('role')
                },
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            
            logger.info(f"Client {sid} authenticated for store {store_id} (user: {payload.get('phone')})")
            
            # Send initial store stats
            await emit_store_stats(store_id, {
                'total_orders': len([o for o in orders_db.values() if o.get('store_id') == store_id]),
                'pending_orders': len([o for o in orders_db.values() if o.get('store_id') == store_id and o.get('status') == 'pending']),
                'connection_count': len(store_connections.get(store_id, set()))
            })
            
        except jwt.ExpiredSignatureError:
            await sio.emit('auth_error', {
                'message': 'Token expired',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
        except jwt.InvalidTokenError:
            await sio.emit('auth_error', {
                'message': 'Invalid token',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            
    except Exception as e:
        logger.error(f"Authentication error for {sid}: {e}")
        await sio.emit('auth_error', {
            'message': 'Authentication failed',
            'timestamp': datetime.now().isoformat()
        }, room=sid)

@sio.event
async def subscribe_store(sid, data):
    """Subscribe to store-specific events"""
    try:
        store_id = data.get('store_id')
        
        if not store_id:
            await sio.emit('subscription_error', {
                'message': 'Missing store_id',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            return
        
        # Add to store room
        await sio.enter_room(sid, f"store_{store_id}")
        
        # Update mappings
        if store_id not in store_connections:
            store_connections[store_id] = set()
        store_connections[store_id].add(sid)
        socket_store_mapping[sid] = store_id
        
        await sio.emit('subscribed', {
            'message': f'Subscribed to store {store_id}',
            'store_id': store_id,
            'timestamp': datetime.now().isoformat()
        }, room=sid)
        
        logger.info(f"Client {sid} subscribed to store {store_id}")
        
    except Exception as e:
        logger.error(f"Subscription error for {sid}: {e}")
        await sio.emit('subscription_error', {
            'message': 'Subscription failed',
            'timestamp': datetime.now().isoformat()
        }, room=sid)

@sio.event
async def accept_order(sid, data):
    """Handle order acceptance from client"""
    try:
        order_id = data.get('order_id')
        store_id = socket_store_mapping.get(sid)
        
        if not order_id or not store_id:
            await sio.emit('action_error', {
                'message': 'Missing order_id or not authenticated',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            return
        
        # TODO: Implement order acceptance logic
        # For now, just acknowledge the action
        await sio.emit('order_accepted', {
            'order_id': order_id,
            'message': 'Order accepted successfully',
            'timestamp': datetime.now().isoformat()
        }, room=sid)
        
        logger.info(f"Order {order_id} accepted by store {store_id}")
        
    except Exception as e:
        logger.error(f"Order acceptance error: {e}")
        await sio.emit('action_error', {
            'message': 'Failed to accept order',
            'timestamp': datetime.now().isoformat()
        }, room=sid)

@sio.event
async def reject_order(sid, data):
    """Handle order rejection from client"""
    try:
        order_id = data.get('order_id')
        reason = data.get('reason', 'No reason provided')
        store_id = socket_store_mapping.get(sid)
        
        if not order_id or not store_id:
            await sio.emit('action_error', {
                'message': 'Missing order_id or not authenticated',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            return
        
        # TODO: Implement order rejection logic
        await sio.emit('order_rejected', {
            'order_id': order_id,
            'reason': reason,
            'message': 'Order rejected',
            'timestamp': datetime.now().isoformat()
        }, room=sid)
        
        logger.info(f"Order {order_id} rejected by store {store_id}: {reason}")
        
    except Exception as e:
        logger.error(f"Order rejection error: {e}")
        await sio.emit('action_error', {
            'message': 'Failed to reject order',
            'timestamp': datetime.now().isoformat()
        }, room=sid)

@sio.event
async def update_status(sid, data):
    """Handle order status update from client"""
    try:
        order_id = data.get('order_id')
        status = data.get('status')
        store_id = socket_store_mapping.get(sid)
        
        if not order_id or not status or not store_id:
            await sio.emit('action_error', {
                'message': 'Missing order_id, status, or not authenticated',
                'timestamp': datetime.now().isoformat()
            }, room=sid)
            return
        
        # TODO: Implement status update logic
        await sio.emit('status_updated', {
            'order_id': order_id,
            'status': status,
            'message': 'Order status updated',
            'timestamp': datetime.now().isoformat()
        }, room=sid)
        
        logger.info(f"Order {order_id} status updated to {status} by store {store_id}")
        
    except Exception as e:
        logger.error(f"Status update error: {e}")
        await sio.emit('action_error', {
            'message': 'Failed to update status',
            'timestamp': datetime.now().isoformat()
        }, room=sid)

@sio.event
async def ping(sid, data):
    """Handle ping from client"""
    await sio.emit('pong', {
        'timestamp': datetime.now().isoformat()
    }, room=sid)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_socket_app():
    """Get Socket.IO app for integration with FastAPI"""
    import socketio
    from aiohttp import web
    
    # Create ASGI app for Socket.IO
    socket_app = socketio.ASGIApp(sio)
    return socket_app

async def emit_order_event(order_event: OrderEvent):
    """Emit order event using the socket manager"""
    if order_event.event_type == 'new_order':
        await socket_manager.emit_new_order(order_event.data)
    elif order_event.event_type == 'order_updated':
        await socket_manager.emit_order_updated(
            order_event.order_id, 
            order_event.store_id, 
            order_event.data
        )
    elif order_event.event_type == 'order_status_changed':
        await socket_manager.emit_order_status_changed(
            order_event.order_id,
            order_event.store_id,
            order_event.data.get('status')
        )

# Export the socket manager for use in other modules
__all__ = ['socket_manager', 'get_socket_app', 'emit_order_event', 'OrderEvent']
