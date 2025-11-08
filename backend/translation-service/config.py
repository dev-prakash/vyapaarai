"""
Cost Control Configuration for Translation Service

This module provides feature flags to control costs during development/testing.
You can enable/disable expensive features via environment variables.
"""

import os
from enum import Enum


class TranslationMode(str, Enum):
    """Translation service operating modes"""
    DISABLED = "disabled"           # Return English only (FREE)
    MOCK = "mock"                   # Return fake translations (FREE)
    CACHE_ONLY = "cache_only"       # Only use cached translations (CHEAP)
    FULL = "full"                   # Use Amazon Translate API (NORMAL COST)


class CostControlConfig:
    """
    Cost control configuration with feature flags

    Set via environment variables to control costs during testing
    """

    # ==================== MASTER SWITCH ====================

    TRANSLATION_MODE = os.environ.get(
        'TRANSLATION_MODE',
        TranslationMode.FULL.value
    )

    # ==================== FEATURE FLAGS ====================

    # Enable/disable actual Amazon Translate API calls
    ENABLE_AMAZON_TRANSLATE = os.environ.get(
        'ENABLE_AMAZON_TRANSLATE',
        'true'
    ).lower() == 'true'

    # Enable/disable translation caching
    ENABLE_CACHE = os.environ.get(
        'ENABLE_CACHE',
        'true'
    ).lower() == 'true'

    # Enable/disable CloudWatch metrics (costs $0.30 per metric)
    ENABLE_CLOUDWATCH_METRICS = os.environ.get(
        'ENABLE_CLOUDWATCH_METRICS',
        'false'  # Default OFF for testing
    ).lower() == 'true'

    # Enable/disable detailed JSON logging (costs ~$3/month)
    ENABLE_DETAILED_LOGGING = os.environ.get(
        'ENABLE_DETAILED_LOGGING',
        'false'  # Default OFF for testing
    ).lower() == 'true'

    # ==================== COST LIMITS ====================

    # Maximum translation requests per day (prevents runaway costs)
    MAX_TRANSLATIONS_PER_DAY = int(os.environ.get(
        'MAX_TRANSLATIONS_PER_DAY',
        '1000'  # 1000 requests = ~$0.50/day max
    ))

    # Maximum API cost per day in dollars (safety limit)
    MAX_DAILY_COST_USD = float(os.environ.get(
        'MAX_DAILY_COST_USD',
        '5.00'  # $5/day max
    ))

    # ==================== TESTING CONTROLS ====================

    # Whitelist of emails/users who can use translation (empty = all allowed)
    ALLOWED_TEST_USERS = os.environ.get(
        'ALLOWED_TEST_USERS',
        ''  # Empty = allow everyone
    ).split(',')

    # Allowed languages (reduce to save costs during testing)
    ALLOWED_LANGUAGES = os.environ.get(
        'ALLOWED_LANGUAGES',
        'en,hi,mr'  # Only 3 languages during testing
    ).split(',')

    # ==================== MOCK TRANSLATIONS ====================

    # Use mock translations instead of real API (FREE)
    MOCK_TRANSLATIONS = {
        'hi': {
            'Tata Salt': 'टाटा नमक [MOCK]',
            'Premium iodized salt': 'प्रीमियम आयोडीन युक्त नमक [MOCK]',
            'Grocery': 'किराना [MOCK]'
        },
        'mr': {
            'Tata Salt': 'टाटा मीठ [MOCK]',
            'Premium iodized salt': 'प्रीमियम आयोडीन युक्त मीठ [MOCK]',
            'Grocery': 'किराणा माल [MOCK]'
        }
    }

    # ==================== HELPER METHODS ====================

    @staticmethod
    def is_translation_enabled() -> bool:
        """Check if translations are enabled"""
        return CostControlConfig.TRANSLATION_MODE != TranslationMode.DISABLED.value

    @staticmethod
    def should_use_amazon_translate() -> bool:
        """Check if we should call Amazon Translate API"""
        return (
            CostControlConfig.TRANSLATION_MODE == TranslationMode.FULL.value
            and CostControlConfig.ENABLE_AMAZON_TRANSLATE
        )

    @staticmethod
    def should_use_mock() -> bool:
        """Check if we should use mock translations"""
        return CostControlConfig.TRANSLATION_MODE == TranslationMode.MOCK.value

    @staticmethod
    def should_use_cache_only() -> bool:
        """Check if we should only use cached translations"""
        return CostControlConfig.TRANSLATION_MODE == TranslationMode.CACHE_ONLY.value

    @staticmethod
    def is_language_allowed(lang_code: str) -> bool:
        """Check if language is in allowed list"""
        if not CostControlConfig.ALLOWED_LANGUAGES or CostControlConfig.ALLOWED_LANGUAGES == ['']:
            return True
        return lang_code in CostControlConfig.ALLOWED_LANGUAGES

    @staticmethod
    def is_user_allowed(user_email: str) -> bool:
        """Check if user is in allowed test users"""
        if not CostControlConfig.ALLOWED_TEST_USERS or CostControlConfig.ALLOWED_TEST_USERS == ['']:
            return True  # All users allowed
        return user_email in CostControlConfig.ALLOWED_TEST_USERS

    @staticmethod
    def get_daily_translation_limit() -> int:
        """Get daily translation limit"""
        return CostControlConfig.MAX_TRANSLATIONS_PER_DAY

    @staticmethod
    def get_cost_info() -> dict:
        """Get current cost control configuration"""
        return {
            'translation_mode': CostControlConfig.TRANSLATION_MODE,
            'amazon_translate_enabled': CostControlConfig.ENABLE_AMAZON_TRANSLATE,
            'cache_enabled': CostControlConfig.ENABLE_CACHE,
            'metrics_enabled': CostControlConfig.ENABLE_CLOUDWATCH_METRICS,
            'detailed_logging_enabled': CostControlConfig.ENABLE_DETAILED_LOGGING,
            'max_translations_per_day': CostControlConfig.MAX_TRANSLATIONS_PER_DAY,
            'max_daily_cost_usd': CostControlConfig.MAX_DAILY_COST_USD,
            'allowed_languages': CostControlConfig.ALLOWED_LANGUAGES,
            'estimated_daily_cost': CostControlConfig._estimate_daily_cost()
        }

    @staticmethod
    def _estimate_daily_cost() -> float:
        """Estimate daily cost based on current config"""
        cost = 0.0

        # Lambda (always running)
        cost += 0.01

        # DynamoDB (always running)
        cost += 0.01

        # Translation API
        if CostControlConfig.should_use_amazon_translate():
            # Assume 3 fields per product, 100 chars each
            chars_per_request = 300
            daily_chars = CostControlConfig.MAX_TRANSLATIONS_PER_DAY * chars_per_request
            cost += (daily_chars / 1_000_000) * 15  # $15 per 1M chars

        # CloudWatch metrics
        if CostControlConfig.ENABLE_CLOUDWATCH_METRICS:
            cost += 0.10

        # Detailed logging
        if CostControlConfig.ENABLE_DETAILED_LOGGING:
            cost += 0.05

        return round(cost, 2)


# ==================== USAGE TRACKER ====================

class UsageTracker:
    """Track daily usage to enforce limits (uses DynamoDB)"""

    def __init__(self):
        self.today_key = self._get_today_key()
        self.translation_count = 0
        self.estimated_cost = 0.0

    def _get_today_key(self) -> str:
        """Get today's date key"""
        from datetime import datetime
        return datetime.utcnow().strftime('%Y-%m-%d')

    async def increment_translation_count(self, chars_translated: int = 300):
        """Increment translation count and cost"""
        self.translation_count += 1

        # Calculate cost (Amazon Translate: $15 per 1M chars)
        char_cost = (chars_translated / 1_000_000) * 15
        self.estimated_cost += char_cost

        # Check limits
        if self.translation_count > CostControlConfig.MAX_TRANSLATIONS_PER_DAY:
            raise Exception(f"Daily translation limit exceeded: {CostControlConfig.MAX_TRANSLATIONS_PER_DAY}")

        if self.estimated_cost > CostControlConfig.MAX_DAILY_COST_USD:
            raise Exception(f"Daily cost limit exceeded: ${CostControlConfig.MAX_DAILY_COST_USD}")

    def get_usage_stats(self) -> dict:
        """Get current usage statistics"""
        return {
            'date': self.today_key,
            'translation_count': self.translation_count,
            'estimated_cost_usd': round(self.estimated_cost, 2),
            'remaining_translations': CostControlConfig.MAX_TRANSLATIONS_PER_DAY - self.translation_count,
            'remaining_budget_usd': round(CostControlConfig.MAX_DAILY_COST_USD - self.estimated_cost, 2),
            'usage_percentage': round((self.translation_count / CostControlConfig.MAX_TRANSLATIONS_PER_DAY) * 100, 1)
        }


# Global usage tracker instance
usage_tracker = UsageTracker()
