"""
Cart Migration Metrics and Structured Logging
Provides CloudWatch-compatible structured logging and custom metrics publishing
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MigrationStatus(Enum):
    """Migration status enum"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    NO_CARTS = "no_carts"
    RATE_LIMITED = "rate_limited"


class MergeStrategy(Enum):
    """Merge strategy enum"""
    MERGE = "merge"
    REPLACE = "replace"
    KEEP_NEWEST = "keep_newest"


class CartMigrationMetrics:
    """
    Handles structured logging and metrics for cart migration.
    Designed for CloudWatch Logs and CloudWatch Metrics integration.
    """

    @staticmethod
    def _log_structured(
        level: str,
        message: str,
        **kwargs
    ):
        """
        Log structured data in JSON format for CloudWatch

        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
            **kwargs: Additional structured data
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }

        # Log as JSON for structured CloudWatch parsing
        log_line = json.dumps(log_data, default=str)

        if level == "INFO":
            logger.info(log_line)
        elif level == "WARNING":
            logger.warning(log_line)
        elif level == "ERROR":
            logger.error(log_line)
        else:
            logger.debug(log_line)

    @classmethod
    def log_migration_start(
        cls,
        customer_id: str,
        guest_session_id: str,
        merge_strategy: str,
        store_id: Optional[str] = None
    ):
        """Log start of cart migration"""
        cls._log_structured(
            "INFO",
            "Cart migration started",
            event_type="migration_start",
            customer_id=customer_id,
            guest_session_id=guest_session_id,
            merge_strategy=merge_strategy,
            store_id=store_id,
            migration_type="single_store" if store_id else "all_stores"
        )

    @classmethod
    def log_migration_success(
        cls,
        customer_id: str,
        guest_session_id: str,
        migrated_carts: int,
        total_items: int,
        total_value: float,
        merge_strategy: str,
        duration_ms: float
    ):
        """Log successful cart migration"""
        cls._log_structured(
            "INFO",
            "Cart migration successful",
            event_type="migration_success",
            customer_id=customer_id,
            guest_session_id=guest_session_id,
            migrated_carts=migrated_carts,
            total_items=total_items,
            total_value=total_value,
            merge_strategy=merge_strategy,
            duration_ms=duration_ms,
            status=MigrationStatus.SUCCESS.value
        )

    @classmethod
    def log_migration_failure(
        cls,
        customer_id: str,
        guest_session_id: str,
        error_message: str,
        error_type: str,
        merge_strategy: str
    ):
        """Log failed cart migration"""
        cls._log_structured(
            "ERROR",
            "Cart migration failed",
            event_type="migration_failure",
            customer_id=customer_id,
            guest_session_id=guest_session_id,
            error_message=error_message,
            error_type=error_type,
            merge_strategy=merge_strategy,
            status=MigrationStatus.FAILURE.value
        )

    @classmethod
    def log_no_guest_carts(
        cls,
        customer_id: str,
        guest_session_id: str,
        store_id: Optional[str] = None
    ):
        """Log when no guest carts are found"""
        cls._log_structured(
            "INFO",
            "No guest carts found for migration",
            event_type="no_guest_carts",
            customer_id=customer_id,
            guest_session_id=guest_session_id,
            store_id=store_id,
            status=MigrationStatus.NO_CARTS.value
        )

    @classmethod
    def log_merge_conflict(
        cls,
        customer_id: str,
        store_id: str,
        merge_strategy: str,
        conflict_type: str,
        resolution: str
    ):
        """Log cart merge conflict resolution"""
        cls._log_structured(
            "INFO",
            "Cart merge conflict resolved",
            event_type="merge_conflict",
            customer_id=customer_id,
            store_id=store_id,
            merge_strategy=merge_strategy,
            conflict_type=conflict_type,
            resolution=resolution
        )

    @classmethod
    def log_rate_limit_exceeded(
        cls,
        customer_id: str,
        ip_address: str,
        endpoint: str
    ):
        """Log rate limit exceeded event"""
        cls._log_structured(
            "WARNING",
            "Rate limit exceeded for cart migration",
            event_type="rate_limit_exceeded",
            customer_id=customer_id,
            ip_address=ip_address,
            endpoint=endpoint,
            status=MigrationStatus.RATE_LIMITED.value
        )

    @classmethod
    def log_cleanup_success(
        cls,
        customer_id: str,
        guest_session_id: str,
        carts_deleted: int
    ):
        """Log successful guest cart cleanup"""
        cls._log_structured(
            "INFO",
            "Guest cart cleanup successful",
            event_type="cleanup_success",
            customer_id=customer_id,
            guest_session_id=guest_session_id,
            carts_deleted=carts_deleted
        )

    @classmethod
    def log_store_cart_migrated(
        cls,
        customer_id: str,
        store_id: str,
        items_count: int,
        cart_total: float,
        merge_strategy: str,
        had_conflict: bool
    ):
        """Log individual store cart migration"""
        cls._log_structured(
            "INFO",
            "Store cart migrated",
            event_type="store_cart_migrated",
            customer_id=customer_id,
            store_id=store_id,
            items_count=items_count,
            cart_total=cart_total,
            merge_strategy=merge_strategy,
            had_conflict=had_conflict
        )

    @classmethod
    def log_authentication_failure(
        cls,
        reason: str,
        token_expired: bool = False
    ):
        """Log authentication failure"""
        cls._log_structured(
            "WARNING",
            "Cart migration authentication failed",
            event_type="auth_failure",
            reason=reason,
            token_expired=token_expired
        )

    @classmethod
    def log_validation_error(
        cls,
        error_field: str,
        error_message: str,
        provided_value: Any
    ):
        """Log validation error"""
        cls._log_structured(
            "WARNING",
            "Cart migration validation error",
            event_type="validation_error",
            error_field=error_field,
            error_message=error_message,
            provided_value=str(provided_value)
        )

    @classmethod
    def log_dynamo_error(
        cls,
        operation: str,
        error_code: str,
        error_message: str,
        table_name: str
    ):
        """Log DynamoDB operation error"""
        cls._log_structured(
            "ERROR",
            "DynamoDB operation failed",
            event_type="dynamo_error",
            operation=operation,
            error_code=error_code,
            error_message=error_message,
            table_name=table_name
        )

    @classmethod
    def log_performance_metric(
        cls,
        operation: str,
        duration_ms: float,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log performance metric"""
        cls._log_structured(
            "INFO",
            f"Performance metric for {operation}",
            event_type="performance_metric",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            **(metadata or {})
        )

    @classmethod
    def create_audit_log(
        cls,
        customer_id: str,
        action: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None
    ):
        """Create audit log entry for compliance"""
        cls._log_structured(
            "INFO",
            "Cart migration audit log",
            event_type="audit_log",
            customer_id=customer_id,
            action=action,
            details=details,
            ip_address=ip_address,
            audit_timestamp=datetime.utcnow().isoformat()
        )


# Convenience function for backward compatibility
def log_migration_event(event_type: str, **kwargs):
    """
    Generic migration event logging

    Args:
        event_type: Type of event
        **kwargs: Event data
    """
    CartMigrationMetrics._log_structured("INFO", f"Migration event: {event_type}", event_type=event_type, **kwargs)
