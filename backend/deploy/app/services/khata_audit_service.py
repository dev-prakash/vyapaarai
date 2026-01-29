"""
Khata Audit Service

Provides comprehensive audit logging for all credit management operations.
Essential for:
- Regulatory compliance (7-year retention for financial records)
- Dispute resolution
- Fraud detection
- Anomaly monitoring

All Khata transactions are immutably logged with full context for traceability.
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime
import asyncio
import os

logger = logging.getLogger(__name__)

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"


@dataclass
class AuditEntry:
    """Immutable audit log entry"""
    audit_id: str
    timestamp: str
    action: str  # credit_sale, payment, adjustment, reversal, balance_update
    actor_id: str  # User who performed the action
    actor_type: str  # store_owner, staff, admin, system
    store_id: str
    customer_phone: str
    transaction_id: Optional[str]
    # Financial details
    amount: Optional[Decimal]
    balance_before: Optional[Decimal]
    balance_after: Optional[Decimal]
    # Context
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]
    idempotency_key: Optional[str]
    # Additional details
    details: Dict[str, Any]
    # Integrity
    checksum: str  # SHA-256 hash for tamper detection


class KhataAuditService:
    """
    Audit logging service for Khata operations

    Features:
    - Immutable audit trail
    - Checksum for tamper detection
    - Real-time anomaly alerts
    - Compliance-ready retention
    """

    # Anomaly thresholds
    LARGE_BALANCE_CHANGE_THRESHOLD = 0.5  # 50% change is suspicious
    HIGH_VALUE_TRANSACTION_THRESHOLD = Decimal("50000")  # ₹50,000
    MAX_TRANSACTIONS_PER_HOUR = 100  # Per customer

    def __init__(self):
        """Initialize audit service"""
        self._transaction_counts: Dict[str, int] = {}  # For rate monitoring
        self._last_reset = datetime.utcnow()

    def _generate_checksum(self, data: Dict[str, Any]) -> str:
        """
        Generate SHA-256 checksum for audit entry

        Ensures data integrity and tamper detection.

        Args:
            data: Audit entry data

        Returns:
            Hex string of SHA-256 hash
        """
        # Create deterministic JSON string
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    async def log_transaction(
        self,
        action: str,
        actor_id: str,
        actor_type: str,
        store_id: str,
        customer_phone: str,
        transaction_id: str,
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> str:
        """
        Log a financial transaction to audit trail

        Args:
            action: Type of action performed
            actor_id: User ID who performed action
            actor_type: Type of user (store_owner, staff, admin, system)
            store_id: Store identifier
            customer_phone: Customer phone number
            transaction_id: Transaction identifier
            amount: Transaction amount
            balance_before: Balance before transaction
            balance_after: Balance after transaction
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            idempotency_key: Idempotency key used
            details: Additional context

        Returns:
            Audit ID for reference
        """
        timestamp = datetime.utcnow().isoformat()
        audit_id = f"AUD-{transaction_id}"

        # Prepare audit data (without checksum)
        audit_data = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "action": action,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "store_id": store_id,
            "customer_phone": customer_phone,
            "transaction_id": transaction_id,
            "amount": str(amount),
            "balance_before": str(balance_before),
            "balance_after": str(balance_after),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "details": details or {}
        }

        # Generate checksum
        checksum = self._generate_checksum(audit_data)
        audit_data["checksum"] = checksum

        # Log to structured logging (CloudWatch in production)
        logger.info(
            "KHATA_AUDIT",
            extra={
                "audit_entry": audit_data,
                "category": "khata_audit"
            }
        )

        # Check for anomalies
        await self._check_anomalies(
            action=action,
            customer_phone=customer_phone,
            store_id=store_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            audit_id=audit_id
        )

        return audit_id

    async def log_balance_query(
        self,
        actor_id: str,
        actor_type: str,
        store_id: str,
        customer_phone: str,
        balance: Decimal,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        """
        Log balance query for access tracking

        Important for compliance - tracks who viewed customer data.

        Args:
            actor_id: User who queried
            actor_type: Type of user
            store_id: Store identifier
            customer_phone: Customer whose balance was viewed
            balance: Balance at time of query
            ip_address: Client IP
            request_id: Request correlation ID

        Returns:
            Audit ID
        """
        timestamp = datetime.utcnow().isoformat()
        audit_id = f"AUD-QUERY-{timestamp.replace(':', '').replace('-', '')}"

        audit_data = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "action": "balance_query",
            "actor_id": actor_id,
            "actor_type": actor_type,
            "store_id": store_id,
            "customer_phone": customer_phone,
            "balance_viewed": str(balance),
            "ip_address": ip_address,
            "request_id": request_id
        }

        checksum = self._generate_checksum(audit_data)
        audit_data["checksum"] = checksum

        logger.info(
            "KHATA_ACCESS_AUDIT",
            extra={
                "audit_entry": audit_data,
                "category": "khata_access"
            }
        )

        return audit_id

    async def log_credit_limit_change(
        self,
        actor_id: str,
        actor_type: str,
        store_id: str,
        customer_phone: str,
        old_limit: Decimal,
        new_limit: Decimal,
        reason: str,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        """
        Log credit limit changes

        Important for tracking risk exposure changes.

        Args:
            actor_id: User making change
            actor_type: Type of user
            store_id: Store identifier
            customer_phone: Customer phone
            old_limit: Previous credit limit
            new_limit: New credit limit
            reason: Reason for change
            ip_address: Client IP
            request_id: Request correlation ID

        Returns:
            Audit ID
        """
        timestamp = datetime.utcnow().isoformat()
        audit_id = f"AUD-LIMIT-{timestamp.replace(':', '').replace('-', '')}"

        change_pct = ((new_limit - old_limit) / old_limit * 100) if old_limit > 0 else 100

        audit_data = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "action": "credit_limit_change",
            "actor_id": actor_id,
            "actor_type": actor_type,
            "store_id": store_id,
            "customer_phone": customer_phone,
            "old_limit": str(old_limit),
            "new_limit": str(new_limit),
            "change_percentage": f"{change_pct:.2f}",
            "reason": reason,
            "ip_address": ip_address,
            "request_id": request_id
        }

        checksum = self._generate_checksum(audit_data)
        audit_data["checksum"] = checksum

        logger.info(
            "KHATA_LIMIT_CHANGE",
            extra={
                "audit_entry": audit_data,
                "category": "khata_limit"
            }
        )

        # Alert for large limit increases
        if change_pct > 100:  # More than doubling
            await self._alert_large_limit_increase(
                store_id=store_id,
                customer_phone=customer_phone,
                old_limit=old_limit,
                new_limit=new_limit,
                actor_id=actor_id,
                audit_id=audit_id
            )

        return audit_id

    async def log_reminder_event(
        self,
        event_type: str,  # scheduled, sent, failed, cancelled
        store_id: str,
        customer_phone: str,
        reminder_id: str,
        outstanding_amount: Decimal,
        channel: str,  # sms, push
        details: Optional[Dict] = None
    ) -> str:
        """
        Log payment reminder events

        Tracks reminder lifecycle for compliance and debugging.

        Args:
            event_type: Type of reminder event
            store_id: Store identifier
            customer_phone: Customer phone
            reminder_id: Reminder identifier
            outstanding_amount: Amount being reminded
            channel: Delivery channel
            details: Additional details

        Returns:
            Audit ID
        """
        timestamp = datetime.utcnow().isoformat()
        audit_id = f"AUD-REM-{reminder_id}"

        audit_data = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "action": f"reminder_{event_type}",
            "store_id": store_id,
            "customer_phone": customer_phone,
            "reminder_id": reminder_id,
            "outstanding_amount": str(outstanding_amount),
            "channel": channel,
            "details": details or {}
        }

        checksum = self._generate_checksum(audit_data)
        audit_data["checksum"] = checksum

        logger.info(
            "KHATA_REMINDER_AUDIT",
            extra={
                "audit_entry": audit_data,
                "category": "khata_reminder"
            }
        )

        return audit_id

    async def log_failed_operation(
        self,
        operation: str,
        store_id: str,
        customer_phone: str,
        error_code: str,
        error_message: str,
        actor_id: Optional[str] = None,
        request_data: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        """
        Log failed operations for debugging and security

        Important for identifying attack patterns and bugs.

        Args:
            operation: Operation that failed
            store_id: Store identifier
            customer_phone: Customer phone
            error_code: Error code
            error_message: Error description
            actor_id: User who attempted operation
            request_data: Sanitized request data
            ip_address: Client IP
            request_id: Request correlation ID

        Returns:
            Audit ID
        """
        timestamp = datetime.utcnow().isoformat()
        audit_id = f"AUD-FAIL-{timestamp.replace(':', '').replace('-', '')}"

        audit_data = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "action": "operation_failed",
            "operation": operation,
            "store_id": store_id,
            "customer_phone": customer_phone,
            "actor_id": actor_id,
            "error_code": error_code,
            "error_message": error_message,
            "request_data": request_data,
            "ip_address": ip_address,
            "request_id": request_id
        }

        checksum = self._generate_checksum(audit_data)
        audit_data["checksum"] = checksum

        logger.warning(
            "KHATA_OPERATION_FAILED",
            extra={
                "audit_entry": audit_data,
                "category": "khata_failure"
            }
        )

        return audit_id

    async def _check_anomalies(
        self,
        action: str,
        customer_phone: str,
        store_id: str,
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        audit_id: str
    ):
        """
        Check for anomalous patterns in transactions

        Alerts for:
        - Large balance changes (>50%)
        - High value transactions
        - Unusual transaction frequency

        Args:
            action: Type of action
            customer_phone: Customer phone
            store_id: Store identifier
            amount: Transaction amount
            balance_before: Previous balance
            balance_after: New balance
            audit_id: Audit ID for reference
        """
        alerts = []

        # Check for large balance change
        if balance_before > 0:
            change_pct = abs(
                (balance_after - balance_before) / balance_before
            )
            if change_pct > self.LARGE_BALANCE_CHANGE_THRESHOLD:
                alerts.append({
                    "type": "large_balance_change",
                    "severity": "warning",
                    "message": f"Balance changed by {change_pct * 100:.1f}%",
                    "details": {
                        "balance_before": str(balance_before),
                        "balance_after": str(balance_after),
                        "change_percentage": f"{change_pct * 100:.1f}"
                    }
                })

        # Check for high value transaction
        if amount > self.HIGH_VALUE_TRANSACTION_THRESHOLD:
            alerts.append({
                "type": "high_value_transaction",
                "severity": "info",
                "message": f"High value transaction: ₹{amount}",
                "details": {
                    "amount": str(amount),
                    "threshold": str(self.HIGH_VALUE_TRANSACTION_THRESHOLD)
                }
            })

        # Check transaction frequency
        customer_key = f"{store_id}:{customer_phone}"
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        if self._last_reset.replace(minute=0, second=0, microsecond=0) != current_hour:
            self._transaction_counts = {}
            self._last_reset = datetime.utcnow()

        self._transaction_counts[customer_key] = self._transaction_counts.get(customer_key, 0) + 1

        if self._transaction_counts[customer_key] > self.MAX_TRANSACTIONS_PER_HOUR:
            alerts.append({
                "type": "high_transaction_frequency",
                "severity": "warning",
                "message": f"Unusual transaction frequency: {self._transaction_counts[customer_key]}/hour",
                "details": {
                    "count": self._transaction_counts[customer_key],
                    "threshold": self.MAX_TRANSACTIONS_PER_HOUR
                }
            })

        # Log alerts
        for alert in alerts:
            logger.warning(
                f"KHATA_ANOMALY_DETECTED: {alert['type']}",
                extra={
                    "anomaly": alert,
                    "audit_id": audit_id,
                    "store_id": store_id,
                    "customer_phone": customer_phone,
                    "category": "khata_anomaly"
                }
            )

    async def _alert_large_limit_increase(
        self,
        store_id: str,
        customer_phone: str,
        old_limit: Decimal,
        new_limit: Decimal,
        actor_id: str,
        audit_id: str
    ):
        """
        Alert for large credit limit increases

        In production, this would send alerts to:
        - Operations dashboard
        - Slack/PagerDuty
        - Email to risk team
        """
        logger.warning(
            "KHATA_LARGE_LIMIT_INCREASE",
            extra={
                "alert_type": "large_limit_increase",
                "store_id": store_id,
                "customer_phone": customer_phone,
                "old_limit": str(old_limit),
                "new_limit": str(new_limit),
                "increase_factor": float(new_limit / old_limit) if old_limit > 0 else None,
                "actor_id": actor_id,
                "audit_id": audit_id,
                "category": "khata_risk_alert"
            }
        )

        # TODO: In production, integrate with:
        # - SNS topic for alerts
        # - CloudWatch alarm
        # - Slack webhook

    async def get_transaction_audit_trail(
        self,
        transaction_id: str
    ) -> Dict[str, Any]:
        """
        Get complete audit trail for a transaction

        Useful for dispute resolution and investigation.

        Args:
            transaction_id: Transaction to look up

        Returns:
            Audit trail data (in production, would query from audit storage)
        """
        # In production, this would query from:
        # - CloudWatch Logs Insights
        # - S3 audit archive
        # - DynamoDB audit table

        logger.info(
            f"Audit trail requested for transaction: {transaction_id}",
            extra={
                "action": "audit_trail_query",
                "transaction_id": transaction_id
            }
        )

        return {
            "transaction_id": transaction_id,
            "message": "Audit trail query - implement with CloudWatch Logs Insights in production"
        }

    async def get_customer_activity(
        self,
        store_id: str,
        customer_phone: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get customer activity summary

        Useful for risk assessment and customer review.

        Args:
            store_id: Store identifier
            customer_phone: Customer phone
            days: Number of days to look back

        Returns:
            Activity summary
        """
        logger.info(
            f"Customer activity requested for {customer_phone} at store {store_id}",
            extra={
                "action": "customer_activity_query",
                "store_id": store_id,
                "customer_phone": customer_phone,
                "days": days
            }
        )

        return {
            "store_id": store_id,
            "customer_phone": customer_phone,
            "period_days": days,
            "message": "Activity summary - implement with CloudWatch Logs Insights in production"
        }


# =============================================================================
# Global Instance
# =============================================================================

khata_audit_service = KhataAuditService()


# =============================================================================
# Convenience Functions
# =============================================================================

async def log_khata_transaction(
    action: str,
    actor_id: str,
    store_id: str,
    customer_phone: str,
    transaction_id: str,
    amount: Decimal,
    balance_before: Decimal,
    balance_after: Decimal,
    **kwargs
) -> str:
    """
    Convenience function to log Khata transactions

    Args:
        action: Type of action
        actor_id: User ID
        store_id: Store ID
        customer_phone: Customer phone
        transaction_id: Transaction ID
        amount: Amount
        balance_before: Balance before
        balance_after: Balance after
        **kwargs: Additional parameters

    Returns:
        Audit ID
    """
    return await khata_audit_service.log_transaction(
        action=action,
        actor_id=actor_id,
        actor_type=kwargs.get("actor_type", "store_owner"),
        store_id=store_id,
        customer_phone=customer_phone,
        transaction_id=transaction_id,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        ip_address=kwargs.get("ip_address"),
        user_agent=kwargs.get("user_agent"),
        request_id=kwargs.get("request_id"),
        idempotency_key=kwargs.get("idempotency_key"),
        details=kwargs.get("details")
    )
