"""
GST Repository - Data Access Layer for GST Reference Tables
Handles CRUD operations for GST rates and HSN mappings in DynamoDB

Author: DevPrakash
"""

import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

# Environment configuration
ENV = os.environ.get("VYAPAARAI_ENV", "prod")


class GSTRepository:
    """Repository for GST rates and HSN mappings in DynamoDB"""

    def __init__(self):
        """Initialize DynamoDB connection"""
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
        self.rates_table = self.dynamodb.Table(f"vyaparai-gst-rates-{ENV}")
        self.hsn_table = self.dynamodb.Table(f"vyaparai-hsn-mappings-{ENV}")

    # =========================================================================
    # GST CATEGORIES CRUD
    # =========================================================================

    async def get_all_categories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all GST categories.

        Args:
            active_only: If True, only return active categories

        Returns:
            List of GST category dictionaries
        """
        try:
            if active_only:
                response = self.rates_table.scan(
                    FilterExpression=Attr("is_active").eq(True) | Attr("is_active").not_exists()
                )
            else:
                response = self.rates_table.scan()

            categories = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                if active_only:
                    response = self.rates_table.scan(
                        FilterExpression=Attr("is_active").eq(True) | Attr("is_active").not_exists(),
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                else:
                    response = self.rates_table.scan(
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                categories.extend(response.get("Items", []))

            return categories

        except Exception as e:
            logger.error(f"Error fetching GST categories: {e}")
            return []

    async def get_category(self, category_code: str) -> Optional[Dict[str, Any]]:
        """
        Get a single GST category by code.

        Args:
            category_code: Category code (e.g., "BISCUITS")

        Returns:
            Category dict if found, None otherwise
        """
        try:
            response = self.rates_table.get_item(
                Key={"category_code": category_code}
            )
            return response.get("Item")

        except Exception as e:
            logger.error(f"Error fetching GST category {category_code}: {e}")
            return None

    async def create_category(
        self,
        category_code: str,
        category_name: str,
        gst_rate: Decimal,
        hsn_prefix: str,
        admin_id: str,
        cess_rate: Decimal = Decimal("0"),
        description: str = "",
        keywords: Optional[List[str]] = None,
        effective_from: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new GST category.

        Args:
            category_code: Unique category code
            category_name: Human-readable name
            gst_rate: GST rate (0, 5, 12, 18, 28)
            hsn_prefix: HSN code prefix
            admin_id: ID of admin creating the category
            cess_rate: Additional cess rate (default 0)
            description: Category description
            keywords: Keywords for product name matching
            effective_from: Date when rate becomes effective

        Returns:
            Created category dict
        """
        now = datetime.utcnow().isoformat()
        item = {
            "category_code": category_code,
            "category_name": category_name,
            "gst_rate": gst_rate,
            "hsn_prefix": hsn_prefix,
            "cess_rate": cess_rate,
            "description": description,
            "keywords": keywords or [],
            "is_active": True,
            "effective_from": effective_from or now[:10],
            "created_at": now,
            "updated_at": now,
            "updated_by": admin_id
        }

        try:
            self.rates_table.put_item(Item=item)
            logger.info(f"Created GST category {category_code} by {admin_id}")
            return item

        except Exception as e:
            logger.error(f"Error creating GST category {category_code}: {e}")
            raise

    async def update_category(
        self,
        category_code: str,
        updates: Dict[str, Any],
        admin_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update a GST category.

        Args:
            category_code: Category code to update
            updates: Dictionary of fields to update
            admin_id: ID of admin making the update

        Returns:
            Updated category dict if successful, None otherwise
        """
        # Allowed fields to update
        allowed_fields = {
            "category_name", "gst_rate", "hsn_prefix", "cess_rate",
            "description", "keywords", "is_active", "effective_from"
        }

        # Filter to only allowed fields
        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            logger.warning(f"No valid update fields for category {category_code}")
            return None

        # Build update expression
        update_parts = []
        expr_names = {}
        expr_values = {":updated_at": datetime.utcnow().isoformat(), ":updated_by": admin_id}

        for key, value in valid_updates.items():
            expr_name = f"#{key}"
            expr_value = f":{key}"
            update_parts.append(f"{expr_name} = {expr_value}")
            expr_names[expr_name] = key
            expr_values[expr_value] = value

        update_parts.append("#updated_at = :updated_at")
        update_parts.append("#updated_by = :updated_by")
        expr_names["#updated_at"] = "updated_at"
        expr_names["#updated_by"] = "updated_by"

        try:
            response = self.rates_table.update_item(
                Key={"category_code": category_code},
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW"
            )
            logger.info(f"Updated GST category {category_code} by {admin_id}: {list(valid_updates.keys())}")
            return response.get("Attributes")

        except Exception as e:
            logger.error(f"Error updating GST category {category_code}: {e}")
            return None

    async def delete_category(self, category_code: str, admin_id: str) -> bool:
        """
        Soft delete a GST category (set is_active=False).

        Args:
            category_code: Category code to delete
            admin_id: ID of admin deleting

        Returns:
            True if successful, False otherwise
        """
        result = await self.update_category(
            category_code,
            {"is_active": False},
            admin_id
        )
        return result is not None

    async def get_categories_by_rate(self, gst_rate: Decimal) -> List[Dict[str, Any]]:
        """
        Get all categories with a specific GST rate.

        Args:
            gst_rate: GST rate to filter by

        Returns:
            List of matching categories
        """
        try:
            response = self.rates_table.query(
                IndexName="gst-rate-index",
                KeyConditionExpression=Key("gst_rate").eq(gst_rate)
            )
            return response.get("Items", [])

        except Exception as e:
            logger.error(f"Error querying categories by rate {gst_rate}: {e}")
            return []

    # =========================================================================
    # HSN MAPPINGS CRUD
    # =========================================================================

    async def get_hsn_mapping(self, hsn_code: str) -> Optional[Dict[str, Any]]:
        """
        Get HSN mapping by code.

        Args:
            hsn_code: HSN code to lookup

        Returns:
            HSN mapping dict if found, None otherwise
        """
        try:
            response = self.hsn_table.get_item(
                Key={"hsn_code": hsn_code}
            )
            item = response.get("Item")

            # Check if active
            if item and item.get("is_active", True):
                return item
            return None

        except Exception as e:
            logger.error(f"Error fetching HSN mapping {hsn_code}: {e}")
            return None

    async def get_hsn_by_prefix(self, prefix: str) -> Optional[Dict[str, Any]]:
        """
        Get HSN mapping by prefix (first 4 digits).

        Args:
            prefix: 4-digit HSN prefix

        Returns:
            HSN mapping dict if found, None otherwise
        """
        # First try exact match
        result = await self.get_hsn_mapping(prefix)
        if result:
            return result

        # If not found, no prefix matching needed at DB level
        # The service layer will handle fallback logic
        return None

    async def get_all_hsn_mappings(self, category_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all HSN mappings, optionally filtered by category.

        Args:
            category_code: Optional category code to filter by

        Returns:
            List of HSN mapping dictionaries
        """
        try:
            if category_code:
                response = self.hsn_table.query(
                    IndexName="category-index",
                    KeyConditionExpression=Key("category_code").eq(category_code)
                )
            else:
                response = self.hsn_table.scan(
                    FilterExpression=Attr("is_active").eq(True) | Attr("is_active").not_exists()
                )

            mappings = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                if category_code:
                    response = self.hsn_table.query(
                        IndexName="category-index",
                        KeyConditionExpression=Key("category_code").eq(category_code),
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                else:
                    response = self.hsn_table.scan(
                        FilterExpression=Attr("is_active").eq(True) | Attr("is_active").not_exists(),
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                mappings.extend(response.get("Items", []))

            return mappings

        except Exception as e:
            logger.error(f"Error fetching HSN mappings: {e}")
            return []

    async def create_hsn_mapping(
        self,
        hsn_code: str,
        category_code: str,
        admin_id: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Create a new HSN code mapping.

        Args:
            hsn_code: HSN code (4, 6, or 8 digits)
            category_code: GST category code to map to
            admin_id: ID of admin creating the mapping
            description: Optional description

        Returns:
            Created HSN mapping dict
        """
        now = datetime.utcnow().isoformat()
        item = {
            "hsn_code": hsn_code,
            "category_code": category_code,
            "description": description,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "updated_by": admin_id
        }

        try:
            self.hsn_table.put_item(Item=item)
            logger.info(f"Created HSN mapping {hsn_code} -> {category_code} by {admin_id}")
            return item

        except Exception as e:
            logger.error(f"Error creating HSN mapping {hsn_code}: {e}")
            raise

    async def update_hsn_mapping(
        self,
        hsn_code: str,
        updates: Dict[str, Any],
        admin_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update an HSN mapping.

        Args:
            hsn_code: HSN code to update
            updates: Dictionary of fields to update
            admin_id: ID of admin making the update

        Returns:
            Updated HSN mapping dict if successful, None otherwise
        """
        allowed_fields = {"category_code", "description", "is_active"}
        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            return None

        update_parts = []
        expr_names = {}
        expr_values = {":updated_at": datetime.utcnow().isoformat(), ":updated_by": admin_id}

        for key, value in valid_updates.items():
            expr_name = f"#{key}"
            expr_value = f":{key}"
            update_parts.append(f"{expr_name} = {expr_value}")
            expr_names[expr_name] = key
            expr_values[expr_value] = value

        update_parts.append("#updated_at = :updated_at")
        update_parts.append("#updated_by = :updated_by")
        expr_names["#updated_at"] = "updated_at"
        expr_names["#updated_by"] = "updated_by"

        try:
            response = self.hsn_table.update_item(
                Key={"hsn_code": hsn_code},
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW"
            )
            logger.info(f"Updated HSN mapping {hsn_code} by {admin_id}")
            return response.get("Attributes")

        except Exception as e:
            logger.error(f"Error updating HSN mapping {hsn_code}: {e}")
            return None

    async def delete_hsn_mapping(self, hsn_code: str, admin_id: str) -> bool:
        """
        Soft delete an HSN mapping.

        Args:
            hsn_code: HSN code to delete
            admin_id: ID of admin deleting

        Returns:
            True if successful, False otherwise
        """
        result = await self.update_hsn_mapping(
            hsn_code,
            {"is_active": False},
            admin_id
        )
        return result is not None

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    async def bulk_upsert_categories(
        self,
        categories: List[Dict[str, Any]],
        admin_id: str
    ) -> int:
        """
        Bulk insert/update GST categories.

        Args:
            categories: List of category dicts with at least category_code
            admin_id: ID of admin performing the operation

        Returns:
            Number of categories processed
        """
        now = datetime.utcnow().isoformat()
        count = 0

        try:
            with self.rates_table.batch_writer() as batch:
                for cat in categories:
                    item = {
                        "category_code": cat["category_code"],
                        "category_name": cat.get("category_name", cat["category_code"]),
                        "gst_rate": Decimal(str(cat.get("gst_rate", 18))),
                        "hsn_prefix": cat.get("hsn_prefix", ""),
                        "cess_rate": Decimal(str(cat.get("cess_rate", 0))),
                        "description": cat.get("description", ""),
                        "keywords": cat.get("keywords", []),
                        "is_active": True,
                        "effective_from": cat.get("effective_from", now[:10]),
                        "created_at": now,
                        "updated_at": now,
                        "updated_by": admin_id
                    }
                    batch.put_item(Item=item)
                    count += 1

            logger.info(f"Bulk upserted {count} GST categories by {admin_id}")
            return count

        except Exception as e:
            logger.error(f"Error in bulk upsert categories: {e}")
            raise

    async def bulk_upsert_hsn_mappings(
        self,
        mappings: List[Dict[str, Any]],
        admin_id: str
    ) -> int:
        """
        Bulk insert/update HSN mappings.

        Args:
            mappings: List of mapping dicts with hsn_code and category_code
            admin_id: ID of admin performing the operation

        Returns:
            Number of mappings processed
        """
        now = datetime.utcnow().isoformat()
        count = 0

        try:
            with self.hsn_table.batch_writer() as batch:
                for mapping in mappings:
                    item = {
                        "hsn_code": mapping["hsn_code"],
                        "category_code": mapping["category_code"],
                        "description": mapping.get("description", ""),
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                        "updated_by": admin_id
                    }
                    batch.put_item(Item=item)
                    count += 1

            logger.info(f"Bulk upserted {count} HSN mappings by {admin_id}")
            return count

        except Exception as e:
            logger.error(f"Error in bulk upsert HSN mappings: {e}")
            raise


# Singleton instance
gst_repository = GSTRepository()
