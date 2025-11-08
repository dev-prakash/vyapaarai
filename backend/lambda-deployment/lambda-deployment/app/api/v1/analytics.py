"""
Analytics API endpoints for VyaparAI
Provides comprehensive analytics and reporting functionality
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Import orders database
try:
    from app.api.v1.orders import orders_db
except ImportError:
    orders_db = {}

class AnalyticsOverviewRequest(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    period: str = Field("week", description="Time period: today, week, month, custom")
    start_date: Optional[str] = Field(None, description="Start date for custom period")
    end_date: Optional[str] = Field(None, description="End date for custom period")

class TopProductsRequest(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    limit: int = Field(10, description="Number of top products to return")
    period: str = Field("week", description="Time period")

class CustomerInsightsRequest(BaseModel):
    store_id: str = Field(..., description="Store identifier")

from app.core.cache import cache_result, invalidate_analytics_cache

@router.get("/overview", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics")  # Cache for 10 minutes
async def get_analytics_overview(
    store_id: str = Query(..., description="Store identifier"),
    period: str = Query("week", description="Time period: today, week, month, custom")
):
    """
    Get comprehensive analytics overview for a store
    
    Returns revenue, orders, customers, and trends data for the specified period.
    """
    try:
        # Calculate date range based on period
        end_date = datetime.now()
        
        if period == "today":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        else:
            # Default to week if invalid period
            start_date = end_date - timedelta(days=7)
        
        # Filter orders for the period
        period_orders = []
        total_revenue = 0
        unique_customers = set()
        status_counts = {'pending': 0, 'completed': 0, 'cancelled': 0}
        payment_counts = {'cash': 0, 'upi': 0, 'card': 0, 'cod': 0}
        
        for order in orders_db.values():
            if order.get('store_id') != store_id:
                continue
                
            order_dt = datetime.fromisoformat(order.get('created_at', '').replace('Z', '+00:00'))
            if start_date <= order_dt <= end_date:
                period_orders.append(order)
                total_revenue += order.get('total', 0)
                unique_customers.add(order.get('customerPhone', ''))
                status = order.get('status', 'pending')
                status_counts[status] = status_counts.get(status, 0) + 1
                payment = order.get('paymentMethod', 'cash')
                payment_counts[payment] = payment_counts.get(payment, 0) + 1
        
        # Calculate metrics
        total_orders = len(period_orders)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        unique_customer_count = len(unique_customers)
        
        # Calculate growth (mock data for now)
        revenue_growth = 12.5  # Mock percentage
        order_growth = 8.2
        customer_growth = 15.5
        
        logger.info(f"Retrieved analytics overview for store {store_id}")
        
        return {
            "success": True,
            "data": {
                "revenue": {
                    "total": total_revenue,
                    "average": round(avg_order_value, 2),
                    "growth": revenue_growth
                },
                "orders": {
                    "total": total_orders,
                    "status_breakdown": status_counts,
                    "growth": order_growth
                },
                "customers": {
                    "total": unique_customer_count,
                    "new": int(unique_customer_count * 0.3),  # Mock: 30% new
                    "returning": int(unique_customer_count * 0.7),  # Mock: 70% returning
                    "growth": customer_growth
                },
                "payment_methods": payment_counts,
                "period": {
                    "type": period,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving analytics overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics overview: {str(e)}"
        )

@router.get("/products/top", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_top_products(
    store_id: str = Query(..., description="Store identifier"),
    limit: int = Query(10, ge=1, le=50, description="Number of top products"),
    period: str = Query("week", description="Time period")
):
    """
    Get top selling products for a store
    
    Returns products ranked by sales volume and revenue for the specified period.
    """
    try:
        # Calculate date range
        end_date = datetime.now()
        if period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=7)
        
        # Aggregate product sales
        product_sales = {}
        
        for order in orders_db.values():
            if order.get('store_id') != store_id:
                continue
                
            order_dt = datetime.fromisoformat(order.get('created_at', '').replace('Z', '+00:00'))
            if start_date <= order_dt <= end_date:
                for item in order.get('items', []):
                    product_name = item.get('productName', 'Unknown')
                    quantity = item.get('quantity', 0)
                    total = item.get('total', 0)
                    
                    if product_name not in product_sales:
                        product_sales[product_name] = {
                            'sales': 0,
                            'revenue': 0
                        }
                    
                    product_sales[product_name]['sales'] += quantity
                    product_sales[product_name]['revenue'] += total
        
        # Sort by sales and get top products
        sorted_products = sorted(
            product_sales.items(),
            key=lambda x: x[1]['sales'],
            reverse=True
        )[:limit]
        
        # Format response
        top_products = [
            {
                'name': name,
                'sales': data['sales'],
                'revenue': data['revenue']
            }
            for name, data in sorted_products
        ]
        
        logger.info(f"Retrieved top {len(top_products)} products for store {store_id}")
        
        return {
            "success": True,
            "data": top_products,
            "period": period,
            "total_products": len(product_sales)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving top products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve top products: {str(e)}"
        )

@router.get("/customers/insights", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_customer_insights(
    store_id: str = Query(..., description="Store identifier")
):
    """
    Get customer behavior insights
    
    Returns customer analytics including new vs returning customers, frequency, and value.
    """
    try:
        # Get all orders for the store
        store_orders = [
            order for order in orders_db.values()
            if order.get('store_id') == store_id
        ]
        
        # Group orders by customer
        customer_orders = {}
        for order in store_orders:
            customer_phone = order.get('customerPhone', '')
            if customer_phone not in customer_orders:
                customer_orders[customer_phone] = []
            customer_orders[customer_phone].append(order)
        
        # Calculate customer metrics
        total_customers = len(customer_orders)
        customer_frequencies = [len(orders) for orders in customer_orders.values()]
        avg_frequency = sum(customer_frequencies) / total_customers if total_customers > 0 else 0
        
        # Calculate customer value
        customer_values = []
        for orders in customer_orders.values():
            total_value = sum(order.get('total', 0) for order in orders)
            customer_values.append(total_value)
        
        avg_customer_value = sum(customer_values) / total_customers if total_customers > 0 else 0
        
        # Categorize customers
        new_customers = len([freq for freq in customer_frequencies if freq == 1])
        returning_customers = total_customers - new_customers
        
        # Calculate retention rate
        retention_rate = (returning_customers / total_customers * 100) if total_customers > 0 else 0
        
        logger.info(f"Retrieved customer insights for store {store_id}")
        
        return {
            "success": True,
            "data": {
                "total_customers": total_customers,
                "new_customers": new_customers,
                "returning_customers": returning_customers,
                "retention_rate": round(retention_rate, 1),
                "average_frequency": round(avg_frequency, 1),
                "average_customer_value": round(avg_customer_value, 2),
                "customer_distribution": {
                    "new": new_customers,
                    "returning": returning_customers
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error retrieving customer insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer insights: {str(e)}"
        )

@router.get("/revenue/trend", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_revenue_trend(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=30, description="Number of days")
):
    """
    Get revenue trend data for charting
    
    Returns daily revenue data for the specified number of days.
    """
    try:
        # Generate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Initialize daily revenue
        daily_revenue = {}
        current_date = start_date
        while current_date <= end_date:
            daily_revenue[current_date.strftime('%Y-%m-%d')] = 0
            current_date += timedelta(days=1)
        
        # Calculate daily revenue
        for order in orders_db.values():
            if order.get('store_id') != store_id:
                continue
                
            order_dt = datetime.fromisoformat(order.get('created_at', '').replace('Z', '+00:00'))
            if start_date <= order_dt <= end_date:
                date_key = order_dt.strftime('%Y-%m-%d')
                daily_revenue[date_key] += order.get('total', 0)
        
        # Format for chart
        revenue_data = [
            {
                'date': date,
                'revenue': amount
            }
            for date, amount in daily_revenue.items()
        ]
        
        logger.info(f"Retrieved revenue trend for store {store_id} ({days} days)")
        
        return {
            "success": True,
            "data": revenue_data,
            "period": f"{days} days",
            "total_revenue": sum(daily_revenue.values())
        }
        
    except Exception as e:
        logger.error(f"Error retrieving revenue trend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve revenue trend: {str(e)}"
        )

@router.get("/orders/volume", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_order_volume(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=30, description="Number of days")
):
    """
    Get order volume trend data for charting
    
    Returns daily order counts for the specified number of days.
    """
    try:
        # Generate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Initialize daily orders
        daily_orders = {}
        current_date = start_date
        while current_date <= end_date:
            daily_orders[current_date.strftime('%Y-%m-%d')] = 0
            current_date += timedelta(days=1)
        
        # Calculate daily orders
        for order in orders_db.values():
            if order.get('store_id') != store_id:
                continue
                
            order_dt = datetime.fromisoformat(order.get('created_at', '').replace('Z', '+00:00'))
            if start_date <= order_dt <= end_date:
                date_key = order_dt.strftime('%Y-%m-%d')
                daily_orders[date_key] += 1
        
        # Format for chart
        order_data = [
            {
                'date': date,
                'orders': count
            }
            for date, count in daily_orders.items()
        ]
        
        logger.info(f"Retrieved order volume for store {store_id} ({days} days)")
        
        return {
            "success": True,
            "data": order_data,
            "period": f"{days} days",
            "total_orders": sum(daily_orders.values())
        }
        
    except Exception as e:
        logger.error(f"Error retrieving order volume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order volume: {str(e)}"
        )

@router.get("/peak-hours", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_peak_hours(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=30, description="Number of days")
):
    """
    Get peak hours analysis
    
    Returns hourly order distribution to identify peak business hours.
    """
    try:
        # Generate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Initialize hourly counts
        hourly_orders = {hour: 0 for hour in range(24)}
        
        # Calculate hourly distribution
        for order in orders_db.values():
            if order.get('store_id') != store_id:
                continue
                
            order_dt = datetime.fromisoformat(order.get('created_at', '').replace('Z', '+00:00'))
            if start_date <= order_dt <= end_date:
                hour = order_dt.hour
                hourly_orders[hour] += 1
        
        # Format for heatmap
        peak_data = [
            {
                'hour': f"{hour:02d}:00",
                'orders': count,
                'hour_num': hour
            }
            for hour, count in hourly_orders.items()
        ]
        
        # Find peak hours
        max_orders = max(hourly_orders.values())
        peak_hours = [
            f"{hour:02d}:00" for hour, count in hourly_orders.items()
            if count == max_orders
        ]
        
        logger.info(f"Retrieved peak hours for store {store_id}")
        
        return {
            "success": True,
            "data": peak_data,
            "peak_hours": peak_hours,
            "max_orders_per_hour": max_orders,
            "period": f"{days} days"
        }
        
    except Exception as e:
        logger.error(f"Error retrieving peak hours: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve peak hours: {str(e)}"
        )
