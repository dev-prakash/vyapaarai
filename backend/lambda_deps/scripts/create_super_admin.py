#!/usr/bin/env python3
"""
Script to create the first super admin user for VyaparAI system
"""

import boto3
import hashlib
import secrets
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    import bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_super_admin():
    """Create the first super admin user"""
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    users_table = dynamodb.Table('vyaparai-users-prod')
    
    # Get admin details
    print("=== VyaparAI Super Admin Creation ===")
    print("This script will create the first super admin user for the system.")
    print()
    
    email = input("Enter admin email: ").strip().lower()
    if not email:
        print("Error: Email is required")
        return False
    
    name = input("Enter admin full name: ").strip()
    if not name:
        print("Error: Name is required")
        return False
    
    phone = input("Enter admin phone number (optional): ").strip()
    
    password = input("Enter admin password (min 8 characters): ").strip()
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long")
        return False
    
    confirm_password = input("Confirm admin password: ").strip()
    if password != confirm_password:
        print("Error: Passwords do not match")
        return False
    
    # Check if user already exists
    try:
        response = users_table.get_item(Key={'id': f'user_{email}'})
        if 'Item' in response:
            print(f"Error: User with email {email} already exists")
            return False
    except Exception as e:
        print(f"Error checking existing user: {e}")
        return False
    
    # Create super admin user
    try:
        user_id = f'user_{email}'
        current_time = datetime.utcnow().isoformat()
        password_hash = hash_password(password)
        
        user_item = {
            'id': user_id,
            'email': email,
            'name': name,
            'role': 'super_admin',
            'status': 'active',
            'password_hash': password_hash,
            'created_at': current_time,
            'updated_at': current_time,
            'created_by': 'system'
        }
        
        if phone:
            user_item['phone'] = phone
        
        users_table.put_item(Item=user_item)
        
        print()
        print("✅ Super admin user created successfully!")
        print(f"Email: {email}")
        print(f"Name: {name}")
        print(f"Role: super_admin")
        print(f"Status: active")
        print()
        print("You can now access the admin panel at:")
        print("https://vyapaarai.com/nimdaaccess")
        print()
        print("⚠️  Keep these credentials secure!")
        
        return True
        
    except Exception as e:
        print(f"Error creating super admin user: {e}")
        return False

def main():
    """Main function"""
    try:
        success = create_super_admin()
        if success:
            print("Super admin creation completed successfully.")
        else:
            print("Super admin creation failed.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()



