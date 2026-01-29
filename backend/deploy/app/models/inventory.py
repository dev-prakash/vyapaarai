from sqlalchemy import Column, String, DateTime, Numeric, Integer, JSON, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    name = Column(String(255), nullable=False)
    name_translations = Column(JSON)  # {"hi": "चावल", "ta": "அரிசி"}
    barcode = Column(String(50), index=True)
    category = Column(String(100))
    brand = Column(String(100))
    unit = Column(String(20))  # kg, litre, packet, dozen
    price = Column(Numeric(10, 2))
    cost = Column(Numeric(10, 2))
    current_stock = Column(Numeric(10, 3), default=0)
    min_stock = Column(Numeric(10, 3), default=0)
    max_stock = Column(Numeric(10, 3))
    image_url = Column(String(500))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)  # Positive for in, negative for out
    operation = Column(String(20), nullable=False)  # "in", "out", "adjustment", "return"
    reference_id = Column(String(100))  # Order ID, purchase ID, etc.
    notes = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

class ProductCategory(Base):
    __tablename__ = "product_categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    parent_category_id = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    supplier_name = Column(String(255))
    supplier_phone = Column(String(20))
    total_amount = Column(Numeric(10, 2))
    status = Column(String(20), default="pending")  # pending, received, cancelled
    notes = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_price = Column(Numeric(10, 2))
    total_price = Column(Numeric(10, 2))
    received_quantity = Column(Numeric(10, 3), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

