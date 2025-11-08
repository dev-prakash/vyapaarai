from sqlalchemy import Column, Integer, String, Decimal, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from decimal import Decimal as PyDecimal
from datetime import datetime
import uuid

class ProductStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"
    OUT_OF_STOCK = "out_of_stock"

class ProductUnit(PyEnum):
    KG = "kg"
    GRAM = "gram"
    LITER = "liter"
    ML = "ml"
    PIECE = "piece"
    PACKET = "packet"
    BOX = "box"
    DOZEN = "dozen"
    BOTTLE = "bottle"
    CAN = "can"

class MovementType(PyEnum):
    IN = "in"
    OUT = "out"
    ADJUSTMENT = "adjustment"
    SET = "set"

# Base class for SQLAlchemy models
class Base:
    pass

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(50), nullable=False, default="STORE-001")
    
    # Basic product information
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(String(100), nullable=False)
    subcategory = Column(String(100))
    
    # Pricing
    price = Column(Decimal(10, 2), nullable=False)
    mrp = Column(Decimal(10, 2))
    cost_price = Column(Decimal(10, 2))
    
    # Inventory tracking
    current_stock = Column(Integer, default=0)
    min_stock_level = Column(Integer, default=10)
    max_stock_level = Column(Integer, default=1000)
    unit = Column(String(20), default="piece")
    
    # Product details
    brand = Column(String(100))
    barcode = Column(String(50), unique=True)
    sku = Column(String(50), unique=True)
    
    # Status and flags
    status = Column(String(20), default=ProductStatus.ACTIVE.value)
    is_featured = Column(Boolean, default=False)
    is_available = Column(Boolean, default=True)
    
    # Supplier information
    supplier_name = Column(String(200))
    supplier_contact = Column(String(50))
    supplier_email = Column(String(100))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    stock_movements = relationship("StockMovement", back_populates="product", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert product to dictionary"""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "subcategory": self.subcategory,
            "price": float(self.price) if self.price else None,
            "mrp": float(self.mrp) if self.mrp else None,
            "cost_price": float(self.cost_price) if self.cost_price else None,
            "current_stock": self.current_stock,
            "min_stock_level": self.min_stock_level,
            "max_stock_level": self.max_stock_level,
            "unit": self.unit,
            "brand": self.brand,
            "barcode": self.barcode,
            "sku": self.sku,
            "status": self.status,
            "is_featured": self.is_featured,
            "is_available": self.is_available,
            "supplier_name": self.supplier_name,
            "supplier_contact": self.supplier_contact,
            "supplier_email": self.supplier_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "stock_status": self.stock_status,
            "is_low_stock": self.is_low_stock,
            "is_out_of_stock": self.is_out_of_stock
        }
    
    @property
    def is_low_stock(self):
        """Check if product is low on stock"""
        return self.current_stock <= self.min_stock_level
    
    @property
    def is_out_of_stock(self):
        """Check if product is out of stock"""
        return self.current_stock <= 0
    
    @property
    def stock_status(self):
        """Get stock status string"""
        if self.is_out_of_stock:
            return "out_of_stock"
        elif self.is_low_stock:
            return "low_stock"
        else:
            return "in_stock"
    
    @property
    def stock_percentage(self):
        """Get stock level as percentage of max stock"""
        if self.max_stock_level <= 0:
            return 0
        return min(100, (self.current_stock / self.max_stock_level) * 100)

class StockMovement(Base):
    __tablename__ = "stock_movements"
    
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(50), ForeignKey("products.id"), nullable=False)
    store_id = Column(String(50), nullable=False, default="STORE-001")
    
    # Movement details
    movement_type = Column(String(20), nullable=False)  # "in", "out", "adjustment", "set"
    quantity = Column(Integer, nullable=False)
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    
    # Reference and reason
    reason = Column(String(200))
    reference_id = Column(String(50))  # Order ID, Purchase ID, etc.
    reference_type = Column(String(50))  # "order", "purchase", "adjustment", etc.
    
    # Audit trail
    created_by = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product = relationship("Product", back_populates="stock_movements")
    
    def to_dict(self):
        """Convert stock movement to dictionary"""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "store_id": self.store_id,
            "movement_type": self.movement_type,
            "quantity": self.quantity,
            "previous_stock": self.previous_stock,
            "new_stock": self.new_stock,
            "reason": self.reason,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "created_by": self.created_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class ProductCategory(Base):
    __tablename__ = "product_categories"
    
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(50), nullable=False, default="STORE-001")
    
    # Category details
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parent_category_id = Column(String(50), ForeignKey("product_categories.id"))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert category to dictionary"""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "name": self.name,
            "description": self.description,
            "parent_category_id": self.parent_category_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id = Column(String(50), nullable=False, default="STORE-001")
    
    # Supplier details
    name = Column(String(200), nullable=False)
    contact_person = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(Text)
    
    # Business details
    gst_number = Column(String(20))
    pan_number = Column(String(20))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert supplier to dictionary"""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "name": self.name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "gst_number": self.gst_number,
            "pan_number": self.pan_number,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
