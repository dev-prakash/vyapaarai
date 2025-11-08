#!/usr/bin/env python3
"""
Script to create the first super admin user for VyaparAI system
"""

import boto3
import bcrypt
import sys
import os
from datetime import datetime

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_super_admin():
    """Create the first super admin user"""
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    users_table = dynamodb.Table('vyaparai-users-prod')
    
    # Admin details
    email = 'nimda.vai@gmail.com'
    name = 'Nimda Admin'
    phone = ''
    password = 'Admin123!@#'
    
    print("=== VyaparAI Super Admin Creation ===")
    print(f"Creating super admin user:")
    print(f"Email: {email}")
    print(f"Name: {name}")
    print(f"Password: {password}")
    print()
    
    # Check if user already exists
    try:
        response = users_table.get_item(Key={'id': f'user_{email}'})
        if 'Item' in response:
            print(f"❌ User with email {email} already exists")
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
        print(f"📧 Email: {email}")
        print(f"👤 Name: {name}")
        print(f"🔑 Password: {password}")
        print(f"🎭 Role: super_admin")
        print(f"✅ Status: active")
        print()
        print("🌐 You can now access the admin panel at:")
        print("https://vyapaarai.com/nimdaaccess")
        print()
        print("⚠️  Keep these credentials secure!")
        print("🔐 Login credentials:")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating super admin user: {e}")
        return False

def main():
    """Main function"""
    try:
        success = create_super_admin()
        if success:
            print("\n🎉 Super admin creation completed successfully.")
        else:
            print("\n💥 Super admin creation failed.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()



