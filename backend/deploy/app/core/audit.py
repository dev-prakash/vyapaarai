"""
Audit Logging Module for VyaparAI

Provides structured audit logging for security-sensitive operations:
- Authentication events (login, logout, OTP requests)
- Authorization events (access denied, privilege escalation)
- Data modifications (create, update, delete)
- API access patterns

Logs are structured for easy parsing and analysis.
"""

import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from fastapi import Request
import hashlib

# Configure audit logger
audit_logger = logging.getLogger("vyaparai.audit")
audit_logger.setLevel(logging.INFO)

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class AuditEventType(str, Enum):
    """Types of audit events"""
    # Authentication events
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_OTP_SEND = "auth.otp.send"
    AUTH_OTP_VERIFY_SUCCESS = "auth.otp.verify.success"
    AUTH_OTP_VERIFY_FAILURE = "auth.otp.verify.failure"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_TOKEN_EXPIRED = "auth.token.expired"
    AUTH_REGISTER = "auth.register"

    # Authorization events
    AUTHZ_ACCESS_DENIED = "authz.access.denied"
    AUTHZ_PRIVILEGE_ESCALATION = "authz.privilege.escalation"
    AUTHZ_ROLE_CHANGE = "authz.role.change"

    # Data events
    DATA_CREATE = "data.create"
    DATA_READ = "data.read"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"

    # Security events
    SECURITY_RATE_LIMIT = "security.rate_limit"
    SECURITY_INJECTION_ATTEMPT = "security.injection_attempt"
    SECURITY_SUSPICIOUS_ACTIVITY = "security.suspicious_activity"

    # Order events
    ORDER_CREATE = "order.create"
    ORDER_UPDATE = "order.update"
    ORDER_CANCEL = "order.cancel"
    ORDER_COMPLETE = "order.complete"

    # Inventory events
    INVENTORY_UPDATE = "inventory.update"
    INVENTORY_LOW_STOCK = "inventory.low_stock"


class AuditSeverity(str, Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data in audit logs.

    Args:
        data: Data dictionary to mask

    Returns:
        Dictionary with sensitive fields masked
    """
    if not data:
        return data

    sensitive_fields = {
        "password", "password_hash", "otp", "token", "access_token",
        "refresh_token", "secret", "api_key", "aadhaar_number",
        "card_number", "cvv", "pin"
    }

    masked = {}
    for key, value in data.items():
        if key.lower() in sensitive_fields:
            if isinstance(value, str) and len(value) > 4:
                masked[key] = f"***{value[-4:]}"
            else:
                masked[key] = "****"
        elif key.lower() == "phone" and isinstance(value, str) and len(value) > 4:
            # Show last 4 digits of phone
            masked[key] = f"***{value[-4:]}"
        elif key.lower() == "email" and isinstance(value, str) and "@" in value:
            # Partially mask email
            parts = value.split("@")
            if len(parts[0]) > 2:
                masked[key] = f"{parts[0][:2]}***@{parts[1]}"
            else:
                masked[key] = f"***@{parts[1]}"
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_data(value)
        else:
            masked[key] = value

    return masked


def get_client_info(request: Optional[Request]) -> Dict[str, Any]:
    """
    Extract client information from request.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary with client information
    """
    if not request:
        return {}

    client_ip = None
    if request.client:
        client_ip = request.client.host

    # Check for forwarded headers (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        client_ip = real_ip

    return {
        "ip_address": client_ip,
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "path": str(request.url.path),
        "method": request.method,
        "request_id": request.headers.get("X-Request-ID"),
    }


def create_audit_log(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    user_id: Optional[str] = None,
    store_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    success: bool = True,
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a structured audit log entry.

    Args:
        event_type: Type of audit event
        severity: Severity level
        user_id: ID of the user performing the action
        store_id: ID of the store (if applicable)
        resource_type: Type of resource being accessed/modified
        resource_id: ID of the resource
        action: Specific action performed
        details: Additional details (will be masked)
        request: FastAPI request object
        success: Whether the operation succeeded
        error_message: Error message if operation failed

    Returns:
        Structured audit log dictionary
    """
    timestamp = datetime.utcnow().isoformat() + "Z"

    audit_entry = {
        "timestamp": timestamp,
        "event_type": event_type.value,
        "severity": severity.value,
        "environment": ENVIRONMENT,
        "success": success,
    }

    if user_id:
        audit_entry["user_id"] = user_id

    if store_id:
        audit_entry["store_id"] = store_id

    if resource_type:
        audit_entry["resource"] = {
            "type": resource_type,
            "id": resource_id
        }

    if action:
        audit_entry["action"] = action

    if details:
        audit_entry["details"] = mask_sensitive_data(details)

    if error_message:
        audit_entry["error"] = error_message

    if request:
        audit_entry["client"] = get_client_info(request)

    return audit_entry


def log_audit_event(
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    user_id: Optional[str] = None,
    store_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    success: bool = True,
    error_message: Optional[str] = None
) -> None:
    """
    Log an audit event.

    Args:
        Same as create_audit_log
    """
    audit_entry = create_audit_log(
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        store_id=store_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details,
        request=request,
        success=success,
        error_message=error_message
    )

    # Log as JSON for easy parsing
    log_message = json.dumps(audit_entry, default=str)

    # Use appropriate log level based on severity
    if severity == AuditSeverity.CRITICAL:
        audit_logger.critical(log_message)
    elif severity == AuditSeverity.ERROR:
        audit_logger.error(log_message)
    elif severity == AuditSeverity.WARNING:
        audit_logger.warning(log_message)
    else:
        audit_logger.info(log_message)


# =============================================================================
# Convenience functions for common audit events
# =============================================================================

def log_auth_success(
    user_id: str,
    auth_method: str,
    request: Optional[Request] = None,
    store_id: Optional[str] = None
) -> None:
    """Log successful authentication"""
    log_audit_event(
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        store_id=store_id,
        action="login",
        details={"auth_method": auth_method},
        request=request,
        success=True
    )


def log_auth_failure(
    identifier: str,
    auth_method: str,
    reason: str,
    request: Optional[Request] = None
) -> None:
    """Log failed authentication"""
    log_audit_event(
        event_type=AuditEventType.AUTH_LOGIN_FAILURE,
        severity=AuditSeverity.WARNING,
        action="login",
        details={"auth_method": auth_method, "identifier": identifier},
        request=request,
        success=False,
        error_message=reason
    )


def log_otp_send(
    phone: str,
    request: Optional[Request] = None
) -> None:
    """Log OTP send request"""
    log_audit_event(
        event_type=AuditEventType.AUTH_OTP_SEND,
        severity=AuditSeverity.INFO,
        action="otp_send",
        details={"phone": phone},
        request=request,
        success=True
    )


def log_otp_verify(
    phone: str,
    success: bool,
    request: Optional[Request] = None,
    error: Optional[str] = None
) -> None:
    """Log OTP verification attempt"""
    log_audit_event(
        event_type=AuditEventType.AUTH_OTP_VERIFY_SUCCESS if success else AuditEventType.AUTH_OTP_VERIFY_FAILURE,
        severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
        action="otp_verify",
        details={"phone": phone},
        request=request,
        success=success,
        error_message=error
    )


def log_access_denied(
    user_id: Optional[str],
    resource_type: str,
    resource_id: str,
    required_role: str,
    request: Optional[Request] = None
) -> None:
    """Log access denied event"""
    log_audit_event(
        event_type=AuditEventType.AUTHZ_ACCESS_DENIED,
        severity=AuditSeverity.WARNING,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action="access_denied",
        details={"required_role": required_role},
        request=request,
        success=False,
        error_message="Access denied: insufficient permissions"
    )


def log_data_modification(
    event_type: AuditEventType,
    user_id: str,
    resource_type: str,
    resource_id: str,
    changes: Optional[Dict[str, Any]] = None,
    store_id: Optional[str] = None,
    request: Optional[Request] = None
) -> None:
    """Log data modification event"""
    log_audit_event(
        event_type=event_type,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        store_id=store_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=event_type.value.split(".")[-1],
        details={"changes": changes} if changes else None,
        request=request,
        success=True
    )


def log_security_event(
    event_type: AuditEventType,
    description: str,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> None:
    """Log security-related event"""
    log_audit_event(
        event_type=event_type,
        severity=AuditSeverity.WARNING,
        action="security_alert",
        details=details,
        request=request,
        success=False,
        error_message=description
    )


def log_rate_limit_exceeded(
    identifier: str,
    limit_type: str,
    request: Optional[Request] = None
) -> None:
    """Log rate limit exceeded event"""
    log_audit_event(
        event_type=AuditEventType.SECURITY_RATE_LIMIT,
        severity=AuditSeverity.WARNING,
        action="rate_limit_exceeded",
        details={"identifier": identifier, "limit_type": limit_type},
        request=request,
        success=False,
        error_message="Rate limit exceeded"
    )


def log_order_event(
    event_type: AuditEventType,
    user_id: str,
    order_id: str,
    store_id: str,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None
) -> None:
    """Log order-related event"""
    log_audit_event(
        event_type=event_type,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        store_id=store_id,
        resource_type="order",
        resource_id=order_id,
        action=event_type.value.split(".")[-1],
        details=details,
        request=request,
        success=True
    )
