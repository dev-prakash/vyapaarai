"""
Khata Database Manager for VyaparAI
Handles DynamoDB operations for Digital Credit Management (Khata) system

Tables:
- vyaparai-khata-transactions-{env}: Credit sales and payment records
- vyaparai-customer-balances-{env}: Real-time customer balance cache
- vyaparai-payment-reminders-{env}: SMS reminder scheduling
- vyaparai-idempotency-keys-{env}: Transaction deduplication

Key Design:
- Customer balances use composite key: STORE#{store_id} (PK) + CUST#{phone} (SK)
- Transactions use: TXN#{transaction_id} (PK) + STORE#{store_id}#CUST#{phone} (SK)
- GSI for querying by phone across all stores
"""

import asyncio
import base64
import json
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
import uuid

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.dynamodb.conditions import Key, Attr

from ..core.config import settings
from ..core.exceptions import (
    DatabaseError,
    CreditLimitExceededError,
    DuplicateTransactionError,
    TransactionRollbackError,
)

logger = logging.getLogger(__name__)


def decimal_to_float(obj: Any) -> Any:
    """Convert Decimal values to float recursively for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


def float_to_decimal(obj: Any) -> Any:
    """Convert float values to Decimal recursively for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(item) for item in obj]
    return obj


# =============================================================================
# Data Classes for Khata Operations
# =============================================================================

@dataclass
class KhataTransaction:
    """Transaction record for credit sales and payments"""
    transaction_id: str
    store_id: str
    customer_phone: str
    transaction_type: str  # 'credit_sale', 'payment', 'adjustment', 'reversal'
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    created_at: str
    created_by: str  # Store owner/staff ID
    # Optional fields
    order_id: Optional[str] = None
    items: Optional[List[Dict]] = None
    notes: Optional[str] = None
    reference_id: Optional[str] = None  # External reference (receipt, etc.)
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class CustomerBalance:
    """Real-time customer balance at a specific store"""
    store_id: str
    customer_phone: str
    customer_name: str  # Encrypted in production
    outstanding_balance: Decimal
    credit_limit: Decimal
    version: int  # For optimistic locking
    last_transaction_id: Optional[str] = None
    last_transaction_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Customer preferences
    reminder_enabled: bool = True
    reminder_frequency: str = "weekly"  # daily, weekly, monthly
    preferred_language: str = "hi"


@dataclass
class PaymentReminder:
    """Scheduled payment reminder for a customer"""
    reminder_id: str
    store_id: str
    customer_phone: str
    outstanding_amount: Decimal
    scheduled_at: str  # ISO timestamp
    status: str  # 'scheduled', 'sent', 'failed', 'cancelled'
    reminder_type: str  # 'sms', 'push', 'both'
    # Tracking
    created_at: str
    sent_at: Optional[str] = None
    failure_reason: Optional[str] = None
    retry_count: int = 0
    ttl: Optional[int] = None  # DynamoDB TTL


@dataclass
class IdempotencyRecord:
    """Record for transaction deduplication"""
    idempotency_key: str
    transaction_id: str
    result: Dict[str, Any]
    created_at: str
    ttl: int  # DynamoDB TTL (30 days)


@dataclass
class KhataResult:
    """Result from Khata database operations"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0
    next_cursor: Optional[str] = None  # For pagination


# =============================================================================
# Khata Database Manager
# =============================================================================

class KhataDatabase:
    """
    Khata Database Manager
    Handles DynamoDB operations for credit management system

    Features:
    - Cursor-based pagination with LastEvaluatedKey
    - Optimistic locking with version attribute
    - Idempotency key support for transaction deduplication
    - Multi-store customer support
    """

    def __init__(self):
        """Initialize the Khata database manager"""
        self.dynamodb = None
        self.dynamodb_client = None
        self._initialize_dynamodb()
        self._build_table_names()

    def _initialize_dynamodb(self):
        """Initialize DynamoDB client"""
        try:
            kwargs = {'region_name': settings.AWS_REGION}

            # Use endpoint if specified (for LocalStack/local development)
            if settings.DYNAMODB_ENDPOINT:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT

            self.dynamodb = boto3.resource('dynamodb', **kwargs)
            self.dynamodb_client = boto3.client('dynamodb', **kwargs)
            logger.info(f"Khata DynamoDB client initialized (region: {settings.AWS_REGION})")
        except NoCredentialsError:
            logger.error("AWS credentials not found for Khata database")
            self.dynamodb = None
            self.dynamodb_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Khata DynamoDB: {e}")
            self.dynamodb = None
            self.dynamodb_client = None

    def _build_table_names(self):
        """Build table names from configuration"""
        self.table_names = {
            'transactions': settings.DYNAMODB_KHATA_TRANSACTIONS_TABLE,
            'balances': settings.DYNAMODB_CUSTOMER_BALANCES_TABLE,
            'reminders': settings.DYNAMODB_PAYMENT_REMINDERS_TABLE,
            'idempotency': settings.DYNAMODB_IDEMPOTENCY_KEYS_TABLE,
        }
        logger.info(f"Khata table names configured: {self.table_names}")

    def _encode_cursor(self, last_evaluated_key: Optional[Dict]) -> Optional[str]:
        """Encode LastEvaluatedKey as base64 cursor for pagination"""
        if not last_evaluated_key:
            return None
        try:
            json_str = json.dumps(last_evaluated_key, default=str)
            return base64.b64encode(json_str.encode()).decode()
        except Exception as e:
            logger.warning(f"Failed to encode pagination cursor: {e}")
            return None

    def _decode_cursor(self, cursor: Optional[str]) -> Optional[Dict]:
        """Decode base64 cursor to LastEvaluatedKey for pagination"""
        if not cursor:
            return None
        try:
            json_str = base64.b64decode(cursor.encode()).decode()
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to decode pagination cursor: {e}")
            return None

    # =========================================================================
    # Idempotency Key Operations
    # =========================================================================

    async def check_idempotency_key(self, idempotency_key: str) -> Optional[Dict]:
        """
        Check if an idempotency key has been used

        Returns:
            Cached result if key exists, None otherwise
        """
        if not self.dynamodb:
            return None

        try:
            table = self.dynamodb.Table(self.table_names['idempotency'])

            response = await asyncio.to_thread(
                table.get_item,
                Key={'idempotency_key': idempotency_key}
            )

            item = response.get('Item')
            if item:
                logger.info(f"Idempotency key found: {idempotency_key}")
                return decimal_to_float(item.get('result', {}))
            return None

        except ClientError as e:
            logger.error(f"Error checking idempotency key: {e}")
            return None

    async def store_idempotency_key(
        self,
        idempotency_key: str,
        transaction_id: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Store idempotency key with result for future deduplication

        Args:
            idempotency_key: Unique key provided by client
            transaction_id: The transaction this key is associated with
            result: The result to return for duplicate requests

        Returns:
            True if stored successfully
        """
        if not self.dynamodb:
            return False

        try:
            table = self.dynamodb.Table(self.table_names['idempotency'])

            # TTL: 30 days from now
            ttl = int(time.time()) + (30 * 24 * 60 * 60)

            item = {
                'idempotency_key': idempotency_key,
                'transaction_id': transaction_id,
                'result': float_to_decimal(result),
                'created_at': datetime.utcnow().isoformat(),
                'ttl': ttl
            }

            await asyncio.to_thread(table.put_item, Item=item)
            logger.info(f"Stored idempotency key: {idempotency_key}")
            return True

        except ClientError as e:
            logger.error(f"Error storing idempotency key: {e}")
            return False

    # =========================================================================
    # Customer Balance Operations
    # =========================================================================

    async def get_customer_balance(
        self,
        store_id: str,
        customer_phone: str
    ) -> KhataResult:
        """
        Get customer balance at a specific store

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number

        Returns:
            KhataResult with CustomerBalance data
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['balances'])

            response = await asyncio.to_thread(
                table.get_item,
                Key={
                    'PK': f"STORE#{store_id}",
                    'SK': f"CUST#{customer_phone}"
                }
            )

            item = response.get('Item')
            if item:
                balance = CustomerBalance(
                    store_id=store_id,
                    customer_phone=customer_phone,
                    customer_name=item.get('customer_name', ''),
                    outstanding_balance=Decimal(str(item.get('outstanding_balance', 0))),
                    credit_limit=Decimal(str(item.get('credit_limit', 0))),
                    version=int(item.get('version', 1)),
                    last_transaction_id=item.get('last_transaction_id'),
                    last_transaction_at=item.get('last_transaction_at'),
                    created_at=item.get('created_at'),
                    updated_at=item.get('updated_at'),
                    reminder_enabled=item.get('reminder_enabled', True),
                    reminder_frequency=item.get('reminder_frequency', 'weekly'),
                    preferred_language=item.get('preferred_language', 'hi')
                )

                return KhataResult(
                    success=True,
                    data=balance,
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            else:
                return KhataResult(
                    success=False,
                    error="Customer not found at this store",
                    processing_time_ms=(time.time() - start_time) * 1000
                )

        except ClientError as e:
            logger.error(f"Error getting customer balance: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def create_customer_balance(
        self,
        store_id: str,
        customer_phone: str,
        customer_name: str,
        credit_limit: Decimal = Decimal("5000.00"),
        preferred_language: str = "hi"
    ) -> KhataResult:
        """
        Create a new customer balance record at a store

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            customer_name: Customer name (will be encrypted in production)
            credit_limit: Initial credit limit
            preferred_language: Preferred language for notifications

        Returns:
            KhataResult with created CustomerBalance
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['balances'])
            now = datetime.utcnow().isoformat()

            item = {
                'PK': f"STORE#{store_id}",
                'SK': f"CUST#{customer_phone}",
                'store_id': store_id,
                'customer_phone': customer_phone,
                'customer_name': customer_name,
                'outstanding_balance': float_to_decimal(0),
                'credit_limit': float_to_decimal(credit_limit),
                'version': 1,
                'created_at': now,
                'updated_at': now,
                'reminder_enabled': True,
                'reminder_frequency': 'weekly',
                'preferred_language': preferred_language,
                # GSI for querying by phone across stores
                'GSI1PK': f"PHONE#{customer_phone}",
                'GSI1SK': f"STORE#{store_id}"
            }

            # Conditional put to prevent overwriting existing records
            await asyncio.to_thread(
                table.put_item,
                Item=item,
                ConditionExpression='attribute_not_exists(PK)'
            )

            balance = CustomerBalance(
                store_id=store_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                outstanding_balance=Decimal("0"),
                credit_limit=credit_limit,
                version=1,
                created_at=now,
                updated_at=now,
                preferred_language=preferred_language
            )

            return KhataResult(
                success=True,
                data=balance,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return KhataResult(
                    success=False,
                    error="Customer already exists at this store",
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            logger.error(f"Error creating customer balance: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def update_customer_balance(
        self,
        store_id: str,
        customer_phone: str,
        amount_change: Decimal,
        expected_version: int,
        transaction_id: str,
        max_retries: int = 3
    ) -> KhataResult:
        """
        Update customer balance with optimistic locking

        Uses conditional update with version check and exponential backoff retry.

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            amount_change: Amount to add (positive) or subtract (negative)
            expected_version: Expected version for optimistic locking
            transaction_id: Transaction ID to record
            max_retries: Maximum retry attempts on version conflict

        Returns:
            KhataResult with updated balance
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        current_version = expected_version

        for attempt in range(max_retries):
            try:
                table = self.dynamodb.Table(self.table_names['balances'])
                now = datetime.utcnow().isoformat()

                response = await asyncio.to_thread(
                    table.update_item,
                    Key={
                        'PK': f"STORE#{store_id}",
                        'SK': f"CUST#{customer_phone}"
                    },
                    UpdateExpression='''
                        SET outstanding_balance = outstanding_balance + :amount,
                            version = version + :one,
                            last_transaction_id = :txn_id,
                            last_transaction_at = :now,
                            updated_at = :now
                    ''',
                    ConditionExpression='version = :expected_version',
                    ExpressionAttributeValues={
                        ':amount': float_to_decimal(amount_change),
                        ':one': 1,
                        ':expected_version': current_version,
                        ':txn_id': transaction_id,
                        ':now': now
                    },
                    ReturnValues='ALL_NEW'
                )

                updated = response['Attributes']
                balance = CustomerBalance(
                    store_id=store_id,
                    customer_phone=customer_phone,
                    customer_name=updated.get('customer_name', ''),
                    outstanding_balance=Decimal(str(updated.get('outstanding_balance', 0))),
                    credit_limit=Decimal(str(updated.get('credit_limit', 0))),
                    version=int(updated.get('version', 1)),
                    last_transaction_id=updated.get('last_transaction_id'),
                    last_transaction_at=updated.get('last_transaction_at'),
                    updated_at=updated.get('updated_at')
                )

                return KhataResult(
                    success=True,
                    data=balance,
                    processing_time_ms=(time.time() - start_time) * 1000
                )

            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        wait_time = (2 ** attempt) * 0.1
                        logger.warning(
                            f"Version conflict on balance update, retrying in {wait_time}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)

                        # Refresh version
                        balance_result = await self.get_customer_balance(store_id, customer_phone)
                        if balance_result.success:
                            current_version = balance_result.data.version
                        continue
                    else:
                        logger.error(f"Max retries exceeded for balance update")
                        return KhataResult(
                            success=False,
                            error="Concurrent modification - max retries exceeded",
                            processing_time_ms=(time.time() - start_time) * 1000
                        )

                logger.error(f"Error updating customer balance: {e}")
                return KhataResult(
                    success=False,
                    error=str(e),
                    processing_time_ms=(time.time() - start_time) * 1000
                )

        return KhataResult(
            success=False,
            error="Unexpected error in balance update",
            processing_time_ms=(time.time() - start_time) * 1000
        )

    async def get_customers_with_balance(
        self,
        store_id: str,
        min_balance: Optional[Decimal] = None,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> KhataResult:
        """
        Get customers with outstanding balance at a store

        Args:
            store_id: Store identifier
            min_balance: Minimum outstanding balance filter
            cursor: Pagination cursor
            limit: Maximum records to return

        Returns:
            KhataResult with list of CustomerBalance and next cursor
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['balances'])

            query_params = {
                'KeyConditionExpression': Key('PK').eq(f"STORE#{store_id}"),
                'Limit': limit
            }

            if min_balance is not None:
                query_params['FilterExpression'] = Attr('outstanding_balance').gte(
                    float_to_decimal(min_balance)
                )

            if cursor:
                exclusive_start_key = self._decode_cursor(cursor)
                if exclusive_start_key:
                    query_params['ExclusiveStartKey'] = exclusive_start_key

            response = await asyncio.to_thread(table.query, **query_params)

            customers = []
            for item in response.get('Items', []):
                balance = CustomerBalance(
                    store_id=store_id,
                    customer_phone=item.get('customer_phone', ''),
                    customer_name=item.get('customer_name', ''),
                    outstanding_balance=Decimal(str(item.get('outstanding_balance', 0))),
                    credit_limit=Decimal(str(item.get('credit_limit', 0))),
                    version=int(item.get('version', 1)),
                    last_transaction_id=item.get('last_transaction_id'),
                    last_transaction_at=item.get('last_transaction_at')
                )
                customers.append(balance)

            next_cursor = self._encode_cursor(response.get('LastEvaluatedKey'))

            return KhataResult(
                success=True,
                data=customers,
                next_cursor=next_cursor,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error getting customers with balance: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def get_customer_stores(
        self,
        customer_phone: str,
        cursor: Optional[str] = None,
        limit: int = 20
    ) -> KhataResult:
        """
        Get all stores where a customer has credit accounts

        Uses GSI1 (phone-index) to query across stores.

        Args:
            customer_phone: Customer phone number
            cursor: Pagination cursor
            limit: Maximum records to return

        Returns:
            KhataResult with list of store balances
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['balances'])

            query_params = {
                'IndexName': 'phone-index',
                'KeyConditionExpression': Key('GSI1PK').eq(f"PHONE#{customer_phone}"),
                'Limit': limit
            }

            if cursor:
                exclusive_start_key = self._decode_cursor(cursor)
                if exclusive_start_key:
                    query_params['ExclusiveStartKey'] = exclusive_start_key

            response = await asyncio.to_thread(table.query, **query_params)

            balances = []
            for item in response.get('Items', []):
                balance = CustomerBalance(
                    store_id=item.get('store_id', ''),
                    customer_phone=customer_phone,
                    customer_name=item.get('customer_name', ''),
                    outstanding_balance=Decimal(str(item.get('outstanding_balance', 0))),
                    credit_limit=Decimal(str(item.get('credit_limit', 0))),
                    version=int(item.get('version', 1))
                )
                balances.append(balance)

            next_cursor = self._encode_cursor(response.get('LastEvaluatedKey'))

            return KhataResult(
                success=True,
                data=balances,
                next_cursor=next_cursor,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error getting customer stores: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    # =========================================================================
    # Transaction Operations
    # =========================================================================

    async def create_transaction(
        self,
        transaction: KhataTransaction
    ) -> KhataResult:
        """
        Create a new Khata transaction record

        Args:
            transaction: Transaction data to store

        Returns:
            KhataResult with created transaction
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['transactions'])

            item = {
                'PK': f"TXN#{transaction.transaction_id}",
                'SK': f"STORE#{transaction.store_id}#CUST#{transaction.customer_phone}",
                'transaction_id': transaction.transaction_id,
                'store_id': transaction.store_id,
                'customer_phone': transaction.customer_phone,
                'transaction_type': transaction.transaction_type,
                'amount': float_to_decimal(transaction.amount),
                'balance_before': float_to_decimal(transaction.balance_before),
                'balance_after': float_to_decimal(transaction.balance_after),
                'created_at': transaction.created_at,
                'created_by': transaction.created_by,
                # GSI for querying by store and customer
                'GSI1PK': f"STORE#{transaction.store_id}",
                'GSI1SK': f"CUST#{transaction.customer_phone}#{transaction.created_at}",
                # GSI for querying by date
                'GSI2PK': f"STORE#{transaction.store_id}",
                'GSI2SK': transaction.created_at
            }

            # Add optional fields
            if transaction.order_id:
                item['order_id'] = transaction.order_id
            if transaction.items:
                item['items'] = float_to_decimal(transaction.items)
            if transaction.notes:
                item['notes'] = transaction.notes
            if transaction.reference_id:
                item['reference_id'] = transaction.reference_id
            if transaction.idempotency_key:
                item['idempotency_key'] = transaction.idempotency_key
            if transaction.metadata:
                item['metadata'] = float_to_decimal(transaction.metadata)

            await asyncio.to_thread(table.put_item, Item=item)

            return KhataResult(
                success=True,
                data=transaction,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error creating transaction: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def get_transaction(self, transaction_id: str) -> KhataResult:
        """
        Get a transaction by ID

        Args:
            transaction_id: Transaction identifier

        Returns:
            KhataResult with transaction data
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['transactions'])

            # Query using PK only (SK is composite, need to scan)
            response = await asyncio.to_thread(
                table.query,
                KeyConditionExpression=Key('PK').eq(f"TXN#{transaction_id}")
            )

            items = response.get('Items', [])
            if items:
                item = items[0]
                transaction = KhataTransaction(
                    transaction_id=item.get('transaction_id'),
                    store_id=item.get('store_id'),
                    customer_phone=item.get('customer_phone'),
                    transaction_type=item.get('transaction_type'),
                    amount=Decimal(str(item.get('amount', 0))),
                    balance_before=Decimal(str(item.get('balance_before', 0))),
                    balance_after=Decimal(str(item.get('balance_after', 0))),
                    created_at=item.get('created_at'),
                    created_by=item.get('created_by'),
                    order_id=item.get('order_id'),
                    items=item.get('items'),
                    notes=item.get('notes'),
                    reference_id=item.get('reference_id'),
                    idempotency_key=item.get('idempotency_key'),
                    metadata=item.get('metadata')
                )

                return KhataResult(
                    success=True,
                    data=transaction,
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            else:
                return KhataResult(
                    success=False,
                    error="Transaction not found",
                    processing_time_ms=(time.time() - start_time) * 1000
                )

        except ClientError as e:
            logger.error(f"Error getting transaction: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def get_customer_transactions(
        self,
        store_id: str,
        customer_phone: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> KhataResult:
        """
        Get transactions for a customer at a store (ledger view)

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            cursor: Pagination cursor
            limit: Maximum records to return

        Returns:
            KhataResult with list of transactions and next cursor
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['transactions'])

            # Query using GSI1 (store-customer index)
            key_condition = Key('GSI1PK').eq(f"STORE#{store_id}")

            # Add sort key condition for customer and date range
            sk_condition = Key('GSI1SK').begins_with(f"CUST#{customer_phone}#")

            if start_date and end_date:
                sk_condition = Key('GSI1SK').between(
                    f"CUST#{customer_phone}#{start_date}",
                    f"CUST#{customer_phone}#{end_date}"
                )

            query_params = {
                'IndexName': 'store-customer-index',
                'KeyConditionExpression': key_condition & sk_condition,
                'ScanIndexForward': False,  # Most recent first
                'Limit': limit
            }

            if cursor:
                exclusive_start_key = self._decode_cursor(cursor)
                if exclusive_start_key:
                    query_params['ExclusiveStartKey'] = exclusive_start_key

            response = await asyncio.to_thread(table.query, **query_params)

            transactions = []
            for item in response.get('Items', []):
                txn = KhataTransaction(
                    transaction_id=item.get('transaction_id'),
                    store_id=item.get('store_id'),
                    customer_phone=item.get('customer_phone'),
                    transaction_type=item.get('transaction_type'),
                    amount=Decimal(str(item.get('amount', 0))),
                    balance_before=Decimal(str(item.get('balance_before', 0))),
                    balance_after=Decimal(str(item.get('balance_after', 0))),
                    created_at=item.get('created_at'),
                    created_by=item.get('created_by'),
                    order_id=item.get('order_id'),
                    items=item.get('items'),
                    notes=item.get('notes'),
                    reference_id=item.get('reference_id')
                )
                transactions.append(txn)

            next_cursor = self._encode_cursor(response.get('LastEvaluatedKey'))

            return KhataResult(
                success=True,
                data=transactions,
                next_cursor=next_cursor,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error getting customer transactions: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def get_store_transactions(
        self,
        store_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        transaction_type: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100
    ) -> KhataResult:
        """
        Get all transactions for a store within a date range

        Args:
            store_id: Store identifier
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            transaction_type: Optional filter by type
            cursor: Pagination cursor
            limit: Maximum records to return

        Returns:
            KhataResult with transactions and next cursor
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['transactions'])

            # Query using GSI2 (store-date index)
            key_condition = Key('GSI2PK').eq(f"STORE#{store_id}")

            if start_date and end_date:
                key_condition = key_condition & Key('GSI2SK').between(start_date, end_date)

            query_params = {
                'IndexName': 'store-date-index',
                'KeyConditionExpression': key_condition,
                'ScanIndexForward': False,  # Most recent first
                'Limit': limit
            }

            if transaction_type:
                query_params['FilterExpression'] = Attr('transaction_type').eq(transaction_type)

            if cursor:
                exclusive_start_key = self._decode_cursor(cursor)
                if exclusive_start_key:
                    query_params['ExclusiveStartKey'] = exclusive_start_key

            response = await asyncio.to_thread(table.query, **query_params)

            transactions = []
            for item in response.get('Items', []):
                txn = KhataTransaction(
                    transaction_id=item.get('transaction_id'),
                    store_id=item.get('store_id'),
                    customer_phone=item.get('customer_phone'),
                    transaction_type=item.get('transaction_type'),
                    amount=Decimal(str(item.get('amount', 0))),
                    balance_before=Decimal(str(item.get('balance_before', 0))),
                    balance_after=Decimal(str(item.get('balance_after', 0))),
                    created_at=item.get('created_at'),
                    created_by=item.get('created_by')
                )
                transactions.append(txn)

            next_cursor = self._encode_cursor(response.get('LastEvaluatedKey'))

            return KhataResult(
                success=True,
                data=transactions,
                next_cursor=next_cursor,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error getting store transactions: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    # =========================================================================
    # Payment Reminder Operations
    # =========================================================================

    async def create_reminder(self, reminder: PaymentReminder) -> KhataResult:
        """
        Create a payment reminder

        Args:
            reminder: Reminder data to store

        Returns:
            KhataResult with created reminder
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['reminders'])

            item = {
                'PK': f"STORE#{reminder.store_id}",
                'SK': f"REM#{reminder.reminder_id}",
                'reminder_id': reminder.reminder_id,
                'store_id': reminder.store_id,
                'customer_phone': reminder.customer_phone,
                'outstanding_amount': float_to_decimal(reminder.outstanding_amount),
                'scheduled_at': reminder.scheduled_at,
                'status': reminder.status,
                'reminder_type': reminder.reminder_type,
                'created_at': reminder.created_at,
                'retry_count': reminder.retry_count,
                # GSI for querying pending reminders by scheduled time
                'GSI1PK': f"STATUS#{reminder.status}",
                'GSI1SK': reminder.scheduled_at
            }

            if reminder.sent_at:
                item['sent_at'] = reminder.sent_at
            if reminder.failure_reason:
                item['failure_reason'] = reminder.failure_reason
            if reminder.ttl:
                item['ttl'] = reminder.ttl

            await asyncio.to_thread(table.put_item, Item=item)

            return KhataResult(
                success=True,
                data=reminder,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error creating reminder: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def get_pending_reminders(
        self,
        before_time: str,
        cursor: Optional[str] = None,
        limit: int = 100
    ) -> KhataResult:
        """
        Get pending reminders scheduled before a given time

        Used by reminder scheduler to process due reminders.

        Args:
            before_time: Get reminders scheduled before this time (ISO format)
            cursor: Pagination cursor
            limit: Maximum records to return

        Returns:
            KhataResult with list of reminders and next cursor
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['reminders'])

            query_params = {
                'IndexName': 'status-scheduled-index',
                'KeyConditionExpression': (
                    Key('GSI1PK').eq('STATUS#scheduled') &
                    Key('GSI1SK').lt(before_time)
                ),
                'Limit': limit
            }

            if cursor:
                exclusive_start_key = self._decode_cursor(cursor)
                if exclusive_start_key:
                    query_params['ExclusiveStartKey'] = exclusive_start_key

            response = await asyncio.to_thread(table.query, **query_params)

            reminders = []
            for item in response.get('Items', []):
                reminder = PaymentReminder(
                    reminder_id=item.get('reminder_id'),
                    store_id=item.get('store_id'),
                    customer_phone=item.get('customer_phone'),
                    outstanding_amount=Decimal(str(item.get('outstanding_amount', 0))),
                    scheduled_at=item.get('scheduled_at'),
                    status=item.get('status'),
                    reminder_type=item.get('reminder_type'),
                    created_at=item.get('created_at'),
                    retry_count=int(item.get('retry_count', 0))
                )
                reminders.append(reminder)

            next_cursor = self._encode_cursor(response.get('LastEvaluatedKey'))

            return KhataResult(
                success=True,
                data=reminders,
                next_cursor=next_cursor,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error getting pending reminders: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    async def update_reminder_status(
        self,
        store_id: str,
        reminder_id: str,
        status: str,
        sent_at: Optional[str] = None,
        failure_reason: Optional[str] = None
    ) -> KhataResult:
        """
        Update reminder status after processing

        Args:
            store_id: Store identifier
            reminder_id: Reminder identifier
            status: New status ('sent', 'failed', 'cancelled')
            sent_at: Time when sent (for successful sends)
            failure_reason: Reason for failure (if failed)

        Returns:
            KhataResult with updated reminder
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['reminders'])

            update_expression = 'SET #status = :status, GSI1PK = :gsi1pk'
            expression_values = {
                ':status': status,
                ':gsi1pk': f"STATUS#{status}"
            }

            if sent_at:
                update_expression += ', sent_at = :sent_at'
                expression_values[':sent_at'] = sent_at

            if failure_reason:
                update_expression += ', failure_reason = :failure_reason, retry_count = retry_count + :one'
                expression_values[':failure_reason'] = failure_reason
                expression_values[':one'] = 1

            response = await asyncio.to_thread(
                table.update_item,
                Key={
                    'PK': f"STORE#{store_id}",
                    'SK': f"REM#{reminder_id}"
                },
                UpdateExpression=update_expression,
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues=expression_values,
                ReturnValues='ALL_NEW'
            )

            return KhataResult(
                success=True,
                data=response.get('Attributes'),
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error updating reminder status: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )

    # =========================================================================
    # Aggregate/Report Operations
    # =========================================================================

    async def get_store_outstanding_summary(self, store_id: str) -> KhataResult:
        """
        Get summary of outstanding balances for a store

        Returns aggregate stats: total outstanding, customer count, etc.

        Args:
            store_id: Store identifier

        Returns:
            KhataResult with summary statistics
        """
        start_time = time.time()

        if not self.dynamodb:
            return KhataResult(
                success=False,
                error="DynamoDB not initialized",
                processing_time_ms=(time.time() - start_time) * 1000
            )

        try:
            table = self.dynamodb.Table(self.table_names['balances'])

            # Query all customers for the store
            total_outstanding = Decimal("0")
            total_credit_limit = Decimal("0")
            customer_count = 0
            customers_with_balance = 0

            last_key = None
            while True:
                query_params = {
                    'KeyConditionExpression': Key('PK').eq(f"STORE#{store_id}"),
                    'ProjectionExpression': 'outstanding_balance, credit_limit'
                }

                if last_key:
                    query_params['ExclusiveStartKey'] = last_key

                response = await asyncio.to_thread(table.query, **query_params)

                for item in response.get('Items', []):
                    customer_count += 1
                    balance = Decimal(str(item.get('outstanding_balance', 0)))
                    total_outstanding += balance
                    total_credit_limit += Decimal(str(item.get('credit_limit', 0)))
                    if balance > 0:
                        customers_with_balance += 1

                last_key = response.get('LastEvaluatedKey')
                if not last_key:
                    break

            summary = {
                'store_id': store_id,
                'total_outstanding': float(total_outstanding),
                'total_credit_limit': float(total_credit_limit),
                'total_customers': customer_count,
                'customers_with_balance': customers_with_balance,
                'utilization_rate': float(total_outstanding / total_credit_limit * 100) if total_credit_limit > 0 else 0,
                'generated_at': datetime.utcnow().isoformat()
            }

            return KhataResult(
                success=True,
                data=summary,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        except ClientError as e:
            logger.error(f"Error getting store outstanding summary: {e}")
            return KhataResult(
                success=False,
                error=str(e),
                processing_time_ms=(time.time() - start_time) * 1000
            )


# =============================================================================
# Global Instance
# =============================================================================

khata_db = KhataDatabase()
