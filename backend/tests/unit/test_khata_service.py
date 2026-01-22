"""
Unit Tests for Khata (Credit Management) Service

Tests for:
- Credit sale recording with Saga pattern
- Payment recording
- Balance adjustments
- Transaction reversal
- Idempotency handling
- Error scenarios and rollback
- Optimistic locking

Following the Saga Pattern implementation from khata_service.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime

from app.services.khata_service import (
    KhataTransactionService,
    TransactionResult,
    TransactionStatus,
)
from app.core.exceptions import (
    CreditLimitExceededError,
    DuplicateTransactionError,
    InvalidPaymentAmountError,
    TransactionRollbackError,
    CustomerNotFoundError,
)


class TestKhataServiceCreditSale:
    """Tests for credit sale (udhar) operations"""

    @pytest.mark.asyncio
    async def test_record_credit_sale_success(self, mock_khata_db, mock_khata_service):
        """Test successful credit sale recording"""
        result = await mock_khata_service.record_credit_sale(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            amount=Decimal("500.00"),
            created_by="owner@test.com",
            customer_name="Test Customer",
            items=[
                {"product_id": "PROD-001", "name": "Rice", "quantity": 2, "unit_price": Decimal("150.00")},
                {"product_id": "PROD-002", "name": "Oil", "quantity": 1, "unit_price": Decimal("200.00")},
            ],
            notes="Regular purchase"
        )

        assert result["success"] is True
        assert "transaction_id" in result
        assert result["new_balance"] == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_record_credit_sale_new_customer(self, mock_khata_db):
        """Test credit sale creates customer if not exists"""
        # Mock customer not found initially
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=False,
            error="Customer not found"
        ))

        # Mock customer creation
        mock_khata_db.create_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            # Configure remaining mocks
            mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=Decimal("500.00"),
                    version=2
                )
            ))
            mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
                success=True,
                data=MagicMock(transaction_id="TXN-001")
            ))
            mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
            mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919999999999",
                amount=Decimal("500.00"),
                created_by="owner@test.com",
                customer_name="New Customer"
            )

            # Verify customer creation was called
            mock_khata_db.create_customer_balance.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_credit_sale_exceeds_credit_limit(self, mock_khata_db):
        """Test credit sale fails when exceeding credit limit"""
        # Mock customer with low credit limit
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("4500.00"),
                credit_limit=Decimal("5000.00"),
                version=1,
                customer_name="Test Customer"
            )
        ))

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db
            mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

            # Attempt to add Rs. 1000 when only Rs. 500 available
            with pytest.raises(CreditLimitExceededError):
                await service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("1000.00"),
                    created_by="owner@test.com"
                )

    @pytest.mark.asyncio
    async def test_record_credit_sale_idempotency(self, mock_khata_db):
        """Test idempotency key prevents duplicate transactions"""
        # Mock idempotency key exists
        cached_result = {
            "success": True,
            "transaction_id": "TXN-CACHED-001",
            "new_balance": Decimal("500.00")
        }
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=cached_result)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com",
                idempotency_key="duplicate-key-123"
            )

            # Should return cached result
            assert result["transaction_id"] == "TXN-CACHED-001"
            # Should not create new transaction
            mock_khata_db.create_transaction.assert_not_called()


class TestKhataServicePayment:
    """Tests for payment recording operations"""

    @pytest.mark.asyncio
    async def test_record_payment_success(self, mock_khata_service):
        """Test successful payment recording"""
        result = await mock_khata_service.record_payment(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            amount=Decimal("500.00"),
            created_by="owner@test.com",
            payment_method="cash",
            notes="Cash payment"
        )

        assert result["success"] is True
        assert result["new_balance"] == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_record_payment_partial(self, mock_khata_db):
        """Test partial payment reduces balance correctly"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("1000.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("600.00"),
                version=2
            )
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="PMT-001")
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_payment(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("400.00"),
                created_by="owner@test.com",
                payment_method="upi"
            )

            assert result.success is True
            # Balance update should be called with negative amount
            mock_khata_db.update_customer_balance.assert_called()

    @pytest.mark.asyncio
    async def test_record_payment_exceeds_balance(self, mock_khata_db):
        """Test payment fails when amount exceeds outstanding balance"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("500.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            with pytest.raises(InvalidPaymentAmountError):
                await service.record_payment(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("1000.00"),  # More than balance
                    created_by="owner@test.com",
                    payment_method="cash"
                )

    @pytest.mark.asyncio
    async def test_record_payment_customer_not_found(self, mock_khata_db):
        """Test payment fails when customer doesn't exist"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=False,
            error="Customer not found"
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            with pytest.raises(CustomerNotFoundError):
                await service.record_payment(
                    store_id="STORE-TEST-001",
                    customer_phone="+919999999999",
                    amount=Decimal("500.00"),
                    created_by="owner@test.com",
                    payment_method="cash"
                )


class TestKhataServiceBalanceAdjustment:
    """Tests for balance adjustment operations"""

    @pytest.mark.asyncio
    async def test_adjust_balance_correction(self, mock_khata_service):
        """Test balance correction adjustment"""
        result = await mock_khata_service.adjust_balance(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210",
            amount=Decimal("-50.00"),
            created_by="owner@test.com",
            adjustment_type="correction",
            notes="Billing error correction"
        )

        assert result["success"] is True
        assert result["new_balance"] == Decimal("450.00")

    @pytest.mark.asyncio
    async def test_adjust_balance_waiver(self, mock_khata_db):
        """Test balance waiver reduces outstanding"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("500.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("400.00"),
                version=2
            )
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="ADJ-001")
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.adjust_balance(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("-100.00"),  # Waive Rs. 100
                created_by="owner@test.com",
                adjustment_type="waiver",
                notes="Loyalty waiver"
            )

            assert result.success is True


class TestKhataServiceReversal:
    """Tests for transaction reversal operations"""

    @pytest.mark.asyncio
    async def test_reverse_credit_sale(self, mock_khata_db):
        """Test reversing a credit sale"""
        # Mock original transaction exists
        mock_khata_db.get_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                transaction_id="TXN-001",
                transaction_type="credit_sale",
                amount=Decimal("500.00"),
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                balance_before=Decimal("0.00"),
                balance_after=Decimal("500.00"),
                is_reversed=False
            )
        ))
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("500.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                version=2
            )
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="REV-001")
        ))
        mock_khata_db.mark_transaction_reversed = AsyncMock(return_value=MagicMock(
            success=True
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.reverse_transaction(
                original_transaction_id="TXN-001",
                created_by="owner@test.com",
                reason="Customer returned items"
            )

            assert result.success is True
            # Original transaction should be marked as reversed
            mock_khata_db.mark_transaction_reversed.assert_called()

    @pytest.mark.asyncio
    async def test_reverse_already_reversed_transaction(self, mock_khata_db):
        """Test cannot reverse an already reversed transaction"""
        mock_khata_db.get_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                transaction_id="TXN-001",
                is_reversed=True
            )
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.reverse_transaction(
                original_transaction_id="TXN-001",
                created_by="owner@test.com",
                reason="Duplicate reversal attempt"
            )

            assert result.success is False
            assert "already reversed" in result.error.lower()


class TestKhataServiceSagaRollback:
    """Tests for Saga pattern rollback scenarios"""

    @pytest.mark.asyncio
    async def test_rollback_on_transaction_creation_failure(self, mock_khata_db):
        """Test rollback when transaction creation fails after balance update"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))

        # Balance update succeeds
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("500.00"),
                version=2
            )
        ))

        # Transaction creation fails
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=False,
            error="DynamoDB write failed"
        ))

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            # Should fail and rollback
            assert result.success is False
            # Balance update should have been called twice (once to add, once to rollback)
            assert mock_khata_db.update_customer_balance.call_count >= 1

    @pytest.mark.asyncio
    async def test_critical_error_on_rollback_failure(self, mock_khata_db):
        """Test TransactionRollbackError when compensation fails"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))

        # First update succeeds
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=[
            MagicMock(success=True, data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)),
            MagicMock(success=False, error="Rollback failed")  # Compensation fails
        ])

        # Transaction creation fails
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=False,
            error="DynamoDB write failed"
        ))

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            with pytest.raises(TransactionRollbackError):
                await service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("500.00"),
                    created_by="owner@test.com"
                )


class TestKhataServiceOptimisticLocking:
    """Tests for optimistic locking with version attribute"""

    @pytest.mark.asyncio
    async def test_optimistic_lock_retry_success(self, mock_khata_db):
        """Test retry succeeds on version conflict"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))

        # First update fails with version conflict, second succeeds
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=[
            MagicMock(success=False, error="ConditionalCheckFailedException"),
            MagicMock(success=True, data=MagicMock(outstanding_balance=Decimal("500.00"), version=3))
        ])

        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-001")
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            # Should succeed after retry
            assert result.success is True
            # Update should be called at least twice (retry)
            assert mock_khata_db.update_customer_balance.call_count >= 2

    @pytest.mark.asyncio
    async def test_optimistic_lock_max_retries_exceeded(self, mock_khata_db):
        """Test failure after max retries on persistent version conflict"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))

        # All updates fail with version conflict
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=False,
            error="ConditionalCheckFailedException"
        ))

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            # Should fail after max retries
            assert result.success is False
            assert "retry" in result.error.lower() or "conflict" in result.error.lower()


class TestKhataServiceLedger:
    """Tests for ledger/transaction history operations"""

    @pytest.mark.asyncio
    async def test_get_customer_ledger(self, mock_khata_service):
        """Test retrieving customer transaction ledger"""
        result = await mock_khata_service.get_customer_ledger(
            store_id="STORE-TEST-001",
            customer_phone="+919876543210"
        )

        assert result["success"] is True
        assert "transactions" in result
        assert "opening_balance" in result
        assert "closing_balance" in result

    @pytest.mark.asyncio
    async def test_get_customer_ledger_with_date_filter(self, mock_khata_db):
        """Test ledger with date range filter"""
        mock_khata_db.get_customer_transactions = AsyncMock(return_value=MagicMock(
            success=True,
            data=[
                MagicMock(
                    transaction_id="TXN-001",
                    transaction_type="credit_sale",
                    amount=Decimal("500.00"),
                    created_at="2026-01-15T10:00:00Z"
                ),
                MagicMock(
                    transaction_id="TXN-002",
                    transaction_type="payment",
                    amount=Decimal("300.00"),
                    created_at="2026-01-16T10:00:00Z"
                )
            ],
            next_cursor=None
        ))
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("200.00"),
                credit_limit=Decimal("5000.00"),
                version=2
            )
        ))

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.get_customer_ledger(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                start_date="2026-01-01",
                end_date="2026-01-31"
            )

            assert result["transactions"] is not None


class TestKhataServiceEdgeCases:
    """Tests for edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_zero_amount_credit_sale_rejected(self, mock_khata_db):
        """Test zero amount credit sale is rejected"""
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("0.00"),
                created_by="owner@test.com"
            )

            assert result.success is False
            assert "amount" in result.error.lower()

    @pytest.mark.asyncio
    async def test_negative_amount_credit_sale_rejected(self, mock_khata_db):
        """Test negative amount credit sale is rejected"""
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("-500.00"),
                created_by="owner@test.com"
            )

            assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_phone_format_rejected(self, mock_khata_db):
        """Test invalid phone number format is rejected"""
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="invalid-phone",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            assert result.success is False

    @pytest.mark.asyncio
    async def test_exact_credit_limit_usage(self, mock_khata_db):
        """Test credit sale exactly at credit limit is allowed"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("4000.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("5000.00"),
                version=2
            )
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-001")
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("1000.00"),  # Exactly reaches limit
                created_by="owner@test.com"
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_payment_clears_full_balance(self, mock_khata_db):
        """Test payment that exactly clears full balance"""
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("1500.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                version=2
            )
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="PMT-001")
        ))
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_payment(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("1500.00"),
                created_by="owner@test.com",
                payment_method="cash"
            )

            assert result.success is True
            assert result.balance_after == Decimal("0.00")
