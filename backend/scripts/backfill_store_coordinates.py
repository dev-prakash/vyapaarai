#!/usr/bin/env python3
"""
Backfill missing latitude/longitude for stores in DynamoDB.

Scans vyaparai-stores-prod for records where latitude or longitude is None,
geocodes the store address via Google Maps Geocoding API, and updates the record.

Usage:
    # Dry run (show what would be updated)
    python backfill_store_coordinates.py --dry-run

    # Actually update DynamoDB
    python backfill_store_coordinates.py

    # Backfill a specific store
    python backfill_store_coordinates.py --store-id STORE-01KFSG8S99QMDCC0SKK47Q01JB

Requires:
    GOOGLE_MAPS_API_KEY env var (or pass via --api-key)
    AWS credentials configured (for DynamoDB access)

Author: DevPrakash
"""

import os
import sys
import argparse
import time
import json
import urllib.request
import urllib.parse
import boto3

# Table name
STORES_TABLE = os.getenv('DYNAMODB_STORES_TABLE', 'vyaparai-stores-prod')
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')


def geocode_address(street: str, city: str, state: str, pincode: str) -> dict | None:
    """Geocode an address using Google Maps API. Returns {latitude, longitude} or None."""
    address_parts = [p.strip() for p in [street, city, state, pincode, "India"] if p and p.strip()]
    full_address = ", ".join(address_parts)

    if not full_address or full_address == "India":
        print(f"  [SKIP] Empty address")
        return None

    params = {
        "address": full_address,
        "key": GOOGLE_MAPS_API_KEY,
        "region": "in",
        "components": "country:IN",
    }

    print(f"  [GEOCODE] Requesting: {full_address}")
    url = GEOCODING_API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    if data.get("status") == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        formatted = data["results"][0].get("formatted_address", full_address)
        print(f"  [OK] ({loc['lat']}, {loc['lng']}) — {formatted}")
        return {"latitude": str(loc["lat"]), "longitude": str(loc["lng"])}

    print(f"  [FAIL] API status: {data.get('status')} — {data.get('error_message', 'No results')}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Backfill store coordinates from address")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
    parser.add_argument("--store-id", type=str, help="Backfill a specific store only")
    parser.add_argument("--api-key", type=str, help="Google Maps API key (overrides env var)")
    args = parser.parse_args()

    global GOOGLE_MAPS_API_KEY
    if args.api_key:
        GOOGLE_MAPS_API_KEY = args.api_key

    if not GOOGLE_MAPS_API_KEY:
        print("ERROR: GOOGLE_MAPS_API_KEY not set. Pass --api-key or set env var.")
        sys.exit(1)

    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(STORES_TABLE)

    # Scan for stores with missing coordinates
    print(f"\nScanning {STORES_TABLE} for stores with missing coordinates...\n")

    stores_to_update = []
    scan_kwargs = {}

    if args.store_id:
        # Fetch specific store
        resp = table.get_item(Key={"id": args.store_id})
        item = resp.get("Item")
        if not item:
            print(f"Store {args.store_id} not found in {STORES_TABLE}")
            sys.exit(1)
        items = [item]
    else:
        # Full table scan
        items = []
        while True:
            resp = table.scan(**scan_kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    print(f"Total stores scanned: {len(items)}\n")

    for item in items:
        store_id = item.get("id") or item.get("store_id")
        name = item.get("name", "Unknown")
        lat = item.get("latitude")
        lng = item.get("longitude")

        if lat is not None and lng is not None:
            continue  # Already has coordinates

        address = item.get("address", {})
        if isinstance(address, str):
            # Some records may store address as a string
            stores_to_update.append({"id": store_id, "name": name, "address_str": address})
        else:
            stores_to_update.append({
                "id": store_id,
                "name": name,
                "street": address.get("street", ""),
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "pincode": address.get("pincode", ""),
            })

    if not stores_to_update:
        print("All stores already have coordinates. Nothing to backfill.")
        return

    print(f"Found {len(stores_to_update)} store(s) missing coordinates:\n")

    success = 0
    failed = 0

    for store in stores_to_update:
        print(f"[{store['id']}] {store['name']}")

        try:
            coords = geocode_address(
                street=store.get("street", ""),
                city=store.get("city", ""),
                state=store.get("state", ""),
                pincode=store.get("pincode", ""),
            )
        except Exception as e:
            print(f"  [ERROR] Geocoding failed: {e}")
            failed += 1
            continue

        if not coords:
            failed += 1
            continue

        if args.dry_run:
            print(f"  [DRY RUN] Would update: lat={coords['latitude']}, lng={coords['longitude']}")
            success += 1
        else:
            try:
                table.update_item(
                    Key={"id": store["id"]},
                    UpdateExpression="SET latitude = :lat, longitude = :lng",
                    ExpressionAttributeValues={
                        ":lat": coords["latitude"],
                        ":lng": coords["longitude"],
                    },
                )
                print(f"  [UPDATED] DynamoDB record updated")
                success += 1
            except Exception as e:
                print(f"  [ERROR] DynamoDB update failed: {e}")
                failed += 1

        # Rate limit: 1 request per 100ms (well under Google's 3000/min limit)
        time.sleep(0.1)

    print(f"\n{'='*50}")
    print(f"Results: {success} updated, {failed} failed, {len(stores_to_update)} total")
    if args.dry_run:
        print("(Dry run — no changes were made)")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
