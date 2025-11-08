"""
Data Privacy and Security Module
Implements encryption, masking, and access control for sensitive data
"""

import hashlib
import base64
import json
import re
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import os

class DataPrivacyManager:
    """Manages data privacy and security for VyaparAI"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize with encryption key"""
        self.encryption_key = encryption_key or os.getenv('ENCRYPTION_KEY')
        if self.encryption_key:
            self.cipher = self._create_cipher(self.encryption_key)
        else:
            self.cipher = None
    
    def _create_cipher(self, key: str) -> Fernet:
        """Create Fernet cipher from key"""
        # Ensure key is 32 bytes
        key_bytes = key.encode()[:32].ljust(32, b'0')
        encoded_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(encoded_key)
    
    # ============================================
    # PII ENCRYPTION
    # ============================================
    
    def encrypt_pii(self, data: str) -> str:
        """Encrypt personally identifiable information"""
        if not self.cipher:
            return data  # Return as-is if encryption not configured
        
        try:
            encrypted = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception:
            return data  # Fallback to unencrypted
    
    def decrypt_pii(self, encrypted_data: str) -> str:
        """Decrypt personally identifiable information"""
        if not self.cipher:
            return encrypted_data
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception:
            return encrypted_data  # Return as-is if decryption fails
    
    # ============================================
    # DATA MASKING
    # ============================================
    
    def mask_phone_number(self, phone: str) -> str:
        """Mask phone number for display (show only last 4 digits)"""
        if len(phone) <= 4:
            return phone
        return 'X' * (len(phone) - 4) + phone[-4:]
    
    def mask_email(self, email: str) -> str:
        """Mask email address for display"""
        if '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 3:
            masked_local = 'X' * len(local)
        else:
            masked_local = local[0] + 'X' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    def mask_address(self, address: str) -> str:
        """Mask address keeping only city/area"""
        # Keep only first few words and last word (usually city)
        words = address.split()
        if len(words) <= 3:
            return address
        
        return f"{words[0]} ... {words[-1]}"
    
    def mask_name(self, name: str) -> str:
        """Mask name showing only initials"""
        words = name.split()
        return ' '.join([w[0] + '*' * (len(w) - 1) for w in words if w])
    
    # ============================================
    # STORE DATA ISOLATION
    # ============================================
    
    def filter_by_store_id(self, data: List[Dict], store_id: str) -> List[Dict]:
        """Filter data to only include items for specific store"""
        return [item for item in data if item.get('store_id') == store_id]
    
    def validate_store_access(self, user_store_id: str, requested_store_id: str) -> bool:
        """Validate if user has access to requested store data"""
        return user_store_id == requested_store_id
    
    # ============================================
    # SENSITIVE DATA HANDLING
    # ============================================
    
    def sanitize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data before logging"""
        sensitive_fields = [
            'password', 'token', 'secret', 'key', 'credit_card',
            'cvv', 'ssn', 'pan', 'aadhaar', 'bank_account'
        ]
        
        sanitized = data.copy()
        for key in list(sanitized.keys()):
            # Check if key contains sensitive terms
            if any(term in key.lower() for term in sensitive_fields):
                sanitized[key] = '[REDACTED]'
            # Mask specific fields
            elif key in ['phone', 'mobile']:
                sanitized[key] = self.mask_phone_number(str(sanitized[key]))
            elif key in ['email']:
                sanitized[key] = self.mask_email(str(sanitized[key]))
            elif key in ['address']:
                sanitized[key] = self.mask_address(str(sanitized[key]))
        
        return sanitized
    
    def hash_sensitive_id(self, id_value: str, salt: str = '') -> str:
        """Create one-way hash of sensitive IDs"""
        combined = f"{id_value}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    # ============================================
    # CUSTOMER DATA PROTECTION
    # ============================================
    
    def anonymize_customer_data(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize customer data for analytics"""
        anonymized = customer.copy()
        
        # Replace identifiable fields
        if 'name' in anonymized:
            anonymized['name'] = f"Customer_{self.hash_sensitive_id(str(customer.get('id', '')))[:8]}"
        if 'phone' in anonymized:
            anonymized['phone'] = self.mask_phone_number(anonymized['phone'])
        if 'email' in anonymized:
            anonymized['email'] = self.mask_email(anonymized['email'])
        if 'address' in anonymized:
            anonymized['address'] = 'Address Hidden'
        
        return anonymized
    
    def get_customer_consent_status(self, customer_id: str) -> Dict[str, bool]:
        """Get customer's data consent preferences"""
        # This would typically query a consent management table
        return {
            'marketing': False,  # Default to no marketing
            'analytics': True,   # Default to analytics allowed
            'third_party': False # Default to no third-party sharing
        }
    
    # ============================================
    # COMPLIANCE HELPERS
    # ============================================
    
    def prepare_gdpr_export(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare customer data for GDPR export request"""
        export_data = {
            'personal_data': {
                'name': customer_data.get('name'),
                'email': customer_data.get('email'),
                'phone': customer_data.get('phone'),
                'address': customer_data.get('address')
            },
            'order_history': customer_data.get('orders', []),
            'preferences': customer_data.get('preferences', {}),
            'consent_history': customer_data.get('consent_history', []),
            'data_collection_date': customer_data.get('created_at'),
            'last_updated': customer_data.get('updated_at')
        }
        return export_data
    
    def redact_for_deletion(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Redact personal data for soft deletion (compliance)"""
        redacted = record.copy()
        
        # Redact PII fields
        pii_fields = ['name', 'email', 'phone', 'address', 'pan', 'aadhaar', 'gstin']
        for field in pii_fields:
            if field in redacted:
                redacted[field] = f"[DELETED_{self.hash_sensitive_id(str(record.get('id', '')))[:8]}]"
        
        redacted['deleted_at'] = datetime.now().isoformat()
        redacted['deletion_reason'] = 'User requested deletion'
        
        return redacted


class AccessControlManager:
    """Manages role-based access control"""
    
    # Define permissions for each role
    PERMISSIONS = {
        'customer': [
            'view_own_orders',
            'create_order',
            'view_products',
            'update_own_profile'
        ],
        'store_staff': [
            'view_store_orders',
            'update_order_status',
            'view_inventory',
            'update_stock'
        ],
        'store_owner': [
            'view_store_orders',
            'update_order_status',
            'view_inventory',
            'update_stock',
            'manage_products',
            'view_analytics',
            'manage_staff',
            'update_store_settings'
        ],
        'admin': [
            'all'  # Full access
        ]
    }
    
    @classmethod
    def has_permission(cls, user_role: str, action: str) -> bool:
        """Check if role has permission for action"""
        if user_role not in cls.PERMISSIONS:
            return False
        
        permissions = cls.PERMISSIONS[user_role]
        return 'all' in permissions or action in permissions
    
    @classmethod
    def filter_response_fields(cls, data: Dict[str, Any], user_role: str) -> Dict[str, Any]:
        """Filter response data based on user role"""
        # Define fields visible to each role
        visible_fields = {
            'customer': ['order_id', 'status', 'total', 'items', 'delivery_date'],
            'store_staff': ['order_id', 'status', 'total', 'items', 'customer_name', 'phone', 'address'],
            'store_owner': None,  # All fields
            'admin': None  # All fields
        }
        
        fields = visible_fields.get(user_role)
        if fields is None:
            return data  # Return all fields
        
        # Filter to only visible fields
        return {k: v for k, v in data.items() if k in fields}


class AuditLogger:
    """Audit logging for compliance and security"""
    
    def __init__(self):
        self.privacy_manager = DataPrivacyManager()
    
    def log_data_access(self, user_id: str, resource: str, action: str, 
                       details: Optional[Dict] = None) -> Dict[str, Any]:
        """Log data access for audit trail"""
        from datetime import datetime
        
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'ip_address': details.get('ip_address') if details else None,
            'user_agent': details.get('user_agent') if details else None,
            'success': details.get('success', True) if details else True
        }
        
        # Sanitize any sensitive data in details
        if details:
            audit_entry['details'] = self.privacy_manager.sanitize_for_logging(details)
        
        # This would typically write to an audit log table
        return audit_entry
    
    def log_consent_change(self, customer_id: str, consent_type: str, 
                          granted: bool, ip_address: str = None) -> Dict[str, Any]:
        """Log consent changes for compliance"""
        from datetime import datetime
        
        consent_log = {
            'timestamp': datetime.now().isoformat(),
            'customer_id': customer_id,
            'consent_type': consent_type,
            'granted': granted,
            'ip_address': ip_address,
            'method': 'explicit_consent',
            'version': '1.0'
        }
        
        return consent_log


# ============================================
# USAGE EXAMPLES
# ============================================

def example_usage():
    """Example usage of privacy features"""
    
    # Initialize privacy manager
    privacy = DataPrivacyManager(encryption_key='your-secret-key-here')
    
    # Encrypt sensitive data
    encrypted_phone = privacy.encrypt_pii('9876543210')
    print(f"Encrypted: {encrypted_phone}")
    
    # Decrypt when needed
    decrypted_phone = privacy.decrypt_pii(encrypted_phone)
    print(f"Decrypted: {decrypted_phone}")
    
    # Mask for display
    masked_phone = privacy.mask_phone_number('9876543210')
    print(f"Masked Phone: {masked_phone}")  # XXXXXX3210
    
    # Check permissions
    can_view = AccessControlManager.has_permission('store_owner', 'view_analytics')
    print(f"Can store owner view analytics? {can_view}")
    
    # Audit logging
    audit = AuditLogger()
    log_entry = audit.log_data_access(
        user_id='user123',
        resource='customer_data',
        action='view',
        details={'customer_id': 'cust456', 'ip_address': '192.168.1.1'}
    )
    print(f"Audit log: {log_entry}")


if __name__ == '__main__':
    from datetime import datetime
    example_usage()