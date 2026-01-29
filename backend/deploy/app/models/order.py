from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentMethod(enum.Enum):
    UPI = "upi"
    CARD = "card"
    COD = "cod"
    WALLET = "wallet"

class Order(Base):
    __tablename__ = "orders"
    
    # Basic order fields
    id = Column(String(50), primary_key=True)
    store_id = Column(String(50), nullable=False, default="STORE-001")
    
    # Customer information
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_email = Column(String(100), nullable=True)
    delivery_address = Column(Text, nullable=False)
    
    # Order items (JSON stored as text)
    items = Column(Text, nullable=False)  # JSON string of order items
    
    # Pricing
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    delivery_fee = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    
    # Order status
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    
    # Payment information
    payment_id = Column(String(100), nullable=True)
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    payment_gateway_response = Column(Text, nullable=True)  # JSON string of gateway response
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    payment_created_at = Column(DateTime, nullable=True)
    payment_completed_at = Column(DateTime, nullable=True)
    
    # Delivery information
    delivery_time = Column(String(50), nullable=True, default="2 hours")
    delivery_notes = Column(Text, nullable=True)
    
    # Additional fields
    channel = Column(String(20), nullable=False, default="web")  # web, whatsapp, phone
    language = Column(String(10), nullable=False, default="en")  # en, hi, etc.
    is_urgent = Column(Boolean, nullable=False, default=False)
    
    def to_dict(self):
        """Convert order to dictionary"""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_email": self.customer_email,
            "delivery_address": self.delivery_address,
            "items": self.items,  # JSON string
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "delivery_fee": self.delivery_fee,
            "total_amount": self.total_amount,
            "status": self.status.value if self.status else None,
            "payment_id": self.payment_id,
            "payment_status": self.payment_status.value if self.payment_status else None,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "payment_gateway_response": self.payment_gateway_response,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "payment_created_at": self.payment_created_at.isoformat() if self.payment_created_at else None,
            "payment_completed_at": self.payment_completed_at.isoformat() if self.payment_completed_at else None,
            "delivery_time": self.delivery_time,
            "delivery_notes": self.delivery_notes,
            "channel": self.channel,
            "language": self.language,
            "is_urgent": self.is_urgent
        }

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(50), ForeignKey("orders.id"), nullable=False)
    
    # Product information
    product_id = Column(String(50), nullable=True)
    product_name = Column(String(100), nullable=False)
    name = Column(String(100), nullable=True)  # Alias for product_name
    
    # Quantity and pricing
    quantity = Column(Float, nullable=False, default=1.0)
    unit = Column(String(20), nullable=True, default="pieces")
    unit_price = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False, default=0.0)
    
    # Additional fields
    notes = Column(Text, nullable=True)
    
    # Relationship
    order = relationship("Order", back_populates="order_items")
    
    def to_dict(self):
        """Convert order item to dictionary"""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "name": self.name or self.product_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "notes": self.notes
        }

# Add relationship to Order model
Order.order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
