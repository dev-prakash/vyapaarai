#!/usr/bin/env python3
"""
Seed GST Tables Script
Migrate GST categories and HSN mappings from static gst_config.py to DynamoDB

Usage:
    python backend/scripts/seed_gst_tables.py [--env prod|dev] [--dry-run]

Author: DevPrakash
"""

import argparse
import sys
from datetime import datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, 'backend')

from app.core.gst_config import GST_CATEGORIES, HSN_TO_CATEGORY


def seed_gst_tables(env: str = 'prod', dry_run: bool = False):
    """
    Seed GST tables from static configuration.

    Args:
        env: Environment (prod or dev)
        dry_run: If True, only simulate without writing
    """
    print(f"\n{'='*60}")
    print("GST TABLES SEEDING SCRIPT")
    print(f"{'='*60}")
    print(f"Environment: {env}")
    print(f"Dry Run: {dry_run}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")

    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    rates_table = dynamodb.Table(f'vyaparai-gst-rates-{env}')
    hsn_table = dynamodb.Table(f'vyaparai-hsn-mappings-{env}')

    # Check if tables exist
    print("Checking table status...")
    try:
        rates_status = rates_table.table_status
        hsn_status = hsn_table.table_status
        print(f"  GST Rates table: {rates_status}")
        print(f"  HSN Mappings table: {hsn_status}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("ERROR: Tables do not exist. Run Terraform first.")
            print("  terraform apply -target=aws_dynamodb_table.gst_rates")
            print("  terraform apply -target=aws_dynamodb_table.hsn_mappings")
            return False
        raise

    now = datetime.utcnow().isoformat()

    # Seed GST Categories
    print(f"\nSeeding GST Categories ({len(GST_CATEGORIES)} items)...")
    cat_count = 0
    cat_errors = 0

    for key, cat in GST_CATEGORIES.items():
        item = {
            'category_code': key,
            'category_name': cat.name,
            'gst_rate': cat.gst_rate.value,
            'hsn_prefix': cat.hsn_prefix,
            'cess_rate': cat.cess_rate,
            'description': cat.description,
            'keywords': [],
            'is_active': True,
            'effective_from': now[:10],
            'created_at': now,
            'updated_at': now,
            'updated_by': 'SYSTEM_MIGRATION'
        }

        if dry_run:
            print(f"  [DRY RUN] Would insert: {key} ({cat.name}) @ {cat.gst_rate.value}%")
            cat_count += 1
        else:
            try:
                rates_table.put_item(Item=item)
                print(f"  ✓ {key} ({cat.name}) @ {cat.gst_rate.value}%")
                cat_count += 1
            except Exception as e:
                print(f"  ✗ {key}: {e}")
                cat_errors += 1

    print(f"\nCategories: {cat_count} inserted, {cat_errors} errors")

    # Seed HSN Mappings
    print(f"\nSeeding HSN Mappings ({len(HSN_TO_CATEGORY)} items)...")
    hsn_count = 0
    hsn_errors = 0

    for hsn_code, category_code in HSN_TO_CATEGORY.items():
        item = {
            'hsn_code': hsn_code,
            'category_code': category_code,
            'description': '',
            'is_active': True,
            'created_at': now,
            'updated_at': now,
            'updated_by': 'SYSTEM_MIGRATION'
        }

        if dry_run:
            print(f"  [DRY RUN] Would insert: {hsn_code} -> {category_code}")
            hsn_count += 1
        else:
            try:
                hsn_table.put_item(Item=item)
                print(f"  ✓ {hsn_code} -> {category_code}")
                hsn_count += 1
            except Exception as e:
                print(f"  ✗ {hsn_code}: {e}")
                hsn_errors += 1

    print(f"\nHSN Mappings: {hsn_count} inserted, {hsn_errors} errors")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"GST Categories: {cat_count}/{len(GST_CATEGORIES)}")
    print(f"HSN Mappings: {hsn_count}/{len(HSN_TO_CATEGORY)}")

    if dry_run:
        print("\n[DRY RUN] No changes were made. Run without --dry-run to apply.")
    else:
        print("\nSeeding complete!")

    return cat_errors == 0 and hsn_errors == 0


def verify_seeding(env: str = 'prod'):
    """
    Verify that seeding was successful by checking table counts.

    Args:
        env: Environment (prod or dev)
    """
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")

    dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
    rates_table = dynamodb.Table(f'vyaparai-gst-rates-{env}')
    hsn_table = dynamodb.Table(f'vyaparai-hsn-mappings-{env}')

    # Count categories
    cat_response = rates_table.scan(Select='COUNT')
    cat_count = cat_response['Count']
    print(f"Categories in DB: {cat_count}")

    # Count HSN mappings
    hsn_response = hsn_table.scan(Select='COUNT')
    hsn_count = hsn_response['Count']
    print(f"HSN Mappings in DB: {hsn_count}")

    # Sample verification
    print("\nSample verification:")

    # Check a known category
    response = rates_table.get_item(Key={'category_code': 'BISCUITS'})
    if 'Item' in response:
        cat = response['Item']
        print(f"  BISCUITS: {cat['gst_rate']}% GST ✓")
    else:
        print("  BISCUITS: NOT FOUND ✗")

    # Check a known HSN
    response = hsn_table.get_item(Key={'hsn_code': '1905'})
    if 'Item' in response:
        mapping = response['Item']
        print(f"  HSN 1905 -> {mapping['category_code']} ✓")
    else:
        print("  HSN 1905: NOT FOUND ✗")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Seed GST tables from static configuration'
    )
    parser.add_argument(
        '--env',
        choices=['prod', 'dev'],
        default='prod',
        help='Environment (prod or dev)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate without writing to database'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing data, do not seed'
    )

    args = parser.parse_args()

    if args.verify_only:
        verify_seeding(args.env)
    else:
        success = seed_gst_tables(args.env, args.dry_run)
        if not args.dry_run:
            verify_seeding(args.env)

        if not success:
            sys.exit(1)


if __name__ == '__main__':
    main()
