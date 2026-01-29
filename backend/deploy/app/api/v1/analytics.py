"""
Analytics API endpoints for VyaparAI
Provides comprehensive analytics and reporting functionality

MVP Reports:
1. Today's Sales Summary - GET /analytics/today
2. Revenue Trend - GET /analytics/revenue/trend
3. Top Products - GET /analytics/products/top
4. Low Stock Alerts - GET /analytics/inventory/low-stock
5. Order Status Distribution - GET /analytics/orders/status
6. Payment Method Analysis - GET /analytics/payments
7. Daily Order Volume - GET /analytics/orders/volume
8. Top Customers - GET /analytics/customers/top
9. Category Performance - GET /analytics/categories
10. Peak Hours Analysis - GET /analytics/peak-hours
"""

import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Query

from app.core.cache import cache_result
from app.services.analytics_service import analytics_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=300, key_prefix="analytics_overview")  # Cache for 5 minutes
async def get_analytics_overview(
    store_id: str = Query(..., description="Store identifier"),
    period: str = Query("week", description="Time period: today, week, month")
):
    """
    Get comprehensive analytics overview for dashboard

    Returns combined metrics including:
    - Today's summary
    - Revenue trend
    - Top products
    - Low stock alerts
    - Order status distribution
    """
    try:
        result = await analytics_service.get_analytics_overview(store_id, period)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve analytics overview"
            )

        logger.info(f"Analytics overview retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving analytics overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve analytics overview: {str(e)}"
        )


@router.get("/today", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=60, key_prefix="analytics_today")  # Cache for 1 minute (real-time feel)
async def get_todays_summary(
    store_id: str = Query(..., description="Store identifier")
):
    """
    Report 1: Today's Sales Summary

    Returns real-time KPIs for today:
    - Total revenue with INR formatting
    - Order count and status breakdown
    - Average order value
    - Payment method breakdown
    - Comparison with yesterday
    """
    try:
        result = await analytics_service.get_todays_summary(store_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve today's summary"
            )

        logger.info(f"Today's summary retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving today's summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve today's summary: {str(e)}"
        )


@router.get("/revenue/trend", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_revenue")  # Cache for 10 minutes
async def get_revenue_trend(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=90, description="Number of days (1-90)")
):
    """
    Report 2: Revenue Trend

    Returns daily revenue data for charting:
    - Date-wise revenue
    - Order counts per day
    - Formatted values for Indian currency
    - Summary statistics
    """
    try:
        result = await analytics_service.get_revenue_trend(store_id, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve revenue trend"
            )

        logger.info(f"Revenue trend retrieved for store {store_id} ({days} days)")
        return result

    except Exception as e:
        logger.error(f"Error retrieving revenue trend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve revenue trend: {str(e)}"
        )


@router.get("/products/top", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_top_products")
async def get_top_products(
    store_id: str = Query(..., description="Store identifier"),
    limit: int = Query(10, ge=1, le=50, description="Number of top products (1-50)"),
    days: int = Query(7, ge=1, le=90, description="Period in days")
):
    """
    Report 3: Top Selling Products

    Returns products ranked by sales:
    - Product name and rank
    - Quantity sold
    - Revenue generated
    - Formatted currency values
    """
    try:
        result = await analytics_service.get_top_products(store_id, limit, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve top products"
            )

        logger.info(f"Top {limit} products retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving top products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve top products: {str(e)}"
        )


@router.get("/inventory/low-stock", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=300, key_prefix="analytics_low_stock")  # Cache for 5 minutes
async def get_low_stock_alerts(
    store_id: str = Query(..., description="Store identifier"),
    threshold: int = Query(20, ge=1, le=100, description="Stock threshold percentage")
):
    """
    Report 4: Low Stock Alerts

    Returns products with stock below threshold:
    - Product details
    - Current stock level
    - Min/Max stock levels
    - Stock percentage
    - Critical vs low status
    - Suggested reorder quantity
    """
    try:
        result = await analytics_service.get_low_stock_alerts(store_id, threshold)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve low stock alerts"
            )

        logger.info(f"Low stock alerts retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving low stock alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve low stock alerts: {str(e)}"
        )


@router.get("/orders/status", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=300, key_prefix="analytics_order_status")
async def get_order_status_distribution(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=90, description="Period in days")
):
    """
    Report 5: Order Status Distribution

    Returns order breakdown by status:
    - Status name
    - Order count
    - Percentage of total
    - Revenue per status
    """
    try:
        result = await analytics_service.get_order_status_distribution(store_id, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve order status distribution"
            )

        logger.info(f"Order status distribution retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving order status distribution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order status distribution: {str(e)}"
        )


@router.get("/payments", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_payments")
async def get_payment_method_analysis(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=90, description="Period in days")
):
    """
    Report 6: Payment Method Analysis

    Returns payment method breakdown:
    - Method name (UPI, Card, COD, Wallet)
    - Order count per method
    - Revenue per method
    - Percentage share
    """
    try:
        result = await analytics_service.get_payment_method_analysis(store_id, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve payment method analysis"
            )

        logger.info(f"Payment method analysis retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving payment method analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment method analysis: {str(e)}"
        )


@router.get("/orders/volume", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_order_volume")
async def get_order_volume(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=90, description="Number of days")
):
    """
    Report 7: Daily Order Volume

    Returns daily order counts:
    - Date and day name
    - Order count per day
    - Summary with peak day
    - Average daily orders
    """
    try:
        result = await analytics_service.get_daily_order_volume(store_id, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve order volume"
            )

        logger.info(f"Order volume retrieved for store {store_id} ({days} days)")
        return result

    except Exception as e:
        logger.error(f"Error retrieving order volume: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve order volume: {str(e)}"
        )


@router.get("/customers/top", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_top_customers")
async def get_top_customers(
    store_id: str = Query(..., description="Store identifier"),
    limit: int = Query(10, ge=1, le=50, description="Number of top customers"),
    days: int = Query(30, ge=1, le=365, description="Period in days")
):
    """
    Report 8: Top Customers

    Returns customers ranked by spend:
    - Customer name/ID
    - Total orders
    - Total spent (INR formatted)
    - Average order value
    - Last order date
    """
    try:
        result = await analytics_service.get_top_customers(store_id, limit, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve top customers"
            )

        logger.info(f"Top {limit} customers retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving top customers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve top customers: {str(e)}"
        )


@router.get("/categories", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_categories")
async def get_category_performance(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=90, description="Period in days")
):
    """
    Report 9: Category Performance

    Returns sales by product category:
    - Category name
    - Quantity sold
    - Revenue generated
    - Revenue share percentage
    - Order count
    """
    try:
        result = await analytics_service.get_category_performance(store_id, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve category performance"
            )

        logger.info(f"Category performance retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving category performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve category performance: {str(e)}"
        )


@router.get("/peak-hours", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
@cache_result(expiry=600, key_prefix="analytics_peak_hours")
async def get_peak_hours(
    store_id: str = Query(..., description="Store identifier"),
    days: int = Query(7, ge=1, le=30, description="Period in days")
):
    """
    Report 10: Peak Hours Analysis

    Returns hourly order distribution:
    - Hour of day (0-23)
    - Order count
    - Revenue per hour
    - Peak hour identification
    - Business pattern analysis (morning/afternoon/evening/night)
    """
    try:
        result = await analytics_service.get_peak_hours_analysis(store_id, days)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve peak hours"
            )

        logger.info(f"Peak hours analysis retrieved for store {store_id}")
        return result

    except Exception as e:
        logger.error(f"Error retrieving peak hours: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve peak hours: {str(e)}"
        )


# Legacy endpoints for backward compatibility
@router.get("/customers/insights", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def get_customer_insights(
    store_id: str = Query(..., description="Store identifier")
):
    """
    Legacy: Get customer behavior insights
    Redirects to top customers with extended metrics
    """
    return await get_top_customers(store_id=store_id, limit=20, days=30)
