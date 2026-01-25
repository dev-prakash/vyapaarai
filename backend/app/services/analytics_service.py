"""
Analytics Service - Real DynamoDB Integration
Provides comprehensive analytics from orders, products, and customers data

Implements MVP Reports:
1. Today's Sales Summary
2. Revenue Trend (7/30 days)
3. Top Selling Products
4. Low Stock Alerts
5. Order Status Distribution
6. Payment Method Analysis
7. Daily Order Volume
8. Top Customers
9. Category Performance
10. Peak Hours Analysis
"""

from typing import List, Dict, Optional, Any, Tuple
from decimal import Decimal
from collections import defaultdict
import asyncio
import logging
from datetime import datetime, timedelta
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def decimal_to_float(obj: Any) -> Any:
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


def format_indian_number(num: float) -> str:
    """Format number in Indian numbering system (lakhs, crores)"""
    if num >= 10000000:  # 1 crore
        return f"{num / 10000000:.2f} Cr"
    elif num >= 100000:  # 1 lakh
        return f"{num / 100000:.2f} L"
    elif num >= 1000:
        return f"{num / 1000:.2f} K"
    return f"{num:.2f}"


class AnalyticsService:
    """
    Analytics Service with real DynamoDB integration

    Provides analytics for:
    - Orders (from vyaparai-orders-prod)
    - Inventory (from vyaparai-store-inventory-prod)
    - Products (from vyaparai-global-products-prod)
    """

    def __init__(self):
        """Initialize analytics service with DynamoDB connection"""
        self.is_production = settings.ENVIRONMENT.lower() == 'production'

        try:
            # Initialize DynamoDB resource
            kwargs = {'region_name': settings.AWS_REGION}
            if settings.DYNAMODB_ENDPOINT:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT

            self.dynamodb = boto3.resource('dynamodb', **kwargs)

            # Get table references
            self.orders_table = self.dynamodb.Table(settings.DYNAMODB_ORDERS_TABLE)
            self.inventory_table = self.dynamodb.Table('vyaparai-store-inventory-prod')
            self.products_table = self.dynamodb.Table('vyaparai-global-products-prod')

            logger.info("Analytics service connected to DynamoDB")
            self.use_mock = False

        except Exception as e:
            logger.error(f"DynamoDB connection failed: {e}")
            if self.is_production:
                raise RuntimeError(f"Analytics DynamoDB connection required: {e}")
            logger.warning("Analytics service using mock mode")
            self.use_mock = True
            self.dynamodb = None

    async def _get_store_orders(
        self,
        store_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Fetch orders for a store within date range
        Uses GSI: store_id-created_at-index
        """
        if self.use_mock:
            return []

        try:
            # Build query parameters
            query_params = {
                'IndexName': 'store_id-created_at-index',
                'KeyConditionExpression': Key('store_id').eq(store_id),
                'ScanIndexForward': False,  # Most recent first
                'Limit': limit
            }

            # Add date range filter if provided
            if start_date and end_date:
                query_params['KeyConditionExpression'] = (
                    Key('store_id').eq(store_id) &
                    Key('created_at').between(
                        start_date.isoformat(),
                        end_date.isoformat()
                    )
                )

            response = await asyncio.to_thread(
                self.orders_table.query,
                **query_params
            )

            orders = decimal_to_float(response.get('Items', []))

            # If date filtering needed and not in key condition, filter manually
            if start_date and end_date and 'between' not in str(query_params.get('KeyConditionExpression', '')):
                filtered_orders = []
                for order in orders:
                    order_date_str = order.get('created_at', '')
                    if order_date_str:
                        try:
                            order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                            if start_date <= order_date.replace(tzinfo=None) <= end_date:
                                filtered_orders.append(order)
                        except (ValueError, TypeError):
                            continue
                return filtered_orders

            return orders

        except ClientError as e:
            logger.error(f"DynamoDB error fetching orders: {e}")
            return []

    async def get_todays_summary(self, store_id: str) -> Dict[str, Any]:
        """
        Report 1: Today's Sales Summary
        Returns KPIs for today: revenue, orders, avg order value, status breakdown
        """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = datetime.now()

        orders = await self._get_store_orders(store_id, today_start, today_end)

        total_revenue = sum(order.get('total_amount', 0) for order in orders)
        total_orders = len(orders)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # Status breakdown
        status_counts = defaultdict(int)
        for order in orders:
            status = order.get('status', 'pending')
            status_counts[status] += 1

        # Payment method breakdown
        payment_counts = defaultdict(int)
        for order in orders:
            payment = order.get('payment_method', 'cod')
            payment_counts[payment] += 1

        # Compare with yesterday
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start
        yesterday_orders = await self._get_store_orders(store_id, yesterday_start, yesterday_end)
        yesterday_revenue = sum(order.get('total_amount', 0) for order in yesterday_orders)

        revenue_change = 0
        if yesterday_revenue > 0:
            revenue_change = ((total_revenue - yesterday_revenue) / yesterday_revenue) * 100

        return {
            "success": True,
            "data": {
                "revenue": {
                    "total": round(total_revenue, 2),
                    "formatted": format_indian_number(total_revenue),
                    "change_percent": round(revenue_change, 1)
                },
                "orders": {
                    "total": total_orders,
                    "status_breakdown": dict(status_counts)
                },
                "average_order_value": round(avg_order_value, 2),
                "payment_methods": dict(payment_counts),
                "period": {
                    "type": "today",
                    "date": today_start.strftime("%Y-%m-%d"),
                    "start_time": today_start.isoformat(),
                    "end_time": today_end.isoformat()
                }
            }
        }

    async def get_revenue_trend(
        self,
        store_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 2: Revenue Trend
        Returns daily revenue for the past N days
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        orders = await self._get_store_orders(store_id, start_date, end_date, limit=5000)

        # Group by date
        daily_revenue = defaultdict(float)
        daily_orders = defaultdict(int)

        # Initialize all days with 0
        for i in range(days + 1):
            date_key = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_revenue[date_key] = 0
            daily_orders[date_key] = 0

        # Aggregate orders
        for order in orders:
            order_date_str = order.get('created_at', '')
            if order_date_str:
                try:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                    date_key = order_date.strftime("%Y-%m-%d")
                    daily_revenue[date_key] += order.get('total_amount', 0)
                    daily_orders[date_key] += 1
                except (ValueError, TypeError):
                    continue

        # Format for chart
        trend_data = [
            {
                "date": date,
                "revenue": round(daily_revenue[date], 2),
                "orders": daily_orders[date],
                "formatted_revenue": format_indian_number(daily_revenue[date])
            }
            for date in sorted(daily_revenue.keys())
        ]

        total_revenue = sum(daily_revenue.values())
        total_orders = sum(daily_orders.values())

        return {
            "success": True,
            "data": trend_data,
            "summary": {
                "total_revenue": round(total_revenue, 2),
                "total_orders": total_orders,
                "average_daily_revenue": round(total_revenue / days, 2) if days > 0 else 0,
                "average_daily_orders": round(total_orders / days, 1) if days > 0 else 0
            },
            "period": f"{days} days"
        }

    async def get_top_products(
        self,
        store_id: str,
        limit: int = 10,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 3: Top Selling Products
        Returns products ranked by quantity sold and revenue
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        orders = await self._get_store_orders(store_id, start_date, end_date, limit=5000)

        # Aggregate by product
        product_stats = defaultdict(lambda: {"quantity": 0, "revenue": 0})

        for order in orders:
            items = order.get('items', [])
            for item in items:
                product_name = item.get('product_name', item.get('productName', 'Unknown'))
                quantity = item.get('quantity', 0)
                total = item.get('total_price', item.get('total', 0))

                product_stats[product_name]["quantity"] += quantity
                product_stats[product_name]["revenue"] += total

        # Sort by quantity sold
        sorted_products = sorted(
            product_stats.items(),
            key=lambda x: x[1]["quantity"],
            reverse=True
        )[:limit]

        top_products = [
            {
                "rank": idx + 1,
                "name": name,
                "quantity_sold": stats["quantity"],
                "revenue": round(stats["revenue"], 2),
                "formatted_revenue": format_indian_number(stats["revenue"])
            }
            for idx, (name, stats) in enumerate(sorted_products)
        ]

        return {
            "success": True,
            "data": top_products,
            "period": f"{period_days} days",
            "total_products_sold": len(product_stats)
        }

    async def get_low_stock_alerts(
        self,
        store_id: str,
        threshold_percent: int = 20
    ) -> Dict[str, Any]:
        """
        Report 4: Low Stock Alerts
        Returns products with stock below threshold
        """
        if self.use_mock:
            return {"success": True, "data": [], "count": 0}

        try:
            # Query store inventory
            response = await asyncio.to_thread(
                self.inventory_table.query,
                KeyConditionExpression=Key('store_id').eq(store_id),
                Limit=500
            )

            items = decimal_to_float(response.get('Items', []))

            low_stock_items = []
            for item in items:
                current_stock = item.get('current_stock', 0)
                min_stock = item.get('min_stock_level', 10)
                max_stock = item.get('max_stock_level', 100)

                # Calculate stock percentage
                if max_stock > 0:
                    stock_percent = (current_stock / max_stock) * 100
                else:
                    stock_percent = 100 if current_stock > 0 else 0

                # Check if below threshold
                if stock_percent <= threshold_percent or current_stock <= min_stock:
                    low_stock_items.append({
                        "product_id": item.get('product_id'),
                        "product_name": item.get('product_name', 'Unknown'),
                        "current_stock": current_stock,
                        "min_stock_level": min_stock,
                        "max_stock_level": max_stock,
                        "stock_percent": round(stock_percent, 1),
                        "status": "critical" if current_stock <= min_stock else "low",
                        "reorder_quantity": max(0, max_stock - current_stock)
                    })

            # Sort by stock level (critical first)
            low_stock_items.sort(key=lambda x: x["current_stock"])

            return {
                "success": True,
                "data": low_stock_items,
                "count": len(low_stock_items),
                "critical_count": len([x for x in low_stock_items if x["status"] == "critical"])
            }

        except ClientError as e:
            logger.error(f"Error fetching low stock items: {e}")
            return {"success": False, "error": str(e), "data": [], "count": 0}

    async def get_order_status_distribution(
        self,
        store_id: str,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 5: Order Status Distribution
        Returns breakdown of orders by status
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        orders = await self._get_store_orders(store_id, start_date, end_date)

        status_counts = defaultdict(int)
        status_revenue = defaultdict(float)

        for order in orders:
            status = order.get('status', 'pending')
            status_counts[status] += 1
            status_revenue[status] += order.get('total_amount', 0)

        total_orders = len(orders)

        distribution = [
            {
                "status": status,
                "count": count,
                "percentage": round((count / total_orders * 100), 1) if total_orders > 0 else 0,
                "revenue": round(status_revenue[status], 2)
            }
            for status, count in status_counts.items()
        ]

        # Sort by count descending
        distribution.sort(key=lambda x: x["count"], reverse=True)

        return {
            "success": True,
            "data": distribution,
            "total_orders": total_orders,
            "period": f"{period_days} days"
        }

    async def get_payment_method_analysis(
        self,
        store_id: str,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 6: Payment Method Analysis
        Returns breakdown of payments by method
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        orders = await self._get_store_orders(store_id, start_date, end_date)

        payment_stats = defaultdict(lambda: {"count": 0, "revenue": 0})

        for order in orders:
            payment = order.get('payment_method', 'cod')
            payment_stats[payment]["count"] += 1
            payment_stats[payment]["revenue"] += order.get('total_amount', 0)

        total_orders = len(orders)
        total_revenue = sum(order.get('total_amount', 0) for order in orders)

        analysis = [
            {
                "method": method,
                "count": stats["count"],
                "revenue": round(stats["revenue"], 2),
                "order_percentage": round((stats["count"] / total_orders * 100), 1) if total_orders > 0 else 0,
                "revenue_percentage": round((stats["revenue"] / total_revenue * 100), 1) if total_revenue > 0 else 0
            }
            for method, stats in payment_stats.items()
        ]

        # Sort by revenue
        analysis.sort(key=lambda x: x["revenue"], reverse=True)

        return {
            "success": True,
            "data": analysis,
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "period": f"{period_days} days"
        }

    async def get_daily_order_volume(
        self,
        store_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 7: Daily Order Volume
        Returns order counts by day
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        orders = await self._get_store_orders(store_id, start_date, end_date)

        # Group by date
        daily_counts = defaultdict(int)

        # Initialize all days
        for i in range(days + 1):
            date_key = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_counts[date_key] = 0

        for order in orders:
            order_date_str = order.get('created_at', '')
            if order_date_str:
                try:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                    date_key = order_date.strftime("%Y-%m-%d")
                    daily_counts[date_key] += 1
                except (ValueError, TypeError):
                    continue

        volume_data = [
            {
                "date": date,
                "orders": count,
                "day_name": datetime.strptime(date, "%Y-%m-%d").strftime("%a")
            }
            for date in sorted(daily_counts.keys())
        ]

        total_orders = sum(daily_counts.values())
        avg_daily = total_orders / days if days > 0 else 0

        return {
            "success": True,
            "data": volume_data,
            "summary": {
                "total_orders": total_orders,
                "average_daily": round(avg_daily, 1),
                "peak_day": max(volume_data, key=lambda x: x["orders"]) if volume_data else None
            },
            "period": f"{days} days"
        }

    async def get_top_customers(
        self,
        store_id: str,
        limit: int = 10,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Report 8: Top Customers
        Returns customers ranked by total spend
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        orders = await self._get_store_orders(store_id, start_date, end_date, limit=5000)

        # Aggregate by customer
        customer_stats = defaultdict(lambda: {
            "orders": 0,
            "total_spent": 0,
            "last_order": None,
            "name": ""
        })

        for order in orders:
            customer_id = order.get('customer_id', order.get('customer_phone', 'Unknown'))
            customer_name = order.get('customer_name', 'Guest')

            customer_stats[customer_id]["orders"] += 1
            customer_stats[customer_id]["total_spent"] += order.get('total_amount', 0)
            customer_stats[customer_id]["name"] = customer_name

            order_date = order.get('created_at', '')
            if not customer_stats[customer_id]["last_order"] or order_date > customer_stats[customer_id]["last_order"]:
                customer_stats[customer_id]["last_order"] = order_date

        # Sort by total spent
        sorted_customers = sorted(
            customer_stats.items(),
            key=lambda x: x[1]["total_spent"],
            reverse=True
        )[:limit]

        top_customers = [
            {
                "rank": idx + 1,
                "customer_id": cid,
                "name": stats["name"] or "Guest",
                "orders": stats["orders"],
                "total_spent": round(stats["total_spent"], 2),
                "formatted_spent": format_indian_number(stats["total_spent"]),
                "average_order_value": round(stats["total_spent"] / stats["orders"], 2) if stats["orders"] > 0 else 0,
                "last_order": stats["last_order"]
            }
            for idx, (cid, stats) in enumerate(sorted_customers)
        ]

        return {
            "success": True,
            "data": top_customers,
            "total_customers": len(customer_stats),
            "period": f"{period_days} days"
        }

    async def get_category_performance(
        self,
        store_id: str,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 9: Category Performance
        Returns sales breakdown by product category
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        orders = await self._get_store_orders(store_id, start_date, end_date, limit=5000)

        # Aggregate by category
        category_stats = defaultdict(lambda: {"quantity": 0, "revenue": 0, "orders": 0})

        for order in orders:
            items = order.get('items', [])
            categories_in_order = set()

            for item in items:
                category = item.get('category', 'Uncategorized')
                quantity = item.get('quantity', 0)
                revenue = item.get('total_price', item.get('total', 0))

                category_stats[category]["quantity"] += quantity
                category_stats[category]["revenue"] += revenue
                categories_in_order.add(category)

            # Count unique orders per category
            for cat in categories_in_order:
                category_stats[cat]["orders"] += 1

        total_revenue = sum(stats["revenue"] for stats in category_stats.values())

        # Format results
        performance = [
            {
                "category": category,
                "quantity_sold": stats["quantity"],
                "revenue": round(stats["revenue"], 2),
                "formatted_revenue": format_indian_number(stats["revenue"]),
                "order_count": stats["orders"],
                "revenue_share": round((stats["revenue"] / total_revenue * 100), 1) if total_revenue > 0 else 0
            }
            for category, stats in category_stats.items()
        ]

        # Sort by revenue
        performance.sort(key=lambda x: x["revenue"], reverse=True)

        return {
            "success": True,
            "data": performance,
            "total_revenue": round(total_revenue, 2),
            "total_categories": len(category_stats),
            "period": f"{period_days} days"
        }

    async def get_peak_hours_analysis(
        self,
        store_id: str,
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Report 10: Peak Hours Analysis
        Returns order distribution by hour of day
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        orders = await self._get_store_orders(store_id, start_date, end_date)

        # Initialize all hours
        hourly_stats = {hour: {"orders": 0, "revenue": 0} for hour in range(24)}

        for order in orders:
            order_date_str = order.get('created_at', '')
            if order_date_str:
                try:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                    hour = order_date.hour
                    hourly_stats[hour]["orders"] += 1
                    hourly_stats[hour]["revenue"] += order.get('total_amount', 0)
                except (ValueError, TypeError):
                    continue

        # Format for heatmap
        peak_data = [
            {
                "hour": hour,
                "time_label": f"{hour:02d}:00",
                "orders": stats["orders"],
                "revenue": round(stats["revenue"], 2)
            }
            for hour, stats in hourly_stats.items()
        ]

        # Find peak hours
        max_orders = max(stats["orders"] for stats in hourly_stats.values())
        peak_hours = [
            f"{hour:02d}:00"
            for hour, stats in hourly_stats.items()
            if stats["orders"] == max_orders and max_orders > 0
        ]

        # Identify business patterns
        morning_orders = sum(hourly_stats[h]["orders"] for h in range(6, 12))
        afternoon_orders = sum(hourly_stats[h]["orders"] for h in range(12, 17))
        evening_orders = sum(hourly_stats[h]["orders"] for h in range(17, 21))
        night_orders = sum(hourly_stats[h]["orders"] for h in range(21, 24)) + sum(hourly_stats[h]["orders"] for h in range(0, 6))

        return {
            "success": True,
            "data": peak_data,
            "summary": {
                "peak_hours": peak_hours,
                "max_orders_per_hour": max_orders,
                "patterns": {
                    "morning_6_12": morning_orders,
                    "afternoon_12_17": afternoon_orders,
                    "evening_17_21": evening_orders,
                    "night_21_6": night_orders
                }
            },
            "period": f"{period_days} days"
        }

    async def get_analytics_overview(
        self,
        store_id: str,
        period: str = "week"
    ) -> Dict[str, Any]:
        """
        Combined overview for dashboard
        Returns key metrics from multiple reports
        """
        # Determine date range
        if period == "today":
            days = 1
        elif period == "week":
            days = 7
        elif period == "month":
            days = 30
        else:
            days = 7

        # Fetch multiple reports in parallel
        results = await asyncio.gather(
            self.get_todays_summary(store_id),
            self.get_revenue_trend(store_id, days),
            self.get_top_products(store_id, 5, days),
            self.get_low_stock_alerts(store_id),
            self.get_order_status_distribution(store_id, days),
            return_exceptions=True
        )

        # Handle errors gracefully
        today_summary = results[0] if not isinstance(results[0], Exception) else {"success": False}
        revenue_trend = results[1] if not isinstance(results[1], Exception) else {"success": False}
        top_products = results[2] if not isinstance(results[2], Exception) else {"success": False}
        low_stock = results[3] if not isinstance(results[3], Exception) else {"success": False}
        status_dist = results[4] if not isinstance(results[4], Exception) else {"success": False}

        return {
            "success": True,
            "data": {
                "today": today_summary.get("data", {}),
                "revenue_trend": revenue_trend.get("data", []),
                "top_products": top_products.get("data", []),
                "low_stock_count": low_stock.get("count", 0),
                "order_status": status_dist.get("data", [])
            },
            "period": period,
            "generated_at": datetime.now().isoformat()
        }


# Global singleton instance
analytics_service = AnalyticsService()
