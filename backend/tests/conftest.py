"""
VyapaarAI Test Configuration
Test fixtures based on actual application schema
"""
import pytest
import boto3
from moto import mock_aws
from typing import Generator, Dict, Any, List
from decimal import Decimal
from datetime import datetime, timedelta
import os
import uuid

# Force test environment
os.environ["VYAPAARAI_ENV"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "ap-south-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"


class DynamoDBSchemas:
    """
    DynamoDB table schemas extracted from actual application code.
    MUST match production table definitions exactly.
    """
    
    ORDERS_TABLE = {
        "TableName": "vyaparai-orders-test",
        "KeySchema": [
            {"AttributeName": "store_id", "KeyType": "HASH"},
            {"AttributeName": "id", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "store_id", "AttributeType": "S"},
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "customer_phone", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "order-id-index",
                "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "store_id-created_at-index",
                "KeySchema": [
                    {"AttributeName": "store_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "customer-phone-index",
                "KeySchema": [
                    {"AttributeName": "customer_phone", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }
    
    STORES_TABLE = {
        "TableName": "vyaparai-stores-test",
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }
    
    PRODUCTS_TABLE = {
        "TableName": "vyaparai-products-test",
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }
    
    SESSIONS_TABLE = {
        "TableName": "vyaparai-sessions-test",
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }
    
    KHATA_TRANSACTIONS_TABLE = {
        "TableName": "vyaparai-khata-transactions-test",
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }
    
    CUSTOMER_BALANCES_TABLE = {
        "TableName": "vyaparai-customer-balances-test",
        "KeySchema": [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }
    
    @classmethod
    def get_all_schemas(cls) -> List[Dict[str, Any]]:
        """Return all table schemas"""
        return [
            cls.ORDERS_TABLE,
            cls.STORES_TABLE,
            cls.PRODUCTS_TABLE,
            cls.SESSIONS_TABLE,
            cls.KHATA_TRANSACTIONS_TABLE,
            cls.CUSTOMER_BALANCES_TABLE,
        ]


def create_table(client, schema: Dict[str, Any]) -> None:
    """Create a DynamoDB table from schema"""
    create_params = {
        "TableName": schema["TableName"],
        "KeySchema": schema["KeySchema"],
        "AttributeDefinitions": schema["AttributeDefinitions"],
        "BillingMode": schema.get("BillingMode", "PAY_PER_REQUEST"),
    }
    if "GlobalSecondaryIndexes" in schema:
        create_params["GlobalSecondaryIndexes"] = schema["GlobalSecondaryIndexes"]
    client.create_table(**create_params)


@pytest.fixture(scope="function")
def dynamodb_mock() -> Generator:
    """Mock DynamoDB with all VyapaarAI tables"""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ap-south-1")
        
        for schema in DynamoDBSchemas.get_all_schemas():
            try:
                create_table(client, schema)
            except Exception:
                pass
        
        yield client


@pytest.fixture(scope="function")
def dynamodb_resource(dynamodb_mock) -> Generator:
    """DynamoDB resource for higher-level operations"""
    resource = boto3.resource("dynamodb", region_name="ap-south-1")
    yield resource


# ============== SAMPLE DATA FIXTURES ==============

@pytest.fixture
def sample_store() -> Dict[str, Any]:
    """Sample store data based on actual code analysis"""
    return {
        "pk": "STR-TEST001",
        "id": "STR-TEST001",
        "store_id": "STR-TEST001",
        "name": "Test Kirana Store",
        "owner_id": "OWNER-TEST001",
        "owner_name": "Test Owner",
        "address": {
            "street": "123 Test Road",
            "city": "Delhi",
            "state": "Delhi",
            "pincode": "110001",
            "landmark": "Near Test Metro"
        },
        "latitude": Decimal("28.6139"),
        "longitude": Decimal("77.2090"),
        "contact_info": {
            "phone": "+919876543210",
            "whatsapp": "+919876543210",
            "email": "test@vyaparai.com"
        },
        "settings": {
            "accepts_online_payment": True,
            "delivery_radius_km": 5,
            "min_order_amount": 100
        },
        "status": "active",
        "verified": True,
        "gsi1pk": "OWNER#OWNER-TEST001",
        "gsi1sk": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_product() -> Dict[str, Any]:
    """Sample product data based on actual code analysis"""
    return {
        "pk": "STORE#STR-TEST001",
        "sk": "PRODUCT#PROD-TEST001",
        "product_id": "PROD-TEST001",
        "store_id": "STR-TEST001",
        "name": "Tata Salt",
        "local_name": "टाटा नमक",
        "category": "grocery",
        "subcategory": "spices",
        "brand": "Tata",
        "unit": "kg",
        "price": Decimal("25.00"),
        "mrp": Decimal("28.00"),
        "stock_quantity": 50,
        "low_stock_threshold": 10,
        "keywords": ["salt", "namak", "iodized"],
        "gsi1pk": "CATEGORY#grocery",
        "gsi1sk": "BRAND#Tata#PROD-TEST001",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_order() -> Dict[str, Any]:
    """Sample order data based on actual code analysis"""
    order_id = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-TEST001"
    return {
        "store_id": "STR-TEST001",
        "id": order_id,
        "customer_id": "CUST-TEST001",
        "customer_phone": "+919876543210",
        "customer_name": "Test Customer",
        "items": [
            {
                "product_id": "PROD-TEST001",
                "name": "Tata Salt 1kg",
                "quantity": 2,
                "price": Decimal("25.00"),
                "unit": "kg"
            }
        ],
        "total_amount": Decimal("50.00"),
        "status": "pending",
        "channel": "whatsapp",
        "language": "hi",
        "intent": "order_create",
        "confidence": Decimal("0.95"),
        "entities": [
            {"type": "product", "value": "salt", "confidence": 0.92}
        ],
        "payment_method": "cod",
        "delivery_address": "123 Test Street, Delhi",
        "delivery_notes": "Call before delivery",
        "order_number": order_id,
        "tracking_id": f"TRK-{uuid.uuid4().hex[:8].upper()}",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_session() -> Dict[str, Any]:
    """Sample session data based on actual code analysis"""
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    return {
        "pk": f"SESSION#{session_id}",
        "session_id": session_id,
        "customer_phone": "+919876543210",
        "store_id": "STR-TEST001",
        "context": {
            "current_order": None,
            "conversation_history": [],
            "selected_products": [],
            "pending_confirmation": False
        },
        "last_activity": datetime.utcnow().isoformat(),
        "gsi1pk": "CUSTOMER#+919876543210",
        "gsi1sk": datetime.utcnow().isoformat(),
        "ttl": int((datetime.utcnow() + timedelta(minutes=30)).timestamp())
    }


@pytest.fixture
def sample_khata_transaction() -> Dict[str, Any]:
    """Sample khata transaction data based on actual code analysis"""
    txn_id = f"txn-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    return {
        "pk": f"TXN#{txn_id}",
        "sk": "STORE#STR-TEST001#CUST#+919876543210",
        "transaction_id": txn_id,
        "store_id": "STR-TEST001",
        "customer_phone": "+919876543210",
        "transaction_type": "credit_sale",
        "amount": Decimal("500.00"),
        "balance_before": Decimal("1000.00"),
        "balance_after": Decimal("1500.00"),
        "order_id": "ORD-TEST001",
        "items": [
            {"name": "Tata Salt 1kg", "quantity": 2, "price": 25.00}
        ],
        "notes": "Test transaction",
        "created_by": "OWNER-TEST001",
        "gsi1pk": "PHONE#+919876543210",
        "gsi1sk": f"STORE#STR-TEST001#{datetime.utcnow().isoformat()}",
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_customer_balance() -> Dict[str, Any]:
    """Sample customer balance data based on actual code analysis"""
    return {
        "pk": "STORE#STR-TEST001",
        "sk": "CUST#+919876543210",
        "store_id": "STR-TEST001",
        "customer_phone": "+919876543210",
        "customer_name": "Test Customer",
        "outstanding_balance": Decimal("1500.00"),
        "credit_limit": Decimal("5000.00"),
        "version": 1,
        "last_transaction_id": "txn-test001",
        "last_transaction_at": datetime.utcnow().isoformat(),
        "reminder_enabled": True,
        "reminder_frequency": "weekly",
        "preferred_language": "hi",
        "gsi1pk": "PHONE#+919876543210",
        "gsi1sk": "STORE#STR-TEST001",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


# ============== HELPER FIXTURES ==============

@pytest.fixture
def orders_table(dynamodb_resource):
    """Get orders table"""
    return dynamodb_resource.Table("vyaparai-orders-test")


@pytest.fixture
def stores_table(dynamodb_resource):
    """Get stores table"""
    return dynamodb_resource.Table("vyaparai-stores-test")


@pytest.fixture
def products_table(dynamodb_resource):
    """Get products table"""
    return dynamodb_resource.Table("vyaparai-products-test")


@pytest.fixture
def seeded_store(stores_table, sample_store):
    """Store with pre-seeded data"""
    stores_table.put_item(Item=sample_store)
    return sample_store


@pytest.fixture
def seeded_product(products_table, sample_product):
    """Product with pre-seeded data"""
    products_table.put_item(Item=sample_product)
    return sample_product


@pytest.fixture
def seeded_order(orders_table, sample_order):
    """Order with pre-seeded data"""
    orders_table.put_item(Item=sample_order)
    return sample_order


# ============== GST FIXTURES ==============

@pytest.fixture
def sample_gst_product() -> Dict[str, Any]:
    """Sample product with GST fields"""
    return {
        "store_id": "STR-TEST001",
        "product_id": "PROD-GST001",
        "product_name": "Tata Tea Gold 500g",
        "brand": "Tata",
        "category": "Beverages",
        "selling_price": Decimal("250.00"),
        "cost_price": Decimal("200.00"),
        "mrp": Decimal("275.00"),
        "hsn_code": "0902",
        "gst_rate": Decimal("5"),
        "cess_rate": Decimal("0"),
        "is_gst_exempt": False,
        "gst_category": "TEA",
        "tax_rate": Decimal("5"),
        "current_stock": 100,
        "min_stock_level": 10,
        "max_stock_level": 500,
        "unit": "pack",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_gst_products() -> List[Dict[str, Any]]:
    """Sample products at different GST rate slabs for testing"""
    now = datetime.utcnow().isoformat()
    return [
        # 0% - Essentials (Fresh Rice)
        {
            "store_id": "STR-TEST001",
            "product_id": "PROD-GST-0",
            "product_name": "Fresh Rice 1kg",
            "brand": "Local",
            "category": "Grains",
            "selling_price": Decimal("50.00"),
            "hsn_code": "1006",
            "gst_rate": Decimal("0"),
            "cess_rate": Decimal("0"),
            "is_gst_exempt": False,
            "gst_category": "GRAINS",
            "current_stock": 200,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        # 5% - Basic packaged (Tata Salt)
        {
            "store_id": "STR-TEST001",
            "product_id": "PROD-GST-5",
            "product_name": "Tata Salt 1kg",
            "brand": "Tata",
            "category": "Essentials",
            "selling_price": Decimal("25.00"),
            "hsn_code": "2501",
            "gst_rate": Decimal("5"),
            "cess_rate": Decimal("0"),
            "is_gst_exempt": False,
            "gst_category": "SALT",
            "current_stock": 150,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        # 12% - Processed (Amul Butter)
        {
            "store_id": "STR-TEST001",
            "product_id": "PROD-GST-12",
            "product_name": "Amul Butter 500g",
            "brand": "Amul",
            "category": "Dairy",
            "selling_price": Decimal("275.00"),
            "hsn_code": "0405",
            "gst_rate": Decimal("12"),
            "cess_rate": Decimal("0"),
            "is_gst_exempt": False,
            "gst_category": "BUTTER",
            "current_stock": 50,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        # 18% - FMCG (Maggi Noodles)
        {
            "store_id": "STR-TEST001",
            "product_id": "PROD-GST-18",
            "product_name": "Maggi Noodles 70g",
            "brand": "Nestle",
            "category": "Instant Foods",
            "selling_price": Decimal("14.00"),
            "hsn_code": "1902",
            "gst_rate": Decimal("18"),
            "cess_rate": Decimal("0"),
            "is_gst_exempt": False,
            "gst_category": "NOODLES",
            "current_stock": 300,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        },
        # 28% with Cess - Luxury (Coca Cola)
        {
            "store_id": "STR-TEST001",
            "product_id": "PROD-GST-28",
            "product_name": "Coca Cola 2L",
            "brand": "Coca Cola",
            "category": "Beverages",
            "selling_price": Decimal("95.00"),
            "hsn_code": "2202",
            "gst_rate": Decimal("28"),
            "cess_rate": Decimal("12"),
            "is_gst_exempt": False,
            "gst_category": "AERATED",
            "current_stock": 40,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
    ]


@pytest.fixture
def gst_service_mock():
    """Mock GST service for unit testing"""
    from unittest.mock import MagicMock, AsyncMock
    from app.services.gst_service import GSTService

    service = MagicMock(spec=GSTService)
    service.use_mock = True

    # Setup async mock methods
    service.get_gst_rate_for_product = AsyncMock()
    service.calculate_item_gst = AsyncMock()
    service.calculate_order_gst = AsyncMock()

    return service
