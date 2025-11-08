"""
RCS Webhook Handler for VyaparAI
Processes incoming RCS messages and integrates with hybrid database
"""

import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Local imports
from ...database.hybrid_db import hybrid_db
from ...services.hybrid_order_service import hybrid_order_service
from .rcs_client import rcs_client
from .rich_cards import OrderConfirmationCard, ProductCarousel, OrderStatusCard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks/rcs")

class RCSWebhookRequest(BaseModel):
    """RCS webhook request model"""
    agentId: str
    messageId: str
    msisdn: str
    message: Optional[Dict[str, Any]] = None
    event: Optional[Dict[str, Any]] = None

@router.post("/")
async def handle_rcs_webhook(
    request: Request, 
    background_tasks: BackgroundTasks
):
    """Process incoming RCS messages"""
    
    try:
        # Parse request body
        body = await request.body()
        data = json.loads(body)
        
        logger.info(f"RCS webhook received: {data}")
        
        # Extract message details
        agent_id = data.get('agentId')
        message_id = data.get('messageId')
        msisdn = data.get('msisdn')  # Phone number
        message = data.get('message', {})
        event = data.get('event', {})
        
        # Verify agent ID
        if agent_id != rcs_client.agent_id:
            logger.warning(f"Invalid agent ID: {agent_id}")
            raise HTTPException(status_code=403, detail="Invalid agent")
        
        # Handle different message types
        if message:
            return await handle_message(msisdn, message, message_id)
        elif event:
            return await handle_event(msisdn, event, message_id)
        else:
            logger.warning("No message or event found in webhook")
            return {"status": "received", "message": "No content to process"}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"RCS webhook error: {e}")
        return {"status": "error", "message": str(e)}

async def handle_message(phone: str, message: Dict[str, Any], message_id: str):
    """Process incoming message"""
    
    try:
        # Send read receipt
        background_tasks.add_task(rcs_client.send_read_receipt, phone, message_id)
        
        # Handle different message types
        if 'text' in message:
            return await handle_text_message(phone, message['text'])
        
        elif 'suggestionResponse' in message:
            return await handle_suggestion_response(
                phone, 
                message['suggestionResponse']
            )
        
        elif 'location' in message:
            return await handle_location(phone, message['location'])
        
        elif 'image' in message:
            return await handle_image(phone, message['image'])
        
        else:
            logger.warning(f"Unsupported message type: {message.keys()}")
            await rcs_client.send_message(
                phone,
                "I can help you with text messages. Please send your order in text format."
            )
            return {"status": "processed", "message": "unsupported_type"}
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await rcs_client.send_message(
            phone,
            "Sorry, I encountered an error. Please try again."
        )
        return {"status": "error", "error": str(e)}

async def handle_text_message(phone: str, text: str):
    """Process text message through hybrid order service"""
    
    try:
        # Show typing indicator
        await rcs_client.send_typing_indicator(phone)
        
        # Get or create session
        session_id = f"rcs-{phone}-{datetime.now().strftime('%Y%m%d')}"
        
        # Get store context (for now, use default store)
        store_id = "store_001"  # TODO: Multi-store support
        
        # Process through hybrid order service
        result = await hybrid_order_service.process_order_hybrid(
            message=text,
            session_id=session_id,
            channel="rcs",
            store_id=store_id,
            customer_phone=phone
        )
        
        # Send appropriate response based on intent
        if result.intent == "place_order" and result.order_id:
            # Send rich card for order confirmation
            card = OrderConfirmationCard(
                order_id=result.order_id,
                items=result.entities,
                total=result.total_amount or 0,
                language=result.language
            )
            
            await rcs_client.send_rich_card(phone, card.build())
            
        elif result.intent == "check_status":
            # Send order status card
            if result.order_id:
                status_card = OrderStatusCard(
                    order_id=result.order_id,
                    status="pending",
                    language=result.language
                )
                await rcs_client.send_rich_card(phone, status_card.build())
            else:
                await rcs_client.send_message(
                    phone,
                    result.response,
                    get_default_suggestions()
                )
        
        elif result.intent == "browse_products":
            # Send product carousel if products found
            if result.product_details:
                carousel = ProductCarousel(result.product_details)
                await rcs_client.send_carousel(phone, carousel.build())
            else:
                await rcs_client.send_message(
                    phone,
                    result.response,
                    get_default_suggestions()
                )
        
        elif result.intent == "greeting":
            # Send welcome message with suggestions
            await rcs_client.send_message(
                phone,
                result.response,
                get_welcome_suggestions()
            )
        
        else:
            # Send text response with suggestions
            await rcs_client.send_message(
                phone,
                result.response,
                get_default_suggestions()
            )
        
        return {
            "status": "processed", 
            "order_id": result.order_id,
            "intent": result.intent,
            "language": result.language
        }
        
    except Exception as e:
        logger.error(f"Error processing text message: {e}")
        await rcs_client.send_message(
            phone,
            "Sorry, I encountered an error processing your message. Please try again.",
            get_default_suggestions()
        )
        return {"status": "error", "error": str(e)}

async def handle_suggestion_response(phone: str, suggestion: Dict[str, Any]):
    """Handle suggested reply clicks"""
    
    try:
        postback_data = suggestion.get('postbackData', '')
        text = suggestion.get('text', '')
        
        logger.info(f"Handling suggestion: {text} - {postback_data}")
        
        # Parse action
        params = {}
        if postback_data:
            for param in postback_data.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
        
        action = params.get('action')
        
        if action == 'confirm_order':
            order_id = params.get('order_id')
            if order_id:
                # Confirm order in database
                await hybrid_db.update_order_status(order_id, 'confirmed')
                await rcs_client.send_message(
                    phone,
                    "✅ Order confirmed! We'll deliver in 30-45 minutes.",
                    get_order_confirmed_suggestions()
                )
            else:
                await rcs_client.send_message(phone, "Order ID not found.")
                
        elif action == 'cancel_order':
            order_id = params.get('order_id')
            if order_id:
                await hybrid_db.update_order_status(order_id, 'cancelled')
                await rcs_client.send_message(
                    phone,
                    "❌ Order cancelled. Let us know if you need anything else!",
                    get_default_suggestions()
                )
            else:
                await rcs_client.send_message(phone, "Order ID not found.")
        
        elif action == 'track_order':
            order_id = params.get('order_id')
            if order_id:
                # Get order details
                order_result = await hybrid_db.get_order(order_id)
                if order_result.success:
                    order = order_result.data
                    status_card = OrderStatusCard(
                        order_id=order_id,
                        status=order.status,
                        language="en"
                    )
                    await rcs_client.send_rich_card(phone, status_card.build())
                else:
                    await rcs_client.send_message(phone, "Order not found.")
            else:
                await rcs_client.send_message(phone, "Order ID not found.")
        
        elif action == 'place_order':
            await rcs_client.send_message(
                phone,
                "Great! Please send your order. For example: '2 kg rice, 1 liter oil'",
                get_default_suggestions()
            )
        
        elif action == 'check_status':
            await rcs_client.send_message(
                phone,
                "Please provide your order number or phone number to check status.",
                get_default_suggestions()
            )
        
        elif action == 'browse':
            await rcs_client.send_message(
                phone,
                "What would you like to browse? Try: 'rice', 'oil', 'milk', etc.",
                get_default_suggestions()
            )
        
        else:
            # Handle as text message
            await handle_text_message(phone, text)
        
        return {"status": "handled", "action": action}
        
    except Exception as e:
        logger.error(f"Error handling suggestion: {e}")
        await rcs_client.send_message(
            phone,
            "Sorry, I encountered an error. Please try again.",
            get_default_suggestions()
        )
        return {"status": "error", "error": str(e)}

async def handle_location(phone: str, location: Dict[str, Any]):
    """Handle location message"""
    
    try:
        # Extract location data
        latitude = location.get('latitude')
        longitude = location.get('longitude')
        
        if latitude and longitude:
            # Store location in session for delivery
            session_id = f"rcs-{phone}-{datetime.now().strftime('%Y%m%d')}"
            
            # TODO: Update session with location data
            logger.info(f"Location received: {latitude}, {longitude}")
            
            await rcs_client.send_message(
                phone,
                "📍 Location received! We'll deliver to this address.",
                get_default_suggestions()
            )
        else:
            await rcs_client.send_message(
                phone,
                "Could not get your location. Please try again or provide your address.",
                get_default_suggestions()
            )
        
        return {"status": "processed", "location": "received"}
        
    except Exception as e:
        logger.error(f"Error handling location: {e}")
        return {"status": "error", "error": str(e)}

async def handle_image(phone: str, image: Dict[str, Any]):
    """Handle image message"""
    
    try:
        # For now, ask for text description
        await rcs_client.send_message(
            phone,
            "I can see you sent an image. Please describe what you'd like to order in text.",
            get_default_suggestions()
        )
        
        return {"status": "processed", "image": "received"}
        
    except Exception as e:
        logger.error(f"Error handling image: {e}")
        return {"status": "error", "error": str(e)}

async def handle_event(phone: str, event: Dict[str, Any], event_id: str):
    """Handle RCS events (delivery receipts, etc.)"""
    
    try:
        event_type = event.get('eventType')
        
        if event_type == 'DELIVERED':
            logger.info(f"Message delivered to {phone}")
        elif event_type == 'READ':
            logger.info(f"Message read by {phone}")
        else:
            logger.info(f"Event received: {event_type} for {phone}")
        
        return {"status": "processed", "event": event_type}
        
    except Exception as e:
        logger.error(f"Error handling event: {e}")
        return {"status": "error", "error": str(e)}

def get_default_suggestions() -> List[Dict[str, Any]]:
    """Get default suggestion buttons"""
    return [
        {
            "reply": {
                "text": "📦 Place Order",
                "postbackData": "action=place_order"
            }
        },
        {
            "reply": {
                "text": "📍 Order Status",
                "postbackData": "action=check_status"
            }
        },
        {
            "reply": {
                "text": "🛍️ Browse Products",
                "postbackData": "action=browse"
            }
        }
    ]

def get_welcome_suggestions() -> List[Dict[str, Any]]:
    """Get welcome message suggestions"""
    return [
        {
            "reply": {
                "text": "🛒 Start Shopping",
                "postbackData": "action=place_order"
            }
        },
        {
            "reply": {
                "text": "📋 View Menu",
                "postbackData": "action=browse"
            }
        },
        {
            "reply": {
                "text": "📞 Contact Support",
                "postbackData": "action=support"
            }
        }
    ]

def get_order_confirmed_suggestions() -> List[Dict[str, Any]]:
    """Get order confirmed suggestions"""
    return [
        {
            "reply": {
                "text": "📍 Track Order",
                "postbackData": "action=track_order"
            }
        },
        {
            "reply": {
                "text": "🛒 Place Another Order",
                "postbackData": "action=place_order"
            }
        },
        {
            "reply": {
                "text": "📞 Contact Support",
                "postbackData": "action=support"
            }
        }
    ]

@router.get("/health")
async def rcs_health_check():
    """Health check for RCS webhook"""
    try:
        # Check if RCS client is configured
        if not rcs_client.agent_id:
            return {"status": "unconfigured", "message": "RCS not configured"}
        
        # Get agent info
        agent_info = await rcs_client.get_agent_info()
        
        return {
            "status": "healthy",
            "agent_id": rcs_client.agent_id,
            "agent_info": agent_info
        }
        
    except Exception as e:
        logger.error(f"RCS health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
