"""
Hybrid Order Service for VyaparAI
Extends UnifiedOrderService with hybrid database integration
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import uuid

# Local imports
from .unified_order_service import UnifiedOrderService, OrderProcessingResult, ChannelType
from ..database.hybrid_db import hybrid_db, OrderData, SessionData, HybridOrderResult

logger = logging.getLogger(__name__)

@dataclass
class HybridOrderProcessingResult:
    """Extended result from hybrid order processing"""
    # Base order processing result
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
    
    # Hybrid database results
    order_id: Optional[str] = None
    total_amount: Optional[float] = None
    store_details: Optional[Dict[str, Any]] = None
    product_details: Optional[List[Dict[str, Any]]] = None
    customer_analytics: Optional[Dict[str, Any]] = None
    db_processing_time_ms: float = 0.0
    db_errors: List[str] = None

class HybridOrderService(UnifiedOrderService):
    """
    Hybrid Order Service
    Extends UnifiedOrderService with hybrid database integration
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        """Initialize the hybrid order service"""
        super().__init__(gemini_api_key)
        self.hybrid_db = hybrid_db
        self._initialize_hybrid_metrics()

    def _initialize_hybrid_metrics(self):
        """Initialize hybrid-specific metrics"""
        self.hybrid_metrics = {
            "db_operations": {
                "dynamodb": 0,
                "postgresql": 0,
                "hybrid": 0
            },
            "db_errors": {
                "dynamodb": 0,
                "postgresql": 0
            },
            "avg_db_processing_time": 0.0,
            "store_lookups": 0,
            "product_searches": 0,
            "analytics_queries": 0
        }

    async def process_order_hybrid(
        self,
        message: str,
        session_id: str,
        channel: str = "whatsapp",
        store_id: Optional[str] = None,
        customer_phone: Optional[str] = None
    ) -> HybridOrderProcessingResult:
        """
        Process order with hybrid database integration

        Args:
            message: Input message in any Indian language
            session_id: Session identifier for tracking
            channel: Communication channel (whatsapp/rcs/sms)
            store_id: Store identifier (required for hybrid processing)
            customer_phone: Customer phone number (optional)

        Returns:
            HybridOrderProcessingResult with complete processing and database details
        """
        start_time = time.time()
        db_start_time = time.time()
        
        # Step 1: Process with base unified service
        base_result = await self.process_order(message, session_id, channel, store_id)
        
        # Step 2: Hybrid database operations
        db_errors = []
        order_id = None
        total_amount = None
        store_details = None
        product_details = None
        customer_analytics = None

        try:
            if store_id:
                # Get store details from PostgreSQL
                store_result = await self.hybrid_db.get_store_details(store_id)
                if store_result.success:
                    store_details = asdict(store_result.data)
                    self.hybrid_metrics["store_lookups"] += 1
                else:
                    db_errors.append(f"Store lookup failed: {store_result.error}")
                    self.hybrid_metrics["db_errors"]["postgresql"] += 1

                # Search products if entities contain product names
                if base_result.entities:
                    product_details = await self._search_products_for_entities(
                        store_id, base_result.entities
                    )

                # Calculate order total using PostgreSQL
                if base_result.entities:
                    total_result = await self.hybrid_db.calculate_order_total(
                        base_result.entities, store_id
                    )
                    if total_result.success:
                        total_amount = total_result.data['total']
                        self.hybrid_metrics["db_operations"]["postgresql"] += 1
                    else:
                        db_errors.append(f"Total calculation failed: {total_result.error}")
                        self.hybrid_metrics["db_errors"]["postgresql"] += 1

                # Create order in DynamoDB
                order_data = OrderData(
                    order_id=str(uuid.uuid4()),
                    customer_phone=customer_phone or "unknown",
                    store_id=store_id,
                    items=base_result.entities,
                    total_amount=total_amount or 0.0,
                    status="pending",
                    channel=base_result.channel_format,
                    language=base_result.language,
                    intent=base_result.intent,
                    confidence=base_result.confidence,
                    entities=base_result.entities,
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat()
                )

                order_result = await self.hybrid_db.create_order(order_data)
                if order_result.success:
                    order_id = order_data.order_id
                    self.hybrid_metrics["db_operations"]["dynamodb"] += 1
                else:
                    db_errors.append(f"Order creation failed: {order_result.error}")
                    self.hybrid_metrics["db_errors"]["dynamodb"] += 1

            # Get customer analytics if phone provided
            if customer_phone:
                analytics_result = await self.hybrid_db.get_customer_analytics(customer_phone)
                if analytics_result.success:
                    customer_analytics = analytics_result.data
                    self.hybrid_metrics["analytics_queries"] += 1
                else:
                    db_errors.append(f"Customer analytics failed: {analytics_result.error}")
                    self.hybrid_metrics["db_errors"]["postgresql"] += 1

            # Create or update session
            if session_id:
                await self._create_or_update_session(
                    session_id, customer_phone, store_id, base_result
                )

        except Exception as e:
            logger.error(f"Error in hybrid database operations: {e}")
            db_errors.append(f"Database operation error: {str(e)}")

        db_processing_time = (time.time() - db_start_time) * 1000
        total_processing_time = (time.time() - start_time) * 1000

        # Update hybrid metrics
        self._update_hybrid_metrics(db_processing_time)

        return HybridOrderProcessingResult(
            # Base result fields
            response=base_result.response,
            intent=base_result.intent,
            confidence=base_result.confidence,
            entities=base_result.entities,
            language=base_result.language,
            processing_time_ms=total_processing_time,
            channel_format=base_result.channel_format,
            original_text=base_result.original_text,
            translated_text=base_result.translated_text,
            gemini_used=base_result.gemini_used,
            error_occurred=base_result.error_occurred,
            error_message=base_result.error_message,
            
            # Hybrid database fields
            order_id=order_id,
            total_amount=total_amount,
            store_details=store_details,
            product_details=product_details,
            customer_analytics=customer_analytics,
            db_processing_time_ms=db_processing_time,
            db_errors=db_errors
        )

    async def _search_products_for_entities(
        self, 
        store_id: str, 
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Search products for extracted entities"""
        product_details = []
        
        for entity in entities:
            product_name = entity.get('product', '')
            if product_name:
                search_result = await self.hybrid_db.search_products(
                    store_id, product_name, limit=3
                )
                if search_result.success:
                    products = [asdict(p) for p in search_result.data]
                    product_details.extend(products)
                    self.hybrid_metrics["product_searches"] += 1

        return product_details

    async def _create_or_update_session(
        self,
        session_id: str,
        customer_phone: Optional[str],
        store_id: Optional[str],
        order_result: OrderProcessingResult
    ):
        """Create or update session in DynamoDB"""
        try:
            session_data = SessionData(
                session_id=session_id,
                customer_phone=customer_phone or "unknown",
                store_id=store_id or "unknown",
                context={
                    "last_intent": order_result.intent,
                    "last_language": order_result.language,
                    "last_entities": order_result.entities,
                    "last_confidence": order_result.confidence,
                    "last_channel": order_result.channel_format
                },
                last_activity=datetime.utcnow().isoformat(),
                ttl=int(time.time()) + 86400  # 24 hours TTL
            )

            await self.hybrid_db.create_session(session_data)
            self.hybrid_metrics["db_operations"]["dynamodb"] += 1

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            self.hybrid_metrics["db_errors"]["dynamodb"] += 1

    async def get_order_details(self, order_id: str) -> HybridOrderResult:
        """Get order details from DynamoDB"""
        return await self.hybrid_db.get_order(order_id)

    async def update_order_status(self, order_id: str, status: str) -> HybridOrderResult:
        """Update order status in DynamoDB"""
        return await self.hybrid_db.update_order_status(order_id, status)

    async def get_customer_orders(self, customer_phone: str, limit: int = 10) -> HybridOrderResult:
        """Get customer orders from DynamoDB"""
        return await self.hybrid_db.get_customer_orders(customer_phone, limit)

    async def get_store_analytics(self, store_id: str, days: int = 30) -> HybridOrderResult:
        """Get store analytics from PostgreSQL"""
        return await self.hybrid_db.get_store_analytics(store_id, days)

    async def get_customer_analytics(self, customer_phone: str) -> HybridOrderResult:
        """Get customer analytics from PostgreSQL"""
        return await self.hybrid_db.get_customer_analytics(customer_phone)

    async def search_products(self, store_id: str, query: str, limit: int = 10) -> HybridOrderResult:
        """Search products in PostgreSQL"""
        return await self.hybrid_db.search_products(store_id, query, limit)

    def _update_hybrid_metrics(self, db_processing_time: float):
        """Update hybrid-specific metrics"""
        total_ops = (
            self.hybrid_metrics["db_operations"]["dynamodb"] +
            self.hybrid_metrics["db_operations"]["postgresql"] +
            self.hybrid_metrics["db_operations"]["hybrid"]
        )
        
        if total_ops > 0:
            self.hybrid_metrics["avg_db_processing_time"] = (
                (self.hybrid_metrics["avg_db_processing_time"] * (total_ops - 1) + db_processing_time)
                / total_ops
            )

    def get_hybrid_metrics(self) -> Dict[str, Any]:
        """Get hybrid-specific metrics"""
        return self.hybrid_metrics.copy()

    def get_hybrid_performance_summary(self) -> Dict[str, Any]:
        """Get hybrid performance summary"""
        total_ops = sum(self.hybrid_metrics["db_operations"].values())
        total_errors = sum(self.hybrid_metrics["db_errors"].values())
        
        if total_ops == 0:
            return {"message": "No hybrid operations performed yet"}

        return {
            "total_database_operations": total_ops,
            "avg_db_processing_time_ms": self.hybrid_metrics["avg_db_processing_time"],
            "error_rate": (total_errors / total_ops) * 100 if total_ops > 0 else 0,
            "database_operations": self.hybrid_metrics["db_operations"],
            "database_errors": self.hybrid_metrics["db_errors"],
            "store_lookups": self.hybrid_metrics["store_lookups"],
            "product_searches": self.hybrid_metrics["product_searches"],
            "analytics_queries": self.hybrid_metrics["analytics_queries"]
        }

    async def process_order_with_context(
        self,
        message: str,
        session_id: str,
        channel: str = "whatsapp",
        store_id: Optional[str] = None,
        customer_phone: Optional[str] = None
    ) -> HybridOrderProcessingResult:
        """
        Process order with context from previous interactions
        """
        # Get session context if available
        context = await self._get_session_context(session_id)
        
        # Enhance message with context if available
        enhanced_message = self._enhance_message_with_context(message, context)
        
        # Process with enhanced message
        result = await self.process_order_hybrid(
            enhanced_message, session_id, channel, store_id, customer_phone
        )
        
        return result

    async def _get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session context from DynamoDB"""
        try:
            # This would require implementing get_session in hybrid_db
            # For now, return None
            return None
        except Exception as e:
            logger.error(f"Error getting session context: {e}")
            return None

    def _enhance_message_with_context(
        self, 
        message: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Enhance message with context from previous interactions"""
        if not context:
            return message

        # Add context information to help with processing
        enhanced_parts = [message]
        
        if context.get("last_intent"):
            enhanced_parts.append(f"Previous intent: {context['last_intent']}")
        
        if context.get("last_entities"):
            entities_text = ", ".join([
                f"{e.get('product', '')} {e.get('quantity', '')} {e.get('unit', '')}"
                for e in context["last_entities"]
            ])
            if entities_text:
                enhanced_parts.append(f"Previous items: {entities_text}")

        return " | ".join(enhanced_parts)

    async def close(self):
        """Close database connections"""
        await self.hybrid_db.close()

# Global instance
hybrid_order_service = HybridOrderService()
