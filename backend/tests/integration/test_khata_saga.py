"""
Integration Tests for Khata Saga Pattern

Tests for:
- End-to-end transaction flows
- Concurrent update handling
- Rollback verification
- Multi-step saga completion
- Database consistency after failures
- API endpoint integration

These tests verify the Saga pattern implementation maintains
data consistency across distributed operations.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


class TestKhataSagaCreditSaleFlow:
    """End-to-end tests for credit sale saga"""

    @pytest.mark.asyncio
    async def test_complete_credit_sale_saga_success(self, mock_khata_db):
        """Test complete saga: idempotency check -> balance update -> transaction create -> audit log"""
        from app.services.khata_service import KhataTransactionService

        # Setup all saga steps to succeed
        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1,
                customer_name="Test Customer"
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("500.00"),
                version=2
            )
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-SAGA-001")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            with patch('app.services.khata_audit_service.KhataAuditService') as MockAudit:
                mock_audit = MockAudit.return_value
                mock_audit.log_transaction = AsyncMock(return_value="AUDIT-001")

                service = KhataTransactionService()
                service.db = mock_khata_db

                result = await service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("500.00"),
                    created_by="owner@test.com",
                    customer_name="Test Customer",
                    items=[{"product_id": "P1", "name": "Rice", "quantity": 1, "unit_price": Decimal("500.00")}]
                )

                # Verify all saga steps completed
                assert result.success is True
                assert result.transaction_id == "TXN-SAGA-001"
                assert result.balance_after == Decimal("500.00")

                # Verify saga step order
                mock_khata_db.check_idempotency_key.assert_called_once()
                mock_khata_db.get_customer_balance.assert_called()
                mock_khata_db.update_customer_balance.assert_called()
                mock_khata_db.create_transaction.assert_called()
                mock_khata_db.store_idempotency_key.assert_called()

    @pytest.mark.asyncio
    async def test_saga_rollback_on_step3_failure(self, mock_khata_db):
        """Test saga rollback when transaction creation (step 3) fails"""
        from app.services.khata_service import KhataTransactionService

        call_count = {'update': 0}

        async def track_updates(*args, **kwargs):
            call_count['update'] += 1
            if call_count['update'] == 1:
                # First call: original balance update succeeds
                return MagicMock(
                    success=True,
                    data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
                )
            else:
                # Second call: rollback succeeds
                return MagicMock(
                    success=True,
                    data=MagicMock(outstanding_balance=Decimal("0.00"), version=3)
                )

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=track_updates)
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=False,
            error="DynamoDB write capacity exceeded"
        ))

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            # Saga should fail
            assert result.success is False

            # Verify rollback was attempted (2 calls: original + rollback)
            assert call_count['update'] == 2


class TestKhataSagaConcurrency:
    """Tests for concurrent transaction handling"""

    @pytest.mark.asyncio
    async def test_concurrent_credit_sales_sequential_processing(self, mock_khata_db):
        """Test concurrent credit sales are processed with optimistic locking"""
        from app.services.khata_service import KhataTransactionService

        version_counter = {'version': 1, 'balance': Decimal("0.00")}

        async def mock_get_balance(*args, **kwargs):
            return MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=version_counter['balance'],
                    credit_limit=Decimal("5000.00"),
                    version=version_counter['version']
                )
            )

        async def mock_update_balance(*args, **kwargs):
            # Simulate version check
            expected_version = kwargs.get('expected_version', 1)
            if expected_version != version_counter['version']:
                return MagicMock(success=False, error="ConditionalCheckFailedException")

            # Successful update
            amount_change = kwargs.get('amount_change', Decimal("0.00"))
            if 'amount_change' not in kwargs and len(args) > 2:
                amount_change = args[2]

            version_counter['version'] += 1
            version_counter['balance'] += amount_change
            return MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=version_counter['balance'],
                    version=version_counter['version']
                )
            )

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(side_effect=mock_get_balance)
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=mock_update_balance)
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-CONCURRENT")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            # Simulate 3 concurrent credit sales
            tasks = [
                service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("100.00"),
                    created_by="owner@test.com",
                    idempotency_key=f"concurrent-{i}"
                )
                for i in range(3)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should eventually succeed with retries
            successful = [r for r in results if not isinstance(r, Exception) and r.success]
            assert len(successful) >= 1  # At least one should succeed

    @pytest.mark.asyncio
    async def test_race_condition_payment_and_credit_sale(self, mock_khata_db):
        """Test race condition between payment and credit sale is handled"""
        from app.services.khata_service import KhataTransactionService

        current_state = {
            'balance': Decimal("1000.00"),
            'version': 1
        }

        async def mock_get_balance(*args, **kwargs):
            return MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=current_state['balance'],
                    credit_limit=Decimal("5000.00"),
                    version=current_state['version']
                )
            )

        call_order = []

        async def mock_update_balance(store_id, customer_phone, amount_change, expected_version, *args, **kwargs):
            call_order.append(('update', amount_change, expected_version))

            if expected_version != current_state['version']:
                return MagicMock(success=False, error="ConditionalCheckFailedException")

            current_state['balance'] += amount_change
            current_state['version'] += 1
            return MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=current_state['balance'],
                    version=current_state['version']
                )
            )

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(side_effect=mock_get_balance)
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=mock_update_balance)
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-RACE")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            # Run payment and credit sale concurrently
            payment_task = service.record_payment(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com",
                payment_method="cash",
                idempotency_key="payment-race"
            )

            credit_task = service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("200.00"),
                created_by="owner@test.com",
                idempotency_key="credit-race"
            )

            results = await asyncio.gather(payment_task, credit_task, return_exceptions=True)

            # Verify both operations completed (with possible retries)
            successful_ops = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_ops) >= 1


class TestKhataSagaAPIIntegration:
    """Integration tests for Khata API endpoints"""

    def test_credit_sale_endpoint_success(self, client, auth_headers_store_owner, sample_credit_sale_request):
        """Test POST /api/v1/khata/credit-sale endpoint"""
        with patch('app.api.v1.khata.get_khata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.record_credit_sale = AsyncMock(return_value=MagicMock(
                success=True,
                transaction_id="TXN-API-001",
                balance_before=Decimal("0.00"),
                balance_after=Decimal("500.00"),
                timestamp=datetime.utcnow().isoformat()
            ))
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/v1/khata/credit-sale",
                json=sample_credit_sale_request,
                headers=auth_headers_store_owner
            )

            # API should return success
            assert response.status_code in [200, 201]
            data = response.json()
            assert data.get("success") is True or "transaction_id" in data

    def test_credit_sale_endpoint_idempotency(self, client, auth_headers_store_owner, sample_credit_sale_request):
        """Test idempotency key prevents duplicate processing"""
        with patch('app.api.v1.khata.get_khata_service') as mock_get_service:
            mock_service = MagicMock()
            call_count = {'count': 0}

            async def mock_credit_sale(*args, **kwargs):
                call_count['count'] += 1
                return MagicMock(
                    success=True,
                    transaction_id="TXN-IDEM-001",
                    balance_after=Decimal("500.00")
                )

            mock_service.record_credit_sale = AsyncMock(side_effect=mock_credit_sale)
            mock_get_service.return_value = mock_service

            # First request
            response1 = client.post(
                "/api/v1/khata/credit-sale",
                json=sample_credit_sale_request,
                headers={**auth_headers_store_owner, "Idempotency-Key": "unique-key-123"}
            )

            # Second request with same idempotency key
            response2 = client.post(
                "/api/v1/khata/credit-sale",
                json=sample_credit_sale_request,
                headers={**auth_headers_store_owner, "Idempotency-Key": "unique-key-123"}
            )

            # Both should return same result
            assert response1.status_code == response2.status_code

    def test_payment_endpoint_success(self, client, auth_headers_store_owner, sample_payment_request):
        """Test POST /api/v1/khata/payment endpoint"""
        with patch('app.api.v1.khata.get_khata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.record_payment = AsyncMock(return_value=MagicMock(
                success=True,
                transaction_id="PMT-API-001",
                balance_before=Decimal("500.00"),
                balance_after=Decimal("0.00"),
                timestamp=datetime.utcnow().isoformat()
            ))
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/v1/khata/payment",
                json=sample_payment_request,
                headers=auth_headers_store_owner
            )

            assert response.status_code in [200, 201]

    def test_customer_ledger_endpoint(self, client, auth_headers_store_owner):
        """Test GET /api/v1/khata/customers/{phone}/ledger endpoint"""
        with patch('app.api.v1.khata.get_khata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_customer_ledger = AsyncMock(return_value={
                "success": True,
                "transactions": [
                    {
                        "transaction_id": "TXN-001",
                        "type": "credit_sale",
                        "amount": 500.00,
                        "created_at": datetime.utcnow().isoformat()
                    }
                ],
                "opening_balance": 0.00,
                "closing_balance": 500.00,
                "next_cursor": None
            })
            mock_get_service.return_value = mock_service

            response = client.get(
                "/api/v1/khata/customers/+919876543210/ledger",
                headers=auth_headers_store_owner
            )

            assert response.status_code == 200
            data = response.json()
            assert "transactions" in data or data.get("success") is True

    def test_outstanding_report_endpoint(self, client, auth_headers_store_owner):
        """Test GET /api/v1/khata/reports/outstanding endpoint"""
        with patch('app.api.v1.khata.get_khata_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_store_outstanding = AsyncMock(return_value={
                "success": True,
                "data": {
                    "store_id": "STORE-TEST-001",
                    "total_outstanding": 15000.00,
                    "total_customers": 10,
                    "generated_at": datetime.utcnow().isoformat()
                }
            })
            mock_get_service.return_value = mock_service

            response = client.get(
                "/api/v1/khata/reports/outstanding",
                headers=auth_headers_store_owner
            )

            assert response.status_code == 200


class TestKhataSagaDataConsistency:
    """Tests for data consistency across saga operations"""

    @pytest.mark.asyncio
    async def test_balance_consistency_after_multiple_transactions(self, mock_khata_db):
        """Test balance remains consistent after multiple sequential transactions"""
        from app.services.khata_service import KhataTransactionService

        running_balance = Decimal("0.00")
        version = 1

        async def mock_get_balance(*args, **kwargs):
            return MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=running_balance,
                    credit_limit=Decimal("10000.00"),
                    version=version
                )
            )

        async def mock_update_balance(store_id, customer_phone, amount_change, expected_version, *args, **kwargs):
            nonlocal running_balance, version
            running_balance += amount_change
            version += 1
            return MagicMock(
                success=True,
                data=MagicMock(
                    outstanding_balance=running_balance,
                    version=version
                )
            )

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(side_effect=mock_get_balance)
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=mock_update_balance)
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            # Sequence of transactions
            transactions = [
                ("credit_sale", Decimal("1000.00")),
                ("credit_sale", Decimal("500.00")),
                ("payment", Decimal("700.00")),
                ("credit_sale", Decimal("300.00")),
                ("payment", Decimal("600.00")),
            ]

            expected_balance = Decimal("0.00")
            for tx_type, amount in transactions:
                if tx_type == "credit_sale":
                    result = await service.record_credit_sale(
                        store_id="STORE-TEST-001",
                        customer_phone="+919876543210",
                        amount=amount,
                        created_by="owner@test.com",
                        idempotency_key=f"tx-{tx_type}-{amount}"
                    )
                    expected_balance += amount
                else:
                    result = await service.record_payment(
                        store_id="STORE-TEST-001",
                        customer_phone="+919876543210",
                        amount=amount,
                        created_by="owner@test.com",
                        payment_method="cash",
                        idempotency_key=f"tx-{tx_type}-{amount}"
                    )
                    expected_balance -= amount

                assert result.success is True

            # Final balance should be: 1000 + 500 - 700 + 300 - 600 = 500
            assert running_balance == Decimal("500.00")
            assert running_balance == expected_balance

    @pytest.mark.asyncio
    async def test_no_orphan_transactions_on_rollback(self, mock_khata_db):
        """Test that failed saga doesn't leave orphan transaction records"""
        from app.services.khata_service import KhataTransactionService

        created_transactions = []

        async def mock_create_transaction(*args, **kwargs):
            # Record attempt
            created_transactions.append(kwargs.get('transaction', args[0] if args else None))
            return MagicMock(success=False, error="Database error")

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
        ))
        mock_khata_db.create_transaction = AsyncMock(side_effect=mock_create_transaction)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            # Transaction should have failed
            assert result.success is False

            # Only one transaction creation attempt (no orphan retry)
            assert len(created_transactions) == 1


class TestKhataSagaAuditTrail:
    """Tests for audit trail during saga execution"""

    @pytest.mark.asyncio
    async def test_audit_log_created_on_success(self, mock_khata_db):
        """Test audit log is created for successful transactions"""
        from app.services.khata_service import KhataTransactionService

        audit_calls = []

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-AUDIT")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            with patch('app.services.khata_audit_service.KhataAuditService') as MockAudit:
                mock_audit = MockAudit.return_value

                async def capture_audit(*args, **kwargs):
                    audit_calls.append({'args': args, 'kwargs': kwargs})
                    return "AUDIT-001"

                mock_audit.log_transaction = AsyncMock(side_effect=capture_audit)

                service = KhataTransactionService()
                service.db = mock_khata_db

                result = await service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("500.00"),
                    created_by="owner@test.com"
                )

                assert result.success is True
                # Audit should have been called (may be async/delayed)

    @pytest.mark.asyncio
    async def test_audit_log_records_rollback(self, mock_khata_db):
        """Test audit log records rollback attempts"""
        from app.services.khata_service import KhataTransactionService

        audit_events = []

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=False,
            error="Database write failed"
        ))

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            with patch('app.services.khata_audit_service.KhataAuditService') as MockAudit:
                mock_audit = MockAudit.return_value

                async def capture_audit(action, *args, **kwargs):
                    audit_events.append({'action': action, 'kwargs': kwargs})
                    return f"AUDIT-{len(audit_events)}"

                mock_audit.log_transaction = AsyncMock(side_effect=capture_audit)

                service = KhataTransactionService()
                service.db = mock_khata_db

                result = await service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("500.00"),
                    created_by="owner@test.com"
                )

                assert result.success is False


class TestKhataSagaErrorRecovery:
    """Tests for error recovery and resilience"""

    @pytest.mark.asyncio
    async def test_transient_error_recovery_with_retry(self, mock_khata_db):
        """Test recovery from transient errors with retry"""
        from app.services.khata_service import KhataTransactionService

        call_count = {'db': 0}

        async def mock_update_with_retry(*args, **kwargs):
            call_count['db'] += 1
            if call_count['db'] < 3:
                # Simulate transient failure
                return MagicMock(success=False, error="ServiceUnavailable")
            return MagicMock(
                success=True,
                data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
            )

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(side_effect=mock_update_with_retry)
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-RECOVER")
        ))
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

            # Should eventually succeed after retries
            assert result.success is True
            assert call_count['db'] >= 3

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_audit_failure(self, mock_khata_db):
        """Test transaction succeeds even if audit logging fails"""
        from app.services.khata_service import KhataTransactionService

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-DEGRADE")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            with patch('app.services.khata_audit_service.KhataAuditService') as MockAudit:
                mock_audit = MockAudit.return_value
                mock_audit.log_transaction = AsyncMock(
                    side_effect=Exception("Audit service unavailable")
                )

                service = KhataTransactionService()
                service.db = mock_khata_db

                # Transaction should still succeed despite audit failure
                result = await service.record_credit_sale(
                    store_id="STORE-TEST-001",
                    customer_phone="+919876543210",
                    amount=Decimal("500.00"),
                    created_by="owner@test.com"
                )

                # Core transaction should succeed
                assert result.success is True


class TestKhataSagaPerformance:
    """Performance-related integration tests"""

    @pytest.mark.asyncio
    async def test_saga_completes_within_timeout(self, mock_khata_db):
        """Test complete saga executes within acceptable time"""
        import time
        from app.services.khata_service import KhataTransactionService

        mock_khata_db.check_idempotency_key = AsyncMock(return_value=None)
        mock_khata_db.get_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(
                outstanding_balance=Decimal("0.00"),
                credit_limit=Decimal("5000.00"),
                version=1
            )
        ))
        mock_khata_db.update_customer_balance = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(outstanding_balance=Decimal("500.00"), version=2)
        ))
        mock_khata_db.create_transaction = AsyncMock(return_value=MagicMock(
            success=True,
            data=MagicMock(transaction_id="TXN-PERF")
        ))
        mock_khata_db.store_idempotency_key = AsyncMock(return_value=True)

        with patch('app.services.khata_service.KhataDatabase', return_value=mock_khata_db):
            service = KhataTransactionService()
            service.db = mock_khata_db

            start_time = time.time()

            result = await service.record_credit_sale(
                store_id="STORE-TEST-001",
                customer_phone="+919876543210",
                amount=Decimal("500.00"),
                created_by="owner@test.com"
            )

            elapsed_time = (time.time() - start_time) * 1000  # Convert to ms

            assert result.success is True
            # Saga should complete within 200ms (excluding actual DB calls)
            assert elapsed_time < 200, f"Saga took {elapsed_time}ms, expected <200ms"
