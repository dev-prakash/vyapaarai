"""
Khata Transaction Service - Saga Pattern Implementation

Provides transactional safety for credit management operations using
the Saga pattern with compensating transactions.

Operations supported:
1. Credit Sale - Record a sale on credit with balance update
2. Payment - Record customer payment with balance reduction
3. Adjustment - Administrative balance adjustments
4. Reversal - Reverse a previous transaction

Each operation follows the Saga pattern:
1. Check idempotency key (prevent duplicates)
2. Validate operation (credit limits, etc.)
3. Update balance with optimistic locking
4. Create transaction record
5. Store idempotency result
6. On failure: Execute compensating transaction

This prevents:
- Duplicate transactions from network retries
- Balance inconsistencies from partial failures
- Credit limit violations
- Lost transactions
"""

import logging
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime, timedelta
import asyncio

from ..database.khata_db import (
    khata_db,
    KhataDatabase,
    KhataTransaction,
    CustomerBalance,
    PaymentReminder,
    KhataResult,
)
from ..core.exceptions import (
    CreditLimitExceededError,
    DuplicateTransactionError,
    InvalidPaymentAmountError,
    TransactionRollbackError,
    CustomerNotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class CreditSaleItem:
    """Item in a credit sale"""
    product_id: str
    name: str
    quantity: int
    unit_price: Decimal
    unit: str = "pieces"

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class TransactionResult:
    """Result of a Khata transaction"""
    success: bool
    transaction_id: Optional[str] = None
    new_balance: Optional[Decimal] = None
    message: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    processing_time_ms: float = 0.0


class KhataTransactionService:
    """
    Transactional Khata Service using Saga Pattern

    Ensures atomic credit operations with proper:
    - Idempotency handling
    - Credit limit validation
    - Optimistic locking for concurrent updates
    - Compensating transactions on failure
    """

    def __init__(self, db: KhataDatabase = None):
        """
        Initialize with database dependency

        Args:
            db: KhataDatabase instance (defaults to global instance)
        """
        self.db = db or khata_db

    async def record_credit_sale(
        self,
        store_id: str,
        customer_phone: str,
        amount: Decimal,
        created_by: str,
        customer_name: Optional[str] = None,
        items: Optional[List[CreditSaleItem]] = None,
        order_id: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> TransactionResult:
        """
        Record a credit sale transaction

        Saga steps:
        1. Check idempotency key
        2. Get/create customer balance
        3. Validate credit limit
        4. Update balance with optimistic locking
        5. Create transaction record
        6. Store idempotency result

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            amount: Sale amount (positive)
            created_by: User recording the transaction
            customer_name: Customer name (for new customers)
            items: List of items in the sale
            order_id: Associated order ID (if any)
            notes: Transaction notes
            idempotency_key: Client-provided key for deduplication

        Returns:
            TransactionResult with success status
        """
        start_time = datetime.utcnow()

        # Validate amount
        if amount <= 0:
            return TransactionResult(
                success=False,
                error="Credit sale amount must be positive",
                error_code="INVALID_AMOUNT",
                processing_time_ms=0.0
            )

        # Step 1: Check idempotency
        if idempotency_key:
            cached_result = await self.db.check_idempotency_key(idempotency_key)
            if cached_result:
                logger.info(f"Returning cached result for idempotency key: {idempotency_key}")
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                return TransactionResult(
                    success=True,
                    transaction_id=cached_result.get('transaction_id'),
                    new_balance=Decimal(str(cached_result.get('new_balance', 0))),
                    message="Transaction already processed (idempotent replay)",
                    processing_time_ms=processing_time
                )

        # Generate transaction ID
        transaction_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"

        # Step 2: Get or create customer balance
        balance_result = await self.db.get_customer_balance(store_id, customer_phone)

        if not balance_result.success:
            # Customer doesn't exist - create new account
            if not customer_name:
                return TransactionResult(
                    success=False,
                    error="Customer name required for new credit account",
                    error_code="CUSTOMER_NAME_REQUIRED",
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

            create_result = await self.db.create_customer_balance(
                store_id=store_id,
                customer_phone=customer_phone,
                customer_name=customer_name
            )

            if not create_result.success:
                return TransactionResult(
                    success=False,
                    error=f"Failed to create customer account: {create_result.error}",
                    error_code="CUSTOMER_CREATE_FAILED",
                    processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )

            customer_balance = create_result.data
        else:
            customer_balance = balance_result.data

        # Step 3: Validate credit limit
        new_balance = customer_balance.outstanding_balance + amount
        if new_balance > customer_balance.credit_limit:
            logger.warning(
                f"Credit limit exceeded for {customer_phone} at store {store_id}: "
                f"limit={customer_balance.credit_limit}, current={customer_balance.outstanding_balance}, "
                f"requested={amount}"
            )
            return TransactionResult(
                success=False,
                error=f"Credit limit exceeded. Available credit: ₹{customer_balance.credit_limit - customer_balance.outstanding_balance:.2f}",
                error_code="CREDIT_LIMIT_EXCEEDED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        # Step 4: Update balance with optimistic locking
        balance_update_result = await self.db.update_customer_balance(
            store_id=store_id,
            customer_phone=customer_phone,
            amount_change=amount,
            expected_version=customer_balance.version,
            transaction_id=transaction_id
        )

        if not balance_update_result.success:
            return TransactionResult(
                success=False,
                error=f"Failed to update balance: {balance_update_result.error}",
                error_code="BALANCE_UPDATE_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        updated_balance = balance_update_result.data

        # Step 5: Create transaction record
        transaction = KhataTransaction(
            transaction_id=transaction_id,
            store_id=store_id,
            customer_phone=customer_phone,
            transaction_type="credit_sale",
            amount=amount,
            balance_before=customer_balance.outstanding_balance,
            balance_after=updated_balance.outstanding_balance,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            order_id=order_id,
            items=[asdict(item) if hasattr(item, '__dataclass_fields__') else item for item in (items or [])],
            notes=notes,
            idempotency_key=idempotency_key
        )

        txn_result = await self.db.create_transaction(transaction)

        if not txn_result.success:
            # Transaction record failed - need to rollback balance update
            logger.error(f"Transaction record failed for {transaction_id}, rolling back balance")

            rollback_result = await self._rollback_balance_update(
                store_id=store_id,
                customer_phone=customer_phone,
                amount=-amount,  # Reverse the change
                original_transaction_id=transaction_id,
                reason="Transaction record creation failed"
            )

            if not rollback_result:
                # Critical: Rollback failed
                logger.critical(
                    f"CRITICAL: Balance rollback FAILED for {transaction_id}! "
                    f"Store: {store_id}, Customer: {customer_phone}, Amount: {amount}"
                )

            return TransactionResult(
                success=False,
                error=f"Failed to create transaction record: {txn_result.error}",
                error_code="TRANSACTION_RECORD_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        # Step 6: Store idempotency result
        if idempotency_key:
            result_to_cache = {
                "transaction_id": transaction_id,
                "new_balance": float(updated_balance.outstanding_balance),
                "success": True
            }
            await self.db.store_idempotency_key(idempotency_key, transaction_id, result_to_cache)

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            f"Credit sale recorded: {transaction_id}, Store: {store_id}, "
            f"Customer: {customer_phone}, Amount: ₹{amount}, "
            f"New Balance: ₹{updated_balance.outstanding_balance}"
        )

        return TransactionResult(
            success=True,
            transaction_id=transaction_id,
            new_balance=updated_balance.outstanding_balance,
            message="Credit sale recorded successfully",
            processing_time_ms=processing_time
        )

    async def record_payment(
        self,
        store_id: str,
        customer_phone: str,
        amount: Decimal,
        created_by: str,
        payment_method: str = "cash",
        reference_id: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> TransactionResult:
        """
        Record a payment received from customer

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            amount: Payment amount (positive)
            created_by: User recording the payment
            payment_method: Payment method (cash, upi, bank, etc.)
            reference_id: External payment reference
            notes: Transaction notes
            idempotency_key: Client-provided key for deduplication

        Returns:
            TransactionResult with success status
        """
        start_time = datetime.utcnow()

        # Validate amount
        if amount <= 0:
            return TransactionResult(
                success=False,
                error="Payment amount must be positive",
                error_code="INVALID_AMOUNT",
                processing_time_ms=0.0
            )

        # Step 1: Check idempotency
        if idempotency_key:
            cached_result = await self.db.check_idempotency_key(idempotency_key)
            if cached_result:
                logger.info(f"Returning cached result for payment idempotency key: {idempotency_key}")
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                return TransactionResult(
                    success=True,
                    transaction_id=cached_result.get('transaction_id'),
                    new_balance=Decimal(str(cached_result.get('new_balance', 0))),
                    message="Payment already processed (idempotent replay)",
                    processing_time_ms=processing_time
                )

        # Generate transaction ID
        transaction_id = f"PMT-{uuid.uuid4().hex[:12].upper()}"

        # Step 2: Get customer balance
        balance_result = await self.db.get_customer_balance(store_id, customer_phone)

        if not balance_result.success:
            return TransactionResult(
                success=False,
                error="Customer not found at this store",
                error_code="CUSTOMER_NOT_FOUND",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        customer_balance = balance_result.data

        # Step 3: Validate payment amount
        if amount > customer_balance.outstanding_balance:
            # Allow overpayment but warn
            logger.warning(
                f"Payment exceeds outstanding balance for {customer_phone} at store {store_id}: "
                f"balance={customer_balance.outstanding_balance}, payment={amount}"
            )

        # Step 4: Update balance (subtract payment)
        balance_update_result = await self.db.update_customer_balance(
            store_id=store_id,
            customer_phone=customer_phone,
            amount_change=-amount,  # Negative to reduce balance
            expected_version=customer_balance.version,
            transaction_id=transaction_id
        )

        if not balance_update_result.success:
            return TransactionResult(
                success=False,
                error=f"Failed to update balance: {balance_update_result.error}",
                error_code="BALANCE_UPDATE_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        updated_balance = balance_update_result.data

        # Step 5: Create transaction record
        transaction = KhataTransaction(
            transaction_id=transaction_id,
            store_id=store_id,
            customer_phone=customer_phone,
            transaction_type="payment",
            amount=amount,
            balance_before=customer_balance.outstanding_balance,
            balance_after=updated_balance.outstanding_balance,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            reference_id=reference_id,
            notes=notes or f"Payment received via {payment_method}",
            idempotency_key=idempotency_key,
            metadata={"payment_method": payment_method}
        )

        txn_result = await self.db.create_transaction(transaction)

        if not txn_result.success:
            # Rollback balance update
            logger.error(f"Payment record failed for {transaction_id}, rolling back balance")

            await self._rollback_balance_update(
                store_id=store_id,
                customer_phone=customer_phone,
                amount=amount,  # Restore the amount
                original_transaction_id=transaction_id,
                reason="Payment record creation failed"
            )

            return TransactionResult(
                success=False,
                error=f"Failed to create payment record: {txn_result.error}",
                error_code="TRANSACTION_RECORD_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        # Step 6: Store idempotency result
        if idempotency_key:
            result_to_cache = {
                "transaction_id": transaction_id,
                "new_balance": float(updated_balance.outstanding_balance),
                "success": True
            }
            await self.db.store_idempotency_key(idempotency_key, transaction_id, result_to_cache)

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            f"Payment recorded: {transaction_id}, Store: {store_id}, "
            f"Customer: {customer_phone}, Amount: ₹{amount}, "
            f"New Balance: ₹{updated_balance.outstanding_balance}"
        )

        return TransactionResult(
            success=True,
            transaction_id=transaction_id,
            new_balance=updated_balance.outstanding_balance,
            message="Payment recorded successfully",
            processing_time_ms=processing_time
        )

    async def adjust_balance(
        self,
        store_id: str,
        customer_phone: str,
        amount: Decimal,
        created_by: str,
        adjustment_type: str = "correction",
        notes: str = None,
        idempotency_key: Optional[str] = None
    ) -> TransactionResult:
        """
        Administrative balance adjustment

        Used for corrections, write-offs, or other adjustments.

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            amount: Adjustment amount (positive increases, negative decreases)
            created_by: Admin user making adjustment
            adjustment_type: Type of adjustment (correction, write_off, opening_balance)
            notes: Reason for adjustment (required)
            idempotency_key: Client-provided key for deduplication

        Returns:
            TransactionResult with success status
        """
        start_time = datetime.utcnow()

        if not notes:
            return TransactionResult(
                success=False,
                error="Notes are required for balance adjustments",
                error_code="NOTES_REQUIRED",
                processing_time_ms=0.0
            )

        # Check idempotency
        if idempotency_key:
            cached_result = await self.db.check_idempotency_key(idempotency_key)
            if cached_result:
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                return TransactionResult(
                    success=True,
                    transaction_id=cached_result.get('transaction_id'),
                    new_balance=Decimal(str(cached_result.get('new_balance', 0))),
                    message="Adjustment already processed (idempotent replay)",
                    processing_time_ms=processing_time
                )

        transaction_id = f"ADJ-{uuid.uuid4().hex[:12].upper()}"

        # Get customer balance
        balance_result = await self.db.get_customer_balance(store_id, customer_phone)

        if not balance_result.success:
            return TransactionResult(
                success=False,
                error="Customer not found at this store",
                error_code="CUSTOMER_NOT_FOUND",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        customer_balance = balance_result.data

        # Validate adjustment won't create negative balance (unless write-off)
        new_balance = customer_balance.outstanding_balance + amount
        if new_balance < 0 and adjustment_type != "write_off":
            return TransactionResult(
                success=False,
                error="Adjustment would result in negative balance",
                error_code="INVALID_ADJUSTMENT",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        # Update balance
        balance_update_result = await self.db.update_customer_balance(
            store_id=store_id,
            customer_phone=customer_phone,
            amount_change=amount,
            expected_version=customer_balance.version,
            transaction_id=transaction_id
        )

        if not balance_update_result.success:
            return TransactionResult(
                success=False,
                error=f"Failed to update balance: {balance_update_result.error}",
                error_code="BALANCE_UPDATE_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        updated_balance = balance_update_result.data

        # Create transaction record
        transaction = KhataTransaction(
            transaction_id=transaction_id,
            store_id=store_id,
            customer_phone=customer_phone,
            transaction_type="adjustment",
            amount=abs(amount),
            balance_before=customer_balance.outstanding_balance,
            balance_after=updated_balance.outstanding_balance,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            notes=notes,
            idempotency_key=idempotency_key,
            metadata={
                "adjustment_type": adjustment_type,
                "direction": "increase" if amount > 0 else "decrease"
            }
        )

        txn_result = await self.db.create_transaction(transaction)

        if not txn_result.success:
            await self._rollback_balance_update(
                store_id=store_id,
                customer_phone=customer_phone,
                amount=-amount,
                original_transaction_id=transaction_id,
                reason="Adjustment record creation failed"
            )

            return TransactionResult(
                success=False,
                error=f"Failed to create adjustment record: {txn_result.error}",
                error_code="TRANSACTION_RECORD_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        if idempotency_key:
            result_to_cache = {
                "transaction_id": transaction_id,
                "new_balance": float(updated_balance.outstanding_balance),
                "success": True
            }
            await self.db.store_idempotency_key(idempotency_key, transaction_id, result_to_cache)

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            f"Balance adjustment: {transaction_id}, Type: {adjustment_type}, "
            f"Amount: ₹{amount}, New Balance: ₹{updated_balance.outstanding_balance}"
        )

        return TransactionResult(
            success=True,
            transaction_id=transaction_id,
            new_balance=updated_balance.outstanding_balance,
            message=f"Balance {adjustment_type} applied successfully",
            processing_time_ms=processing_time
        )

    async def reverse_transaction(
        self,
        original_transaction_id: str,
        created_by: str,
        reason: str,
        idempotency_key: Optional[str] = None
    ) -> TransactionResult:
        """
        Reverse a previous transaction

        Creates a compensating transaction that reverses the effect
        of the original transaction.

        Args:
            original_transaction_id: ID of transaction to reverse
            created_by: User initiating reversal
            reason: Reason for reversal
            idempotency_key: Client-provided key for deduplication

        Returns:
            TransactionResult with reversal transaction ID
        """
        start_time = datetime.utcnow()

        # Check idempotency
        if idempotency_key:
            cached_result = await self.db.check_idempotency_key(idempotency_key)
            if cached_result:
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                return TransactionResult(
                    success=True,
                    transaction_id=cached_result.get('transaction_id'),
                    new_balance=Decimal(str(cached_result.get('new_balance', 0))),
                    message="Reversal already processed (idempotent replay)",
                    processing_time_ms=processing_time
                )

        # Get original transaction
        txn_result = await self.db.get_transaction(original_transaction_id)

        if not txn_result.success:
            return TransactionResult(
                success=False,
                error=f"Original transaction not found: {original_transaction_id}",
                error_code="TRANSACTION_NOT_FOUND",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        original = txn_result.data

        # Check if already reversed
        if original.transaction_type == "reversal":
            return TransactionResult(
                success=False,
                error="Cannot reverse a reversal transaction",
                error_code="INVALID_REVERSAL",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        # Calculate reversal amount
        if original.transaction_type in ("credit_sale", "adjustment"):
            reversal_amount = -original.amount  # Reduce balance
        else:  # payment
            reversal_amount = original.amount  # Increase balance

        reversal_id = f"REV-{uuid.uuid4().hex[:12].upper()}"

        # Get current balance
        balance_result = await self.db.get_customer_balance(
            original.store_id, original.customer_phone
        )

        if not balance_result.success:
            return TransactionResult(
                success=False,
                error="Customer balance not found",
                error_code="BALANCE_NOT_FOUND",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        customer_balance = balance_result.data

        # Update balance
        balance_update_result = await self.db.update_customer_balance(
            store_id=original.store_id,
            customer_phone=original.customer_phone,
            amount_change=reversal_amount,
            expected_version=customer_balance.version,
            transaction_id=reversal_id
        )

        if not balance_update_result.success:
            return TransactionResult(
                success=False,
                error=f"Failed to update balance for reversal: {balance_update_result.error}",
                error_code="BALANCE_UPDATE_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        updated_balance = balance_update_result.data

        # Create reversal transaction record
        reversal_txn = KhataTransaction(
            transaction_id=reversal_id,
            store_id=original.store_id,
            customer_phone=original.customer_phone,
            transaction_type="reversal",
            amount=abs(reversal_amount),
            balance_before=customer_balance.outstanding_balance,
            balance_after=updated_balance.outstanding_balance,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            reference_id=original_transaction_id,
            notes=f"Reversal of {original_transaction_id}: {reason}",
            idempotency_key=idempotency_key,
            metadata={
                "original_transaction_id": original_transaction_id,
                "original_type": original.transaction_type,
                "reversal_reason": reason
            }
        )

        txn_create_result = await self.db.create_transaction(reversal_txn)

        if not txn_create_result.success:
            # Rollback balance
            await self._rollback_balance_update(
                store_id=original.store_id,
                customer_phone=original.customer_phone,
                amount=-reversal_amount,
                original_transaction_id=reversal_id,
                reason="Reversal record creation failed"
            )

            return TransactionResult(
                success=False,
                error=f"Failed to create reversal record: {txn_create_result.error}",
                error_code="TRANSACTION_RECORD_FAILED",
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )

        if idempotency_key:
            result_to_cache = {
                "transaction_id": reversal_id,
                "new_balance": float(updated_balance.outstanding_balance),
                "original_transaction_id": original_transaction_id,
                "success": True
            }
            await self.db.store_idempotency_key(idempotency_key, reversal_id, result_to_cache)

        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(
            f"Transaction reversed: {reversal_id} reverses {original_transaction_id}, "
            f"Amount: ₹{abs(reversal_amount)}, New Balance: ₹{updated_balance.outstanding_balance}"
        )

        return TransactionResult(
            success=True,
            transaction_id=reversal_id,
            new_balance=updated_balance.outstanding_balance,
            message=f"Transaction {original_transaction_id} reversed successfully",
            processing_time_ms=processing_time
        )

    async def get_customer_ledger(
        self,
        store_id: str,
        customer_phone: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get customer transaction ledger

        Returns transactions with running balance calculation.

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            start_date: Optional start date filter
            end_date: Optional end date filter
            cursor: Pagination cursor
            limit: Maximum records per page

        Returns:
            Dict with transactions, balance info, and pagination
        """
        # Get current balance
        balance_result = await self.db.get_customer_balance(store_id, customer_phone)

        if not balance_result.success:
            return {
                "success": False,
                "error": "Customer not found"
            }

        customer = balance_result.data

        # Get transactions
        txn_result = await self.db.get_customer_transactions(
            store_id=store_id,
            customer_phone=customer_phone,
            start_date=start_date,
            end_date=end_date,
            cursor=cursor,
            limit=limit
        )

        if not txn_result.success:
            return {
                "success": False,
                "error": txn_result.error
            }

        return {
            "success": True,
            "customer": {
                "phone": customer_phone,
                "name": customer.customer_name,
                "outstanding_balance": float(customer.outstanding_balance),
                "credit_limit": float(customer.credit_limit),
                "available_credit": float(customer.credit_limit - customer.outstanding_balance)
            },
            "transactions": [
                {
                    "id": txn.transaction_id,
                    "type": txn.transaction_type,
                    "amount": float(txn.amount),
                    "balance_after": float(txn.balance_after),
                    "created_at": txn.created_at,
                    "created_by": txn.created_by,
                    "notes": txn.notes
                }
                for txn in txn_result.data
            ],
            "next_cursor": txn_result.next_cursor,
            "has_more": txn_result.next_cursor is not None
        }

    async def _rollback_balance_update(
        self,
        store_id: str,
        customer_phone: str,
        amount: Decimal,
        original_transaction_id: str,
        reason: str
    ) -> bool:
        """
        Rollback a balance update (compensating transaction)

        Args:
            store_id: Store identifier
            customer_phone: Customer phone number
            amount: Amount to adjust (positive to increase, negative to decrease)
            original_transaction_id: Original transaction being rolled back
            reason: Reason for rollback

        Returns:
            True if rollback successful, False otherwise
        """
        logger.info(
            f"Executing balance rollback for {original_transaction_id}: "
            f"amount={amount}, reason={reason}"
        )

        try:
            # Get current balance to get version
            balance_result = await self.db.get_customer_balance(store_id, customer_phone)

            if not balance_result.success:
                logger.error(f"Cannot rollback - customer not found: {customer_phone}")
                return False

            customer_balance = balance_result.data

            # Apply rollback
            rollback_id = f"ROLLBACK-{uuid.uuid4().hex[:8].upper()}"

            result = await self.db.update_customer_balance(
                store_id=store_id,
                customer_phone=customer_phone,
                amount_change=amount,
                expected_version=customer_balance.version,
                transaction_id=rollback_id,
                max_retries=5  # More retries for rollback
            )

            if result.success:
                logger.info(f"Balance rollback successful: {rollback_id}")
                return True
            else:
                logger.error(f"Balance rollback failed: {result.error}")
                return False

        except Exception as e:
            logger.critical(
                f"CRITICAL: Exception during balance rollback for {original_transaction_id}: {e}"
            )
            return False


# =============================================================================
# Factory Functions
# =============================================================================

def create_khata_service() -> KhataTransactionService:
    """Create KhataTransactionService with real dependencies"""
    return KhataTransactionService(khata_db)


# Global instance (lazy initialization)
_khata_service: Optional[KhataTransactionService] = None


def get_khata_service() -> KhataTransactionService:
    """Get or create the global KhataTransactionService instance"""
    global _khata_service
    if _khata_service is None:
        _khata_service = create_khata_service()
    return _khata_service
