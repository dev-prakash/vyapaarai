import bcrypt
import hashlib
from typing import Optional

class PasswordService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt with cost factor 12"""
        if not password:
            raise ValueError("Password cannot be empty")
        
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """Verify password against bcrypt hash"""
        if not password or not hashed_password:
            return False
        
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False
    
    @staticmethod
    def is_sha256_hash(hashed_password: str) -> bool:
        """Check if hash is SHA-256 format (64 hex characters)"""
        return len(hashed_password) == 64 and all(c in '0123456789abcdef' for c in hashed_password.lower())
    
    @staticmethod
    def verify_legacy_sha256(password: str, sha256_hash: str) -> bool:
        """Verify password against legacy SHA-256 hash"""
        if not password or not sha256_hash:
            return False
        
        computed_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return computed_hash == sha256_hash
    
    @staticmethod
    def migrate_sha256_to_bcrypt(password: str, old_sha256_hash: str) -> Optional[str]:
        """Migrate SHA-256 hash to bcrypt if password is correct"""
        if PasswordService.verify_legacy_sha256(password, old_sha256_hash):
            return PasswordService.hash_password(password)
        return None
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Validate password strength requirements"""
        if not password:
            return False, "Password cannot be empty"
        
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        
        if len(password) > 128:
            return False, "Password must be less than 128 characters"
        
        # Check for at least one uppercase, lowercase, digit, and special character
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not has_upper:
            return False, "Password must contain at least one uppercase letter"
        
        if not has_lower:
            return False, "Password must contain at least one lowercase letter"
        
        if not has_digit:
            return False, "Password must contain at least one digit"
        
        if not has_special:
            return False, "Password must contain at least one special character"
        
        return True, "Password meets strength requirements"
