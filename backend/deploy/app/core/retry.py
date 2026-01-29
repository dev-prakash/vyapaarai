"""
Retry Configuration for External Services

Provides:
- Configurable retry logic with exponential backoff
- Circuit breaker pattern for failing services
- Timeout configuration for external calls

Usage:
    from app.core.retry import with_retry, RetryConfig

    @with_retry(RetryConfig(max_attempts=3, base_delay=1.0))
    async def call_external_api():
        return await http_client.get(url)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, TypeVar, Optional, Type, Tuple, Any

logger = logging.getLogger(__name__)

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    "RetryConfig",
    "CircuitBreaker",
    "with_retry",
    "with_circuit_breaker",
    "DEFAULT_RETRY_CONFIG",
    "AGGRESSIVE_RETRY_CONFIG",
    "CONSERVATIVE_RETRY_CONFIG",
]

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""

    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[int, Exception], None]] = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number"""
        delay = min(
            self.base_delay * (self.exponential_base ** (attempt - 1)),
            self.max_delay
        )
        if self.jitter:
            import random
            delay *= (0.5 + random.random())
        return delay


# Pre-defined configurations
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
)

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=5.0,
)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker to prevent repeated calls to failing services.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected
    - HALF_OPEN: Testing if service has recovered
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds
    half_open_max_calls: int = 3

    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _state: str = field(default="CLOSED", init=False)
    _half_open_calls: int = field(default=0, init=False)

    @property
    def state(self) -> str:
        """Get current circuit state"""
        if self._state == "OPEN":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "HALF_OPEN"
                self._half_open_calls = 0
        return self._state

    def record_success(self) -> None:
        """Record a successful call"""
        if self._state == "HALF_OPEN":
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = "CLOSED"
                self._failure_count = 0
                logger.info("Circuit breaker closed - service recovered")
        else:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Record a failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "HALF_OPEN":
            self._state = "OPEN"
            logger.warning("Circuit breaker opened - service still failing")
        elif self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures"
            )

    def can_execute(self) -> bool:
        """Check if a request can be executed"""
        state = self.state
        if state == "CLOSED":
            return True
        if state == "HALF_OPEN":
            return True
        return False

    def reset(self) -> None:
        """Reset the circuit breaker"""
        self._failure_count = 0
        self._state = "CLOSED"
        self._half_open_calls = 0


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator to add retry logic to async functions.

    Args:
        config: Retry configuration (uses DEFAULT_RETRY_CONFIG if not provided)

    Example:
        @with_retry(RetryConfig(max_attempts=5))
        async def fetch_data():
            return await client.get(url)
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                        )
                        raise

                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )

                    if config.on_retry:
                        config.on_retry(attempt, e)

                    await asyncio.sleep(delay)

            raise last_exception  # Should never reach here

        return wrapper
    return decorator


def with_circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to add circuit breaker to async functions.

    Args:
        breaker: CircuitBreaker instance

    Example:
        api_breaker = CircuitBreaker(failure_threshold=5)

        @with_circuit_breaker(api_breaker)
        async def call_api():
            return await client.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if not breaker.can_execute():
                raise RuntimeError(
                    f"Circuit breaker is open for {func.__name__}. "
                    f"Try again after {breaker.recovery_timeout}s"
                )

            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        return wrapper
    return decorator
