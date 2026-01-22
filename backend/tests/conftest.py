"""
VyaparAI Test Configuration and Fixtures

This module provides:
- Pytest configuration
- Test fixtures for database, services, and API client
- Mock factories for common test data
- Async test support
"""

import os
import sys
import pytest
import asyncio
from typing import AsyncGenerator, Generator, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from decimal import Decimal

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test_secret_key_for_testing_only_32chars!"
os.environ["AWS_REGION"] = "ap-south-1"
os.environ["DYNAMODB_ORDERS_TABLE"] = "vyaparai-orders-test"
os.environ["DYNAMODB_STORES_TABLE"] = "vyaparai-stores-test"
os.environ["DYNAMODB_INVENTORY_TABLE"] = "vyaparai-inventory-test"
# Khata (Credit Management) tables
os.environ["DYNAMODB_KHATA_TRANSACTIONS_TABLE"] = "vyaparai-khata-transactions-test"
os.environ["DYNAMODB_CUSTOMER_BALANCES_TABLE"] = "vyaparai-customer-balances-test"
os.environ["DYNAMODB_PAYMENT_REMINDERS_TABLE"] = "vyaparai-payment-reminders-test"
os.environ["DYNAMODB_IDEMPOTENCY_KEYS_TABLE"] = "vyaparai-idempotency-keys-test"

from fastapi.testclient import TestClient
from httpx import AsyncClient


# =============================================================================
# Pytest Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Application Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create test application instance."""
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture
def client(app) -> Generator:
    """Create synchronous test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def async_client(app) -> AsyncGenerator:
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Database Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB client for testing."""
    mock = MagicMock()
    mock.Table.return_value = MagicMock()
    return mock


@pytest.fixture
def mock_db_manager(mock_dynamodb):
    """Mock DatabaseManager for testing."""
    with patch("app.core.database.db_manager") as mock_manager:
        mock_manager.get_dynamodb.return_value = mock_dynamodb
        mock_manager.get_dynamodb_client.return_value = mock_dynamodb
        mock_manager.health_check.return_value = {
            "dynamodb": True,
            "postgres_pool": False,
            "redis": True
        }
        yield mock_manager


@pytest.fixture
def mock_hybrid_db():
    """Mock HybridDatabase for order operations."""
    mock = MagicMock()

    # Mock successful order creation
    mock.create_order = AsyncMock(return_value=MagicMock(
        success=True,
        data={"order_id": "ORD-TEST-001"},
        error=None
    ))

    # Mock successful order retrieval
    mock.get_order = AsyncMock(return_value=MagicMock(
        success=True,
        data={
            "order_id": "ORD-TEST-001",
            "status": "pending",
            "total_amount": Decimal("150.00"),
            "items": []
        },
        error=None
    ))

    # Mock successful status update
    mock.update_order_status = AsyncMock(return_value=MagicMock(
        success=True,
        error=None
    ))

    return mock


# =============================================================================
# Service Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_inventory_service():
    """Mock InventoryService for testing."""
    mock = MagicMock()

    # Mock product retrieval
    mock.get_product = AsyncMock(return_value={
        "product_id": "PROD-001",
        "name": "Test Product",
        "price": Decimal("50.00"),
        "current_stock": 100,
        "status": "active"
    })

    # Mock availability check
    mock.check_availability = AsyncMock(return_value={
        "available": True,
        "current_stock": 100,
        "requested": 5
    })

    # Mock stock update
    mock.update_stock = AsyncMock(return_value={
        "success": True,
        "new_stock": 95,
        "product_id": "PROD-001"
    })

    # Mock bulk transactional update
    mock.update_stock_bulk_transactional = AsyncMock(return_value={
        "success": True,
        "updated_count": 2,
        "failed_count": 0
    })

    return mock


@pytest.fixture
def mock_payment_service():
    """Mock PaymentService for testing."""
    mock = MagicMock()

    mock.process_payment = AsyncMock(return_value={
        "success": True,
        "transaction_id": "TXN-TEST-001",
        "status": "completed"
    })

    mock.verify_payment = AsyncMock(return_value={
        "verified": True,
        "amount": Decimal("150.00")
    })

    return mock


@pytest.fixture
def mock_unified_order_service():
    """Mock UnifiedOrderService for testing."""
    from app.services.unified_order_service import OrderProcessingResult

    mock = MagicMock()
    mock.process_order = AsyncMock(return_value=OrderProcessingResult(
        original_text="test order",
        language="en",
        intent="place_order",
        confidence=0.95,
        entities=[],
        response="Order processed successfully",
        processing_time_ms=50.0
    ))

    return mock


# =============================================================================
# Redis Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.ping = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_rate_limiter(mock_redis):
    """Mock rate limiter for testing."""
    with patch("app.middleware.rate_limit.redis_client", mock_redis):
        yield mock_redis


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture
def test_store_owner_token():
    """Generate test JWT token for store owner."""
    from app.core.security import create_store_owner_token
    return create_store_owner_token(
        user_id="test_user_001",
        store_id="STORE-TEST-001",
        email="test@store.com"
    )


@pytest.fixture
def test_customer_token():
    """Generate test JWT token for customer."""
    from app.core.security import create_customer_token
    return create_customer_token(
        customer_id="CUST-TEST-001",
        phone="+919876543210"
    )


@pytest.fixture
def test_admin_token():
    """Generate test JWT token for admin."""
    from app.core.security import create_admin_token
    return create_admin_token(
        user_id="admin_001",
        email="admin@vyaparai.com",
        role="admin"
    )


@pytest.fixture
def auth_headers_store_owner(test_store_owner_token):
    """Authorization headers for store owner."""
    return {"Authorization": f"Bearer {test_store_owner_token}"}


@pytest.fixture
def auth_headers_customer(test_customer_token):
    """Authorization headers for customer."""
    return {"Authorization": f"Bearer {test_customer_token}"}


@pytest.fixture
def auth_headers_admin(test_admin_token):
    """Authorization headers for admin."""
    return {"Authorization": f"Bearer {test_admin_token}"}


# =============================================================================
# Test Data Factories
# =============================================================================

@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "order_id": "ORD-TEST-001",
        "customer_phone": "+919876543210",
        "store_id": "STORE-TEST-001",
        "items": [
            {
                "product_id": "PROD-001",
                "name": "Rice",
                "quantity": 2,
                "price": Decimal("50.00"),
                "unit": "kg"
            },
            {
                "product_id": "PROD-002",
                "name": "Dal",
                "quantity": 1,
                "price": Decimal("80.00"),
                "unit": "kg"
            }
        ],
        "total_amount": Decimal("180.00"),
        "status": "pending",
        "payment_status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "product_id": "PROD-001",
        "store_id": "STORE-TEST-001",
        "name": "Basmati Rice",
        "category": "Grains & Cereals",
        "price": Decimal("120.00"),
        "mrp": Decimal("150.00"),
        "current_stock": 50,
        "min_stock_level": 10,
        "max_stock_level": 200,
        "unit": "kg",
        "status": "active",
        "barcode": "8901234567890"
    }


@pytest.fixture
def sample_store_data():
    """Sample store data for testing."""
    return {
        "store_id": "STORE-TEST-001",
        "name": "Test Kirana Store",
        "owner_name": "Test Owner",
        "phone": "+919876543210",
        "email": "test@store.com",
        "address": "123 Test Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400001",
        "status": "active",
        "is_verified": True
    }


@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "customer_id": "CUST-TEST-001",
        "phone": "+919876543210",
        "name": "Test Customer",
        "email": "customer@test.com",
        "addresses": [
            {
                "id": "ADDR-001",
                "label": "Home",
                "address": "456 Customer Lane",
                "city": "Mumbai",
                "pincode": "400002",
                "is_default": True
            }
        ]
    }


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def freeze_time():
    """Fixture to freeze time for consistent testing."""
    from unittest.mock import patch
    from datetime import datetime

    frozen_time = datetime(2025, 12, 3, 12, 0, 0)

    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = frozen_time
        mock_dt.utcnow.return_value = frozen_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield frozen_time


@pytest.fixture
def capture_logs():
    """Fixture to capture log output for testing."""
    import logging
    from io import StringIO

    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)

    logger = logging.getLogger()
    logger.addHandler(handler)

    yield log_capture

    logger.removeHandler(handler)


# =============================================================================
# Khata (Credit Management) Fixtures
# =============================================================================

@pytest.fixture
def mock_khata_db():
    """Mock KhataDatabase for testing credit management operations."""
    from app.database.khata_db import KhataResult, CustomerBalance, KhataTransaction, PaymentReminder

    mock = MagicMock()

    # Mock customer balance operations
    mock.get_customer_balance = AsyncMock(return_value=KhataResult(
        success=True,
        data=CustomerBalance(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            customer_name="Test Customer",
            outstanding_balance=Decimal("500.00"),
            credit_limit=Decimal("5000.00"),
            version=1
        ),
        processing_time_ms=5.0
    ))

    mock.create_customer_balance = AsyncMock(return_value=KhataResult(
        success=True,
        data=CustomerBalance(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            customer_name="New Customer",
            outstanding_balance=Decimal("0.00"),
            credit_limit=Decimal("5000.00"),
            version=1
        ),
        processing_time_ms=10.0
    ))

    mock.update_customer_balance = AsyncMock(return_value=KhataResult(
        success=True,
        data=CustomerBalance(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            customer_name="Test Customer",
            outstanding_balance=Decimal("1000.00"),
            credit_limit=Decimal("5000.00"),
            version=2
        ),
        processing_time_ms=15.0
    ))

    mock.get_customers_with_balance = AsyncMock(return_value=KhataResult(
        success=True,
        data=[],
        next_cursor=None,
        processing_time_ms=20.0
    ))

    # Mock transaction operations
    mock.create_transaction = AsyncMock(return_value=KhataResult(
        success=True,
        data=KhataTransaction(
            transaction_id="TXN-TEST-001",
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            transaction_type="credit_sale",
            amount=Decimal("500.00"),
            balance_before=Decimal("0.00"),
            balance_after=Decimal("500.00"),
            created_at=datetime.utcnow().isoformat(),
            created_by="owner@test.com"
        ),
        processing_time_ms=10.0
    ))

    mock.get_transaction = AsyncMock(return_value=KhataResult(
        success=True,
        data=None,
        processing_time_ms=5.0
    ))

    mock.get_customer_transactions = AsyncMock(return_value=KhataResult(
        success=True,
        data=[],
        next_cursor=None,
        processing_time_ms=15.0
    ))

    # Mock idempotency operations
    mock.check_idempotency_key = AsyncMock(return_value=None)
    mock.store_idempotency_key = AsyncMock(return_value=True)

    # Mock reminder operations
    mock.create_reminder = AsyncMock(return_value=KhataResult(
        success=True,
        data=PaymentReminder(
            reminder_id="REM-TEST-001",
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            outstanding_amount=Decimal("500.00"),
            scheduled_at=datetime.utcnow().isoformat(),
            status="scheduled",
            reminder_type="sms",
            created_at=datetime.utcnow().isoformat()
        ),
        processing_time_ms=8.0
    ))

    mock.get_pending_reminders = AsyncMock(return_value=KhataResult(
        success=True,
        data=[],
        next_cursor=None,
        processing_time_ms=10.0
    ))

    mock.update_reminder_status = AsyncMock(return_value=KhataResult(
        success=True,
        data={"status": "sent"},
        processing_time_ms=5.0
    ))

    # Mock aggregate operations
    mock.get_store_outstanding_summary = AsyncMock(return_value=KhataResult(
        success=True,
        data={
            "store_id": "STORE-TEST-001",
            "total_outstanding": 15000.00,
            "total_credit_limit": 50000.00,
            "total_customers": 10,
            "customers_with_balance": 5,
            "utilization_rate": 30.0
        },
        processing_time_ms=50.0
    ))

    return mock


@pytest.fixture
def mock_khata_service():
    """Mock KhataTransactionService for testing."""
    mock = MagicMock()

    # Mock credit sale
    mock.record_credit_sale = AsyncMock(return_value={
        "success": True,
        "transaction_id": "TXN-TEST-001",
        "new_balance": Decimal("500.00"),
        "message": "Credit sale recorded successfully"
    })

    # Mock payment
    mock.record_payment = AsyncMock(return_value={
        "success": True,
        "transaction_id": "PMT-TEST-001",
        "new_balance": Decimal("0.00"),
        "message": "Payment recorded successfully"
    })

    # Mock balance adjustment
    mock.adjust_balance = AsyncMock(return_value={
        "success": True,
        "transaction_id": "ADJ-TEST-001",
        "new_balance": Decimal("450.00"),
        "message": "Balance adjusted successfully"
    })

    # Mock ledger
    mock.get_customer_ledger = AsyncMock(return_value={
        "success": True,
        "transactions": [],
        "opening_balance": Decimal("0.00"),
        "closing_balance": Decimal("500.00"),
        "next_cursor": None
    })

    return mock


@pytest.fixture
def sample_khata_transaction_data():
    """Sample Khata transaction data for testing."""
    return {
        "transaction_id": "TXN-TEST-001",
        "store_id": "STORE-TEST-001",
        "customer_phone": "+919876543210",
        "transaction_type": "credit_sale",
        "amount": Decimal("500.00"),
        "balance_before": Decimal("0.00"),
        "balance_after": Decimal("500.00"),
        "created_at": datetime.utcnow().isoformat(),
        "created_by": "owner@store.com",
        "order_id": "ORD-TEST-001",
        "items": [
            {
                "product_id": "PROD-001",
                "name": "Rice",
                "quantity": 2,
                "unit_price": Decimal("150.00"),
                "total": Decimal("300.00")
            },
            {
                "product_id": "PROD-002",
                "name": "Oil",
                "quantity": 1,
                "unit_price": Decimal("200.00"),
                "total": Decimal("200.00")
            }
        ],
        "notes": "Regular customer credit purchase",
        "idempotency_key": "idem-key-12345-67890"
    }


@pytest.fixture
def sample_customer_balance_data():
    """Sample customer balance data for testing."""
    return {
        "store_id": "STORE-TEST-001",
        "customer_phone": "+919876543210",
        "customer_name": "Ramesh Kumar",
        "outstanding_balance": Decimal("1500.00"),
        "credit_limit": Decimal("5000.00"),
        "version": 3,
        "last_transaction_id": "TXN-003",
        "last_transaction_at": datetime.utcnow().isoformat(),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": datetime.utcnow().isoformat(),
        "reminder_enabled": True,
        "reminder_frequency": "weekly",
        "preferred_language": "hi"
    }


@pytest.fixture
def sample_payment_reminder_data():
    """Sample payment reminder data for testing."""
    from datetime import timedelta
    return {
        "reminder_id": "REM-TEST-001",
        "store_id": "STORE-TEST-001",
        "customer_phone": "+919876543210",
        "outstanding_amount": Decimal("1500.00"),
        "scheduled_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "status": "scheduled",
        "reminder_type": "sms",
        "created_at": datetime.utcnow().isoformat(),
        "retry_count": 0
    }


@pytest.fixture
def sample_credit_sale_request():
    """Sample credit sale request for API testing."""
    return {
        "customer_phone": "+919876543210",
        "customer_name": "Ramesh Kumar",
        "amount": 500.00,
        "items": [
            {
                "product_id": "PROD-001",
                "name": "Rice",
                "quantity": 2,
                "unit_price": 150.00
            },
            {
                "product_id": "PROD-002",
                "name": "Oil",
                "quantity": 1,
                "unit_price": 200.00
            }
        ],
        "notes": "Credit purchase",
        "idempotency_key": "test-idem-key-123"
    }


@pytest.fixture
def sample_payment_request():
    """Sample payment recording request for API testing."""
    return {
        "customer_phone": "+919876543210",
        "amount": 500.00,
        "payment_method": "cash",
        "reference_id": "RCPT-001",
        "notes": "Cash payment received",
        "idempotency_key": "test-payment-idem-123"
    }


@pytest.fixture
def mock_sms_service():
    """Mock SMS service for Khata reminders."""
    mock = MagicMock()

    mock.send_otp = AsyncMock(return_value=MagicMock(
        success=True,
        message_id="MSG-001",
        error=None,
        processing_time_ms=100.0
    ))

    mock.send_transactional_sms = AsyncMock(return_value=MagicMock(
        success=True,
        message_id="MSG-002",
        error=None,
        processing_time_ms=150.0
    ))

    mock.check_balance = AsyncMock(return_value={
        "success": True,
        "balance": 1000.0,
        "provider": "Gupshup"
    })

    mock.get_status = MagicMock(return_value={
        "provider": "Gupshup",
        "configured": True,
        "sender_id": "VYAPAR",
        "dlt_configured": True,
        "environment": "test"
    })

    return mock


# =============================================================================
# Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Clean up after each test."""
    yield
    # Any cleanup code here
