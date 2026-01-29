from sqlalchemy import Column, String, DateTime, Numeric, Integer, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"))
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255))
    email = Column(String(255))
    address = Column(JSON)  # {"street": "", "city": "", "pincode": ""}
    tags = Column(JSON, default=list)  # ["regular", "vip", "wholesale", "new"]
    credit_limit = Column(Numeric(10, 2), default=0)
    current_balance = Column(Numeric(10, 2), default=0)  # Amount owed
    total_orders = Column(Integer, default=0)
    total_spent = Column(Numeric(10, 2), default=0)
    last_order_date = Column(DateTime)
    preferred_language = Column(String(10), default="en")
    whatsapp_enabled = Column(Boolean, default=True)
    notes = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CustomerCredit(Base):
    __tablename__ = "customer_credits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"))
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"))
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String(20))  # "credit", "payment", "order"
    description = Column(String(255))
    order_id = Column(String(50))
    balance_after = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

class CustomerCreditTransaction(Base):
    __tablename__ = "customer_credit_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)  # Positive for credit, negative for debit
    transaction_type = Column(String(20), nullable=False)  # "credit", "payment", "order"
    reference_id = Column(String(100))  # Order ID or transaction reference
    notes = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    owner_phone = Column(String(20))
    address = Column(JSON)
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    phone = Column(String(20), nullable=False)
    name = Column(String(255))
    role = Column(String(20), default="staff")  # "owner", "manager", "staff"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
