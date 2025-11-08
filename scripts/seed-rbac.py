#!/usr/bin/env python3
"""
Seed RBAC (Role-Based Access Control) data into DynamoDB tables.
This script populates the permissions and roles tables with initial data.
"""

import json
import boto3
from datetime import datetime

# Initialize DynamoDB client
dynamodb = boto3.client('dynamodb', region_name='ap-south-1')

def seed_permissions(permissions):
    """Seed permissions into vyaparai-permissions-prod table"""
    print("\n📝 Seeding permissions...")
    count = 0

    for perm in permissions:
        try:
            print(f"  Adding permission: {perm['permission_id']}")

            dynamodb.put_item(
                TableName='vyaparai-permissions-prod',
                Item={
                    'permission_id': {'S': perm['permission_id']},
                    'name': {'S': perm['name']},
                    'description': {'S': perm['description']},
                    'category': {'S': perm['category']},
                    'resource': {'S': perm['resource']},
                    'action': {'S': perm['action']},
                    'status': {'S': perm['status']},
                    'created_at': {'S': perm['created_at']},
                    'updated_at': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            )
            count += 1
        except Exception as e:
            print(f"  ⚠️  Failed to add {perm['permission_id']}: {str(e)}")

    print(f"✅ Added {count} permissions")
    return count

def seed_roles(roles):
    """Seed roles into vyaparai-roles-prod table"""
    print("\n👥 Seeding roles...")
    count = 0

    for role in roles:
        try:
            print(f"  Adding role: {role['role_id']}")

            # Convert permissions list to DynamoDB StringSet
            permissions_ss = {'SS': role['permissions']} if role['permissions'] != ['*'] else {'SS': ['*']}

            dynamodb.put_item(
                TableName='vyaparai-roles-prod',
                Item={
                    'role_id': {'S': role['role_id']},
                    'role_name': {'S': role['role_name']},
                    'description': {'S': role['description']},
                    'permissions': permissions_ss,
                    'hierarchy_level': {'N': str(role['hierarchy_level'])},
                    'is_system_role': {'BOOL': role['is_system_role']},
                    'status': {'S': role['status']},
                    'created_at': {'S': role['created_at']},
                    'updated_at': {'S': datetime.utcnow().isoformat() + 'Z'}
                }
            )
            count += 1
        except Exception as e:
            print(f"  ⚠️  Failed to add {role['role_id']}: {str(e)}")

    print(f"✅ Added {count} roles")
    return count

def main():
    print("🚀 Starting RBAC data seeding...")

    # Load seed data
    with open('/Users/devprakash/MyProjects/VyaparAI/vyaparai/scripts/seed-rbac-data.json', 'r') as f:
        data = json.load(f)

    # Seed permissions
    perm_count = seed_permissions(data['permissions'])

    # Seed roles
    role_count = seed_roles(data['roles'])

    # Summary
    print("\n🎉 RBAC seeding completed!")
    print(f"\n📊 Summary:")
    print(f"  Permissions added: {perm_count}")
    print(f"  Roles added: {role_count}")

    # Verify counts in tables
    print(f"\n🔍 Verifying tables...")
    try:
        perm_table = dynamodb.describe_table(TableName='vyaparai-permissions-prod')
        role_table = dynamodb.describe_table(TableName='vyaparai-roles-prod')
        print(f"  Permissions table: {perm_table['Table']['ItemCount']} items")
        print(f"  Roles table: {role_table['Table']['ItemCount']} items")
    except Exception as e:
        print(f"  Could not verify: {str(e)}")

if __name__ == '__main__':
    main()
