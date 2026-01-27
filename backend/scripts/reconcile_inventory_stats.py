#!/usr/bin/env python3
"""
Batch Reconciliation Script for Inventory Stats

This script reconciles pre-computed inventory statistics with actual
inventory data. Run periodically (recommended: daily at low-traffic hours)
to ensure stats accuracy.

Pattern: Stripe-style reconciliation (trust atomic updates, verify periodically)

Usage:
    # Reconcile all stores
    python reconcile_inventory_stats.py

    # Reconcile specific store
    python reconcile_inventory_stats.py --store-id STORE-xxx

    # Dry run (show discrepancies without updating)
    python reconcile_inventory_stats.py --dry-run

    # Verbose output
    python reconcile_inventory_stats.py --verbose

Author: DevPrakash
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = 'prod'  # Used for some tables
AWS_REGION = 'ap-south-1'

# Table names (explicit because Lambda uses 'production' but data tables use 'prod')
STORES_TABLE = 'vyaparai-stores-prod'
PRODUCTS_TABLE = 'vyaparai-store-inventory-prod'
STATS_TABLE = 'vyaparai-store-stats-production'  # Matches Lambda ENVIRONMENT=production


class StatsReconciler:
    """Reconciles pre-computed stats with actual inventory data."""

    def __init__(self, region: str = AWS_REGION, dry_run: bool = False, verbose: bool = False):
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.stores_table = self.dynamodb.Table(STORES_TABLE)
        self.products_table = self.dynamodb.Table(PRODUCTS_TABLE)
        self.stats_table = self.dynamodb.Table(STATS_TABLE)
        self.dry_run = dry_run
        self.verbose = verbose

        # Metrics
        self.stores_processed = 0
        self.stores_with_discrepancies = 0
        self.stores_updated = 0
        self.total_discrepancies = []

    def get_all_stores(self) -> List[str]:
        """Get all store IDs from the stores table."""
        store_ids = []
        scan_kwargs = {'ProjectionExpression': 'store_id'}

        try:
            while True:
                response = self.stores_table.scan(**scan_kwargs)
                for item in response.get('Items', []):
                    if 'store_id' in item:
                        store_ids.append(item['store_id'])

                # Handle pagination
                if 'LastEvaluatedKey' not in response:
                    break
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

        except ClientError as e:
            logger.error(f"Error scanning stores table: {e}")
            raise

        logger.info(f"Found {len(store_ids)} stores to reconcile")
        return store_ids

    def compute_actual_stats(self, store_id: str) -> Dict:
        """Compute actual inventory statistics from products table."""
        stats = {
            'total_products': 0,
            'active_products': 0,
            'archived_products': 0,
            'total_stock_value': Decimal('0'),
            'low_stock_count': 0,
            'out_of_stock_count': 0
        }

        scan_kwargs = {
            'FilterExpression': 'store_id = :sid',
            'ExpressionAttributeValues': {':sid': store_id}
        }

        try:
            while True:
                response = self.products_table.scan(**scan_kwargs)

                for product in response.get('Items', []):
                    stats['total_products'] += 1

                    is_active = product.get('is_active', True)
                    if is_active:
                        stats['active_products'] += 1

                        # Calculate stock value for active products
                        price = Decimal(str(product.get('selling_price', 0) or 0))
                        stock = int(product.get('current_stock', 0) or 0)
                        stats['total_stock_value'] += price * stock

                        # Check stock levels
                        min_stock = int(product.get('min_stock_level', 10) or 10)
                        if stock == 0:
                            stats['out_of_stock_count'] += 1
                        elif stock < min_stock:
                            stats['low_stock_count'] += 1
                    else:
                        stats['archived_products'] += 1

                # Handle pagination
                if 'LastEvaluatedKey' not in response:
                    break
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

        except ClientError as e:
            logger.error(f"Error computing stats for store {store_id}: {e}")
            raise

        return stats

    def get_stored_stats(self, store_id: str) -> Optional[Dict]:
        """Get pre-computed stats from stats table."""
        try:
            response = self.stats_table.get_item(
                Key={'store_id': store_id}
            )
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error getting stored stats for {store_id}: {e}")
            return None

    def find_discrepancies(
        self,
        store_id: str,
        actual: Dict,
        stored: Optional[Dict]
    ) -> List[Tuple[str, any, any]]:
        """Compare actual stats with stored stats and return discrepancies."""
        discrepancies = []

        if not stored:
            # No stored stats - this is a discrepancy (stats need initialization)
            return [('no_stored_stats', None, actual)]

        fields_to_check = [
            'total_products',
            'active_products',
            'archived_products',
            'total_stock_value',
            'low_stock_count',
            'out_of_stock_count'
        ]

        for field in fields_to_check:
            actual_val = actual.get(field, 0)
            stored_val = stored.get(field, 0)

            # Convert to comparable types
            if isinstance(actual_val, Decimal):
                actual_val = float(actual_val)
            if isinstance(stored_val, Decimal):
                stored_val = float(stored_val)

            # Allow small floating point tolerance for stock value
            if field == 'total_stock_value':
                if abs(actual_val - stored_val) > 0.01:
                    discrepancies.append((field, stored_val, actual_val))
            elif actual_val != stored_val:
                discrepancies.append((field, stored_val, actual_val))

        return discrepancies

    def update_stats(self, store_id: str, stats: Dict) -> bool:
        """Update stats table with reconciled values."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update stats for {store_id}")
            return True

        now = datetime.now(timezone.utc).isoformat()

        item = {
            'store_id': store_id,
            'total_products': stats['total_products'],
            'active_products': stats['active_products'],
            'archived_products': stats['archived_products'],
            'total_stock_value': stats['total_stock_value'],
            'low_stock_count': stats['low_stock_count'],
            'out_of_stock_count': stats['out_of_stock_count'],
            'last_updated': now,
            'last_reconciled': now,
            'version': 1  # Reset version on reconciliation
        }

        try:
            self.stats_table.put_item(Item=item)
            return True
        except ClientError as e:
            logger.error(f"Error updating stats for {store_id}: {e}")
            return False

    def reconcile_store(self, store_id: str) -> bool:
        """Reconcile stats for a single store."""
        if self.verbose:
            logger.info(f"Reconciling store: {store_id}")

        # Compute actual stats
        actual_stats = self.compute_actual_stats(store_id)

        # Get stored stats
        stored_stats = self.get_stored_stats(store_id)

        # Find discrepancies
        discrepancies = self.find_discrepancies(store_id, actual_stats, stored_stats)

        if discrepancies:
            self.stores_with_discrepancies += 1

            for field, stored_val, actual_val in discrepancies:
                self.total_discrepancies.append({
                    'store_id': store_id,
                    'field': field,
                    'stored': stored_val,
                    'actual': actual_val
                })

                if field == 'no_stored_stats':
                    logger.warning(f"  Store {store_id}: No stored stats found, initializing...")
                else:
                    logger.warning(
                        f"  Store {store_id}: {field} mismatch - "
                        f"stored={stored_val}, actual={actual_val}"
                    )

            # Update stats to correct values
            if self.update_stats(store_id, actual_stats):
                self.stores_updated += 1
                if self.verbose:
                    logger.info(f"  Updated stats for {store_id}")
                return True
            return False

        elif self.verbose:
            logger.info(f"  Store {store_id}: Stats are accurate")

        return True

    def reconcile_all(self, store_ids: Optional[List[str]] = None) -> Dict:
        """Reconcile stats for all stores or specified stores."""
        if store_ids is None:
            store_ids = self.get_all_stores()

        logger.info(f"Starting reconciliation for {len(store_ids)} stores...")
        if self.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")

        start_time = datetime.now()

        for store_id in store_ids:
            self.reconcile_store(store_id)
            self.stores_processed += 1

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Summary report
        report = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'stores_processed': self.stores_processed,
            'stores_with_discrepancies': self.stores_with_discrepancies,
            'stores_updated': self.stores_updated,
            'dry_run': self.dry_run,
            'discrepancies': self.total_discrepancies
        }

        return report


def print_report(report: Dict):
    """Print a formatted reconciliation report."""
    print("\n" + "=" * 60)
    print("INVENTORY STATS RECONCILIATION REPORT")
    print("=" * 60)
    print(f"Start Time:    {report['start_time']}")
    print(f"End Time:      {report['end_time']}")
    print(f"Duration:      {report['duration_seconds']:.2f} seconds")
    print("-" * 60)
    print(f"Stores Processed:           {report['stores_processed']}")
    print(f"Stores with Discrepancies:  {report['stores_with_discrepancies']}")
    print(f"Stores Updated:             {report['stores_updated']}")
    print(f"Dry Run:                    {'Yes' if report['dry_run'] else 'No'}")
    print("-" * 60)

    if report['discrepancies']:
        print("\nDISCREPANCIES FOUND:")
        for d in report['discrepancies']:
            if d['field'] == 'no_stored_stats':
                print(f"  {d['store_id']}: No stored stats (initialized)")
            else:
                print(f"  {d['store_id']}: {d['field']} - stored={d['stored']}, actual={d['actual']}")
    else:
        print("\nNo discrepancies found. All stats are accurate.")

    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Reconcile inventory statistics with actual inventory data'
    )
    parser.add_argument(
        '--store-id',
        help='Reconcile specific store only'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show discrepancies without updating'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--region',
        default=AWS_REGION,
        help=f'AWS region (default: {AWS_REGION})'
    )

    args = parser.parse_args()

    reconciler = StatsReconciler(
        region=args.region,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    store_ids = [args.store_id] if args.store_id else None

    try:
        report = reconciler.reconcile_all(store_ids)
        print_report(report)

        # Exit with error code if discrepancies found and not updated
        if report['stores_with_discrepancies'] > 0 and args.dry_run:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()
