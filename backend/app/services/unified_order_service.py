"""
Unified Order Processing Service
Combines multilingual service, NER, intent classifier, and Gemini for intelligent order processing
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re

# Google Generative AI imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Google Generative AI not available. Install with: pip install google-generativeai")

# Local imports
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from nlp.indian_commerce_ner import indian_commerce_ner
from nlp.intent_classifier import indian_intent_classifier
from services.indian_multilingual_service import indian_multilingual_service, MultilingualResult

# WebSocket imports
try:
    from websocket.socket_manager import socket_manager, OrderEvent
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logging.warning("WebSocket support not available")

class ChannelType(Enum):
    """Supported communication channels"""
    WHATSAPP = "whatsapp"
    RCS = "rcs"
    SMS = "sms"

@dataclass
class OrderProcessingResult:
    """Complete result from order processing"""
    response: str
    intent: str
    confidence: float
    entities: List[Dict[str, Any]]
    language: str
    processing_time_ms: float
    channel_format: str
    original_text: str
    translated_text: Optional[str]
    gemini_used: bool
    error_occurred: bool
    error_message: Optional[str] = None

class UnifiedOrderService:
    """
    Unified Order Processing Service
    Combines all NLP components with Gemini for intelligent response generation
    """
    
    def __init__(self, gemini_api_key: Optional[str] = None):
        """Initialize the unified order service"""
        self.gemini_api_key = gemini_api_key
        self.gemini_model = None
        self._initialize_gemini()
        self._build_response_templates()
        self._build_channel_formatters()
        self._initialize_metrics()
        
    def _initialize_gemini(self):
        """Initialize Gemini model for response generation"""
        if not GEMINI_AVAILABLE:
            logging.warning("Gemini not available - will use template responses")
            return
            
        try:
            if self.gemini_api_key:
                genai.configure(api_key=self.gemini_api_key)
            
            # Initialize Gemini model
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logging.info("Gemini model initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize Gemini: {e}")
            self.gemini_model = None
    
    def _build_response_templates(self):
        """Build response templates for fallback scenarios"""
        self.response_templates = {
            "place_order": {
                "en": "Order confirmed! {items} will be delivered in 30-45 minutes. Total: ₹{total}",
                "hi": "ऑर्डर कन्फर्म! {items} 30-45 मिनट में डिलीवर होगा। कुल: ₹{total}",
                "mixed": "Order confirm! {items} 30-45 minute mein deliver hoga. Total: ₹{total}"
            },
            "check_status": {
                "en": "Your order status is being checked. Please provide your order number for faster assistance.",
                "hi": "आपका ऑर्डर स्टेटस चेक किया जा रहा है। तेज सहायता के लिए कृपया अपना ऑर्डर नंबर दें।",
                "mixed": "Aapka order status check kiya ja raha hai. Tez help ke liye order number dijiye."
            },
            "cancel_order": {
                "en": "Your order has been cancelled successfully. Refund will be processed within 3-5 business days.",
                "hi": "आपका ऑर्डर सफलतापूर्वक रद्द कर दिया गया है। रिफंड 3-5 कार्य दिवसों में प्रोसेस होगा।",
                "mixed": "Aapka order successfully cancel ho gaya hai. Refund 3-5 din mein process hoga."
            },
            "greeting": {
                "en": "Hello! Welcome to VyaparAI. How can I help you with your order today?",
                "hi": "नमस्ते! VyaparAI में आपका स्वागत है। आज आपके ऑर्डर में कैसे मदद कर सकता हूं?",
                "mixed": "Hello! VyaparAI mein aapka swagat hai. Aaj aapke order mein kaise help kar sakta hoon?"
            },
            "modify_order": {
                "en": "I'll help you modify your order. Please provide the changes you'd like to make.",
                "hi": "मैं आपके ऑर्डर को संशोधित करने में मदद करूंगा। कृपया वे परिवर्तन बताएं जो आप करना चाहते हैं।",
                "mixed": "Main aapke order ko modify karne mein help karunga. Changes batayein jo aap karna chahte hain."
            },
            "general_query": {
                "en": "I understand you're looking for something. Could you please provide more details about your order?",
                "hi": "मैं समझता हूं कि आप कुछ ढूंढ रहे हैं। कृपया अपने ऑर्डर के बारे में अधिक विवरण दें?",
                "mixed": "Main samajhta hoon aap kuch dhundh rahe hain. Order ke bare mein details dijiye."
            }
        }
    
    def _build_channel_formatters(self):
        """Build channel-specific formatters"""
        self.channel_formatters = {
            ChannelType.WHATSAPP: {
                "emoji_map": {
                    "place_order": "✅",
                    "check_status": "🔍", 
                    "cancel_order": "❌",
                    "greeting": "👋",
                    "modify_order": "✏️",
                    "general_query": "❓"
                },
                "format_response": self._format_whatsapp_response
            },
            ChannelType.RCS: {
                "format_response": self._format_rcs_response
            },
            ChannelType.SMS: {
                "format_response": self._format_sms_response
            }
        }
    
    def _initialize_metrics(self):
        """Initialize metrics tracking"""
        self.metrics = {
            "total_requests": 0,
            "language_distribution": {},
            "intent_distribution": {},
            "gemini_usage": 0,
            "template_usage": 0,
            "error_count": 0,
            "avg_processing_time": 0.0,
            "channel_distribution": {}
        }
    
    async def emit_order_event(self, order_data: Dict[str, Any], event_type: str = "new_order"):
        """Emit WebSocket event for order updates"""
        if not WEBSOCKET_AVAILABLE:
            logging.warning("WebSocket not available - skipping event emission")
            return
        
        try:
            store_id = order_data.get('store_id', 'default_store')
            order_id = order_data.get('order_id', f"order_{int(time.time())}")
            
            order_event = OrderEvent(
                order_id=order_id,
                store_id=store_id,
                event_type=event_type,
                data=order_data
            )
            
            await socket_manager.emit_new_order(order_data)
            logging.info(f"Emitted {event_type} event for order {order_id}")
            
        except Exception as e:
            logging.error(f"Failed to emit order event: {e}")
    
    async def process_order(
        self, 
        message: str, 
        session_id: str, 
        channel: str = "whatsapp",
        store_id: Optional[str] = None
    ) -> OrderProcessingResult:
        """
        Main method to process order in any Indian language
        
        Args:
            message: Input message in any Indian language
            session_id: Session identifier for tracking
            channel: Communication channel (whatsapp/rcs/sms)
            store_id: Optional store identifier
            
        Returns:
            OrderProcessingResult with complete processing details
        """
        start_time = time.time()
        error_occurred = False
        error_message = None
        
        try:
            # Update metrics
            self.metrics["total_requests"] += 1
            self.metrics["channel_distribution"][channel] = self.metrics["channel_distribution"].get(channel, 0) + 1
            
            # Step 1: Language detection and translation
            lang_result = await indian_multilingual_service.process_indian_order(message, session_id)
            detected_language = lang_result.detected_language
            translated_text = lang_result.translated_text
            
            # Update language distribution
            self.metrics["language_distribution"][detected_language] = self.metrics["language_distribution"].get(detected_language, 0) + 1
            
            # Step 2: Intent classification
            processing_text = translated_text if translated_text else message
            intent_result = indian_intent_classifier.classify(processing_text)
            intent = intent_result.get("intent", "general_query")
            confidence = intent_result.get("confidence", 0.0)
            
            # Update intent distribution
            self.metrics["intent_distribution"][intent] = self.metrics["intent_distribution"].get(intent, 0) + 1
            
            # Step 3: Entity extraction
            entities = indian_commerce_ner.extract_entities(processing_text)
            
            # Step 4: Generate response
            response, gemini_used = await self._generate_response(
                intent, confidence, entities, detected_language, channel, store_id
            )
            
            # Step 5: Format response for channel
            channel_enum = ChannelType(channel.lower())
            formatted_response = self.channel_formatters[channel_enum]["format_response"](
                response, intent, entities, detected_language
            )
            
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Update processing time metrics
            self.metrics["avg_processing_time"] = (
                (self.metrics["avg_processing_time"] * (self.metrics["total_requests"] - 1) + processing_time_ms) 
                / self.metrics["total_requests"]
            )
            
            return OrderProcessingResult(
                response=formatted_response,
                intent=intent,
                confidence=confidence,
                entities=entities,
                language=detected_language,
                processing_time_ms=processing_time_ms,
                channel_format=channel,
                original_text=message,
                translated_text=translated_text,
                gemini_used=gemini_used,
                error_occurred=error_occurred,
                error_message=error_message
            )
            
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            self.metrics["error_count"] += 1
            logging.error(f"Error processing order: {e}")
            
            # Return fallback response
            processing_time_ms = (time.time() - start_time) * 1000
            fallback_response = self._get_fallback_response(detected_language if 'detected_language' in locals() else "en")
            
            return OrderProcessingResult(
                response=fallback_response,
                intent="general_query",
                confidence=0.0,
                entities=[],
                language=detected_language if 'detected_language' in locals() else "en",
                processing_time_ms=processing_time_ms,
                channel_format=channel,
                original_text=message,
                translated_text=None,
                gemini_used=False,
                error_occurred=error_occurred,
                error_message=error_message
            )
    
    async def _generate_response(
        self, 
        intent: str, 
        confidence: float, 
        entities: List[Dict[str, Any]], 
        language: str,
        channel: str,
        store_id: Optional[str]
    ) -> Tuple[str, bool]:
        """
        Generate response using Gemini or templates
        
        Returns:
            Tuple of (response_text, gemini_used)
        """
        # Use Gemini if available and confidence is high
        if self.gemini_model and confidence > 0.7:
            try:
                response = await self._generate_gemini_response(intent, confidence, entities, language, channel, store_id)
                self.metrics["gemini_usage"] += 1
                return response, True
            except Exception as e:
                logging.warning(f"Gemini generation failed, falling back to template: {e}")
        
        # Fallback to template response
        response = self._generate_template_response(intent, entities, language)
        self.metrics["template_usage"] += 1
        return response, False
    
    async def _generate_gemini_response(
        self, 
        intent: str, 
        confidence: float, 
        entities: List[Dict[str, Any]], 
        language: str,
        channel: str,
        store_id: Optional[str]
    ) -> str:
        """Generate response using Gemini"""
        
        # Build context for Gemini
        context = self._build_gemini_context(intent, entities, language, channel, store_id)
        
        # Create prompt
        prompt = f"""
You are VyaparAI, an intelligent order processing assistant for Indian grocery stores.

Context:
- Intent: {intent} (confidence: {confidence:.2f})
- Language: {language}
- Channel: {channel}
- Store ID: {store_id or 'Not specified'}
- Extracted Entities: {json.dumps(entities, indent=2)}

Instructions:
1. Generate a natural, helpful response in {language} language
2. Include all relevant order details from entities
3. Be conversational and friendly
4. Include pricing if available (use ₹ symbol)
5. Mention delivery time (30-45 minutes for orders)
6. Keep response concise but informative
7. Use appropriate tone for {channel} channel

Generate a response:
"""
        
        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                prompt
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini generation error: {e}")
            raise
    
    def _build_gemini_context(self, intent: str, entities: List[Dict[str, Any]], language: str, channel: str, store_id: Optional[str]) -> Dict[str, Any]:
        """Build context for Gemini prompt"""
        return {
            "intent": intent,
            "entities": entities,
            "language": language,
            "channel": channel,
            "store_id": store_id,
            "total_items": len(entities),
            "has_brands": any(entity.get("brand") for entity in entities),
            "total_quantity": sum(entity.get("quantity", 0) for entity in entities)
        }
    
    def _generate_template_response(self, intent: str, entities: List[Dict[str, Any]], language: str) -> str:
        """Generate response using templates"""
        
        # Get template for intent and language
        templates = self.response_templates.get(intent, self.response_templates["general_query"])
        template = templates.get(language, templates.get("en", "Order processed successfully."))
        
        if intent == "place_order" and entities:
            # Format items for template
            items = []
            total = 0
            
            for entity in entities:
                product = entity.get("product", "item")
                quantity = entity.get("quantity", 0)
                unit = entity.get("unit", "")
                brand = entity.get("brand", "")
                
                item_desc = f"{quantity} {unit} {product}".strip()
                if brand:
                    item_desc = f"{brand} {item_desc}"
                items.append(item_desc)
                
                # Estimate price (simplified)
                base_prices = {
                    "rice": 50, "flour": 40, "oil": 120, "milk": 60, 
                    "bread": 30, "noodles": 15, "biscuits": 20, "tea": 50,
                    "coffee": 100, "sugar": 45, "salt": 20
                }
                price_per_unit = base_prices.get(product, 30)
                total += quantity * price_per_unit
            
            items_text = ", ".join(items[:-1]) + f" and {items[-1]}" if len(items) > 1 else items[0]
            
            return template.format(items=items_text, total=total)
        
        return template
    
    def _format_whatsapp_response(self, response: str, intent: str, entities: List[Dict[str, Any]], language: str) -> str:
        """Format response for WhatsApp"""
        emoji_map = self.channel_formatters[ChannelType.WHATSAPP]["emoji_map"]
        emoji = emoji_map.get(intent, "📝")
        
        # Add emoji prefix
        formatted_response = f"{emoji} {response}"
        
        # Add line breaks for better readability
        if len(formatted_response) > 100:
            formatted_response = formatted_response.replace(". ", ".\n")
        
        return formatted_response
    
    def _format_rcs_response(self, response: str, intent: str, entities: List[Dict[str, Any]], language: str) -> str:
        """Format response for RCS (Rich Communication Services)"""
        # For RCS, we return a JSON structure that can be used to create rich cards
        rcs_response = {
            "text": response,
            "intent": intent,
            "entities": entities,
            "language": language,
            "rich_card": {
                "title": f"Order {intent.replace('_', ' ').title()}",
                "description": response,
                "suggestions": self._get_rcs_suggestions(intent)
            }
        }
        
        return json.dumps(rcs_response, ensure_ascii=False)
    
    def _format_sms_response(self, response: str, intent: str, entities: List[Dict[str, Any]], language: str) -> str:
        """Format response for SMS"""
        # SMS has 160 character limit, so we need to be concise
        if len(response) > 160:
            # Truncate and add ellipsis
            response = response[:157] + "..."
        
        # Remove emojis and special characters for SMS
        response = re.sub(r'[^\w\s\.\,\!\?\-\(\)]', '', response)
        
        return response
    
    def _get_rcs_suggestions(self, intent: str) -> List[Dict[str, str]]:
        """Get RCS suggestions based on intent"""
        suggestions = {
            "place_order": [
                {"text": "Track Order", "action": "track_order"},
                {"text": "Modify Order", "action": "modify_order"},
                {"text": "Cancel Order", "action": "cancel_order"}
            ],
            "check_status": [
                {"text": "Track Order", "action": "track_order"},
                {"text": "Place New Order", "action": "place_order"},
                {"text": "Contact Support", "action": "contact_support"}
            ],
            "cancel_order": [
                {"text": "Place New Order", "action": "place_order"},
                {"text": "Track Refund", "action": "track_refund"},
                {"text": "Contact Support", "action": "contact_support"}
            ]
        }
        
        return suggestions.get(intent, [
            {"text": "Place Order", "action": "place_order"},
            {"text": "Check Status", "action": "check_status"},
            {"text": "Contact Support", "action": "contact_support"}
        ])
    
    def _get_fallback_response(self, language: str) -> str:
        """Get fallback response when processing fails"""
        fallback_templates = {
            "en": "Sorry, I couldn't process your request. Please try again or contact support.",
            "hi": "क्षमा करें, मैं आपका अनुरोध प्रोसेस नहीं कर सका। कृपया पुनः प्रयास करें या सहायता से संपर्क करें।",
            "mixed": "Sorry, main aapka request process nahi kar saka. Please try again ya support se contact karein."
        }
        
        return fallback_templates.get(language, fallback_templates["en"])
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset metrics"""
        self._initialize_metrics()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        total_requests = self.metrics["total_requests"]
        if total_requests == 0:
            return {"message": "No requests processed yet"}
        
        return {
            "total_requests": total_requests,
            "avg_processing_time_ms": self.metrics["avg_processing_time"],
            "error_rate": (self.metrics["error_count"] / total_requests) * 100,
            "gemini_usage_rate": (self.metrics["gemini_usage"] / total_requests) * 100,
            "template_usage_rate": (self.metrics["template_usage"] / total_requests) * 100,
            "top_languages": sorted(
                self.metrics["language_distribution"].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5],
            "top_intents": sorted(
                self.metrics["intent_distribution"].items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5],
            "channel_distribution": self.metrics["channel_distribution"]
        }

# Global instance for easy access
unified_order_service = UnifiedOrderService()
