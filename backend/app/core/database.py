"""
Centralized Database Connection Manager for VyaparAI

Enterprise-grade database connection management with:
- DynamoDB (boto3 with connection pooling, retries, and proper credential handling)
- PostgreSQL (asyncpg connection pool)
- Redis (connection pool)

Key Design Decisions:
1. Uses botocore.config.Config for enterprise features (retries, timeouts, pooling)
2. Does NOT override credential handling - lets boto3's default credential chain work
3. Lambda-compatible: Works with IAM roles via environment variable credentials
4. Singleton pattern for connection reuse across Lambda invocations

AWS Best Practices Applied:
- Standard retry mode (AWS recommended) with exponential backoff
- Connection pooling for high-throughput scenarios
- Proper timeout configuration for Lambda environment
- Initialize clients outside handler for connection reuse

References:
- https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html
- https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html

Usage:
    from app.core.database import db_manager

    # Get DynamoDB resource
    dynamodb = db_manager.get_dynamodb()
    table = dynamodb.Table('vyaparai-orders-prod')

    # Get PostgreSQL pool
    pool = await db_manager.get_postgres_pool()
    async with pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM orders")
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
from functools import lru_cache

import boto3
from botocore.config import Config as BotoConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Enterprise Configuration for AWS SDK
# =============================================================================
# These settings are designed to work correctly with:
# - AWS Lambda IAM role credentials (via environment variables)
# - Local development with ~/.aws/credentials or environment variables
# - EC2 instances with instance profiles
#
# IMPORTANT: We do NOT set any credential-related options in BotoConfig.
# This allows boto3's default credential provider chain to work correctly.
# =============================================================================

def _create_boto_config(
    max_pool_connections: int = 25,
    connect_timeout: int = 5,
    read_timeout: int = 30,
    max_attempts: int = 3,
    retry_mode: str = 'standard'
) -> BotoConfig:
    """
    Create a boto3 Config object with enterprise-grade settings.

    This configuration is Lambda-safe because it:
    1. Does NOT override any credential settings
    2. Uses 'standard' retry mode (AWS recommended)
    3. Sets reasonable timeouts for Lambda's 15-minute limit
    4. Enables connection pooling for performance

    Args:
        max_pool_connections: Maximum connections in the pool (default: 25)
        connect_timeout: Connection timeout in seconds (default: 5)
        read_timeout: Read timeout in seconds (default: 30)
        max_attempts: Maximum retry attempts including initial (default: 3)
        retry_mode: Retry mode - 'legacy', 'standard', or 'adaptive' (default: 'standard')

    Returns:
        BotoConfig object safe to use with Lambda IAM credentials

    Note:
        - 'standard' mode is recommended by AWS for production use
        - 'adaptive' mode is experimental and not recommended for multi-tenant apps
        - 'legacy' mode is deprecated but still the default if not specified
    """
    return BotoConfig(
        # Connection pool settings - improves performance for high-throughput
        max_pool_connections=max_pool_connections,

        # Timeout settings - prevent hanging requests
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,

        # Retry configuration with AWS recommended 'standard' mode
        # Standard mode provides:
        # - Jittered exponential backoff
        # - Transient error handling
        # - Max 20-second delay between retries
        retries={
            'max_attempts': max_attempts,
            'mode': retry_mode
        }

        # INTENTIONALLY NOT SETTING:
        # - region_name: Let boto3 get from AWS_REGION env var
        # - signature_version: Let boto3 auto-detect
        # - Any credential-related options
    )


class DatabaseManager:
    """
    Enterprise-grade centralized database connection manager.

    Features:
    - Singleton pattern for connection reuse across Lambda invocations
    - Connection pooling (25 connections for DynamoDB)
    - AWS-recommended 'standard' retry mode with exponential backoff
    - Proper timeout configuration
    - Lambda IAM role compatible (no credential overrides)

    Thread Safety:
    - DynamoDB clients are thread-safe
    - DynamoDB resources are NOT thread-safe (use client for multi-threaded code)
    - PostgreSQL pool handles its own thread safety
    """

    _instance: Optional['DatabaseManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._dynamodb_resource: Optional[Any] = None
        self._dynamodb_client: Optional[Any] = None
        self._postgres_pool: Optional[Any] = None
        self._redis_client: Optional[Any] = None
        self._boto_config: Optional[BotoConfig] = None

        # Configuration from environment
        self._aws_region = os.getenv('AWS_REGION', 'ap-south-1')
        self._dynamodb_endpoint = os.getenv('DYNAMODB_ENDPOINT')

        # Enterprise configuration settings (can be overridden via env vars)
        self._max_pool_connections = int(os.getenv('BOTO_MAX_POOL_CONNECTIONS', '25'))
        self._connect_timeout = int(os.getenv('BOTO_CONNECT_TIMEOUT', '5'))
        self._read_timeout = int(os.getenv('BOTO_READ_TIMEOUT', '30'))
        self._max_retry_attempts = int(os.getenv('BOTO_MAX_RETRY_ATTEMPTS', '3'))
        self._retry_mode = os.getenv('BOTO_RETRY_MODE', 'standard')

        # Initialize connections with enterprise config
        self._init_boto_config()
        self._init_dynamodb()

        logger.info(
            f"DatabaseManager initialized: region={self._aws_region}, "
            f"pool_size={self._max_pool_connections}, retry_mode={self._retry_mode}"
        )

    def _init_boto_config(self):
        """
        Initialize the enterprise boto3 configuration.

        Creates a BotoConfig with:
        - Connection pooling for performance
        - Standard retry mode (AWS recommended)
        - Proper timeouts

        IMPORTANT: Does NOT set region or credentials in config.
        Region is passed separately; credentials come from default chain.
        """
        self._boto_config = _create_boto_config(
            max_pool_connections=self._max_pool_connections,
            connect_timeout=self._connect_timeout,
            read_timeout=self._read_timeout,
            max_attempts=self._max_retry_attempts,
            retry_mode=self._retry_mode
        )
        logger.debug(
            f"Boto config created: pool={self._max_pool_connections}, "
            f"timeout={self._connect_timeout}/{self._read_timeout}s, "
            f"retries={self._max_retry_attempts} ({self._retry_mode})"
        )

    def _init_dynamodb(self):
        """
        Initialize DynamoDB resource and client with enterprise configuration.

        Key Design:
        - region_name is passed as a separate kwarg (NOT in BotoConfig)
        - config object contains only non-credential settings
        - Credentials come from boto3's default provider chain:
          1. Environment variables (AWS_ACCESS_KEY_ID, etc.) - used by Lambda
          2. Shared credentials file (~/.aws/credentials)
          3. AWS config file (~/.aws/config)
          4. IAM role for EC2/ECS (IMDS)

        This separation is critical for Lambda compatibility.
        """
        try:
            # Build kwargs - region is separate from config
            kwargs = {
                'region_name': self._aws_region,
                'config': self._boto_config
            }

            # Use local endpoint if specified (for development with DynamoDB Local)
            if self._dynamodb_endpoint:
                kwargs['endpoint_url'] = self._dynamodb_endpoint
                logger.info(f"Using local DynamoDB endpoint: {self._dynamodb_endpoint}")

            # Create DynamoDB resource and client
            # Both use the same config for consistent behavior
            self._dynamodb_resource = boto3.resource('dynamodb', **kwargs)
            self._dynamodb_client = boto3.client('dynamodb', **kwargs)

            logger.info(
                f"DynamoDB initialized: region={self._aws_region}, "
                f"endpoint={'local' if self._dynamodb_endpoint else 'aws'}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize DynamoDB: {e}", exc_info=True)
            self._dynamodb_resource = None
            self._dynamodb_client = None

    async def init_postgres_pool(self):
        """Initialize PostgreSQL connection pool"""
        try:
            import asyncpg

            host = os.getenv('RDS_HOSTNAME')
            port = int(os.getenv('RDS_PORT', '5432'))
            database = os.getenv('RDS_DATABASE', 'vyaparai')
            username = os.getenv('RDS_USERNAME')
            password = os.getenv('RDS_PASSWORD')

            if not all([host, username, password]):
                logger.warning("PostgreSQL environment variables not set, pool will not be created")
                return

            # Connection pool configuration
            self._postgres_pool = await asyncpg.create_pool(
                host=host,
                port=port,
                database=database,
                user=username,
                password=password,
                min_size=5,           # Minimum connections in pool
                max_size=20,          # Maximum connections in pool
                max_inactive_connection_lifetime=300,  # Close idle connections after 5 min
                command_timeout=30,   # Query timeout
                statement_cache_size=100  # Cache prepared statements
            )

            logger.info("PostgreSQL connection pool initialized (min=5, max=20)")

        except ImportError:
            logger.warning("asyncpg not installed, PostgreSQL pool will not be available")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            self._postgres_pool = None

    async def init_redis(self):
        """Initialize Redis connection pool"""
        try:
            import redis.asyncio as redis

            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

            self._redis_client = redis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                max_connections=20
            )

            # Test connection
            await self._redis_client.ping()

            logger.info("Redis connection pool initialized (max=20)")

        except ImportError:
            logger.warning("redis-py not installed, Redis pool will not be available")
        except Exception as e:
            logger.error(f"Failed to initialize Redis pool: {e}")
            self._redis_client = None

    def get_dynamodb(self) -> Optional[Any]:
        """
        Get the shared DynamoDB resource.

        Returns:
            boto3 DynamoDB resource with connection pooling
        """
        if not self._dynamodb_resource:
            logger.warning("DynamoDB resource not initialized")
        return self._dynamodb_resource

    def get_dynamodb_client(self) -> Optional[Any]:
        """
        Get the shared DynamoDB client.

        Returns:
            boto3 DynamoDB client with connection pooling
        """
        if not self._dynamodb_client:
            logger.warning("DynamoDB client not initialized")
        return self._dynamodb_client

    def get_table(self, table_name: str):
        """
        Get a DynamoDB table reference.

        Args:
            table_name: Name of the DynamoDB table

        Returns:
            DynamoDB Table resource
        """
        if not self._dynamodb_resource:
            raise RuntimeError("DynamoDB not initialized")
        return self._dynamodb_resource.Table(table_name)

    async def get_postgres_pool(self):
        """
        Get the PostgreSQL connection pool.

        Returns:
            asyncpg connection pool
        """
        if not self._postgres_pool:
            await self.init_postgres_pool()
        return self._postgres_pool

    async def get_redis(self):
        """
        Get the Redis client with connection pool.

        Returns:
            Redis client
        """
        if not self._redis_client:
            await self.init_redis()
        return self._redis_client

    async def close(self):
        """Close all database connections"""
        logger.info("Closing database connections...")

        if self._postgres_pool:
            await self._postgres_pool.close()
            logger.info("PostgreSQL pool closed")

        if self._redis_client:
            await self._redis_client.close()
            logger.info("Redis connection closed")

        # Note: boto3 handles its own connection cleanup
        logger.info("All database connections closed")

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of all database connections.

        Returns:
            Dictionary with health status of each connection
        """
        health = {
            "dynamodb": self._dynamodb_resource is not None,
            "postgres_pool": self._postgres_pool is not None,
            "redis": self._redis_client is not None
        }

        if self._postgres_pool:
            health["postgres_pool_size"] = self._postgres_pool.get_size()
            health["postgres_pool_free"] = self._postgres_pool.get_idle_size()

        return health

    async def verify_connections_at_startup(self, fail_on_error: bool = True) -> Dict[str, Any]:
        """
        Verify all database connections are working at application startup.

        This method should be called during app startup to ensure all
        critical database connections are functional before serving traffic.

        Args:
            fail_on_error: If True, raise RuntimeError on critical failures

        Returns:
            Dictionary with verification results for each connection

        Raises:
            RuntimeError: If fail_on_error=True and critical connection fails
        """
        logger.info("Verifying database connections at startup...")

        results = {
            "dynamodb": {"status": "unknown", "verified": False},
            "postgres": {"status": "unknown", "verified": False},
            "redis": {"status": "unknown", "verified": False},
            "overall": {"status": "unknown", "critical_failures": 0}
        }

        critical_failures = 0

        # Verify DynamoDB (CRITICAL)
        if self._dynamodb_client:
            try:
                # Perform actual API call to verify connectivity
                tables = self._dynamodb_client.list_tables(Limit=1)
                results["dynamodb"] = {
                    "status": "healthy",
                    "verified": True,
                    "message": "DynamoDB connection verified"
                }
                logger.info("✅ DynamoDB connection verified")
            except Exception as e:
                results["dynamodb"] = {
                    "status": "unhealthy",
                    "verified": False,
                    "error": str(e)
                }
                critical_failures += 1
                logger.error(f"❌ DynamoDB verification failed: {e}")
        else:
            results["dynamodb"] = {
                "status": "not_initialized",
                "verified": False,
                "error": "DynamoDB client not initialized"
            }
            critical_failures += 1
            logger.error("❌ DynamoDB client not initialized")

        # Verify PostgreSQL (if configured)
        try:
            pool = await self.get_postgres_pool()
            if pool:
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                results["postgres"] = {
                    "status": "healthy",
                    "verified": True,
                    "pool_size": pool.get_size(),
                    "pool_free": pool.get_idle_size()
                }
                logger.info(f"✅ PostgreSQL connection verified (pool: {pool.get_size()})")
            else:
                results["postgres"] = {
                    "status": "not_configured",
                    "verified": False,
                    "message": "PostgreSQL not configured"
                }
                logger.info("ℹ️ PostgreSQL not configured")
        except Exception as e:
            results["postgres"] = {
                "status": "unhealthy",
                "verified": False,
                "error": str(e)
            }
            logger.warning(f"⚠️ PostgreSQL verification failed: {e}")

        # Verify Redis (optional)
        try:
            redis_client = await self.get_redis()
            if redis_client:
                await redis_client.ping()
                results["redis"] = {
                    "status": "healthy",
                    "verified": True,
                    "message": "Redis connection verified"
                }
                logger.info("✅ Redis connection verified")
            else:
                results["redis"] = {
                    "status": "not_configured",
                    "verified": False,
                    "message": "Redis not configured"
                }
                logger.info("ℹ️ Redis not configured")
        except Exception as e:
            results["redis"] = {
                "status": "unhealthy",
                "verified": False,
                "error": str(e)
            }
            logger.warning(f"⚠️ Redis verification failed (non-critical): {e}")

        # Set overall status
        results["overall"]["critical_failures"] = critical_failures
        if critical_failures == 0:
            results["overall"]["status"] = "healthy"
            logger.info("✅ All critical database connections verified")
        else:
            results["overall"]["status"] = "unhealthy"
            logger.error(f"❌ {critical_failures} critical connection(s) failed verification")

            if fail_on_error:
                raise RuntimeError(
                    f"Database startup verification failed: {critical_failures} critical failure(s). "
                    f"Details: {results}"
                )

        return results

    def get_pool_metrics(self) -> Dict[str, Any]:
        """
        Get detailed connection pool metrics for monitoring.

        Returns:
            Dictionary with pool statistics for each connection type
        """
        metrics = {
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            "dynamodb": {
                "initialized": self._dynamodb_resource is not None,
                "region": self._aws_region,
                "endpoint": self._dynamodb_endpoint or "aws-default",
                "max_pool_connections": self._max_pool_connections,
                "connect_timeout_seconds": self._connect_timeout,
                "read_timeout_seconds": self._read_timeout,
                "retry_mode": self._retry_mode,
                "max_retry_attempts": self._max_retry_attempts,
            },
            "postgres": {
                "initialized": self._postgres_pool is not None,
            },
            "redis": {
                "initialized": self._redis_client is not None,
            }
        }

        # PostgreSQL pool metrics
        if self._postgres_pool:
            try:
                metrics["postgres"].update({
                    "pool_size": self._postgres_pool.get_size(),
                    "pool_free": self._postgres_pool.get_idle_size(),
                    "pool_used": self._postgres_pool.get_size() - self._postgres_pool.get_idle_size(),
                    "pool_min": 5,
                    "pool_max": 20,
                    "utilization_percent": round(
                        (self._postgres_pool.get_size() - self._postgres_pool.get_idle_size())
                        / 20 * 100, 2
                    )
                })
            except Exception as e:
                logger.warning(f"Failed to get PostgreSQL pool metrics: {e}")
                metrics["postgres"]["error"] = str(e)

        # Redis metrics (if available)
        if self._redis_client:
            try:
                # Note: Getting Redis pool info requires the connection pool attribute
                metrics["redis"].update({
                    "max_connections": 20,  # From init config
                })
            except Exception as e:
                logger.warning(f"Failed to get Redis metrics: {e}")
                metrics["redis"]["error"] = str(e)

        return metrics


# Singleton instance - initialize at import time
# This ensures DynamoDB is ready when modules are loaded
# Import-time initialization works well in Lambda since credentials are available at INIT phase
_db_manager_instance: DatabaseManager = DatabaseManager()


def _get_db_manager() -> DatabaseManager:
    """
    Get the DatabaseManager singleton.
    Returns the instance initialized at module import time.
    """
    return _db_manager_instance


# Convenience functions for backward compatibility
def get_dynamodb():
    """Get the shared DynamoDB resource"""
    return _get_db_manager().get_dynamodb()


def get_dynamodb_client():
    """Get the shared DynamoDB client"""
    return _get_db_manager().get_dynamodb_client()


def get_table(table_name: str):
    """Get a DynamoDB table reference"""
    return _get_db_manager().get_table(table_name)


async def get_postgres_pool():
    """Get the PostgreSQL connection pool"""
    return await _get_db_manager().get_postgres_pool()


async def get_redis():
    """Get the Redis client"""
    return await _get_db_manager().get_redis()


# Backward compatibility: export db_manager as a lazy property
# This allows code that imports `from app.core.database import db_manager` to work
# while still using lazy initialization
class _LazyDbManager:
    """Lazy proxy for DatabaseManager that initializes on first access."""

    def __getattr__(self, name):
        return getattr(_get_db_manager(), name)


db_manager = _LazyDbManager()


# Table name constants (from environment or defaults)
# Note: Defaults use -prod suffix to match deployed Lambda configuration
ORDERS_TABLE = os.getenv('DYNAMODB_ORDERS_TABLE', 'vyaparai-orders-prod')
STORES_TABLE = os.getenv('DYNAMODB_STORES_TABLE', 'vyaparai-stores-prod')
SESSIONS_TABLE = os.getenv('DYNAMODB_SESSIONS_TABLE', 'vyaparai-sessions-prod')
CUSTOMERS_TABLE = os.getenv('DYNAMODB_CUSTOMERS_TABLE', 'vyaparai-customers-prod')
USERS_TABLE = os.getenv('DYNAMODB_USERS_TABLE', 'vyaparai-users-prod')
CART_TABLE = os.getenv('DYNAMODB_CART_TABLE', 'vyaparai-carts-prod')
INVENTORY_TABLE = os.getenv('DYNAMODB_INVENTORY_TABLE', 'vyaparai-inventory-prod')
PRODUCTS_TABLE = os.getenv('DYNAMODB_PRODUCTS_TABLE', 'vyaparai-products-prod')
